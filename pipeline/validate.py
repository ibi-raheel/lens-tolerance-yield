"""Validation of the rebuilt lens and of the MTF engine. Writes results/validation.json.

Checks (METHOD.md section 6):
  1. EFL, F-number, TTL, image height vs the patent text.
  2. Element focal lengths: Optiland paraxial of each isolated element AND the
     thick-lens lensmaker equation, vs the patent's Table 1.
  3. Nominal MTF under the diffraction limit at every field and frequency.
  4. Sensor-tilt hand calc: corner defocus = h * theta, vs traced best focus shift.
  5. Field curvature (best-focus T and S per field height) vs the patent's FIG. 2,
     digitised by eye (+/- 0.01 mm), and distortion vs FIG. 2.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import optiland.backend as be
from optiland.optic import Optic

from . import module as M
from .lens import WAVELENGTHS_UM, _material, build_optic, load_prescription, Perturbation
from .mtf import FREQS, ModuleWavefronts

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "results"

# FIG. 2 of the patent, read by eye from the plot (image height mm -> focus mm).
# Tangential (dashed) and sagittal (solid) astigmatic field curves, and distortion (%).
FIG2 = {
    "img_ht": [0.72, 1.45, 2.17],
    "tan_mm": [0.02, -0.01, -0.06],
    "sag_mm": [0.00, -0.01, -0.03],
    "distortion_pct": [1.0, 2.8, 2.7],
    "read_uncertainty_mm": 0.01,
    "read_uncertainty_pct": 0.4,
}


def thick_lens_f(R1, R2, t, n):
    c1 = 0.0 if R1 is None else 1.0 / R1
    c2 = 0.0 if R2 is None else 1.0 / R2
    P = (n - 1) * (c1 - c2 + (n - 1) * t * c1 * c2 / n)
    return 1.0 / P


def element_f_optiland(s1, s2):
    op = Optic()
    op.surfaces.add(index=0, radius=be.inf, thickness=be.inf)
    mat = _material(s1["n"], s1["v"])
    op.surfaces.add(index=1, surface_type="even_asphere", radius=s1["R"], conic=s1["k"],
                    coefficients=[0.0] + s1["A"], thickness=s1["t"], material=mat, is_stop=True)
    op.surfaces.add(index=2, surface_type="even_asphere", radius=s2["R"], conic=s2["k"],
                    coefficients=[0.0] + s2["A"], thickness=5.0)
    op.surfaces.add(index=3)
    op.set_aperture(aperture_type="EPD", value=0.5)
    op.fields.set_type(field_type="angle"); op.fields.add(y=0.0)
    op.wavelengths.add(value=0.5876, is_primary=True)
    return float(op.paraxial.f2())


def diffraction_mtf(nu, fno, wl_um):
    nuc = 1.0 / (wl_um * 1e-3 * fno)
    x = min(nu / nuc, 1.0)
    phi = math.acos(x)
    return (2 / math.pi) * (phi - math.cos(phi) * math.sin(phi))


def per_field_best_focus(mw, field, direction=None, grid=None):
    grid = np.arange(-0.10, 0.10001, 0.001) if grid is None else grid
    if direction is None:
        m = 0.5 * (mw.mtf(field, FREQS[0], "tan", grid) + mw.mtf(field, FREQS[0], "sag", grid))
    else:
        m = mw.mtf(field, FREQS[0], direction, grid)
    k = int(np.argmax(m))
    if 0 < k < len(grid) - 1:
        y0, y1, y2 = m[k - 1], m[k], m[k + 1]
        den = y0 - 2 * y1 + y2
        off = 0.5 * (y0 - y2) / den if den < 0 else 0.0
        return float(grid[k] + off * (grid[1] - grid[0]))
    return float(grid[k])


def pencil_focus(op, Hy, delta=0.04, wl=0.5876):
    """Narrow-pencil (Coddington-style) T and S focus: where rays at +/-delta pupil
    cross, measured along z from the image plane (mm). This is what patent field-curve
    plots show."""
    def trace(Px, Py):
        op.trace_generic(Hx=0.0, Hy=Hy, Px=Px, Py=Py, wavelength=wl)
        sg = op.surface_group
        g = lambda a: float(np.asarray(be.to_numpy(a[-1])).ravel()[0])
        return g(sg.x), g(sg.y), g(sg.L), g(sg.M), g(sg.N)
    _, y1, _, M1, N1 = trace(0.0, delta)
    _, y2, _, M2, N2 = trace(0.0, -delta)
    t_tan = (y2 - y1) / (M1 / N1 - M2 / N2)
    x1, ys1, L1, Ms1, N1s = trace(delta, 0.0)
    x2, ys2, L2, Ms2, N2s = trace(-delta, 0.0)
    t_sag = (x2 - x1) / (L1 / N1s - L2 / N2s)
    return t_tan, t_sag


def run():
    rx = load_prescription()
    pub = rx["published"]
    v = {}

    # 1. first-order
    op = build_optic(rx, fields=[(0.0, 0.0), (0.0, M.HFOV)])
    op.set_ray_aiming("robust")
    efl = float(op.paraxial.f2()); fno = float(op.paraxial.FNO())
    ttl = sum(s["t"] for s in rx["surfaces"])
    imgh_pub = pub["ttl_mm"] / pub["ttl_over_imgh"]
    v["first_order"] = dict(
        efl_mm=dict(rebuilt=round(efl, 4), published=pub["efl_mm"], err_pct=round(100 * (efl / pub["efl_mm"] - 1), 2)),
        fno=dict(rebuilt=round(fno, 4), published=pub["fno"], err_pct=round(100 * (fno / pub["fno"] - 1), 2),
                 note="not an independent check: the aperture is set as EPD = published EFL / published F#, "
                      "so this equals the EFL ratio. The independent aperture check is epd_mm against the "
                      "patent's EPD/ImgH ratio."),
        ttl_mm=dict(rebuilt=round(ttl, 4), published=pub["ttl_mm"], err_pct=round(100 * (ttl / pub["ttl_mm"] - 1), 2)),
        epd_mm=dict(rebuilt=round(float(op.paraxial.EPD()), 4),
                    published_from_ratio=round(pub["epd_over_imgh"] * imgh_pub, 3)),
        imgh_mm_published=round(imgh_pub, 3),
    )

    # 2. element focal lengths
    S = rx["surfaces"]
    rows = []
    for e in range(6):
        s1, s2 = S[2 * e], S[2 * e + 1]
        f_opt = element_f_optiland(s1, s2)
        f_thick = thick_lens_f(s1["R"], s2["R"], s1["t"], s1["n"])
        pubf = pub["element_focal_mm"][e]
        rows.append(dict(element=f"L{e + 1}", published=pubf, optiland=round(f_opt, 3),
                         lensmaker=round(f_thick, 3), err_pct=round(100 * (f_opt / pubf - 1), 2)))
    v["element_focal_lengths"] = rows

    # 3. nominal MTF vs diffraction limit (polychromatic diffraction limit = mean of 3)
    nom = M.nominal()
    tab = nom["mtf"]
    lim = [float(np.mean([diffraction_mtf(nu, fno, w) for w in WAVELENGTHS_UM])) for nu in FREQS]
    under = bool(np.all(tab[:, 0, :] <= lim[0] + 1e-6) and np.all(tab[:, 1, :] <= lim[1] + 1e-6))
    v["mtf_vs_diffraction"] = dict(freqs=[round(f, 1) for f in FREQS], diffraction_limit=[round(x, 3) for x in lim],
                                   nominal_centre=[round(float(tab[0, j].mean()), 3) for j in range(2)],
                                   cutoff_lpmm=round(1 / (0.5876e-3 * fno), 1), all_under=under)

    # 4. tilt hand calc. Sensor tilt about x by theta: a field point at image height y sees
    # the image plane displaced axially by y * tan(theta). Corner K-+ / K++ etc. have y = h/sqrt(2).
    mw0 = M.trace_module(np.zeros(M.DIM))
    fK = M.FIELDS[5]                                   # K++ corner
    h = float(np.hypot(*mw0.data[(mw0.field_coords[5], mw0.primary)].chief_xyz[:2]))
    yK = float(mw0.data[(mw0.field_coords[5], mw0.primary)].chief_xyz[1])
    z0 = per_field_best_focus(mw0, mw0.field_coords[5])
    tilt_rows = []
    for theta in (0.05, 0.10, 0.15):
        u = np.zeros(M.DIM); u[M.NAMES.index("Sensor tx")] = theta / M.LIMITS[M.NAMES.index("Sensor tx")]
        mwt = M.trace_module(u)
        zt = per_field_best_focus(mwt, mwt.field_coords[5])
        hand = yK * math.tan(math.radians(theta))
        tilt_rows.append(dict(theta_deg=theta, hand_calc_um=round(hand * 1e3, 2),
                              traced_um=round(abs(zt - z0) * 1e3, 2)))
    lam = 0.5876e-3
    dof = 2 * lam * fno ** 2
    v["tilt_hand_calc"] = dict(
        corner_image_height_mm=round(h, 3), corner_y_mm=round(yK, 3),
        depth_of_focus_um=round(dof * 1e3, 2),
        tilt_to_reach_dof_deg_diagonal=round(math.degrees(dof / h), 3),
        rows=tilt_rows,
        equation="dz = y_corner * tan(theta); DOF = +/- 2 lambda N^2",
    )

    # 5. field curves and distortion vs FIG. 2 (d line, monochromatic)
    rel = [h_ / imgh_pub for h_ in FIG2["img_ht"]]
    # find field angles giving these image heights: real chief-ray height vs angle
    angs = np.linspace(0, M.HFOV * 0.95, 40)
    opd = build_optic(rx, fields=[(0.0, a) for a in angs], wavelengths=(0.5876,))
    opd.set_ray_aiming("robust")
    ys = []
    for a in angs:
        opd.trace_generic(Hx=0.0, Hy=a / angs.max(), Px=0.0, Py=0.0, wavelength=0.5876)
        ys.append(float(np.asarray(be.to_numpy(opd.surface_group.y[-1])).ravel()[0]))
    ys = np.array(ys)
    want = np.interp(FIG2["img_ht"], ys, angs)
    opm = build_optic(rx, fields=[(0.0, 0.0), (0.0, M.HFOV)], wavelengths=(0.5876,))
    opm.set_ray_aiming("robust")
    t0, s0 = pencil_focus(opm, 1e-6)
    # Distortion reference (Zemax F-Tan(theta) convention): the PARAXIAL chief-ray height on
    # the actual image surface. The patent's image plane sits ~17 um behind paraxial focus,
    # so f*tan(theta) alone leaves a constant +0.63 % offset that does not vanish as theta -> 0.
    yc, _uc = opm.paraxial.chief_ray()
    y_par_max = abs(float(np.ravel(be.to_numpy(yc))[-1]))
    ref_scale = y_par_max / math.tan(math.radians(M.HFOV))      # mm per unit tan(theta)
    curves = []
    for k, hh in enumerate(FIG2["img_ht"]):
        tt, ss = pencil_focus(opm, float(want[k]) / M.HFOV)
        y_real = np.interp(want[k], angs, ys)
        dist = 100 * (y_real / (ref_scale * math.tan(math.radians(want[k]))) - 1)
        dist_f = 100 * (y_real / (efl * math.tan(math.radians(want[k]))) - 1)
        curves.append(dict(img_ht=hh, field_deg=round(float(want[k]), 2),
                           tan_mm=round(tt - t0, 4), tan_patent=FIG2["tan_mm"][k],
                           sag_mm=round(ss - s0, 4), sag_patent=FIG2["sag_mm"][k],
                           distortion_pct=round(float(dist), 2), distortion_patent=FIG2["distortion_pct"][k],
                           distortion_pct_vs_efl_tan=round(float(dist_f), 2)))
    v["fig2_comparison"] = dict(rows=curves, note="Patent values read by eye from FIG. 2 "
                                f"(+/- {FIG2['read_uncertainty_mm']} mm, +/- {FIG2['read_uncertainty_pct']} %). "
                                "Ours: narrow-pencil (+/-0.04 pupil) T and S foci at 587.6 nm relative to the axial pencil focus. "
                                 "Distortion is referenced to the paraxial chief-ray height on the image surface (Zemax "
                                 "F-Tan(theta)); distortion_pct_vs_efl_tan uses EFL*tan(theta) and carries a +0.63 % "
                                 "offset from the 17 um defocus of the patent's image plane.")

    # nominal MTF vs image height (for the brochure chart)
    hts = np.linspace(0, 0.9, 10)
    angs2 = np.interp(hts * imgh_pub, ys, angs)
    opn = build_optic(rx, fields=[(0.0, float(a)) for a in angs2])
    opn.set_ray_aiming("robust")
    mwn = ModuleWavefronts(opn, 40)
    tabn = mwn.mtf_table(nom["dz"])
    v["nominal_mtf_vs_height"] = dict(
        img_ht_mm=[round(float(x), 3) for x in hts * imgh_pub],
        tan_n4=[round(float(x), 3) for x in tabn[:, 0, 0]], sag_n4=[round(float(x), 3) for x in tabn[:, 0, 1]],
        tan_n2=[round(float(x), 3) for x in tabn[:, 1, 0]], sag_n2=[round(float(x), 3) for x in tabn[:, 1, 1]],
        focus_um=round(nom["dz"] * 1e3, 2))
    v["nominal_eval_fields"] = dict(names=M.FIELD_NAMES, field_deg=[list(map(float, f)) for f in M.FIELDS],
                                    mtf=np.round(tab, 4).tolist())
    OUT.mkdir(exist_ok=True)
    (OUT / "validation.json").write_text(json.dumps(v, indent=1))
    return v


if __name__ == "__main__":
    print(json.dumps(run(), indent=1))
