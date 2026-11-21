"""K/F reference geometry, live mechanics, owned coefficients and state reuse."""
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
import runpy
import numpy as np
import pytest
from scipy.integrate import quad_vec
from scipy.optimize import linear_sum_assignment
from openswing.aero import FlightCondition, evaluate_aerodynamics, solve_rigid
from openswing.asw import parse_asw
from openswing.frozen_influence import FrozenInfluences
from openswing.geometry import model_meshes
from openswing.network import solve_static
from openswing.flow_survey import survey
from openswing.time_state import read_condition, checkpoint, resume_time
from openswing.time_initialization import launch_time
from openswing.linear_dynamics import make_system, linearize, eigensystem
from openswing.frequency_response import solve_frequency_response

STUDY = runpy.run_path('scripts/verify-frozen-influences.py')


def test_new_conditions_freeze_influences_and_saved_conditions_preserve_their_choice():
    assert FlightCondition().freeze_influences is True
    assert FlightCondition(freeze_influences=False).freeze_influences is False
    legacy = {'speed': 30, 'controls': {'1': 4}}
    original = deepcopy(legacy)
    assert read_condition(legacy).freeze_influences is False
    assert read_condition(legacy, saved=False).freeze_influences is True
    assert legacy == original
    for value in (True, False):
        for saved in (True, False):
            assert read_condition(dict(legacy, freeze_influences=value), saved=saved).freeze_influences is value
    model, c, _ = STUDY['setup'](dict(panels=4, alpha=8, beta=4))
    default = replace(c, freeze_influences=FlightCondition().freeze_influences)
    result = solve_rigid(model, default, 4)
    frozen = solve_rigid(model, replace(c, freeze_influences=True), 4)
    current = solve_rigid(model, replace(c, freeze_influences=False), 4)
    np.testing.assert_array_equal(result['force'], frozen['force'])
    assert np.linalg.norm(np.array(result['force'])-current['force']) > 1e-3


@pytest.mark.parametrize('value', [None, 0, 1, 'false', [], {}])
def test_flag_is_strict_boolean_and_old_conditions_keep_current_influences(value):
    assert read_condition({'speed': 30}).freeze_influences is False
    model, c, meshes = STUDY['setup'](dict(panels=4))
    c = replace(c, freeze_influences=value)
    for call in [lambda: solve_rigid(model, c, 4), lambda: evaluate_aerodynamics(model, c, meshes)]:
        with pytest.raises(ValueError, match='Freeze aerodynamic influences must be a boolean'):
            call()


@pytest.mark.parametrize('spec', [dict(panels=4), dict(panels=8, mach=.6, ground=1),
    dict(panels=8, alpha=-12, beta=-9, rotations=[[.12,-.18,.06],[-.15,.11,-.04]], stretches=[1.2,.9])])
def test_frozen_influences_match_independent_lines_and_current_frame_loads(spec):
    expected, actual = STUDY['reference'](spec), STUDY['compute'](spec)
    np.testing.assert_allclose(STUDY['physical'](actual), STUDY['physical'](expected), rtol=3e-10, atol=3e-10)


def test_zero_wind_jig_case_matches_current_mode_and_current_geometry_still_affects_loads():
    model, c, meshes = STUDY['setup'](dict(panels=4, alpha=0, beta=0))
    frozen = evaluate_aerodynamics(model, c, meshes)
    current = evaluate_aerodynamics(model, replace(c, freeze_influences=False), meshes)
    for key in ['force', 'moment', 'CL', 'CD', 'CDi', 'circulation_residual']:
        np.testing.assert_allclose(frozen[key], current[key], rtol=2e-14, atol=2e-14)
    gamma = [s['circulation'] for s in frozen['strips']]
    stretched = [replace(m, r0=m.r0*[1,2,1], r1=m.r1*[1,2,1], rm=m.rm*[1,2,1], length=m.length*2) for m in meshes]
    other = evaluate_aerodynamics(model, c, stretched, gamma)
    np.testing.assert_allclose(other['force'], 2*np.array(frozen['force']), atol=2e-13)
    np.testing.assert_array_equal(other['circulation_residual'], frozen['circulation_residual'])
    np.testing.assert_array_equal([s['wake_core_radius'] for s in other['strips']], [s['wake_core_radius'] for s in frozen['strips']])


def test_cache_reuses_only_matching_coefficients_and_rebuilds_for_mach_core_and_ground(monkeypatch):
    import openswing.aero as aero
    model, c, meshes = STUDY['setup'](dict(panels=4))
    cache = FrozenInfluences(model, meshes)
    original = aero.finite_vortex
    calls = []
    def counted(*args, **kwargs):
        calls.append(1)
        return original(*args, **kwargs)
    monkeypatch.setattr(aero, 'finite_vortex', counted)
    first = evaluate_aerodynamics(model, c, meshes, frozen_influences=cache)
    count = len(calls)
    moved = [replace(m, r0=m.r0+[.1,0,.2], r1=m.r1+[.1,0,.2], rm=m.rm+[.1,0,.2]) for m in meshes]
    evaluate_aerodynamics(model, replace(c, alpha=12, beta=-6, speed=40), moved, frozen_influences=cache)
    assert len(calls) == count  # no vortex-integral work for geometry/angle/speed changes at fixed Mach
    for change in [dict(mach=.4), dict(wake_core_ratio=1.), dict(ground_effect=1),
                   dict(ground_effect=1, position_earth=[0,0,2]), dict(ground_effect=1, attitude=[3,2,0]), dict(mach=None, speed=60)]:
        updated = replace(c, **change)
        before = len(calls)
        reused = evaluate_aerodynamics(model, updated, meshes, frozen_influences=cache)
        assert len(calls) > before
        fresh = evaluate_aerodynamics(model, updated, meshes)
        np.testing.assert_array_equal(reused['force'], fresh['force'])
        assert np.linalg.norm(np.array(first['force'])-reused['force']) > 1e-5
    with pytest.raises(ValueError, match='different model or material mesh'):
        evaluate_aerodynamics(model, c, model_meshes(model, 8), frozen_influences=cache)


def test_frozen_volume_sources_and_attached_receivers_use_jig_but_gust_uses_current_position():
    source = '''Name
Frozen body and point volumes
End
Unit
L 1 m
T 1 s
F 1 N
End
Constant
9.80665 1.225 340.294
End
Reference
4 1 4
End
Ground
1 0 0
End
Weight
1 0 1 .5 2.3 0 .2 .5
1 4 3 -.4 2.2 0 .1 .3
End
Sensor
1 1 2 2 .6 2.4
End
Beam 1
Tapered body
t x y z radius Cdf Cdp
0 0 0 2 .1 0 0
4 4 0 2 .2 0 0
End
'''
    model = parse_asw(source); meshes = model_meshes(model, 16)
    shift = np.array([.2,-.3,.4])
    moved = [replace(m, r0=m.r0+shift, r1=m.r1+shift, rm=m.rm+shift) for m in meshes]
    objects = np.array([row[2:5] for row in model.records['weight']])
    sensor = np.array([2.,.6,2.4]); probes = np.array([[2.,1.3,3.], [5.,-.6,2.4]])
    c = FlightCondition(alpha=12,beta=-8,mach=.6,stall=False,freeze_influences=True,
                        gust=dict(type='expression', components=['0','0','.2*z']))
    result = evaluate_aerodynamics(model,c,moved,point_positions=objects+shift,
                                  sensor_positions=[sensor+shift],survey_positions=probes)
    pg = np.diag([1.25,1.,1.])
    def field(target, excluded=None):
        target = np.asarray(target)
        def body(x):
            radius = .1+.025*x
            delta = (target-[x,0,2])@pg.T
            return 2*np.pi*radius*.025*1.25*delta/(np.sum(delta*delta,axis=-1)+(radius/2)**2)[...,None]**1.5/(4*np.pi)@pg
        value = quad_vec(body,0,4,epsabs=1e-12)[0]
        for i, (position, area, vol) in enumerate(zip(objects,[.2,.1],[.5,.3])):
            if excluded == i:
                continue
            d=(target-position)@pg.T;r2=np.sum(d*d,axis=-1)
            core=max(np.sqrt(area/np.pi),np.cbrt(vol/np.pi));den=r2+core*core
            dipole=np.array([vol*1.25,0,0])
            value+=(area*d/den[...,None]**1.5+(dipole*r2[...,None]-3*(d@dipole)[...,None]*d)/den[...,None]**2.5)/(4*np.pi)@pg
        return c.speed*value
    np.testing.assert_allclose(result['flow_survey']['velocity_body']['volume'],field(probes),atol=2e-10,rtol=2e-10)
    np.testing.assert_allclose(result['sensor_airflow'][0]['induced_velocity'],field(sensor),atol=2e-10,rtol=2e-10)
    np.testing.assert_allclose(result['sensor_airflow'][0]['position'],sensor+shift)
    np.testing.assert_allclose(result['sensor_airflow'][0]['gust_velocity'],[0,0,.2*(sensor+shift)[2]])
    for i, area in enumerate([.2,.1]):
        velocity = c.speed*c.vectors()[0]+field(objects[i],i)+[0,0,.2*(objects[i]+shift)[2]]
        expected = .5*1.225*area*np.linalg.norm(velocity)*velocity
        np.testing.assert_allclose(result['point_forces'][i],expected,rtol=3e-10,atol=3e-10)


def test_modal_lag_poles_match_independent_frozen_circulation_system():
    spec=dict(panels=4,alpha=8,beta=4,mach=.3)
    _, ref = STUDY['reference'](spec, details=True)
    model,c,_=STUDY['setup'](spec)
    vp=ref['velocity']-np.sum(ref['velocity']*ref['spans'],axis=1)[:,None]*ref['spans']
    expected=np.linalg.eigvals(np.pi/2*np.linalg.norm(vp,axis=1)[:,None]*ref['matrix'])
    system,_=make_system(model,c,4,gravity=[0,0,0]);a,m=linearize(system)
    modes,meta=eigensystem(a,m,time_scale=system.W,count=20)
    actual=np.array([complex(*mode['eigenvalue']) for mode in modes])
    assert meta['finite_dimension']==len(expected)==len(actual)
    i,j=linear_sum_assignment(abs(actual[:,None]-expected[None,:]))
    np.testing.assert_allclose(actual[i],expected[j],rtol=2e-7,atol=2e-7)


def test_harmonic_gust_response_matches_independent_rate_lift_and_circulation():
    spec=dict(panels=4,alpha=8,beta=4,mach=.3)
    base,ref=STUDY['reference'](spec,details=True);model,c,_=STUDY['setup'](spec)
    v,s=ref['velocity'],ref['spans'];gamma=np.array(base['gamma'])
    speed=np.linalg.norm(v-np.sum(v*s,axis=1)[:,None]*s,axis=1)
    result=solve_frequency_response(model,c,4,gravity=[0,0,0],frequencies=[0.,7.],inputs=[dict(kind='gust',wave='uniform')])
    for sample in result['samples']:
        omega=sample['omega']
        dg=np.linalg.solve(ref['matrix']-np.diag(2j*omega/(np.pi*speed)),-ref['normal'][:,2])
        dv=[0,0,1]+np.einsum('ijk,j->ik',ref['hv_matrix'],dg)
        df=1.225*ref['length'][:,None]*((dg*(1+1j*omega*ref['chord']/speed))[:,None]*np.cross(v,s)+gamma[:,None]*np.cross(dv,s))
        expected=df.sum(axis=0)@c.vectors()[2]/(.5*1.225*c.speed**2*4.9)
        value=sample['responses'][0]['output']['global']['CL']
        assert complex(value['real'],value['imag'])==pytest.approx(expected,rel=2e-7,abs=2e-9)


def test_saved_state_survey_time_launch_and_restart_retain_the_approximation():
    model,c,_=STUDY['setup'](dict(panels=4))
    base=solve_static(model,c,4,gravity=[0,0,0]);saved=deepcopy(base['equilibrium_state']);original=deepcopy(saved)
    assert saved['launch']['condition']['freeze_influences'] is True
    field=survey(model,positions=STUDY['POINTS'],equilibrium_state=saved)
    expected=STUDY['reference'](dict(panels=4))
    np.testing.assert_allclose(field['velocity']['lifting'],expected['field'],atol=1e-9)
    assert field['aerodynamic_influences']['frozen'] is True
    history=launch_time(model,saved,duration=.02,dt=.01)
    resumed=resume_time(model,checkpoint(history,1),duration=.01)
    for s in history['snapshots']+resumed['snapshots']:
        assert s['aerodynamic_influences']['frozen'] is True
        np.testing.assert_allclose(s['force'],base['force'],rtol=2e-9,atol=1e-8)
    assert saved==original
    changed=solve_static(model,replace(c,freeze_influences=False),4,gravity=[0,0,0],initial_state=saved)
    fresh=solve_static(model,replace(c,freeze_influences=False),4,gravity=[0,0,0])
    np.testing.assert_allclose(changed['force'],fresh['force'],atol=1e-8)
    assert np.linalg.norm(np.array(base['force'])-fresh['force'])>1.
