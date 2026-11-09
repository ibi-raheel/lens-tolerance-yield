"""The two classical stacks implement the documented recipes."""
import numpy as np
import pytest
from scipy.stats import norm

from pipeline import module as M
from pipeline.stack import SensitivityStack, criteria, field_outputs


def _fake_sens(y0, plus, minus):
    """Build a [2k+1, 9, 2, 2] array whose field outputs are the given 5-vectors."""
    k = len(plus)
    arr = np.zeros((2 * k + 1, 9, 2, 2))
    def put(i, y5):
        arr[i, 0, 0, :] = y5[0]
        for c, f in enumerate(M.CORNERS):
            arr[i, f, 0, :] = y5[1 + c]
    put(0, y0)
    for i in range(k):
        put(1 + 2 * i, plus[i]); put(2 + 2 * i, minus[i])
    return arr


def test_field_outputs_roundtrip():
    y0 = np.array([0.6, 0.3, 0.31, 0.32, 0.33])
    arr = _fake_sens(y0, [y0], [y0])
    assert np.allclose(field_outputs(arr)[0], y0)


def test_baseline_A_is_rss_of_worse_limit_change():
    y0 = np.array([0.6, 0.3, 0.3, 0.3, 0.3])
    plus = [y0 - [0.0, 0.02, 0, 0, 0], y0 + [0.01, 0, 0, 0, 0]]
    minus = [y0 - [0.0, 0.01, 0, 0, 0], y0 - [0.03, 0, 0, 0, 0]]
    st = SensitivityStack(_fake_sens(y0, plus, minus))
    assert st.rss[1] == pytest.approx(0.02)
    assert st.rss[0] == pytest.approx(0.03)
    thr = dict(centre=0.57, corner_min=0.28)
    want = norm.cdf(0.03 / 0.015) * norm.cdf(0.02 / 0.01)
    assert st.yield_A(thr) == pytest.approx(want)


def test_baseline_B_recovers_a_diagonal_quadratic_exactly():
    rng = np.random.default_rng(0)
    k = 4
    y0 = np.array([0.6, 0.3, 0.3, 0.3, 0.3])
    a = rng.normal(0, 0.01, (k, 5)); b = -np.abs(rng.normal(0, 0.01, (k, 5)))
    plus = [y0 + a[i] + b[i] for i in range(k)]
    minus = [y0 - a[i] + b[i] for i in range(k)]
    st = SensitivityStack(_fake_sens(y0, plus, minus))
    U = rng.uniform(-1, 1, (50, k))
    assert np.allclose(st.predict_B(U), y0 + U @ a + (U ** 2) @ b)
