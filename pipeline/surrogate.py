"""Trained surrogates: perturbation vector u (41, units of current limit) -> the five
field outputs (centre + four corners, (T+S)/2 MTF at Nyquist/4, after autofocus).

Candidates (all scored only on the held-out Monte Carlo set):
  mlp        neural net (2 hidden layers) on u
  hybrid     the same neural net trained on the residual of the second-order stack,
             y = B(u) + NN(u): physics prior + learned interactions
  gbm        gradient-boosted trees (LightGBM), one per output
  quad_ridge full quadratic response surface (all 902 square/cross terms), ridge
"""
from __future__ import annotations

import json
import warnings

import numpy as np
from sklearn.linear_model import RidgeCV
from sklearn.neural_network import MLPRegressor
from sklearn.preprocessing import PolynomialFeatures, StandardScaler

warnings.filterwarnings("ignore")


class MLPSurrogate:
    name = "mlp"

    def __init__(self, hidden=(96, 96), alpha=1e-4, seed=0, base=None):
        self.hidden, self.alpha, self.seed, self.base = hidden, alpha, seed, base

    def _base(self, U):
        return self.base.predict_B(U) if self.base is not None else 0.0

    def fit(self, U, Y):
        R = Y - self._base(U)
        self.xs = StandardScaler().fit(U)
        self.ys = StandardScaler().fit(R)
        self.m = MLPRegressor(hidden_layer_sizes=self.hidden, activation="tanh", alpha=self.alpha,
                              learning_rate_init=2e-3, max_iter=3000, early_stopping=True,
                              validation_fraction=0.15, n_iter_no_change=60, random_state=self.seed)
        self.m.fit(self.xs.transform(U), self.ys.transform(R))
        return self

    def predict(self, U):
        r = self.ys.inverse_transform(self.m.predict(self.xs.transform(U)).reshape(len(U), -1))
        return r + self._base(U)

    def export(self) -> dict:
        """Weights for the in-browser scrubber (tanh MLP, standardised in/out)."""
        return dict(x_mean=self.xs.mean_.tolist(), x_scale=self.xs.scale_.tolist(),
                    y_mean=self.ys.mean_.tolist(), y_scale=self.ys.scale_.tolist(),
                    weights=[w.tolist() for w in self.m.coefs_],
                    biases=[b.tolist() for b in self.m.intercepts_], activation="tanh",
                    residual_of_quadratic_stack=self.base is not None)


class GBMSurrogate:
    name = "gbm"

    def fit(self, U, Y):
        import lightgbm as lgb
        self.ms = [lgb.LGBMRegressor(n_estimators=600, learning_rate=0.03, num_leaves=15,
                                     min_child_samples=10, subsample=0.8, subsample_freq=1,
                                     colsample_bytree=0.8, verbose=-1, n_jobs=1).fit(U, Y[:, j])
                   for j in range(Y.shape[1])]
        return self

    def predict(self, U):
        return np.stack([m.predict(U) for m in self.ms], axis=1)


class QuadRidgeSurrogate:
    name = "quad_ridge"

    def fit(self, U, Y):
        self.pf = PolynomialFeatures(2, include_bias=False)
        X = self.pf.fit_transform(U)
        self.xs = StandardScaler().fit(X)
        self.m = RidgeCV(alphas=np.logspace(-4, 3, 15)).fit(self.xs.transform(X), Y)
        return self

    def predict(self, U):
        return self.m.predict(self.xs.transform(self.pf.transform(U)))


def make(name, stack=None, seed=0):
    if name == "mlp":
        return MLPSurrogate(seed=seed)
    if name == "hybrid":
        s = MLPSurrogate(seed=seed, base=stack); s.name = "hybrid"; return s
    if name == "gbm":
        return GBMSurrogate()
    if name == "quad_ridge":
        return QuadRidgeSurrogate()
    raise ValueError(name)


def save_json(obj, path):
    path.write_text(json.dumps(obj))
