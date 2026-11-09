"""Parallel ray-traced Monte Carlo runner (max 4 workers, run under `nice`).

Usage (from repo root, isolated interpreter):
  python -I -m pipeline.mc main      # 6000 modules on the current budget
  python -I -m pipeline.mc diag      # diagnosis set: one injected out-of-spec part each
  python -I -m pipeline.mc verify <budget.json>   # fresh MC on a reallocated budget
Results go to data/runs/*.npz (raw) and are summarised by pipeline/analyze.py.
"""
from __future__ import annotations

import json
import os
import sys
import time
from multiprocessing import get_context
from pathlib import Path

for _v in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "NUMBA_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
RUNS = ROOT / "data" / "runs"
WORKERS = 4


def _work(args):
    import warnings
    warnings.filterwarnings("ignore")
    from pipeline import module as M
    u, limits = args
    try:
        r = M.simulate(u, limits)
        return r["mtf"], r["dz"], r["vignetting"], True
    except Exception:  # a module whose chief ray cannot be traced: counts as a failure
        return np.zeros((len(M.FIELDS), 2, 2)), np.nan, 1.0, False


def run_batch(U: np.ndarray, limits: np.ndarray, out: Path, chunk: int = 200) -> dict:
    """Simulate every row of U (units of limit) with the given limits; checkpoint to out."""
    out.parent.mkdir(parents=True, exist_ok=True)
    n = len(U)
    mtf = np.zeros((n, 9, 2, 2)); dz = np.full(n, np.nan); vig = np.zeros(n); ok = np.zeros(n, bool)
    done = 0
    if out.exists():
        z = np.load(out)
        if z["U"].shape == U.shape and np.allclose(z["U"], U):
            done = int(z["done"]); mtf[:done] = z["mtf"][:done]; dz[:done] = z["dz"][:done]
            vig[:done] = z["vig"][:done]; ok[:done] = z["ok"][:done]
            print(f"resume {out.name} at {done}/{n}", flush=True)
    t0 = time.time()
    ctx = get_context("spawn")
    with ctx.Pool(WORKERS) as pool:
        while done < n:
            hi = min(n, done + chunk)
            res = pool.map(_work, [(U[i], limits) for i in range(done, hi)], chunksize=4)
            for k, (m, d, v, o) in enumerate(res):
                mtf[done + k], dz[done + k], vig[done + k], ok[done + k] = m, d, v, o
            done = hi
            np.savez_compressed(out, U=U, limits=limits, mtf=mtf, dz=dz, vig=vig, ok=ok, done=done)
            el = time.time() - t0
            print(f"{out.name}: {done}/{n}  {el / 60:.1f} min", flush=True)
    return dict(U=U, mtf=mtf, dz=dz, vig=vig, ok=ok)


def main_mc(seed=1, n=6000):
    from pipeline import module as M
    U = M.sample_u(n, np.random.default_rng(seed))
    return run_batch(U, M.LIMITS, RUNS / "mc_main.npz")


def sensitivity_runs():
    """2k+1 traces: nominal + each tolerance at its + and - limit (others zero)."""
    from pipeline import module as M
    U = [np.zeros(M.DIM)]
    for i in range(M.DIM):
        for s in (+1.0, -1.0):
            u = np.zeros(M.DIM); u[i] = s; U.append(u)
    return run_batch(np.array(U), M.LIMITS, RUNS / "sensitivity.npz", chunk=100)


def diag_set(seed=2, n=2400):
    """Background tolerances + one part pushed 2-4x past its limit (the culprit)."""
    from pipeline import module as M
    rng = np.random.default_rng(seed)
    groups = sorted({t.group for t in M.TOLS})
    U = M.sample_u(n, rng)
    labels = []
    for k in range(n):
        g = groups[rng.integers(len(groups))]
        idx = [i for i, t in enumerate(M.TOLS) if t.group == g]
        mag = rng.uniform(2.0, 4.0)
        if g == "spacing":
            i = idx[rng.integers(len(idx))]; U[k, i] = mag * rng.choice([-1, 1])
        elif g == "image-plane tilt":
            pair = idx[:2] if rng.random() < 0.5 else idx[2:]   # barrel or sensor
            phi = rng.uniform(0, 2 * np.pi); U[k, pair[0]] = mag * np.cos(phi); U[k, pair[1]] = mag * np.sin(phi)
        elif len(idx) == 2:                                       # x/y pair: decenter or tilt
            phi = rng.uniform(0, 2 * np.pi); U[k, idx[0]] = mag * np.cos(phi); U[k, idx[1]] = mag * np.sin(phi)
        else:
            U[k, idx[0]] = mag * rng.choice([-1, 1])
        labels.append(g)
    (RUNS).mkdir(parents=True, exist_ok=True)
    (RUNS / "diag_labels.json").write_text(json.dumps(labels))
    return run_batch(U, M.LIMITS, RUNS / "diag.npz")


def verify(budget_path, seed=3, n=3000, name="verify"):
    from pipeline import module as M
    b = json.loads(Path(budget_path).read_text())
    limits = np.array([b["limits"][t.name] for t in M.TOLS])
    U = M.sample_u(n, np.random.default_rng(seed))
    return run_batch(U, limits, RUNS / f"{name}.npz")


def scrubs():
    """Section 3 curves: sensor tilt 0..0.2 deg and L-gap despace, with autofocus."""
    from pipeline import module as M
    U = []
    i_tilt = M.NAMES.index("Sensor tx")
    i_gap = M.NAMES.index("G56 gap")
    tilts = np.linspace(0, 0.20, 11)
    gaps = np.linspace(0, 0.020, 11)
    for t in tilts:
        u = np.zeros(M.DIM); u[i_tilt] = t / M.LIMITS[i_tilt]; U.append(u)
    for g in gaps:
        u = np.zeros(M.DIM); u[i_gap] = g / M.LIMITS[i_gap]; U.append(u)
    r = run_batch(np.array(U), M.LIMITS, RUNS / "scrubs.npz", chunk=100)
    np.savez(RUNS / "scrubs_axes.npz", tilts=tilts, gaps=gaps)
    return r


def wide_set(seed=4, n=2000):
    """Design-of-experiments set for the reallocation surrogate: every tolerance sampled
    out to 2x its current limit (truncated normal, sigma = current limit), so the model
    is not extrapolating when it evaluates a loosened budget."""
    from pipeline import module as M
    U = 2.0 * M.sample_u(n, np.random.default_rng(seed))
    return run_batch(U, M.LIMITS, RUNS / "wide.npz")


def signature_library():
    """Lookup baseline library: each culprit group pushed to 3x its limit, pair groups in
    8 directions, single tolerances at both signs (plus the nominal)."""
    from pipeline import module as M
    U, meta = [np.zeros(M.DIM)], [("nominal", "")]
    groups = {}
    for i, t in enumerate(M.TOLS):
        groups.setdefault((t.group, t.attr.split("_")[0] + "_" + t.attr.split("_")[1][:-1] if t.attr.endswith(("x", "y")) else t.attr), []).append(i)
    for (g, sub), idx in groups.items():
        if len(idx) == 2:
            for k in range(8):
                phi = k * np.pi / 4
                u = np.zeros(M.DIM); u[idx[0]] = 3 * np.cos(phi); u[idx[1]] = 3 * np.sin(phi)
                U.append(u); meta.append((g, f"{sub}@{k * 45}"))
        else:
            for i in idx:
                for sgn in (1, -1):
                    u = np.zeros(M.DIM); u[i] = 3 * sgn
                    U.append(u); meta.append((g, f"{M.TOLS[i].name}{'+' if sgn > 0 else '-'}"))
    RUNS.mkdir(parents=True, exist_ok=True)
    (RUNS / "signatures_meta.json").write_text(json.dumps(meta))
    return run_batch(np.array(U), M.LIMITS, RUNS / "signatures.npz", chunk=100)


def dispatch(argv):
    what = argv[0]
    {"main": main_mc, "sens": sensitivity_runs, "diag": diag_set, "scrubs": scrubs, "wide": wide_set, "sig": signature_library,
     "verify": lambda: verify(argv[1], name=argv[2] if len(argv) > 2 else "verify")}[what]()


if __name__ == "__main__":
    dispatch(sys.argv[1:])
