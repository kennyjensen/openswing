import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from modal_directional_check import actions, projected_correction


def test_complex_pencil_uses_real_states_and_the_published_mass_sign():
    a = np.array([[0., -2.], [2., 0.]])
    m = np.diag([3., 2.])
    v = np.array([1.+2j, -3.+.5j])
    calls = []
    def residual(z, zdot):
        assert not np.iscomplexobj(z) and not np.iscomplexobj(zdot)
        calls.append(True)
        return np.array([7., -5.])+a@z-m@zdot
    av, mv = actions(residual, v, .02)
    np.testing.assert_allclose(av, a@v, atol=2e-13)
    np.testing.assert_allclose(mv, m@v, atol=2e-13)
    assert len(calls) == 8


def test_centered_probe_error_refines_quadratically_without_hiding_wrong_matrix():
    v = np.array([1.])
    def residual(z, zdot):
        return -4*z-2*zdot+3*z*z+5*z*z*z
    errors = []
    for h in [.1, .05, .025]:
        a, m = actions(residual, v, h)
        errors.append(abs(a[0]+4))
        np.testing.assert_allclose(m, [2.], atol=1e-14)
        # An incorrect saved A=-3.8 predicts lambda=-1.9. The exact nonlinear
        # derivative instead predicts -2, independent of this wrong matrix.
        shift = projected_correction([1.], m, a-(-1.9)*m)
        assert shift.real == pytest.approx(-.1+2.5*h*h, abs=2e-14)
    assert errors[1] == pytest.approx(errors[0]/4, abs=2e-14)
    assert errors[2] == pytest.approx(errors[1]/4, abs=2e-14)


def test_left_projection_is_invariant_to_complex_mode_scaling():
    left = np.array([2.-3j, 4.+1j])
    mass = np.array([5.+1j, 2.-1j])
    defect = np.array([.1+.3j, -.2+.1j])
    expected = projected_correction(left, mass, defect)
    scale, adjoint = 2.-4j, -3.+2j
    actual = projected_correction(adjoint*left, scale*mass, scale*defect)
    assert actual == pytest.approx(expected, abs=1e-15)


def test_zero_mass_pairing_cannot_report_a_pole_correction():
    with pytest.raises(ValueError, match='mass pairing'):
        projected_correction([1., 0.], [0., 1.], [1., 1.])
