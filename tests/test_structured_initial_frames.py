"""Free/mixed initial matrices, physical roots and unchanged rejection paths."""
from pathlib import Path
import numpy as np
import pytest
from openswing.asw import parse_asw
from openswing.aero import FlightCondition,AnalysisError
from openswing.network import StaticNetwork,_equilibrate_full
from openswing.operating import time_load_constraints
from openswing.structured_static import jacobian,block_solve,check_initial_rank
import openswing.time_integration as time


CASES=[
 ('transient-wing',{},'free',None),
 ('flexible',{'circulation_modes':{1:3}},'free',None),
 ('powered',{'powers':{1:30}},'mixed',{'force.x':.1,'moment.y':.2}),
 ('articulated',{},'mixed',{'force.y':.2,'moment.x':.1}),
 ('wing-body',{'ground_effect':1,'position_earth':[0,0,30],
                'attitude':[13,-7,21]},'free',None),
 ('guided-body',None,'free',None),
]


def network(example,extra,frame,targets):
    model=parse_asw(Path('examples/'+example+'.asw').read_text())
    model.reference[1]=[.7,.2,-.4];model.reference[2]=[.3,-.2,.4]
    condition=None if extra is None else FlightCondition(speed=20,alpha=3,mach=.1,
        rates=[.003,-.002,.001],**extra)
    return StaticNetwork(model,4,condition,None,[],operating_constraints=time_load_constraints(frame,targets))


@pytest.mark.parametrize('example,extra,frame,targets',CASES)
def test_initial_matrix_local_rows_global_wrenches_and_complete_border(example,extra,frame,targets):
    net=network(example,extra,frame,targets)
    x=np.random.default_rng(435).normal(0,.0001,net.size)
    x[net.gamma_start:net.operating_start]+=.04
    before=net.residual(x,.6).copy()
    # Exercise the grouped mechanical fallback before checking the current
    # direct blocks below. With direct mechanics, some small meshes have no
    # remaining disjoint geometry columns and therefore no grouping savings.
    grouped,counts=jacobian(net,x,.6,direct_circulation=False,direct_mechanics=False)
    individual,reference=jacobian(net,x,.6,grouped=False,direct_circulation=False,direct_mechanics=False)
    np.testing.assert_allclose(grouped.toarray(),individual.toarray(),atol=2e-8,rtol=1e-9)
    assert counts['evaluations']<reference['evaluations']
    assert net.iteration_fields is None and net.tangent_influences is None
    np.testing.assert_array_equal(net.residual(x,.6),before)
    # Check direct circulation and all acceleration columns independently in
    # the original full fields, including unscaled global rows at continuation.
    direct,counts=jacobian(net,x,.6)
    if net.ng:assert counts['circulation_derivative']=='direct fixed-geometry blocks'
    for j in range(net.gamma_start,net.size):
        h=1e-6*max(1.,abs(x[j]));plus=x.copy();minus=x.copy();plus[j]+=h;minus[j]-=h
        expected=(net.residual(plus,.6)-net.residual(minus,.6))/(2*h)
        np.testing.assert_allclose(direct.toarray()[:,j],expected,rtol=3e-6,atol=3e-7)
    rhs=np.random.default_rng(91).normal(size=net.size)
    np.testing.assert_allclose(block_solve(direct,rhs),np.linalg.solve(direct.toarray(),rhs),rtol=2e-7,atol=2e-7)
    # At zero external load the exact full matrix is triangular. Both diagonal
    # blocks retain the complete original operator; only the lower left lags.
    x=np.zeros(net.size);x[net.gamma_start:net.operating_start]=.04
    zero,_=jacobian(net,x,0.,direct_circulation=False);full=net.jacobian(x,0.)
    split=net.gamma_start
    np.testing.assert_array_equal(zero.mechanical.toarray(),full[:split,:split])
    np.testing.assert_array_equal(zero.force_circulation,full[:split,split:])
    np.testing.assert_array_equal(zero.circulation,full[split:,split:])
    assert not np.any(zero.force_circulation)
    assert check_initial_rank(net,x)['method']=='block-triangular rank certificate'


@pytest.mark.parametrize('case',['free','mixed','powered','posed','vacuum','flow'])
def test_initial_state_and_response_match_original_unsteady_equations(monkeypatch,case):
    from openswing.inertia import Motion
    name={'powered':'powered','posed':'wing-body','vacuum':'guided-body'}.get(case,'transient-wing')
    model=parse_asw(Path('examples/'+name+'.asw').read_text())
    args=dict(panels=4,duration=.02,dt=.01,frame='free')
    if case=='vacuum':
        args.update(motion=Motion(rates=[.2,-.3,.4]),gravity=[.3,-.4,-2],position=[1,2,3],attitude=[13,-7,21])
    else:
        extra=dict(ground_effect=1,position_earth=[0,0,30],attitude=[13,-7,21]) if case=='posed' else {}
        args['condition']=FlightCondition(speed=20,alpha=3,mach=.1,rates=[.003,-.002,.001],**extra)
    if case=='mixed':args.update(frame='mixed',load_targets={'force.x':.1,'moment.y':.2},forcing='time Fx My Ay\n0 .3 .4 .2\n.02 .5 .6 .4')
    if case=='powered':args['forcing']='time E1 Fx\n0 7 .1\n.02 9 .2'
    if case=='flow':
        from dataclasses import replace
        args['condition']=replace(args['condition'],speed=18,alpha=-2,beta=4,
                                  position_earth=[3,4,5],attitude=[11,-9,7])
    used=[]
    import openswing.structured_static as module
    original=module.equilibrate
    def track(*a,**kw):
        result=original(*a,**kw);used.append(True);return result
    monkeypatch.setattr(module,'equilibrate',track)
    actual=time.solve_time(model,**args)
    assert used
    def dense(net,options,tolerance,continuation_steps,progress=None):
        return _equilibrate_full(net,min(tolerance,1e-12),continuation_steps,**options)
    monkeypatch.setattr(time,'initial_equilibrium',dense)
    expected=time.solve_time(model,**args)
    assert actual['accepted_steps']==expected['accepted_steps']==2
    assert actual['rejected_steps']==expected['rejected_steps']==0
    for a,b in zip(actual['snapshots'],expected['snapshots']):
        assert a['residual']<=1e-8
        for key in ['force','moment','support_force','support_moment','local_velocity','local_acceleration','circulation_rate']:
            if key in b:np.testing.assert_allclose(a[key],b[key],rtol=2e-6,atol=3e-7,err_msg=case+'/'+key)
        np.testing.assert_allclose([n['position'] for n in a['nodes']],[n['position'] for n in b['nodes']],atol=2e-9,rtol=1e-9)
        for key in ['position_earth','body_to_earth','velocity_origin_body','rates_body','acceleration_reference_body','angular_acceleration_body']:
            np.testing.assert_allclose(a['frame'][key],b['frame'][key],atol=3e-8,rtol=2e-7,err_msg=case+'/'+key)
        for aa,bb in zip(a['operating_constraints'],b['operating_constraints']):
            assert aa['quantity']==bb['quantity'] and aa['target']==bb['target']
            assert abs(aa['normalized_residual'])<=1e-8


def test_initial_override_preserves_original_unknown_coordinates_and_scales():
    from openswing.inertia import Motion
    model=parse_asw(Path('examples/inertial.asw').read_text())
    condition=FlightCondition(speed=20,alpha=3,mach=.1,acceleration=[.3,.4,.5],
                              angular_acceleration=[.01,.02,.03])
    constraints=time_load_constraints('free')
    n=StaticNetwork(model,4,condition,None,[],operating_constraints=constraints)
    reference=StaticNetwork(model,4,condition,None,[],operating_constraints=constraints)
    base,scale=n.operating.base.copy(),n.operating.scale.copy()
    z=np.zeros_like(n.rj)
    options=dict(elastic_motion=(z,z,z,z),circulation_rate=np.zeros(n.circulation_basis.panels),
        condition_override=FlightCondition(speed=17,alpha=-2,beta=6,mach=.1,
                                           position_earth=[3,4,5],attitude=[11,-9,7]),
        motion_override=Motion(rates=[.03,-.02,.01],acceleration=[3,4,5],angular_acceleration=[.1,.2,.3]),
        gravity_override=np.array([.3,-.4,-2]),operating_targets={'force.x':.1,'moment.y':.2})
    actual,_=time.initial_equilibrium(n,options,1e-8,4)
    expected,_=_equilibrate_full(reference,1e-12,4,**options)
    assert n.operating.base==base and n.operating.scale==scale
    np.testing.assert_allclose(actual,expected,rtol=1e-8,atol=2e-9)
    assert np.max(abs(n.residual(actual,**options)))<=1e-8


def test_large_linear_frame_acceleration_does_not_require_artificial_unit_steps():
    from test_time_integration import rigid_body
    from openswing.network import equilibrate,network_result
    net=StaticNetwork(rigid_body(),4,None,[0,0,0],
        [dict(beam=1,t=0,force=[1000,0,0],moment=[0,0,4000])],
        operating_constraints=time_load_constraints('free'))
    x,steps=equilibrate(net)
    result=network_result(net,x)
    assert steps==4 and len(net.structured_iterations)<=8
    assert result['residual']<=1e-12
    # m=1 and Izz=4 in consistent SI units; no translational/rotational motion.
    np.testing.assert_allclose([result['operating_values']['acceleration.'+a] for a in 'xyz'],[1000,0,0],atol=1e-7)
    np.testing.assert_allclose([result['operating_values']['angular_acceleration.'+a] for a in 'xyz'],[0,0,1000],atol=1e-7)


@pytest.mark.parametrize('failure',['missing_inertia','redundant_ground','unrestrained_rotation'])
def test_initial_free_frame_still_rejects_missing_mass_or_mechanisms(failure):
    from test_time_integration import rigid_body
    model=rigid_body()
    if failure=='missing_inertia':model.records['weight'][0][11]=0
    elif failure=='redundant_ground':model.records['ground']*=2
    else:model.records['ground'][0][2]=1
    net=StaticNetwork(model,4,None,[0,0,0],[],operating_constraints=time_load_constraints('free'))
    with pytest.raises(AnalysisError,match='mechanism or redundant'):
        check_initial_rank(net,np.zeros(net.size))
