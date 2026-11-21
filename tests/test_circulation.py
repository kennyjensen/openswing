"""Fourier circulation: continuum, full-basis, dynamics and restart checks."""
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
import json
import numpy as np
import pytest
from openswing.aero import FlightCondition, solve_rigid, evaluate_aerodynamics, AnalysisError
from openswing.asw import parse_asw
from openswing.circulation import CirculationBasis
from openswing.geometry import mesh_beam
from openswing.network import StaticNetwork, solve_static
from openswing.linear_dynamics import make_system, linearize, eigensystem
from openswing.time_integration import solve_time
from openswing.time_state import checkpoint, resume_time
from openswing.time_initialization import launch_time

SOURCE = Path('examples/rectangular.asw').read_text()


def test_material_glauert_basis_retains_orientation_under_elastic_stretch():
    model = parse_asw(SOURCE); condition = FlightCondition(circulation_modes={1: 3})
    n = StaticNetwork(model, 8, condition, [0, 0, 0], ())
    assert n.ng == 3 < n.circulation_basis.panels
    q = np.broadcast_to(np.eye(3), (n.nn, 3, 3)); r = n.rj.copy(); r[:, 1] *= 1.1
    deformed = n.deformed_meshes(r, q, n.geometry(r, q))
    basis = CirculationBasis(deformed, {'1': 3})
    np.testing.assert_array_equal(basis.sample, n.circulation_basis.sample)
    theta = np.array(basis.beams[0]['theta_midpoint'])
    # Positive second coefficient gives negative lift on the negative-y side.
    gamma = basis.decode(np.array([2., 3., -.4]))
    np.testing.assert_allclose(gamma, 2*np.sin(theta)+3*np.sin(2*theta)-.4*np.sin(3*theta), atol=1e-14)
    np.testing.assert_allclose(basis.encode(gamma), [2., 3., -.4], atol=1e-14)


@pytest.mark.parametrize('alpha,control', [(7., 3.), (25., 0.), (-25., -2.)])
def test_complete_fourier_basis_reproduces_pointwise_attached_and_stalled_loads(alpha, control):
    model = parse_asw(SOURCE); mesh = mesh_beam(model.beams[0], 8)
    condition = FlightCondition(alpha=alpha, beta=4., mach=.2, controls={1: control})
    point = solve_rigid(model, condition, 8)
    fourier = solve_rigid(model, replace(condition, circulation_modes={1: len(mesh.tm)}), 8)
    for key in ('force', 'moment', 'CL', 'CD', 'CDi', 'efficiency'):
        np.testing.assert_allclose(fourier[key], point[key], rtol=1e-8, atol=1e-8)
    np.testing.assert_allclose([s['circulation'] for s in fourier['strips']], [s['circulation'] for s in point['strips']], rtol=1e-8, atol=1e-8)
    assert max(abs(np.array(fourier['circulation_local_residual']))) < 1e-8


def test_one_mode_elliptic_wing_matches_prandtl_continuum_and_separates_local_defect():
    span = 80.; ts = np.linspace(-span/2, span/2, 201)
    chord = np.maximum(np.sqrt(1-(2*ts/span)**2), 1e-5)
    source = f'Name\nElliptic Fourier check\nEnd\nUnit\nL 1 m\nT 1 s\nF 1 N\nEnd\nConstant\n9.80665 1.225 340.294\nEnd\nReference\n{np.pi*span/4} 1 {span}\nEnd\nBeam 1\nWing\nt y chord Xax\n'
    source += '\n'.join(f'{t} {t} {c} .25' for t,c in zip(ts,chord))+'\nEnd\n'
    model = parse_asw(source)
    r = solve_rigid(model, FlightCondition(alpha=.1, mach=0., stall=False, circulation_modes={1: 1}), 96)
    exact = 2*np.pi/(1+2/(span**2/model.reference[0, 0]))
    assert r['CL']/np.deg2rad(.1) == pytest.approx(exact, rel=.01)
    assert r['efficiency'] == pytest.approx(1., abs=1e-10)
    assert len(r['circulation_residual']) == 1 and r['residual'] < 1e-10
    assert max(abs(np.array(r['circulation_local_residual']))) > 1e-7


def test_generalized_wake_lag_has_only_the_selected_circulation_modes():
    source = SOURCE[:SOURCE.index('t dCLdF1')]+'End\n'
    source = source.replace('6 0 6 0','100000 0 100000 0').replace('6 .008','100000 .008').replace('.008','0').replace('12 1 12','200000 1 200000')
    condition = FlightCondition(speed=30., alpha=0., mach=0., stall=False, circulation_modes={1: 3})
    system, _ = make_system(parse_asw(source), condition, 8, gravity=[0, 0, 0])
    a, m = linearize(system)
    modes, meta = eigensystem(a, m, time_scale=system.W, count=10)
    assert meta['finite_dimension'] == len(modes) == 3
    # Uniform infinite-span section: Gamma_dot + V/(2c) Gamma = forcing.
    np.testing.assert_allclose([complex(*v['eigenvalue']) for v in modes], -15., rtol=2e-4, atol=1e-7)


def test_fourier_harmonic_gust_recovers_independent_section_lag_and_rate_lift():
    from openswing.frequency_response import solve_frequency_response
    source = SOURCE[:SOURCE.index('t dCLdF1')]+'End\n'
    source = source.replace('6 0 6 0','100000 0 100000 0').replace('6 .008','100000 .008').replace('.008','0').replace('12 1 12','200000 1 200000')
    condition = FlightCondition(speed=30., alpha=0., mach=0., stall=False, circulation_modes={1: 3})
    result = solve_frequency_response(parse_asw(source), condition, 8, gravity=[0, 0, 0], frequencies=[0., 3., 30.], inputs=[dict(kind='gust', wave='uniform')])
    for sample in result['samples']:
        omega = sample['omega']; value = sample['responses'][0]['output']['global']['CL']
        exact = 2*np.pi/30*(1+1j*omega/30)/(1+2j*omega/30)
        assert complex(value['real'], value['imag']) == pytest.approx(exact, rel=2e-4)


def test_mixed_pointwise_and_fourier_surfaces_retain_cross_surface_interaction():
    source = SOURCE
    tail = SOURCE[SOURCE.index('Beam 1'):].replace('Beam 1','Beam 2').replace('0 0 0 0 1 .25','0 4 0 2 1 .25').replace('6 0 6 0 1 .25','6 4 6 2 1 .25')
    model = parse_asw(source+'\n'+tail)
    p = len(mesh_beam(model.beams[0], 8).tm)
    condition = FlightCondition(alpha=5., mach=0., stall=False)
    point = solve_rigid(model, condition, 8)
    full = solve_rigid(model, replace(condition, circulation_modes={1: p}), 8)
    np.testing.assert_allclose(full['force'], point['force'], rtol=1e-10, atol=1e-9)
    short = solve_rigid(model, replace(condition, circulation_modes={1: 3}), 8)
    assert short['circulation_discretization']['independent_unknowns'] == p+3
    assert [b['representation'] for b in short['circulation_discretization']['beams']] == ['fourier', 'pointwise']
    assert short['residual'] < 1e-10


def test_fourier_saved_equilibrium_launch_and_bdf_checkpoint_preserve_physical_circulation():
    model = parse_asw(SOURCE)
    condition = FlightCondition(speed=20., alpha=3., mach=0., circulation_modes={1: 3})
    base = solve_static(model, condition, 4, gravity=[0, 0, 0])
    saved = json.loads(json.dumps(base['equilibrium_state'])); original = deepcopy(saved)
    warm = solve_static(model, condition, 4, gravity=[0, 0, 0], initial_state=saved)
    assert warm['CL'] == pytest.approx(base['CL'], abs=1e-12)
    trajectory = launch_time(model, saved, duration=.04, dt=.01, forcing='time +F1\n0 0\n.02 2\n.04 2\n')
    continued = resume_time(model, checkpoint(trajectory, 2), duration=.02)
    for actual, expected in zip(continued['snapshots'], trajectory['snapshots'][2:]):
        np.testing.assert_allclose(actual['circulation_rate'], expected['circulation_rate'], atol=2e-8)
        np.testing.assert_allclose([s['circulation'] for s in actual['strips']], [s['circulation'] for s in expected['strips']], atol=2e-8)
        assert len(actual['circulation_rate']) == actual['lifting_panels'] > 3
        assert len(actual['circulation_residual']) == 3
    assert saved == original
    for other in ({1: 2}, {}):
        with pytest.raises(AnalysisError, match='mesh'):
            solve_static(model, replace(condition, circulation_modes=other), 4, gravity=[0, 0, 0], initial_state=saved)


@pytest.mark.parametrize('modes', [{1: -1}, {1: 2.5}, {1: True}, {1: 1000000000}, {2: 2}, {'1.5': 1}])
def test_invalid_or_unresolvable_mode_requests_are_rejected_before_solving(modes):
    with pytest.raises(ValueError):
        solve_rigid(parse_asw(SOURCE), FlightCondition(circulation_modes=modes), 4)


def test_supplied_circulation_and_rate_must_belong_to_selected_space():
    model = parse_asw(SOURCE); mesh = mesh_beam(model.beams[0], 8)
    condition = FlightCondition(circulation_modes={1: 1})
    for kwargs in (dict(circulation=np.ones(len(mesh.tm))), dict(circulation_rate=np.ones(len(mesh.tm)))):
        with pytest.raises(ValueError, match='outside'):
            evaluate_aerodynamics(model, condition, [mesh], **kwargs)
    basis = CirculationBasis([mesh], {1: 3})
    with pytest.raises(ValueError, match='cannot change'):
        evaluate_aerodynamics(model, condition, [mesh], circulation_basis=basis)


def test_controller_equilibrium_keeps_the_reduced_circulation_coordinates():
    model = parse_asw(SOURCE); condition = FlightCondition(alpha=4., mach=0., circulation_modes={1: 3})
    controller = dict(outputs=[dict(actuator='F1', expression='2')])
    closed = solve_static(model, condition, 4, gravity=[0, 0, 0], controller=controller)
    prescribed = solve_static(model, replace(condition, controls={1: 2.}), 4, gravity=[0, 0, 0])
    np.testing.assert_allclose(closed['force'], prescribed['force'], atol=1e-8)
    system, _ = make_system(model, condition, 4, gravity=[0, 0, 0], controller=controller,
                            initial_state=closed['equilibrium_state'])
    assert system.network.ng == 3
    assert system.base_report()['modal_base']['continuous_residual'] < 1e-8


def test_all_mode_rom_with_fourier_circulation_reproduces_full_harmonic_response():
    from openswing.reduced_model import solve_reduced_model
    model = parse_asw(Path('examples/heave-pitch.asw').read_text()+'\nSensor\n1 2 0 0 0 1\nEnd\n')
    condition = FlightCondition(speed=50., alpha=0., mach=0., stall=False, circulation_modes={2: 1})
    r = solve_reduced_model(model, condition, 4, gravity=[0, 0, 0], count=20,
        inputs=[dict(kind='gust', wave='uniform')], outputs=['RZ[1]'], frequencies=[.5, 20., 60.])
    assert len(r['matrices']['A']) == 5
    for sample in r['samples']:
        actual = np.array(sample['reduced']['real'])+1j*np.array(sample['reduced']['imag'])
        full = np.array(sample['full']['real'])+1j*np.array(sample['full']['imag'])
        assert np.max(abs(full)) > 1e-8
        np.testing.assert_allclose(actual, full, rtol=2e-7, atol=1e-8)
