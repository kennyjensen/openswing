"""Conservative warm-state rank checks never bypass the original SVD gate."""
import numpy as np
import pytest
from scipy.sparse import csc_matrix,diags
from openswing.aero import AnalysisError
from openswing.sparse_rank import column_scaled_inverse_bound
from openswing.equilibrium_state import check_tangent_rank


def reciprocal(matrix):
    a=matrix.toarray()
    singular=np.linalg.svd(a/np.maximum(np.linalg.norm(a,axis=0),1e-30),compute_uv=False)
    return float(singular[-1]/singular[0])


def test_large_sparse_check_avoids_dense_conversion_and_svd(monkeypatch):
    matrix=diags(np.geomspace(1e-25,1e25,301)).tocsc()
    def forbidden(*args,**kwargs):raise AssertionError('Sparse certificate densified the matrix')
    monkeypatch.setattr(csc_matrix,'toarray',forbidden)
    monkeypatch.setattr(np.linalg,'svd',forbidden)
    events=[]
    report=check_tangent_rank(matrix,lambda *args:events.append(args))
    assert report['rank_check']=='sparse inverse-norm certificate'
    assert report['column_scaled_reciprocal_condition'] is None
    assert 1e-10 < report['column_scaled_reciprocal_condition_lower_bound'] <= 1
    assert events[0]==('equilibrium_rank',0,301)
    assert events[-1]==('equilibrium_rank',301,301)


@pytest.mark.parametrize('floor',[1e-25,1e-32,1e-35])
def test_certificate_respects_original_column_norm_floor(floor):
    matrix=diags([floor,1e-7,1e3]).tocsc()
    bound=column_scaled_inverse_bound(matrix)
    assert 0 < bound <= reciprocal(matrix)*(1+1e-14)


@pytest.mark.parametrize('delta',[0.,1e-13,1.8e-10,2.2e-10,1e-9])
def test_singular_and_threshold_cases_match_full_svd(delta):
    matrix=csc_matrix([[1.,1.,0.],[0.,delta,0.],[0.,0.,1.]])
    exact=reciprocal(matrix)
    bound=column_scaled_inverse_bound(matrix)
    assert 0 <= bound <= exact*(1+1e-14)
    if exact < 1e-10:
        with pytest.raises(AnalysisError,match='singular'):check_tangent_rank(matrix)
    else:
        result=check_tangent_rank(matrix)
        if delta==2.2e-10:
            assert result['rank_check']=='full-Jacobian SVD'
            assert result['column_scaled_reciprocal_condition']==exact


def test_dense_and_inconclusive_sparse_paths_keep_exact_svd_diagnostic(monkeypatch):
    import openswing.sparse_rank as rank
    matrix=csc_matrix([[2.,1.],[0.,3.]])
    monkeypatch.setattr(rank,'column_scaled_inverse_bound',lambda *args,**kwargs:0.)
    events=[]
    for value in [matrix,matrix.toarray()]:
        result=check_tangent_rank(value,lambda *args:events.append(args))
        assert result['rank_check']=='full-Jacobian SVD'
        assert result['column_scaled_reciprocal_condition']==reciprocal(matrix)
        assert 'column_scaled_reciprocal_condition_lower_bound' not in result
    assert events==[('equilibrium_rank_svd',0,2)]*2


def test_inverse_residual_prevents_a_false_certificate(monkeypatch):
    from types import SimpleNamespace
    import scipy.sparse.linalg as linalg
    # A failed inverse must not certify the matrix, even when LU returns it.
    monkeypatch.setattr(linalg,'splu',lambda matrix:SimpleNamespace(solve=lambda rhs:np.zeros_like(rhs)))
    matrix=csc_matrix([[2.,1.],[0.,3.]])
    assert column_scaled_inverse_bound(matrix)==0.
    assert check_tangent_rank(matrix)['rank_check']=='full-Jacobian SVD'


def test_general_nonnormal_matrices_have_conservative_bounds():
    rng=np.random.default_rng(719)
    for size in [2,9,17]:
        for condition in [1.,1e5,1e11]:
            left,_=np.linalg.qr(rng.normal(size=(size,size)))
            right,_=np.linalg.qr(rng.normal(size=(size,size)))
            matrix=csc_matrix((left*np.geomspace(1.,1/condition,size))@right.T)
            bound=column_scaled_inverse_bound(matrix)
            assert 0 <= bound <= reciprocal(matrix)*(1+1e-10)


def test_zero_matrix_and_nonfinite_data_cannot_be_certified():
    assert column_scaled_inverse_bound(csc_matrix((3,3)))==0.
    assert column_scaled_inverse_bound(csc_matrix([[1.,float('nan')],[0.,1.]]))==0.
    with pytest.raises(AnalysisError,match='singular'):check_tangent_rank(csc_matrix((3,3)))
