from dataclasses import replace
import json
from pathlib import Path
import numpy as np
import pytest
from scipy.integrate import quad_vec
from openswing.asw import parse_asw
from openswing.aero import FlightCondition, solve_rigid, evaluate_aerodynamics
from openswing.geometry import mesh_beam
from openswing.ground import body_to_earth
from openswing.inertia import Motion
from openswing.local_motion import LocalMotion, rotation_matrix as exp
from openswing.sensors import sensor_axes, sensor_euler, measure_sensor
from openswing.network import solve_static, StaticNetwork, network_result
from openswing.time_integration import solve_time
from openswing.linear_dynamics import solve_modes
from openswing.frequency_response import solve_frequency_response
from test_network import model, beam
from test_time_integration import rigid_body, oscillator
from test_volume import body_source
from test_propulsion import engine


def with_sensor(configuration, rows='1 1 2 .3 2 .2'):
    return parse_asw(configuration.dumps()+'\nSensor\n'+rows+'\nEnd\n')


def z(value):
    return np.array(value['real'])+1j*np.array(value['imag'])


def test_sensor_axes_default_tilted_orthonormal_and_nonmutating():
    row = np.zeros(12); np.testing.assert_array_equal(sensor_axes(row), np.eye(3))
    row[6:] = [3, 1, -2, -.2, 4, 2]; before = row.copy(); axes = sensor_axes(row)
    np.testing.assert_allclose(axes.T@axes, np.eye(3), atol=2e-16)
    assert np.linalg.det(axes) == pytest.approx(1)
    assert axes[:, 1]@row[9:] == pytest.approx(0, abs=1e-15)
    np.testing.assert_array_equal(row, before)
    row[6:9] *= 17; row[9:] *= .02
    np.testing.assert_allclose(sensor_axes(row), axes, atol=2e-16)


@pytest.mark.parametrize('rows', ['0 1 1 0 1 0', '1 1 1 0 1 0\n1 1 2 0 2 0',
    '1 1 3 0 3 0', '1.5 1 1 0 1 0', '1 1.5 1 0 1 0'])
def test_sensor_declarations_reject_nonunique_or_fractional_indices_and_stations(rows):
    with pytest.raises(ValueError, match='Sensor|Index/type columns'):
        with_sensor(model(), rows)


def test_default_sensor_recovers_flight_angles_and_pose_in_still_air():
    configuration = with_sensor(model(beam(stiffness='0 0 0 0 0 0')), '3 1 0 0 0 0')
    c = FlightCondition(speed=21, alpha=8, beta=-12, mach=0, attitude=[23, -31, 74], position_earth=[2, 3, 8])
    out = solve_rigid(configuration, c, 4)['sensors'][0]
    assert [out[k] for k in ('speed','alpha','beta')] == pytest.approx([21, 8, -12])
    assert [out[k] for k in ('bank','elevation','heading')] == pytest.approx(c.attitude)
    np.testing.assert_array_equal(out['position_earth'], c.position_earth)
    R = body_to_earth(c.attitude)
    np.testing.assert_allclose(out['velocity_earth'], R@(-c.speed*c.vectors()[0]), atol=1e-14)
    np.testing.assert_allclose(out['acceleration_sensor'], R.T@[0, 0, 9.80665], atol=1e-14)


def test_sensor_motion_matches_independent_earth_trajectory_derivatives():
    configuration = with_sensor(model(), '1 1 1 .4 1.2 -.3 1 .2 .3 -.1 1 2')
    row = configuration.records['sensor'][0]
    R = body_to_earth([27, -18, 39]); Q = exp(np.array([.2, -.4, .3]))
    r = np.array([.1, 1.1, -.2]); u = np.array([.2, -.1, .3]); ud = np.array([-.1, .2, .15])
    w = np.array([.6, -.2, .1]); wd = np.array([-.2, .1, .3]); omega = np.array([.3, .4, -.5])
    P = np.array([2., 4., -1]); V = np.array([-12., 3., 2.]); A = np.array([.4, -.3, .2])
    reference = np.array([.3, -.1, .2]); configuration.reference[2] = reference
    motion = Motion(omega, R.T@A+np.cross(omega,np.cross(omega,reference)))
    c = FlightCondition(speed=12, sensor_flow='kinematic')
    result = measure_sensor(row, r, Q, LocalMotion(r,u,w,ud,wd), motion, model=configuration, condition=c,
        gravity=R.T@[0, 0, -9.81], frame=dict(body_to_earth=R,position_earth=P,velocity_origin_body=R.T@V))
    arm = row[3:6]-configuration.beams[0].position(1)
    def orientation(t): return R@exp(t*omega)@exp(t*w+.5*t*t*wd)@Q@sensor_axes(row)
    def position(t): return P+t*V+.5*t*t*A+R@exp(t*omega)@(r+t*u+.5*t*t*ud+exp(t*w+.5*t*t*wd)@Q@arm)
    h = 1e-4; axes = orientation(0)
    velocity = (position(h)-position(-h))/(2*h)
    acceleration = (position(h)+position(-h)-2*position(0))/h**2
    np.testing.assert_allclose(result['velocity_earth'], velocity, atol=5e-9)
    np.testing.assert_allclose(result['acceleration_sensor'], axes.T@(acceleration-[0, 0, -9.81]), atol=2e-7)
    def angular(t):
        d = 1e-5; mat = (orientation(t+d)-orientation(t-d))/(2*d)@orientation(t).T
        return np.array([mat[2,1],mat[0,2],mat[1,0]])
    np.testing.assert_allclose(result['rates_sensor'], axes.T@angular(0), atol=2e-10)
    np.testing.assert_allclose(result['angular_acceleration_sensor'], axes.T@(angular(h)-angular(-h))/(2*h), atol=1e-7)
    np.testing.assert_array_equal(result['anchor_velocity_body'], u)
    assert not np.allclose(result['velocity_earth'], R@u)


def test_sensor_zero_flow_and_vertical_attitude_are_explicitly_undefined():
    configuration=with_sensor(model(), '1 1 0 0 0 0')
    c=FlightCondition(speed=10,alpha=0,mach=0,attitude=[0,90,0],gust=dict(type='uniform',velocity=[0,0,10]))
    s=solve_rigid(configuration,c,4)['sensors'][0]
    assert s['speed'] < 1e-12 and s['alpha'] is None and s['beta'] is None
    assert s['attitude_singular'] and s['bank'] is None and s['heading'] is None
    assert s['elevation'] == pytest.approx(90)
    json.dumps(s,allow_nan=False)


def test_sensor_includes_regularized_vortex_field_checked_by_line_quadrature():
    source=Path('examples/rectangular.asw').read_text()
    configuration=with_sensor(parse_asw(source), '1 1 0 -2 .7 2')
    c=FlightCondition(speed=10,alpha=0,mach=0,stall=False)
    mesh=mesh_beam(configuration.beams[0],4); gamma=np.linspace(.2,.7,len(mesh.tm))
    out=evaluate_aerodynamics(configuration,c,[mesh],circulation=gamma)
    point=np.array([-2,.7,2.]); expected=np.zeros(3)
    def segment(a,b,core,lo,hi):
        def f(t):
            r=point-(a+t*b)
            return np.cross(b,r)/(np.dot(r,r)+core*core)**1.5/(4*np.pi)
        return quad_vec(f,lo,hi,epsabs=1e-12)[0]
    for i,(a,b) in enumerate(zip(mesh.r0,mesh.r1)):
        core=max(1/4,mesh.length[i])
        expected+=gamma[i]*(segment(a,b-a,core,0,1)+segment(b,np.array([1.,0,0]),core,0,np.inf)-segment(a,np.array([1.,0,0]),core,0,np.inf))
    np.testing.assert_allclose(out['sensor_airflow'][0]['induced_velocity'],expected,atol=1e-12)


def test_full_and_kinematic_airflow_separate_gust_and_point_volume_effects():
    # A point's regularized potential is differentiated independently at a sensor.
    source=body_source(radius=0,attachments='Ground\n1 0 0\nEnd\nWeight\n1 0 .1 -.2 .3 0 .2 .5\nEnd\n')
    configuration=with_sensor(parse_asw(source),'1 1 0 1.2 .9 1.1')
    c=FlightCondition(speed=10,alpha=0,mach=0,gust=dict(type='uniform',velocity=[1,2,3]))
    full=solve_rigid(configuration,c,4); kinematic=solve_rigid(configuration,replace(c,sensor_flow='kinematic'),4)
    s=full['sensors'][0]; kin=kinematic['sensors'][0]
    np.testing.assert_allclose(kin['air_velocity_sensor'],[10,0,0],atol=1e-14)
    np.testing.assert_allclose(s['air_velocity_sensor'],np.array([11,2,3])+full['sensor_airflow'][0]['induced_velocity'],atol=1e-14)
    np.testing.assert_allclose(full['force'],kinematic['force'],atol=1e-14)
    assert np.linalg.norm(full['sensor_airflow'][0]['induced_velocity'])>0


def test_pylon_position_and_axes_follow_large_elastic_rotation():
    configuration=with_sensor(model(beam(stiffness='100 0 0 0 0 0')))
    out=solve_static(configuration,panels=12,gravity=[0,0,0],loads=[dict(beam=1,t=2,moment=[50*np.pi,0,0])])
    sensor=out['sensors'][0]; tip=out['nodes'][-1]; q=np.array(tip['rotation'])
    np.testing.assert_allclose(sensor['position_body'],np.array(tip['position'])+q@[.3,0,.2],atol=1e-13)
    np.testing.assert_allclose(sensor['axes_body'],q,atol=1e-13)
    assert sensor['speed'] is None  # vacuum has no pitot measurement
    np.testing.assert_allclose(sensor['moment_local'],[50*np.pi,0,0],atol=1e-8)


def test_sensor_load_traces_include_distributed_loading_and_concentrated_jump():
    b=beam(stiffness='0 0 0 0 0 0').replace('End','t mg\n0 9.80665\n2 9.80665\nEnd')
    configuration=with_sensor(model(b),'1 1 0 0 0 0\n2 1 1 0 1 0\n3 1 2 0 2 0')
    out=solve_static(configuration,panels=4,loads=[dict(beam=1,t=1,force=[0,0,-3],moment=[2,0,0])])
    first, middle, last=out['sensors']
    np.testing.assert_allclose(first['force_local'],[0,0,-2*9.80665-3],atol=1e-9)
    np.testing.assert_allclose(first['moment_local'],[-2*9.80665-3+2,0,0],atol=1e-9)
    np.testing.assert_allclose(last['force_local'],0,atol=1e-10)
    np.testing.assert_allclose(last['moment_local'],0,atol=1e-10)
    left,right=middle['section_traces']
    np.testing.assert_allclose(np.array(left['force_local'])-right['force_local'],[0,0,-3],atol=1e-10)
    np.testing.assert_allclose(np.array(left['moment_local'])-right['moment_local'],[2,0,0],atol=1e-10)
    assert middle['load_trace']=='left'


def test_vacuum_free_fall_sensor_specific_force_is_zero_and_gps_moves():
    configuration=with_sensor(rigid_body(),'1 1 0 .3 .2 .1')
    out=solve_time(configuration,panels=4,frame='free',duration=.1,dt=.05,position=[1,2,3],attitude=[20,-15,30])
    R=body_to_earth([20,-15,30]); p=np.array([1,2,3])+R@[.3,.2,.1]
    for snapshot in out['snapshots']:
        s=snapshot['sensors'][0]; t=snapshot['time']
        np.testing.assert_allclose(s['acceleration_sensor'],0,atol=2e-8)
        np.testing.assert_allclose(s['velocity_earth'],[0,0,-9.80665*t],atol=2e-9)
        assert s['position_earth'][2] <= p[2]+1e-10


def test_sensor_harmonic_output_retains_acceleration_and_direct_gust_feedthrough():
    source=Path('examples/forced-oscillator.asw').read_text()
    configuration=with_sensor(parse_asw(source),'1 1 2 0 2 0')
    frequencies=[0.,3.,15.]
    out=solve_frequency_response(configuration,FlightCondition(speed=10,alpha=0,mach=0),4,
        frequencies=frequencies,inputs=['power.1',dict(kind='gust',wave='uniform')],gravity=[0,0,0])
    for point in out['samples']:
        w=point['omega']; s=point['responses'][0]['output']['sensors'][0]
        exact=1/(500*(1+.02j*w)-2*w*w)
        assert z(s['displacement_body'])[1] == pytest.approx(exact,abs=2e-10)
        assert z(s['acceleration_sensor'])[1] == pytest.approx(-w*w*exact,abs=2e-9)
        gust=point['responses'][1]['output']['sensors'][0]
        np.testing.assert_allclose(z(gust['air_velocity_sensor']),[0,0,1],atol=1e-10)
        assert z(gust['alpha']) == pytest.approx(180/np.pi/10,rel=1e-9)


def test_modal_sensor_rate_and_angle_branch_derivatives():
    configuration=with_sensor(oscillator(.02),'1 1 2 0 2 0 -1 0 0 0 0 1')
    out=solve_modes(configuration,panels=4,count=2,gravity=[0,0,0],position=[1,2,3],attitude=[0,0,180])
    for mode in out['modes']:
        lam=complex(*mode['eigenvalue']); s=mode['output']['sensors'][0]
        tip=mode['output']['nodes'][-1]
        np.testing.assert_allclose(z(s['anchor_velocity_body']),lam*z(tip['displacement']),atol=2e-9)
        # Same yaw at all stencil points; no spurious full-turn/h derivative.
        assert abs(z(s['heading']))<1e-6
        np.testing.assert_allclose(z(s['position_earth']),body_to_earth([0,0,180])@z(tip['displacement']),atol=2e-9)


def test_sensor_euler_branch_is_unwrapped_for_a_linear_perturbation():
    from openswing.linear_dynamics import make_system, output_perturbation
    configuration=with_sensor(oscillator(.02),'1 1 2 0 2 0')
    system,_=make_system(configuration,None,4,gravity=[0,0,0],attitude=[0,0,180])
    vector=np.zeros(system.size,dtype=complex)
    # Rotate all local frames in yaw across the heading ±180-degree branch.
    vector[:6*system.network.nn].reshape(-1,6)[:,5]=1
    out=output_perturbation(system,vector,np.zeros_like(vector))
    assert z(out['sensors'][0]['heading']) == pytest.approx(-180/np.pi,abs=1e-8)


@pytest.mark.parametrize('singularity', ['zero airflow', 'vertical attitude'])
def test_complex_sensor_outputs_do_not_linearize_a_singular_base(singularity):
    from openswing.linear_dynamics import make_system, output_perturbation
    configuration=with_sensor(oscillator(.02),'1 1 2 0 2 0')
    c=FlightCondition(speed=10,alpha=0,mach=0,
        gust=dict(type='uniform',velocity=[-10,0,0]) if singularity=='zero airflow' else None,
        attitude=[0,90,0] if singularity=='vertical attitude' else [0,0,0])
    system,_=make_system(configuration,c,4,gravity=[0,0,0])
    vector=np.zeros(system.size,dtype=complex)
    vector[:6*system.network.nn].reshape(-1,6)[:,4]=1+.3j
    vector[system.velocity_start:system.frame_start].reshape(2,-1,3)[0,:,2]=.4+.7j
    # The perturbed stencil has finite angles even though the base does not.
    out=output_perturbation(system,vector,np.zeros_like(vector))['sensors'][0]
    undefined=('speed','alpha','beta') if singularity=='zero airflow' else ('bank','elevation','heading')
    assert all(out[key] is None for key in undefined)
    assert out['air_velocity_sensor'] is not None
    json.dumps(out,allow_nan=False)


def test_sensor_sees_propulsive_jet_at_its_actual_position():
    from openswing.propulsion import jet_profile
    configuration=with_sensor(parse_asw(body_source(radius=0)),'1 1 0 2 0 0')
    row=engine(typ=1,radius=.7,omega=150,torque=0);row[4:7]=[0,0,0]
    configuration.records['engine']=[row]
    c=FlightCondition(speed=20,alpha=0,mach=0,powers={1:1200})
    out=solve_rigid(configuration,c,4);state=out['engines'][0]
    # Axis centerline velocity equals the top-hat profile's core increment.
    _,_,dv,_=jet_profile(state,2,1.225)
    assert out['sensors'][0]['speed'] == pytest.approx(20+float(dv),abs=1e-10)
