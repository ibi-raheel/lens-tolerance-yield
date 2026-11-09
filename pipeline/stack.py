"""Classical tolerance stacks built from the 2k+1 sensitivity traces.

Baseline A, limit-based RSS (how Zemax/CODE V-style sensitivity tolerancing reports it):
  for each tolerance i, trace it alone at +limit and at -limit with the compensator
  (autofocus) re-optimised; take the worse change of the criterion,
      d_i = min(m(+L_i), m(-L_i)) - m0
  and root-sum-square them, RSS = sqrt(sum d_i^2). The limit is 2 sigma of the
  Monte Carlo sampling, so the criterion is modelled as Normal(m0, (RSS/2)^2), no mean
  shift (the RSS method reports nominal +/- RSS). Yield = product of the pass
  probabilities of the two criteria (treated as independent).

Baseline B, second-order (diagonal quadratic) stack:
  each field-point output y_f (centre and the four corners) is modelled per tolerance as
      y_f(u) = y_f0 + sum_i (a_fi u_i + b_fi u_i^2),  u_i in units of the limit,
      a_fi = (y_f(+1) - y_f(-1)) / 2,   b_fi = (y_f(+1) + y_f(-1)) / 2 - y_f0
  which captures the one-sided (quadratic) loss from tilt and decenter but no interactions
  and no compensator coupling. It predicts every module, so yield = share of modules whose
  predicted criteria pass.

Footnote, derivative-based linear stack: y_f = y_f0 + sum_i a_fi u_i (B without b).
"""
from __future__ import annotations

import math

import numpy as np
from scipy.stats import norm

from . import module as M


def field_outputs(mtf: np.ndarray) -> np.ndarray:
    """mtf[..., 9, 2, 2] -> (T+S)/2 at N/4 for [centre, 4 corners] -> [..., 5]."""
    avg = mtf[..., 0, :].mean(axis=-1)          # [..., 9]
    return np.concatenate([avg[..., [0]], avg[..., M.CORNERS]], axis=-1)


def criteria(y5: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    return y5[..., 0], y5[..., 1:].min(axis=-1)


class SensitivityStack:
    def __init__(self, sens_mtf: np.ndarray):
        """sens_mtf: [2k+1, 9, 2, 2], order nominal, (+1, -1) for each tolerance."""
        y = field_outputs(sens_mtf)               # [2k+1, 5]
        self.y0 = y[0]
        yp, ym = y[1::2], y[2::2]                 # [k, 5]
        self.a = (yp - ym) / 2
        self.b = (yp + ym) / 2 - self.y0
        c0, k0 = criteria(self.y0)
        cp, kp = criteria(yp); cm, km = criteria(ym)
        self.m0 = (float(c0), float(k0))
        self.d_centre = np.minimum(cp, cm) - c0
        self.d_corner = np.minimum(kp, km) - k0
        self.rss = (float(np.sqrt(np.sum(self.d_centre ** 2))), float(np.sqrt(np.sum(self.d_corner ** 2))))
        self.traces = int(sens_mtf.shape[0])

    # Baseline A ------------------------------------------------------------------------
    def yield_A(self, thr: dict) -> float:
        sc, sk = self.rss[0] / 2, self.rss[1] / 2
        pc = norm.cdf((self.m0[0] - thr["centre"]) / max(sc, 1e-12))
        pk = norm.cdf((self.m0[1] - thr["corner_min"]) / max(sk, 1e-12))
        return float(pc * pk)

    def yield_A_scaled(self, thr: dict, k: np.ndarray) -> float:
        """Same recipe for a budget whose limits are scaled by k (per tolerance), assuming the
        traced change at the new limit scales as the tolerance (linear) or its square
        (quadratic). We use the quadratic fit of B to re-evaluate the change at the new limit."""
        y0 = self.y0
        yp = y0 + self.a * k[:, None] + self.b * (k[:, None] ** 2)
        ym = y0 - self.a * k[:, None] + self.b * (k[:, None] ** 2)
        cp, kp = criteria(yp); cm, km = criteria(ym)
        dc = np.minimum(cp, cm) - self.m0[0]; dk = np.minimum(kp, km) - self.m0[1]
        sc, sk = math.sqrt(np.sum(dc ** 2)) / 2, math.sqrt(np.sum(dk ** 2)) / 2
        return float(norm.cdf((self.m0[0] - thr["centre"]) / sc) * norm.cdf((self.m0[1] - thr["corner_min"]) / sk))

    # Baseline B ------------------------------------------------------------------------
    def predict_B(self, U: np.ndarray) -> np.ndarray:
        return self.y0 + U @ self.a + (U ** 2) @ self.b

    def predict_linear(self, U: np.ndarray) -> np.ndarray:
        return self.y0 + U @ self.a
