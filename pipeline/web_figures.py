"""Figure data for the web page that summary.json does not carry.

  lens     element profiles (sag equation, meridional section) and real rays traced by
           Optiland at 0, 0.5 and 0.7 field in F, d and C light, plus the y-z path of
           each ray through every surface. Used for the cross-section drawing.
  scatter  traced worst-corner MTF of the 2,000 held-out modules against the two
           predictions scored in summary.json: the second-order stack (Baseline B) and
           the chosen surrogate (same seeds, same split, so the RMSE matches).

Writes web/public/data/figures.json. Run:
  python -I -c "import sys; sys.path.insert(0, '.'); from pipeline import web_figures; web_figures.run()"
"""
from __future__ import annotations

import json
import math

import numpy as np
import optiland.backend as be

from . import analyze as A
from . import lens as L
from . import module as M
from . import stack as S
from . import surrogate as SU


def _sag(s, y):
    R, k, coeffs = s["R"], s["k"], s["A"]
    c = 1.0 / R
    z = c * y * y / (1 + math.sqrt(max(1 - (1 + k) * c * c * y * y, 0.0)))
    for i, a in enumerate(coeffs):
        z += a * y ** (4 + 2 * i)
    return z


def lens_figure():
    rx = L.load_prescription()
    lay = L.surface_layout(rx)
    hfov = rx["published"]["hfov_deg"]
    fields = [0.0, 0.5, 0.7]
    rays = []
    max_y = {}
    for rel in fields:
        for wl in L.WAVELENGTHS_UM:
            for py in np.linspace(-1, 1, 7):
                rays.append(dict(field=rel, wl=wl, py=float(py)))
    # fields 0 and full HFOV, so the normalised field Hy equals the relative field
    op = L.build_optic(rx, fields=[(0.0, 0.0), (0.0, hfov)])
    out_rays = []
    for r in rays:
        op.trace_generic(Hx=0.0, Hy=r["field"], Px=0.0, Py=r["py"], wavelength=r["wl"])
        sg = op.surface_group
        ys = np.asarray(be.to_numpy(sg.y)).ravel()
        zs = np.asarray(be.to_numpy(sg.z)).ravel()
        if not np.all(np.isfinite(ys)):
            continue
        pts = [[round(float(z), 4), round(float(y), 4)] for z, y in zip(zs[1:], ys[1:])]
        # entry segment: start 0.6 mm in front of L1 along the incoming direction
        ang = math.radians(r["field"] * hfov)
        z0 = -0.6
        y0 = pts[0][1] - (pts[0][0] - z0) * math.tan(ang)
        pts.insert(0, [z0, round(y0, 4)])
        out_rays.append(dict(field=r["field"], wl=r["wl"], py=r["py"], pts=pts))
        for j, (z, y) in enumerate(zip(zs[1:], ys[1:])):
            max_y[j] = max(max_y.get(j, 0.0), abs(float(y)))
    # element profiles, semi-diameter = max ray height on that surface + 3% margin
    surf_rows = []
    j = 0
    for s in lay:
        sd = max_y.get(j, 0.0) * 1.03
        if s["R"] is not None:
            ys = np.linspace(-sd, sd, 41)
            prof = [[round(float(s["pos"][2] + _sag(s, y)), 4), round(float(y), 4)] for y in ys]
        else:
            prof = [[round(float(s["pos"][2]), 4), round(-sd, 4)], [round(float(s["pos"][2]), 4), round(sd, 4)]]
        surf_rows.append(dict(name=s["name"], element=s["element"], z=round(float(s["pos"][2]), 4),
                              sd=round(sd, 4), profile=prof))
        j += 1
    return dict(surfaces=surf_rows, rays=out_rays, wavelengths_um=list(L.WAVELENGTHS_UM),
                fields_rel=fields, hfov_deg=hfov,
                note="meridional section; rays traced by Optiland through the nominal design")


def scatter_figure(out):
    mc, U, Y, st, thr = A._data()
    n = len(U); a, b = A.SPLIT
    tr, ho = slice(0, a), slice(b, n)
    name = out["surrogates"]["chosen"]
    ms = [SU.make(name, st, seed=sd).fit(U[tr], Y[tr]) for sd in (0, 1, 2)]
    P = A._ens_predict(ms, U[ho])
    PB = st.predict_B(U[ho])
    k = S.criteria(Y[ho])[1]
    kS = S.criteria(P)[1]
    kB = S.criteria(PB)[1]
    rm = lambda p: float(np.sqrt(np.mean((p - k) ** 2)))
    r4 = lambda v: [round(float(x), 4) for x in v]
    return dict(traced=r4(k), stack=r4(kB), surrogate=r4(kS), spec=thr["corner_min"],
                rmse_stack=rm(kB), rmse_surrogate=rm(kS), model=name, n=int(len(k)))


def run():
    out = A.summary_load()
    fig = dict(lens=lens_figure(), scatter=scatter_figure(out))
    p = A.ROOT / "web" / "public" / "data" / "figures.json"
    p.write_text(json.dumps(fig, separators=(",", ":")))
    print("wrote", p, "rmse", fig["scatter"]["rmse_stack"], fig["scatter"]["rmse_surrogate"],
          "rays", len(fig["lens"]["rays"]))


if __name__ == "__main__":
    run()
