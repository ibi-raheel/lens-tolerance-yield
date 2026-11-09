"""MTF engine: diffraction limit, through-focus, agreement with Optiland's FFT MTF."""
import math

import numpy as np
import pytest

from pipeline.lens import Perturbation, build_optic
from pipeline.mtf import FieldWavefront, ModuleWavefronts
from pipeline.validate import diffraction_mtf


def test_perfect_pupil_gives_circular_aperture_mtf():
    n = 64
    x = np.linspace(-1, 1, n)
    gx, gy = np.meshgrid(x, x)
    m = gx ** 2 + gy ** 2 <= 1
    gx, gy = gx[m], gy[m]
    na = 1 / (2 * 2.0)  # F/2
    L, M = na * gx, na * gy
    N = np.sqrt(1 - L ** 2 - M ** 2)
    fw = FieldWavefront(gx, gy, n, np.zeros_like(gx), np.ones_like(gx, bool), L, M, N,
                        (0, 0, 0), (0, 0, 1), 0.55)
    for nu in (100, 300, 600):
        got = abs(fw.otf(("t", nu), np.array([0.0, nu]), 0.0)[0])
        assert got == pytest.approx(diffraction_mtf(nu, 2.0, 0.55), abs=0.02)


def test_analytic_defocus_matches_retrace():
    f = [(0.0, 0.0), (0.0, 19.75)]
    op = build_optic(fields=f); op.set_ray_aiming("robust")
    op2 = build_optic(pert=Perturbation(focus=0.006), fields=f); op2.set_ray_aiming("robust")
    a = ModuleWavefronts(op, 40).mtf_table(0.006)
    b = ModuleWavefronts(op2, 40).mtf_table(0.0)
    assert np.max(np.abs(a - b)) < 0.02


def test_agrees_with_optiland_fft_mtf_on_axis():
    from optiland.mtf import FFTMTF
    op = build_optic(fields=[(0.0, 0.0)], wavelengths=(0.5876,)); op.set_ray_aiming("robust")
    ref = FFTMTF(op, fields="all", wavelength=0.5876, num_rays=128, max_freq=450)
    ours = ModuleWavefronts(op, 48).mtf_table(0.0)
    for j, nu in enumerate((111.6, 223.2)):
        r = float(np.interp(nu, np.asarray(ref.freq_tang[0]), np.asarray(ref.mtf[0][0])))
        assert ours[0, j, 0] == pytest.approx(r, abs=0.02)


def test_nominal_below_diffraction_limit():
    from pipeline import module as M
    tab = M.nominal()["mtf"]
    for j, nu in enumerate((111.6, 223.2)):
        lim = np.mean([diffraction_mtf(nu, 1.49, w) for w in (0.4861, 0.5876, 0.6563)])
        assert np.all(tab[:, j, :] <= lim)
