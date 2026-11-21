"""Exact determinant factors, weak poles and physical rigid-body zero modes."""
import json
from pathlib import Path
import numpy as np
import pytest
from scipy.linalg import block_diag
from openswing.linear_dynamics import eigensystem,IntegratorDeflation,integrator_kernel
from openswing.reduced_model import real_projection


def roots(modes):return np.array([complex(*m['eigenvalue']) for m in modes])


@pytest.mark.parametrize('time',[1.,60.,.001])
def test_exact_jordan_chain_and_weak_poles_survive_scaling_and_independent_permutations(time):
    # Chain xdot=2v, vdot=-3a, adot=0; oscillator -1±2i;
    # genuinely nonzero slow growth, plus an algebraic variable q=0.
    a=block_diag(np.array([[0,2,0],[0,0,-3],[0,0,0.]]),np.array([[-1,-2],[2,-1.]]),[[1e-10]],[[1.]])
    m=np.diag([1.,1.,1.,1.,1.,1.,0.])
    rp=[4,2,6,0,5,1,3];cp=[1,6,3,5,0,2,4]
    row=np.array([1e-4,7.,1e3,.3,90.,.02,2.]);column=np.array([3,.1,8,.03,2,7,.4])
    aa=(row[:,None]*a*column)[np.ix_(rp,cp)];mm=(row[:,None]*m*column)[np.ix_(rp,cp)]/time
    modes,meta=eigensystem(aa,mm,time_scale=time,count=10)
    values=roots(modes)/time
    assert meta['finite_dimension']==6 and meta['integrator_deflation']['count']==3
    assert sum(v==0 for v in values)==3
    for expected in [-1+2j,-1-2j,1e-10]:assert min(abs(values-expected))<1e-12*max(abs(expected),1e-10)
    slow=min(modes,key=lambda mode:abs(complex(*mode['eigenvalue'])/time-1e-10))
    assert not slow['exact_integrator']
    for mode in modes:
        lam=complex(*mode['eigenvalue']);v,w=mode['right'],mode['left']
        np.testing.assert_allclose(aa@v,lam*mm@v,atol=2e-9)
        assert mode['right_backward_error']<1e-10 and mode['left_backward_error']<1e-10


def test_zero_kernel_does_not_discard_small_nonzero_pivots():
    # Rank tolerances would wrongly mix the weak mode into the exact kernel.
    a=np.diag([0.,1e-200,1.]);basis=integrator_kernel(a)
    assert basis.shape==(3,1)
    np.testing.assert_array_equal(a@basis,0)
    assert basis[0,0]!=0 and basis[1,0]==0


def test_dense_nilpotent_similarity_is_not_snapped_by_a_numerical_threshold():
    a=np.array([[2.,1.],[-4.,-2.]])
    reduction=IntegratorDeflation(a,np.eye(2))
    assert not reduction.operations
    np.testing.assert_array_equal(reduction.a,a)
    modes,metadata=eigensystem(a,np.eye(2),count=2)
    assert all(not mode['exact_integrator'] for mode in modes)
    assert metadata['integrator_deflation']['original_A_nullity_estimate'] is None


def test_row_deflation_recovers_coupled_nonzero_right_vectors():
    a=np.array([[-2.,7.,1.],[0.,0.,0.],[0.,0.,-3.]])
    m=np.array([[1.,.4,0.],[0.,2.,0.],[0.,-.2,1.]])
    reduced=IntegratorDeflation(a,m)
    assert len(reduced.operations)==1 and reduced.operations[0]['side']=='row'
    modes,meta=eigensystem(a,m,count=3)
    np.testing.assert_allclose(sorted(roots(modes).real),[-3,-2,0],atol=1e-14)
    for mode in modes:
        lam=complex(*mode['eigenvalue'])
        np.testing.assert_allclose(a@mode['right'],lam*m@mode['right'],atol=2e-14)
        np.testing.assert_allclose(mode['left'].conj()@a,lam*mode['left'].conj()@m,atol=2e-14)


def test_semisimple_integrators_keep_independent_vectors_and_rom_coordinates():
    a=np.zeros((3,3));m=np.diag([2.,3.,4.])
    modes,meta=eigensystem(a,m,count=3)
    assert meta['integrator_deflation']['count']==3
    assert meta['finite_mass_reciprocal_condition'] is None
    assert all(mode['exact_integrator'] and mode['biorthogonal_normalized'] for mode in modes)
    assert all(mode['right_backward_error']==mode['left_backward_error']==0 for mode in modes)
    ar,lift,dual,report=real_projection(a,m,modes)
    np.testing.assert_allclose(ar,0,atol=0)
    np.testing.assert_allclose(dual@m@lift,np.eye(3),atol=1e-14)


def test_defective_integrators_are_not_an_independent_eigenvector_rom_basis():
    modes,meta=eigensystem(np.array([[0,1.],[0,0.]]),np.eye(2),count=2)
    assert all(mode['exact_integrator'] for mode in modes)
    assert meta['integrator_deflation']['original_A_nullity_estimate']==1
    with pytest.raises(ValueError,match='pairing|defective'):real_projection(np.array([[0,1.],[0,0.]]),np.eye(2),modes)


def test_deflation_does_not_hide_an_underdetermined_algebraic_coordinate():
    with pytest.raises(ValueError,match='underdetermined'):eigensystem(np.zeros((2,2)),np.diag([1.,0.]))


def test_shift_invert_selects_exact_integrators_and_nearby_dynamic_roots():
    a=block_diag(np.array([[0,1.],[0,0.]]),-np.diag(np.arange(1.,9.)));m=np.eye(10)
    for shift,expected in [((0.,0.),[0.,0.]),((-3.4,0.),[-3.,-4.])]:
        modes,meta=eigensystem(a,m,count=2,shift=shift,method='shift_invert')
        assert meta['method']=='shift_invert'
        np.testing.assert_allclose(sorted(roots(modes).real),sorted(expected),atol=1e-11)


@pytest.mark.parametrize('name,count,expected',[
    ('gyro_y',8,[.7071067811865475,-.7071067811865475,2j,-2j]),
    ('gyro_z',6,[2j/np.sqrt(3),-2j/np.sqrt(3),2j,-2j]),
])
def test_captured_rigid_pencils_recover_exact_zero_multiplicity_without_changing_physical_roots(name,count,expected):
    # Historical, fully specified matrices retain their original source record.
    case=json.loads(Path('docs/validation/dynamic-targets.json').read_text())['cases'][name]['result']
    a,m=(np.array(case['matrices'][key]) for key in ('A','M'))
    modes,meta=eigensystem(a,m,time_scale=case['diagnostics']['time_scale'],count=20)
    values=roots(modes)
    assert meta['finite_dimension']==12 and meta['integrator_deflation']['count']==count
    assert sum(v==0 for v in values)==count
    for value in expected:assert min(abs(values-value))<1e-8
    assert max(mode['right_backward_error'] for mode in modes)<1e-12
    assert max(mode['left_backward_error'] for mode in modes)<1e-12
