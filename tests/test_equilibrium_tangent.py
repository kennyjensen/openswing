"""The final corrected equilibrium block is the same physical Bode derivative."""
from copy import copy
from pathlib import Path
import numpy as np
import pytest
from openswing.asw import parse_asw
from openswing.aero import FlightCondition
from openswing.linear_dynamics import make_system,linearize
from openswing.frequency_response import FrequencyAnalysis


CASES=[('rectangular','fixed',{}),('flexible','free',{'circulation_modes':{1:3}}),
       ('wing-body','fixed',{'ground_effect':1}),('wing-body','mixed',{}),
       ('wing-body','free',{'freeze_influences':True}),('powered','free',{'powers':{1:7}})]


@pytest.mark.parametrize('example,frame,extra',CASES)
def test_warm_equilibrium_block_is_reused_without_changing_full_pencil(example,frame,extra):
    model=parse_asw(Path('examples',example+'.asw').read_text())
    condition=FlightCondition(speed=20,alpha=3,beta=2,mach=.1,position_earth=[0,0,30],
                              attitude=[13,-7,21],rates=[.003,-.002,.001],**extra)
    options=dict(frame=frame,load_targets={'force.z':0} if frame=='mixed' else None)
    panels=8 if example=='wing-body' else 4
    base,_=make_system(model,condition,panels,structured_base=True,**options)
    events=[]
    analysis=FrequencyAnalysis(model,condition,panels,inputs=[dict(kind='gust',name='gust')],
        initial_state=base.equilibrium_state,progress=lambda *args:events.append(args),**options)
    system=analysis.system;n=system.network
    assert system.state_derivative_diagnostics['equilibrium_columns_reused']==n.size
    assert any(e[0]=='equilibrium_reuse' for e in events)
    assert analysis.template['base']['equilibrium_initialization']['final_tangent'].startswith('provided physical tangent')
    before=n.nfev
    a,m=linearize(system,sparse=system.size>256)
    reused_calls=n.nfev-before
    system._equilibrium_tangent=None
    before=n.nfev
    original,original_m=linearize(system,sparse=system.size>256)
    assert n.nfev-before>reused_calls
    dense=lambda v:v.toarray() if hasattr(v,'toarray') else v
    np.testing.assert_allclose(dense(a),dense(original),atol=2e-10,rtol=2e-10)
    np.testing.assert_allclose(dense(m),dense(original_m),atol=3e-12,rtol=3e-12)
    result=analysis.solve([.3,3.7])
    assert result['converged']
    # Same complete physical output recovery with the independently rebuilt A/M.
    analysis.a,analysis.m=original,original_m
    expected=analysis.solve([.3,3.7])
    for actual,reference in zip(result['samples'],expected['samples']):
        for value,other in zip(actual['responses'],reference['responses']):
            for part in ('real','imag'):
                np.testing.assert_allclose(value['state'][part],other['state'][part],atol=2e-9,rtol=2e-8)
                np.testing.assert_allclose(value['output']['global']['force'][part],
                    other['output']['global']['force'][part],atol=2e-8,rtol=2e-8)


def retained_system():
    model=parse_asw(Path('examples/rectangular.asw').read_text());condition=FlightCondition(speed=20,mach=.1)
    base,_=make_system(model,condition,4,structured_base=True)
    system,_=make_system(model,condition,4,structured_base=True,initial_state=base.equilibrium_state,
                        _retain_equilibrium_tangent=(1e-5,lambda size:True))
    return system


def test_matrix_ownership_step_and_physical_changes_invalidate_reuse():
    system=retained_system();packet=system._equilibrium_tangent;n=system.network
    assert packet.matches(system,1e-5,True)
    assert not packet.matches(copy(system),1e-5,True)
    assert not packet.matches(system,3e-6,True)
    assert not packet.matches(system,1e-5,False)
    for values,index,delta in [(system.base,0,1e-8),(n.S,(0,0,0),1e-8),
        (n.gravity,2,.1),(n.model.reference,(1,0),.1),(system.Q0,(0,0,0),1e-8),
        (n.damping_times,(0,0),.01)]:
        original=values[index];values[index]=original+delta
        assert not packet.matches(system,1e-5,True)
        values[index]=original
        assert packet.matches(system,1e-5,True)
    speed=n.condition.speed;n.condition.speed+=1
    assert not packet.matches(system,1e-5,True)
    n.condition.speed=speed
    assert packet.matches(system,1e-5,True)
    with pytest.raises(ValueError):packet.matrix.data[0]=99
    original=packet.matrix.copy();a,_=linearize(system,sparse=True)
    a.data[:]=99
    np.testing.assert_array_equal(packet.matrix.toarray(),original.toarray())


def test_changed_difference_step_rebuilds_every_equilibrium_column():
    system=retained_system()
    a,m=linearize(system,3e-6,sparse=True)
    assert system.state_derivative_diagnostics['equilibrium_columns_reused']==0
    system._equilibrium_tangent=None
    expected,mass=linearize(system,3e-6,sparse=True)
    np.testing.assert_array_equal(a.toarray(),expected.toarray())
    np.testing.assert_array_equal(m.toarray(),mass.toarray())


@pytest.mark.parametrize('sparse',[False,True])
def test_absolute_rotation_rank_map_uses_spatial_derivatives_at_large_rotation(sparse):
    from test_network import model,beam
    from openswing.network import solve_static
    from openswing.equilibrium_tangent import retain_for_rank
    aircraft=model(beam(stiffness='100 0 0 0 0 0'))
    options=dict(gravity=[0,0,0],loads=[dict(beam=1,t=2,moment=[70,0,0])])
    base=solve_static(aircraft,panels=6,**options)
    system,_=make_system(aircraft,panels=6,initial_state=base['equilibrium_state'],**options)
    n=system.network;x=system.base
    actual=retain_for_rank(system,x,1e-5,sparse=sparse)
    if sparse:
        from scipy.sparse import issparse
        assert issparse(actual)
        actual=actual.toarray()
    zero=np.zeros(system.size);_,_,residual_options=system.physical_state(zero,zero)
    for j in range(6*n.nn):
        h=3e-6*max(1.,abs(x[j]));delta=np.zeros(n.size);delta[j]=h
        p,m,pp,mm=[n.residual(x+sign*delta,**residual_options) for sign in (1,-1,2,-2)]
        np.testing.assert_allclose(actual[:,j],(8*(p-m)-(pp-mm))/(12*h),atol=3e-9,rtol=3e-9)


def test_saved_unloaded_mechanism_cannot_bypass_final_rank_check():
    from test_network import model,beam
    from openswing.network import StaticNetwork
    from openswing.equilibrium_state import capture
    from openswing.aero import AnalysisError
    aircraft=model(beam(),attachments='Ground\n1 0 1\nEnd\n')
    network=StaticNetwork(aircraft,4,None,[0,0,0],[])
    saved=capture(network,np.zeros(network.size))
    with pytest.raises(AnalysisError,match='singular'):
        make_system(aircraft,panels=4,gravity=[0,0,0],initial_state=saved,
                    _retain_equilibrium_tangent=(1e-5,lambda size:True))
