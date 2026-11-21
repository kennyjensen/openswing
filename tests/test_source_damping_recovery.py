"""Source damping recovery from manufactured fields, without any physics solve.

No residual, equilibrium, eigensystem or time step is evaluated. The production
output stencil receives four algebraic snapshots to check complex rate output.
"""
from copy import deepcopy
from types import SimpleNamespace

import numpy as np
import pytest

from openswing.asw import parse_asw
from openswing.linear_dynamics import output_perturbation
from openswing.sensors import UNITS, network_sensors, source_sensor_limitations
from openswing.source_discrete import SourceSectionNetwork
from openswing.source_recovery import recover_source_structure


SOURCE = '''Name
Manufactured damped recovery fields
End
Unit
L 1 m
T 1 s
F 1 N
End
Constant
10 1.225 340
End
Reference
2 .2 2
0 0 0
End
Ground
1 1 0
End
Sensor
1 1 1 .1 0 .2
2 1 2 .2 1 .1
3 1 3 .3 2 -.1
End
Beam 1
Sided sections
t x y z chord
1 0 0 0 .2
3 0 2 0 .2
t EA GKc GKn EIcc GJ EInn EIcs EIcn EIsn Cea Nea Cta Nta
1 800 300 400 100 75 150 8 -13 9 -.1 .07 .3 -.2
2 1000 350 500 120 85 160 7 -10 8 -.05 .05 .2 -.1
2 1200 600 700 130 95 170 6 -8 7 .1 -.03 -.2 .2
3 1600 900 1000 140 100 180 6 2 5 .2 -.03 -.1 .4
t Cshell Nshell Atshell
1 .4 .2 .01
2 .5 .3 .02
2 .8 .6 .04
3 .9 .7 .05
End
'''


@pytest.fixture
def fields():
    model = parse_asw(SOURCE, beam_interpolation='drela-segspl-v1')
    n = SourceSectionNetwork(model, {'default': 4, 'beams': {'1': {
        'nodes': [1., 1.5, 2., 2.5, 3.]}}}, None, [0, 0, 0], [])
    # Only the reporting protocol is exercised. These are not claimed states
    # of SourceDynamicNetwork, nor equilibrium data or an independent PDE test.
    n.source_dynamic = True
    n.structural_operator = 'drela-fixed-vacuum-v1'
    n.damping_times = np.full((4, 6), .2)
    r = n.rj.copy()
    angles = np.array([.1, -.15, .25, -.2, .3])
    q = np.array([[[np.cos(a), 0, np.sin(a)], [0, 1, 0],
                   [-np.sin(a), 0, np.cos(a)]] for a in angles])
    pa, pb, ra, rb, *_ = n.geometry(r, q)
    transform = (ra.transpose(0, 2, 1)+rb.transpose(0, 2, 1))/2
    force = np.arange(12, dtype=float).reshape(4, 3)/3+2
    moment = np.arange(12, dtype=float).reshape(4, 3)/7-.4
    strain = np.array([[.02, .03, -.04], [.04, .06, -.08],
                       [.06, .09, -.12], [.08, .12, -.16]])
    curvature = strain[:, [2, 0, 1]]/2
    data = dict(r=r, Q=q, N=force, M=moment,
        element_forces=np.arange(24, dtype=float).reshape(4, 2, 3)/30,
        element_moments=np.arange(24, dtype=float).reshape(4, 2, 3)/50,
        section_frame=ra, condition=None, motion=n.motion, local_motion=None,
        gravity=np.zeros(3), aero=None,
        source_discrete=dict(transform_average=transform,
            force_local=np.einsum('nij,nj->ni', transform, force),
            moment_local=np.einsum('nij,nj->ni', transform, moment),
            translation_strain=strain, axial_strain=strain[:, 1],
            curvature_change=curvature))
    return n, data


def test_damped_intervals_keep_corrected_strain_and_total_stress(fields):
    n, data = fields
    elements, meta = recover_source_structure(n, data)
    assert meta['strain_source'] == 'source_discrete_damped_constitutive'
    for j, item in enumerate(elements):
        np.testing.assert_array_equal(item['strain'], data['source_discrete']['translation_strain'][j])
        np.testing.assert_array_equal(item['curvature_change'], data['source_discrete']['curvature_change'][j])
        section = n.source_sections[j]
        eps, k = np.array(item['strain']), np.array(item['curvature_change'])
        axial = eps[1]-section.Nta*k[0]+section.Cta*k[2]
        shell = item['shell']
        assert item['axial_strain_tension'] == pytest.approx(axial)
        assert shell['axial_strain'] == pytest.approx(axial+shell['c']*k[2]-shell['n']*k[0])
        f, m = item['force_local'], item['moment_local']
        torque = m[1]-section.Nea*f[0]+section.Cea*f[2]
        assert shell['shear_stress'] == pytest.approx(torque/(2*shell['area_thickness']))
        elastic_only = section.compliance()@np.r_[f, m]
        assert np.linalg.norm(np.r_[eps, k]-elastic_only) > .01
        assert np.linalg.norm(np.array(item['transform_average'])@np.array(item['transform_average']).T-np.eye(3)) > .01


def test_damped_endpoints_expose_loads_but_never_static_compliance_strain(fields):
    n, data = fields
    elements, meta = recover_source_structure(n, data)
    for j, item in enumerate(elements):
        for end, trace in enumerate(item['endpoint_traces']):
            for key in ['strain', 'curvature_change', 'axial_strain_tension']:
                assert trace[key] is None
            assert trace['strain_source'] == 'unavailable_endpoint_material_rate'
            assert not trace['shell']['strain_available']
            assert trace['shell']['axial_strain'] is None
            assert trace['shell']['axial_strain_bound'] is None
            section = n.source_endpoint_sections[j][end]
            f, m = trace['force_local'], trace['moment_local']
            torque = m[1]-section.Nea*f[0]+section.Cea*f[2]
            assert trace['shell']['shear_stress'] == pytest.approx(torque/(2*trace['shell']['area_thickness']))
            assert trace['shell']['stress_source'] == 'total_section_resultant'
    assert meta['summary']['max_abs_shell_strain']['sample_location'] == 'element constitutive average'
    assert elements[1]['endpoint_traces'][1]['shell']['area_thickness'] == .02
    assert elements[2]['endpoint_traces'][0]['shell']['area_thickness'] == .04


def test_sensor_interval_strain_is_sided_and_separate_from_anchor_stress(fields):
    n, data = fields
    elements, _ = recover_source_structure(n, data)
    sensors = network_sensors(n, data, elements)
    reduced, _ = recover_source_structure(n, data, sensor_traces_only=True)
    assert sum(len(item['endpoint_traces']) for item in reduced) < 2*n.ne
    assert network_sensors(n, data, reduced) == sensors
    for sensor, j, end, side in zip(sensors, [0, 1, 3], [0, 1, 1], ['right', 'left', 'left']):
        interval, trace = elements[j], elements[j]['endpoint_traces'][end]
        for key in ['strain', 'curvature_change']:
            assert sensor[key] == interval[key]
        assert sensor['shell_strain'] == interval['shell']['axial_strain']
        assert sensor['shell_shear_stress'] == trace['shell']['shear_stress']
        assert sensor['force_local'] == trace['force_local']
        assert sensor['moment_local'] == trace['moment_local']
        assert sensor['strain_sample_t'] == interval['t'] != sensor['t']
        assert sensor['strain_sample_element'] == j
        assert sensor['strain_sample_side'] == side
        assert sensor['strain_axes_body'] is None
        assert sensor['strain_transform_average'] == interval['transform_average']
        assert sensor['section_axes_body'] == trace['frame']
        assert sensor['shell_shear_stress_sample_t'] == sensor['t']
    assert [trace['side'] for trace in sensors[1]['section_traces']] == ['left', 'right']
    assert all(trace['strain'] is None for trace in sensors[1]['section_traces'])
    assert 'nonorthogonal' in source_sensor_limitations(n, data)[2]


def test_zero_damping_interval_and_old_policies_keep_anchor_recovery(fields):
    n, data = fields
    n.damping_times[1] = 0
    elements, _ = recover_source_structure(n, data)
    sensors = network_sensors(n, data, elements)
    assert sensors[1]['strain_sample_t'] == 2
    assert sensors[1]['strain'] == elements[1]['endpoint_traces'][1]['strain']
    assert 'strain_transform_average' not in sensors[1]
    assert 'strain_source' not in elements[1]
    n.damping_times[:] = 0
    dynamic = recover_source_structure(n, data)
    dynamic_sensors = network_sensors(n, data, dynamic[0])
    n.source_dynamic = False
    static = recover_source_structure(n, data)
    static_sensors = network_sensors(n, data, static[0])
    assert dynamic == static
    assert dynamic_sensors == static_sensors
    assert dynamic[1]['strain_source'] == 'source_discrete_constitutive'
    assert 'strain_source' not in dynamic[0][0]
    assert all('strain_source' not in trace for trace in dynamic[0][0]['endpoint_traces'])


def test_modal_output_stencil_keeps_complex_interval_rate_strain(fields, monkeypatch):
    n, data = fields
    # The unrelated support tangent is outside this reporting test. All section
    # and sensor stencils below are the actual output_perturbation implementation.
    monkeypatch.setattr('openswing.support_outputs.support_outputs', lambda *args: {})
    state = SimpleNamespace(r=data['r'], Q=data['Q'], orientation=np.eye(3), position=np.zeros(3))
    shape = np.array([.3, -.2, .4])
    rate_shape = np.array([.12, .18, -.15])
    calls = []

    def snapshot(z, zdot, *, forcing=None, linear_output=False):
        calls.append((z.copy(), zdot.copy()))
        d = deepcopy(data)
        # Manufactured source law: corrected mechanical strain has both state
        # and material-rate terms; no production residual is called here.
        change = shape*z[0]-rate_shape*zdot[0]
        d['source_discrete']['translation_strain'] += change
        d['source_discrete']['curvature_change'] += change/3
        elements, structure = recover_source_structure(n, d, sensor_traces_only=linear_output)
        sensors = network_sensors(n, d, elements)
        return state, dict(geometry=[], attachments=[], operating_values={}, strips=[],
            elements=elements, structure=structure, sensors=sensors)

    _, base = snapshot(np.zeros(12*n.nn), np.zeros(12*n.nn))
    calls.clear()
    system = SimpleNamespace(network=n, size=12*n.nn, L=n.L, V=1., W=1.,
        velocity_start=6*n.nn, frame_start=12*n.nn, frame='fixed', feedback=None,
        base=np.zeros(n.size), condition=None, motion=n.motion,
        _section_output_mask=[], _sensor_output_mask=[{key:s.get(key) is not None for key in UNITS}
            for s in base['sensors']], snapshot=snapshot)
    v = np.zeros(system.size, dtype=complex);v[0] = .7+.2j
    rate = np.zeros_like(v);rate[0] = -.4+.6j
    result = output_perturbation(system, v, rate)
    expected = shape*v[0]-rate_shape*rate[0]
    assert len(calls) == 4
    assert system.structural_output_diagnostics['method'] == 'physical output stencils'
    for sample in [*result['sections'], *result['sensors']]:
        np.testing.assert_allclose(np.array(sample['strain']['real'])+1j*np.array(sample['strain']['imag']), expected, atol=2e-12)
        np.testing.assert_allclose(np.array(sample['curvature_change']['real'])+1j*np.array(sample['curvature_change']['imag']), expected/3, atol=2e-12)
