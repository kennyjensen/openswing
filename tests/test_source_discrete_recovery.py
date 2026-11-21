"""Independent recovery checks for the opt-in source static operator.

All states are prescribed algebraic fields. These tests call detailed residuals
to obtain their reporting inputs, but never run an equilibrium/aircraft solve.
Literal stiffness matrices and closed section formulas define the expectations.
"""
from copy import deepcopy
import json

import numpy as np
import pytest
from scipy.spatial.transform import Rotation

from openswing.asw import parse_asw
from openswing.local_motion import LocalMotion
from openswing.network import StaticNetwork, network_snapshot
from openswing.recovery import recover_structure
from openswing.sensors import measure_sensor, network_sensors
from openswing.source_discrete import SourceDiscreteNetwork, STRUCTURAL_POLICY


# Two independently linear segments separated by a real section/frame jump.
E = np.array([[[100., 10., 4.], [10., 80., 3.], [4., 3., 120.]],
              [[180., 13., -5.], [13., 130., 7.], [-5., 7., 210.]],
              [[90., -8., 6.], [-8., 150., -9.], [6., -9., 170.]],
              [[160., 12., -7.], [12., 95., 8.], [-7., 8., 230.]]])
EA = np.array([1000., 1800., 900., 1400.])
SHELL = np.array([[.2, .1, .02], [.4, -.2, .04],
                  [-.1, .3, .03], [.5, .2, .06]])
TWIST = np.array([8., 20., -12., 17.])
NODES = np.linspace(1., 3., 5)
GRID = {'default': 4, 'beams': {'1': {'nodes': NODES.tolist()}}}
ROTATIONS = np.array([[.14, -.2, .03], [-.11, .24, .08], [.17, -.09, -.1],
                      [.05, .12, -.18], [-.13, -.04, .16]])
DISPLACEMENTS = np.array([[.01, -.02, .03], [.05, .01, .08], [.09, -.03, .12],
                          [.06, -.05, .17], [.12, -.07, .21]])
FORCES = np.array([[1., 8., -3.], [-2., 13., 5.], [4., -6., 2.], [3., 10., -4.]])
MOMENTS = np.array([[2., 3., 4.], [-3., 5., 2.], [4., -2., -3.], [1., 4., -2.]])
POINT_FORCE = np.array([0., 0., 1.])  # 4 N applied + the 3 N downward weight


def properties(t, side='right'):
    """Literal two-point interpolation, independent of the parser/Section."""
    a, b, f = (0, 1, t-1) if t < 2 or (t == 2 and side == 'left') else (2, 3, t-2)
    return tuple((1-f)*v[a]+f*v[b] for v in (E, EA, SHELL, TWIST))


def model():
    rows = []
    for t, e, ea, shell in zip([1, 2, 2, 3], E, EA, SHELL):
        values = [t, ea, e[0, 0], e[1, 1], e[2, 2], e[0, 1], e[0, 2], e[1, 2], *shell]
        rows.append(' '.join(map(str, values)))
    return parse_asw('Name\nSource recovery synthetic fields\nEnd\n'
        'Unit\nL 1 m\nT 1 s\nF 1 N\nEnd\nConstant\n10 1.225 340\nEnd\n'
        'Reference\n2 1 2\nEnd\nGround\n1 1 0\nEnd\n'
        'Weight\n1 2 .3 1 .2 3\nEnd\nSensor\n'
        '1 1 1 .3 0 .2\n2 1 2 .2 1 -.1 1 .2 .1 -.1 .3 1\n3 1 3 .1 2 .3\nEnd\n'
        'Beam 1\nStraight with sided material\nt x y z chord\n1 0 0 0 .2\n3 0 2 0 .2\n'
        't EA EIcc GJ EInn EIcs EIcn EIsn Cshell Nshell Atshell\n'
        + '\n'.join(rows) + '\nt twist\n1 8\n2 20\n2 -12\n3 17\n'
        't mg\n1 2\n3 6\nEnd\n', beam_interpolation='drela-segspl-v1')


def prescribed(network_class=SourceDiscreteNetwork):
    loads = [dict(beam=1, t=2, force=[0, 0, 4], moment=[2, 0, 0])]
    n = network_class(model(), GRID, None, [0, 0, -10], loads)
    assert n.nn == 5 and n.ne == 4
    q = Rotation.from_rotvec(ROTATIONS).as_matrix()
    r = np.c_[np.zeros(5), NODES-1, np.zeros(5)]+DISPLACEMENTS
    force, moment = FORCES.copy(), MOMENTS.copy()
    # Manufactured node-2 force/couple jumps, using the actual rotated pylon.
    # Other rows need not be in equilibrium: recovery is an algebraic map.
    weights = np.array([1.25, 1.75, 2.25, 2.75])
    half = np.c_[np.zeros(4), np.zeros(4), -weights/2]
    force[1] = force[2]+half[2]+POINT_FORCE+half[1]
    point_moment = np.cross(q[2]@[.3, 0, .2], [0, 0, -3])+[2, 0, 0]
    dr = np.diff(r, axis=0)
    moment[1] = moment[2]+np.cross(dr[2], force[2])/2+point_moment+np.cross(dr[1], force[1])/2
    x = np.zeros(n.size)
    pose = x[:6*n.nn].reshape(n.nn, 6)
    pose[:, :3] = DISPLACEMENTS/n.L
    pose[:, 3:] = ROTATIONS
    internal = x[6*n.nn:6*(n.nn+n.ne)].reshape(n.ne, 6)
    internal[:, :3], internal[:, 3:] = force/n.F, moment/(n.F*n.L)
    residual, data = n.residual(x, detail=True)
    return n, data, residual, q, r, force, moment, point_moment


@pytest.fixture
def state():
    return prescribed()


def expected_section(force, moment, e, ea, shell):
    axial = force[1]/ea
    curvature = np.linalg.solve(e, moment)
    c, normal, area = shell
    return dict(strain=np.array([0., axial, 0.]), curvature=curvature,
                shell_strain=axial+c*curvature[2]-normal*curvature[0],
                shell_bound=abs(axial)+abs(c*curvature[2])+abs(normal*curvature[0]),
                stress=moment[1]/(2*area))


def assert_section(actual, force, moment, e, ea, shell):
    expected = expected_section(force, moment, e, ea, shell)
    for key, value in [('force_local', force), ('moment_local', moment), ('moment_axes', moment),
                       ('strain', expected['strain']), ('curvature_change', expected['curvature'])]:
        np.testing.assert_allclose(actual[key], value, rtol=2e-13, atol=2e-14)
    assert actual['axial_strain_tension'] == pytest.approx(expected['strain'][1], abs=2e-14)
    np.testing.assert_allclose([actual['shell'][k] for k in ('c', 'n', 'area_thickness')], shell, atol=2e-15)
    for key, value in [('axial_strain', expected['shell_strain']), ('axial_strain_bound', expected['shell_bound']),
                       ('shear_stress', expected['stress']), ('shear_stress_abs', abs(expected['stress']))]:
        assert actual['shell'][key] == pytest.approx(value, rel=2e-13, abs=2e-14)


def actual_frame(q, node, t, side):
    # A straight +y span has surface frame Ry(jig twist).
    theta = np.deg2rad(properties(t, side)[3])
    jig = np.array([[np.cos(theta), 0, np.sin(theta)], [0, 1, 0], [-np.sin(theta), 0, np.cos(theta)]])
    return q[node]@jig


def test_interval_constitutive_average_is_not_a_physical_frame_or_mean_compliance(state):
    n, data, _, q, r, force, moment, _ = state
    elements, metadata = recover_structure(n, data)
    assert metadata['strain_source'] == 'source_discrete_constitutive'
    assert metadata['structural_operator'] == STRUCTURAL_POLICY
    for j, element in enumerate(elements):
        a, b = properties(NODES[j]), properties(NODES[j+1], 'left')
        ta = (actual_frame(q, j, NODES[j], 'right').T+actual_frame(q, j+1, NODES[j+1], 'left').T)/2
        average = [(v+w)/2 for v, w in zip(a, b)]
        fl, ml = ta@force[j], ta@moment[j]
        assert_section(element, fl, ml, *average[:3])
        np.testing.assert_allclose(element['transform_average'], ta, atol=2e-15)
        assert np.linalg.norm(ta@ta.T-np.eye(3)) > 1e-3
        physical = np.array(element['physical_midpoint_frame'])
        np.testing.assert_allclose(physical.T@physical, np.eye(3), atol=1e-14)
        np.testing.assert_array_equal(element['frame'], physical)
        assert element['sample_location'] == 'element constitutive average'
        assert 'geometric display only' in element['frame_role']
        assert element['t'] == pytest.approx((NODES[j]+NODES[j+1])/2, abs=1e-14)
        np.testing.assert_allclose(element['position'], (r[j]+r[j+1])/2, atol=2e-15)
        assert np.linalg.norm(fl-physical.T@force[j]) > 1e-3
        mean_compliance = (np.linalg.solve(a[0], ml)+np.linalg.solve(b[0], ml))/2
        assert np.linalg.norm(np.asarray(element['curvature_change'])-mean_compliance) > 1e-5
        mean_endpoint_stress = (ml[1]/(2*a[2][2])+ml[1]/(2*b[2][2]))/2
        assert abs(element['shell']['shear_stress']-mean_endpoint_stress) > 1e-3


def test_endpoint_recovery_uses_sided_real_frames_sections_and_conservative_wrenches(state):
    n, data, _, q, r, force, moment, _ = state
    # Independent nonsymmetric H/J fields exercise each endpoint transfer sign.
    # They are reporting operands, not a new supported source external-load law.
    data = deepcopy(data)
    data['element_forces'] += np.arange(24).reshape(4, 2, 3)/70
    data['element_moments'] = np.arange(24).reshape(4, 2, 3)/50-.2
    elements, _ = recover_structure(n, data)
    for j, element in enumerate(elements):
        for end, (side, sign) in enumerate([('right', 1), ('left', -1)]):
            trace = element['endpoint_traces'][end]
            node, t = j+end, NODES[j+end]
            frame = actual_frame(q, node, t, side)
            f = force[j]+sign*data['element_forces'][j, end]
            m = moment[j]+sign*np.cross(r[j+1]-r[j], force[j])/2+sign*data['element_moments'][j, end]
            assert (trace['side'], trace['node'], trace['t']) == (side, node, t)
            np.testing.assert_allclose(trace['position'], r[node], atol=2e-15)
            np.testing.assert_allclose(trace['frame'], frame, atol=2e-15)
            np.testing.assert_allclose(trace['force'], f, atol=2e-14)
            np.testing.assert_allclose(trace['moment'], m, atol=2e-14)
            assert_section(trace, frame.T@f, frame.T@m, *properties(t, side)[:3])
    left, right = elements[1]['endpoint_traces'][1], elements[2]['endpoint_traces'][0]
    assert np.linalg.norm(np.array(left['frame'])-right['frame']) > .1
    assert left['shell']['area_thickness'] == .04 and right['shell']['area_thickness'] == .03
    assert np.linalg.norm(np.array(left['curvature_change'])-right['curvature_change']) > .01


def test_point_weight_pylon_and_nodal_load_jump_survive_endpoint_recovery(state):
    n, data, _, _, _, _, _, point_moment = state
    elements, _ = recover_structure(n, data)
    left, right = elements[1]['endpoint_traces'][1], elements[2]['endpoint_traces'][0]
    np.testing.assert_allclose(np.array(left['force'])-right['force'], POINT_FORCE, atol=4e-14)
    np.testing.assert_allclose(np.array(left['moment'])-right['moment'], point_moment, atol=4e-14)
    # A constitutive interval value would erase both this load jump and sided E.
    assert not np.allclose(left['strain'], right['strain'])
    assert not np.allclose(left['shell']['axial_strain'], right['shell']['axial_strain'])


def test_sensors_keep_exact_pylon_kinematics_and_use_selected_anchor_section(state):
    n, data, _, _, _, _, _, _ = state
    elements, _ = recover_structure(n, data)
    sensors = network_sensors(n, data, elements)
    selected = [(0, 0, 'right'), (1, 1, 'left'), (3, 1, 'left')]
    for row, sensor, (j, end, side) in zip(n.model.records['sensor'], sensors, selected):
        node = int(np.where(NODES == row[2])[0][0])
        kin = measure_sensor(row, data['r'][node], data['Q'][node],
            LocalMotion(data['r'][node], *[np.zeros(3) for _ in range(4)]), data['motion'],
            model=n.model, condition=None, gravity=data['gravity'])
        for key, value in kin.items():
            assert sensor[key] == value
        trace = elements[j]['endpoint_traces'][end]
        assert sensor['load_trace'] == side
        assert sensor['strain_sample_t'] == row[2]
        assert sensor['strain_sample_location'] == 'one-sided sensor anchor section'
        for key in ('force_local', 'moment_local', 'strain', 'curvature_change'):
            np.testing.assert_array_equal(sensor[key], trace[key])
        np.testing.assert_array_equal(sensor['section_axes_body'], trace['frame'])
        np.testing.assert_array_equal(sensor['strain_axes_body'], trace['frame'])
        assert sensor['shell_strain'] == trace['shell']['axial_strain']
        assert sensor['shell_shear_stress'] == trace['shell']['shear_stress']
        assert np.linalg.norm(np.array(sensor['strain'])-elements[j]['strain']) > 1e-5
    assert [t['side'] for t in sensors[1]['section_traces']] == ['left', 'right']
    for trace, element, end in zip(sensors[1]['section_traces'], [elements[1], elements[2]], [1, 0]):
        np.testing.assert_array_equal(trace['section_axes_body'], element['endpoint_traces'][end]['frame'])


@pytest.mark.parametrize('ea', [0., 1000.])
def test_rigid_and_pure_axial_limits_recover_exactly_without_solving(ea):
    m = parse_asw('Name\nRecovery exact limits\nEnd\nUnit\nL 1 m\nT 1 s\nF 1 N\nEnd\n'
        'Constant\n10 1.225 340\nEnd\nReference\n2 1 2\nEnd\n'
        'Ground\n1 1 0\nEnd\nBeam 1\nStraight\nt y chord EA Cshell Nshell Atshell\n'
        f'1 0 .2 {ea} .2 .1 .02\n3 2 .2 {ea} .2 .1 .02\nEnd\n')
    n = SourceDiscreteNetwork(m, GRID, None, [0, 0, 0], [])
    x = np.zeros(n.size)
    internal = x[6*n.nn:6*(n.nn+n.ne)].reshape(n.ne, 6)
    internal[:, 1], internal[:, 4] = 10/n.F, 4/(n.F*n.L)
    if ea:
        x[:6*n.nn].reshape(n.nn, 6)[:, 1] = .01*(NODES-1)/n.L
    residual, data = n.residual(x, detail=True)
    np.testing.assert_allclose(residual[:6*n.ne], 0, atol=2e-15)
    elements, _ = recover_structure(n, data)
    for e in elements:
        for recovered in [e, *e['endpoint_traces']]:
            np.testing.assert_array_equal(recovered['curvature_change'], 0)
            np.testing.assert_allclose(recovered['strain'], [0, .01 if ea else 0, 0], atol=2e-15)
            assert recovered['shell']['axial_strain'] == (.01 if ea else 0)
            assert recovered['shell']['shear_stress'] == 100.


def test_default_operator_still_reports_midpoint_section_and_sensor_strain():
    n, data, _, _, _, _, _, _ = prescribed(StaticNetwork)
    assert 'source_discrete' not in data
    elements, metadata = recover_structure(n, data)
    assert metadata['sample_location'] == 'material midpoint'
    assert metadata['strain_source'] == 'elastic_load_compliance'
    for j, element in enumerate(elements):
        assert 'endpoint_traces' not in element and 'transform_average' not in element
        frame = np.array(element['frame'])
        assert_section(element, frame.T@data['N'][j], frame.T@data['M'][j], *properties(element['t'])[:3])
    sensors = network_sensors(n, data, elements)
    for sensor, j in zip(sensors, [0, 1, 3]):
        assert sensor['strain_sample_t'] == elements[j]['t']
        assert sensor['strain_sample_t'] != sensor['t']
        np.testing.assert_array_equal(sensor['strain'], elements[j]['strain'])
        np.testing.assert_array_equal(sensor['strain_axes_body'], elements[j]['frame'])
    snapshot = network_snapshot(n, np.zeros(n.size), data)
    assert 'output_scope' not in snapshot and 'structural_operator' not in snapshot
    assert any('SO(3) midpoint' in line for line in snapshot['limitations'])


def test_snapshot_metadata_and_peaks_cover_interval_and_endpoint_samples(state):
    n, data, residual, *_ = state
    elements, metadata = recover_structure(n, data)
    candidates = [(e, 'element constitutive average') for e in elements]
    candidates += [(t, 'endpoint '+t['side']) for e in elements for t in e['endpoint_traces']]
    for name, key in [('max_abs_shell_strain', 'axial_strain'), ('max_shell_strain_bound', 'axial_strain_bound'),
                      ('max_abs_shear_stress', 'shear_stress')]:
        trace, location = max(candidates, key=lambda item: abs(item[0]['shell'][key]))
        peak = metadata['summary'][name]
        assert peak['value'] == trace['shell'][key] and peak['t'] == trace['t']
        assert peak['sample_location'] == location
    snapshot = network_snapshot(n, residual, data)
    assert snapshot['elements'] == elements
    assert snapshot['structure'] == metadata
    assert snapshot['sensors'] == network_sensors(n, data, elements)
    assert snapshot['structural_operator'] == STRUCTURAL_POLICY
    assert 'one-sided endpoint' in snapshot['output_scope']['authoritative']
    assert 'actual sided point samples' in snapshot['output_scope']['element_coordinates']
    assert any('rigid joints; no airflow' in line for line in snapshot['limitations'])
    assert any('geometric display only' in line for line in snapshot['limitations'])
    assert not any('SO(3) midpoint' in line or 'are supported' in line or 'CDi' in line
                   for line in snapshot['limitations'])
    # Each call owns its text: downstream display annotations cannot contaminate
    # the next restored snapshot or the shared solved-result reporting path.
    snapshot['limitations'].append('local display annotation')
    snapshot['output_scope']['authoritative'] = 'local display annotation'
    next_snapshot = network_snapshot(n, residual, data)
    assert 'local display annotation' not in next_snapshot['limitations']
    assert 'one-sided endpoint' in next_snapshot['output_scope']['authoritative']
    assert any('one-sided' in line for line in snapshot['sensor_metadata']['limitations'])
    assert not any('selected adjacent element material midpoint' in line for line in snapshot['sensor_metadata']['limitations'])
    json.dumps(snapshot, allow_nan=False)
