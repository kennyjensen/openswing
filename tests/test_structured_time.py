"""Grouped BDF support, dense controls and physical time-response comparisons."""
from pathlib import Path
import numpy as np
import pytest
from openswing.asw import parse_asw
from openswing.aero import FlightCondition
from openswing.network import StaticNetwork
from openswing.time_integration import TimeSystem, bdf_coefficients
from openswing.structured_time import jacobian, Factorization


def setup(example,extra=None,panels=4,*,constraints=(),frame='prescribed'):
    model=parse_asw(Path(f'examples/{example}.asw').read_text())
    condition=FlightCondition(speed=20,alpha=3,mach=.1,**(extra or {}))
    network=StaticNetwork(model,panels,condition,None,[],operating_constraints=constraints)
    system=TimeSystem(network)
    velocity=-condition.speed*condition.vectors()[0]-np.cross(network.motion.rates,model.reference[3])
    previous,_,_=system.initial(position=condition.position_earth,attitude=condition.attitude,
        velocity=velocity,tolerance=1e-8,continuation_steps=4,frame=frame)
    coefficients=bdf_coefficients(.017,.013)
    # A real two-step stencil, deformed initial geometry and nonzero trial rates.
    older=previous
    values=system.guess(previous,.017)
    values+=np.random.default_rng(78).normal(0,1e-5,len(values))
    function=lambda x:system.residual(x,previous,older,.017,coefficients)
    return system,function,values


@pytest.mark.parametrize('example,extra',[
    ('flexible',{}),('wing-body',{}),('powered',{'powers':{1:30}}),
    ('articulated',{}),('transient-wing',{}),
    ('flexible',{'circulation_modes':{1:3}}),
    ('wing-body',{'ground_effect':1,'position_earth':[0,0,30],
                  'attitude':[13,-7,21],'rates':[.003,-.002,.001]}),
])
def test_grouped_matrix_covers_entire_lagged_bdf_linearization(example,extra):
    system,function,x=setup(example,extra)
    before=function(x).copy()
    matrix,permutation,counts=jacobian(system,function,x)
    dense,reference_permutation,reference_counts=jacobian(system,function,x,grouped=False)
    np.testing.assert_array_equal(permutation,reference_permutation)
    np.testing.assert_allclose(matrix.toarray(),dense.toarray(),rtol=1e-9,atol=2e-8)
    assert counts['evaluations']<reference_counts['evaluations']
    assert counts['matrix_storage_bytes'] < 8*system.size**2
    np.testing.assert_array_equal(function(x),before)
    assert system.network.iteration_fields is None and system.network.tangent_influences is None
    # Circulation (including its BDF derivative) and every frame column retain
    # the full physical tangent, independent of the local lagged approximation.
    split=matrix.mechanical.shape[0]
    for j,column in enumerate(permutation[split:]):
        h=1e-6*max(1.,abs(x[column]));trial=x.copy();trial[column]+=h
        expected=(function(trial)-before)[permutation]/h
        actual=np.r_[matrix.force_circulation[:,j],matrix.circulation[:,j]]
        np.testing.assert_allclose(actual,expected,rtol=1e-8,atol=2e-8)
    rhs=np.random.default_rng(91).normal(size=system.size)
    delta=Factorization(matrix,permutation).solve(rhs)
    expected=np.linalg.solve(matrix.toarray(),rhs[permutation])
    np.testing.assert_allclose(delta[permutation],expected,rtol=2e-7,atol=2e-7)


def test_failed_capture_restores_original_physics():
    from openswing.structured_time import linearization
    system,function,x=setup('flexible')
    before=function(x).copy()
    with pytest.raises(RuntimeError,match='deliberate'):
        with linearization(system,function,x):raise RuntimeError('deliberate')
    assert system.network.iteration_fields is None and system.network.tangent_influences is None
    np.testing.assert_array_equal(function(x),before)


def test_zero_rate_base_retains_new_apparent_mass_velocity_terms():
    system,function,x=setup('transient-wing')
    x[system.network.size:system.frame_start]=0
    x[system.frame_start+3:system.frame_start+6]=0
    before=function(x).copy()
    matrix,permutation,_=jacobian(system,function,x)
    np.testing.assert_array_equal(function(x),before)
    inverse=np.argsort(permutation);dense=matrix.toarray()
    for column in range(system.network.size,system.frame_start):
        trial=x.copy();trial[column]+=1e-6
        expected=(function(trial)-before)[permutation]/1e-6
        np.testing.assert_allclose(dense[:,inverse[column]],expected,atol=2e-8,rtol=1e-9)


@pytest.mark.parametrize('case',['flap','engine','release','spin'])
def test_complete_response_matches_original_dense_newton(monkeypatch,case):
    from openswing.time_integration import solve_time
    from openswing.inertia import Motion
    from test_time_integration import oscillator,rigid_body
    import openswing.structured_time as module
    if case=='flap':
        model=parse_asw(Path('examples/transient-wing.asw').read_text())
        args=dict(condition=FlightCondition(speed=20,alpha=3,mach=0),
                  forcing='time +F1\n0 0\n.015 0\n.015 1\n.03 1')
    elif case=='engine':
        model=parse_asw(Path('examples/powered.asw').read_text())
        args=dict(condition=FlightCondition(speed=20,alpha=3,mach=0),
                  forcing='time E1\n0 5\n.03 7')
    elif case=='release':
        model=oscillator(.02);args=dict(gravity=[0,0,0],initial_loads=[dict(beam=1,t=2,force=[0,1,0])])
    else:
        model=rigid_body();args=dict(gravity=[0,0,0],motion=Motion(rates=[.2,.3,4],angular_acceleration=[.1,-.2,.3]))
    # Compare the two algorithms after resolving the dimensional balance
    # defects to the accuracy asserted below. At the default 1e-8 scaled
    # residual, both can stop with force defects larger than the 2e-6 N
    # comparison limit; this also occurs without linear-solve refinement.
    args['tolerance']=1e-10
    used=[];original=module.jacobian
    def track(*a,**kw):
        result=original(*a,**kw);used.append(result[2]);return result
    monkeypatch.setattr(module,'jacobian',track)
    actual=solve_time(model,panels=4,duration=.03,dt=.01,**args)
    assert used
    monkeypatch.setattr(module,'attach',lambda *args,**kwargs:None)
    expected=solve_time(model,panels=4,duration=.03,dt=.01,**args)
    assert actual['accepted_steps']==expected['accepted_steps']
    assert actual['rejected_steps']==expected['rejected_steps']==0
    for a,b in zip(actual['snapshots'],expected['snapshots']):
        assert a['time']==b['time'] and a['residual']<=args['tolerance']
        for key in ['force','moment','support_force','support_moment','local_velocity',
                    'local_rates','local_acceleration','circulation_rate',
                    'force_balance','moment_balance','applied_force','applied_moment']:
            if key not in b:
                assert key not in a
                continue
            np.testing.assert_allclose(a[key],b[key],rtol=2e-6,atol=2e-6,err_msg=case+'/'+key)
        for key in ['position_earth','velocity_origin_body','body_to_earth','rates_body']:
            np.testing.assert_allclose(a['frame'][key],b['frame'][key],rtol=1e-8,atol=1e-9)
        np.testing.assert_allclose([n['position'] for n in a['nodes']],
                                   [n['position'] for n in b['nodes']],rtol=1e-8,atol=1e-8)


@pytest.mark.parametrize('failure',['assembly','solve','direction'])
def test_sparse_failure_uses_original_physical_tangent_before_rejecting_step(monkeypatch,failure):
    from openswing.time_integration import solve_time
    from test_time_integration import oscillator
    import openswing.structured_time as module
    calls=[]
    def broken(*args,**kwargs):
        calls.append(True)
        if failure=='direction':return np.zeros_like(args[1])
        raise ValueError('deliberately unavailable sparse solve')
    if failure=='assembly':monkeypatch.setattr(module,'jacobian',broken)
    else:monkeypatch.setattr(module.Factorization,'solve',broken)
    args=dict(panels=4,duration=.02,dt=.01,gravity=[0,0,0],initial_loads=[dict(beam=1,t=2,force=[0,1,0])])
    actual=solve_time(oscillator(.02),**args)
    assert calls and actual['rejected_steps']==0
    monkeypatch.setattr(module,'attach',lambda *args,**kwargs:None)
    expected=solve_time(oscillator(.02),**args)
    for a,b in zip(actual['snapshots'],expected['snapshots']):
        np.testing.assert_allclose(a['local_velocity'],b['local_velocity'],atol=1e-10)
        assert a['residual']<=1e-8


def test_general_inverse_and_controller_contexts_do_not_use_sparse_approximation():
    from openswing.structured_time import attach
    from openswing.operating import time_operating_constraints
    system,function,_=setup('flexible')
    system.feedback=object();attach(system,function)
    assert not hasattr(function,'factorization_builder')
    system.feedback=None;system.network.operating.constraints=time_operating_constraints('prescribed',
        actuator_constraints=[dict(variable='control.1',quantity='force.z',target=0)])
    attach(system,function)
    assert not hasattr(function,'factorization_builder')


def test_singular_local_block_is_rejected_before_sparse_lu(monkeypatch):
    from scipy.sparse import csc_matrix
    from openswing.structured_static import StructuredMatrix
    import openswing.structured_time as module
    def forbidden(*args,**kwargs):raise AssertionError('Singular pattern reached sparse LU')
    monkeypatch.setattr(module,'splu',forbidden)
    # The complete saddle-point matrix is nonsingular, but its chosen local
    # block is singular: the original dense fallback must own this case.
    matrix=StructuredMatrix(csc_matrix((1,1)),np.ones((1,1)),csc_matrix([[1.]]),np.zeros((1,1)))
    assert np.linalg.det(matrix.toarray())==-1
    with pytest.raises(ValueError,match='Structurally singular'):
        module.Factorization(matrix,np.arange(2))
