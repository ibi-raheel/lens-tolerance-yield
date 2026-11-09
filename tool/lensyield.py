"""lensyield: tolerance yield + failing-module diagnosis for a compact camera lens.

  run       prescription JSON + tolerance CSV -> Monte Carlo yield (autofocus as the
            compensator), both classical stacks, ranked drivers and a reallocated
            tolerance table (verify it with a second `run --tolerances <new.csv>`).
  diagnose  a failing module's through-field MTF (CSV) -> ranked likely culprit parts,
            from the trained classifier and from the signature lookup.

Examples (from the repo root; -I keeps the interpreter isolated from the working dir):
  python -I tool/lensyield.py run --prescription data/prescription_us9435983_e1.json \\
         --tolerances tool/example_tolerances.csv --modules 400 --out out/
  python -I tool/lensyield.py diagnose --mtf tool/example_failing_module.csv

Input formats
  prescription: data/prescription_us9435983_e1.json (surfaces with R, t, n, v, k, A[4..16],
                element index; published efl/fno/hfov). Up to any number of elements.
  tolerances:   CSV with columns name,limit (mm or deg, +/- limit = 2 sigma). Names:
                L<i> dx|dy|tx|ty|ct, G<i><i+1> gap, Barrel dx|dy|tx|ty, Sensor tx|ty.
                Missing names keep the default limit.
  mtf:          CSV with columns field,freq_lpmm,T,S for the 9 fields
                C, M+x, M-x, M+y, M-y, K++, K-+, K--, K+- at 111.6 and 223.2 lp/mm.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402


def cmd_run(a):
    from pipeline import module as M, stack as S, surrogate as SU
    from pipeline.mc import run_batch
    from pipeline.analyze import passes, se

    M.configure(rx_path=a.prescription, tol_csv=a.tolerances)
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    thr = M.spec_thresholds()
    print(f"spec: centre >= {thr['centre']:.3f}, worst corner >= {thr['corner_min']:.3f} "
          f"((T+S)/2 MTF at {M.FREQS[0]:.1f} lp/mm)")
    # 2k+1 sensitivity traces -> classical stacks
    U = [np.zeros(M.DIM)]
    for i in range(M.DIM):
        for s in (1.0, -1.0):
            u = np.zeros(M.DIM); u[i] = s; U.append(u)
    sens = run_batch(np.array(U), M.LIMITS, out / "sensitivity.npz", chunk=100)
    st = S.SensitivityStack(sens["mtf"])
    # Monte Carlo
    Umc = M.sample_u(a.modules, np.random.default_rng(a.seed))
    mc = run_batch(Umc, M.LIMITS, out / "mc.npz")
    Y = S.field_outputs(mc["mtf"]); Y[~mc["ok"]] = 0
    p = passes(Y, thr)
    yA = st.yield_A(thr)
    yB = float(passes(st.predict_B(Umc), thr).mean())
    # surrogate (physics prior + neural net) for drivers and reallocation
    model = SU.make("hybrid", st).fit(Umc, Y)
    rng = np.random.default_rng(1)
    base = M.sample_u(30000, rng)
    groups = list(dict.fromkeys(t.group for t in M.TOLS))
    gidx = {g: [i for i, t in enumerate(M.TOLS) if t.group == g] for g in groups}
    y_all = float(passes(model.predict(base), thr).mean())
    drivers = []
    for g in groups:
        Uz = base.copy(); Uz[:, gidx[g]] = 0
        drivers.append((g, 100 * (float(passes(model.predict(Uz), thr).mean()) - y_all)))
    drivers.sort(key=lambda r: -r[1])
    # reallocation: loosen groups that cost little yield, within the trained range (<= 1.25x
    # unless the model was trained on a wider design; see SOLUTION.md)
    k = {g: 1.0 for g in groups}
    def yld(kk):
        v = np.ones(M.DIM)
        for g, s in kk.items():
            v[gidx[g]] = s
        return float(passes(model.predict(base * v), thr).mean()), v
    target = y_all
    for g, _ in reversed(drivers):
        for step in (1.25,) if a.max_loosen <= 1.25 else (1.25, 1.5, a.max_loosen):
            kk = dict(k); kk[g] = step
            if yld(kk)[0] >= target:
                k = kk
    yk, v = yld(k)
    new_csv = out / "tolerances_reallocated.csv"
    with open(new_csv, "w", newline="") as f:
        w = csv.writer(f); w.writerow(["name", "limit", "factor"])
        for i, t in enumerate(M.TOLS):
            w.writerow([t.name, f"{t.limit * v[i]:.6g}", f"{v[i]:.2f}"])
    res = dict(modules=int(len(p)), yield_=float(p.mean()), yield_se=se(p.mean(), len(p)),
               baseline_A_limit_rss=yA, baseline_B_quadratic=yB,
               drivers_recovered_pts=dict(drivers), reallocated_csv=str(new_csv),
               reallocated_yield_surrogate=yk,
               next_step=f"verify: lensyield run --tolerances {new_csv} (fresh Monte Carlo)")
    (out / "result.json").write_text(json.dumps(res, indent=1))
    print(f"yield {100 * p.mean():.1f}% +/- {100 * se(p.mean(), len(p)):.1f} (n={len(p)})")
    print(f"baseline A (limit RSS) {100 * yA:.1f}%   baseline B (2nd-order) {100 * yB:.1f}%")
    print("top drivers (yield points recovered if perfect):")
    for g, d in drivers[:5]:
        print(f"  {g:22s} {d:+.1f}")
    print(f"reallocated table -> {new_csv} (surrogate yield {100 * yk:.1f}%); verify with a fresh run")


def cmd_diagnose(a):
    import joblib
    from pipeline import module as M
    model = joblib.load(ROOT / "results" / "diagnosis_model.joblib")
    lib = json.loads((ROOT / "results" / "signature_library.json").read_text())
    names = M.FIELD_NAMES
    tab = np.full((9, 2, 2), np.nan)
    with open(a.mtf) as f:
        for row in csv.DictReader(f):
            i = names.index(row["field"].strip())
            j = int(np.argmin([abs(float(row["freq_lpmm"]) - x) for x in M.FREQS]))
            tab[i, j] = [float(row["T"]), float(row["S"])]
    if np.isnan(tab).any():
        raise SystemExit("MTF CSV must give T and S for all 9 fields at both frequencies")
    x = tab.reshape(-1) - np.asarray(model["nominal"])
    clf = model["clf"]
    pr = clf.predict_proba(x[None])[0]
    order = np.argsort(-pr)
    print("trained model (probability):")
    for i in order[:3]:
        print(f"  {clf.classes_[i]:40s} {pr[i]:.2f}")
    Sg = np.array(lib["signatures"]); groups = lib["groups"]
    alpha = np.clip(Sg @ x / (np.sum(Sg * Sg, axis=1) + 1e-12), 0, None)
    res = np.sum((x[None] - alpha[:, None] * Sg) ** 2, axis=1)
    best = {}
    for g, r in zip(groups, res):
        m = model["label_name"][model["final"][g]]
        best[m] = min(best.get(m, np.inf), r)
    print("signature lookup (best residual first):")
    for g in sorted(best, key=best.get)[:3]:
        print(f"  {g}")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="lensyield", description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--prescription", default=str(ROOT / "data" / "prescription_us9435983_e1.json"))
    r.add_argument("--tolerances", default=None)
    r.add_argument("--modules", type=int, default=1000)
    r.add_argument("--seed", type=int, default=7)
    r.add_argument("--max-loosen", type=float, default=1.25)
    r.add_argument("--out", default="out")
    d = sub.add_parser("diagnose")
    d.add_argument("--mtf", required=True)
    a = ap.parse_args(argv)
    {"run": cmd_run, "diagnose": cmd_diagnose}[a.cmd](a)


if __name__ == "__main__":
    main()
