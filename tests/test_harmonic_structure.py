"""Exact harmonic block reuse against full equations and independent inverses."""
from pathlib import Path
import numpy as np
import pytest
from scipy.sparse import csc_matrix,diags
from openswing.harmonic_structure import ReusableBeamStructure,StructureUnavailable
from openswing.frequency_response import harmonic_solve,HarmonicPole,FrequencyAnalysis
from openswing.asw import parse_asw
from openswing.aero import FlightCondition
from openswing.linear_dynamics import make_system,linearize


def freeze(*matrices):
    for matrix in matrices:
        for values in (matrix.data,matrix.indices,matrix.indptr):values.flags.writeable=False
    return matrices


def synthetic(diagonal=True,units=False):
    rng=np.random.default_rng(7)
    a=rng.normal(size=(8,8));m=rng.normal(size=(8,8))
    rows=np.array([5,1]);cols=np.array([6,2]);vr=np.array([3,7]);vc=np.array([0,4])
    a[np.ix_(rows,cols)]=[[3.,.1],[-.2,2.]]
    a[np.ix_(rows,vc)]=0.;m[rows]=0.
    a[np.ix_(vr,vc)]=np.diag([-1.,-2.]);m[np.ix_(vr,vc)]=0.
    if not diagonal:a[vr[0],vc[1]]=.17
    if units:
        r=10.**np.linspace(-5,5,8);c=10.**np.linspace(4,-4,8)
        a=r[:,None]*a*c;m=r[:,None]*m*c
    a,m=freeze(csc_matrix(a),csc_matrix(m))
    return a,m,ReusableBeamStructure(a,m,rows,cols,vr,vc)


@pytest.mark.parametrize('diagonal',[False,True])
@pytest.mark.parametrize('units',[False,True])
def test_permuted_blocks_recover_all_rhs_and_full_inverse_adjoint(diagonal,units):
    a,m,structure=synthetic(diagonal,units)
    rng=np.random.default_rng(13)
    for s in [0j,.3+.7j,19j]:
        k=s*m-a;rows=np.maximum(abs(k).max(axis=1).toarray().ravel(),1e-30)
        rowed=diags(1/rows)@k;cols=np.maximum(abs(rowed).max(axis=0).toarray().ravel(),1e-30)
        scaled=(rowed@diags(1/cols)).toarray();factor=structure.factor(a,m,s,rows,cols)
        assert factor.dimension==(4 if diagonal else 6)
        # Include arbitrary forcing in eliminated equations, and independently
        # verify the full inverse, transpose and conjugate transpose actions.
        for trans,operator in [('N',scaled),('T',scaled.T),('H',scaled.conj().T)]:
            rhs=rng.normal(size=(8,3))+1j*rng.normal(size=(8,3))
            exact=np.linalg.solve(operator,rhs)
            np.testing.assert_allclose(factor.solve(rhs,trans=trans),exact,rtol=2e-11,atol=2e-11)
            np.testing.assert_allclose(factor.solve(rhs[:,0],trans=trans),exact[:,0],rtol=2e-11,atol=2e-11)
        b=rng.normal(size=(8,3))+1j*rng.normal(size=(8,3))
        actual,checks=harmonic_solve(a,m,b,s.imag,shift=s.real,_structure=structure)
        expected,reference=harmonic_solve(a,m,b,s.imag,shift=s.real)
        np.testing.assert_allclose(actual,expected,rtol=2e-10,atol=2e-10)
        assert checks['reciprocal_condition']==pytest.approx(reference['reciprocal_condition'],rel=2e-10)
        assert checks['factor_dimension']==factor.dimension
        assert checks['beam_equations_eliminated']==2


def structure_for(system,a,m):
    n=system.network;freeze(a,m)
    return ReusableBeamStructure(a,m,np.r_[np.arange(6*n.ne),np.arange(6*(n.ne+n.nn),n.gamma_start)],
        np.arange(6*(n.nn+n.ne)),np.arange(n.size,system.frame_start),np.arange(system.velocity_start,system.frame_start))


@pytest.mark.parametrize('example,frame,extra',[
    ('rectangular','fixed',{}),('flexible','free',{'circulation_modes':{1:3}}),
    ('wing-body','free',{'ground_effect':1,'attitude':[11,-7,23],'position_earth':[0,0,30]}),
    ('powered','fixed',{'powers':{1:7}}),('articulated','fixed',{}),
])
def test_physical_pencils_keep_every_state_and_full_condition_gate(example,frame,extra):
    model=parse_asw(Path('examples',example+'.asw').read_text())
    s,_=make_system(model,FlightCondition(speed=20,alpha=3,mach=.1,**extra),4,frame=frame,structured_base=True)
    a,m=linearize(s,sparse=True);structure=structure_for(s,a,m)
    rhs=np.random.default_rng(12).normal(size=(s.size,2))
    for w in [.37,12.]:
        expected,reference=harmonic_solve(a,m,rhs,w)
        actual,checks=harmonic_solve(a,m,rhs,w,_structure=structure)
        np.testing.assert_allclose(actual,expected,rtol=2e-7,atol=5e-6)
        assert checks['reciprocal_condition']==pytest.approx(reference['reciprocal_condition'],rel=2e-6)
        assert max(checks['scaled_residuals'])<1e-7
        assert checks['beam_equations_eliminated']>0


def test_controller_and_material_damping_preserve_rate_coupling():
    from test_feedback import configuration,condition,law
    model=configuration()
    # Material damping couples compatibility equations to elastic velocities.
    from openswing.asw import Distribution
    model.beams[0].distributions['tdeps']=Distribution('tdeps',np.array([0.,2.]),np.array([.01,.01]),0)
    s,_=make_system(model,condition(),4,gravity=[0,0,0],controller=law(ki=100.,ka=3.))
    a,m=linearize(s,sparse=True);structure=structure_for(s,a,m)
    assert np.max(s.network.damping_times)==.01
    assert m[structure.rows].nnz==0
    b=np.random.default_rng(52).normal(size=(s.size,3))
    for w in [.4,9.]:
        actual,checks=harmonic_solve(a,m,b,w,_structure=structure)
        expected,_=harmonic_solve(a,m,b,w)
        np.testing.assert_allclose(actual,expected,rtol=2e-7,atol=5e-6)
        assert max(checks['scaled_residuals'])<1e-7


def test_rows_with_derivative_terms_are_not_treated_as_static():
    a,m,t=synthetic();m=m.toarray();m[t.rows[0],0]=.23;m=freeze(csc_matrix(m))[0]
    reduced=ReusableBeamStructure(a,m,t.rows,t.columns,[],[])
    assert reduced.rows.tolist()==[t.rows[1]]
    b=np.arange(16).reshape(8,2)
    for w in [.2,30.]:
        actual,_=harmonic_solve(a,m,b,w,_structure=reduced)
        expected,_=harmonic_solve(a,m,b,w)
        np.testing.assert_allclose(actual,expected,rtol=2e-12,atol=2e-12)


@pytest.mark.parametrize('delta',[0.,1e-12])
def test_singular_or_poorly_conditioned_optional_pivots_are_rejected(delta):
    a,m=freeze(csc_matrix([[1.,1.,.2],[1.,1.+delta,.3],[.1,.4,1.]]),csc_matrix((3,3)))
    with pytest.raises(StructureUnavailable):ReusableBeamStructure(a,m,[0,1],[0,1],[],[])


def test_storage_mutability_missing_structure_and_owner_guards():
    a,m,t=synthetic()
    args=(t.rows,t.columns,[],[])
    with pytest.raises(StructureUnavailable,match='immutable'):
        ReusableBeamStructure(a.copy(),m.copy(),*args)
    with pytest.raises(StructureUnavailable,match='budget'):
        ReusableBeamStructure(a,m,*args,byte_budget=1)
    with pytest.raises(StructureUnavailable,match='frequency-independent'):
        ReusableBeamStructure(a,freeze(csc_matrix(np.eye(8)))[0],*args)
    with pytest.raises(StructureUnavailable,match='different descriptor'):
        t.factor(a.copy(),m,1j,np.ones(8),np.ones(8))
    # Public harmonic solve safely falls back if supplied a stale owner.
    actual,checks=harmonic_solve(a.copy(),m,np.ones((8,1)),1.,_structure=t)
    expected,_=harmonic_solve(a,m,np.ones((8,1)),1.)
    np.testing.assert_array_equal(actual,expected)
    assert checks['beam_equations_eliminated']==0


@pytest.mark.parametrize('delta',[0.,1e-13,1e-10,1e-7])
def test_full_pencil_near_pole_gate_survives_a_well_conditioned_beam_block(delta):
    a,m=freeze(csc_matrix([[1.,0.,0.],[0.,1.,1.],[0.,1.,1.+delta]]),csc_matrix((3,3)))
    t=ReusableBeamStructure(a,m,[0],[0],[],[])
    if delta<=1e-13:
        with pytest.raises(HarmonicPole):harmonic_solve(a,m,np.ones((3,1)),1.,_structure=t)
    else:
        actual,checks=harmonic_solve(a,m,np.ones((3,1)),1.,_structure=t)
        expected,reference=harmonic_solve(a,m,np.ones((3,1)),1.)
        np.testing.assert_allclose(actual,expected,rtol=2e-9,atol=2e-9)
        assert checks['reciprocal_condition']==pytest.approx(reference['reciprocal_condition'],rel=2e-9)
        assert checks['beam_equations_eliminated']==(0 if delta==1e-10 else 1)


@pytest.mark.parametrize('failure',['factor','inverse','solution','residual'])
def test_failed_optional_reduction_uses_original_solver(monkeypatch,failure):
    a,m,t=synthetic();original=t.factor
    class Fault:
        def __init__(self,factor):self.factor=factor;self.calls=0
        def solve(self,rhs,trans='N'):
            self.calls+=1
            if failure=='inverse' or (failure=='solution' and np.asarray(rhs).ndim==2 and rhs.shape[1]==3):
                raise ValueError('unavailable inverse')
            value=self.factor.solve(rhs,trans=trans)
            return .9*value if failure=='residual' else value
    def broken(*args):
        if failure=='factor':raise ValueError('unavailable factor')
        return Fault(original(*args))
    monkeypatch.setattr(t,'factor',broken)
    rhs=np.arange(24).reshape(8,3)+1
    actual,checks=harmonic_solve(a,m,rhs,1.,_structure=t)
    expected,reference=harmonic_solve(a,m,rhs,1.)
    np.testing.assert_array_equal(actual,expected);assert checks==reference


def test_frequency_runs_and_extensions_share_only_matching_beam_factors(monkeypatch):
    model=parse_asw(Path('examples/rectangular.asw').read_text());c=FlightCondition(speed=20,alpha=0,mach=.1)
    options=dict(inputs=['control.1'],gravity=[0,0,0])
    original=FrequencyAnalysis(model,c,14,**options)
    structure=original.harmonic_structure;assert structure is not None
    expected=original.solve([.3,3.])
    def forbidden(*args,**kwargs):raise AssertionError('Rebuilt cached beam factors')
    with monkeypatch.context() as patch:
        patch.setattr(ReusableBeamStructure,'__init__',forbidden)
        assert original.solve([.3,3.])==expected
        reused=FrequencyAnalysis(model,c,14,_base_analysis=original,**options)
        assert reused.harmonic_structure is structure
        assert reused.solve([.7])['converged']
    changed=FrequencyAnalysis(model,FlightCondition(speed=21,alpha=0,mach=.1),14,_base_analysis=original,**options)
    assert changed.harmonic_structure is not structure
