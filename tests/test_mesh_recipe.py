"""Saved meshes retain their original equations without relaxing identity checks."""
from copy import deepcopy
import json
from pathlib import Path

import numpy as np
import pytest

from openswing.aero import AnalysisError
from openswing.asw import parse_asw
from openswing.discretization import CURRENT_MESH_RECIPE, CHORDAL_MESH_RECIPE, LEGACY_MESH_RECIPE
from openswing.equilibrium_state import (
    capture, identity, matching_identity, recipe_from_identity, restore,
    warm_start_recipe,
)
from openswing.geometry import mesh_beam, model_meshes, undeformed_mesh
from openswing.network import StaticNetwork, exp, solve_static
from openswing.time_initialization import launch_time
from openswing.time_state import checkpoint, restore_checkpoint
from test_network import model


BEAM = '''Beam 1
Curved massive beam with a reporting-only break
t x y z
0 0 0 0
.5 .1 .5 .12
1.2 .35 1.2 .5
2 .8 2 1.3
t twist
0 0
.9 12
.9 12
2 23
t mg mgcc mgnn
0 1 .1 .1
2 1 .1 .1
t Cshell
0 .1
.43 .1
.43 .2
2 .2
End
'''
LOADS = [dict(beam=1, t=1.1, force=[0., 0., 0.])]
MESH_FIELDS = ('t0', 't1', 'tm', 'ts', 'r0', 'r1', 'rm', 'frames', 'length', 'theta')


def aircraft(*, lifting=False):
    source = BEAM.replace('End\n', 't chord\n0 .5\n2 .5\nEnd\n') if lifting else BEAM
    return model(source)


def original_all_break_mesh(beam, panels=4, stations=(), *, shell=True):
    """Literal pre-recipe construction, independent of current break helpers.

    This deliberately includes every distribution break in both arc quadrature
    and mandatory nodes. The curved geometry detects changing only one of them.
    """
    lo, hi = beam.domain
    breaks = []
    for name, distribution in beam.distributions.items():
        if not shell and name in {'Cshell', 'Nshell', 'Atshell'}:
            continue
        breaks.extend(distribution.breaks)
        if beam.lifting and distribution.t[0] == 0:
            breaks.extend(-distribution.breaks)
            breaks.append(0.)
    breaks = np.array(sorted({float(t) for t in breaks if lo < t < hi}))
    dense_t = np.unique(np.r_[np.linspace(lo, hi, 2049), breaks])
    intervals = beam.position(dense_t[1:], side='left') - beam.position(dense_t[:-1], side='right')
    arc = np.r_[0., np.cumsum(np.linalg.norm(intervals, axis=1))]
    fraction = np.linspace(0, 1, panels + 1)
    s = arc[-1] * ((1 - np.cos(np.pi * fraction)) / 2)
    base_nodes = np.interp(s, arc, dense_t)
    required = np.unique(np.r_[breaks, stations])
    for point in required:
        base_nodes[np.abs(base_nodes - point) < 1e-11 * (hi - lo)] = point
    nodes = np.unique(np.r_[base_nodes, required])
    ns = np.interp(nodes, dense_t, arc)
    angle = np.arccos(np.clip(1 - 2 * ns / arc[-1], -1, 1))
    sm = arc[-1] * (1 - np.cos((angle[:-1] + angle[1:]) / 2)) / 2
    tm = np.interp(sm, arc, dense_t)
    r0 = beam.position(nodes[:-1], side='right')
    r1 = beam.position(nodes[1:], side='left')
    rm = r0 + ((sm - ns[:-1]) / np.diff(ns))[:, None] * (r1 - r0)
    ts = np.interp((ns[:-1] + ns[1:]) / 2, arc, dense_t)
    tangent = beam.position(tm, derivative=1)
    tangent = tangent / np.linalg.norm(tangent, axis=-1, keepdims=True)
    if beam.lifting:
        phi = np.arctan2(tangent[:, 2], tangent[:, 1])
        psi = -np.arcsin(np.clip(tangent[:, 0], -1, 1))
        c0 = np.stack([np.cos(psi), np.sin(psi)*np.cos(phi), np.sin(psi)*np.sin(phi)], axis=-1)
        n0 = np.stack([np.zeros_like(phi), -np.sin(phi), np.cos(phi)], axis=-1)
    else:
        phi = np.arcsin(np.clip(tangent[:, 2], -1, 1))
        psi = np.arctan2(-tangent[:, 0], tangent[:, 1])
        c0 = np.stack([np.cos(psi), np.sin(psi), np.zeros_like(phi)], axis=-1)
        n0 = np.stack([np.sin(psi)*np.sin(phi), -np.cos(psi)*np.sin(phi), np.cos(phi)], axis=-1)
    twist = np.deg2rad(beam.value('twist', tm))[:, None]
    frames = np.stack([c0*np.cos(twist) - n0*np.sin(twist), tangent,
                       c0*np.sin(twist) + n0*np.cos(twist)], axis=-1)
    return dict(t0=nodes[:-1], t1=nodes[1:], tm=tm, ts=ts, r0=r0, r1=r1,
                rm=rm, frames=frames, length=np.diff(ns), theta=np.pi-angle)


@pytest.mark.parametrize('lifting', [False, True])
@pytest.mark.parametrize('recipe', [LEGACY_MESH_RECIPE, CHORDAL_MESH_RECIPE])
def test_legacy_mesh_exactly_reproduces_original_curved_all_break_recipe(lifting, recipe):
    m = aircraft(lifting=lifting)
    beam = m.beams[0]
    old = original_all_break_mesh(beam, stations=[0., 1.1], shell=recipe == LEGACY_MESH_RECIPE)
    legacy = mesh_beam(beam, 4, [0., 1.1], mesh_recipe=recipe)
    through_model = model_meshes(m, 4, LOADS, mesh_recipe=recipe)[0]
    for field in MESH_FIELDS:
        np.testing.assert_array_equal(getattr(legacy, field), old[field], err_msg=field)
        np.testing.assert_array_equal(getattr(through_model, field), old[field], err_msg=field)
    current = model_meshes(m, 4, LOADS)[0]
    assert legacy.mesh_recipe == through_model.mesh_recipe == recipe
    assert current.mesh_recipe == CURRENT_MESH_RECIPE
    assert (.43 in np.r_[legacy.t0, legacy.t1[-1]]) == (recipe == LEGACY_MESH_RECIPE)
    assert .43 not in np.r_[current.t0, current.t1[-1]]
    assert .9 in current.t0 and 1.1 in current.t0
    if lifting:
        assert (-.43 in legacy.t0) == (recipe == LEGACY_MESH_RECIPE)
        assert -.43 not in current.t0


@pytest.mark.parametrize('recipe', [LEGACY_MESH_RECIPE, CHORDAL_MESH_RECIPE, CURRENT_MESH_RECIPE])
def test_deformation_and_jig_recovery_keep_recipe_and_material_geometry(recipe):
    n = StaticNetwork(aircraft(), 4, None, [0, 0, 0], LOADS, mesh_recipe=recipe)
    # A nonuniform displacement and rotation exercise the deformed mesh path.
    r = n.rj.copy()
    r[:, 0] += .01 * r[:, 1]**2
    rotations = np.zeros_like(r)
    rotations[:, 2] = .04 * r[:, 1]
    q = exp(rotations)
    deformed = n.deformed_meshes(r, q, n.geometry(r, q))[0]
    assert deformed.mesh_recipe == recipe
    assert np.max(abs(deformed.r0 - n.meshes[0].r0)) > .001
    recovered = undeformed_mesh(deformed)
    assert recovered.mesh_recipe == recipe
    for field in MESH_FIELDS:
        np.testing.assert_allclose(getattr(recovered, field), getattr(n.meshes[0], field),
                                   rtol=0, atol=2e-14, err_msg=field)


@pytest.fixture(scope='module', params=[LEGACY_MESH_RECIPE, CHORDAL_MESH_RECIPE, CURRENT_MESH_RECIPE])
def saved_equilibrium(request):
    recipe = request.param
    m = aircraft()
    n = StaticNetwork(m, 4, None, [0, 0, 0], LOADS, mesh_recipe=recipe)
    # The unloaded jig is an exact equilibrium. Explicit legacy construction
    # manufactures an old packet without relabelling a new mesh or its fields.
    saved = json.loads(json.dumps(capture(n, np.zeros(n.size), residual=0.)))
    return m, n, saved, recipe


def check_recipe_identity(saved_identity, recipe):
    assert recipe_from_identity(saved_identity) == recipe
    if recipe == LEGACY_MESH_RECIPE:
        assert 'mesh_recipe' not in saved_identity
    else:
        assert saved_identity['mesh_recipe'] == recipe


def test_capture_and_warm_steady_preserve_old_or_new_mesh(saved_equilibrium):
    m, n, saved, recipe = saved_equilibrium
    before = deepcopy(saved)
    check_recipe_identity(saved['identity'], recipe)
    old_keys = {'model_sha256', 'nodes', 'elements', 'stations', 'constraints', 'circulation_count'}
    assert set(saved['identity']) == old_keys | ({'mesh_recipe'} if recipe != LEGACY_MESH_RECIPE else set())
    assert warm_start_recipe(m, 4, saved) == recipe
    assert warm_start_recipe(m, 4, None) == CURRENT_MESH_RECIPE
    assert matching_identity(saved['identity'], identity(n))
    np.testing.assert_array_equal(restore(n, saved), np.zeros(n.size))
    out = solve_static(m, panels=4, gravity=[0, 0, 0], loads=LOADS, initial_state=saved)
    assert out['converged'] and out['residual'] < 1e-10
    assert out['equilibrium_initialization']['initialization'] == 'saved physical equilibrium'
    assert out['equilibrium_state']['identity'] == saved['identity']
    check_recipe_identity(out['equilibrium_state']['identity'], recipe)
    assert saved == before


def test_empty_override_representation_keeps_the_same_requested_mesh(saved_equilibrium):
    m, _, saved, recipe = saved_equilibrium
    equivalent = {'default': 4, 'beams': {}}
    assert warm_start_recipe(m, equivalent, saved) == recipe
    out = solve_static(m, panels=equivalent, gravity=[0, 0, 0], loads=LOADS, initial_state=saved)
    assert out['equilibrium_state']['identity'] == saved['identity']
    old = deepcopy(saved)
    old['launch']['panels'] = equivalent
    assert warm_start_recipe(m, 4, old) == recipe


@pytest.fixture(scope='module', params=[2, 5], ids=['bdf2', 'radau'])
def saved_time(saved_equilibrium, request):
    m, n, saved, recipe = saved_equilibrium
    before = deepcopy(saved)
    out = launch_time(m, saved, duration=.02, dt=.01, order=request.param,
                      forcing='time Ay\n0 .2\n.03 .2', tolerance=1e-9)
    assert saved == before
    return m, n, saved, recipe, out


def test_saved_launch_and_accepted_bdf_radau_replay_use_original_recipe(saved_time):
    m, original_network, saved, recipe, out = saved_time
    assert out['initialization']['equilibrium_recomputed'] is False
    assert out['accepted_steps'] == 2 and out['rejected_steps'] == 0
    # Exercise a nonzero accepted response, including method-owned old inputs.
    np.testing.assert_allclose(out['snapshots'][-1]['frame']['velocity_origin_body'],
                               [0., .004, 0.], atol=2e-10, rtol=0)
    initial = checkpoint(out, 0)
    final = checkpoint(out)
    assert final['accepted_method']['kind'] in ('bdf', 'radau_iia')
    if final['accepted_method']['kind'] == 'bdf':
        assert final['accepted_method']['effective_order'] == 2
        assert final['older'] is not None
    for packet in (initial, final):
        before = deepcopy(packet)
        check_recipe_identity(packet['context']['identity'], recipe)
        check_recipe_identity(packet['accepted_method']['accepted_inputs']['identity'], recipe)
        assert packet['context']['identity'] == saved['identity']
        restored = restore_checkpoint(m, packet)
        n = restored[0]
        assert n.mesh_recipe == recipe
        assert n.panels == 4 and n.nn == original_network.nn
        for field in MESH_FIELDS:
            np.testing.assert_array_equal(getattr(n.meshes[0], field),
                                          getattr(original_network.meshes[0], field))
        assert restored[6] < 1e-8
        assert restored[7]['acceptance_validation']['discrete_replayed'] == (packet is final)
        assert packet == before


@pytest.mark.parametrize('panels', [
    5,
    {'default': 4, 'beams': {'1': {'count': 4, 'spacing': 'uniform'}}},
    {'default': 4, 'beams': {'1': {'nodes': [0., .4, .8, 1.4, 2.]}}},
], ids=['count', 'spacing', 'explicit-nodes'])
def test_saved_recipe_never_overrides_requested_mesh(saved_equilibrium, panels):
    m, _, saved, _ = saved_equilibrium
    before = deepcopy(saved)
    with pytest.raises(AnalysisError, match='mesh'):
        solve_static(m, panels=panels, gravity=[0, 0, 0], loads=LOADS, initial_state=saved)
    assert saved == before


@pytest.mark.parametrize('change', ['model', 'attachment', 'identity-node', 'identity-topology'])
def test_saved_mesh_does_not_relax_aircraft_attachment_or_identity_checks(saved_equilibrium, change):
    m, _, original, _ = saved_equilibrium
    saved = deepcopy(original)
    loads = deepcopy(LOADS)
    if change == 'model':
        m = model(BEAM.replace('.8 2 1.3', '.8 2 1.31'))
    elif change == 'attachment':
        loads.append(dict(beam=1, t=1.17, force=[0., 0., 0.]))
    elif change == 'identity-node':
        saved['identity']['nodes'][-1][0] += 1e-8
    else:
        saved['identity']['elements'][0][1] += 1
    with pytest.raises(AnalysisError, match='mesh'):
        solve_static(m, panels=4, gravity=[0, 0, 0], loads=loads, initial_state=saved)


@pytest.mark.parametrize('bad_identity', [None, [], 'physical-breaks-v1',
    {'mesh_recipe': 'future-recipe'}, {'mesh_recipe': None}, {'mesh_recipe': []}])
def test_malformed_identity_and_unknown_recipe_fail_explicitly(saved_equilibrium, bad_identity):
    m, _, original, _ = saved_equilibrium
    saved = deepcopy(original)
    saved['identity'] = deepcopy(bad_identity)
    with pytest.raises(AnalysisError, match='[Ii]dentity|recipe'):
        solve_static(m, panels=4, gravity=[0, 0, 0], loads=LOADS, initial_state=saved)


@pytest.mark.parametrize('location', ['context', 'accepted-inputs'])
def test_checkpoint_recipe_cannot_be_relabelled_independently(saved_time, location):
    m, _, _, recipe, out = saved_time
    saved = checkpoint(out)
    if location == 'context':
        target = saved['context']['identity']
    else:
        target = saved['accepted_method']['accepted_inputs']['identity']
    if recipe == LEGACY_MESH_RECIPE:
        target['mesh_recipe'] = CURRENT_MESH_RECIPE
    else:
        target.pop('mesh_recipe')
    with pytest.raises(AnalysisError, match='mesh|identity'):
        restore_checkpoint(m, saved)


@pytest.mark.parametrize('recipe', ['future-recipe', None, []])
def test_unknown_requested_mesh_recipe_is_rejected(recipe):
    m = aircraft()
    with pytest.raises(ValueError, match='recipe'):
        model_meshes(m, 4, mesh_recipe=recipe)
    with pytest.raises((ValueError, AnalysisError), match='recipe'):
        StaticNetwork(m, 4, None, [0, 0, 0], (), mesh_recipe=recipe)


@pytest.mark.parametrize('name,recipe', [('legacy', LEGACY_MESH_RECIPE), ('current', CHORDAL_MESH_RECIPE)])
def test_frozen_historical_packets_keep_exact_geometry_and_identity(name, recipe):
    # These are immutable fixtures produced before the accurate-arc change.
    path = Path(__file__).parent/'fixtures'/'mesh-recipe'/f'{name}.json'
    saved = json.loads(path.read_text())
    m = parse_asw((path.parent/'curved-shell.asw').read_text())
    assert saved['recipe'] == recipe
    assert warm_start_recipe(m, saved['panels'], saved['equilibrium']) == recipe
    n = StaticNetwork(m, saved['panels'], None, [0, 0, 0], saved['loads'], mesh_recipe=recipe)
    assert identity(n) == saved['equilibrium']['identity']
    np.testing.assert_array_equal(restore(n, saved['equilibrium']), np.zeros(n.size))
    for field in MESH_FIELDS:
        np.testing.assert_array_equal(getattr(n.meshes[0], field), saved['mesh'][field])
