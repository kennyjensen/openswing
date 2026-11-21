"""Additive cache-ownership cases; previous frozen 51+31 files stay unchanged."""
import numpy as np
import pytest
from scipy.sparse import csc_matrix, csr_matrix
from openswing.sparse_rank import column_scaled_inverse_bound


@pytest.mark.parametrize('constructor', [csc_matrix, csr_matrix], ids=['csc', 'csr'])
@pytest.mark.parametrize('cache', ['stale-false', 'absent'])
def test_valid_storage_does_not_refresh_caller_canonical_flag_caches(constructor, cache):
    matrix = constructor(np.array([[2., 1.], [0., 3.]], dtype=np.float64))
    names = ('_has_sorted_indices', '_has_canonical_format')
    for name in names:
        if cache == 'stale-false':
            setattr(matrix, name, False)
        else:
            matrix.__dict__.pop(name, None)
    before_flags = {name: matrix.__dict__.get(name, '<absent>') for name in names}
    before = {name: (id(getattr(matrix, name)), getattr(matrix, name).copy())
              for name in ('data', 'indices', 'indptr')}
    bound = column_scaled_inverse_bound(matrix)
    assert np.isfinite(bound) and 1e-10 < bound <= 1.
    assert {name: matrix.__dict__.get(name, '<absent>') for name in names} == before_flags
    for name, (identity, value) in before.items():
        assert id(getattr(matrix, name)) == identity
        np.testing.assert_array_equal(getattr(matrix, name), value)
