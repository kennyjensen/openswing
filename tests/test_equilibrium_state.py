"""Physical steady-state saved guesses and parameter continuation checks."""
from copy import deepcopy
from pathlib import Path
import json
import numpy as np
import pytest
from openswing.asw import parse_asw
from openswing.aero import FlightCondition,AnalysisError
from openswing.network import solve_static,StaticNetwork
from openswing.equilibrium_state import restore,capture
from openswing.linear_dynamics import solve_modes
from openswing.frequency_response import solve_frequency_response
from test_feedback import configuration,condition,law
from test_custom_feedback import lag_law
from test_network import model,beam,tip


@pytest.fixture(scope='module')
def loaded():
    m=configuration();c=condition();c.powers={1:1}
    result=solve_static(m,c,4,gravity=[0,0,0])
    return m,result


def test_loaded_state_recovers_new_force_and_solver_scaling_without_unloading(loaded):
    m,a=loaded;saved=deepcopy(a['equilibrium_state'])
    c=condition();c.speed=40;c.powers={1:3}
    b=solve_static(m,c,4,gravity=[0,0,0],initial_state=saved)
    assert b['sensors'][1]['displacement_body'][1]==pytest.approx(3/500,abs=1e-10)
    np.testing.assert_allclose(b['support_force'],[0,-3,0],atol=1e-8)
    assert b['equilibrium_initialization']['initialization']=='saved physical equilibrium'
    assert b['equilibrium_initialization']['newton_iterations']<5
    assert saved==a['equilibrium_state']
    json.dumps(b,allow_nan=False)


def test_raw_seed_mapping_preserves_positions_loads_reactions_and_circulation(loaded):
    m,a=loaded;c=condition();c.speed=100;c.powers={1:3}
    n=StaticNetwork(m,4,c,[0,0,0],());x=restore(n,a['equilibrium_state']);roundtrip=capture(n,x)
    for key in ('positions','rotations','internal_force','internal_moment','reactions','circulation'):
        np.testing.assert_allclose(roundtrip[key],a['equilibrium_state'][key],atol=1e-14)
    assert n.F>1000  # substantial change in the numerical force scale


@pytest.mark.parametrize('edit',[
    lambda s:s.update(version=2),
    lambda s:s['identity'].update(model_sha256='wrong'),
    lambda s:s.update(positions=[[0,0,0]]),
    lambda s:s['rotations'][0].__setitem__(0,float('nan')),
    lambda s:s['reactions'].__setitem__(0,float('inf')),
])
def test_malformed_or_incompatible_seeds_are_explicit_errors(loaded,edit):
    m,a=loaded;saved=deepcopy(a['equilibrium_state']);edit(saved)
    with pytest.raises(AnalysisError):solve_static(m,condition(),4,gravity=[0,0,0],initial_state=saved)


def test_mesh_changes_are_rejected(loaded):
    m,a=loaded
    with pytest.raises(AnalysisError,match='mesh'):
        solve_static(m,condition(),6,gravity=[0,0,0],initial_state=a['equilibrium_state'])


def test_generated_mesh_roundoff_is_portable_but_coordinates_and_topology_remain_checked(loaded):
    m,a=loaded;n=StaticNetwork(m,4,condition(),[0,0,0],())
    saved=deepcopy(a['equilibrium_state']);node=saved['identity']['nodes'][-1]
    axis=int(np.argmax(abs(np.array(node))));node[axis]=float(np.nextafter(node[axis],np.inf))
    stations=next(iter(saved['identity']['stations'].values()))
    stations[0][-1]=float(np.nextafter(stations[0][-1],np.inf))
    np.testing.assert_array_equal(restore(n,saved),restore(n,a['equilibrium_state']))
    for edit in (
        lambda s:s['identity']['nodes'][-1].__setitem__(axis,node[axis]+1e-10),
        lambda s:s['identity']['nodes'][-1].__setitem__(axis,float('nan')),
        lambda s:s['identity']['stations'][next(iter(s['identity']['stations']))][0].__setitem__(-1,stations[0][-1]+1e-10),
        lambda s:s['identity']['elements'][0].__setitem__(0,999),
        lambda s:s['identity']['stations'][next(iter(s['identity']['stations']))][1].__setitem__(0,999),
    ):
        bad=deepcopy(saved);edit(bad)
        with pytest.raises(AnalysisError,match='mesh'):restore(n,bad)


def test_large_rotation_continuation_recovers_independent_circular_arc():
    m=model(beam(stiffness='100 0 0 0 0 0'));saved=None
    for angle in [1.,1.5,2.]:
        out=solve_static(m,panels=12,gravity=[0,0,0],loads=[dict(beam=1,t=2,moment=[50*angle,0,0])],initial_state=saved)
        expected=[0,2*np.sin(angle)/angle,2*(1-np.cos(angle))/angle]
        np.testing.assert_allclose(tip(out),expected,atol=.003)
        saved=out['equilibrium_state']
    assert out['equilibrium_initialization']['newton_iterations']>0


def test_trim_unknown_is_reencoded_about_new_prescribed_value(loaded):
    m,_=loaded;c=condition()
    first=solve_static(m,c,4,gravity=[0,0,0],operating_constraints=[dict(variable='power.1',quantity='power.1',target=2)])
    c.powers={1:10};second=solve_static(m,c,4,gravity=[0,0,0],initial_state=first['equilibrium_state'],
        operating_constraints=[dict(variable='power.1',quantity='power.1',target=3)])
    assert second['operating_values']['power.1']==pytest.approx(3,abs=1e-8)
    assert second['sensors'][1]['displacement_body'][1]==pytest.approx(.006,abs=1e-10)


def test_controller_trim_commands_and_integrals_survive_seed_then_accept_explicit_command():
    m=configuration();c=condition();control=law(kd=0,ki=100)
    a=solve_static(m,c,4,gravity=[0,0,0],controller=control,
        operating_constraints=[dict(variable='command.RY[2]',quantity='force.y',target=5)])
    saved=deepcopy(a['equilibrium_state']);c.speed=40
    b=solve_static(m,c,4,gravity=[0,0,0],controller=control,initial_state=saved)
    assert b['feedback']['commands']['RY[2]']==pytest.approx(2.01,abs=1e-10)
    assert b['feedback']['actuators']['E1']==pytest.approx(5,abs=1e-8)
    assert b['feedback']['integrals']['RY[2]']==pytest.approx(-.05,abs=1e-9)
    control=deepcopy(control);control['commands']={'RY[2]':2.02}
    d=solve_static(m,c,4,gravity=[0,0,0],controller=control,initial_state=b['equilibrium_state'])
    assert d['feedback']['actuators']['E1']==pytest.approx(10,abs=1e-8)
    assert saved==a['equilibrium_state']


def test_controller_custom_state_and_loaded_modal_frequency_bases_are_preserved():
    m=configuration();c=condition();control=lag_law();control['commands']={'RY[2]':2.01}
    a=solve_static(m,c,4,gravity=[0,0,0],controller=control)
    seed=a['equilibrium_state'];expected=2/700
    modal=solve_modes(m,c,4,gravity=[0,0,0],controller=control,initial_state=seed,count=3)
    harmonic=solve_frequency_response(m,c,4,gravity=[0,0,0],controller=control,initial_state=seed,frequencies=[0],inputs=['command.RY[2]'])
    for out in (modal,harmonic):
        assert out['base']['sensors'][1]['displacement_body'][1]==pytest.approx(expected,abs=1e-9)
        assert out['base']['feedback']['states']['lag']==pytest.approx(500*expected,abs=1e-7)
        assert out['base']['equilibrium_state']['feedback']['layout']['states']==[dict(name='lag',unit='file engine setting')]
    altered=deepcopy(seed);altered['feedback']['layout']['states'][0]['unit']='different'
    with pytest.raises(AnalysisError,match='layout'):
        solve_static(m,c,4,gravity=[0,0,0],controller=control,initial_state=altered)


def test_nonzero_lifting_line_seed_rescales_and_bridge_corrects_to_rigid_limit():
    from openswing.aero import solve_rigid
    from openswing.bridge import run_json
    source=Path('examples/rectangular.asw').read_text();m=parse_asw(source)
    c=FlightCondition(speed=10,alpha=3,mach=0);first=solve_static(m,c,4,gravity=[0,0,0])
    saved=first['equilibrium_state'];assert max(abs(np.array(saved['circulation'])))>1
    changed=FlightCondition(speed=30,alpha=5,mach=0);n=StaticNetwork(m,4,changed,[0,0,0],())
    restored=capture(n,restore(n,saved))
    np.testing.assert_allclose(restored['circulation'],saved['circulation'],atol=1e-14)
    out=json.loads(run_json(json.dumps(dict(action='solve',mode='mounted',source=source,panels=4,
        gravity=[0,0,0],condition=dict(speed=30,alpha=5,mach=0),initial_state=saved))))
    reference=solve_rigid(m,changed,4)
    for key in ('CL','CD','force','moment'):np.testing.assert_allclose(out[key],reference[key],atol=1e-7)
    assert out['equilibrium_initialization']['initialization']=='saved physical equilibrium'
    assert out['max_displacement']<1e-10 and out['residual']<1e-8
