"""Physical normal-gravity output, without changing equilibrium equations."""
from copy import deepcopy
from types import SimpleNamespace

import numpy as np
import pytest

from openswing.asw import parse_asw
from openswing.source_discrete import solve_source_discrete
from openswing.source_recovery import source_static_distributed_gravity

POLICIES = ('drela-steady-zero-offset-v1', 'drela-steady-section-v1')


def fields(policy=POLICIES[1]):
    # The three intervals have unequal material lengths and signed loads.
    lengths = np.array([.5, 2., 4.])
    density = np.array([[0., 0., -2.], [1., -3., 4.], [0., 0., 5.]])
    angle = np.pi/3
    rotation = np.array([[1., 0., 0.], [0., np.cos(angle), -np.sin(angle)],
                         [0., np.sin(angle), np.cos(angle)]])
    frames = np.array([np.eye(3), rotation, rotation])
    n = SimpleNamespace(structural_operator=policy, meshes=[SimpleNamespace(length=lengths[:1]),
        SimpleNamespace(length=lengths[1:])])
    data = dict(condition=None, section_frame=frames,
                element_forces=np.repeat((density*lengths[:, None]/2)[:, None, :], 2, axis=1))
    return n, data, lengths, density


@pytest.mark.parametrize('policy', POLICIES)
def test_material_length_units_sign_and_physical_normal(policy):
    n, data, lengths, density = fields(policy)
    before = deepcopy(data)
    rows = source_static_distributed_gravity(n, data)
    np.testing.assert_array_equal([r['force_per_length'] for r in rows], density)
    np.testing.assert_allclose([r['normal'] for r in rows], [-2., 3*np.sqrt(3)/2+2., 2.5], atol=1e-14)
    np.testing.assert_allclose(np.sum(np.array([r['force_per_length'] for r in rows])*lengths[:, None], axis=0),
                               np.sum(data['element_forces'], axis=(0, 1)), atol=1e-14)
    for key in ('element_forces', 'section_frame'):
        np.testing.assert_array_equal(data[key], before[key])
    assert all('interval' in r['sample_location'] for r in rows)


def test_joint_rotation_of_force_and_frame_preserves_normal_component():
    n, data, _, _ = fields()
    original = source_static_distributed_gravity(n, data)
    # Independent right-handed 90-degree cyclic permutation of body axes.
    rotation = np.array([[0., 0., 1.], [1., 0., 0.], [0., 1., 0.]])
    data['element_forces'] = data['element_forces']@rotation.T
    data['section_frame'] = np.einsum('ij,njk->nik', rotation, data['section_frame'])
    rotated = source_static_distributed_gravity(n, data)
    np.testing.assert_allclose([r['normal'] for r in rotated], [r['normal'] for r in original], atol=1e-14)


@pytest.mark.parametrize('policy', ('midpoint-v1', 'drela-steady-coupled-v1',
    'drela-fixed-vacuum-v1', 'drela-moving-airflow-v1'))
def test_other_load_policies_remain_unavailable_without_reading_force_arrays(policy):
    assert source_static_distributed_gravity(SimpleNamespace(structural_operator=policy), {}) is None


def test_dynamic_or_airflow_fields_cannot_be_called_gravity():
    n, data, _, _ = fields(); n.source_dynamic = True
    assert source_static_distributed_gravity(n, data) is None
    n.source_dynamic = False; data['condition'] = object()
    assert source_static_distributed_gravity(n, data) is None


@pytest.mark.parametrize('bad', ('length', 'force', 'frame', 'mean_transform'))
def test_invalid_or_nonphysical_display_inputs_are_rejected(bad):
    n, data, _, _ = fields()
    if bad == 'length': n.meshes[0].length[0] = 0
    elif bad == 'force': data['element_forces'][0, 0, 0] = np.nan
    elif bad == 'frame': data['section_frame'] = data['section_frame'][:-1]
    else: data['section_frame'][0, 2, 2] = .8
    with pytest.raises(ValueError, match='Static gravity recovery'):
        source_static_distributed_gravity(n, data)


@pytest.mark.parametrize('policy', POLICIES)
def test_fresh_static_solution_uses_actual_gravity_and_excludes_point_loads(policy):
    model = parse_asw('''Name
Static gravity output
End
Unit
L 1 m
F 1 N
T 1 s
End
Constant
10 1.225 340
End
Reference
2 1 2
End
Ground
1 1 0
End
Weight
1 3 0 2 0 7
End
Beam 1
Cantilever
t x y z chord EA EIcc GJ EInn mg Dmg
1 0 0 0 .2 1000000 100000 100000 100000 2 -1
3 0 2 0 .2 1000000 100000 100000 100000 4 -1
End
''', beam_interpolation='drela-segspl-v1')
    gravity = np.array([2., -3., -4.]); point_force = np.array([1., 2., 3.])
    result = solve_source_discrete(model, panels={'default':4, 'beams':{'1':{'nodes':[1.,1.5,2.,2.5,3.]}}},
        gravity=gravity, loads=[dict(beam=1, t=3, force=point_force.tolist())],
        allow_signed_distributed_weights=True, structural_operator=policy, tolerance=1e-10)
    assert result['converged'] and result['residual'] < 1e-10
    np.testing.assert_allclose(result['applied_force'], 11*gravity/10+point_force, atol=1e-12)
    for e in result['elements']:
        # mg+Dmg = t, so the endpoint average is (t0+t1)/2 exactly.
        expected = (e['t0']+e['t1'])/2*gravity/10
        np.testing.assert_allclose(e['distributed_gravity']['force_per_length'], expected, atol=1e-14)
        assert e['distributed_gravity']['normal'] == pytest.approx(expected@np.array(e['physical_midpoint_frame'])[:, 2], abs=1e-14)
        assert all('distributed_gravity' not in trace for trace in e['endpoint_traces'])
    assert result['structure']['units']['distributed_load'] == 'input F / input L'
    assert result['structure']['distributed_gravity']['available'] is True
    assert 'Concentrated' in result['structure']['distributed_gravity']['excludes']
