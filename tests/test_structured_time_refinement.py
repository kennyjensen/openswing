"""A small constrained motion must survive large-load Schur back substitution."""
import numpy as np
import pytest
from scipy.sparse import csc_matrix

from openswing.structured_static import StructuredMatrix
from openswing.structured_time import Factorization


@pytest.mark.parametrize('load,motion', [(1e16, 1.), (-1e16, 1e-8), (1e20, -1e-5)])
@pytest.mark.parametrize('permutation', [np.arange(3), np.array([2, 0, 1])])
def test_small_constrained_motion_survives_back_substitution(load,motion,permutation):
    # x0 + y = load; x1 - 2*y = -2*load; x0 = motion.
    # In floating arithmetic y rounds to load. The exactly representable
    # local motions remain x0=motion and x1=-2*motion, even though subtracting
    # the two large terms in ordinary Schur back substitution gives zero.
    matrix=StructuredMatrix(csc_matrix(np.eye(2)),np.array([[1.],[-2.]]),
        csc_matrix([[1.,0.]]),np.zeros((1,1)))
    rhs=np.empty(3);rhs[permutation]=[load,-2*load,motion]
    factors=Factorization(matrix,permutation)
    answer=factors.solve(rhs)[permutation]
    np.testing.assert_allclose(answer[:2],[motion,-2*motion],rtol=2e-15,atol=0)
    np.testing.assert_array_equal(matrix.toarray()@answer,rhs[permutation])
    # Reuse the same factors at a different load and motion scale.
    next_rhs=rhs*.25
    np.testing.assert_allclose(factors.solve(next_rhs)[permutation][:2],
        np.array([motion,-2*motion])*.25,rtol=2e-15,atol=0)
