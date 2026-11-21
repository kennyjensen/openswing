from pathlib import Path
import runpy
import numpy as np
import pytest
from openswing.aero import FlightCondition, evaluate_aerodynamics, solve_rigid, AnalysisError
from openswing.asw import parse_asw
from openswing.geometry import model_meshes
from openswing.network import solve_static
from openswing.time_initialization import launch_time
from test_volume import body_source

STUDY = runpy.run_path(str(Path(__file__).resolve().parents[1]/'scripts/verify-section-airflow.py'))


@pytest.mark.parametrize('sweep,units', [(-35., [1., 1., 1.]), (0., [1., 1., 1.]), (35., [.3048, 2., 4.4482216152605])])
def test_reported_velocity_matches_closed_form_wake_field(sweep, units):
    STUDY['compute'](dict(sweep=sweep, panels=64, units=units))


@pytest.mark.parametrize('frozen', [False, True])
def test_relative_velocity_uses_current_force_location_rates_and_gust(frozen):
    source = STUDY['source'](dict(sweep=35.)).replace('.25 0 0', '0 0 0')
    model = parse_asw(source)
    condition = FlightCondition(speed=30, alpha=7, beta=-4, mach=.25, rates=(.2, -.1, .3),
                                gust=dict(type='uniform', velocity=[2., -1., 3.]), freeze_influences=frozen)
    mesh = model_meshes(model, 8)
    result = evaluate_aerodynamics(model, condition, mesh, circulation=np.zeros(8))
    angle = np.deg2rad(35.)
    span = np.array([np.sin(angle), np.cos(angle), 0.])
    wind = condition.vectors()[0]
    influence = np.array([1., 0., 0.]) if frozen else wind
    for row in result['strips']:
        axis = np.array([np.tan(angle)*row['t'], row['t'], 0.])
        force_point = axis+.125/np.linalg.norm(np.cross(influence, span))*influence
        expected = 30*wind-np.cross(condition.rates, force_point)+[2., -1., 3.]
        normal_speed = np.linalg.norm(expected-(expected@span)*span)
        np.testing.assert_allclose(row['velocity_position'], force_point, atol=2e-14)
        np.testing.assert_allclose(row['relative_velocity'], expected, atol=2e-13)
        assert row['normal_speed'] == pytest.approx(normal_speed, abs=2e-13)
        assert row['normal_mach'] == pytest.approx(normal_speed/340.294, abs=2e-14)
        assert abs(row['normal_mach']-result['mach']) > .1


def test_error_retains_actual_local_mach_location_and_speed_at_fixed_pg_zero():
    model = parse_asw(STUDY['source'](dict(sweep=0.)))
    with pytest.raises(AnalysisError, match='Local section-normal Mach reaches unity') as caught:
        solve_rigid(model, FlightCondition(speed=30, alpha=0, mach=0,
                    gust=dict(type='uniform', velocity=[400., 0., 0.])), 8)
    details = caught.value.details
    assert details['kind'] == 'section_normal_mach'
    assert details['maximum']['beam'] == 1
    assert details['maximum']['normal_speed'] == pytest.approx(430.)
    assert details['maximum']['normal_mach'] == pytest.approx(430./340.294)
    np.testing.assert_allclose(details['maximum']['relative_velocity'], [430., 0., 0.], atol=1e-13)
    breakdown = details['vortex_breakdown']
    assert breakdown['available'] and not breakdown['bound_sources'] and not breakdown['wake_sources']
    np.testing.assert_allclose(breakdown['incident_velocity'], [430., 0., 0.], atol=1e-13)
    np.testing.assert_array_equal(breakdown['vortex_velocity'], 0.)
    assert 'Vortex contribution is zero' in str(caught.value)
    assert 'body force point' in str(caught.value) and 'Maximum M_perp=' in str(caught.value)


def test_body_only_result_has_no_fabricated_surface_samples():
    result = solve_rigid(parse_asw(body_source()), FlightCondition(speed=30, alpha=0, mach=0), 8)
    assert result['lifting_airflow']['samples'] == 0
    assert result['lifting_airflow']['maximum'] is None
    assert all('normal_mach' not in row for row in result['strips'])


def test_saved_steady_launch_keeps_airflow_in_each_physical_time_snapshot():
    source = STUDY['source'](dict(sweep=35.)).replace('Beam 1', 'Ground\n1 0 0\nEnd\nBeam 1')
    model = parse_asw(source)
    condition = FlightCondition(speed=30, alpha=0, mach=0, freeze_influences=True,
                                gust=dict(type='uniform', velocity=[2., 0., 0.]))
    steady = solve_static(model, condition, 4, gravity=[0., 0., 0.])
    history = launch_time(model, steady['equilibrium_state'], duration=.02, dt=.01)
    for result in [steady, *history['snapshots']]:
        assert result['lifting_airflow']['samples'] == 4
        for row in result['strips']:
            np.testing.assert_allclose(row['relative_velocity'], [32., 0., 0.], atol=1e-9)
            assert row['normal_speed'] == pytest.approx(32*np.cos(np.deg2rad(35.)), abs=1e-9)
