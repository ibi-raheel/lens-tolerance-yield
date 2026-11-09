"""Turns the ray-traced Monte Carlo runs into the measured results (results/*.json).

Stages (each writes into results/summary.json):
  yield_and_baselines  measured yield (held-out), Baseline A, Baseline B, linear footnote
  surrogates           candidate models scored on the held-out set + learning curve
  drivers              yield-loss share per culprit group (surrogate), Sobol total order,
                       spot check by direct ray trace (if data/runs/spot.npz exists)
  diagnosis            classifier vs nearest-signature lookup on held-out failing modules
  reallocation         budget search on the surrogate (needs wide.npz), writes
                       results/budget_reallocated.json for a fresh verification Monte Carlo
  verification         reads verify.npz (fresh MC on the new budget) and the current-budget
                       held-out yield; only the verified yield is reported
"""
from __future__ import annotations

import json
import math
import sys
import warnings
from pathlib import Path

import numpy as np

from . import module as M
from . import stack as S
from . import surrogate as SU

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parent.parent
RUNS = ROOT / "data" / "runs"
RES = ROOT / "results"
SPLIT = (3000, 4000)  # train [0, 3000), validation [3000, 4000), held-out [4000, 6000)


def _load(name):
    z = np.load(RUNS / name)
    n = int(z["done"])
    return {k: z[k][:n] if z[k].ndim and z[k].shape[0] == z["U"].shape[0] else z[k] for k in z.files}


def se(p, n):
    return math.sqrt(max(p * (1 - p), 1e-12) / n)


def passes(Y5, thr):
    c, k = S.criteria(Y5)
    return (c >= thr["centre"]) & (k >= thr["corner_min"])


def calibrated_yield(P, R, thr, draws=40, seed=0):
    """Yield from a regression surrogate with its prediction error put back.

    A surrogate predicts E[y | u], which is smoother than y, so thresholding it overstates
    the pass rate. Adding residual vectors drawn from the VALIDATION set (jointly across
    the five outputs, so corner-to-corner correlation is kept) gives an unbiased estimate of
    P(y passes) when the error is roughly independent of u."""
    rng = np.random.default_rng(seed)
    acc = 0.0
    for _ in range(draws):
        acc += passes(P + R[rng.integers(0, len(R), len(P))], thr).mean()
    return float(acc / draws)


def summary_load():
    p = RES / "summary.json"
    return json.loads(p.read_text()) if p.exists() else {}


def summary_save(d):
    RES.mkdir(exist_ok=True)
    (RES / "summary.json").write_text(json.dumps(d, indent=1))


def _data():
    mc = _load("mc_main.npz")
    U, Y = mc["U"], S.field_outputs(mc["mtf"])
    Y[~mc["ok"]] = 0.0                       # untraceable module = fail
    st = S.SensitivityStack(_load("sensitivity.npz")["mtf"])
    thr = M.spec_thresholds()
    return mc, U, Y, st, thr


# ---------------------------------------------------------------------------------------
def yield_and_baselines(out):
    mc, U, Y, st, thr = _data()
    n = len(U)
    a, b = SPLIT
    ho = slice(b, n)
    truth = passes(Y, thr)
    c, k = S.criteria(Y)
    YB = st.predict_B(U[ho]); YL = st.predict_linear(U[ho])
    cB, kB = S.criteria(YB); cL, kL = S.criteria(YL)
    ytrue = float(truth[ho].mean()); nh = int(truth[ho].size)
    yA = st.yield_A(thr)
    yB = float(passes(YB, thr).mean()); yL = float(passes(YL, thr).mean())
    # convergence of the full-population yield
    conv_n = [int(x) for x in np.unique(np.geomspace(50, n, 25).astype(int))]
    conv = [float(truth[:m].mean()) for m in conv_n]
    hist_edges = np.linspace(0, 0.45, 46)
    out["population"] = dict(n_total=int(n), n_train=a, n_val=b - a, n_heldout=nh,
                             untraceable=int((~mc["ok"]).sum()),
                             yield_all=float(truth.mean()), yield_all_se=se(truth.mean(), n),
                             convergence=dict(n=conv_n, yield_=conv))
    out["spec"] = dict(thresholds=thr, nominal=dict(centre=st.m0[0], corner_min=st.m0[1]),
                       rule=f"centre >= {M.SPEC['centre_frac']:.0%} of nominal AND every corner >= "
                            f"{M.SPEC['corner_frac']:.0%} of the nominal worst corner; (T+S)/2 MTF at Nyquist/4 "
                            f"= {M.FREQS[0]:.1f} lp/mm, 1.12 um pixel")
    out["histogram"] = dict(edges=hist_edges.tolist(),
                            corner_counts=np.histogram(k, hist_edges)[0].tolist(),
                            centre_counts=np.histogram(c, np.linspace(0.4, 0.75, 36))[0].tolist(),
                            centre_edges=np.linspace(0.4, 0.75, 36).tolist(),
                            corner_values_sample=np.round(k[:1500], 4).tolist(),
                            fail_reason=dict(centre_only=int(((c < thr["centre"]) & (k >= thr["corner_min"])).sum()),
                                             corner_only=int(((c >= thr["centre"]) & (k < thr["corner_min"])).sum()),
                                             both=int(((c < thr["centre"]) & (k < thr["corner_min"])).sum())))
    out["yield"] = dict(
        heldout_truth=ytrue, heldout_se=se(ytrue, nh),
        A_limit_rss=dict(yield_=yA, error_pts=100 * (yA - ytrue), traces=st.traces,
                         rss_centre=st.rss[0], rss_corner=st.rss[1],
                         per_tol_worst_change_corner=dict(zip(M.NAMES, np.round(st.d_corner, 5).tolist()))),
        B_quadratic=dict(yield_=yB, error_pts=100 * (yB - ytrue), traces=st.traces,
                         corner_rmse=float(np.sqrt(np.mean((kB - k[ho]) ** 2))),
                         centre_rmse=float(np.sqrt(np.mean((cB - c[ho]) ** 2))),
                         pass_fail_accuracy=float((passes(YB, thr) == truth[ho]).mean())),
        B_quadratic_calibrated=dict(
            yield_=(yBc := calibrated_yield(YB, Y[a:b] - st.predict_B(U[a:b]), thr)),
            error_pts=100 * (yBc - ytrue), traces=st.traces + (b - a),
            note="Baseline B plus its own validation residuals (needs 1,000 traced modules)"),
        linear_footnote=dict(yield_=yL, error_pts=100 * (yL - ytrue),
                             corner_rmse=float(np.sqrt(np.mean((kL - k[ho]) ** 2)))),
        mean_shift=dict(corner_mean=float(k.mean()), corner_nominal=st.m0[1],
                        centre_mean=float(c.mean()), centre_nominal=st.m0[0]))
    return out


# ---------------------------------------------------------------------------------------
def surrogates(out, seeds=(0, 1, 2)):
    mc, U, Y, st, thr = _data()
    n = len(U); a, b = SPLIT
    tr, va, ho = slice(0, a), slice(a, b), slice(b, n)
    truth = passes(Y, thr)
    c, k = S.criteria(Y)
    rows = {}
    best = None
    for name in ("mlp", "hybrid", "mlp_sym", "hybrid_sym", "gbm", "quad_ridge"):
        preds = []
        for sd in (seeds if "mlp" in name or "hybrid" in name else (0,)):
            m = SU.make(name, st, seed=sd).fit(U[tr], Y[tr])
            preds.append((m, m.predict(U[va]), m.predict(U[ho])))
        # ensemble mean over seeds for the neural nets
        Pva = np.mean([p[1] for p in preds], axis=0); Pho = np.mean([p[2] for p in preds], axis=0)
        cv_, kv_ = S.criteria(Pva); ch, kh = S.criteria(Pho)
        Rva = Y[va] - Pva
        yraw = float(passes(Pho, thr).mean())
        yh = calibrated_yield(Pho, Rva, thr)
        rows[name] = dict(val_corner_rmse=float(np.sqrt(np.mean((kv_ - k[va]) ** 2))),
                          heldout_yield=yh, heldout_error_pts=100 * (yh - truth[ho].mean()),
                          heldout_yield_uncalibrated=yraw,
                          heldout_error_pts_uncalibrated=100 * (yraw - truth[ho].mean()),
                          corner_rmse=float(np.sqrt(np.mean((kh - k[ho]) ** 2))),
                          centre_rmse=float(np.sqrt(np.mean((ch - c[ho]) ** 2))),
                          pass_fail_accuracy=float((passes(Pho, thr) == truth[ho]).mean()),
                          traces=a + st.traces * (name == "hybrid"))
        if best is None or rows[name]["val_corner_rmse"] < rows[best]["val_corner_rmse"]:
            best = name
            best_models = [p[0] for p in preds]
            best_resid = Rva
    out["surrogates"] = dict(candidates=rows, chosen=best, chosen_by="lowest validation corner RMSE "
                             "(held-out set never used for selection)",
                             yield_estimator="threshold the prediction plus validation residuals "
                                             "(residual bootstrap, 40 draws); uncalibrated also reported")
    np.save(RES / "val_residuals.npy", best_resid) if RES.exists() else None
    # learning curve for the chosen model and the plain MLP
    sizes = [s for s in (50, 100, 200, 400, 800, 1600, 3000) if s <= a]
    lc = {}
    for name in sorted({best, "mlp", "hybrid"}):
        ys, rm = [], []
        for s in sizes:
            ms = [SU.make(name, st, seed=sd).fit(U[:s], Y[:s]) for sd in (0, 1)]
            P = np.mean([m.predict(U[ho]) for m in ms], axis=0)
            Rv = Y[va] - np.mean([m.predict(U[va]) for m in ms], axis=0)
            ys.append(100 * abs(calibrated_yield(P, Rv, thr) - truth[ho].mean()))
            rm.append(float(np.sqrt(np.mean((S.criteria(P)[1] - k[ho]) ** 2))))
        lc[name] = dict(abs_yield_error_pts=ys, corner_rmse=rm)
    out["learning_curve"] = dict(train_sizes=sizes, curves=lc,
                                 B_reference=dict(traces=st.traces,
                                                  abs_yield_error_pts=abs(out["yield"]["B_quadratic"]["error_pts"]),
                                                  corner_rmse=out["yield"]["B_quadratic"]["corner_rmse"]),
                                 A_reference=dict(traces=st.traces,
                                                  abs_yield_error_pts=abs(out["yield"]["A_limit_rss"]["error_pts"])))
    # export the first chosen model for the browser
    RES.mkdir(exist_ok=True)
    if hasattr(best_models[0], "export"):
        exp = best_models[0].export()
        exp["symmetrised_at_test_time"] = best.endswith("_sym")
        if getattr(best_models[0], "base", None) is not None:
            exp["quadratic_stack"] = dict(y0=st.y0.tolist(), a=st.a.tolist(), b=st.b.tolist())
        exp["tolerances"] = [dict(name=t.name, limit=t.limit, unit=t.unit) for t in M.TOLS]
        exp["outputs"] = ["centre", "K++", "K-+", "K--", "K+-"]
        (RES / "surrogate_weights.json").write_text(json.dumps(exp))
    return out, best, (best_models, best_resid)


def _ens_predict(models, U):
    return np.mean([m.predict(U) for m in models], axis=0)


# ---------------------------------------------------------------------------------------
GROUPS = sorted({t.group for t in M.TOLS}, key=lambda g: [t.group for t in M.TOLS].index(g))


def drivers(out, models_resid, n_samp=60000, seed=11):
    models, R = models_resid
    mc, U, Y, st, thr = _data()
    rng = np.random.default_rng(seed)
    Us = M.sample_u(n_samp, rng)
    y_all = calibrated_yield(_ens_predict(models, Us), R, thr, draws=4)
    rows = []
    for g in GROUPS:
        idx = [i for i, t in enumerate(M.TOLS) if t.group == g]
        Uz = Us.copy(); Uz[:, idx] = 0.0
        yg = calibrated_yield(_ens_predict(models, Uz), R, thr, draws=4)
        rows.append(dict(group=g, yield_if_perfect=yg, recovered_pts=100 * (yg - y_all)))
    tot = sum(max(r["recovered_pts"], 0) for r in rows)
    for r in rows:
        r["share_of_loss"] = max(r["recovered_pts"], 0) / tot if tot > 0 else 0.0
    rows.sort(key=lambda r: -r["recovered_pts"])
    # Sobol total-order indices on the worst-corner MTF, groups, truncated-normal inputs
    try:
        from SALib.analyze import sobol
        from SALib.sample import sobol as ssob
        prob = dict(num_vars=M.DIM, names=M.NAMES, groups=[t.group for t in M.TOLS],
                    bounds=[[-1, 1, 0, 0.5]] * M.DIM, dists=["truncnorm"] * M.DIM)
        X = ssob.sample(prob, 2048, calc_second_order=False, seed=seed)
        kk = S.criteria(_ens_predict(models, X))[1]
        Si = sobol.analyze(prob, kk, calc_second_order=False, seed=seed)
        names = list(dict.fromkeys(t.group for t in M.TOLS))
        sob = {g: dict(ST=float(Si["ST"][i]), S1=float(Si["S1"][i])) for i, g in enumerate(names)}
    except Exception as e:  # pragma: no cover
        sob = {"error": str(e)}
    out["drivers"] = dict(yield_all_surrogate=y_all, rows=rows, sobol_corner=sob,
                          method="yield recovered if the group were perfect (others at current tolerance), "
                                 f"surrogate on {n_samp} sampled modules; share = recovered / sum of recovered")
    spot = RUNS / "spot.npz"
    if spot.exists():
        z = _load("spot.npz"); meta = json.loads((RUNS / "spot_meta.json").read_text())
        Ysp = S.field_outputs(z["mtf"]); Ysp[~z["ok"]] = 0
        base_idx = np.array(meta["base_rows"])
        Ybase = Y[base_idx]
        traced = 100 * (passes(Ysp, thr).mean() - passes(Ybase, thr).mean())
        pred = 100 * (calibrated_yield(_ens_predict(models, z["U"]), R, thr) -
                      calibrated_yield(_ens_predict(models, U[base_idx]), R, thr))
        out["drivers"]["spot_check"] = dict(groups=meta["groups"], n=int(len(base_idx)),
                                            traced_recovered_pts=float(traced), surrogate_recovered_pts=float(pred))
    return out


def make_spot(groups, n=500):
    """Re-trace n held-out modules with the given groups set perfect (direct ray trace)."""
    mc, U, Y, st, thr = _data()
    a, b = SPLIT
    rows = list(range(b, b + n))
    Uz = U[rows].copy()
    for g in groups:
        idx = [i for i, t in enumerate(M.TOLS) if t.group == g]
        Uz[:, idx] = 0.0
    (RUNS / "spot_meta.json").write_text(json.dumps(dict(groups=groups, base_rows=rows)))
    from .mc import run_batch
    run_batch(Uz, M.LIMITS, RUNS / "spot.npz")


# ---------------------------------------------------------------------------------------
def diagnosis(out, seed=0):
    from sklearn.model_selection import StratifiedKFold, cross_val_predict
    from sklearn.neural_network import MLPClassifier
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    z = _load("diag.npz")
    labels = np.array(json.loads((RUNS / "diag_labels.json").read_text()))[: len(z["U"])]
    nom = M.nominal()["mtf"].reshape(-1)
    X = z["mtf"].reshape(len(z["U"]), -1) - nom
    ok = z["ok"]
    thr = M.spec_thresholds()
    fail = ~passes(S.field_outputs(z["mtf"]), thr) & ok
    n = len(X); ntr = int(0.75 * n)
    tr = np.arange(ntr); te = np.arange(ntr, n)
    tr = tr[ok[tr]]; te = te[ok[te]]

    # signature library for the lookup baseline
    sig = _load("signatures.npz"); meta = json.loads((RUNS / "signatures_meta.json").read_text())
    Sg = sig["mtf"].reshape(len(sig["U"]), -1) - nom
    sig_groups = np.array([m[0] for m in meta])
    keep = sig_groups != "nominal"
    Sg, sig_groups = Sg[keep], sig_groups[keep]
    RES.mkdir(exist_ok=True)
    (RES / "signature_library.json").write_text(json.dumps(dict(signatures=np.round(Sg, 6).tolist(),
                                                                 groups=sig_groups.tolist())))

    def lookup_scores(x):
        """Least-squares fit x ~ alpha * s (alpha >= 0) for every signature; best residual per group."""
        nn = np.sum(Sg * Sg, axis=1) + 1e-12
        alpha = np.clip(Sg @ x / nn, 0, None)
        res = np.sum((x[None] - alpha[:, None] * Sg) ** 2, axis=1)
        best = {}
        for g, r in zip(sig_groups, res):
            best[g] = min(best.get(g, np.inf), r)
        return best

    def lookup_rank(x):
        b = lookup_scores(x)
        return sorted(b, key=b.get)

    # classifier: MLP on the through-field MTF change
    clf = make_pipeline(StandardScaler(), MLPClassifier(hidden_layer_sizes=(128, 64), alpha=1e-3,
                                                        max_iter=2000, early_stopping=True,
                                                        n_iter_no_change=40, random_state=seed))
    # merge look-alike culprits: cross-validated confusion on the TRAINING set only
    groups = sorted(set(labels))
    cvp = cross_val_predict(clf, X[tr], labels[tr], cv=StratifiedKFold(5, shuffle=True, random_state=0))
    merge = {g: g for g in groups}

    def find(g):
        while merge[g] != g:
            g = merge[g]
        return g

    trf = fail[tr]
    changed = True
    while changed:
        changed = False
        lab_m = np.array([find(g) for g in labels[tr]]); pred_m = np.array([find(g) for g in cvp])
        cls = sorted(set(lab_m))
        best_pair, best_c = None, 0.35
        for i, gi in enumerate(cls):
            for gj in cls[i + 1:]:
                ni = ((lab_m == gi) & trf).sum(); nj = ((lab_m == gj) & trf).sum()
                if ni + nj < 10:
                    continue
                cij = ((lab_m == gi) & (pred_m == gj) & trf).sum() + ((lab_m == gj) & (pred_m == gi) & trf).sum()
                c = cij / (ni + nj)
                if c > best_c:
                    best_pair, best_c = (gi, gj), c
        if best_pair:
            merge[best_pair[1]] = best_pair[0]
            changed = True
    final = {g: find(g) for g in groups}
    names = {}
    for g, r in final.items():
        names.setdefault(r, []).append(g)
    label_name = {r: " / ".join(sorted(v)) for r, v in names.items()}
    ym = np.array([label_name[final[g]] for g in labels])

    clf.fit(X[tr], ym[tr])
    classes = list(clf.classes_)
    proba = clf.predict_proba(X[te])
    order = np.argsort(-proba, axis=1)
    te_fail = te[fail[te]]
    mask = fail[te]
    top1_ml = float(np.mean([classes[order[i, 0]] == ym[te][i] for i in np.where(mask)[0]]))
    top2_ml = float(np.mean([ym[te][i] in (classes[order[i, 0]], classes[order[i, 1]]) for i in np.where(mask)[0]]))

    look1, look2, look_pred = [], [], []
    for j in te_fail:
        rk = []
        for g in lookup_rank(X[j]):
            m_ = label_name[final[g]]
            if m_ not in rk:
                rk.append(m_)
        look_pred.append(rk[0])
        look1.append(rk[0] == ym[j]); look2.append(ym[j] in rk[:2])
    ml_pred = [classes[order[i, 0]] for i in np.where(mask)[0]]
    labs = sorted(set(ym[te_fail]) | set(ml_pred) | set(look_pred))
    def confusion(pred):
        cm = np.zeros((len(labs), len(labs)), int)
        for t, p in zip(ym[te_fail], pred):
            cm[labs.index(t), labs.index(p)] += 1
        return cm.tolist()
    counts = {l: int((ym[te_fail] == l).sum()) for l in labs}
    out["diagnosis"] = dict(
        n_train=int(len(tr)), n_test=int(len(te)), n_test_failing=int(len(te_fail)),
        merged=[v for v in names.values() if len(v) > 1],
        classes=labs, test_failing_counts=counts,
        model=dict(top1=top1_ml, top2=top2_ml, confusion=confusion(ml_pred)),
        lookup=dict(top1=float(np.mean(look1)), top2=float(np.mean(look2)), confusion=confusion(look_pred),
                    library_traces=int(len(Sg) + 1)),
        chance_top1=float(max(counts.values()) / max(1, len(te_fail))),
        method="classifier: MLP on the 36 through-field MTF changes (9 fields x 2 freqs x T/S); "
               "lookup: least-squares fit to a traced signature library (each culprit at 3x its limit, "
               "8 directions for x/y pairs), best residual wins")
    # an example failing module for the dashboard
    if len(te_fail):
        j = te_fail[0]
        out["diagnosis"]["example"] = dict(
            true=ym[j], model=ml_pred[0], lookup=look_pred[0],
            mtf=np.round(z["mtf"][j], 4).tolist(), nominal=np.round(M.nominal()["mtf"], 4).tolist(),
            proba={classes[i]: round(float(p), 3) for i, p in enumerate(proba[list(te).index(j)])})
    import joblib
    joblib.dump(dict(clf=clf, label_name=label_name, final=final, nominal=nom), RES / "diagnosis_model.joblib")
    return out


# ---------------------------------------------------------------------------------------
STEPS = np.array([0.5, 0.67, 0.8, 1.0, 1.25, 1.5, 2.0])


def reallocation(out, n_samp=20000, seed=21):
    mc, U, Y, st, thr = _data()
    wide = _load("wide.npz")
    Uw, Yw = wide["U"], S.field_outputs(wide["mtf"]); Yw[~wide["ok"]] = 0
    a, b = SPLIT
    Utr = np.vstack([U[:a], Uw]); Ytr = np.vstack([Y[:a], Yw])
    name = out["surrogates"]["chosen"]
    models = [SU.make(name, st, seed=sd).fit(Utr, Ytr) for sd in (0, 1, 2)]
    Rv = Y[a:b] - _ens_predict(models, U[a:b])
    rng = np.random.default_rng(seed)
    base = M.sample_u(n_samp, rng)
    gidx = {g: [i for i, t in enumerate(M.TOLS) if t.group == g] for g in GROUPS}
    adjustable = [g for g in GROUPS]

    def scale_vec(k):
        v = np.ones(M.DIM)
        for g, s in k.items():
            v[gidx[g]] = s
        return v

    def yld(k):
        return calibrated_yield(_ens_predict(models, base * scale_vec(k)), Rv, thr, draws=3, seed=5)

    def cost(k):
        return float(np.sum(1.0 / scale_vec(k)))  # each tolerance costs ~ 1 / tolerance width

    k = {g: 1.0 for g in adjustable}
    y0 = yld(k); target = y0 + 0.005
    c0 = cost(k)
    hist = [dict(step="current", yield_=y0, cost=c0)]
    top = [r["group"] for r in out.get("drivers", {}).get("rows", [])[:6]] or adjustable[:6]
    for _ in range(60):
        cur_c = cost(k)
        singles = []
        for g in adjustable:
            si = int(np.argmin(np.abs(STEPS - k[g])))
            if si + 1 < len(STEPS):
                kk = dict(k); kk[g] = float(STEPS[si + 1]); singles.append(kk)
        feas = [(cost(kk), kk) for kk in singles if yld(kk) >= target]
        if not feas:
            pairs = []
            for g1 in top:
                s1 = int(np.argmin(np.abs(STEPS - k[g1])))
                if s1 == 0:
                    continue
                for g2 in adjustable:
                    s2 = int(np.argmin(np.abs(STEPS - k[g2])))
                    if g2 != g1 and s2 + 1 < len(STEPS):
                        kk = dict(k); kk[g1] = float(STEPS[s1 - 1]); kk[g2] = float(STEPS[s2 + 1])
                        if cost(kk) < cur_c - 1e-9:
                            pairs.append(kk)
            feas = [(cost(kk), kk) for kk in pairs if yld(kk) >= target]
        if not feas:
            break
        best_c, best = min(feas, key=lambda t: t[0])
        k = best
        hist.append(dict(step=len(hist), yield_=yld(k), cost=best_c))
    yk = yld(k)
    limits_new = {t.name: float(t.limit * scale_vec(k)[i]) for i, t in enumerate(M.TOLS)}
    RES.mkdir(exist_ok=True)
    (RES / "budget_reallocated.json").write_text(json.dumps(dict(limits=limits_new, scale=k), indent=1))
    out["reallocation"] = dict(
        surrogate=name, surrogate_training_traces=int(len(Utr)),
        current_yield_surrogate=y0, new_yield_surrogate=yk, target=target,
        cost_current=c0, cost_new=cost(k), cost_change_pct=100 * (cost(k) / c0 - 1),
        scale=k, search=hist,
        table=[dict(tol=t.name, group=t.group, unit=t.unit, callout=t.callout,
                    current=t.limit, new=limits_new[t.name], factor=float(scale_vec(k)[i]))
               for i, t in enumerate(M.TOLS)],
        cost_model="cost proxy = sum over the 41 tolerances of (current limit / new limit); "
                   "loosening a tolerance 2x halves its term")
    return out


def verification(out):
    mc, U, Y, st, thr = _data()
    a, b = SPLIT
    v = _load("verify.npz")
    Yv = S.field_outputs(v["mtf"]); Yv[~v["ok"]] = 0
    pv = passes(Yv, thr)
    cur = passes(Y[b:], thr)
    out["verification"] = dict(
        new_budget_yield=float(pv.mean()), new_budget_se=se(pv.mean(), len(pv)), n_new=int(len(pv)),
        current_budget_yield=float(cur.mean()), current_budget_se=se(cur.mean(), len(cur)), n_current=int(len(cur)),
        difference_pts=100 * float(pv.mean() - cur.mean()),
        difference_se_pts=100 * math.sqrt(se(pv.mean(), len(pv)) ** 2 + se(cur.mean(), len(cur)) ** 2),
        note="fresh, independent ray-traced Monte Carlo (seed 3) on the reallocated budget vs the "
             "held-out modules of the current budget")
    return out


def scrub_curves(out):
    """Section 3: sensor tilt 0..0.2 deg vs a despace error, with and without autofocus."""
    nom = M.nominal()
    rows = {}
    for name, tol, values in (("sensor_tilt", "Sensor tx", np.linspace(0, 0.20, 11)),
                              ("despace", "G12 gap", np.linspace(0, 0.012, 11))):
        i = M.NAMES.index(tol)
        r = dict(values=values.tolist(), unit="deg" if "tilt" in name else "mm",
                 centre_af=[], corners_af=[], worst_af=[], centre_fixed=[], worst_fixed=[], focus_um=[])
        for v in values:
            u = np.zeros(M.DIM); u[i] = v / M.LIMITS[i]
            mw = M.trace_module(u)
            dz = mw.best_focus(center=nom["dz"])
            for key, z_ in (("af", dz), ("fixed", nom["dz"])):
                avg = mw.mtf_table(z_)[:, 0, :].mean(axis=1)
                r[f"centre_{key}"].append(float(avg[0]))
                r[f"worst_{key}"].append(float(avg[M.CORNERS].min()))
                if key == "af":
                    r["corners_af"].append([float(x) for x in avg[M.CORNERS]])
            r["focus_um"].append(1e3 * (dz - nom["dz"]))
        if name == "sensor_tilt":
            th = np.array(values[1:]); w0 = r["worst_af"][0]
            mean_c = np.array([np.mean(c) for c in r["corners_af"]])
            loss_w = w0 - np.array(r["worst_af"][1:]); loss_m = mean_c[0] - mean_c[1:]
            fit = lambda L: float(np.polyfit(np.log(th[L > 1e-6]), np.log(L[L > 1e-6]), 1)[0])
            r["exponent_worst_corner"] = fit(loss_w)
            r["exponent_mean_of_corners"] = fit(loss_m)
            r["mean_corners_af"] = mean_c.tolist()
        rows[name] = r
    out["scrubs"] = dict(rows=rows, corner_names=[M.FIELD_NAMES[c] for c in M.CORNERS],
                         note="sensor tilt about the x axis; despace = L1-L2 air gap error; "
                              "'af' = autofocus re-optimised, 'fixed' = focus held at nominal")
    return out


def main(stages):
    out = summary_load()
    models = None
    for s in stages:
        if s == "yield":
            yield_and_baselines(out)
        elif s == "surrogates":
            out, best, models = surrogates(out)
        elif s == "drivers":
            if models is None:
                mc, U, Y, st, thr = _data()
                name = out["surrogates"]["chosen"]
                ms = [SU.make(name, st, seed=sd).fit(U[:SPLIT[0]], Y[:SPLIT[0]]) for sd in (0, 1, 2)]
                Rv = Y[SPLIT[0]:SPLIT[1]] - _ens_predict(ms, U[SPLIT[0]:SPLIT[1]])
                models = (ms, Rv)
            drivers(out, models)
        elif s == "diagnosis":
            diagnosis(out)
        elif s == "realloc":
            reallocation(out)
        elif s == "verify":
            verification(out)
        elif s == "scrubs":
            scrub_curves(out)
        summary_save(out)
        print("done", s, flush=True)
    return out


if __name__ == "__main__":
    main(sys.argv[1:])
