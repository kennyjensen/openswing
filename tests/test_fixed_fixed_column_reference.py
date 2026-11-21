"""Independent boundary-value checks for the analytical column reference."""
import importlib.util
from pathlib import Path

import numpy as np
import pytest

PATH = Path(__file__).resolve().parents[1]/'scripts/verify-fixed-fixed-column.py'
SPEC = importlib.util.spec_from_file_location('fixed_column_reference', PATH)
reference = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(reference)


@pytest.mark.parametrize('ei,count,ratio', [(100., 4, 0.), (100., 16, .5),
    (100., 16, 1.5), (200., 8, .3)])
def test_closed_form_against_independent_four_state_boundary_problem(ei, count, ratio):
    # Physical states [w, theta, M, F], with w'=theta, EI theta'=M,
    # M'=-P theta-F and F'=0. Solve unknown root M and transverse F
    # from unit end displacement and zero end rotation.
    load = ratio*reference.critical(ei)
    operator = np.zeros((4, 4))
    operator[0, 1] = 1.
    operator[1, 2] = 1/ei
    operator[2, 1] = -load
    operator[2, 3] = -1.
    h = reference.L/count
    transfer = np.linalg.solve(np.eye(4)-h*operator/2, np.eye(4)+h*operator/2)
    full = np.linalg.matrix_power(transfer, count)
    moment, force = np.linalg.solve(full[:2, 2:], [1., 0.])
    state = np.array([0., 0., moment, force])
    states = [state.copy()]
    for _ in range(count):
        state = transfer@state
        states.append(state.copy())
    states = np.array(states)
    displacement, rotation = reference.shapes(load, ei, count)
    np.testing.assert_allclose(states[:, 0], displacement, rtol=1e-11, atol=1e-12)
    np.testing.assert_allclose(states[:, 1], rotation, rtol=1e-11, atol=1e-12)
    assert force == pytest.approx(reference.stiffness(load, ei, count), rel=1e-11)


def test_full_length_euler_limit_and_fixed_fixed_symmetry():
    full_length = 2*reference.L
    assert reference.critical() == pytest.approx(4*np.pi**2*100/full_length**2)
    count = 16
    # At the first discrete critical load the symmetric full-column mode
    # is 1-cos(2*pi*x/full_length), normalized to unit midpoint motion.
    w, theta = reference.shapes(reference.critical(count=count), 100., count)
    s = np.linspace(0., reference.L, count+1)
    np.testing.assert_allclose(w, (1-np.cos(np.pi*s/reference.L))/2, atol=1e-13)
    assert w[0] == 0 and w[-1] == pytest.approx(1.)
    assert theta[0] == 0 and abs(theta[-1]) < 1e-12
    assert reference.stiffness(.9999*reference.critical(count=count), 100., count) > 0
    assert reference.stiffness(1.0001*reference.critical(count=count), 100., count) < 0
