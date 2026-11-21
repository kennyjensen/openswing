"""Core settings: physical-beam exemption, spacing floor, current geometry and restart."""
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
import runpy
import numpy as np
import pytest
from openswing.aero import FlightCondition, solve_rigid, evaluate_aerodynamics
from openswing.asw import parse_asw
from openswing.geometry import model_meshes
from openswing.flow_survey import survey
from openswing.network import solve_static
from openswing.time_initialization import launch_time
from openswing.time_state import checkpoint, resume_time, read_condition

HELPERS = runpy.run_path('scripts/verify-wake-core.py')


@pytest.mark.parametrize('value', [None, True, False, -.1, float('nan'), float('inf'), '0.25', [], {}, 10**1000])
def test_core_ratio_rejects_invalid_values_at_public_and_instantaneous_entries(value):
    model = parse_asw(Path('examples/wake-interaction.asw').read_text())
    c = FlightCondition(wake_core_ratio=value)
    with pytest.raises(ValueError, match='Wake core radius/chord'):
        solve_rigid(model, c, 4)
    with pytest.raises(ValueError, match='Wake core radius/chord'):
        evaluate_aerodynamics(model, c, model_meshes(model, 4))
    assert read_condition({'speed': 30}).wake_core_ratio == .25


def test_effective_core_overflow_is_diagnosed_without_arbitrary_ratio_cap():
    model = parse_asw(Path('examples/wake-interaction.asw').read_text())
    for r in [1e155, 1e308]:
        with pytest.raises(ValueError, match='Wake core radius is too large'):
            solve_rigid(model, FlightCondition(wake_core_ratio=r), 4)
    for r in [0., 1e-200, 20.]:
        assert solve_rigid(model, FlightCondition(wake_core_ratio=r), 4)['converged']


@pytest.mark.parametrize('ratio,mach,ground', [(0., 0., 0), (1., .6, 1), (.25, .6, -1)])
def test_interacting_surfaces_and_external_sensors_match_independent_line_integrals(ratio, mach, ground):
    spec = dict(panels=4, ratio=ratio, mach=mach, ground=ground)
    actual, reference = HELPERS['compute'](spec), HELPERS['independent'](spec)
    np.testing.assert_allclose(HELPERS['physical'](actual), HELPERS['physical'](reference), rtol=3e-11, atol=3e-11)


def test_same_physical_surface_ignores_core_even_when_split_into_logical_beams():
    source = Path('examples/rectangular.asw').read_text().split('t dCLdF1')[0]+'End\n'
    # Separate logical halves with one physical index. No doubled center panel.
    source = source.split('Beam 1')[0]
    for index, lo, hi in [(1, -6, 0), (2, 0, 6)]:
        source += f'Beam {index} 7\nHalf {index}\nt x y z chord Xax\n{lo} 0 {lo} 0 1 .25\n{hi} 0 {hi} 0 1 .25\nEnd\n'
    model = parse_asw(source)
    before = solve_rigid(model, FlightCondition(mach=0, wake_core_ratio=0), 4)
    after = solve_rigid(model, FlightCondition(mach=0, wake_core_ratio=2), 4)
    for key in ['force', 'moment', 'CL', 'CD', 'CDi', 'circulation_local_residual']:
        np.testing.assert_array_equal(before[key], after[key])
    np.testing.assert_array_equal([s['circulation'] for s in before['strips']], [s['circulation'] for s in after['strips']])


def test_spacing_floor_and_current_interval_lengths_control_the_core():
    model = parse_asw(Path('examples/wake-interaction.asw').read_text())
    c = FlightCondition(alpha=0, mach=0, stall=False, wake_core_ratio=0)
    meshes = model_meshes(model, 4)
    zero = evaluate_aerodynamics(model, c, meshes)
    small = evaluate_aerodynamics(model, replace(c, wake_core_ratio=.01), meshes)
    for key in ['force', 'moment', 'circulation_local_residual']:
        np.testing.assert_array_equal(zero[key], small[key])
    # A stretched current configuration, with the material stations unchanged.
    scale = np.array([1., 2., 1.])
    stretched = [replace(m, r0=m.r0*scale, r1=m.r1*scale, rm=m.rm*scale, length=m.length*2) for m in meshes]
    actual = evaluate_aerodynamics(model, replace(c, wake_core_ratio=.25), stretched)
    expected = np.concatenate([np.maximum(.25*m.beam.value('chord', m.tm), 2*m.length) for m in meshes])
    np.testing.assert_allclose([s['wake_core_radius'] for s in actual['strips']], expected, rtol=1e-15)


def test_saved_equilibrium_time_restart_and_flow_keep_the_selected_core():
    model = parse_asw(Path('examples/wake-interaction.asw').read_text())
    c = FlightCondition(alpha=0, mach=0, stall=False, wake_core_ratio=1.)
    base = solve_static(model, c, 4, gravity=[0, 0, 0])
    saved = deepcopy(base['equilibrium_state']); original = deepcopy(saved)
    assert saved['launch']['condition']['wake_core_ratio'] == 1.
    field = survey(model, positions=HELPERS['POINTS'], equilibrium_state=saved)
    expected = HELPERS['independent'](dict(panels=4, ratio=1.))
    np.testing.assert_allclose(field['velocity']['lifting'], expected['field'], atol=1e-10)
    assert field['wake_core']['ratio'] == 1.
    history = launch_time(model, saved, duration=.02, dt=.01)
    resumed = resume_time(model, checkpoint(history, 1), duration=.01)
    for s in history['snapshots']+resumed['snapshots']:
        assert s['wake_core']['ratio'] == 1.
        np.testing.assert_allclose(s['force'], base['force'], rtol=2e-9, atol=1e-8)
    np.testing.assert_allclose([s['circulation'] for s in resumed['snapshots'][-1]['strips']],
        [s['circulation'] for s in history['snapshots'][-1]['strips']], atol=1e-10)
    assert saved == original
    # Reusing the geometry as a steady seed must solve the new core equations.
    changed = solve_static(model, replace(c, wake_core_ratio=.25), 4, gravity=[0, 0, 0], initial_state=saved)
    fresh = solve_static(model, replace(c, wake_core_ratio=.25), 4, gravity=[0, 0, 0])
    np.testing.assert_allclose(changed['force'], fresh['force'], atol=1e-8)
    assert np.linalg.norm(np.array(base['force'])-fresh['force']) > 1.
