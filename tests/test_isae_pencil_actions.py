"""Physical left/right pencil checks retain complex phase and singular mass."""
import numpy as np
import pytest
from scripts.isae_pencil_actions import pencil_residuals,real_pencil,matrix_norm


def test_nonnormal_singular_mass_matches_complex_definition_without_mutation():
    a=np.array([[2.,7.,-3.],[-4.,1.,5.],[0.,-2.,9.]])
    m=np.array([[1.,2.,0.],[0.,0.,0.],[3.,0.,4.]])
    right=np.array([2.+3j,-1.+2j,4.-1j])
    left=np.array([3.-2j,1.+4j,-2.+1j])
    pole=-.75+2.3j
    saved=[v.copy() for v in (a,m,right,left)]
    for v in (a,m,right,left):v.flags.writeable=False
    rr,lr,pair=pencil_residuals(a,m,pole,right,left)
    np.testing.assert_allclose(rr,a@right-pole*(m@right),rtol=2e-15,atol=2e-14)
    np.testing.assert_allclose(lr,left.conj()@a-pole*(left.conj()@m),rtol=2e-15,atol=2e-14)
    np.testing.assert_allclose(pair,left.conj()@m@right,rtol=2e-15,atol=2e-14)
    for old,new in zip(saved,(a,m,right,left)):np.testing.assert_array_equal(old,new)


def test_exact_complex_mode_preserves_mass_normalization_and_detects_bad_vector():
    a=np.array([[-2.,-5.],[5.,-2.]])
    m=np.eye(2)
    right=np.array([1.,-1j]);left=right/2
    rr,lr,pair=pencil_residuals(a,m,-2.+5j,right,left)
    np.testing.assert_array_equal(rr,[0.,0.]);np.testing.assert_array_equal(lr,[0.,0.])
    assert pair==1
    rr,lr,pair=pencil_residuals(a,m,-2.+5j,right,2*left)
    assert pair==2
    rr,lr,_=pencil_residuals(a,m,-2.+5j,right,np.array([1.,1j]))
    assert np.linalg.norm(lr)>1


def test_complex_matrix_is_not_silently_treated_as_real():
    a=np.array([[1.+1e-20j]])
    with pytest.raises(ValueError,match='real pencil'):
        pencil_residuals(a,np.eye(1),1.,np.ones(1),np.ones(1))


def test_json_pencil_never_requests_a_dense_square_copy(monkeypatch):
    original=np.asarray
    def bounded(value,*args,**kwargs):
        if isinstance(value,list) and value and isinstance(value[0],list):
            raise AssertionError('A whole JSON matrix must not become a dense array')
        return original(value,*args,**kwargs)
    tiny=np.nextafter(0.,1.)
    with monkeypatch.context() as patch:
        patch.setattr(np,'asarray',bounded)
        a,m=real_pencil(dict(A=[[tiny,0.,2.],[0.,3.,0.],[4.,0.,-5.]],M=[[1.,0.,0.],[0.,0.,0.],[0.,0.,2.]]))
    assert a[0,0]==tiny and a.nnz==5 and m.nnz==2
    np.testing.assert_array_equal(a.toarray(),[[tiny,0.,2.],[0.,3.,0.],[4.,0.,-5.]])
    assert matrix_norm(a)==np.linalg.norm(a.toarray())


def test_duplicate_sparse_entries_contribute_to_the_actual_matrix_norm():
    from scipy.sparse import csr_matrix
    source=csr_matrix(([3.,4.,-2.],[0,0,1],[0,2,3]),shape=(2,2))
    a,m=real_pencil(dict(A=source,M=np.eye(2)))
    np.testing.assert_array_equal(a.toarray(),[[7.,0.],[0.,-2.]])
    assert matrix_norm(a)==matrix_norm(source)==np.sqrt(53.)
    assert source.nnz==3


def test_sparse_actions_and_real_pole_certificates_match_dense():
    from scripts.isae_modal_classification import classify_modes
    a=np.array([[-23.,7.],[0.,-37.]]);m=np.eye(2)
    right=np.array([1.,0.])*np.exp(.4j);left=np.array([1.,.5])*np.exp(-.7j)
    sa,sm=real_pencil(dict(A=a.tolist(),M=m.tolist()))
    for actual,expected in zip(pencil_residuals(sa,sm,-23.,right,left),pencil_residuals(a,m,-23.,right,left)):
        np.testing.assert_allclose(actual,expected,atol=1e-14,rtol=1e-14)
    split=lambda v:dict(real=v.real.tolist(),imag=v.imag.tolist())
    modes=[dict(eigenvalue=[-23.,1e-12],right=split(right),left=split(left))]
    dense=classify_modes(modes,a,m,shift=[0.,200.],characteristic_rate=1.)
    sparse=classify_modes(modes,sa,sm,shift=[0.,200.],characteristic_rate=1.)
    assert dense[0]['classification']==sparse[0]['classification']=='certified_real'


@pytest.mark.parametrize('bad',[[[1.,2.]],[[float('nan')]],[[1.+1j]]])
def test_invalid_json_pencil_is_rejected(bad):
    with pytest.raises(ValueError,match='pencil matrices'):
        real_pencil(dict(A=bad,M=[[1.]]))
