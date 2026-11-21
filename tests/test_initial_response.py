"""Initial spectra against ODE transforms and constrained descriptor mechanics."""
from copy import deepcopy
from pathlib import Path
import json
import numpy as np
import pytest
from openswing.asw import parse_asw
from openswing.aero import FlightCondition, AnalysisError
from openswing.frequency_response import solve_frequency_response, harmonic_solve
from openswing.initial_response import ConsistentSubspace, dynamic_state
from openswing.linear_dynamics import make_system
from openswing.geometry import model_meshes
from openswing.circulation import CirculationBasis
from test_time_integration import rigid_body


def z(value):return np.asarray(value['real'])+1j*np.asarray(value['imag'])


@pytest.mark.parametrize('amplitude', [1., 1e-12])
def test_hidden_constraints_complete_reactions_without_projecting_incompatible_motion(amplitude):
    a=np.array([[0,0,1,0,0],[0,0,0,1,0],[-18,7,-.4,0,1],[7,-24,0,-.8,-1],[1,-1,0,0,0]],float)
    m=np.diag([1.,1.,2.,3.,0.]);space=ConsistentSubspace(a,m,[0,1,2,3])
    initial,rate,checks=space.complete(amplitude*np.array([.01,.01,.02,.02,0]))
    np.testing.assert_allclose(initial/amplitude,[.01,.01,.02,.02,-.0036],atol=1e-14)
    np.testing.assert_allclose(rate[:4]/amplitude,[.02,.02,-.0608,-.0608],atol=1e-14)
    assert space.report['finite_dimension']==2 and checks['dynamic_coordinate_mismatch']<1e-13
    with pytest.raises(AnalysisError,match='violates algebraic or hidden'):
        space.complete(amplitude*np.array([.01,.011,.02,.02,0]))


def test_integrator_chain_keeps_initial_value_subtraction_and_time_units():
    for seconds_per_unit in (1.,.001):
        a=np.array([[0.,seconds_per_unit],[0.,0.]]);m=np.eye(2)
        space=ConsistentSubspace(a,m,[0,1],time_scale=seconds_per_unit)
        initial,rate,_=space.complete(np.array([2.,3.]));np.testing.assert_allclose(rate,[3*seconds_per_unit,0],atol=1e-15)
        shift=.7*seconds_per_unit;omega=2*seconds_per_unit;s=shift+1j*omega
        response,checks=harmonic_solve(a,m,m@initial,omega,shift=shift)
        np.testing.assert_allclose(response,[2/s+3*seconds_per_unit/s**2,3/s],rtol=1e-14)
        np.testing.assert_allclose(s*response-initial,[3*seconds_per_unit/s,0],atol=1e-14)
        assert checks['backward_errors'][0]<1e-14


@pytest.fixture(scope='module')
def oscillator():
    model=parse_asw(Path('examples/instrumented-oscillator.asw').read_text())
    inputs=json.loads(Path('examples/initial-spring.json').read_text())
    original=deepcopy(inputs)
    result=solve_frequency_response(model,FlightCondition(alpha=0,mach=0),4,frequencies=[0,1,10,30,100],
        inputs=['power.1',*inputs],gravity=[0,0,0],matrices=True)
    assert inputs==original
    return model,result


def test_initial_displacement_velocity_acceleration_and_damping_boundary_terms(oscillator):
    _,out=oscillator
    assert out['diagnostics']['initial_conditions']['spectral_abscissa']==pytest.approx(-2.5,abs=1e-8)
    for sample in out['samples']:
        s=1j*sample['omega'];denominator=2*s*s+10*s+500
        for i,(q0,v0) in enumerate(((.002,0),(0,.01)),1):
            response=sample['responses'][i];o=response['output'];q=((2*s+10)*q0+2*v0)/denominator
            velocity=s*q-q0;acceleration=s*velocity-v0
            assert z(o['nodes'][-1]['displacement'])[1]==pytest.approx(q,abs=1e-12)
            assert z(o['nodes'][-1]['velocity'])[1]==pytest.approx(velocity,abs=1e-12)
            assert z(o['sensors'][-1]['acceleration_sensor'])[1]==pytest.approx(acceleration,abs=3e-10)
            assert z(o['sections'][-1]['force_local'])[1]==pytest.approx(500*q+10*velocity,abs=3e-10)
            assert z(o['global']['applied_force'])[1]==pytest.approx(-2*acceleration,abs=3e-10)
            np.testing.assert_allclose(z(o['global']['applied_force'])+z(o['global']['support_force']),0,atol=3e-10)
            initial=np.array(out['inputs'][i]['resolved_state'])
            np.testing.assert_allclose(z(response['state_rate']),s*z(response['state'])-initial,atol=1e-15)
            np.testing.assert_allclose(np.array(out['matrices']['M'])@initial,z(sample['B'])[:,i],atol=1e-15)
            assert not response['broken_loop']['available'] and out['inputs'][i]['output_time_power']==1
        # Adding initial channels does not change the periodic unit-force transfer.
        assert z(sample['responses'][0]['output']['nodes'][-1]['displacement'])[1]==pytest.approx(1/denominator,abs=1e-12)
    json.dumps(out,allow_nan=False)


def test_initial_output_contains_completed_physical_loads_and_sensor_acceleration(oscillator):
    _,out=oscillator
    for i,(q,v) in enumerate(((.002,0),(0,.01)),1):
        o=out['inputs'][i]['initial_output']
        assert z(o['nodes'][-1]['displacement'])[1]==pytest.approx(q,abs=1e-12)
        assert z(o['nodes'][-1]['velocity'])[1]==pytest.approx(v,abs=1e-12)
        assert z(o['sections'][-1]['force_local'])[1]==pytest.approx(500*q+10*v,abs=1e-10)
        assert z(o['sensors'][-1]['acceleration_sensor'])[1]==pytest.approx(-(500*q+10*v)/2,abs=1e-10)


def test_free_flight_initial_spectrum_survives_a_simultaneous_periodic_dc_gap():
    m=parse_asw(rigid_body().dumps()+'\nEngine\n1 0 1 0 0 0 0 1 0 0 1 0 -1 0 0\nEnd\n')
    initial=dict(kind='initial',state=dict(frame=dict(velocity_origin_body=[1,0,0])))
    out=solve_frequency_response(m,FlightCondition(alpha=0,mach=0),4,frame='free',gravity=[0,0,0],
        frequencies=[0,2],inputs=['power.1',initial],initial_shift=.7)
    assert not out['converged'];dc=out['samples'][0]
    assert dc['resolved_inputs']==1 and not dc['responses'][0]['converged'] and dc['responses'][1]['converged']
    for sample in out['samples']:
        s=.7+1j*sample['omega'];o=sample['responses'][1]['output']
        assert z(o['frame']['position_earth'])[0]==pytest.approx(1/s**2,abs=1e-8)
        assert z(o['frame']['velocity_origin_body'])[0]==pytest.approx(1/s,abs=1e-8)
        assert z(o['operating']['acceleration.x'])==pytest.approx(0,abs=1e-10)
    with pytest.raises(AnalysisError,match='no ordinary Fourier integral'):
        solve_frequency_response(m,FlightCondition(alpha=0,mach=0),4,frame='free',gravity=[0,0,0],frequencies=[2],inputs=[initial])


def test_initial_circulation_in_fourier_basis_recovers_section_lag():
    source=Path('examples/rectangular.asw').read_text().split('t dCLdF1')[0]+'End\n'
    source=source.replace('6 0 6 0','100000 0 100000 0').replace('6 .008','100000 .008').replace('.008','0').replace('12 1 12','200000 1 200000')
    m=parse_asw(source);c=FlightCondition(speed=30,alpha=0,mach=0,stall=False,circulation_modes={1:1})
    basis=CirculationBasis(model_meshes(m,8),{1:1});gamma=basis.decode(np.array([.1]))
    out=solve_frequency_response(m,c,8,frequencies=[0,5,30],inputs=[dict(kind='initial',state=dict(circulation=gamma.tolist()))],gravity=[0,0,0])
    for sample in out['samples']:
        actual=[z(row['circulation']) for row in sample['responses'][0]['output']['strips']]
        np.testing.assert_allclose(actual,gamma/(15+1j*sample['omega']),rtol=3e-4,atol=1e-10)


@pytest.mark.parametrize('kind', ['integral','lag'])
def test_controller_initial_integrals_and_custom_states_match_independent_odes(kind):
    m=parse_asw(Path('examples/instrumented-oscillator.asw').read_text())
    state=dict(beam_fields=[dict(beam=1,displacement=[[0,0,0,0],[2,0,.002,0]],velocity=[[0,0,0,0],[2,0,.01,0]])])
    if kind=='integral':
        controller=dict(commands={'RY[2]':2},outputs=[dict(actuator='E1',terms=[dict(input='RY[2]',gain=-200),dict(input='RY[2]',gain=-100,mode='integral')])])
        state['feedback']=dict(integrals={'RY[2]':.003});a=np.array([[0,1,0],[-350,-5,-50],[1,0,0.]])
        initial=np.array([.002,.01,.003]);key='integrals_RY[2]'
    else:
        controller=json.loads(Path('examples/actuator-lag-controller.json').read_text());controller['commands']={'RY[2]':2,'UY[2]':0}
        state['feedback']=dict(states={'lag':.1});a=np.array([[0,1,0],[-250,-5,.5],[-4000,-400,-20.]])
        initial=np.array([.002,.01,.1]);key='states_lag'
    out=solve_frequency_response(m,FlightCondition(speed=10,alpha=0,mach=0),4,frequencies=[0,5,30],initial_shift=.3,
        inputs=[dict(kind='initial',state=state)],gravity=[0,0,0],controller=controller)
    for sample in out['samples']:
        s=.3+1j*sample['omega'];exact=np.linalg.solve(s*np.eye(3)-a,initial);o=sample['responses'][0]['output']
        assert z(o['nodes'][-1]['displacement'])[1]==pytest.approx(exact[0],abs=1e-11)
        assert z(o['nodes'][-1]['velocity'])[1]==pytest.approx(exact[1],abs=1e-11)
        assert z(o['feedback'][key])==pytest.approx(exact[2],abs=1e-10)
        actuator=-200*exact[0]-100*exact[2] if kind=='integral' else exact[2]
        assert z(o['feedback']['actuators_E1'])==pytest.approx(actuator,abs=1e-10)
        if kind=='lag':assert z(o['feedback']['state_rates_lag'])==pytest.approx(s*exact[2]-initial[2],abs=1e-10)


@pytest.fixture(scope='module')
def system():
    m=parse_asw(Path('examples/instrumented-oscillator.asw').read_text())
    return make_system(m,FlightCondition(alpha=0,mach=0),4,gravity=[0,0,0])[0]


@pytest.mark.parametrize('state',[
    {'unknown':1}, {'nodes':{}}, {'nodes':[{'beam':1,'t':.17,'velocity':[0,1,0]}]},
    {'nodes':[{'beam':7,'t':0,'velocity':[0,1,0]}]}, {'nodes':[{'beam':1,'t':0,'velocity':[0,float('nan'),0]}]},
    {'frame':{'velocity_origin_body':[1,0,0]}}, {'feedback':{'integrals':{'V':1}}}, {'circulation':[1]},
    {'beam_fields':[{'beam':1,'velocity':[[.1,0,0,0],[2,0,1,0]]}]},
    {'nodes':[{'beam':1,'t':0,'velocity':[0,1,0]},{'beam':1,'t':0,'velocity':[0,2,0]}]},
])
def test_invalid_initial_physical_fields_are_rejected(system,state):
    with pytest.raises((AnalysisError,ValueError)):dynamic_state(system,state)


def test_nonzero_root_displacement_fails_constraints_even_at_tiny_amplitude(system):
    from openswing.linear_dynamics import linearize
    a,m=linearize(system);space=ConsistentSubspace(a,m,system.dynamic_indices,system.W)
    for amplitude in (1e-3,1e-12):
        requested=dynamic_state(system,dict(nodes=[dict(beam=1,t=0,displacement=[0,amplitude,0])]))
        with pytest.raises(AnalysisError,match='violates algebraic or hidden'):space.complete(requested)


def test_tiny_arbitrary_parameter_domain_does_not_match_a_different_initial_station(system):
    from copy import copy
    local=copy(system);local.network=copy(system.network)
    local.network.station_nodes={k:(ts*1e-20,ids.copy()) for k,(ts,ids) in system.network.station_nodes.items()}
    with pytest.raises(AnalysisError,match='not a node'):
        dynamic_state(local,dict(nodes=[dict(beam=1,t=.17e-20,velocity=[0,1,0])]))
    value=dynamic_state(local,dict(nodes=[dict(beam=1,t=2e-20,velocity=[0,1,0])]))
    assert np.count_nonzero(value)==1


@pytest.mark.parametrize('step,rank_tolerance', [(1e-5,1e-9),(1e-4,1e-12)])
def test_loaded_flexible_fourier_mode_initial_state_matches_modal_resolvent(step,rank_tolerance):
    from openswing.linear_dynamics import linearize,eigensystem
    from test_network import model,beam
    m=model(beam(stiffness='1000 0 0 0 0 0').replace('End','t mg chord Xax\n0 19.6133 1 .25\n2 19.6133 1 .25\nEnd'))
    c=FlightCondition(speed=10,alpha=4,mach=0,circulation_modes={1:3})
    system,_=make_system(m,c,4,gravity=[0,0,0]);n=system.network;a,mass=linearize(system,step=step)
    modes,_=eigensystem(a,mass,time_scale=system.W,count=4,rank_tolerance=rank_tolerance)
    mode=next(v for v in modes if abs(v['eigenvalue'][1])>1e-3)
    right=mode['right']*.001;initial=right.real;root=complex(*mode['eigenvalue'])
    coordinates=initial[:6*n.nn].reshape(n.nn,6)
    velocity,rates=initial[system.velocity_start:system.frame_start].reshape(2,n.nn,3)
    rows=[]
    for beam,(ts,ids) in n.station_nodes.items():
        for t,i in zip(ts,ids):rows.append(dict(beam=beam,t=float(t),displacement=(n.L*coordinates[i,:3]).tolist(),
            rotation=coordinates[i,3:].tolist(),velocity=(system.V*velocity[i]).tolist(),rates=(system.W*rates[i]).tolist()))
    gamma=n.circulation_basis.decode(initial[n.gamma_start:n.operating_start]*n.gamma_scale)
    out=solve_frequency_response(n.model,c,4,gravity=[0,0,0],frequencies=[0,5],initial_shift=100,
        inputs=[dict(kind='initial',state=dict(nodes=rows,circulation=gamma.tolist()))],step=step,initial_rank_tolerance=rank_tolerance)
    assert out['base']['max_displacement']>.01
    for sample in out['samples']:
        s=100+1j*sample['omega'];expected=.5*(right/(s-root)+right.conj()/(s-root.conjugate()))
        np.testing.assert_allclose(z(sample['responses'][0]['state']),expected,rtol=2e-6,atol=1e-10)
