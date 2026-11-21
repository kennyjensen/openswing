"""Independent heave reference and bounded source-equation time regression."""
import importlib.util
import math
from pathlib import Path
import sys

import pytest
from scipy.integrate import quad

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
SPEC = importlib.util.spec_from_file_location('isae_ua_time', ROOT/'scripts/verify-isae-ua-time.py')
UA = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(UA)


@pytest.mark.parametrize('k,time_value', [(.06785714285714285, .5), (.475, .13), (.95, .23)])
def test_cold_heave_reference_matches_independent_convolution(k, time_value):
    # Evaluate the convolution of the forcing with the circulation relaxation
    # kernel, independently of the closed trigonometric formula in the verifier.
    speed, amplitude = 10., .001
    omega, tau, h = 2*speed*k, 2/speed, amplitude/2
    velocity = lambda t: -h*omega*math.sin(omega*t)
    gamma = quad(lambda t: -math.pi*velocity(t)*math.exp(-(time_value-t)/tau)/tau,
                 0., time_value, epsabs=1e-14)[0]
    rate = (-math.pi*velocity(time_value)-gamma)/tau
    acceleration = -h*omega**2*math.cos(omega*time_value)
    expected_lift = 2*gamma/speed+2*rate/speed**2-math.pi*acceleration/(2*speed**2)
    actual = UA.cold_heave(time_value, amplitude_ratio=amplitude, k=k, speed=speed)
    assert actual['circulation'] == pytest.approx(gamma, abs=1e-14, rel=0)
    assert actual['circulation_rate'] == pytest.approx(rate, abs=1e-14, rel=0)
    assert actual['CL'] == pytest.approx(expected_lift, abs=1e-14, rel=0)


def test_startup_is_zero_circulation_with_the_physical_added_mass_load():
    value = UA.cold_heave(0., amplitude_ratio=.05, k=.95, speed=10.)
    assert value['z'] == .025  # A is the verified peak-to-peak displacement.
    assert value['circulation'] == value['circulation_rate'] == value['velocity'] == 0
    assert value['CL'] == pytest.approx(.05*math.pi*.95**2, abs=1e-15)


def test_source_time_heave_refines_to_the_published_startup_equation():
    from openswing.bridge import dispatch
    errors = []
    for count in (40, 80):
        request = UA.make_request(steps=count, amplitude_ratio=.001, k=.475)
        result = dispatch(request)
        compared = UA.compare(result, request, amplitude_ratio=.001, k=.475, aspect_ratio=200000.)
        assert result['converged'] and result['rejected_steps'] == 0
        assert result['accepted_steps'] == count
        assert result['structural_operator'] == 'drela-moving-airflow-v1'
        assert result['temporal_policy'] == 'drela-euler-bdf-v1'
        assert compared['maximum_residual'] < 1e-10
        assert compared['maximum_acceleration_error'] < 1e-14
        assert max(abs(x) for s in compared['samples'] for x in s['frame_rates']) < 1e-12
        errors.append(compared['maximum_waveform_error_fraction'])
    assert errors[1] < .003
    assert errors[1] < .35*errors[0]
