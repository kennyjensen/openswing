"""Newton/Bode physical mechanical blocks and unchanged nonlinear safeguards."""
from pathlib import Path
import numpy as np
import pytest
from openswing.asw import parse_asw
from openswing.aero import FlightCondition
from openswing.network import StaticNetwork
from openswing.structured_static import jacobian,linearization,equilibrate
from openswing.mechanical_tangent import network_mechanical_columns,MechanicalDerivativeUnavailable
from openswing.operating import time_load_constraints
from test_direct_circulation import state_for,model_for
from test_joints import linked


def network(example='flexible',frame='prescribed',panels=4):
    model=model_for(example)
    return StaticNetwork(model,panels,FlightCondition(speed=20,alpha=5,beta=2,mach=.1,
        powers={1:7} if example=='powered' else {}),None,[],operating_constraints=time_load_constraints(frame,{'force.x':.1,'moment.y':.2} if frame=='mixed' else None))


@pytest.mark.parametrize('factor',[0.,.37,1.])
@pytest.mark.parametrize('reverse',[False,True])
def test_shared_hinge_partial_respects_continued_zero_angle_and_both_traces(factor,reverse):
    model=linked(curve='-100 -45\n0 15\n100 135',axis='1 2 3',reverse=reverse,offset=True)
    n=StaticNetwork(model,4,None,[0,0,0],[]);x=state_for(n,.3)
    x[:6*n.nn].reshape(-1,6)[:,3:]+=[.5,-.2,.3]
    _,data=n.residual(x,factor,detail=True)
    scales=np.maximum(1.,abs(x));actual,report=network_mechanical_columns(n,data,scales,1e-6,factor=factor)
    assert report['hinge_constraints']==1
    hinge=next(c for c in n.constraints if c['type']==3)
    assert hinge['end'] is not reverse
    rng=np.random.default_rng(826)
    for width in [1e-4,3e-5]:
        for local in rng.normal(size=(3,actual.shape[1])):
            delta=np.r_[np.zeros(6*n.nn),local,np.zeros(n.size-n.gamma_start)]
            values=[n.residual(x+k*width*delta,factor) for k in [1,-1,2,-2]]
            reference=(8*(values[0]-values[1])-(values[2]-values[3]))/(12*width)
            assert np.max(abs(actual@local-reference)/(1+abs(reference)))<2e-8


@pytest.mark.parametrize('example,frame',[('flexible','prescribed'),('wing-body','free'),('powered','mixed'),('torsion-joint','prescribed'),('dae','free')])
def test_shared_newton_blocks_match_full_residual_and_leave_other_columns(example,frame):
    n=network(example,frame);x=state_for(n,.3)
    direct,report=jacobian(n,x,.37)
    old,old_report=jacobian(n,x,.37,direct_mechanics=False)
    a,b=direct.toarray(),old.toarray();idx=np.r_[np.arange(6*n.nn),np.arange(n.gamma_start,n.size)]
    # Geometry groups change, but disjoint structural supports cannot alter
    # the individual original forward-difference columns.
    np.testing.assert_array_equal(a[:,idx],b[:,idx])
    assert report['mechanical_derivative']['columns']==n.gamma_start-6*n.nn
    assert report['evaluations']<old_report['evaluations']
    assert report['groups']<old_report['groups']
    rng=np.random.default_rng(519)
    for local in rng.normal(size=(3,n.gamma_start-6*n.nn)):
        delta=np.r_[np.zeros(6*n.nn),local,np.zeros(n.size-n.gamma_start)];h=3e-5
        values=[n.residual(x+k*h*delta,.37) for k in [1,-1,2,-2]]
        physical=(8*(values[0]-values[1])-(values[2]-values[3]))/(12*h)
        assert np.max(abs(a@delta-physical)/(1+abs(physical)))<2e-8
    assert n.iteration_fields is None and n.tangent_influences is None


def test_direct_budget_fallback_restores_original_matrix_and_counts(monkeypatch):
    import openswing.mechanical_tangent as module
    n=network();x=state_for(n,.3);expected,reference=jacobian(n,x,.37,direct_mechanics=False)
    def fail(*args,**kwargs):raise MechanicalDerivativeUnavailable('deliberate budget limit')
    monkeypatch.setattr(module,'network_mechanical_columns',fail)
    actual,report=jacobian(n,x,.37)
    np.testing.assert_array_equal(actual.toarray(),expected.toarray())
    assert report['evaluations']==reference['evaluations']
    assert report['groups']==reference['groups']
    assert 'deliberate' in report['mechanical_derivative_fallback']
    assert n.iteration_fields is None and n.tangent_influences is None


@pytest.mark.parametrize('branch',[False,True])
def test_continued_hinge_branch_falls_back_to_the_original_newton_stencil(branch):
    model=linked(curve='-100 -85\n100 115' if branch else '-100 -85\n0 15\n0 15\n100 215')
    n=StaticNetwork(model,4,None,[0,0,0],[]);x=np.zeros(n.size);factor=.37
    if branch:
        # At zero moment the continued angle is factor*15 degrees.
        x[:6*n.nn].reshape(-1,6)[n.beam_nodes[2],3]=np.pi-1e-8+factor*np.deg2rad(15)
    actual,report=jacobian(n,x,factor);expected,_=jacobian(n,x,factor,direct_mechanics=False)
    assert ('logarithm branch' if branch else 'slope break') in report['mechanical_derivative_fallback']
    np.testing.assert_array_equal(actual.toarray(),expected.toarray())


@pytest.mark.parametrize('example,frame',[('flexible','prescribed'),('powered','mixed'),('torsion-joint','prescribed'),('wing-body','free')])
def test_shared_blocks_preserve_complete_converged_equilibrium(example,frame,monkeypatch):
    import openswing.structured_static as module
    n=network(example,frame);actual,steps=equilibrate(n,tolerance=1e-12)
    baseline=network(example,frame);original=module.jacobian
    def legacy(*args,**kwargs):return original(*args,**kwargs,direct_mechanics=False)
    with monkeypatch.context() as context:
        context.setattr(module,'jacobian',legacy)
        expected,reference_steps=equilibrate(baseline,tolerance=1e-12)
    assert np.max(abs(n.residual(actual)))<=1e-12
    assert np.max(abs(baseline.residual(expected)))<=1e-12
    np.testing.assert_allclose(actual,expected,rtol=1e-8,atol=2e-9)
    assert steps==reference_steps
    assert any(row.get('mechanical_derivative') for row in n.structured_iterations)
    assert n.iteration_fields is None and n.tangent_influences is None


def test_newton_capture_keeps_load_only_path_and_the_original_base_residual(monkeypatch):
    n=network('torsion-joint');x=state_for(n,.3);expected=n.residual(x,.37)
    original=n.external;detail=[]
    def external(*args,**kwargs):
        detail.append(kwargs.get('_loads_only'))
        return original(*args,**kwargs)
    monkeypatch.setattr(n,'external',external)
    with linearization(n,x,.37,capture_mechanics=True) as (fields,base):
        np.testing.assert_array_equal(base,expected)
        data=fields.mechanical_data
        assert set(data)=={'r','Q','section_frame','hinges'}
        assert data['hinges'] and set(data['hinges'][0])=={'joint','structural_moment'}
        n.residual(x+1e-7,.37)
        assert fields.mechanical_data is data
    assert detail and all(detail)
    assert n.iteration_fields is None and n.tangent_influences is None


@pytest.mark.parametrize('example',['flexible','torsion-joint'])
@pytest.mark.parametrize('factor',[0.,.37])
@pytest.mark.parametrize('moving',[False,True])
def test_complete_newton_jacobian_shares_the_physical_load_columns(example,factor,moving):
    n=network(example);x=state_for(n,.3);options={}
    if moving:
        rng=np.random.default_rng(283)
        options=dict(elastic_motion=tuple(rng.normal(size=(n.nn,3))*.001 for _ in range(4)),
                     circulation_rate=np.full(n.circulation_basis.panels,.002))
    before=n.nfev;actual=n.jacobian(x,factor,**options);calls=n.nfev-before
    assert n.mechanical_derivative_diagnostics['columns']==n.gamma_start-6*n.nn
    before=n.nfev;original=n.jacobian(x,factor,_direct_mechanics=False,**options)
    assert calls<n.nfev-before
    other=np.r_[np.arange(6*n.nn),np.arange(n.gamma_start,n.size)]
    np.testing.assert_array_equal(actual[:,other],original[:,other])
    for local in np.random.default_rng(719).normal(size=(2,n.gamma_start-6*n.nn)):
        delta=np.r_[np.zeros(6*n.nn),local,np.zeros(n.size-n.gamma_start)];h=3e-5
        values=[n.residual(x+k*h*delta,factor,**options) for k in [1,-1,2,-2]]
        physical=(8*(values[0]-values[1])-(values[2]-values[3]))/(12*h)
        assert np.max(abs(actual@delta-physical)/(1+abs(physical)))<2e-8
    assert n.iteration_fields is None and n.tangent_influences is None


def test_complete_newton_storage_fallback_preserves_legacy_columns(monkeypatch):
    import openswing.mechanical_tangent as module
    n=network('torsion-joint');x=state_for(n,.3)
    expected=n.jacobian(x,.37,_direct_mechanics=False)
    def fail(*args,**kwargs):raise MechanicalDerivativeUnavailable('deliberate physical block limit')
    monkeypatch.setattr(module,'network_mechanical_columns',fail)
    actual=n.jacobian(x,.37)
    np.testing.assert_array_equal(actual,expected)
    assert 'deliberate' in n.mechanical_derivative_diagnostics['fallback']
    assert n.iteration_fields is None and n.tangent_influences is None
