"""ASWING K/L: algebraic circulation, rate loads, dynamics and saved setup."""
from dataclasses import replace
from pathlib import Path
import json
import numpy as np
import pytest
from openswing.aero import FlightCondition, solve_rigid, evaluate_aerodynamics
from openswing.asw import parse_asw
from openswing.geometry import model_meshes
from openswing.linear_dynamics import make_system, linearize, eigensystem
from openswing.frequency_response import solve_frequency_response
from openswing.network import solve_static
from openswing.time_initialization import launch_time
from openswing.time_state import checkpoint, resume_time, read_condition


def long_wing():
    source=Path('examples/rectangular.asw').read_text().split('t dCLdF1')[0]+'End\n'
    return parse_asw(source.replace('6 0 6 0','100000 0 100000 0')
        .replace('6 .008','100000 .008').replace('.008','0').replace('12 1 12','200000 1 200000'))


@pytest.mark.parametrize('value',[None,0,1,'false',[],{}])
def test_lag_flag_is_boolean_and_older_conditions_default_to_enabled(value):
    assert FlightCondition().aero_lag is True
    assert read_condition(dict(speed=30)).aero_lag is True
    model=parse_asw(Path('examples/rectangular.asw').read_text())
    with pytest.raises(ValueError,match='lag must be a boolean'):
        solve_rigid(model,FlightCondition(aero_lag=value),4)


@pytest.mark.parametrize('modes',[{}, {1:3}])
def test_disabling_lag_removes_rate_wrench_and_downwash_but_retains_added_mass(modes):
    model=long_wing();meshes=model_meshes(model,8)
    c=FlightCondition(alpha=0,mach=0,stall=False,aero_lag=False,circulation_modes=modes,acceleration=[0,0,2.])
    from openswing.circulation import CirculationBasis
    basis=CirculationBasis(meshes,modes)
    rate=basis.decode(np.arange(1.,basis.size+1))
    zero=evaluate_aerodynamics(model,c,meshes,circulation_rate=np.zeros_like(rate))
    actual=evaluate_aerodynamics(model,c,meshes,circulation_rate=rate)
    enabled=evaluate_aerodynamics(model,replace(c,aero_lag=True),meshes,circulation_rate=rate)
    for key in ['force','moment','circulation_residual','circulation_local_residual','apparent_force','apparent_moment']:
        np.testing.assert_array_equal(actual[key],zero[key])
    np.testing.assert_array_equal(actual['circulation_rate_force'],[0,0,0])
    np.testing.assert_array_equal([s['circulation_rate'] for s in actual['strips']],rate)
    # Classical flat-plate added mass, rho*pi*c^2/4 per unit span.
    expected=-1.225*np.pi/4*200000*2
    assert actual['apparent_force'][2]==pytest.approx(expected,rel=1e-13)
    assert enabled['apparent_force'][2]==pytest.approx(expected,rel=1e-13)
    assert np.linalg.norm(enabled['circulation_rate_force'])>0
    assert actual['aerodynamic_lag']['circulation']=='algebraic'


@pytest.mark.parametrize('lag',[False,True])
def test_uniform_gust_frequency_transfer_has_the_selected_section_physics(lag):
    c=FlightCondition(speed=30,alpha=0,mach=0,stall=False,aero_lag=lag,circulation_modes={1:3})
    out=solve_frequency_response(long_wing(),c,8,gravity=[0,0,0],
        frequencies=[0.,3.,30.,300.],inputs=[dict(kind='gust',wave='uniform')])
    assert out['converged'] and out['base']['aerodynamic_lag']['enabled']==lag
    for sample in out['samples']:
        omega=sample['omega'];v=sample['responses'][0]['output']['global']['CL']
        expected=2*np.pi/30*((1+1j*omega/30)/(1+2j*omega/30) if lag else 1)
        assert complex(v['real'],v['imag'])==pytest.approx(expected,rel=2e-4)


def test_coupled_modes_remove_only_circulation_dynamics_and_preserve_structural_mass():
    model=parse_asw(Path('examples/heave-pitch.asw').read_text())
    pencils=[]
    for lag,count in [(True,8),(False,4)]:
        c=FlightCondition(speed=50,alpha=0,mach=0,stall=False,aero_lag=lag)
        system,_=make_system(model,c,4,gravity=[0,0,0]);a,m=linearize(system)
        modes,meta=eigensystem(a,m,time_scale=system.W,count=20)
        assert meta['finite_dimension']==len(modes)==count
        assert max(x['right_backward_error'] for x in modes)<1e-9
        pencils.append((system,a,m))
    # Removing circulation time derivatives preserves every other mass column.
    n=pencils[0][0].network;before,after=pencils[0][2],pencils[1][2]
    columns=np.r_[0:n.gamma_start,n.operating_start:len(before)]
    np.testing.assert_array_equal(before[:,columns],after[:,columns])
    np.testing.assert_array_equal(after[:,n.gamma_start:n.operating_start],0)
    assert np.linalg.norm(before[:,n.gamma_start:n.operating_start])>0


def test_lag_disabled_saved_launch_and_restart_follow_instantaneous_gust():
    model=long_wing()
    c=FlightCondition(speed=30,alpha=0,mach=0,stall=False,aero_lag=False,
        gust=dict(type='expression',components=['0','0','.001*t']))
    base=solve_static(model,c,4,gravity=[0,0,0])
    saved=json.loads(json.dumps(base['equilibrium_state']))
    assert saved['launch']['condition']['aero_lag'] is False
    trajectory=launch_time(model,saved,duration=.06,dt=.02)
    assert trajectory['restart_context']['setup']['condition']['aero_lag'] is False
    for s in trajectory['snapshots']:
        assert s['CL']==pytest.approx(2*np.pi*.001*s['time']/30,rel=2e-4,abs=1e-12)
        np.testing.assert_array_equal(s['circulation_rate_force'],[0,0,0])
        assert s['aerodynamic_lag']['enabled'] is False
    assert max(abs(x) for x in trajectory['snapshots'][-1]['circulation_rate'])>1e-4
    resumed=resume_time(model,checkpoint(trajectory,1),duration=.04)
    for actual,expected in zip(resumed['snapshots'],trajectory['snapshots'][1:]):
        assert actual['CL']==pytest.approx(expected['CL'],abs=1e-12)
        np.testing.assert_allclose(actual['circulation_rate'],expected['circulation_rate'],atol=1e-10)
    assert saved==base['equilibrium_state']
