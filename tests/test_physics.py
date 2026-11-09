"""Hand calcs and physical sanity checks on traced modules."""
import math

import numpy as np
import pytest

from pipeline import module as M
from pipeline.validate import per_field_best_focus


def test_sensor_tilt_defocus_matches_hand_calc():
    mw0 = M.trace_module(np.zeros(M.DIM))
    f = mw0.field_coords[5]
    y = mw0.data[(f, mw0.primary)].chief_xyz[1]
    z0 = per_field_best_focus(mw0, f)
    theta = 0.10
    u = np.zeros(M.DIM); i = M.NAMES.index("Sensor tx"); u[i] = theta / M.LIMITS[i]
    mwt = M.trace_module(u)
    zt = per_field_best_focus(mwt, mwt.field_coords[5])
    hand = y * math.tan(math.radians(theta))
    assert abs(zt - z0) == pytest.approx(hand, rel=0.05)


def test_depth_of_focus_hand_calc():
    lam, N = 0.5876e-3, 1.49
    assert 2 * lam * N ** 2 * 1e3 == pytest.approx(2.61, abs=0.01)


def test_barrel_decenter_changes_nothing_but_image_position():
    u = np.zeros(M.DIM); u[M.NAMES.index("Barrel dx")] = 1.0
    a = M.simulate(np.zeros(M.DIM)); b = M.simulate(u)
    # 40x40 pupil-grid sampling noise floor is ~0.008 MTF (METHOD.md); spec fields move < 1e-4
    assert np.max(np.abs(a["mtf"] - b["mtf"])) < 0.01
    assert abs(a["corner_min"] - b["corner_min"]) < 1e-3 and abs(a["centre"] - b["centre"]) < 1e-3


def test_decenter_loss_is_even_in_sign():
    i = M.NAMES.index("L1 dx")
    up = np.zeros(M.DIM); up[i] = 1; dn = np.zeros(M.DIM); dn[i] = -1
    a, b = M.simulate(up), M.simulate(dn)
    assert a["corner_min"] == pytest.approx(b["corner_min"], abs=2e-3)
    assert a["corner_min"] < M.metrics_from_table(M.nominal()["mtf"])["corner_min"] - 0.01


def test_mc_sampling_is_seed_reproducible_and_truncated():
    a = M.sample_u(500, np.random.default_rng(42)); b = M.sample_u(500, np.random.default_rng(42))
    assert np.array_equal(a, b)
    assert np.abs(a).max() <= 1.0
    assert a.std() == pytest.approx(0.44, abs=0.03)  # sigma 0.5 truncated at 2 sigma -> 0.44


def test_simulation_is_deterministic():
    u = M.sample_u(1, np.random.default_rng(3))[0]
    assert np.array_equal(M.simulate(u)["mtf"], M.simulate(u)["mtf"])
