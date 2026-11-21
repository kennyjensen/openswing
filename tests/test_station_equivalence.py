"""Exact source Weight-station equivalence; geometry only, no solves."""
import copy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from openswing.asw import Distribution, parse_asw, weight_station
from openswing.asw_edit import edit_distribution, model_data
from openswing.discretization import CURRENT_MESH_RECIPE, requirements
from openswing.equilibrium_state import identity, matching_identity
from openswing.geometry import attachment_geometry, model_meshes


def source(token='48', multiplier='.0254', adder='0', *, start='.0001', units='1 m', jump=False):
    stations = ('.0001 0 .0001 0 .2\n.6096 0 .6096 0 .2\n.6096 0 .7096 0 .2\n1.2192 0 1.3192 0 .2'
                if jump else f'{start} 0 {start} 0 .2\n1.2192 0 1.2192 0 .2')
    return f'''Name
Exact station fixture
End
Unit
L {units}
T 1 s
F 1 N
End
Constant
9.81 1.2256 340.21
End
Reference
1 .2 2.4384
0 0 0
End
Ground
1 {start} 0
End
Weight
* {multiplier}
+ {adder}
1 {token} 0 1.2192 0 1
End
Beam 1
Fixture
t x y z chord
{stations}
End
'''


def nodes(mesh):
    return np.r_[mesh.t0, mesh.t1[-1]]


def test_scaled_tip_unifies_only_analysis_coordinate_and_retains_raw_source_records():
    text = source(); model = parse_asw(text)
    row = model.records['weight'][0]
    old = row.copy(); data = copy.deepcopy(model_data(model))
    assert row[1] == 48*.0254 and row[1] != 1.2192
    assert weight_station(model, row) == 1.2192
    mesh, = model_meshes(model, 4)
    assert len(mesh.tm) == 4 and nodes(mesh)[-1] == 1.2192
    assert requirements(model)[1][-1] == {'t': 1.2192, 'kind': 'weight 1'}
    np.testing.assert_array_equal(row, old)
    assert model_data(model) == data and model.dumps() == text


@pytest.mark.parametrize('token,multiplier,adder', [
    ('48D0', '2.54D-2', '0'), ('4.8+1', '2.54-2', '0'),
    ('-48', '-.0254', '0'), ('36', '.0254', '.3048'), ('12', '.1', '.0192'),
])
def test_exact_products_adders_and_fortran_spelling(token, multiplier, adder):
    model = parse_asw(source(token, multiplier, adder))
    row = model.records['weight'][0]; original = row.copy()
    assert weight_station(model, row) == 1.2192
    assert nodes(model_meshes(model, 4)[0])[-1] == 1.2192
    np.testing.assert_array_equal(row, original)


@pytest.mark.parametrize('unit', ['1 m', '.3048 m', '1 ft'])
def test_station_equivalence_stays_in_input_units(unit):
    model = parse_asw(source(units=unit))
    assert weight_station(model, model.records['weight'][0]) == 1.2192
    assert nodes(model_meshes(model, 4)[0])[-1] == 1.2192
    assert model.units.declarations['L'][1] == unit.split()[1]


def test_mirrored_endpoint_and_negative_distribution_scaling():
    model = parse_asw(source('-48', start='0'))
    assert weight_station(model, model.records['weight'][0]) == -1.2192
    assert nodes(model_meshes(model, 4)[0])[0] == -1.2192
    text = source('-48').replace('1 .0001 0\nEnd\nWeight', '1 -.0001 0\nEnd\nWeight')
    text = text.replace('t x y z chord\n', 't x y z chord\n* -1 1 -1 1 1\n')
    model = parse_asw(text)
    assert model.beams[0].domain == (-1.2192, -.0001)
    assert weight_station(model, model.records['weight'][0]) == -1.2192
    assert nodes(model_meshes(model, 4)[0])[0] == -1.2192


def test_true_position_jump_and_its_right_side_are_preserved():
    model = parse_asw(source('24', jump=True))
    beam = model.beams[0]; row = model.records['weight'][0]
    assert row[1] != .6096 and weight_station(model, row) == .6096
    mesh, = model_meshes(model, 4)
    assert np.count_nonzero(nodes(mesh) == .6096) == 1
    left = np.flatnonzero(mesh.t1 == .6096)[0]; right = np.flatnonzero(mesh.t0 == .6096)[0]
    np.testing.assert_array_equal(mesh.r1[left], [0, .6096, 0])
    np.testing.assert_array_equal(mesh.r0[right], [0, .7096, 0])
    assert sum(beam.distributions['y'].t == .6096) == 2
    obj = next(o for o in attachment_geometry(model) if o['kind'] == 'weight')
    np.testing.assert_array_equal(obj['segments'][0][0], [0, .7096, 0])


@pytest.mark.parametrize('token,multiplier', [
    ('47.99999999999999', '.0254'), ('48.00000000000002', '.0254'),
    ('1.2191999999999998', '1'), ('1.2192000000000003', '1'),
])
def test_genuinely_distinct_decimal_station_is_not_merged(token, multiplier):
    model = parse_asw(source(token, multiplier))
    # A flexible beam cannot use the separate rigid-pylon reduction. This
    # isolates exact decimal aliasing from the new, explicitly tagged policy.
    beam = model.beams[0]
    beam.distributions['EIcc'] = Distribution('EIcc', np.array(beam.domain), np.full(2, 1e12), 1)
    row = model.records['weight'][0]
    assert weight_station(model, row) == row[1]
    with pytest.raises(ValueError, match='outside|too close'):
        model_meshes(model, 4)


def test_explicit_adjacent_user_nodes_still_fail_the_original_guard():
    model = parse_asw(source())
    # Interior nodes avoid the pre-existing endpoint/base-node snap rule.
    grid = [.0001, .3, .6, np.nextafter(.6, np.inf), 1.2192]
    with pytest.raises(ValueError, match='node stations are too close'):
        model_meshes(model, {'default': 4, 'beams': {'1': {'nodes': grid}}})


def test_distinct_decimal_that_already_rounds_to_endpoint_keeps_old_binary_behavior():
    model = parse_asw(source('48.00000000000001'))
    row = model.records['weight'][0]
    assert row[1] == 1.2192
    assert weight_station(model, row) == row[1]
    assert nodes(model_meshes(model, 4)[0])[-1] == row[1]


@pytest.mark.parametrize('change', ['record_copy', 'record_coordinate', 'beam_coordinate', 'distribution_replaced'])
def test_edited_or_replaced_station_data_cannot_use_stale_provenance(change):
    model = parse_asw(source()); row = model.records['weight'][0]
    if change == 'record_copy':
        model.records['weight'][0] = row.copy(); row = model.records['weight'][0]
    elif change == 'record_coordinate':
        row[1] = np.nextafter(row[1], -np.inf)
    elif change == 'beam_coordinate':
        model.beams[0].distributions['chord'].t[-1] = 1.3
    else:
        d = model.beams[0].distributions['chord']
        model.beams[0].distributions['chord'] = Distribution(d.name, d.t.copy(), d.values.copy(), d.line)
    assert weight_station(model, row) == row[1]


def test_deepcopy_canonical_export_and_unrelated_edit_keep_analysis_attachment():
    model = parse_asw(source()); raw = model.records['weight'][0].copy()
    copied = copy.deepcopy(model)
    assert weight_station(copied, copied.records['weight'][0]) == 1.2192
    canonical = model.dumps(canonical=True)
    restored = parse_asw(canonical)
    assert restored.records['weight'][0][1] == 1.2192
    np.testing.assert_array_equal(model.records['weight'][0], raw)
    np.testing.assert_array_equal(nodes(model_meshes(model, 4)[0]), nodes(model_meshes(restored, 4)[0]))
    edited = edit_distribution(model, 1, 'chord', multiplier=2.)
    assert edited.records['weight'][0][1] == 1.2192
    assert edited.beams[0].value('chord', .5) == .4
    np.testing.assert_array_equal(nodes(model_meshes(model, 4)[0]), nodes(model_meshes(edited, 4)[0]))


def _identity(model, stations):
    count = len(stations); ids = np.arange(count)
    network = SimpleNamespace(model=model, rj=model.beams[0].position(stations),
        a=ids[:-1], b=ids[1:], station_nodes={1: (stations, ids)}, constraints=[], ng=0,
        mesh_recipe=CURRENT_MESH_RECIPE, circulation_basis=SimpleNamespace(modes={}))
    return identity(network)


def test_saved_identity_keeps_source_hash_but_rejects_different_mesh_topology():
    model = parse_asw(source()); grid = nodes(model_meshes(model, 4)[0])
    current = _identity(model, grid)
    reopened = parse_asw(model.dumps())
    assert current == _identity(reopened, nodes(model_meshes(reopened, 4)[0]))
    assert current['model_sha256'] == hashlib.sha256(source().encode()).hexdigest()
    hypothetical_old = _identity(model, np.sort(np.r_[grid, model.records['weight'][0][1]]))
    assert not matching_identity(hypothetical_old, current)
    changed_source = parse_asw(model.dumps(canonical=True))
    assert not matching_identity(current, _identity(changed_source, nodes(model_meshes(changed_source, 4)[0])))


@pytest.mark.parametrize('variant', ['7d', '7e', '7f'])
def test_original_st4_tip_models_construct_without_changing_one_source_byte(variant):
    root = Path(__file__).resolve().parents[1]
    folder = root/'.reference/isae-validation/f62943df20e9e4d7d9f50e070477b22426b5f865/3 - Structure/CASE - ST4 Concentrated weight/Simulation_files'
    path = folder/f'Weight{variant}/{variant}_b48.asw'
    if not path.exists():
        pytest.skip('Optional original ISAE data are absent.')
    text = path.read_text(); model = parse_asw(text)
    original = [row.copy() for row in model.records['weight']]
    meshes = model_meshes(model, {'default': 32, 'beams': {'1': {'count': 32, 'spacing': 'uniform'}}})
    assert len(meshes) == 1 and len(meshes[0].tm) == 32
    assert nodes(meshes[0])[-1] == model.beams[0].domain[1] == 1.2192
    assert all(weight_station(model, row) == 1.2192 for row in model.records['weight'])
    for row, before in zip(model.records['weight'], original):
        np.testing.assert_array_equal(row, before)
    assert model.dumps() == text
    restored = parse_asw(model.dumps(canonical=True))
    np.testing.assert_array_equal(nodes(meshes[0]), nodes(model_meshes(restored, {'default': 32, 'beams': {'1': {'count': 32, 'spacing': 'uniform'}}})[0]))


def test_nonweight_attachment_and_unscaled_ordinary_model_are_unchanged():
    text = source().replace('Weight\n* .0254\n+ 0\n1 48 0 1.2192 0 1\nEnd\n',
                            'Strut\n* .0254\n1 48 0 1.2192 0 0 0 0 1 0\nEnd\n')
    model = parse_asw(text)
    assert requirements(model)[1][-1]['t'] == 48*.0254
    with pytest.raises(ValueError, match='too close'):
        model_meshes(model, 4)
    ordinary = parse_asw(source('1.2192', '1'))
    before = json.dumps(model_data(ordinary), sort_keys=True)
    model_meshes(ordinary, 4)
    assert json.dumps(model_data(ordinary), sort_keys=True) == before


@pytest.mark.parametrize('aerodynamic_field', [None, 6, 7])
def test_wall_root_weight_identity_matches_lossless_and_canonical_geometry(aerodynamic_field):
    from openswing.geometry import surface_frame
    from openswing.ground import GroundPlane
    from openswing.wall_root import WallRootBoundary
    text = source().replace('Ground\n1 .0001 0', 'Ground\n1 1.2192 0')
    original = parse_asw(text)
    if aerodynamic_field is not None:
        original.records['weight'][0][aerodynamic_field] = .1
    canonical = parse_asw(original.dumps(canonical=True))
    masks = []
    for model in (original, canonical):
        mesh, = model_meshes(model, 4)
        plane = GroundPlane(1, position=[0, -1.2192, 0], normal=[0, 1, 0])
        boundary = WallRootBoundary(plane, [mesh], model)
        frame = surface_frame(mesh.beam, mesh.t1, 'left')
        roots = boundary.surface(mesh, mesh.t1, mesh.r1, frame, 'left')
        assert roots[-1] and np.count_nonzero(roots) == 1
        masks.append(boundary.point_mask([model.records['weight'][0][2:5]]))
    np.testing.assert_array_equal(masks[0], masks[1])
    assert masks[0].tolist() == [aerodynamic_field is None]


@pytest.mark.parametrize('token,multiplier,adder', [
    ('48', '.0254', '0'),
    ('10000000000000001.2192', '1', '-10000000000000000'),
    ('1.2192', '1', '0'),
])
def test_network_and_local_motion_use_resolved_analysis_copy_without_a_distance_limit(token, multiplier, adder):
    from openswing.network import StaticNetwork
    from openswing.local_motion import NetworkMotion
    model = parse_asw(source(token, multiplier, adder))
    raw = model.records['weight'][0].copy()
    if token.startswith('1000'):
        assert raw[1] == 2.  # catastrophic cancellation, not a near-node case
    nets = [StaticNetwork(m, 4, None, [0, 0, 0], []) for m in
            (model, parse_asw(model.dumps(canonical=True)))]
    outputs = []
    for n in nets:
        np.testing.assert_array_equal(n.rj, nets[0].rj)
        assert n.weights[0][1] == 1.2192
        assert n.node(*n.weights[0][:2]) == n.nn-1
        r = n.rj + [.1, -.2, .05]
        q = np.tile(np.eye(3), (n.nn, 1, 1))
        fields = np.arange(12*n.nn, dtype=float).reshape(4, n.nn, 3)/100
        motion = NetworkMotion(n, r, q, *fields).point('weight', 0)
        outputs.append((n.point_positions(r, q), vars(motion)))
    np.testing.assert_array_equal(outputs[0][0], outputs[1][0])
    for key in outputs[0][1]:
        np.testing.assert_array_equal(outputs[0][1][key], outputs[1][1][key])
    np.testing.assert_array_equal(model.records['weight'][0], raw)
    assert model.dumps() == source(token, multiplier, adder)
    # Null-object filtering owns its list, while unchanged rows retain identity.
    assert (nets[0].weights[0] is model.records['weight'][0]) == (raw[1] == 1.2192)
