"""The D4 augmentation used to train the surrogate is exact physics: check by ray trace."""
import numpy as np

from pipeline import module as M, stack as S, symmetry as SY


def _y(u):
    return S.field_outputs(M.simulate(u[0])["mtf"][None])


def test_rotation_by_90_deg_permutes_corners():
    u = M.sample_u(1, np.random.default_rng(9))
    ur, yr = SY.rotate(u, _y(u))
    assert np.max(np.abs(yr - _y(ur))) < 2e-3


def test_mirror_permutes_corners():
    u = M.sample_u(1, np.random.default_rng(10))
    um, ym = SY.mirror(u, _y(u))
    assert np.max(np.abs(ym - _y(um))) < 2e-3


def test_augment_is_the_full_orbit():
    u = M.sample_u(3, np.random.default_rng(0)); y = np.arange(15.0).reshape(3, 5)
    Ua, Ya = SY.augment(u, y)
    assert Ua.shape == (24, M.DIM) and Ya.shape == (24, 5)
    r4 = u
    for _ in range(4):
        r4, _ = SY.rotate(r4)
    assert np.allclose(r4, u)  # four quarter turns = identity
