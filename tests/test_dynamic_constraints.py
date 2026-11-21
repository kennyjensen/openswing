"""Mixed-frame modes and harmonic inputs against independent rigid mechanics."""
from pathlib import Path
import numpy as np
import pytest
from openswing.asw import parse_asw
from openswing.aero import FlightCondition
from openswing.inertia import Motion
from openswing.linear_dynamics import make_system,linearize,eigensystem
from openswing.frequency_response import HarmonicInput,solve_frequency_response


def body():return parse_asw(Path('examples/guided-body.asw').read_text())
def z(value):return np.asarray(value['real'])+1j*np.asarray(value['imag'])


@pytest.fixture(scope='module')
def simple_response():
    inputs=['target.force.x','acceleration.y','acceleration.z',
            'angular_acceleration.x','angular_acceleration.y','target.moment.z']
    return solve_frequency_response(body(),FlightCondition(10,alpha=0,mach=0),4,
        frame='mixed',load_targets={'force.x':0,'moment.z':0},gravity=[0,0,0],
        frequencies=[0,.7,3.],inputs=inputs,matrices=True)


def test_six_mixed_inputs_recover_force_inertia_kinematics_and_reactions(simple_response):
    result=simple_response
    assert result['frame_load_targets']=={'force.x':0,'moment.z':0}
    assert result['diagnostics']['state_layout']['frame']['width']==12
    assert not result['samples'][0]['converged']
    for sample in result['samples'][1:]:
        w=sample['omega']
        for j,response in enumerate(sample['responses']):
            out=response['output'];acc=np.zeros(3);angular=np.zeros(3)
            if j<3:acc[j]=[-1,1,1][j]
            else:angular[j-3]=[1,1,-.25][j-3]
            rates=angular/(1j*w)
            velocity=(acc-np.cross(rates,[-10,0,0]))/(1j*w)
            np.testing.assert_allclose(z(out['frame']['velocity_origin_body']),velocity,atol=2e-8)
            np.testing.assert_allclose(z(out['frame']['rates_body']),rates,atol=2e-8)
            np.testing.assert_allclose(z(out['frame']['position_earth']),-acc/w**2,atol=2e-8)
            np.testing.assert_allclose(z(out['frame']['attitude_rad']),-np.array([-1,1,-1])*angular/w**2,atol=2e-8)
            np.testing.assert_allclose(z(out['global']['applied_force']),-acc,atol=2e-8)
            np.testing.assert_allclose(z(out['global']['applied_moment']),-np.array([2,3,4])*angular,atol=2e-8)
            np.testing.assert_allclose(z(out['global']['support_force']),acc,atol=2e-8)
            np.testing.assert_allclose(z(out['global']['support_moment']),[2,3,4]*angular,atol=2e-8)
            a,m=(np.array(result['matrices'][k]) for k in ('A','M'))
            np.testing.assert_allclose((1j*w*m-a)@z(response['state']),z(sample['B'])[:,j],atol=2e-9)


@pytest.mark.parametrize('spin,targets,expected',[
    ([0,0,2],{'moment.x':0,'moment.y':0},2j/np.sqrt(3)),
    ([0,2,0],{'moment.x':0,'moment.z':0},2/np.sqrt(8)),
])
def test_mixed_rigid_modes_retain_nutation_and_intermediate_axis_instability(spin,targets,expected):
    system,_=make_system(body(),panels=4,frame='mixed',load_targets=targets,
                         motion=Motion(rates=spin),gravity=[0,0,0])
    a,m=linearize(system)
    modes,report=eigensystem(a,m,time_scale=system.W,count=20)
    values=np.array([complex(*mode['eigenvalue']) for mode in modes])
    assert report['finite_dimension']==12
    assert min(abs(values-expected))<1e-7 and min(abs(values+expected))<1e-7
    for mode in modes:
        assert mode['right_backward_error']<1e-9 and mode['left_backward_error']<1e-9


@pytest.fixture(scope='module')
def mixed_system():
    return make_system(body(),panels=4,frame='mixed',load_targets={'force.x':0},gravity=[0,0,0])[0]


@pytest.mark.parametrize('name,match',[
    ('target.force.y','active frame'),('target.moment.x','active frame'),
    ('acceleration.x','conflicts'),('angular_acceleration.q','xyz component'),
])
def test_inactive_or_conflicting_harmonic_frame_inputs_are_rejected(mixed_system,name,match):
    with pytest.raises(ValueError,match=match):HarmonicInput(mixed_system,name,0)


@pytest.mark.parametrize('frame,targets,match',[
    ('mixed',None,'at least one'),('fixed',{'force.x':0},'no load targets'),
    ('invalid',None,'fixed, prescribed, free or mixed'),('mixed',{'force.x':True},'finite numeric'),
])
def test_invalid_dynamic_frame_selection_fails_before_solving(frame,targets,match):
    with pytest.raises(ValueError,match=match):make_system(body(),frame=frame,load_targets=targets)


def test_fixed_frame_has_no_harmonic_frame_acceleration_input():
    system,_=make_system(body(),panels=4,gravity=[0,0,0])
    with pytest.raises(ValueError,match='free or mixed'):HarmonicInput(system,'acceleration.x',0)


def prescribed_request():
    return dict(action='frequency',source=body().dumps(),panels=4,gravity=[0,0,0],
        condition=dict(speed=10,alpha=0,mach=0),frequency=dict(frame='prescribed',frequencies=[.7,3.],
        inputs=[kind+'.'+axis for kind in ('acceleration','angular_acceleration') for axis in 'xyz']))


def compare_prescribed(result):
    assert result['frame_mode']=='prescribed' and result['frame_load_targets']=={}
    error=0.
    for sample in result['samples']:
        w=sample['omega']
        for j,response in enumerate(sample['responses']):
            out=response['output'];acc=np.zeros(3);angular=np.zeros(3)
            (acc if j<3 else angular)[j%3]=1
            rates=angular/(1j*w);velocity=(acc-np.cross(rates,[-10,0,0]))/(1j*w)
            error=max(error,float(np.max(abs(z(out['frame']['velocity_origin_body'])-velocity))))
            np.testing.assert_allclose(z(out['frame']['position_earth']),-acc/w**2,atol=2e-8)
            np.testing.assert_allclose(z(out['frame']['rates_body']),rates,atol=2e-8)
            np.testing.assert_allclose(z(out['global']['applied_force']),-acc,atol=2e-8)
            np.testing.assert_allclose(z(out['global']['applied_moment']),-np.array([2,3,4])*angular,atol=2e-8)
    assert error<2e-8
    return error


def test_all_prescribed_frame_inputs_retain_motion_and_inertial_reaction():
    from openswing.bridge import dispatch
    compare_prescribed(dispatch(prescribed_request()))


def offset_request(step=1e-5):
    m=body();m.reference[1:]=[[.7,.1,-.2],[.3,-.2,.4],[-.4,.2,.1]]
    return dict(action='frequency',source=m.dumps(),panels=4,gravity=[0,0,0],
        condition=dict(speed=10,alpha=6,beta=-4,mach=0,rates=[.2,-.3,.4],
                       acceleration=[0,.7,0],angular_acceleration=[.1,0,-.2],attitude=[17,-23,31]),
        loads=[dict(beam=1,t=0,force=[1,2,3],moment=[.2,-.1,.3])],
        frequency=dict(frame='mixed',load_targets={'force.x':.4,'force.z':-.7,'moment.y':.2},
            inputs=['target.force.x','acceleration.y','target.force.z',
                    'angular_acceleration.x','target.moment.y','angular_acceleration.z'],
            frequencies=[.7,3.],step=step))


def compare_offset(result):
    from rigid_frame_reference import harmonic,acceleration
    alpha,beta=np.deg2rad([6,-4]);omega=np.array([.2,-.3,.4]);rv=np.array([-.4,.2,.1])
    velocity=-10*np.array([np.cos(alpha)*np.cos(beta),-np.sin(beta),np.sin(alpha)*np.cos(beta)])-np.cross(omega,rv)
    state=np.r_[velocity,omega,np.zeros(3),np.deg2rad([17,-23,31])]
    exact=harmonic(state,[s['omega'] for s in result['samples']]);error=0.
    base_a,base_f=acceleration(omega,np.zeros(6))
    np.testing.assert_allclose(result['base']['applied_force'],base_f[:3],atol=2e-8)
    np.testing.assert_allclose(result['base']['applied_moment'],base_f[3:],atol=2e-8)
    for sample,reference in zip(result['samples'],exact):
        for j,response in enumerate(sample['responses']):
            output=response['output'];f=output['frame']
            actual=np.concatenate([z(f[key]) for key in ('velocity_origin_body','rates_body','position_earth','attitude_rad')])
            error=max(error,float(np.max(abs(actual-reference['state'][:,j]))))
            np.testing.assert_allclose(actual,reference['state'][:,j],atol=2e-7,rtol=2e-8)
            force=np.r_[z(output['global']['applied_force']),z(output['global']['applied_moment'])]
            np.testing.assert_allclose(force,reference['wrench'][:,j],atol=2e-7,rtol=2e-8)
            for key,i in [('acceleration.x',0),('acceleration.z',2),('angular_acceleration.y',4)]:
                np.testing.assert_allclose(z(output['operating'][key]),reference['acceleration'][i,j],atol=2e-7,rtol=2e-8)
    return error


@pytest.mark.parametrize('step',[1e-5,3e-6])
def test_frozen_harmonic_reference_offsets_rotation_and_nonzero_targets(step):
    from openswing.bridge import dispatch
    compare_offset(dispatch(offset_request(step)))


def feedback_setup():
    m=parse_asw(body().dumps()+'\nEngine\n1 0 1 0 0 0 0 1 0 0 1 0 -1 0 0\nEnd\n')
    control=dict(commands={'V':8},outputs=[dict(actuator='E1',terms=[dict(input='V',
        gain=dict(speed=[5,15],density=[0],values=[[2.5,3.5]]))])])
    return m,FlightCondition(10,alpha=0,mach=0),dict(frame='mixed',load_targets={'force.x':.4},
        controller=control,gravity=[0,0,0])


def test_mixed_feedback_target_and_command_transfers_retain_schedule_derivative():
    m,c,options=feedback_setup()
    result=solve_frequency_response(m,c,4,frequencies=[.7,3.],
        inputs=['target.force.x','command.V'],**options)
    assert result['base']['feedback']['actuators']['E1']==pytest.approx(6,abs=1e-8)
    assert result['base']['operating_values']['acceleration.x']==pytest.approx(5.6,abs=1e-8)
    for sample in result['samples']:
        s=1j*sample['omega']
        for j,response in enumerate(sample['responses']):
            out=response['output'];v=(1 if j==0 else 3)/(s+3.2)
            assert z(out['frame']['velocity_origin_body'])[0]==pytest.approx(-v,abs=3e-8)
            assert z(out['feedback']['measurements_V'])==pytest.approx(v,abs=3e-8)
            assert z(out['global']['applied_force'])[0]==pytest.approx(1 if j==0 else 0,abs=3e-8)


def test_mixed_frame_rom_keeps_selected_decay_and_direct_load_response():
    from openswing.reduced_model import solve_reduced_model
    from openswing.rom_file import export_rom,parse_rom,rom_response
    m,c,options=feedback_setup()
    # The stable speed mode is nearest this shift; the omitted zero modes
    # govern position and attitude, not these speed/acceleration outputs.
    result=solve_reduced_model(m,c,4,count=1,shift=(-3.2,0),inputs=['target.force.x'],
        outputs=['V','Ax'],frequencies=[.7,3.],**options)
    assert result['diagnostics']['dimension']==1
    for sample in result['samples']:
        s=1j*sample['omega'];expected=np.array([[1/(s+3.2)],[-s/(s+3.2)]])
        np.testing.assert_allclose(z(sample['full']),expected,atol=5e-8)
        np.testing.assert_allclose(z(sample['reduced']),expected,atol=5e-8)
    saved=parse_rom(export_rom(result,m.units,m.name))
    assert saved['inputs'][0]['unit']=='N'


def test_angular_acceleration_rom_input_converts_minutes_to_si_transfer():
    from openswing.asw import UnitSystem
    from openswing.rom_file import export_rom,parse_rom,rom_response
    # omega_dot=-2 omega+alpha, time in minutes, omega output in deg/min.
    result=dict(inputs=[dict(name='angular_acceleration.y',unit='rad/input T^2')],
        outputs=[dict(name='Wy',unit='deg/input T')],matrices=dict(A=[[-2]],B=[[1]],
        C=[[180/np.pi]],D=[[0]],D_rate=[[0]]),diagnostics=dict(retained=[dict(coordinates=[0],eigenvalue=[-2,0],source_index=0)]))
    units=UnitSystem({'L':(1.,'m'),'T':(60.,'s'),'F':(1.,'N')})
    model=parse_rom(export_rom(result,units));assert model['inputs'][0]['unit']=='rad/s^2'
    for sample in rom_response(model,[0,.3,3.])['samples']:
        assert z(sample['response'])[0,0]==pytest.approx((180/np.pi)/(1/30+1j*sample['omega']),rel=1e-12)
