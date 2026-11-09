"""One camera module = published lens + sampled mechanical errors + autofocus.

Everything the rest of the pipeline needs lives here: the evaluation fields, the
tolerance table (with the GD&T hand calcs that size it, see METHOD.md section 3),
sampling, and `simulate(x)` which ray-traces one module and returns its MTFs at
autofocus best focus.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from functools import lru_cache

import numpy as np

from .lens import Perturbation, build_optic, load_prescription
from .mtf import FREQS, ModuleWavefronts

HFOV = 39.5  # deg, published
N_GRID = 40

# ---- evaluation fields: centre, 4 mid-field points on the axes, 4 corners ----------
MID_REL, CORNER_REL = 0.5, 0.7


def _diag(rel, sx, sy):
    t = math.tan(math.radians(rel * HFOV)) / math.sqrt(2)  # Optiland composes tan(fx), tan(fy)
    a = math.degrees(math.atan(t))
    return (sx * a, sy * a)


FIELD_NAMES = ["C", "M+x", "M-x", "M+y", "M-y", "K++", "K-+", "K--", "K+-"]
FIELDS = [(0.0, 0.0),
          (MID_REL * HFOV, 0.0), (-MID_REL * HFOV, 0.0), (0.0, MID_REL * HFOV), (0.0, -MID_REL * HFOV),
          _diag(CORNER_REL, 1, 1), _diag(CORNER_REL, -1, 1), _diag(CORNER_REL, -1, -1), _diag(CORNER_REL, 1, -1)]
CORNERS = [5, 6, 7, 8]
MIDS = [1, 2, 3, 4]


# ---- tolerance table -------------------------------------------------------------------
@dataclass(frozen=True)
class Tol:
    name: str        # e.g. "L3 dx"
    group: str       # culprit group used by the diagnosis model
    attr: str        # Perturbation attribute
    index: int       # array index (-1 for scalars)
    limit: float     # +/- limit in the attribute's unit (mm or deg)
    unit: str
    callout: str     # drawing callout it comes from


def _tols(n_elem=6, dec_um=2.0, tilt_deg=0.03, ct_um=3.0, gap_um=3.0, barrel_dec_um=20.0,
          barrel_tilt_deg=0.08, sensor_tilt_deg=0.05):
    out = []
    for e in range(n_elem):
        L = f"L{e + 1}"
        out += [Tol(f"{L} dx", f"{L} decenter", "elem_dx", e, dec_um * 1e-3, "mm", f"{L} OD-to-optical-axis concentricity + interlock fit"),
                Tol(f"{L} dy", f"{L} decenter", "elem_dy", e, dec_um * 1e-3, "mm", f"{L} OD-to-optical-axis concentricity + interlock fit"),
                Tol(f"{L} tx", f"{L} tilt", "elem_tx", e, tilt_deg, "deg", f"{L} flange flatness / parallelism"),
                Tol(f"{L} ty", f"{L} tilt", "elem_ty", e, tilt_deg, "deg", f"{L} flange flatness / parallelism"),
                Tol(f"{L} ct", f"{L} thickness", "elem_dt", e, ct_um * 1e-3, "mm", f"{L} centre thickness")]
    for g in range(n_elem - 1):
        out.append(Tol(f"G{g + 1}{g + 2} gap", "spacing", "gap_dt", g, gap_um * 1e-3, "mm", f"L{g + 1}-L{g + 2} spacer / seat height"))
    out += [Tol("Barrel dx", "barrel decenter", "barrel_dx", -1, barrel_dec_um * 1e-3, "mm", "holder bore position"),
            Tol("Barrel dy", "barrel decenter", "barrel_dy", -1, barrel_dec_um * 1e-3, "mm", "holder bore position"),
            Tol("Barrel tx", "image-plane tilt", "barrel_tx", -1, barrel_tilt_deg, "deg", "holder seat perpendicularity + bondline wedge"),
            Tol("Barrel ty", "image-plane tilt", "barrel_ty", -1, barrel_tilt_deg, "deg", "holder seat perpendicularity + bondline wedge"),
            Tol("Sensor tx", "image-plane tilt", "sensor_tx", -1, sensor_tilt_deg, "deg", "die-attach bondline wedge"),
            Tol("Sensor ty", "image-plane tilt", "sensor_ty", -1, sensor_tilt_deg, "deg", "die-attach bondline wedge")]
    return out


TOLS = _tols()
NAMES = [t.name for t in TOLS]
LIMITS = np.array([t.limit for t in TOLS])
DIM = len(TOLS)
_RX_PATH = None


def configure(rx_path=None, tol_csv=None):
    """Point the module at another prescription (same JSON format) and/or tolerance CSV
    (columns: name,limit; names as in NAMES, units mm or deg). Used by the CLI tool."""
    global TOLS, NAMES, LIMITS, DIM, HFOV, _RX_PATH
    import csv
    if rx_path is not None:
        import os
        _RX_PATH = str(Path(rx_path).resolve())
        os.environ["LENSYIELD_RX"] = _RX_PATH  # spawned Monte Carlo workers inherit it
        _rx.cache_clear(); nominal.cache_clear()
        HFOV = float(_rx()["published"]["hfov_deg"])
        _reset_fields()
    TOLS = _tols(n_elem=max(s_["element"] for s_ in _rx()["surfaces"]))
    if tol_csv is not None:
        limits = {}
        with open(tol_csv) as f:
            for row in csv.DictReader(f):
                limits[row["name"].strip()] = float(row["limit"])
        unknown = set(limits) - {t.name for t in TOLS}
        if unknown:
            raise ValueError(f"unknown tolerance names: {sorted(unknown)}")
        TOLS = [Tol(t.name, t.group, t.attr, t.index, limits.get(t.name, t.limit), t.unit, t.callout) for t in TOLS]
    NAMES = [t.name for t in TOLS]
    LIMITS = np.array([t.limit for t in TOLS])
    DIM = len(TOLS)
    nominal.cache_clear()


def to_perturbation(u: np.ndarray, limits: np.ndarray = LIMITS, focus: float = 0.0) -> Perturbation:
    """u is in units of each tolerance's limit (u = 1 means at the + limit)."""
    n_elem = max(s_["element"] for s_ in _rx()["surfaces"])
    p = Perturbation(n_elem=n_elem, focus=focus)
    x = np.asarray(u, float) * limits
    for t, v in zip(TOLS, x):
        if t.index >= 0:
            getattr(p, t.attr)[t.index] = v
        else:
            setattr(p, t.attr, float(v))
    return p


def sample_u(n: int, rng: np.random.Generator) -> np.ndarray:
    """Truncated normal with the limit at 2 sigma (Zemax-style Monte Carlo default)."""
    out = rng.normal(0.0, 0.5, size=(n, DIM))
    bad = np.abs(out) > 1.0
    while bad.any():
        out[bad] = rng.normal(0.0, 0.5, size=bad.sum())
        bad = np.abs(out) > 1.0
    return out


# ---- simulation -------------------------------------------------------------------------
@lru_cache(maxsize=1)
def _rx():
    return load_prescription(_RX_PATH) if _RX_PATH else load_prescription()


def _reset_fields():
    global FIELDS
    FIELDS = [(0.0, 0.0),
              (MID_REL * HFOV, 0.0), (-MID_REL * HFOV, 0.0), (0.0, MID_REL * HFOV), (0.0, -MID_REL * HFOV),
              _diag(CORNER_REL, 1, 1), _diag(CORNER_REL, -1, 1), _diag(CORNER_REL, -1, -1), _diag(CORNER_REL, 1, -1)]


def trace_module(u: np.ndarray, limits: np.ndarray = LIMITS, n_grid: int = N_GRID) -> ModuleWavefronts:
    op = build_optic(_rx(), to_perturbation(u, limits), fields=FIELDS)
    op.set_ray_aiming("robust")
    return ModuleWavefronts(op, n_grid)


@lru_cache(maxsize=1)
def nominal():
    """Nominal module at its own autofocus best focus."""
    mw = trace_module(np.zeros(DIM))
    dz = mw.best_focus()
    tab = mw.mtf_table(dz)
    return dict(dz=dz, mtf=tab, focus_ref=dz)


def metrics_from_table(tab: np.ndarray) -> dict:
    """tab[field, freq, (T,S)] -> scalar metrics used for the spec."""
    avg = tab.mean(axis=2)  # (T+S)/2
    return dict(centre=float(avg[0, 0]),
                mid_min=float(avg[MIDS, 0].min()),
                corner_min=float(avg[CORNERS, 0].min()),
                corner_min_n2=float(avg[CORNERS, 1].min()))


def simulate(u: np.ndarray, limits: np.ndarray = LIMITS, n_grid: int = N_GRID) -> dict:
    """Trace one module, run autofocus, return MTFs (fields x freqs x T/S) and metrics."""
    mw = trace_module(u, limits, n_grid)
    nom = nominal()
    dz = mw.best_focus(center=nom["dz"], half_range=0.030, step=0.002)
    tab = mw.mtf_table(dz)
    vig = float(np.mean([fw.vignetting for fw in mw.data.values()]))
    out = dict(dz=dz - nom["dz"], mtf=tab, vignetting=vig)
    out.update(metrics_from_table(tab))
    return out


# ---- the spec (fixed before any Monte Carlo was run; see METHOD.md section 4) -----------
SPEC = dict(centre_frac=0.90, corner_frac=0.80)


def spec_thresholds():
    m = metrics_from_table(nominal()["mtf"])
    return dict(centre=SPEC["centre_frac"] * m["centre"], corner_min=SPEC["corner_frac"] * m["corner_min"])


def passes(metrics: dict, thr: dict | None = None) -> bool:
    thr = thr or spec_thresholds()
    return metrics["centre"] >= thr["centre"] and metrics["corner_min"] >= thr["corner_min"]


def flat_features(tab: np.ndarray) -> np.ndarray:
    """MTF table -> feature vector (9 fields x 2 freqs x T/S = 36)."""
    return np.asarray(tab).reshape(-1)


# Monte Carlo workers are spawned fresh; pick up a non-default prescription from the env.
import os as _os  # noqa: E402
if _os.environ.get("LENSYIELD_RX"):
    configure(rx_path=_os.environ["LENSYIELD_RX"])
