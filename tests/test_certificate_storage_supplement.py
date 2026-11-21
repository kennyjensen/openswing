"""Independent supplement: forged sparse flags/storage and invalid inverse API.

Malformed sparse structures are passed ONLY to the certificate helper's input
guard. They are never densified, factored, multiplied, or passed to rank/SVD.
The frozen original 51-case suite is unchanged.
"""
from copy import deepcopy
from types import SimpleNamespace
import warnings

import numpy as np
import pytest
from scipy.sparse import csc_matrix, csr_matrix
import scipy.sparse.linalg as linalg

from openswing.equilibrium_state import check_tangent_rank
import openswing.sparse_rank as rank


def storage(matrix):
    return dict(shape=matrix.shape,
                arrays={name: (id(getattr(matrix, name)), getattr(matrix, name).copy(), getattr(matrix, name).flags.writeable)
                        for name in ('data', 'indices', 'indptr')},
                caches={name: matrix.__dict__.get(name, '<absent>')
                        for name in ('_has_sorted_indices', '_has_canonical_format')})


def unchanged(matrix, before):
    assert matrix.shape == before['shape']
    for name, (identity, values, writeable) in before['arrays'].items():
        value = getattr(matrix, name)
        assert id(value) == identity and value.dtype == values.dtype
        assert value.flags.writeable == writeable
        np.testing.assert_array_equal(value, values)
    assert {name: matrix.__dict__.get(name, '<absent>') for name in before['caches']} == before['caches']


def forbid_unsafe_work(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('Invalid compressed storage reached numerical work or dense conversion')
    for cls in (csc_matrix, csr_matrix):
        for name in ('toarray', 'power', 'tocsc', 'tocsr'):
            monkeypatch.setattr(cls, name, forbidden)
    monkeypatch.setattr(linalg, 'splu', forbidden)
    monkeypatch.setattr(np.linalg, 'svd', forbidden)
    monkeypatch.setattr(rank, 'structural_rank', forbidden)


@pytest.mark.parametrize('constructor', [csc_matrix, csr_matrix], ids=['csc', 'csr'])
@pytest.mark.parametrize('defect', ['duplicate', 'unsorted'])
def test_forged_true_canonical_flags_do_not_authorize_bad_segments(constructor, defect, monkeypatch):
    # Both 2x2 compressed formats accept these literal buffers without requiring
    # arithmetic. Forge the same cached flags a later caller mutation can leave.
    if defect == 'duplicate':
        matrix = constructor(([1., 1., 3.], [0, 0, 1], [0, 2, 3]), shape=(2, 2))
    else:
        matrix = constructor(([1., 2., 3.], [1, 0, 1], [0, 2, 3]), shape=(2, 2))
    matrix._has_sorted_indices = True
    matrix._has_canonical_format = True
    before = storage(matrix); events = []
    forbid_unsafe_work(monkeypatch)
    assert rank.column_scaled_inverse_bound(matrix, progress=lambda *args: events.append(args)) == 0.
    assert events == []
    unchanged(matrix, before)


@pytest.mark.parametrize('constructor', [csc_matrix, csr_matrix], ids=['csc', 'csr'])
@pytest.mark.parametrize('defect', [
    'negative-index', 'out-of-bounds-index', 'nonzero-pointer-start', 'wrong-pointer-end',
    'nonmonotone-pointers', 'wrong-pointer-length', 'wrong-index-length',
    'noninteger-pointers', 'noninteger-indices',
])
def test_invalid_compressed_structure_declines_before_any_sparse_arithmetic(constructor, defect, monkeypatch):
    # Build a valid 3x3 object first, then install malformed public buffers.
    # No SciPy constructor or dense operation is invoked after the mutation.
    matrix = constructor(([2., 3., 4.], [0, 1, 2], [0, 1, 2, 3]), shape=(3, 3))
    if defect == 'negative-index':
        matrix.indices[1] = -1
    elif defect == 'out-of-bounds-index':
        matrix.indices[1] = 3
    elif defect == 'nonzero-pointer-start':
        matrix.indptr[0] = 1
    elif defect == 'wrong-pointer-end':
        matrix.indptr[-1] = 2
    elif defect == 'nonmonotone-pointers':
        matrix.indptr[:] = [0, 2, 1, 3]
    elif defect == 'wrong-pointer-length':
        matrix.indptr = np.array([0, 1, 3], dtype=matrix.indptr.dtype)
    elif defect == 'wrong-index-length':
        matrix.indices = matrix.indices[:2].copy()
    elif defect == 'noninteger-pointers':
        matrix.indptr = matrix.indptr.astype(np.float64)
    else:
        matrix.indices = matrix.indices.astype(np.float64)
    matrix._has_sorted_indices = True
    matrix._has_canonical_format = True
    before = storage(matrix); events = []
    forbid_unsafe_work(monkeypatch)
    assert rank.column_scaled_inverse_bound(matrix, progress=lambda *args: events.append(args)) == 0.
    assert events == []
    unchanged(matrix, before)


@pytest.mark.parametrize('kind', [
    'flat-vector', 'one-row', 'one-column', 'rank-three', 'python-list',
    'complex-array', 'float32-array', 'scalar', 'object-array',
])
def test_invalid_inverse_shape_container_or_dtype_is_inconclusive(kind, monkeypatch):
    dense = np.array([[2., 1.], [0., 3.]], dtype=np.float64)
    matrix = csc_matrix(dense); before = storage(matrix)
    # Independent small-SVD oracle, evaluated only on this valid dense control.
    singular = np.linalg.svd(dense / np.linalg.norm(dense, axis=0), compute_uv=False)
    exact = float(singular[-1] / singular[0])
    values = {
        'flat-vector': np.zeros(2),
        'one-row': np.zeros((1, 2)),
        'one-column': np.zeros((2, 1)),
        'rank-three': np.zeros((2, 2, 1)),
        'python-list': [[0., 0.], [0., 0.]],
        'complex-array': np.zeros((2, 2), dtype=np.complex128),
        'float32-array': np.zeros((2, 2), dtype=np.float32),
        'scalar': 0.,
        'object-array': np.zeros((2, 2), dtype=object),
    }
    invalid = values[kind]; original = deepcopy(invalid); calls = []
    def solve(rhs):
        calls.append((rhs.shape, rhs.dtype))
        return invalid
    monkeypatch.setattr(linalg, 'splu', lambda *args, **kwargs: SimpleNamespace(solve=solve))
    with warnings.catch_warnings(record=True) as recorded:
        warnings.simplefilter('always')
        assert rank.column_scaled_inverse_bound(matrix) == 0.
        report = check_tangent_rank(matrix)
    assert not recorded
    assert calls == [((2, 2), np.dtype(np.float64))] * 2
    assert report['rank_check'] == 'full-Jacobian SVD'
    assert 'column_scaled_reciprocal_condition_lower_bound' not in report
    assert report['column_scaled_reciprocal_condition'] >= 1e-10
    assert report['column_scaled_reciprocal_condition'] == pytest.approx(exact, rel=1e-13, abs=0)
    if isinstance(invalid, np.ndarray):
        assert invalid.dtype == original.dtype and invalid.shape == original.shape
        np.testing.assert_array_equal(invalid, original)
    else:
        assert invalid == original
    unchanged(matrix, before)
