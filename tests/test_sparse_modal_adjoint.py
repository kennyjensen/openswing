"""Sparse left-vector recovery must preserve constrained transfer residues."""
import numpy as np
import pytest
from scipy.linalg import block_diag
import openswing.linear_dynamics as dynamics


def constrained_oscillators(repeated=False):
    matrices=[];masses=[]
    for j in range(13):
        k=1 if repeated else j+1
        matrices.append(np.array([[0,0,1,0,0],[0,0,0,1,0],
            [-18*k,7*k,-.4,0,1],[7*k,-24*k,0,-.8,-1],[1,-1,0,0,0]],float))
        masses.append(np.diag([1.,1.,2.,3.,0.]))
    return block_diag(*matrices),block_diag(*masses)


@pytest.mark.parametrize('time_scale',[.1,1.,10.])
def test_sparse_adjoint_keeps_reactions_and_independent_oscillator_transfers(time_scale):
    a,m=constrained_oscillators();m=m/time_scale
    modes,report=dynamics.eigensystem(a,m,time_scale=time_scale,count=100)
    assert report['finite_dimension']==26
    counts=report['left_recovery_counts']
    assert counts['sparse_adjoint']==counts['conjugate_reuse']==13
    assert counts['schur_pencils']==counts['sparse_rejected']==0
    for mode in modes:
        value=complex(*mode['eigenvalue']);v,w=mode['right'],mode['left']
        np.testing.assert_allclose(a@v,value*(m@v),atol=2e-10)
        np.testing.assert_allclose(w.conj()@a,value*(w.conj()@m),atol=2e-10)
        assert np.vdot(w,m@v)==pytest.approx(1,abs=2e-11)
    # Combine both masses analytically: 5q''+1.2q'+28(j+1)q=u.
    # A force on only mass1 also excites the original algebraic reaction.
    # Correct frequencies alone would not establish these transfer residues.
    for j in [0,6,12]:
        b=np.zeros(len(a));b[5*j+2]=1.
        for physical_s in [.3+2j,.1+5j,3j]:
            s=physical_s*time_scale
            actual=sum(mode['right'][5*j]*np.vdot(mode['left'],b)/(s-complex(*mode['eigenvalue'])) for mode in modes)
            exact=1/(5*physical_s**2+1.2*physical_s+28*(j+1))
            assert actual==pytest.approx(exact,rel=2e-10,abs=2e-12)


@pytest.mark.parametrize('count',[2,100])
def test_repeated_poles_use_complete_spectrum_to_preserve_schur_fallback(count):
    a,m=constrained_oscillators(repeated=True)
    modes,report=dynamics.eigensystem(a,m,count=count)
    assert report['finite_dimension']==26
    counts=report['left_recovery_counts']
    assert counts['sparse_adjoint']==counts['conjugate_reuse']==0
    assert counts['schur_pencils']==1
    for mode in modes:
        value=complex(*mode['eigenvalue'])
        assert min(abs(value-np.roots([5.,1.2,28.])))<2e-10
        assert max(mode['left_backward_error'],mode['right_backward_error'])<1e-11


def test_rejected_sparse_recovery_retains_original_schur_solution(monkeypatch):
    a,m=constrained_oscillators()
    expected,_=dynamics.eigensystem(a,m,count=4)
    monkeypatch.setattr(dynamics,'_sparse_adjoint',lambda *args:None)
    actual,report=dynamics.eigensystem(a,m,count=4)
    assert report['left_recovery_counts']['sparse_rejected']==4
    assert report['left_recovery_counts']['schur_pencils']==1
    for before in expected:
        value=complex(*before['eigenvalue']);after=min(actual,key=lambda r:abs(complex(*r['eigenvalue'])-value))
        np.testing.assert_allclose(after['left'],before['left'],rtol=2e-10,atol=2e-10)


def test_weak_biorthogonal_pairing_rejects_ill_conditioned_border():
    a=-np.diag(np.r_[1.,2.,3.,np.arange(10.,72.)]);a[0,1]=a[1,2]=1e9;m=np.eye(len(a))
    modes,report=dynamics.eigensystem(a,m,count=2,rank_tolerance=1e-12)
    assert report['left_recovery_counts']['sparse_rejected']==2
    assert report['left_recovery_counts']['schur_pencils']==1
    np.testing.assert_allclose(sorted(complex(*r['eigenvalue']).real for r in modes),[-2.,-1.],atol=1e-10)
    assert max(r['left_backward_error'] for r in modes)<1e-10


def test_exact_integrators_need_no_additional_generalized_eigensolve():
    modes,report=dynamics.eigensystem(np.zeros((64,64)),np.eye(64),count=8)
    assert report['left_recovery_counts']['exact_kernel']==8
    assert report['left_recovery_counts']['schur_pencils']==0
    assert all(r['exact_integrator'] and r['eigenvalue']==[0.,0.] for r in modes)
