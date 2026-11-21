"""Rank certification using existing physical blocks, including released hinges."""
from pathlib import Path

import numpy as np
import pytest
from scipy.sparse import csc_matrix, eye
from openswing.structured_static import mechanical_svd_certificate, equilibrate_rank_matrix


@pytest.mark.parametrize('small',[0.,5e-11,1e-10,2e-10])
def test_unchanged_singular_value_threshold(small):
    matrix=csc_matrix(np.diag([1.,.2,small]))
    before=matrix.copy()
    report=mechanical_svd_certificate(matrix)
    assert report['certified'] is (small>=1e-10)
    assert report['threshold']==1e-10
    np.testing.assert_array_equal(matrix.toarray(),before.toarray())


def test_nonfinite_oversized_and_failed_svd_cannot_certify(monkeypatch):
    assert not mechanical_svd_certificate(csc_matrix([[np.nan]]))['certified']
    assert not mechanical_svd_certificate(csc_matrix([[np.inf]]))['certified']
    large=eye(5,format='csc')
    def forbidden():pytest.fail('Oversized block must not be densified')
    monkeypatch.setattr(large,'toarray',forbidden)
    assert not mechanical_svd_certificate(large,max_size=4)['certified']
    def failed(*args,**kwargs):raise np.linalg.LinAlgError('deliberate')
    monkeypatch.setattr(np.linalg,'svd',failed)
    assert not mechanical_svd_certificate(eye(2,format='csc'))['certified']


@pytest.mark.parametrize('name',['flare10-air-n16','flare30-air-n8','flare30-air-n16','flare20-air-n16'])
def test_saved_physical_matrices_pass_but_explicit_released_axes_do_not(name):
    root=Path(__file__).parent/'fixtures/hinge-history/rank'
    original=np.load(root/(name+'.npz'))
    mechanical=original['mechanical'];size=len(mechanical)
    released=np.load(root/(name+'-explicit-released-hinges.npz'))['altered_matrix'][:size,:size]
    for values,expected in [(mechanical,True),(released,False)]:
        balanced,_=equilibrate_rank_matrix(csc_matrix(values))
        assert balanced is not None
        report=mechanical_svd_certificate(balanced)
        assert report['certified'] is expected
        # Compare with the independent saved full physical system at the same gate.
        full=original['full'] if expected else np.load(root/(name+'-explicit-released-hinges.npz'))['altered_matrix']
        full_balanced,_=equilibrate_rank_matrix(full)
        singular=np.linalg.svd(full_balanced,compute_uv=False)
        assert bool(singular[-1]>=1e-10*singular[0]) is expected
