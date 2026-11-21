"""Check the nonlinear heave oracle against independently evaluated limits."""
import importlib.util
import math
from pathlib import Path
import sys

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from isae_suite_unsteady import model_text
from isae_ua_section_reference import cold_heave, section_load


@pytest.mark.parametrize('k,t', [(.1, .3), (.475, .13), (.95, .23)])
def test_nonlinear_reference_recovers_the_published_small_amplitude_limit(k, t):
    spec = importlib.util.spec_from_file_location('ua_time', ROOT/'scripts/verify-isae-ua-time.py')
    linear = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(linear)
    args = dict(amplitude_ratio=1e-6, k=k, speed=10.)
    expected = linear.cold_heave(t, **args)
    actual = cold_heave(t, **args)
    for field in ('circulation', 'circulation_rate', 'CL'):
        assert actual[field] == pytest.approx(expected[field], rel=2e-11, abs=1e-16)


def evaluate_section(gamma, velocity, acceleration, *, frozen=False):
    from openswing.asw import parse_asw
    from openswing.aero import FlightCondition, evaluate_aerodynamics
    from openswing.network import StaticNetwork

    speed, aspect_ratio = 10., 200000.
    reference = section_load(gamma, velocity, acceleration, speed=speed)
    # Prescribed body heave changes the incident wind itself. Merely adding
    # a local nodal velocity would leave the influence control points fixed.
    condition = FlightCondition(speed=math.hypot(speed, velocity),
        alpha=math.degrees(math.atan2(-velocity, speed)), mach=0.,
        acceleration=(0., 0., acceleration), stall=False, aero_lag=True,
        freeze_influences=frozen)
    net = StaticNetwork(parse_asw(model_text(aspect_ratio)), 4, condition, [0, 0, 0], [])
    rotations = np.broadcast_to(np.eye(3), (net.nn, 3, 3))
    meshes = net.deformed_meshes(net.rj, rotations, net.geometry(net.rj, rotations))
    actual = evaluate_aerodynamics(net.model, condition, meshes,
        point_positions=net.point_positions(net.rj, rotations),
        circulation=np.full(net.ng, gamma),
        circulation_rate=np.full(net.ng, reference['circulation_rate']))
    return reference, actual, .5*1.225*speed**2*aspect_ratio


@pytest.mark.parametrize('gamma,velocity,acceleration', [(3., -4.75, 20.), (-3., 4.75, -20.), (-1., 2., -30.)])
def test_live_wind_nonlinear_section_matches_production_residual_and_each_load(gamma, velocity, acceleration):
    expected, actual, qs = evaluate_section(gamma, velocity, acceleration)
    assert max(map(abs, actual['circulation_residual'])) < 2e-5
    rate, added = actual['circulation_rate_force'][2]/qs, actual['apparent_force'][2]/qs
    circulation = actual['force'][2]/qs-rate-added
    assert rate == pytest.approx(expected['CL_rate'], abs=2e-5, rel=0)
    assert added == pytest.approx(expected['CL_added'], abs=1e-12, rel=0)
    assert circulation == pytest.approx(expected['CL_circulation'], abs=2e-5, rel=0)
    assert actual['force'][2]/qs == pytest.approx(expected['CL'], abs=2e-5, rel=0)


def test_check_distinguishes_frozen_from_live_control_points():
    _, actual, _ = evaluate_section(3., -4.75, 20., frozen=True)
    assert max(map(abs, actual['circulation_residual'])) > 1e-3
