"""Guard physical setup, continuous startup and unmasked per-strip errors."""
from pathlib import Path
import sys

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from isae_ua1_periodic_study import Case, request, reference_history, summarize_grid, check_restart_join
from isae_ua_incidence_periodic import full_request as original_request, reference_history as original_reference
from isae_ua_incidence_reference import trajectory


def test_previous_inclined_setup_and_reference_are_preserved_exactly():
    case = Case(9., .94)
    assert request(case, 24) == original_request(24)
    actual, expected = reference_history(case, 24), original_reference(24)
    assert actual['cold_rows'] == expected['cold_rows']
    assert actual['periodic'] == expected['periodic']


def test_changed_physical_parameters_reach_the_full_acceleration_table():
    case = Case(5., .47, .3, speed=30.)
    model = request(case, 24)
    table = np.loadtxt(model['time']['forcing'].splitlines()[1:])
    forces = table[:, [1, 2]]
    direction = case.direction[[0, 2]]
    wind = case.wind[[0, 2]]
    omega = 2*case.speed*case.k
    np.testing.assert_allclose(forces@wind, 0., atol=2e-14)
    np.testing.assert_allclose(forces@direction, -.15*omega**2*np.cos(omega*table[:, 0]), atol=2e-12)
    assert table.shape == (193, 3)
    # Equivalent period multiplications can differ by one ULP. This is the
    # same absolute clock tolerance declared for retained production states.
    assert abs(table[-1, 0]-model['time']['duration']) < 1e-12
    assert model['condition']['alpha'] == 5. and model['condition']['speed'] == 30.
    np.testing.assert_allclose(model['condition']['position_earth'], .15*case.direction, atol=0)


def test_new_condition_transient_matches_direct_integration_over_all_cycles():
    case = Case(5., .47)
    reference = reference_history(case, 24)
    direct = trajectory([r['time'] for r in reference['cold_rows']], **case.settings, boundary='steady', method='DOP853')
    for key in ('CL', 'circulation', 'circulation_rate'):
        expected = np.array([r[key] for r in direct['rows']])
        actual = np.array([r[key] for r in reference['cold_rows']])
        assert np.max(abs(actual-expected))/np.max(abs(expected)) < 1e-9
    assert abs(reference['cold_rows'][0]['circulation_rate']) < 1e-12
    assert abs(reference['cold_rows'][0]['circulation']-reference['periodic']['initial_circulation']) > .1


def test_single_strip_error_is_not_hidden_by_strip_averaging_or_steady_mean():
    case = Case(9., .47, amplitude_ratio=.01)
    reference = reference_history(case, 24)
    rows = [dict(time=r['time'], CL=r['CL'], circulation=[r['circulation']]*4,
                 circulation_rate=[r['circulation_rate']]*4, residual=0.,
                 heave_position=r['displacement'], heave_velocity=r['velocity']) for r in reference['cold_rows']]
    before = summarize_grid(case, 24, rows, reference, 24)
    scale = before['cold_scales']['circulation']
    rows[27]['circulation'][3] += .004*scale
    after = summarize_grid(case, 24, rows, reference, 24)
    assert after['cold_error_fractions']['circulation'] == pytest.approx(.004, abs=2e-14)
    assert before['cold_error_fractions']['circulation'] == 0


@pytest.mark.parametrize('settings', [(5., 0.), (float('nan'), .47), (79., 2.)])
def test_invalid_or_reversed_chordwise_flow_is_rejected(settings):
    with pytest.raises(ValueError):
        Case(*settings)


def test_internal_moment_roundtrip_accepts_one_ulp_and_reports_it():
    moment = -77514.90904853858
    other = np.nextafter(moment, np.inf).item()
    before = dict(network=dict(internal_moment=[[moment]], circulation=[1.25]), time=.5)
    after = dict(network=dict(internal_moment=[[other]], circulation=[1.25]), time=.5)
    result = check_restart_join(before, after)
    assert len(result) == 1 and result[0]['difference_in_ulps'] == 1


@pytest.mark.parametrize('field,ulps', [('internal_moment', 16), ('circulation', 1), ('positions', 1)])
def test_restart_audit_rejects_changed_physics_or_excess_scale_roundoff(field, ulps):
    value = 1.25
    changed = value
    for _ in range(ulps):
        changed = np.nextafter(changed, np.inf).item()
    with pytest.raises(AssertionError):
        check_restart_join(dict(network={field: [value]}), dict(network={field: [changed]}))
