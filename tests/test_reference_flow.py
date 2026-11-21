"""Independent vector air-data references, inverse constraints and saved bases."""
from copy import deepcopy
from pathlib import Path
import json
import numpy as np
import pytest
from scipy.spatial.transform import Rotation
from openswing.asw import parse_asw
from openswing.aero import FlightCondition, solve_rigid
from openswing.network import solve_static
from openswing.reference_flow import reference_airflow, reference_airflow_constraints
from openswing.operating import OperatingConstraint
from openswing.bridge import dispatch


def model():
    source=Path('examples/gust-modes.asw').read_text()
    return parse_asw(source.replace('2 1 2\nEnd', '2 1 2\n.2 -.1 .3\n-.3 .4 .2\n1.1 -.5 .7\nEnd'))


def vector(speed, alpha, beta):
    a,b=np.deg2rad([alpha,beta])
    return speed*np.array([np.cos(a)*np.cos(b),-np.sin(b),np.sin(a)*np.cos(b)])


def angles(v):
    return np.rad2deg([np.arctan2(v[2],v[0]),np.arctan2(-v[1],np.hypot(v[0],v[2]))])


def test_reference_vector_uses_displaced_earth_sample_and_counts_rotation_once():
    m=model();c=FlightCondition(speed=19,alpha=7,beta=-4,mach=0,attitude=[17,-11,31],
        position_earth=[7,-3,9],rates=[.4,-.2,.3],time=2.5,
        gust=dict(type='expression',components=['.2*x+.3*t','-.4*y','.1*z-t']))
    # ASW Eq.205 signs, independently composed with SciPy axis rotations.
    rotation=Rotation.from_euler('z',-31,degrees=True).as_matrix()@Rotation.from_euler('y',-11,degrees=True).as_matrix()@Rotation.from_euler('x',-17,degrees=True).as_matrix()
    earth=np.array(c.position_earth)+rotation@m.reference[3]
    gust=np.array([.2*earth[0]+.3*c.time,-.4*earth[1],.1*earth[2]-c.time])
    expected=vector(19,7,-4)+rotation.T@gust
    out=solve_rigid(m,c,4);r=out['reference_flow']
    np.testing.assert_allclose(r['reference_earth'],earth,atol=1e-13)
    np.testing.assert_allclose(r['relative_velocity_body'],expected,atol=1e-13)
    np.testing.assert_allclose(r['relative_velocity_earth'],rotation@expected,atol=1e-13)
    np.testing.assert_allclose(-np.array(out['earth_state']['velocity_origin_body'])-np.cross(c.rates,m.reference[3])+rotation.T@gust,expected,atol=1e-13)
    assert r['speed']==pytest.approx(np.linalg.norm(expected),abs=1e-13)
    np.testing.assert_allclose([r['alpha'],r['beta']],angles(expected),atol=1e-13)
    assert out['atmosphere']['dynamic_pressure']==pytest.approx(.5*out['atmosphere']['density']*19**2)


def test_inverse_reference_speed_angles_recover_uniform_gust_compensation_and_point_drag():
    m=model();gust=np.array([3,-1,2]);desired=vector(20,6,-3);still=desired-gust
    c=FlightCondition(speed=20,alpha=6,beta=-3,mach=0,gust=dict(type='uniform',velocity=gust.tolist()))
    out=solve_static(m,c,4,gravity=[0,0,0],operating_constraints=reference_airflow_constraints(20,6,-3))
    assert out['operating_values']['speed']==pytest.approx(np.linalg.norm(still),abs=2e-8)
    np.testing.assert_allclose([out['operating_values'][k] for k in ('alpha','beta')],angles(still),atol=2e-8)
    force=.5*out['atmosphere']['density']*.4*20*desired
    np.testing.assert_allclose(out['force'],force,atol=3e-7)
    np.testing.assert_allclose(out['moment'],np.cross(np.array([1.2,.6,-.3])-m.reference[1],force),atol=3e-7)
    np.testing.assert_allclose(out['reference_flow']['relative_velocity_body'],desired,atol=3e-8)
    assert max(abs(c['normalized_residual']) for c in out['operating_constraints'])<1e-8


def test_spatial_gust_constraint_can_solve_earth_position():
    m=model();c=FlightCondition(speed=10,alpha=0,mach=0,gust=dict(type='expression',components=['.2*x','0','0']))
    out=solve_static(m,c,4,gravity=[0,0,0],operating_constraints=[dict(variable='position_earth.x',quantity='reference.speed',target=12)])
    assert out['operating_values']['position_earth.x']==pytest.approx(10-m.reference[3,0],abs=1e-8)
    assert out['reference_flow']['speed']==pytest.approx(12,abs=1e-8)


@pytest.mark.parametrize('quantity,target,expected',[
    ('reference.equivalent_airspeed',20,20*np.sqrt(1.225/.7)),
    ('reference.dynamic_pressure',200,np.sqrt(400/.7)),
    ('equivalent_airspeed',20,20*np.sqrt(1.225/.7)+3),
    ('dynamic_pressure',200,np.sqrt(400/.7)+3),
])
def test_local_and_still_air_density_targets_remain_distinct(quantity,target,expected):
    c=FlightCondition(speed=20,alpha=0,density=.7,mach=0,gust=dict(type='uniform',velocity=[3,0,0]))
    out=solve_static(model(),c,4,gravity=[0,0,0],operating_constraints=[dict(variable='speed',quantity=quantity,target=target)])
    assert out['reference_flow']['speed']==pytest.approx(expected,abs=1e-8)


def test_alpha_continuation_crosses_branch_cut_on_short_path():
    c=FlightCondition(speed=10,alpha=179,mach=0)
    out=solve_static(model(),c,4,gravity=[0,0,0],operating_constraints=[dict(variable='alpha',quantity='reference.alpha',target=-179)])
    assert out['operating_values']['alpha']==pytest.approx(181,abs=1e-8)
    assert out['reference_flow']['alpha']==pytest.approx(-179,abs=1e-8)


@pytest.mark.parametrize('gust,beta',[([-10,0,0],None),([-10,2,0],-90.)])
def test_undefined_angles_are_null_and_only_active_angle_constraints_fail(gust,beta):
    m=model();c=FlightCondition(speed=10,alpha=0,mach=0,gust=dict(type='uniform',velocity=gust))
    out=solve_rigid(m,c,4);r=out['reference_flow'];assert r['alpha'] is None;assert r['beta']==beta
    json.dumps(out,allow_nan=False)
    with pytest.raises(ValueError,match='reference.alpha is undefined'):
        solve_static(m,c,4,operating_constraints=[dict(variable='alpha',quantity='reference.alpha',target=0)])


@pytest.mark.parametrize('quantity,target',[(name,v) for name,v in [
    ('speed',0),('speed',True),('speed','10'),('speed',np.inf),('speed',np.nan),
    ('equivalent_airspeed',-1),('dynamic_pressure',0),('alpha',180.1),('beta',-90.1),('unknown',1)]])
def test_invalid_reference_targets_are_explicit_errors(quantity,target):
    with pytest.raises(ValueError,match='Reference'):
        solve_static(model(),FlightCondition(mach=0),4,operating_constraints=[OperatingConstraint('speed','reference.'+quantity,target)])


def test_reference_airflow_uses_file_units_and_sea_level_density():
    m=model();c=FlightCondition(speed=20,alpha=4,beta=3,mach=0,density=.8,gust=dict(type='uniform',velocity=[3,2,-1]))
    a=reference_airflow(m,c)
    # Same file model in feet and milliseconds: scale numerical values by L/T.
    length=1/.3048;time=1000;velocity=length/time
    scaled=deepcopy(m);scaled.reference[1:]*=length;scaled.constants[1]*=time**2/length**4
    c.speed*=velocity;c.gust['velocity']=(np.array(c.gust['velocity'])*velocity).tolist();c.density*=time**2/length**4
    b=reference_airflow(scaled,c)
    for key in ('speed','equivalent_airspeed'):assert b[key]==pytest.approx(a[key]*velocity)
    assert b['dynamic_pressure']==pytest.approx(a['dynamic_pressure']/length**2)
    np.testing.assert_allclose([b['alpha'],b['beta']],[a['alpha'],a['beta']],atol=1e-13)


@pytest.mark.parametrize('beta',[-90,90])
def test_transverse_trigonometric_roundoff_does_not_define_alpha(beta):
    r=reference_airflow(model(),FlightCondition(speed=10,alpha=17,beta=beta,mach=0))
    assert r['alpha'] is None
    assert r['beta']==pytest.approx(beta,abs=1e-12)


def test_posed_gust_cancellation_does_not_define_roundoff_angles():
    m=model();c=FlightCondition(speed=10,alpha=7,beta=3,mach=0,attitude=[17,-11,31])
    rotation=Rotation.from_euler('z',-31,degrees=True).as_matrix()@Rotation.from_euler('y',-11,degrees=True).as_matrix()@Rotation.from_euler('x',-17,degrees=True).as_matrix()
    c.gust=dict(type='uniform',velocity=(-rotation@vector(10,7,3)).tolist())
    r=reference_airflow(m,c)
    assert r['speed']<1e-13
    assert r['alpha'] is r['beta'] is None


def test_bridge_preset_and_saved_trim_reuse_in_frequency_base():
    source=Path('examples/instrumented-oscillator.asw').read_text()
    constraints=dispatch(dict(action='reference_airflow_constraints',source=source,preset=dict(speed=10,alpha=0,beta=0)))
    req=dict(source=source,panels=4,gravity=[0,0,0],condition=dict(speed=10,alpha=0,mach=0,powers={'1':2},gust=dict(type='uniform',velocity=[2,1,-.5])),operating_constraints=constraints)
    a=dispatch(dict(req,action='solve',mode='mounted'));saved=deepcopy(a['equilibrium_state'])
    b=dispatch(dict(req,action='frequency',frequency=dict(initial_state=saved,frequencies=[0,10],inputs=['power.1'])))
    assert b['base']['reference_flow']['speed']==pytest.approx(10,abs=1e-8)
    assert b['base']['sensors'][1]['displacement_body'][1]==pytest.approx(.004,abs=1e-9)
    assert b['base']['equilibrium_initialization']['initialization']=='saved physical equilibrium'
    assert saved==a['equilibrium_state']
    for row in b['samples']:
        value=row['responses'][0]['output']['nodes'][-1]['displacement']
        actual=value['real'][1]+1j*value['imag'][1];w=row['omega']
        assert actual==pytest.approx(1/(500+10j*w-2*w*w),abs=1e-9)
