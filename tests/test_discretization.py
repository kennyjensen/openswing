"""Editable material meshes: geometry, conservative mechanics and state reuse."""
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
import json
import numpy as np
import pytest
from openswing.asw import parse_asw
from openswing.geometry import mesh_beam, model_meshes
from openswing.discretization import normalize, report
from openswing.aero import FlightCondition, solve_rigid, AnalysisError
from openswing.network import StaticNetwork, solve_static
from openswing.bridge import dispatch
from openswing.time_initialization import launch_time
from openswing.time_state import checkpoint, resume_time
from openswing.frequency_response import solve_frequency_response
from openswing.inertia import InertiaModel
from test_network import beam, model, balanced, tip


def custom(nodes, default=8):
    return dict(default=default, beams={'1': dict(nodes=nodes)})


def stations(mesh):
    return np.r_[mesh.t0, mesh.t1[-1]]


@pytest.mark.parametrize('spacing', ['cosine', 'uniform'])
def test_generated_spacing_uses_material_arc_not_arbitrary_parameter(spacing):
    m = model('Beam 1\nNonuniform t\nt y\n-2 0\n0 .4\n3 2\nEnd\n', 'Ground\n1 -2 0\nEnd\n')
    mesh = model_meshes(m, dict(default=8, beams={'1': dict(count=8, spacing=spacing)}))[0]
    expected = np.linspace(0, 1, 9)
    if spacing == 'cosine': expected = (1-np.cos(np.pi*expected))/2
    np.testing.assert_allclose(np.r_[0, np.cumsum(mesh.length)]/2, expected, atol=5e-15)
    np.testing.assert_allclose(np.r_[mesh.r0[:, 1], mesh.r1[-1, 1]]/2, expected, atol=2e-7)
    np.testing.assert_allclose(mesh.theta, np.arccos(2*expected-1), atol=1e-14)
    assert not np.allclose(stations(mesh), np.linspace(-2, 3, 9))


def test_per_beam_settings_do_not_mutate_requests_or_asw_geometry():
    m = model(beam()+beam(2, start=3, end=5), 'Ground\n1 0 0\n2 0 0\nEnd\n')
    settings = dict(default=12, beams={'1': dict(count=5, spacing='uniform')})
    before = deepcopy(settings); source = m.dumps()
    meshes = model_meshes(m, settings)
    assert [len(a.tm) for a in meshes] == [5, 12]
    np.testing.assert_allclose(stations(meshes[0]), np.linspace(0, 2, 6))
    assert m.dumps() == source and settings == before
    normalized = normalize(settings, m); normalized['beams']['1']['count'] = 20
    assert settings == before


@pytest.mark.parametrize('count', [4, 5, 40, 101, 512, 513, 608, 1024])
def test_modified_cosine_mesh_is_symmetric_and_preserves_endpoints(count):
    m = model(beam())
    settings = dict(default=count, beams={'1': dict(count=count, spacing='modified-cosine')})
    mesh = model_meshes(m, settings)[0]
    t = stations(mesh)
    assert len(t) == count+1 and (t[0], t[-1]) == (0., 2.)
    assert np.all(np.diff(t) > 0)
    np.testing.assert_allclose(t+t[::-1], 2., atol=1e-14, rtol=0)
    if count % 2 == 0:
        assert t[count//2] == 1.
    assert not np.allclose(t, stations(model_meshes(m, count)[0]))


def test_decreasing_source_parameter_and_unequal_intervals_preserve_mass_tensor():
    # Exact uniform line mass: m=2 kg, CG y=1, Ixx=Izz=m L^2/12.
    source = 'Beam 1\nUniform mass\nt y mg\n2 2 9.80665\n0 0 9.80665\nEnd\n'
    m = model(source);settings=custom([0,.07,.41,1.7,2])
    meshes=model_meshes(m,settings);inertia=InertiaModel(m,meshes)
    mass=inertia.summary(inertia.elements(meshes))
    assert mass['mass']==pytest.approx(2,abs=1e-13)
    np.testing.assert_allclose(mass['cg'],[0,1,0],atol=1e-13)
    np.testing.assert_allclose(mass['inertia_cg'],np.diag([2/3,0,2/3]),atol=1e-13)
    forward=model(source.replace('2 2 9.80665\n0 0 9.80665','0 0 9.80665\n2 2 9.80665'))
    np.testing.assert_array_equal(meshes[0].r0,model_meshes(forward,settings)[0].r0)


@pytest.mark.parametrize('intervals', [608, 1024])
@pytest.mark.parametrize('explicit', [False, True])
def test_large_mesh_keeps_attachment_and_exact_line_mass_properties(intervals, explicit):
    m = model('Beam 1\nUniform mass\nt y mg\n0 0 9.80665\n2 2 9.80665\nEnd\n',
              'Ground\n1 0 0\nEnd\nWeight\n1 .73 .1 .73 .2 2.941995\nEnd\n')
    nodes = np.linspace(0, 2, intervals+1).tolist()
    settings = (custom(nodes, default=intervals) if explicit else
                dict(default=intervals, beams={'1':dict(count=intervals,spacing='uniform')}))
    meshes = model_meshes(m, settings)
    actual = stations(meshes[0])
    assert len(actual) == intervals+2 and .73 in actual
    if explicit:
        assert set(nodes) <= set(actual)
    np.testing.assert_allclose([sum(meshes[0].length),actual[0],actual[-1]], [2,0,2],atol=1e-13)
    inertia = InertiaModel(m,meshes)
    mass = inertia.summary(inertia.elements(meshes))
    point = np.array([.1,.73,.2])
    expected_cg = (np.array([0,2,0])+.3*point)/2.3
    expected_origin = np.diag([8/3,0,8/3])+.3*(point@point*np.eye(3)-np.outer(point,point))
    expected_inertia = expected_origin-2.3*(expected_cg@expected_cg*np.eye(3)-np.outer(expected_cg,expected_cg))
    assert mass['mass'] == pytest.approx(2.3,abs=1e-12)
    np.testing.assert_allclose(mass['cg'],expected_cg,atol=1e-12)
    np.testing.assert_allclose(mass['inertia_cg'],expected_inertia,atol=1e-12)
    inspected = dispatch(dict(action='inspect',source=m.dumps(),panels=settings))
    assert inspected['mesh_discretization']['settings'] == settings
    assert next(n for n in inspected['mesh_discretization']['beams'][0]['nodes'] if n['t']==.73)['required'] == ['weight 1']


@pytest.mark.parametrize('spacing', ['explicit', 'modified-cosine'])
def test_required_nodes_keep_all_attachment_reasons_and_loads(spacing):
    attachments = '''Ground
1 0 0
End
Weight
1 .41 0 .41 0 10
End
Sensor
1 1 .41 0 .41 0
End
Engine
1 0 1 .83 0 .83 0 0 1 0 1 0 -1 0 0
End
Strut
1 1.27 0 1.27 0 0 1.27 1 0 100
End
Joint
1 2 1.69 0 0
End
'''
    m = model(beam()+beam(2, start=1.69, end=3.69), attachments)
    settings = (custom([0, .25, .75, 1.5, 2]) if spacing == 'explicit' else
                dict(default=8, beams={'1': dict(count=8, spacing=spacing)}))
    loads = [dict(beam=1, t=1.73, force=[0, 1, 0])]
    meshes = model_meshes(m, settings, loads)
    nodes = report(m, meshes, settings, loads)['beams'][0]['nodes']
    required = {n['t']:n['required'] for n in nodes}
    assert required[.41] == ['weight 1', 'sensor 1']
    assert required[.83] == ['engine 1'] and required[1.27] == ['strut 1']
    assert required[1.69] == ['joint 1'] and required[1.73] == ['load 1']
    network = StaticNetwork(m, settings, FlightCondition(alpha=0), [0, 0, 0], loads)
    np.testing.assert_array_equal(network.station_nodes[1][0], stations(meshes[0]))
    inspected = dispatch(dict(action='inspect', source=m.dumps(), panels=settings, loads=loads))
    assert inspected['mesh_discretization']['beams'][0]['nodes'] == nodes


def test_arbitrary_nodes_keep_exact_extension_and_force_moment_balance():
    m = model(beam(stiffness='0 0 0 1000 0 0'))
    settings = custom([0, .1, .9, 1.8, 2])
    out = solve_static(m, panels=settings, gravity=[0, 0, 0], loads=[dict(beam=1, t=.73, force=[0, 10, 0])])
    np.testing.assert_allclose(tip(out), [0, 2+10*.73/1000, 0], atol=1e-11)
    np.testing.assert_allclose(out['support_force'], [0, -10, 0], atol=1e-11)
    assert .73 in [n['t'] for n in out['nodes']]
    assert out['mesh_discretization']['settings'] == settings
    balanced(out)
    bridged = dispatch(dict(action='solve', mode='mounted', source=m.dumps(), panels=settings,
        condition=dict(alpha=0, mach=0), gravity=[0,0,0], loads=[dict(beam=1,t=.73,force=[0,10,0])]))
    np.testing.assert_allclose(tip(bridged), tip(out), atol=1e-11)
    assert bridged['mesh_discretization'] == out['mesh_discretization']


def test_position_jump_is_rigid_offset_and_not_material_arc():
    source = 'Beam 1\nJump\nt x y z\n0 0 0 0\n1 0 1 0\n1 .4 1 .3\n2 .4 2 .3\nEnd\n'
    m = model(source); settings = custom([0, .2, .7, 1.6, 2])
    mesh = model_meshes(m, settings)[0]
    assert sum(mesh.length) == pytest.approx(2., abs=1e-14)
    assert 1 in stations(mesh)
    rows = report(m, [mesh], settings)['beams'][0]['nodes']
    assert next(n for n in rows if n['t'] == 1)['fraction'] == pytest.approx(.5)
    out = solve_static(m, panels=settings, gravity=[0, 0, 0], loads=[dict(beam=1, t=2, force=[2, 3, 4])])
    np.testing.assert_allclose(out['support_moment'], -np.cross([.4, 2, .3], [2, 3, 4]), atol=1e-9)
    balanced(out)


def test_nonsymmetric_explicit_mesh_full_fourier_basis_matches_pointwise_rigid_limit():
    m = parse_asw(Path('examples/rectangular.asw').read_text())
    settings = custom([-6, -4.2, -1.1, 0, .8, 3.7, 6])
    c = FlightCondition(alpha=5, beta=3, mach=0, controls={1: 2})
    point = solve_rigid(m, c, settings)
    fourier = solve_rigid(m, replace(c, circulation_modes={1: len(model_meshes(m, settings)[0].tm)}), settings)
    coupled = solve_static(m, c, settings, gravity=[0, 0, 0])
    for other in (fourier, coupled):
        np.testing.assert_allclose(other['force'], point['force'], atol=1e-8, rtol=1e-9)
        np.testing.assert_allclose(other['moment'], point['moment'], atol=1e-8, rtol=1e-9)
        assert other['mesh_discretization'] == point['mesh_discretization']


@pytest.mark.parametrize('spacing', ['explicit', 'modified-cosine'])
def test_custom_mesh_equilibrium_launch_checkpoint_and_incompatible_state(spacing):
    m = model(beam(stiffness='0 0 0 1000 0 0'))
    settings = (custom([0, .2, .8, 1.7, 2]) if spacing == 'explicit' else
                dict(default=4, beams={'1': dict(count=4, spacing=spacing)}))
    out = solve_static(m, panels=settings, gravity=[0, 0, 0], loads=[dict(beam=1, t=2, force=[0, 1, 0])])
    saved = json.loads(json.dumps(out['equilibrium_state']))
    assert saved['launch']['panels'] == settings
    history = launch_time(m, saved, duration=.02, dt=.01)
    continued = resume_time(m, checkpoint(history), duration=.01)
    assert continued['restart_context']['setup']['panels'] == settings
    np.testing.assert_allclose(tip(continued['snapshots'][-1]), [0, 2.002, 0], atol=1e-10)
    with pytest.raises(AnalysisError, match='mesh'):
        solve_static(m, panels=custom([0, .2, .9, 1.7, 2]), gravity=[0, 0, 0], initial_state=saved)


def test_custom_mesh_harmonic_oscillator_recovers_analytic_transfer():
    m = parse_asw(Path('examples/instrumented-oscillator.asw').read_text())
    settings = custom([0, .03, .41, 1.61, 2])
    out = solve_frequency_response(m, FlightCondition(alpha=0, mach=0), settings,
        gravity=[0, 0, 0], frequencies=[0, 10, 30])
    for sample in out['samples']:
        w = sample['omega']; output = sample['responses'][0]['output']
        d = output['nodes'][-1]['displacement']; y = d['real'][1]+1j*d['imag'][1]
        assert y == pytest.approx(1/(500*(1+1j*.02*w)-2*w*w), abs=3e-11)
    assert out['base']['mesh_discretization']['settings'] == settings


def test_custom_mesh_preserves_nonzero_velocity_and_bdf_history_on_restart():
    m=parse_asw(Path('examples/instrumented-oscillator.asw').read_text())
    settings=custom([0,.03,.41,1.61,2]);c=FlightCondition(alpha=0,mach=0,powers={1:2})
    saved=solve_static(m,c,settings,gravity=[0,0,0])['equilibrium_state']
    out=launch_time(m,saved,duration=.03,dt=.01,forcing='time E1\n0 0\n.1 0\n')
    cp=checkpoint(out,2);assert np.linalg.norm(cp['state']['local_velocity'])>1e-4
    restarted=resume_time(m,json.loads(json.dumps(cp)),duration=.01)
    assert restarted['snapshots'][-1]['order']==2
    for field in ('local_velocity','local_acceleration'):
        np.testing.assert_allclose(restarted['snapshots'][-1][field],out['snapshots'][-1][field],atol=1e-11)
    np.testing.assert_allclose(tip(restarted['snapshots'][-1]),tip(out['snapshots'][-1]),atol=1e-11)


@pytest.mark.parametrize('settings', [True, 4.5, 3, 1025, custom(np.linspace(0,2,1026).tolist()), {'beams':{}}, {'default':4, 'extra':1},
    {'default':4, 'beams':{'7':{'count':4}}}, {'default':4, 'beams':{'1':{'spacing':'linear'}}},
    custom([0, .5, .5, 1, 2]), custom([0, .5, float('nan'), 1, 2]), custom([0, .5, 1, 1.5]),
    custom([.1, .5, 1, 1.5, 2]), custom([0, .5, 1, 1.5, 2.1]), custom([0, True, 1, 1.5, 2]),
    custom([0, .5, .5+1e-13, 1.5, 2]), {'default':4, 'beams':{'1':{'nodes':[0,.5,1,1.5,2],'count':4}}}])
def test_invalid_mesh_settings_fail_before_solving(settings):
    with pytest.raises(ValueError):
        dispatch(dict(action='inspect', source=model().dumps(), panels=settings))
