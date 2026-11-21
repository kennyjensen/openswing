"""Rank normalization must preserve physical matrices and released mechanisms."""
from pathlib import Path
import numpy as np
import pytest
from scipy.sparse import csc_matrix,eye,load_npz,diags
from openswing.structured_static import (equilibrate_rank_matrix,
    mechanical_svd_certificate,refine_mechanical_rank_certificate)

FIXTURES=Path(__file__).parent/'fixtures/hinge-history/rank'


@pytest.mark.parametrize('name',['flare10-air-n16','flare30-air-n8','flare30-air-n16','flare20-air-n16'])
@pytest.mark.parametrize('released',[False,True])
def test_additional_scaling_preserves_physical_hinge_rank(name,released):
    original=np.load(FIXTURES/(name+'.npz'))['mechanical'];size=len(original)
    if released:
        original=np.load(FIXTURES/(name+'-explicit-released-hinges.npz'))['altered_matrix'][:size,:size]
    raw=csc_matrix(original);before=raw.copy()
    balanced,scaling=equilibrate_rank_matrix(raw)
    svd,refined=refine_mechanical_rank_certificate(balanced,scaling)
    assert svd['certified'] is not released and svd['threshold']==1e-10
    assert refined['iterations']<=300
    np.testing.assert_array_equal(raw.toarray(),before.toarray())
    # Reconstruct the advertised transform of the original physical matrix.
    transformed=diags(refined['row_scale'])@raw@diags(refined['column_scale'])
    independent=np.linalg.svd(transformed.toarray(),compute_uv=False)
    assert bool(independent[-1]>=1e-10*independent[0]) is not released
    np.testing.assert_allclose(svd['singular_ratio'],independent[-1]/independent[0],rtol=2e-4,atol=2e-15)


def test_actual_211_node_source_block_passes_without_physics_rebuild():
    raw=load_npz(FIXTURES/'flare20-pm2-211-mechanical.npz');before=raw.copy()
    balanced,scaling=equilibrate_rank_matrix(raw)
    old=mechanical_svd_certificate(balanced)
    assert not old['certified'] and old['reason']=='mechanical block exceeds bounded SVD scope'
    result,updated=refine_mechanical_rank_certificate(balanced,scaling)
    assert result['certified'] and result['singular_ratio']>=1e-10
    assert result['dense_input_bytes']<=64*1024**2
    assert updated['iterations']<=300
    # The norm target is not itself authority to certify rank.
    assert not updated['refinement']['norm_converged']
    assert (raw-before).nnz==0


def test_near_dependence_stays_below_unchanged_gate():
    raw=csc_matrix([[1.,1.],[1.,1.+1e-12]])
    balanced,scaling=equilibrate_rank_matrix(raw)
    result,_=refine_mechanical_rank_certificate(balanced,scaling)
    assert not result['certified'] and result['singular_ratio']<1e-10


def test_dense_budget_rejects_before_any_conversion(monkeypatch):
    raw=eye(5,format='csc');balanced,scaling=equilibrate_rank_matrix(raw)
    def forbidden(*args,**kwargs):pytest.fail('Oversized refined block was densified')
    monkeypatch.setattr(balanced,'toarray',forbidden)
    report,_=refine_mechanical_rank_certificate(balanced,scaling,max_dense_bytes=199)
    assert not report['certified'] and report['dense_input_bytes']==200


@pytest.mark.parametrize('scale',[0.,float('inf'),float('nan')])
def test_noninvertible_accumulated_scales_do_not_certify(scale):
    balanced,scaling=equilibrate_rank_matrix(eye(2,format='csc'))
    scaling['row_scale'][0]=scale
    result,_=refine_mechanical_rank_certificate(balanced,scaling)
    assert not result['certified']
