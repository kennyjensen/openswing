"""Full equilibrium controls and safeguards for cached Newton factors."""
from pathlib import Path
import numpy as np
import pytest
from openswing.asw import parse_asw
from openswing.aero import FlightCondition
from openswing.network import StaticNetwork
from openswing.operating import time_load_constraints
from openswing.structured_static import jacobian,BlockFactorization,block_solve,equilibrate


def network(example='flexible',extra=None,frame='prescribed'):
    model=parse_asw(Path('examples/'+example+'.asw').read_text())
    model.reference[1]=[.7,.2,-.4];model.reference[2]=[.3,-.2,.4]
    targets={'force.x':.1,'moment.y':.2} if frame=='mixed' else None
    return StaticNetwork(model,4,FlightCondition(speed=20,alpha=3,mach=.1,**(extra or {})),
                         None,[],operating_constraints=time_load_constraints(frame,targets))


@pytest.mark.parametrize('example,frame',[('flexible','prescribed'),('wing-body','free'),('stepped-body','prescribed')])
def test_fixed_factors_solve_multiple_original_matrix_right_hand_sides(example,frame):
    n=network(example,frame=frame);x=np.random.default_rng(4).normal(0,.0001,n.size)
    x[n.gamma_start:n.operating_start]+=.04
    matrix,_=jacobian(n,x,.6);factor=BlockFactorization(matrix)
    for rhs in np.random.default_rng(6).normal(size=(3,n.size)):
        actual=block_solve(matrix,rhs,factorization=factor)
        expected=np.linalg.solve(matrix.toarray(),rhs)
        np.testing.assert_allclose(actual,expected,rtol=1e-8,atol=1e-8)
        assert np.max(abs(matrix.toarray()@actual-rhs))<1e-8*max(1.,np.max(abs(rhs)))


@pytest.mark.parametrize('example,extra,frame',[
    ('flexible',{},'prescribed'),('dae',{},'free'),
    ('powered',{'powers':{1:30}},'mixed'),
    ('wing-body',{'ground_effect':1,'position_earth':[0,0,30],'attitude':[13,-7,21]},'free'),
    ('articulated',{},'prescribed'),
    ('flexible',{'circulation_modes':{1:3}},'free'),
])
def test_reuse_reaches_the_full_fresh_matrix_equilibrium(example,extra,frame):
    n=network(example,extra,frame);control=network(example,extra,frame)
    actual,steps=equilibrate(n)
    expected,reference_steps=equilibrate(control,reuse_matrices=False)
    assert steps==reference_steps and steps>0
    if not n.hinges:assert steps==4
    assert np.max(abs(n.residual(actual)))<=1e-12
    assert np.max(abs(control.residual(expected)))<=1e-12
    np.testing.assert_allclose(actual,expected,atol=2e-9,rtol=1e-8)
    assert n.structured_rank_check['method']==control.structured_rank_check['method']
    assert any(r['matrix_reused'] for r in n.structured_iterations)
    assert sum(not r['matrix_reused'] for r in n.structured_iterations)<len(control.structured_iterations)
    assert not any(r['matrix_reused'] for r in control.structured_iterations)
    previous=None
    for record in n.structured_iterations:
        if record['load_fraction']!=previous:assert not record['matrix_reused']
        assert record['matrix_age']<=6
        previous=record['load_fraction']
    assert n.iteration_fields is None and n.tangent_influences is None


@pytest.mark.parametrize('angle', [200., -200.])
def test_hinge_reuse_preserves_analytic_solution_and_refreshes_at_chart_crossing(angle):
    from test_hinge_chart_state import network as hinge_network
    from openswing.equilibrium_state import capture
    n=hinge_network(angle)
    x,steps=equilibrate(n)
    theta=np.deg2rad(angle)
    assert np.max(abs(n.residual(x)))<=1e-12
    assert capture(n,x)['hinge_charts'][0]['angle_rad']==pytest.approx(theta,abs=2e-12)
    r,Q,*_=n.unpack(x)
    np.testing.assert_allclose(r[-1],[0,2+2*np.cos(theta),2*np.sin(theta)],atol=2e-12)
    c,s=np.cos(theta),np.sin(theta)
    np.testing.assert_allclose(Q[-1],[[1,0,0],[0,c,-s],[0,s,c]],atol=2e-12)
    records=n.structured_iterations
    assert any(r['matrix_reused'] for r in records)
    crossings=[i for i,r in enumerate(records) if r.get('rotation_chart_changed')]
    assert crossings
    for i in crossings:
        if i+1<len(records):assert not records[i+1]['matrix_reused']
    assert max(r['accepted_load_rotation_increment_rad'] for r in n.continuation_diagnostics
               if r['accepted'])<=np.deg2rad(5)*(1+1e-12)


@pytest.mark.parametrize('frame', ['prescribed', 'mixed'])
def test_source_airflow_hinge_reuse_matches_fresh_moving_equations(frame):
    from openswing.source_airflow import SourceAirflowNetwork
    from test_source_joints import source, mounted_condition
    model=parse_asw(source(distant=False, offsets=True, mass=True, axis='1 0 0'),
                    beam_interpolation='drela-segspl-v1')
    constraints=time_load_constraints(frame,{'moment.x':0.} if frame=='mixed' else None)
    def make():
        return SourceAirflowNetwork(model,4,mounted_condition(),[0,0,0],[],
            operating_constraints=constraints,steady_trim=True)
    actual_net,reference_net=make(),make()
    actual,_=equilibrate(actual_net)
    reference,_=equilibrate(reference_net,reuse_matrices=False)
    assert np.max(abs(actual_net.residual(actual)))<=1e-12
    assert np.max(abs(reference_net.residual(reference)))<=1e-12
    np.testing.assert_allclose(actual,reference,atol=2e-9,rtol=1e-8)
    assert any(r['matrix_reused'] for r in actual_net.structured_iterations)
    assert sum(not r['matrix_reused'] for r in actual_net.structured_iterations)<len(reference_net.structured_iterations)
    assert actual_net.iteration_fields is None and actual_net.tangent_influences is None


@pytest.mark.parametrize('failure',['factor','direction'])
def test_failed_reuse_rebuilds_at_same_state_before_full_fallback(monkeypatch,failure):
    import openswing.structured_static as module
    n=network();original=module.block_solve;seen=[];failed=[]
    def fail_stale(matrix,rhs,*args,**kwargs):
        factor=kwargs['factorization']
        repeated=any(factor is old for old in seen);seen.append(factor)
        if repeated and not failed:
            failed.append(True)
            if failure=='factor':raise ValueError('deliberate stale factor failure')
            return np.zeros_like(rhs) # No physical merit reduction at any line-search step.
        return original(matrix,rhs,*args,**kwargs)
    monkeypatch.setattr(module,'block_solve',fail_stale)
    x,steps=equilibrate(n)
    assert failed and steps==4 and np.max(abs(n.residual(x)))<=1e-12
    recovery=[r for r in n.structured_iterations if r.get('reuse_failed')]
    assert recovery and all(not r['matrix_reused'] and not r.get('exact_fallback') for r in recovery)
    assert n.iteration_fields is None and n.tangent_influences is None


def test_corrupt_factor_is_rejected_by_original_linear_equations():
    n=network();x=np.zeros(n.size);x[n.gamma_start:n.operating_start]=.04
    matrix,_=jacobian(n,x,.6);factor=BlockFactorization(matrix)
    factor.coupling[:]=0
    with pytest.raises(ValueError,match='linear solve failed'):
        factor.solve(np.random.default_rng(6).normal(size=n.size))
