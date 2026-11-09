"""Build the published phone lens in Optiland, nominal or perturbed.

The prescription comes from data/prescription_*.json (transcribed patent tables).
Every Monte Carlo module is a fresh Optic built from the nominal prescription
plus a perturbation dict, so no state leaks between modules.

Coordinate conventions (Optiland): z along the optical axis, surfaces placed by
global vertex position (x, y, z) and rotations (rx, ry) in radians about the
surface's own vertex. A rigid element tilt about a pivot is modelled by rotating
both surfaces by the same angle AND moving each vertex to pivot + R(vertex - pivot).
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import optiland.backend as be
from optiland.materials import AbbeMaterial
from optiland.optic import Optic

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RX = ROOT / "data" / "prescription_us9435983_e1.json"

# Fraunhofer F, d, C lines (micrometres); d is primary. Equal weights.
WAVELENGTHS_UM = (0.4861, 0.5876, 0.6563)


def load_prescription(path: Path | str = DEFAULT_RX) -> dict:
    return json.loads(Path(path).read_text())


@dataclass
class Perturbation:
    """Mechanical errors of one module. Units: mm and degrees.

    elem_dx/dy[i]   decenter of element i+1 (rigid), mm
    elem_tx/ty[i]   tilt of element i+1 about its own centre, deg (tx: about x axis)
    elem_dt[i]      centre-thickness error of element i+1, mm
    gap_dt[i]       error of air gap after element i+1 (i = 0..4), mm
    barrel_dx/dy    whole lens barrel decenter relative to sensor, mm
    barrel_tx/ty    whole barrel tilt about the stop/L1 region, deg
    sensor_tx/ty    image-plane tilt, deg
    focus           image-plane axial shift (the compensator), mm
    """

    n_elem: int = 6
    elem_dx: np.ndarray = None
    elem_dy: np.ndarray = None
    elem_tx: np.ndarray = None
    elem_ty: np.ndarray = None
    elem_dt: np.ndarray = None
    gap_dt: np.ndarray = None
    barrel_dx: float = 0.0
    barrel_dy: float = 0.0
    barrel_tx: float = 0.0
    barrel_ty: float = 0.0
    sensor_tx: float = 0.0
    sensor_ty: float = 0.0
    focus: float = 0.0

    def __post_init__(self):
        z = lambda k: np.zeros(k)
        for name in ("elem_dx", "elem_dy", "elem_tx", "elem_ty", "elem_dt"):
            if getattr(self, name) is None:
                setattr(self, name, z(self.n_elem))
        if self.gap_dt is None:
            self.gap_dt = z(self.n_elem - 1)


def _rot_matrix(rx: float, ry: float) -> np.ndarray:
    """Rotation applied as rx (about x) then ry (about y), radians, matching
    Optiland's globalize order (rotate_x, then rotate_y)."""
    cx, sx = math.cos(rx), math.sin(rx)
    cy, sy = math.cos(ry), math.sin(ry)
    Rx = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]])
    Ry = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
    return Ry @ Rx


def _rotate_point(p, pivot, R):
    return pivot + R @ (np.asarray(p) - pivot)


def _check_rotation_convention():
    """Optiland rotate_x(+a) on a +z unit vector: confirm sign of our matrix."""
    from optiland.rays import RealRays

    r = RealRays(0.0, 0.0, 1.0, 0.0, 0.0, 1.0, 1.0, 0.55)
    r.rotate_x(0.1)
    ours = _rot_matrix(0.1, 0.0) @ np.array([0, 0, 1.0])
    got = np.array([float(be.to_numpy(r.x)[0]), float(be.to_numpy(r.y)[0]), float(be.to_numpy(r.z)[0])])
    return ours, got


def surface_layout(rx: dict, pert: Perturbation | None = None):
    """Return the list of surface dicts with global vertex position + rotation.

    Order: L1 front, stop, L1 back, L2..L6 surfaces, 2 filter surfaces, image.
    """
    pert = pert or Perturbation()
    surfs = rx["surfaces"]
    n_elem = max(s["element"] for s in surfs)
    # nominal axial thicknesses with thickness/gap errors
    t = [s["t"] for s in surfs]
    for i in range(n_elem):
        t[2 * i] += float(pert.elem_dt[i])  # element centre thickness
        if i < n_elem - 1:
            t[2 * i + 1] += float(pert.gap_dt[i])  # air gap after element i+1
    # L1 front vertex at z=0. The patent's stop row has thickness -0.379, i.e. the
    # aperture stop plane lies 0.379 mm BEHIND the L1 front vertex (inside L1's
    # front sag). It is inserted after L1 front, in L1's material; it belongs to
    # the barrel, not to element 1.
    z_stop = -rx["stop_thickness_mm"]
    out = []
    z = 0.0
    for i, s in enumerate(surfs):
        out.append(dict(name=s["name"], R=s["R"], k=s["k"], A=s["A"], n_after=s["n"],
                        v_after=s["v"], pos=np.array([0.0, 0.0, z]), rx=0.0, ry=0.0,
                        element=s["element"]))
        if i == 0:
            out.append(dict(name="stop", R=None, k=0.0, A=[], n_after=s["n"], v_after=s["v"],
                            pos=np.array([0.0, 0.0, z_stop]), rx=0.0, ry=0.0, element=-1))
        z += t[i]
    image_z = z + pert.focus
    out.append(dict(name="image", R=None, k=0.0, A=[], n_after=1.0, v_after=0.0,
                    pos=np.array([0.0, 0.0, image_z]), rx=0.0, ry=0.0, element=-2))

    # 1) element rigid errors: tilt about the element's mid-thickness point, then decenter
    for e in range(1, n_elem + 1):
        idx = [j for j, s in enumerate(out) if s["element"] == e]
        zc = 0.5 * (out[idx[0]]["pos"][2] + out[idx[-1]]["pos"][2])
        pivot = np.array([0.0, 0.0, zc])
        arx = math.radians(float(pert.elem_tx[e - 1]))
        ary = math.radians(float(pert.elem_ty[e - 1]))
        R = _rot_matrix(arx, ary)
        for j in idx:
            out[j]["pos"] = _rotate_point(out[j]["pos"], pivot, R)
            out[j]["rx"] += arx
            out[j]["ry"] += ary
            out[j]["pos"] = out[j]["pos"] + np.array([float(pert.elem_dx[e - 1]), float(pert.elem_dy[e - 1]), 0.0])

    # 2) barrel (all lens surfaces, stop and filter move together relative to the sensor);
    #    pivot at the barrel's mid-length.
    barrel_idx = [j for j, s in enumerate(out) if s["element"] != -2]
    zc = 0.5 * (out[0]["pos"][2] + out[barrel_idx[-1]]["pos"][2])
    pivot = np.array([0.0, 0.0, zc])
    R = _rot_matrix(math.radians(pert.barrel_tx), math.radians(pert.barrel_ty))
    for j in barrel_idx:
        out[j]["pos"] = _rotate_point(out[j]["pos"], pivot, R)
        out[j]["rx"] += math.radians(pert.barrel_tx)
        out[j]["ry"] += math.radians(pert.barrel_ty)
        out[j]["pos"] = out[j]["pos"] + np.array([pert.barrel_dx, pert.barrel_dy, 0.0])

    # 3) sensor tilt about its own centre (on axis)
    out[-1]["rx"] += math.radians(pert.sensor_tx)
    out[-1]["ry"] += math.radians(pert.sensor_ty)
    return out


_MAT_CACHE: dict = {}


def _material(n: float, v: float):
    if n == 1.0:
        return "air"
    key = (n, v)
    if key not in _MAT_CACHE:
        _MAT_CACHE[key] = AbbeMaterial(n=n, abbe=v, model="buchdahl")
    return _MAT_CACHE[key]


def build_optic(rx: dict | None = None, pert: Perturbation | None = None,
                fields: list[tuple[float, float]] | None = None,
                wavelengths=WAVELENGTHS_UM) -> Optic:
    """Build an Optiland Optic. fields: list of (x_deg, y_deg) field angles."""
    rx = rx or load_prescription()
    pub = rx["published"]
    lay = surface_layout(rx, pert)
    op = Optic()
    op.surfaces.add(index=0, radius=be.inf, thickness=be.inf)
    for i, s in enumerate(lay):
        kw = dict(index=i + 1, x=float(s["pos"][0]), y=float(s["pos"][1]), z=float(s["pos"][2]),
                  rx=float(s["rx"]), ry=float(s["ry"]))
        mat = _material(s["n_after"], s["v_after"])
        if s["name"] == "stop":
            op.surfaces.add(**kw, radius=be.inf, is_stop=True, material=mat)
        elif s["name"] == "image":
            op.surfaces.add(**kw, radius=be.inf)
        elif s["R"] is None:
            op.surfaces.add(**kw, radius=be.inf, material=mat)
        else:
            coeffs = [0.0] + list(s["A"])  # Optiland coefficient[0] multiplies r^2
            op.surfaces.add(**kw, surface_type="even_asphere", radius=s["R"], conic=s["k"],
                            coefficients=coeffs, material=mat)
    op.set_aperture(aperture_type="EPD", value=pub["efl_mm"] / pub["fno"])
    op.fields.set_type(field_type="angle")
    if fields is None:
        fields = [(0.0, 0.0)]
    for fx, fy in fields:
        op.fields.add(y=fy, x=fx)
    for w in wavelengths:
        op.wavelengths.add(value=w, is_primary=(abs(w - 0.5876) < 1e-3))
    return op
