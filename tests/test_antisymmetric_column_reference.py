"""Separate transfer-matrix and Euler checks of the closed-form reference."""
import sys
from pathlib import Path

import numpy as np
import pytest
from scipy.linalg import expm

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
import antisymmetric_column_reference as reference


@pytest.mark.parametrize('ei,count,ratio', [(100., 4, 0.), (100., 16, .5),
    (100., 16, 1.5), (200., 8, .3), (100., None, .7)])
def test_closed_form_against_four_state_boundary_problem(ei, count, ratio):
    load = ratio*reference.critical(ei)
    operator = np.zeros((4, 4))
    operator[0, 1] = 1.
    operator[1, 2] = 1/ei
    operator[2, 1] = -load
    operator[2, 3] = -1.
    if count is None:
        full = expm(reference.L*operator)
    else:
        h = reference.L/count
        transfer = np.linalg.solve(np.eye(4)-h*operator/2, np.eye(4)+h*operator/2)
        full = np.linalg.matrix_power(transfer, count)
    moment, force = np.linalg.solve(full[:2, 2:], [0., 1.])
    initial = np.array([0., 0., moment, force])
    end = full@initial
    assert end[2] == pytest.approx(reference.stiffness(load, ei, count), rel=2e-11)
    if count is not None:
        states = [initial]
        for _ in range(count):
            states.append(transfer@states[-1])
        w, theta = reference.shapes(load, ei, count)
        np.testing.assert_allclose(np.asarray(states)[:, :2], np.c_[w, theta], rtol=1e-11, atol=1e-12)


def test_antisymmetric_euler_root_and_critical_shape():
    # The first antisymmetric fixed-fixed root obeys tan(qL)=qL and is
    # distinct from the symmetric qL=pi root.
    root = np.sqrt(reference.critical()/100)*reference.L
    assert root == pytest.approx(4.493409457909064, rel=2e-14)
    for count in (4, 16, 96):
        load = reference.critical(count=count)
        assert load > reference.critical()
        w, theta = reference.shapes(load, 100., count)
        assert abs(w[0]) < 1e-13 and abs(w[-1]) < 1e-13
        assert abs(theta[0]) < 1e-13 and theta[-1] == pytest.approx(1.)
        assert abs(reference.stiffness(load, 100., count)) < 1e-10
        assert reference.stiffness(.9999*load, 100., count) > 0
        assert reference.stiffness(1.0001*load, 100., count) < 0
