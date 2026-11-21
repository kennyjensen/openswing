"""Custom trim integration with aerodynamic response, derivatives and time."""
from pathlib import Path
import numpy as np
import pytest
from openswing.aero import FlightCondition,AnalysisError
from openswing.asw import parse_asw
from openswing.bridge import dispatch
from openswing.time_initialization import launch_time
from test_custom_constraints import setup,target,solve


def test_aerodynamic_expression_reaches_the_same_loaded_state_as_direct_coefficient_trim():
    from openswing.network import solve_static
    m=parse_asw(Path('examples/flexible.asw').read_text());c=FlightCondition(speed=18,alpha=3,mach=0)
    direct=solve_static(m,c,4,gravity=[0,0,0],operating_constraints=[dict(variable='alpha',quantity='CL',target=.45)],tolerance=1e-11)
    t=target('2*aero("CL")',.9);t.update(variable='alpha',unit='dimensionless',residual_scale=1)
    out=solve(m,c,[t],tolerance=1e-11)
    assert out['CL']==pytest.approx(.45,abs=1e-9)
    assert out['operating_values']['alpha']==pytest.approx(direct['operating_values']['alpha'],abs=1e-7)
    np.testing.assert_allclose([n['position'] for n in out['nodes']],[n['position'] for n in direct['nodes']],atol=1e-8)


def test_custom_trim_releases_for_static_derivative_and_unforced_time_launch():
    m,c=setup()
    out=dispatch(dict(action='solve',mode='mounted',source=m.dumps(),panels=4,gravity=[0,0,0],
        condition=dict(speed=10,alpha=0,mach=0),operating_constraints=[target()],derivatives=dict(parameters=['power.1'])))
    d=np.asarray(out['derivatives']['matrices']['positions'])
    np.testing.assert_allclose(d[-1,:,0],[0,1/500,0],atol=1e-9)
    seed=out['equilibrium_state'];history=launch_time(m,seed,duration=.02,dt=.01)
    assert history['continuation_steps']==0
    for state in history['snapshots']:
        assert state['sensors'][1]['displacement_body'][1]==pytest.approx(.01,abs=1e-9)
        assert state['operating_constraints']==[]
        np.testing.assert_allclose(state['local_velocity'],0,atol=1e-9)
    assert history['initialization']['released_constraints'][0]['expression']==target()['expression']


def test_smooth_composite_with_abs_is_accepted_and_constant_equation_is_rejected():
    m,c=setup()
    out=solve(m,c,[target('abs(sensor("2.displacement_body.y"))**2+sensor("2.displacement_body.y")',0)])
    assert abs(out['operating_values']['power.1'])<1e-10
    with pytest.raises(AnalysisError,match='singular'):solve(m,c,[target('0',0)])


@pytest.mark.parametrize('allocated',[False,True])
def test_closed_loop_seed_requires_the_controller_in_custom_equilibrium(allocated):
    m,c=setup(two=allocated);t=target();t['variable']='command.E1'
    control=dict(outputs=[dict(actuator='E1',expression='command("E1")')])
    saved=solve(m,c,[t],controller=control)['equilibrium_state']
    targets=[target()]+([dict(variable='power.2',quantity='minimum_control')] if allocated else [])
    with pytest.raises(AnalysisError,match='matching controller'):solve(m,c,targets,initial_state=saved)


@pytest.mark.parametrize('seed',[[],42,'invalid'])
def test_malformed_custom_seed_has_the_regular_equilibrium_validation_error(seed):
    m,c=setup()
    with pytest.raises(AnalysisError,match='equilibrium'):solve(m,c,[target()],initial_state=seed)
