"""Full matrix and independent dynamics checks for sparse free/mixed BDF steps."""
from pathlib import Path
import numpy as np
import pytest
from openswing.asw import parse_asw
from openswing.aero import FlightCondition
from openswing.operating import time_operating_constraints
from openswing.structured_time import jacobian, Factorization
from openswing.time_integration import solve_time
from test_structured_time import setup


@pytest.mark.parametrize('example,extra,frame,targets',[
    ('inertial',{},'free',None),
    ('transient-wing',{},'free',None),
    ('transient-wing',{'circulation_modes':{1:3}},'free',None),
    ('powered',{'powers':{1:30}},'mixed',{'force.x':.1,'moment.y':.2}),
    ('wing-body',{'ground_effect':1,'position_earth':[0,0,30],
                  'attitude':[13,-7,21],'rates':[.003,-.002,.001]},'mixed',{'force.z':.5}),
    ('articulated',{},'mixed',{'force.y':.2,'moment.x':.1}),
])
def test_grouped_load_rows_match_individual_columns_and_full_border(example,extra,frame,targets):
    system,function,x=setup(example,extra,frame=frame,
        constraints=time_operating_constraints(frame,targets))
    original=function(x).copy()
    matrix,p,counts=jacobian(system,function,x)
    reference,rp,individual=jacobian(system,function,x,grouped=False)
    np.testing.assert_array_equal(p,rp)
    np.testing.assert_allclose(matrix.toarray(),reference.toarray(),rtol=1e-8,atol=2e-8)
    assert counts['evaluations']<individual['evaluations']
    assert counts['matrix_storage_bytes']<8*system.size**2
    assert system.network.iteration_fields is None
    assert system.network.tangent_influences is None
    np.testing.assert_array_equal(function(x),original)
    nlocal=matrix.mechanical.shape[0]
    for j,column in enumerate(p[nlocal:]):
        trial=x.copy();h=1e-6*max(1.,abs(x[column]));trial[column]+=h
        expected=(function(trial)-original)[p]/h
        actual=np.r_[matrix.force_circulation[:,j],matrix.circulation[:,j]]
        np.testing.assert_allclose(actual,expected,rtol=1e-8,atol=2e-8)
    rhs=np.random.default_rng(91).normal(size=system.size)
    actual=Factorization(matrix,p).solve(rhs)[p]
    expected=np.linalg.solve(matrix.toarray(),rhs[p])
    np.testing.assert_allclose(actual,expected,rtol=2e-7,atol=2e-7)


@pytest.mark.parametrize('case',['aerodynamic','flap','mixed_loads','free_spin'])
def test_complete_frame_response_matches_dense_newton(monkeypatch,case):
    from test_time_integration import rigid_body
    from openswing.inertia import Motion
    import openswing.structured_time as module
    if case in ('aerodynamic','flap'):
        model=parse_asw(Path('examples/'+('inertial' if case=='aerodynamic' else 'transient-wing')+'.asw').read_text())
        args=dict(condition=FlightCondition(speed=20,alpha=3,mach=.1),frame='free')
        if case=='flap':args['forcing']='time +F1\n0 0\n.02 0\n.02 1\n.04 1'
    else:
        model=rigid_body()
        args=dict(gravity=[0,0,0],motion=Motion(rates=[.2,.3,.4]))
        if case=='mixed_loads':args.update(frame='mixed',load_targets={'force.x':0,'moment.z':0},forcing='time Fx Mz\n0 0 0\n.04 .2 .3')
        else:args['frame']='free'
    counts=[];original=module.Factorization.solve
    def track(self,rhs):
        result=original(self,rhs);counts.append(True);return result
    monkeypatch.setattr(module.Factorization,'solve',track)
    actual=solve_time(model,panels=4,duration=.04,dt=.01,**args)
    assert counts
    monkeypatch.setattr(module,'attach',lambda *a,**kw:None)
    expected=solve_time(model,panels=4,duration=.04,dt=.01,**args)
    assert actual['accepted_steps']==expected['accepted_steps']
    assert actual['rejected_steps']==expected['rejected_steps']==0
    for a,b in zip(actual['snapshots'],expected['snapshots']):
        assert a['time']==b['time'] and a['residual']<=1e-8
        for key in ('force','moment','support_force','support_moment','local_velocity',
                    'local_rates','local_acceleration','circulation_rate',
                    'force_balance','moment_balance','applied_force','applied_moment'):
            if key in b:np.testing.assert_allclose(a[key],b[key],rtol=3e-6,atol=3e-6,err_msg=case+'/'+key)
        for key in ('position_earth','velocity_origin_body','body_to_earth','rates_body',
                    'acceleration_reference_body','angular_acceleration_body'):
            np.testing.assert_allclose(a['frame'][key],b['frame'][key],rtol=2e-7,atol=2e-8,err_msg=case+'/'+key)
        np.testing.assert_allclose([n['position'] for n in a['nodes']],
                                   [n['position'] for n in b['nodes']],rtol=1e-8,atol=1e-8)


@pytest.mark.parametrize('frame',['free','mixed'])
def test_refined_steps_and_restart_retain_independent_frame_loads(monkeypatch,frame):
    from test_time_integration import rigid_body
    from openswing.time_state import checkpoint,resume_time
    import openswing.structured_time as module
    used=[];original=module.Factorization.solve
    def track(self,rhs):
        result=original(self,rhs);used.append(True);return result
    monkeypatch.setattr(module.Factorization,'solve',track)
    model=rigid_body()
    out=solve_time(model,panels=4,frame=frame,load_targets={'force.x':.3,'moment.z':.2},
        duration=.04,dt=.02,gravity=[0,0,0],accuracy=dict(rtol=.001,atol=1e-6))
    assert used and out['accuracy']['maximum_accepted_ratio']<=1
    resumed=resume_time(model,checkpoint(out),duration=.02)
    assert resumed['snapshots'][0]['time']==.04
    for row in out['snapshots']+resumed['snapshots']:
        assert row['residual']<=1e-8
        # One kg at the frame origin, Izz=4, no applied force or torque.
        np.testing.assert_allclose(row['frame']['acceleration_reference_body'],[-.3,0,0],atol=2e-8)
        np.testing.assert_allclose(row['frame']['angular_acceleration_body'],[0,0,-.05],atol=2e-8)
        np.testing.assert_allclose(row['frame']['rates_body'],[0,0,-.05*row['time']],atol=2e-8)
        assert row['applied_force'][0]==pytest.approx(.3,abs=2e-8)
        assert row['applied_moment'][2]==pytest.approx(.2,abs=2e-8)
