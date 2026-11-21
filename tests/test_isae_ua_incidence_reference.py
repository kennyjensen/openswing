"""Limits, independent integration, and coordinate checks for inclined heave."""
import math
from pathlib import Path
import sys

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from isae_ua_incidence_reference import fields, steady_circulation, trajectory
from isae_ua_incidence_production import evaluate_point
from isae_ua_section_reference import section_load


@pytest.mark.parametrize('gamma,w,a', [(3., -4.7, 20.), (-3., 4.7, -20.), (-1., 2., -30.)])
def test_zero_incidence_reduces_to_previous_nonlinear_section(gamma, w, a):
    actual = fields(gamma, w, a, alpha_deg=0.)
    old = section_load(gamma, w, a, speed=10.)
    for key in ('circulation_rate', 'CL', 'CL_circulation', 'CL_rate'):
        assert actual[key] == pytest.approx(old[key], rel=1e-14, abs=1e-14)
    assert actual['CL_apparent'] == old['CL_added']


@pytest.mark.parametrize('alpha', [-9., 5., 9.])
def test_steady_limit_and_zero_amplitude_periodic_boundary(alpha):
    gamma = steady_circulation(alpha_deg=alpha)
    expected = 2*math.pi*math.tan(math.radians(alpha))
    result = trajectory(np.linspace(0, math.pi/9.4, 9), alpha_deg=alpha, amplitude_ratio=0.)
    for row in result['rows']:
        assert row['circulation'] == pytest.approx(gamma, rel=1e-12)
        assert abs(row['circulation_rate']) < 1e-10
        assert row['CL'] == pytest.approx(expected, rel=1e-12)


@pytest.mark.parametrize('alpha,k', [(5., .47), (9., .94)])
def test_integrating_factor_and_two_ode_methods_agree(alpha, k):
    times = np.linspace(0, math.pi/(10*k), 65)
    expected = trajectory(times, alpha_deg=alpha, k=k)
    for method in ('DOP853', 'Radau'):
        actual = trajectory(times, alpha_deg=alpha, k=k, method=method)
        for key in ('circulation', 'circulation_rate', 'CL'):
            a = np.array([r[key] for r in actual['rows']])
            b = np.array([r[key] for r in expected['rows']])
            assert np.max(abs(a-b))/np.max(abs(b)) < 1e-9
    assert expected['rows'][0]['circulation'] == pytest.approx(expected['rows'][-1]['circulation'], abs=1e-11)


def test_mean_incidence_sign_reversal_matches_half_cycle_shift():
    times = np.linspace(0, math.pi/9.4, 65)
    plus = trajectory(times, alpha_deg=9.)['rows'][:-1]
    minus = trajectory(times, alpha_deg=-9.)['rows'][:-1]
    for key in ('circulation', 'circulation_rate', 'CL'):
        np.testing.assert_allclose([r[key] for r in plus],
            -np.roll([r[key] for r in minus], -32), rtol=1e-11, atol=1e-10)


@pytest.mark.parametrize('alpha,g,w,a', [(5., 3., -4.7, -20.), (9., -3., 4.7, 20.), (9., 8., 0., -88.36)])
def test_both_production_coordinate_representations_match_force_components(alpha, g, w, a):
    reference = fields(g, w, a, alpha_deg=alpha)
    outputs = []
    for representation in ('body', 'wind'):
        actual = evaluate_point(g, reference['circulation_rate'], w, a,
                                alpha_deg=alpha, representation=representation)
        assert actual['maximum_residual'] < 5e-5
        for key in ('CF', 'CF_rate'):
            np.testing.assert_allclose(actual[key], reference[key], rtol=0, atol=5e-5)
        np.testing.assert_allclose(actual['CF_apparent'], reference['CF_apparent'], rtol=0, atol=1e-12)
        assert actual['CL_instantaneous'] == pytest.approx(reference['CL_instantaneous'], abs=5e-5)
        outputs.append(actual)
    for key in ('CF', 'CF_rate', 'CF_apparent'):
        np.testing.assert_allclose(outputs[0][key], outputs[1][key], rtol=0, atol=1e-12)


def test_frozen_wind_fails_the_same_finite_motion_state():
    ref = fields(3., -4.7, 20., alpha_deg=9.)
    actual = evaluate_point(3., ref['circulation_rate'], -4.7, 20., alpha_deg=9., frozen=True)
    assert actual['maximum_residual'] > 1e-3
