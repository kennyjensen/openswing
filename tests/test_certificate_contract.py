"""Independent small-matrix gate, dtype, fallback and ownership regressions.

No aircraft, equilibrium, derivative or physical residual calls. The reference
is a direct small dense SVD or analytic Hermitian spectrum, not the certificate
implementation's norm or outward-bound arithmetic.
"""
import gc
import math
import weakref
from types import SimpleNamespace

import numpy as np
import pytest
from scipy.sparse import csc_matrix, csr_matrix, coo_matrix, dia_matrix, diags
import scipy.sparse.linalg as linalg

from openswing.aero import AnalysisError
from openswing.equilibrium_state import check_tangent_rank
import openswing.sparse_rank as rank

GATE = 1e-10
CONTROL = np.array([[2., 1.], [0., 3.]], dtype=np.float64)


def oracle(dense):
    # NumPy's complex norm uses absolute/conjugated squares. Explicit float64
    # conversion of the reference preserves every entry of our float32/int cases.
    value = np.asarray(dense, dtype=np.complex128 if np.iscomplexobj(dense) else np.float64)
    singular = np.linalg.svd(value / np.maximum(np.linalg.norm(value, axis=0), 1e-30), compute_uv=False)
    return float(singular[-1] / singular[0]) if singular[0] else 0.


def snapshot(matrix):
    # Establish flag caches before the call so evaluating a property is not
    # mistaken for mutation by the function under test.
    flags = tuple(getattr(matrix, name, None) for name in ('has_sorted_indices', 'has_canonical_format'))
    arrays = {name: (id(getattr(matrix, name)), getattr(matrix, name).copy(), getattr(matrix, name).flags.writeable)
              for name in ('data', 'indices', 'indptr') if hasattr(matrix, name)}
    return arrays, flags


def unchanged(matrix, before):
    arrays, flags = before
    for name, (identity, values, writeable) in arrays.items():
        actual = getattr(matrix, name)
        assert id(actual) == identity
        np.testing.assert_array_equal(actual, values)
        assert actual.dtype == values.dtype and actual.flags.writeable == writeable
    assert tuple(getattr(matrix, name, None) for name in ('has_sorted_indices', 'has_canonical_format')) == flags


def conservative(bound, exact):
    assert np.isfinite(bound) and 0 <= bound <= 1
    # Only accommodates the independent tiny SVD oracle's final rounding.
    assert bound <= exact * (1 + 1e-10)
    if bound > GATE:
        assert exact >= GATE


def certificate_metadata(report):
    assert report['rank_check'] == 'sparse inverse-norm certificate'
    assert report['column_scaled_reciprocal_condition'] is None
    lower = report['column_scaled_reciprocal_condition_lower_bound']
    assert np.isfinite(lower) and GATE < lower <= 1


def dense_metadata(report, exact):
    assert report['rank_check'] == 'full-Jacobian SVD'
    assert 'column_scaled_reciprocal_condition_lower_bound' not in report
    actual = report['column_scaled_reciprocal_condition']
    assert np.isfinite(actual) and actual >= GATE
    # Unsupported float32 is deliberately checked with the original SVD path,
    # whose precision need not equal the independent float64 reference.
    assert actual == pytest.approx(exact, rel=5e-7, abs=5e-15)


def test_observed_complex_false_accept_is_rejected_by_original_svd(monkeypatch):
    # Exact binary64 entries frozen in diagnostic-types/matrices.json.
    a, b = 221206.6960055904, 221206.6960033301
    dense = np.array([[a, 1j*b], [-1j*b, a]], dtype=np.complex128)
    matrix = csc_matrix(dense); before = snapshot(matrix)
    exact = oracle(dense)
    assert math.exp(-26) < GATE and exact < GATE
    assert exact == pytest.approx(math.exp(-26), rel=5e-4, abs=0)
    assert rank.column_scaled_inverse_bound(matrix) == 0.
    svd = np.linalg.svd; calls = []
    def observe(*args, **kwargs):
        calls.append(np.asarray(args[0]).copy())
        return svd(*args, **kwargs)
    monkeypatch.setattr(np.linalg, 'svd', observe)
    with pytest.raises(AnalysisError, match='singular'):
        check_tangent_rank(matrix)
    assert len(calls) == 1 and np.iscomplexobj(calls[0])
    unchanged(matrix, before)


@pytest.mark.parametrize('kind', ['complex-csc', 'float32-csc', 'float32-csr',
                                 'int64-csc', 'int64-csr', 'float64-coo', 'float64-dia'])
def test_unsupported_dtype_or_format_declines_without_factorization(kind, monkeypatch):
    values = CONTROL.astype(np.complex128 if kind.startswith('complex') else
                            np.float32 if kind.startswith('float32') else
                            np.int64 if kind.startswith('int64') else np.float64)
    constructor = {'csc': csc_matrix, 'csr': csr_matrix, 'coo': coo_matrix, 'dia': dia_matrix}[kind.split('-')[1]]
    matrix = constructor(values); before = snapshot(matrix)
    def forbidden(*args, **kwargs):
        raise AssertionError('Unsupported certificate input reached sparse factorization')
    monkeypatch.setattr(linalg, 'splu', forbidden)
    assert rank.column_scaled_inverse_bound(matrix) == 0.
    dense_metadata(check_tangent_rank(matrix), oracle(values))
    unchanged(matrix, before)


@pytest.mark.parametrize('kind', ['csc-duplicates', 'csr-duplicates', 'csc-unsorted', 'csr-unsorted'])
def test_noncanonical_input_declines_without_modifying_arrays_or_flags(kind, monkeypatch):
    if kind == 'csc-duplicates':
        matrix = csc_matrix(([1., 1., .25, .75, 1., 2.], [0, 0, 0, 0, 1, 1], [0, 2, 6]), shape=(2, 2))
    elif kind == 'csr-duplicates':
        matrix = csr_matrix(([1., 1., .25, .75, 1., 2.], [0, 0, 1, 1, 1, 1], [0, 4, 6]), shape=(2, 2))
    elif kind == 'csc-unsorted':
        matrix = csc_matrix(([2., 3., 1.], [0, 1, 0], [0, 1, 3]), shape=(2, 2))
    else:
        matrix = csr_matrix(([1., 2., 3.], [1, 0, 1], [0, 2, 3]), shape=(2, 2))
    assert not matrix.has_canonical_format
    before = snapshot(matrix)
    def forbidden(*args, **kwargs):
        raise AssertionError('Noncanonical caller storage reached sparse factorization')
    monkeypatch.setattr(linalg, 'splu', forbidden)
    assert rank.column_scaled_inverse_bound(matrix) == 0.
    unchanged(matrix, before)
    dense_metadata(check_tangent_rank(matrix), oracle(CONTROL))
    unchanged(matrix, before)


@pytest.mark.parametrize('constructor', [csc_matrix, csr_matrix], ids=['csc', 'csr'])
@pytest.mark.parametrize('readonly', [False, True], ids=['writeable', 'readonly'])
def test_canonical_real64_control_certifies_without_densifying_or_mutating(constructor, readonly, monkeypatch):
    matrix = constructor(CONTROL)
    assert matrix.has_canonical_format and matrix.has_sorted_indices
    if readonly:
        for array in (matrix.data, matrix.indices, matrix.indptr):
            array.flags.writeable = False
    before = snapshot(matrix); exact = oracle(CONTROL)
    def forbidden(*args, **kwargs):
        raise AssertionError('Canonical real64 certificate unexpectedly densified or used full SVD')
    monkeypatch.setattr(csc_matrix, 'toarray', forbidden)
    monkeypatch.setattr(csr_matrix, 'toarray', forbidden)
    monkeypatch.setattr(np.linalg, 'svd', forbidden)
    bound = rank.column_scaled_inverse_bound(matrix)
    conservative(bound, exact)
    assert bound > GATE
    certificate_metadata(check_tangent_rank(matrix))
    unchanged(matrix, before)


@pytest.mark.parametrize('size', [2, 5, 9])
@pytest.mark.parametrize('condition', [1., 1e5, 1e10])
def test_random_nonnormal_bound_is_conservative_against_small_svd(size, condition):
    rng = np.random.default_rng(20261024 + size)
    left, _ = np.linalg.qr(rng.normal(size=(size, size)))
    right, _ = np.linalg.qr(rng.normal(size=(size, size)))
    dense = (left * np.geomspace(1., 1./condition, size)) @ right.T
    matrix = csc_matrix(dense); before = snapshot(matrix)
    exact = oracle(dense); bound = rank.column_scaled_inverse_bound(matrix)
    conservative(bound, exact)
    if exact < GATE:
        with pytest.raises(AnalysisError, match='singular'):
            check_tangent_rank(matrix)
    else:
        report = check_tangent_rank(matrix)
        if report['rank_check'] == 'sparse inverse-norm certificate':
            certificate_metadata(report)
        else:
            dense_metadata(report, exact)
    unchanged(matrix, before)


@pytest.mark.parametrize('delta', [0., 1e-12, 1.8e-10, 2.2e-10, 1e-8])
def test_symmetric_analytic_threshold_matches_original_gate(delta):
    off = 1. - delta
    dense = np.array([[1., off], [off, 1.]])
    # Equal column norms: the exact spectrum of this represented real matrix
    # gives reciprocal condition (1-off)/(1+off).
    analytic = (1.-off)/(1.+off)
    exact = oracle(dense)
    assert abs(exact-analytic) < 5e-16
    matrix = csc_matrix(dense)
    bound = rank.column_scaled_inverse_bound(matrix)
    conservative(bound, exact)
    if analytic < GATE:
        with pytest.raises(AnalysisError, match='singular'):
            check_tangent_rank(matrix)
    else:
        report = check_tangent_rank(matrix)
        if report['rank_check'] == 'sparse inverse-norm certificate':
            certificate_metadata(report)
        else:
            dense_metadata(report, exact)


@pytest.mark.parametrize('floor', [1e-25, 1e-32, 1e-35])
def test_original_column_floor_keeps_conservative_gate(floor):
    dense = np.diag([floor, 1e-7, 1e3]); matrix = csc_matrix(dense)
    exact = oracle(dense)
    conservative(rank.column_scaled_inverse_bound(matrix), exact)
    report = check_tangent_rank(matrix)
    if report['rank_check'] == 'sparse inverse-norm certificate':
        certificate_metadata(report)
    else:
        dense_metadata(report, exact)


@pytest.mark.parametrize('diagonal', [[1e308, 1e308], [1e-310, 1e-310], [1e308, 1e-308]],
                         ids=['square-overflow-range', 'subnormal-range', 'mixed-extreme-range'])
def test_unsafe_extreme_range_is_inconclusive_and_nonmutating(diagonal):
    matrix = diags(diagonal).tocsc(); before = snapshot(matrix)
    assert rank.column_scaled_inverse_bound(matrix) == 0.
    unchanged(matrix, before)


@pytest.mark.parametrize('bad', [float('nan'), float('inf')], ids=['nan', 'infinity'])
def test_nonfinite_real_matrix_is_inconclusive(bad):
    matrix = csc_matrix([[1., bad], [0., 2.]])
    before = snapshot(matrix)
    assert rank.column_scaled_inverse_bound(matrix) == 0.
    unchanged(matrix, before)


@pytest.mark.parametrize('bad_inverse', ['zero', 'nan'])
def test_invalid_inverse_cannot_certify_and_original_svd_recovers(bad_inverse, monkeypatch):
    def solve(rhs):
        return np.zeros_like(rhs) if bad_inverse == 'zero' else np.full_like(rhs, np.nan)
    monkeypatch.setattr(linalg, 'splu', lambda *args, **kwargs: SimpleNamespace(solve=solve))
    matrix = csc_matrix(CONTROL); before = snapshot(matrix)
    assert rank.column_scaled_inverse_bound(matrix) == 0.
    dense_metadata(check_tangent_rank(matrix), oracle(CONTROL))
    unchanged(matrix, before)


@pytest.mark.parametrize('where', ['factor', 'solve'])
def test_factor_or_solve_runtime_error_is_inconclusive_with_original_svd_fallback(where, monkeypatch):
    def unavailable(*args, **kwargs):
        raise RuntimeError('injected '+where+' unavailability')
    monkeypatch.setattr(linalg, 'splu', unavailable if where == 'factor' else
                        lambda *args, **kwargs: SimpleNamespace(solve=unavailable))
    matrix = csc_matrix(CONTROL); before = snapshot(matrix)
    assert rank.column_scaled_inverse_bound(matrix) == 0.
    dense_metadata(check_tangent_rank(matrix), oracle(CONTROL))
    unchanged(matrix, before)


@pytest.mark.parametrize('where', ['factor', 'solve'])
@pytest.mark.parametrize('kind', [MemoryError, KeyboardInterrupt], ids=['memory', 'interrupt'])
def test_resource_or_interrupt_propagates_without_full_svd(where, kind, monkeypatch):
    failure = kind('injected '+where+' propagation')
    def unavailable(*args, **kwargs):
        raise failure
    def forbidden(*args, **kwargs):
        raise AssertionError('Resource/interruption failure triggered dense SVD')
    monkeypatch.setattr(linalg, 'splu', unavailable if where == 'factor' else
                        lambda *args, **kwargs: SimpleNamespace(solve=unavailable))
    monkeypatch.setattr(np.linalg, 'svd', forbidden)
    matrix = csc_matrix(CONTROL); before = snapshot(matrix)
    with pytest.raises(kind) as caught:
        check_tangent_rank(matrix)
    assert caught.value is failure
    unchanged(matrix, before)


@pytest.mark.parametrize('outcome', ['success', 'inconclusive'])
def test_certificate_factor_not_retained_after_return(outcome, monkeypatch):
    original = linalg.splu; references = []
    class Observed:
        def __init__(self, factor):
            self.factor = factor
        def solve(self, rhs, *args, **kwargs):
            return np.zeros_like(rhs) if outcome == 'inconclusive' else self.factor.solve(rhs, *args, **kwargs)
        def __getattr__(self, name):
            return getattr(self.factor, name)
    def observe(*args, **kwargs):
        value = Observed(original(*args, **kwargs))
        references.append(weakref.ref(value))
        return value
    monkeypatch.setattr(linalg, 'splu', observe)
    matrix = csc_matrix(CONTROL); before = snapshot(matrix)
    value = rank.column_scaled_inverse_bound(matrix)
    assert value > GATE if outcome == 'success' else value == 0.
    gc.collect()
    assert len(references) == 1 and references[0]() is None
    unchanged(matrix, before)


@pytest.mark.parametrize('bound', [0., GATE, np.nextafter(GATE, np.inf)], ids=['zero', 'threshold', 'just-above'])
def test_rank_api_strict_certificate_boundary_and_json_metadata(bound, monkeypatch):
    import json
    monkeypatch.setattr(rank, 'column_scaled_inverse_bound', lambda *args, **kwargs: bound)
    matrix = csc_matrix(CONTROL); exact = oracle(CONTROL)
    result = check_tangent_rank(matrix)
    if bound > GATE:
        certificate_metadata(result)
    else:
        dense_metadata(result, exact)
    assert json.loads(json.dumps(result, allow_nan=False)) == result
