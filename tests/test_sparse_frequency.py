"""Full-equation parity for sparse harmonic matrices, poles and physical loads."""
from pathlib import Path
import numpy as np
import pytest
from scipy.sparse import csc_matrix,issparse
from openswing.asw import parse_asw
from openswing.aero import FlightCondition
from openswing.linear_dynamics import make_system,linearize
from openswing.frequency_response import harmonic_solve,HarmonicPole


@pytest.mark.parametrize('example,frame,extra',[
 ('rectangular','fixed',{}),('flexible','free',{'circulation_modes':{1:3}}),
 ('wing-body','free',{'ground_effect':1,'attitude':[11,-7,23],'position_earth':[0,0,30]}),
 ('wing-body','fixed',{'ground_effect':-1,'position_earth':[0,0,30]}),
 ('powered','free',{'powers':{1:7}}),('powered','fixed',{'powers':{1:7}}),('articulated','fixed',{}),
])
def test_sparse_complete_pencil_matches_original_fourth_order_equations(example,frame,extra):
    model=parse_asw(Path('examples',example+'.asw').read_text())
    model.reference[1]=[.7,-.2,.3];model.reference[2]=[.1,.2,-.1]
    s,_=make_system(model,FlightCondition(speed=20,alpha=3,mach=.1,rates=[.003,-.002,.001],**extra),4,
                    frame=frame,structured_base=True)
    dense_a,dense_m=linearize(s)
    a,m=linearize(s,sparse=True)
    assert issparse(a) and issparse(m)
    np.testing.assert_allclose(a.toarray(),dense_a,atol=2e-10,rtol=2e-10)
    np.testing.assert_allclose(m.toarray(),dense_m,atol=3e-12,rtol=3e-12)
    assert s.network.tangent_influences is None and s.network.iteration_fields is None
    # The original full equations also check the sparse solution independently.
    rhs=np.random.default_rng(12).normal(size=(s.size,2))
    for w in (.37,12.):
        x,d=harmonic_solve(a,m,rhs,w)
        reference,_=harmonic_solve(dense_a,dense_m,rhs,w)
        np.testing.assert_allclose(x,reference,atol=5e-6,rtol=2e-7)
        assert max(d['scaled_residuals'])<1e-7


@pytest.mark.parametrize('w',[0.,.7,13.])
def test_sparse_solve_is_covariant_with_units_and_keeps_algebraic_feedthrough(w):
    a=np.array([[-2.,1.,0.],[0.,-4.,1.],[.5,0.,-1.]])
    m=np.diag([1.,2.,0.]);b=np.array([[1.,.2],[0.,1.],[2.,-.7]])
    exact=np.linalg.solve(1j*w*m-a,b)
    for row,column in [(np.ones(3),np.ones(3)),(np.array([1e-5,2e4,.01]),np.array([1e3,1e-4,7.]))]:
        x,d=harmonic_solve(csc_matrix(row[:,None]*a*column),csc_matrix(row[:,None]*m*column),row[:,None]*b,w)
        np.testing.assert_allclose(column[:,None]*x,exact,atol=2e-14,rtol=2e-14)
        assert max(d['scaled_residuals'])<1e-12


def test_sparse_poles_and_ill_conditioned_pencils_remain_gaps():
    for a,m,w in [(np.zeros((2,2)),np.eye(2),0.),
                  (np.array([[0.,1.],[-4.,0.]]),np.eye(2),2.),
                  (np.array([[1.,1.],[1.,1.+1e-13]]),np.zeros((2,2)),1.)]:
        with pytest.raises(HarmonicPole):harmonic_solve(csc_matrix(a),csc_matrix(m),np.ones((2,1)),w)


def test_exact_cache_is_restored_after_failed_dynamic_stencil(monkeypatch):
    s,_=make_system(parse_asw(Path('examples/rectangular.asw').read_text()),FlightCondition(speed=20),4,structured_base=True)
    original=s.residual;count=0
    def fail(*args,**kw):
        nonlocal count
        count+=1
        if count==5:raise ValueError('failed stencil')
        return original(*args,**kw)
    monkeypatch.setattr(s,'residual',fail)
    with pytest.raises(ValueError,match='failed stencil'):linearize(s,sparse=True)
    assert s.network.tangent_influences is None and s.network.iteration_fields is None


def test_sparse_feedback_inertia_and_cubic_hinge_match_dense_equations():
    from test_feedback import configuration,condition,law
    from test_joints import linked
    from openswing.asw import Distribution
    controlled,_=make_system(configuration(),condition(),4,gravity=[0,0,0],controller=law(ki=100.,ka=3.))
    model=linked(curve='-100 -40\n0 5\n100 140',axis='2 1 3',offset=True)
    for name,value in [('mg',19.6133),('mgcc',.3),('mgnn',.5)]:
        model.beams[0].distributions[name]=Distribution(name,np.array([0.,2.]),np.array([value,value]),0)
    hinged,_=make_system(model,None,4,gravity=[0,0,0],loads=[dict(beam=2,t=2,moment=[4,2,6])])
    for s in (controlled,hinged):
        a,m=linearize(s);aa,mm=linearize(s,sparse=True)
        np.testing.assert_allclose(aa.toarray(),a,atol=2e-10,rtol=2e-10)
        np.testing.assert_allclose(mm.toarray(),m,atol=3e-12,rtol=3e-12)


def test_sparse_live_refinement_reuses_pencil_and_retains_previous_samples(monkeypatch):
    from openswing.frequency_sweep import FrequencySweep
    import openswing.frequency_response as module
    sweep=FrequencySweep(parse_asw(Path('examples/rectangular.asw').read_text()),
        FlightCondition(speed=20,alpha=0,mach=.1),14,frequencies=[.3,3.],inputs=['control.1'],gravity=[0,0,0])
    assert issparse(sweep.analysis.a)
    saved=sweep.report();a=sweep.analysis.a.copy();m=sweep.analysis.m.copy()
    def forbidden(*args,**kwargs):raise AssertionError('Refinement must reuse the frozen loaded model')
    monkeypatch.setattr(module,'make_system',forbidden);monkeypatch.setattr(module,'linearize',forbidden)
    result=sweep.extend([.3,1.,10.])
    assert result['converged']
    for row in saved['samples']:assert row==next(s for s in result['samples'] if s['omega']==row['omega'])
    assert (a!=sweep.analysis.a).nnz==0 and (m!=sweep.analysis.m).nnz==0
