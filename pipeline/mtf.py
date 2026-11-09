"""Polychromatic MTF from traced wavefronts, by pupil autocorrelation.

Why not optiland.mtf.FFTMTF: on this fast (F/1.49) phone lens the outer zones of
the high-order aspheres send some marginal rays to a wrong Newton root (NaN), and
FFTMTF aborts the whole field when that happens. Here those rays are treated as
vignetted (zero amplitude), which is what the barrel's clear apertures do anyway.
On fields where both run, the two agree within about 0.02 MTF (tests/test_mtf.py).

Method, per field and wavelength (equations in METHOD.md):
  1. Trace a square pupil grid with Optiland's chief-ray reference sphere -> OPD W(p)
     (waves) and image-space direction cosines (L, M, N) per ray.
  2. Pupil function P(p) = A(p) exp(2 pi i W(p)); A = 1 for a valid ray, else 0.
  3. Fit the linear map J: p -> (L - Lc, M - Mc). A spatial frequency vector nu
     (cycles/mm) shears the pupil by dp = J^-1 (lambda nu), lambda in mm.
  4. OTF(nu) = sum_p P(p) conj(P(p - dp)) / sum_p A(p), bilinear interpolation.
Polychromatic OTF = mean over wavelengths of OTF_w exp(-2 pi i nu . dx_w), where dx_w is
the chief-ray image point of wavelength w relative to the primary (lateral colour).
Through-focus (the autofocus compensator) is analytic: moving the image plane by dz
moves the reference point by delta = dz (Lc/Nc, Mc/Nc, 1), which adds
-delta . (k - k_chief) / lambda waves to each ray (first order; checked against a
re-trace in tests/test_mtf.py).
"""
from __future__ import annotations

import math

import numpy as np

import optiland.backend as be
from optiland.distribution import create_distribution
from optiland.utils import resolve_fields, resolve_wavelengths
from optiland.wavefront.strategy import create_strategy

PIXEL_UM = 1.12
NYQUIST = 1000.0 / (2 * PIXEL_UM)          # 446.4 lp/mm
FREQS = (NYQUIST / 4, NYQUIST / 2)          # 111.6 and 223.2 lp/mm


def _np(a):
    return np.asarray(be.to_numpy(a), dtype=float).ravel()


class FieldWavefront:
    """Traced pupil data for one field point and one wavelength."""

    def __init__(self, gx, gy, n, opd_waves, valid, L, M, N, chief_xyz, chief_LMN, wl_um):
        self.n = n
        self.wl_mm = wl_um * 1e-3
        self.chief_xyz = np.asarray(chief_xyz, float)
        self.chief_LMN = np.asarray(chief_LMN, float)
        self.ix = np.rint((gx + 1) / 2 * (n - 1)).astype(int)
        self.iy = np.rint((gy + 1) / 2 * (n - 1)).astype(int)
        self.valid = valid
        self.nvalid = int(valid.sum())
        self.vignetting = 1.0 - valid.mean()
        v = valid
        self.flat = (self.iy * n + self.ix)[v]          # flat grid index of each valid ray
        self.W = opd_waves[v]
        Lc, Mc, Nc = self.chief_LMN
        dL, dM, dN = (L - Lc)[v], (M - Mc)[v], (N - Nc)[v]
        # defocus kernel: waves per mm of image-plane shift
        self.D = -((Lc / Nc) * dL + (Mc / Nc) * dM + dN) / self.wl_mm
        if self.nvalid >= 6:
            P = np.stack([gx[v], gy[v]], axis=1)
            Jt, *_ = np.linalg.lstsq(P, np.stack([dL, dM], axis=1), rcond=None)
            self.J = Jt.T
        else:
            self.J = np.eye(2) * 0.3
        self.Jinv = np.linalg.inv(self.J)
        self._wcache = {}

    def chief_point(self, dz):
        Lc, Mc, Nc = self.chief_LMN
        x, y, _ = self.chief_xyz
        return np.array([x + dz * Lc / Nc, y + dz * Mc / Nc])

    def _weights(self, key, nu_vec):
        """Bilinear neighbour indices/weights of p - dp for every valid ray."""
        if key in self._wcache:
            return self._wcache[key]
        n = self.n
        dp = self.Jinv @ (self.wl_mm * np.asarray(nu_vec, float))
        sx, sy = dp[0] * (n - 1) / 2, dp[1] * (n - 1) / 2
        x = self.ix[self.valid] - sx
        y = self.iy[self.valid] - sy
        x0, y0 = np.floor(x).astype(int), np.floor(y).astype(int)
        fx, fy = x - x0, y - y0
        idx, wts = [], []
        for ddx, ddy, w in ((0, 0, (1 - fx) * (1 - fy)), (1, 0, fx * (1 - fy)),
                            (0, 1, (1 - fx) * fy), (1, 1, fx * fy)):
            xx, yy = x0 + ddx, y0 + ddy
            inside = (xx >= 0) & (xx < n) & (yy >= 0) & (yy < n)
            idx.append(np.where(inside, yy * n + xx, n * n))  # n*n = zero pad
            wts.append(np.where(inside, w, 0.0))
        out = (np.stack(idx), np.stack(wts))
        self._wcache[key] = out
        return out

    def otf(self, key, nu_vec, dz):
        """Complex OTF for an array of focus shifts dz (mm). Returns shape (len(dz),)."""
        dz = np.atleast_1d(dz)
        if self.nvalid == 0:
            return np.zeros(len(dz), complex)
        idx, wts = self._weights(key, nu_vec)
        phase = 2 * np.pi * (self.W[None, :] + dz[:, None] * self.D[None, :])
        Pv = np.exp(1j * phase)                                  # (ndz, nvalid)
        grid = np.zeros((len(dz), self.n * self.n + 1), complex)
        grid[:, self.flat] = Pv
        shifted = (grid[:, idx] * wts[None]).sum(axis=1)         # (ndz, nvalid)
        return (Pv * np.conj(shifted)).sum(axis=1) / self.nvalid


class _WF:
    """Chief-ray wavefront strategy without Optiland's eager all-field trace."""

    def __init__(self, optic, n_grid):
        self.fields = resolve_fields(optic, "all")
        self.wavelengths = resolve_wavelengths(optic, "all")
        self.distribution = create_distribution("uniform")
        self.distribution.generate_points(n_grid)
        self.strategy = create_strategy(strategy_name="chief_ray", optic=optic,
                                        distribution=self.distribution, reference_type="sphere")


class ModuleWavefronts:
    """All fields x wavelengths of one (possibly perturbed) optic."""

    def __init__(self, optic, n_grid=40):
        self.n = n_grid
        wf = _WF(optic, n_grid)
        gx, gy = _np(wf.distribution.x), _np(wf.distribution.y)
        self.field_coords = [fp.coord for fp in wf.fields]
        self.wls = [wp.value for wp in wf.wavelengths]
        self.primary = self.wls[len(self.wls) // 2]
        self.data = {}
        for f in self.field_coords:
            for wl in self.wls:
                try:
                    d = wf.strategy.compute_wavefront_data(f, wl)
                    opd, inten = _np(d.opd), _np(d.intensity)
                    sg = optic.surface_group                      # last trace = pupil grid
                    L, M, N = _np(sg.L[-1]), _np(sg.M[-1]), _np(sg.N[-1])
                    chief = wf.strategy._chief_ray
                    cxyz = (float(_np(chief.x)[0]), float(_np(chief.y)[0]), float(_np(chief.z)[0]))
                    cLMN = (float(_np(chief.L)[0]), float(_np(chief.M)[0]), float(_np(chief.N)[0]))
                    valid = np.isfinite(opd) & (inten > 0) & np.isfinite(L) & np.isfinite(M)
                except ValueError:  # chief ray failed: whole field lost
                    m = len(gx)
                    opd = np.zeros(m); L = M = np.zeros(m); N = np.ones(m)
                    valid = np.zeros(m, bool); cxyz = (0.0, 0.0, 0.0); cLMN = (0.0, 0.0, 1.0)
                if valid.any():
                    opd = opd - np.mean(opd[valid])
                self.data[(f, wl)] = FieldWavefront(gx, gy, n_grid, np.nan_to_num(opd), valid,
                                                    np.nan_to_num(L), np.nan_to_num(M),
                                                    np.nan_to_num(N, nan=1.0), cxyz, cLMN, wl)

    def _dir(self, field, direction):
        prim = self.data[(field, self.primary)]
        cp = prim.chief_xyz[:2]
        if math.hypot(*field) < 1e-9 or np.linalg.norm(cp) < 1e-6:
            radial = np.array([0.0, 1.0])
        else:
            radial = cp / np.linalg.norm(cp)
        return radial if direction == "tan" else np.array([-radial[1], radial[0]])

    def mtf(self, field, nu, direction, dz=0.0):
        """Polychromatic MTF; dz may be an array. Returns array of len(dz)."""
        dz = np.atleast_1d(np.asarray(dz, float))
        u = self._dir(field, direction)
        nu_vec = nu * u
        key = (round(nu, 4), direction)
        prim = self.data[(field, self.primary)]
        p0 = prim.chief_point(0.0)
        Lp, Mp, Np_ = prim.chief_LMN
        total = np.zeros(len(dz), complex)
        for wl in self.wls:
            fw = self.data[(field, wl)]
            # lateral colour: chief point offset vs primary, including its change with dz
            Lc, Mc, Nc = fw.chief_LMN
            dx0 = fw.chief_point(0.0) - p0
            slope = np.array([Lc / Nc - Lp / Np_, Mc / Nc - Mp / Np_])
            dxs = dx0[None, :] + dz[:, None] * slope[None, :]
            total += fw.otf(key, nu_vec, dz) * np.exp(-2j * np.pi * (dxs @ nu_vec))
        return np.abs(total / len(self.wls))

    def mtf_table(self, dz=0.0, freqs=FREQS):
        """Array [field, freq, (tan, sag)] at a single focus shift dz (mm)."""
        out = np.zeros((len(self.field_coords), len(freqs), 2))
        for i, f in enumerate(self.field_coords):
            for j, nu in enumerate(freqs):
                out[i, j, 0] = self.mtf(f, nu, "tan", dz)[0]
                out[i, j, 1] = self.mtf(f, nu, "sag", dz)[0]
        return out

    def merit_curve(self, dz_grid, nu=FREQS[0]):
        """Mean over fields of (T+S)/2 MTF at nu, for every dz in dz_grid."""
        acc = np.zeros(len(dz_grid))
        for f in self.field_coords:
            acc += 0.5 * (self.mtf(f, nu, "tan", dz_grid) + self.mtf(f, nu, "sag", dz_grid))
        return acc / len(self.field_coords)

    def best_focus(self, center=0.0, half_range=0.030, step=0.002):
        """Autofocus compensator: grid search + parabolic refinement of merit_curve."""
        grid = center + np.arange(-half_range, half_range + 1e-12, step)
        m = self.merit_curve(grid)
        k = int(np.argmax(m))
        if 0 < k < len(grid) - 1:
            y0, y1, y2 = m[k - 1], m[k], m[k + 1]
            den = y0 - 2 * y1 + y2
            off = 0.5 * (y0 - y2) / den if den < 0 else 0.0
            dz = grid[k] + np.clip(off, -1, 1) * step
        else:
            dz = grid[k]
        return float(dz)
