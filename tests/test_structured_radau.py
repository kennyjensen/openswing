"""Full descriptor stage algebra and guarded transformed solve checks."""
import numpy as np
import pytest
from scipy.sparse import csc_matrix

from openswing.radau_time import INVERSE
from openswing.structured_static import StructuredMatrix
from openswing.structured_radau import Factorization


def blocks(value, permutation):
    ordered = value[np.ix_(permutation, permutation)]
    return StructuredMatrix(csc_matrix(ordered[:2, :2]), ordered[:2, 2:],
                            csc_matrix(ordered[2:, :2]), ordered[2:, 2:])


@pytest.mark.parametrize('step', [.0005, .03, 2.])
def test_transformed_full_descriptor_solve_matches_original_three_stage_system(step):
    rng = np.random.default_rng(281)
    state = rng.normal(size=(4, 4)) + 4*np.eye(4)
    # A singular rate matrix retains both differential and algebraic rows.
    rate = np.diag([1., 0., 2., 0.])
    permutation = np.array([2, 0, 3, 1])
    factor = Factorization(blocks(state, permutation), blocks(rate, permutation),
                           permutation, INVERSE, step)
    original = np.kron(np.eye(3), state) + np.kron(INVERSE/step, rate)
    for rhs in rng.normal(size=(3, 12)):
        actual = factor.solve(rhs)
        expected = np.linalg.solve(original, rhs)
        np.testing.assert_allclose(actual, expected, rtol=2e-12, atol=2e-12)
        np.testing.assert_allclose(original @ actual, rhs, rtol=2e-12, atol=2e-12)


def test_original_stage_check_rejects_corrupted_reconstruction(monkeypatch):
    state, rate = np.eye(4), np.diag([1., 0., 2., 0.])
    p = np.arange(4)
    factor = Factorization(blocks(state, p), blocks(rate, p), p, INVERSE, .1)
    factor.transform[1, 0] += .1
    with pytest.raises(ValueError, match='original-stage residual'):
        factor.solve(np.arange(12.)+1)


def test_invalid_stage_input_is_rejected():
    p = np.arange(4)
    state, rate = blocks(np.eye(4), p), blocks(np.eye(4), p)
    with pytest.raises(ValueError, match='coordinates'):
        Factorization(state, rate, p, INVERSE, 0.)
    factor = Factorization(state, rate, p, INVERSE, .1)
    with pytest.raises(ValueError, match='right-hand side'):
        factor.solve(np.ones(12, dtype=complex))
