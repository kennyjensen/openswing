"""Finite rejected-state forces remain partial and cannot supply missing moments."""
import json
from copy import deepcopy

import numpy as np
import pytest

from openswing.airflow_diagnostics import rejected_surface_forces


def arguments():
    return dict(parameters=dict(beam=np.array([1, 2])),
        lift=np.array([[0., 0., 8.], [0., 0., 2.]]),
        rate=np.array([[1., 0., 0.], [-1., 0., 0.]]),
        profile=np.array([[2., 3., 0.], [1., -1., 0.]]),
        axes=np.array([[.6, 0., .8], [0., 1., 0.], [-.8, 0., .6]]),
        density=2., speed=10., reference_area=2.,
        normal_mach=np.array([np.nextafter(1., 0.), 1.]))


def test_signed_wind_force_budget_and_inclusive_rejected_strip_sum():
    args = arguments(); before = deepcopy(args)
    result = rejected_surface_forces(**args)
    assert result['available'] and result['validity'] == 'rejected-state diagnostic'
    assert result['pitching_moment_available'] is False
    assert 'apparent-mass loads' in result['excluded'] and 'engine loads' in result['excluded']
    total = result['terms']['sum']
    np.testing.assert_array_equal(total['force_body'], [3., 2., 10.])
    assert total['lift'] == pytest.approx(3.6)
    assert total['drag'] == pytest.approx(9.8)
    assert total['side'] == pytest.approx(2.)
    assert total['CL'] == pytest.approx(.018)
    assert total['CD'] == pytest.approx(.049)
    assert result['terms']['profile']['lift'] == pytest.approx(-2.4)
    assert result['rejected_strips'] == 1
    np.testing.assert_array_equal(result['rejected_strip_sum']['force_body'], [0., -1., 2.])
    np.testing.assert_array_equal(np.sum([b['force_body'] for b in result['beams']], axis=0), total['force_body'])
    for key in ['lift', 'rate', 'profile', 'axes', 'normal_mach']:
        np.testing.assert_array_equal(args[key], before[key])
    result['terms']['circulatory']['force_body'][2] = -123.
    assert args['lift'][0, 2] == 8.
    json.dumps(result, allow_nan=False)


def test_force_units_and_rigid_rotation_preserve_coefficients():
    args = arguments(); base = rejected_surface_forces(**args)
    rotate = np.array([[0., -1., 0.], [1., 0., 0.], [0., 0., 1.]])
    for key in ['lift', 'rate', 'profile']:
        args[key] = 13.*args[key]@rotate.T
    args['axes'] = args['axes']@rotate.T
    args['density'] *= 13.
    actual = rejected_surface_forces(**args)
    for name, expected in base['terms'].items():
        np.testing.assert_allclose(actual['terms'][name]['force_body'],13.*rotate@expected['force_body'],atol=1e-13)
        for coefficient in ['CL', 'CD', 'CY']:
            assert actual['terms'][name][coefficient] == pytest.approx(expected[coefficient], abs=1e-16)


@pytest.mark.parametrize('setting', ['reference_area', 'speed'])
def test_missing_normalization_retains_dimensional_forces(setting):
    args = arguments(); args[setting] = 0.
    result = rejected_surface_forces(**args)
    assert result['available'] and not result['normalization']['coefficients_available']
    assert result['terms']['sum']['force_body'] == [3., 2., 10.]
    for row in [*result['terms'].values(), *result['beams'], result['rejected_strip_sum']]:
        assert row['CL'] is row['CD'] is row['CY'] is None
    json.dumps(result, allow_nan=False)


@pytest.mark.parametrize('kind', ['nonfinite', 'overflow'])
def test_invalid_force_budget_is_withheld_without_nonfinite_json(kind):
    args = arguments()
    if kind == 'nonfinite': args['profile'][0, 0] = np.nan
    else: args['speed'] = 1e300
    result = rejected_surface_forces(**args)
    assert result['available'] is False and 'terms' not in result
    json.dumps(result, allow_nan=False)
