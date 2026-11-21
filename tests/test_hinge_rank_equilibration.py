"""Saved physical FFWT pencils and explicitly released-axis negative controls."""
from pathlib import Path
import numpy as np
import pytest
from scipy.sparse import csc_matrix
from openswing.structured_static import equilibrate_rank_matrix

EVIDENCE=Path(__file__).resolve().parent/'fixtures'/'hinge-history'/'rank'

@pytest.mark.parametrize('name',['flare10-air-n16','flare30-air-n8','flare30-air-n16','flare20-air-n16'])
def test_hinge_finite_springs_and_explicit_releases_keep_same_rank_gate(name):
 original=np.load(EVIDENCE/(name+'.npz'))['full'];snapshot=original.copy()
 balanced,report=equilibrate_rank_matrix(original);s=np.linalg.svd(balanced,compute_uv=False)
 assert s[-1]>=1e-10*s[0]
 np.testing.assert_array_equal(original,snapshot)
 np.testing.assert_allclose(balanced,np.asarray(report['row_scale'])[:,None]*original*np.asarray(report['column_scale'])[None,:],rtol=3e-14,atol=1e-30)
 released=np.load(EVIDENCE/(name+'-explicit-released-hinges.npz'))['altered_matrix']
 balanced,_=equilibrate_rank_matrix(released);s=np.linalg.svd(balanced,compute_uv=False)
 assert np.sum(s<1e-10*s[0])==2

def test_hinge_equilibration_preserves_sparse_matrix_and_does_not_hide_dependence():
 a=np.array([[1.,1.],[1.,1.+1e-12]])
 for row,column in [(np.ones(2),np.ones(2)),(np.array([.01,100.]),np.array([100.,.01]))]:
  raw=row[:,None]*a*column[None,:];sparse=csc_matrix(raw);before=sparse.copy()
  balanced,_=equilibrate_rank_matrix(sparse);s=np.linalg.svd(balanced.toarray(),compute_uv=False)
  assert s[-1]<1e-10*s[0]
  np.testing.assert_array_equal(sparse.toarray(),before.toarray())
 for a in (np.array([[1.,1.],[0.,0.]]),np.array([[1.,0.],[1.,0.]])):
  balanced,report=equilibrate_rank_matrix(a)
  assert balanced is None and not report['valid']
