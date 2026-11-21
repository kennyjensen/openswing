"""Source attribution retains the existing physical operator and cancellations."""
from dataclasses import replace
import json
import numpy as np
import pytest

from openswing.aero import AnalysisError, FlightCondition, evaluate_aerodynamics, horseshoe_velocity
from openswing.airflow_diagnostics import local_vortex_breakdown, breakdown_message, rejected_section_airflow
from openswing.asw import parse_asw
from openswing.factored_influence import FactoredInfluence
from openswing.geometry import model_meshes
from openswing.ground import GroundPlane


def test_all_rejected_sections_keep_exact_gate_and_distinct_frozen_receivers():
    # Include the boundary itself, a just-valid section, and a tied maximum.
    mach = np.array([1., np.nextafter(1., 0.), 1.2, 1.2])
    speed = mach*340.
    velocity = np.column_stack([speed, np.zeros(4), np.full(4, 7.)])
    points = np.arange(12, dtype=float).reshape(4, 3)
    parameters = dict(beam=np.array([1, 1, 2, 3]), t=np.array([0., 1., 2., -2.]), hv=points)
    geometry = dict(hv=points+np.array([0., 0., .5]))
    result = rejected_section_airflow(parameters, geometry, velocity, speed, mach)
    assert [r['panel_index'] for r in result] == [2, 3, 0]
    assert [r['normal_mach'] for r in result] == [1.2, 1.2, 1.]
    for record in result:
        i=record['panel_index']
        assert record['beam'] == parameters['beam'][i]
        np.testing.assert_array_equal(record['position'],points[i])
        np.testing.assert_array_equal(record['influence_position'],points[i]+[0.,0.,.5])
        np.testing.assert_array_equal(record['relative_velocity'],velocity[i])
    result[0]['position'][0] = -999.
    assert points[2,0] == 6.  # JSON records cannot mutate the solved arrays.
    json.dumps(result,allow_nan=False)
    assert rejected_section_airflow(parameters,geometry,velocity,speed,np.full(4,.9)) == []


@pytest.mark.parametrize('ground_flag', [0, 1, -1])
def test_cached_components_reconstruct_pg_and_image_field(ground_flag):
    points = np.array([[.5, .1, .3], [1., -.3, .2], [1.5, .7, -.1]])
    a = np.array([[0., -.5, 0.], [.1, .2, -.1], [.3, -.7, -.2]])
    b = np.array([[.1, .2, -.1], [.2, .8, .1], [.4, .6, .1]])
    wind = np.array([1., .2, -.1]); wind /= np.linalg.norm(wind)
    pg = np.eye(3)+(1/np.sqrt(1-.4**2)-1)*np.outer(wind, wind)
    physical = np.array([1, 2, 2]); source_core = np.array([.03, .06, .06])
    core = np.where(physical[:, None] == physical[None], 0., source_core[None])
    ground = GroundPlane(ground_flag, position=(0, 0, 2), normal=(.1, .2, 1.))
    mask = np.eye(3, dtype=bool)
    operator = FactoredInfluence(points, a, b, wind, pg, core, ground, exclude_bound=mask)
    gamma = np.array([.75, -1.25, .375])
    incident, jet = np.array([20., 1., -2.]), np.array([3., 0., .5])
    expanded = horseshoe_velocity(points[:, None], a[None], b[None], wind, pg, core, ground, exclude_bound=mask)
    expected = np.einsum('ijk,j->ik', expanded, gamma)[1]
    parameters = dict(physical=physical, beam=np.array([1, 2, 3]), t=np.array([-.3, .1, .5]))
    geometry = dict(a=a, b=b, hv=points, physical=physical)
    result = local_vortex_breakdown(operator, 1, gamma, parameters, geometry, wind,
                                   source_core, incident, jet, incident+jet+expected)
    assert result['available'] and result['reconstruction_error'] < 2e-13
    np.testing.assert_allclose(result['vortex_velocity'], expected, rtol=2e-12, atol=2e-13)
    np.testing.assert_allclose(result['reconstructed_velocity'], incident+jet+expected, atol=2e-13)
    for item in result['bound_sources']:
        i = item['panel_index']
        assert item['beam'] == parameters['beam'][i] and item['strip_t'] == parameters['t'][i]
        assert item['core_radius'] == core[1, i]
    if ground_flag == 0:
        assert 1 not in [b['panel_index'] for b in result['bound_sources']]
    json.dumps(result, allow_nan=False)


@pytest.mark.parametrize('jump', [0., 2.**-30])
def test_shared_ray_strength_is_combined_before_ranking_without_reassembly(monkeypatch, jump):
    a = np.array([[0., -1., 0.], [0., 0., 0.]])
    b = np.array([[0., 0., 0.], [0., 1., 0.]])
    points = np.array([[1., 2.**-30, 0.]])
    gamma = np.array([1., 1.+jump]); wind = np.array([1., 0., 0.])
    operator = FactoredInfluence(points, a, b, wind, np.eye(3))
    expected = operator.apply(gamma)[0]
    size = operator.nbytes
    def forbidden(*args, **kwargs):
        raise AssertionError('Diagnostics must not assemble or apply a full field again')
    monkeypatch.setattr(operator, 'apply', forbidden)
    monkeypatch.setattr(operator, 'matrix', forbidden)
    monkeypatch.setattr(FactoredInfluence, '__init__', forbidden)
    parameters = dict(physical=np.ones(2), beam=np.array([1, 2]), t=np.array([-.5, .5]))
    geometry = dict(a=a, b=b, hv=points, physical=np.ones(2))
    result = local_vortex_breakdown(operator, 0, gamma, parameters, geometry, wind,
                                   np.zeros(2), np.zeros(3), np.zeros(3), expected)
    assert result['available'] and operator.nbytes == size
    np.testing.assert_allclose(result['vortex_velocity'], expected, atol=2e-15)
    shared = [r for r in result['wake_sources'] if r['origin'] == [0., 0., 0.]]
    if jump == 0:
        assert not shared and result['zero_strength_wake_groups'] == 1
    else:
        assert len(shared) == 1
        assert shared[0]['net_circulation'] == -jump
        assert shared[0]['source_count'] == 2
        assert shared[0]['physical_ray_distance'] == 2.**-30
        assert shared[0]['speed'] < 1.  # Individually the cancelling rays exceed 1e8.
    json.dumps(result, allow_nan=False)


@pytest.mark.parametrize('reverse_source,reverse_receiver', [(False,False),(True,False),(False,True),(True,True)])
@pytest.mark.parametrize('gap', [0., 1e-8])
def test_bound_distance_and_shared_corner_use_physical_geometry_without_merging_near_roots(reverse_source, reverse_receiver, gap):
    # A 90-degree corner: incoming in the x/y plane, outgoing along z.
    # PG stretches x only. Reported distances/angles must stay physical.
    source = np.array([[-1.,-1.,gap],[0.,0.,gap]])
    receiver = np.array([[0.,0.,0.],[0.,0.,1.]])
    if reverse_source: source = source[::-1]
    if reverse_receiver: receiver = receiver[::-1]
    a = np.array([source[0],receiver[0]]); b = np.array([source[1],receiver[1]])
    points = np.array([[-.5,-.5,gap],[0.,0.,.25]])
    wind = np.array([1.,0.,0.]); pg = np.diag([2.,1.,1.]); gamma = np.array([1.,1.])
    operator = FactoredInfluence(points,a,b,wind,pg,exclude_bound=np.eye(2,dtype=bool))
    expected = operator.apply(gamma)[1].copy()
    geometry = dict(a=a,b=b,hv=points,physical=np.ones(2))
    parameters = dict(physical=np.ones(2),beam=np.array([1,2]),t=np.array([-.5,.25]))
    result = local_vortex_breakdown(operator,1,gamma,parameters,geometry,wind,
                                   np.zeros(2),np.zeros(3),np.zeros(3),expected)
    item = next(s for s in result['bound_sources'] if s['panel_index']==0)
    assert item['physical_bound_distance'] == pytest.approx(.25-gap,abs=1e-15)
    np.testing.assert_array_equal(item['physical_closest_point'],[0.,0.,gap])
    if gap == 0:
        assert item['shared_bound_endpoint'] == dict(position=[0.,0.,0.],turn_degrees=90.)
    else:
        assert item['shared_bound_endpoint'] is None
    np.testing.assert_array_equal(operator.apply(gamma)[1],expected)
    np.testing.assert_allclose(result['vortex_velocity'],expected,atol=2e-15)
    # A bound-dominated failure keeps this context in plain exception text.
    message = breakdown_message(dict(result,wake_sources=[]))
    assert 'Distance to its physical bound segment=' in message
    assert ('90-degree geometric turn' in message) == (gap == 0)
    json.dumps(result,allow_nan=False)


SOURCE = '''Name
Diagnostic surface
End
Unit
L 1 m
T 1 s
M 1 kg
End
Constant
9.81 1.225 340.294
End
Reference
4 1 4
0 0 0
End
Beam 1
Wing
t x y z chord Xax
0 0 0 0 1 0
2 0 2 0 1 0
End
'''


@pytest.mark.parametrize('frozen', [False, True])
@pytest.mark.parametrize('loads_only', [False, True])
def test_local_mach_exception_explains_current_or_frozen_source_geometry(frozen, loads_only):
    model = parse_asw(SOURCE)
    jig = model_meshes(model, 4)
    shift = np.array([0., 0., .3])
    meshes = [replace(m, r0=m.r0+shift, r1=m.r1+shift, rm=m.rm+shift) for m in jig]
    condition = FlightCondition(speed=30, alpha=9, beta=3, mach=.25, rates=(.2, -.1, .3),
        gust=dict(type='uniform', velocity=[400., 0., 0.]), freeze_influences=frozen)
    gamma = np.full(4, 2.)
    with pytest.raises(AnalysisError, match='Local section-normal Mach reaches unity') as caught:
        evaluate_aerodynamics(model, condition, meshes, circulation=gamma, _loads_only=loads_only)
    details = caught.value.details; result = details['vortex_breakdown']
    assert result['available'] and result['reconstruction_error'] < 1e-12
    assert result['influence_geometry'] == ('frozen jig' if frozen else 'current')
    current_point = np.asarray(details['maximum']['position'])
    np.testing.assert_allclose(result['influence_receiver'], current_point-shift if frozen else current_point)
    np.testing.assert_allclose(result['reconstructed_velocity'], details['maximum']['relative_velocity'], atol=1e-12)
    expected_incident = 30*condition.vectors()[0]-np.cross(condition.rates, current_point)+[400., 0., 0.]
    np.testing.assert_allclose(result['incident_velocity'], expected_incident, atol=2e-13)
    assert details['circulation_residual'] > 0
    assert 'Circulation residual=' in str(caught.value)
    assert 'source strip beam' in str(caught.value)
    assert breakdown_message(result) in str(caught.value)
    diagnostic = details['surface_force_diagnostic']
    assert diagnostic['available'] and not diagnostic['pitching_moment_available']
    # Only the sound speed changes. Fixed global PG, prescribed circulation,
    # geometry and flight/gust/rate inputs keep every pre-moment force identical.
    # This is a formula control, not a physical cure for the original failure.
    reference_model = parse_asw(SOURCE.replace('340.294', '1000.'))
    reference = evaluate_aerodynamics(reference_model, condition, meshes, circulation=gamma)
    expected = np.array(reference['force'])-reference['apparent_force']
    np.testing.assert_allclose(diagnostic['terms']['sum']['force_body'], expected, rtol=2e-14, atol=1e-10)
    for name, axis in [('CD', 0), ('CY', 1), ('CL', 2)]:
        expected_coefficient = expected@condition.vectors()[axis]/(.5*1.225*30**2*4)
        assert diagnostic['terms']['sum'][name] == pytest.approx(expected_coefficient, rel=2e-14, abs=1e-13)
    json.dumps(details, allow_nan=False)
