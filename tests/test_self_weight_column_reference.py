"""Independent shooting and scaling checks for the Airy static reference."""
import sys
from pathlib import Path

import numpy as np
import pytest
from scipy.integrate import solve_ivp
from scipy.optimize import brentq

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
import self_weight_column_reference as reference


def shoot(load):
    # Integrate from the free tip, theta=1 and M/EI=0, toward the clamp.
    return solve_ivp(lambda s, y: [y[1], -load*(1-s)*y[0]],
                     (1., 0.), [1., 0.], method='DOP853', rtol=2e-12, atol=2e-13,
                     dense_output=True)


def test_airy_root_against_independent_differential_equation_shooting():
    load = brentq(lambda g: shoot(g).y[0, -1], 5., 10., xtol=1e-12)
    assert reference.critical(ei=1.) == pytest.approx(load, rel=2e-11)
    assert load == pytest.approx(7.8373474389435, rel=2e-11)
    s = np.linspace(0., 1., 31)
    _, theta = reference.shapes(s)
    shot = shoot(load).sol(s)[0]
    np.testing.assert_allclose(theta/theta[-1], shot, rtol=1e-10, atol=1e-11)


def test_length_mass_stiffness_scaling_and_clamped_free_shape():
    g = reference.critical()
    assert reference.critical(ei=200.) == pytest.approx(2*g)
    assert reference.critical(mass_per_length=2.) == pytest.approx(g/2)
    assert reference.critical(length=2.) == pytest.approx(g/8)
    w, theta = reference.shapes([0., .5, 1.])
    assert abs(w[0]) < 1e-13 and abs(theta[0]) < 1e-13
    assert w[-1] == pytest.approx(1.)
    assert 0 < w[1] < 1 and 0 < theta[1] < theta[-1]
