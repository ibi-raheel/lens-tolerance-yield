"""Rotational symmetry of the nominal lens -> exact data augmentation (dihedral group D4).

Rotating the whole module by +90 deg about the optical axis maps every x/y pair as a
vector, (dx, dy) -> (-dy, dx) and (tx, ty) -> (-ty, tx) (a tilt is a rotation vector),
leaves thicknesses and gaps unchanged, and moves each corner to the next one:
K++ -> K-+ -> K-- -> K+- -> K++. Mirroring x -> -x maps (dx, dy) -> (-dx, dy),
(tx, ty) -> (tx, -ty) (axial vector) and swaps K++ <-> K-+, K-- <-> K+-.
Checked against direct ray traces in tests/test_symmetry.py.
"""
from __future__ import annotations

import numpy as np

from . import module as M

# outputs: [centre, K++, K-+, K--, K+-]
_ROT_OUT = np.array([0, 4, 1, 2, 3])   # new[i] = old[_ROT_OUT[i]]
_MIR_OUT = np.array([0, 2, 1, 4, 3])


def _pairs():
    pairs = []
    for i, t in enumerate(M.TOLS):
        if t.attr.endswith("x") and t.attr[:-1] + "y" in {s.attr for s in M.TOLS}:
            j = next(k for k, s in enumerate(M.TOLS) if s.attr == t.attr[:-1] + "y" and s.index == t.index)
            kind = "tilt" if t.attr.endswith("tx") else "dec"
            pairs.append((i, j, kind))
    return pairs


def rotate(U, Y=None):
    U2 = U.copy()
    for i, j, _ in _pairs():
        U2[:, i], U2[:, j] = -U[:, j], U[:, i]
    return (U2, None if Y is None else Y[:, _ROT_OUT])


def mirror(U, Y=None):
    U2 = U.copy()
    for i, j, kind in _pairs():
        if kind == "dec":
            U2[:, i] = -U[:, i]
        else:
            U2[:, j] = -U[:, j]
    return (U2, None if Y is None else Y[:, _MIR_OUT])


def augment(U, Y):
    """All 8 symmetry images of every module."""
    Us, Ys = [], []
    for m in (False, True):
        u, y = (mirror(U, Y) if m else (U, Y))
        for _ in range(4):
            Us.append(u); Ys.append(y)
            u, y = rotate(u, y)
    return np.vstack(Us), np.vstack(Ys)


# full 9-field tables [C, M+x, M-x, M+y, M-y, K++, K-+, K--, K+-]: new[i] = old[perm[i]]
FIELD_ROT = np.array([0, 4, 3, 1, 2, 8, 5, 6, 7])
FIELD_MIR = np.array([0, 2, 1, 3, 4, 6, 5, 8, 7])


def augment_tables(T, labels):
    """8 symmetry images of MTF tables T[n, 9, ...] (culprit labels are invariant)."""
    Ts, Ls = [], []
    for m in (False, True):
        t = T[:, FIELD_MIR] if m else T
        for _ in range(4):
            Ts.append(t); Ls.append(labels)
            t = t[:, FIELD_ROT]
    return np.concatenate(Ts), np.concatenate(Ls)
