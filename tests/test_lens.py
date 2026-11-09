"""Prescription parsing, first-order optics and the rigid-body perturbation geometry."""
import math

import numpy as np
import pytest

from pipeline.lens import Perturbation, build_optic, load_prescription, surface_layout
from pipeline.validate import thick_lens_f, element_f_optiland


def test_prescription_parses_and_ttl_matches_patent():
    rx = load_prescription()
    assert len(rx["surfaces"]) == 14
    assert max(s["element"] for s in rx["surfaces"]) == 6
    ttl = sum(s["t"] for s in rx["surfaces"])
    assert ttl == pytest.approx(rx["published"]["ttl_mm"], abs=0.005)
    for s in rx["surfaces"][:12]:
        assert len(s["A"]) == 7  # A4..A16


def test_paraxial_efl_and_fno_match_patent():
    op = build_optic()
    assert float(op.paraxial.f2()) == pytest.approx(3.43, rel=0.005)
    assert float(op.paraxial.FNO()) == pytest.approx(1.49, rel=0.005)


@pytest.mark.parametrize("e", range(6))
def test_element_focal_lengths_lensmaker_and_optiland(e):
    rx = load_prescription()
    s1, s2 = rx["surfaces"][2 * e], rx["surfaces"][2 * e + 1]
    pub = rx["published"]["element_focal_mm"][e]
    f_thick = thick_lens_f(s1["R"], s2["R"], s1["t"], s1["n"])
    assert f_thick == pytest.approx(pub, rel=0.01)
    assert element_f_optiland(s1, s2) == pytest.approx(f_thick, rel=1e-3)


def test_rigid_element_tilt_preserves_thickness_and_axis():
    rx = load_prescription()
    nom = surface_layout(rx)
    p = Perturbation(); p.elem_tx[2] = 0.5  # L3 tilted 0.5 deg about x
    lay = surface_layout(rx, p)
    i = [k for k, s in enumerate(lay) if s["element"] == 3]
    d_nom = np.linalg.norm(nom[i[1]]["pos"] - nom[i[0]]["pos"])
    d_new = np.linalg.norm(lay[i[1]]["pos"] - lay[i[0]]["pos"])
    assert d_new == pytest.approx(d_nom, abs=1e-12)
    # both vertices lie on one line tilted by 0.5 deg
    v = lay[i[1]]["pos"] - lay[i[0]]["pos"]
    assert math.degrees(math.atan2(-v[1], v[2])) == pytest.approx(0.5, abs=1e-9)
    assert lay[i[0]]["rx"] == pytest.approx(math.radians(0.5))


def test_stop_sits_behind_L1_vertex():
    lay = surface_layout(load_prescription())
    assert lay[1]["name"] == "stop"
    assert lay[1]["pos"][2] == pytest.approx(0.379)
