"""Physical roots and continuation safeguards with the LU corrector."""
import numpy as np
import pytest
import openswing.circulation_solve as solver


def test_analytic_corrector_crosses_two_folds_without_changing_endpoint():
    residual = lambda x: (3-x)*(x*x-x+.5)
    derivative = lambda x: np.diag(-3*x*x+8*x-3.5)
    answer, report = solver.continue_circulation(residual, np.eye(1), derivative=derivative)
    assert answer[0] == pytest.approx(3., abs=1e-10)
    assert report['correctors']['newton'] > 0
    assert any(b['parameter'] < a['parameter'] for a,b in zip(report['trace'],report['trace'][1:]))
    assert report['final_regularization'] == 0
    assert abs(residual(answer)[0]) < 1e-11


def test_analytic_corrector_cannot_accept_a_fold_without_a_physical_root():
    with pytest.raises(solver.CirculationContinuationError, match='no full physical solution'):
        solver.continue_circulation(lambda x: x*x+1, np.eye(1),
                                   derivative=lambda x: np.diag(2*x))


def test_failed_lu_correction_retries_original_hybrid_from_prediction(monkeypatch):
    def unresolved(*args, **kwargs):
        raise np.linalg.LinAlgError('Deliberately unresolved Newton factorization')
    monkeypatch.setattr(solver, 'solve', unresolved)
    residual = lambda x: np.array([2-np.sinh(x[0]), 3-x[1]**3])
    derivative = lambda x: np.diag([-np.cosh(x[0]), -3*x[1]**2])
    answer, report = solver.continue_circulation(residual, np.diag([2.,.7]), derivative=derivative)
    np.testing.assert_allclose(answer, [np.arcsinh(2), np.cbrt(3)], rtol=0, atol=2e-10)
    assert report['correctors']['newton'] == 0
    assert report['correctors']['hybrid'] > 0
    assert report['physical_residual'] < 1e-11


def test_newton_and_hybrid_follow_same_three_root_branch(monkeypatch):
    residual = lambda x: -(x-1)*(x-2)*(x-3)
    derivative = lambda x: np.diag(-3*x*x+12*x-11)
    newton, report = solver.continue_circulation(residual, np.eye(1), derivative=derivative)
    assert report['correctors']['newton'] > 0
    monkeypatch.setattr(solver, '_newton_corrector', lambda *args: None)
    hybrid, _ = solver.continue_circulation(residual, np.eye(1), derivative=derivative)
    np.testing.assert_allclose(newton, [1.], rtol=0, atol=1e-10)
    np.testing.assert_allclose(newton, hybrid, rtol=0, atol=1e-10)
