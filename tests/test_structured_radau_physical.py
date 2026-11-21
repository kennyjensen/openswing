"""Continuous physical partials and full-residual controls for sparse Radau.

The state tangent intentionally lags nonlocal geometry. Rate columns at a
fixed physical stage must instead agree with the original, uncached residual.
These checks do not treat a shared lagged assembly as an independent oracle.
"""
from pathlib import Path

import numpy as np
import pytest

from openswing.aero import FlightCondition
from openswing.asw import parse_asw
from openswing.network import StaticNetwork
from openswing.nonlinear_initial import InitialSystem
from openswing.operating import OperatingConstraint, TimeHistoryConstraint, time_operating_constraints
from openswing.radau_time import INVERSE
from openswing.time_integration import TimeSystem, solve_time
from openswing import structured_radau, structured_time


def _loaded_chart(frame, lag, modes):
    model = parse_asw(Path('examples/transient-wing.asw').read_text())
    # Distinct moment, acceleration and velocity references exercise the
    # frame coupling rather than assuming every reference is the origin.
    model.reference[1] = [.7, .2, -.4]
    model.reference[2] = [.3, -.2, .4]
    model.reference[3] = [.2, .1, -.3]
    condition = FlightCondition(speed=20, alpha=3, beta=2, mach=.1,
        attitude=[13, -7, 21], rates=[.02, -.015, .01], aero_lag=lag,
        circulation_modes={} if modes is None else {1: modes})
    targets = None if frame == 'free' else {'force.x': .1, 'moment.y': .2}
    net = StaticNetwork(model, 4, condition, None, [],
        operating_constraints=time_operating_constraints(frame, targets))
    system = TimeSystem(net)
    velocity = -condition.speed*condition.vectors()[0]-np.cross(net.motion.rates, model.reference[3])
    seed, _, _ = system.initial(position=condition.position_earth, attitude=condition.attitude,
        velocity=velocity, tolerance=1e-8, continuation_steps=4, frame=frame)
    chart = InitialSystem(system, seed, frame)
    rng = np.random.default_rng(184)
    z = rng.normal(0, .0002, chart.size)
    # Finite, noncommuting node and frame charts, and nonzero Gamma-dot.
    z[:6*net.nn].reshape(net.nn, 6)[:, 3:] += [.04, -.03, .02]
    z[system.frame_start+9:system.feedback_start] = [.07, -.04, .03]
    z[net.size:system.frame_start] += rng.normal(0, .002, 6*net.nn)
    rate = rng.normal(0, .003, chart.size)
    rate[net.gamma_start:net.operating_start] += .02
    return chart, z, rate


@pytest.mark.parametrize('frame,lag,modes', [('free', True, None), ('mixed', False, 3)])
def test_actual_continuous_rate_columns_match_full_uncached_residual(frame, lag, modes, record_property):
    chart, z, rate = _loaded_chart(frame, lag, modes)
    system, net = chart.system, chart.network
    assert structured_radau.eligible(chart)
    time = .013
    function = lambda d: chart.residual(z, d, time)
    original = function(rate).copy()
    matrix, p, counts = structured_time.jacobian(system, function, rate, circulation_rate_factor=None)
    assert counts['circulation_derivative'] == 'forward differences'
    assert net.iteration_fields is None and net.tangent_influences is None
    inverse = np.argsort(p)
    actual = matrix.toarray()[np.ix_(inverse, inverse)]
    expected = np.empty_like(actual)
    # Full physical calls are outside the field-capture context. Every rate
    # column is checked, including ignored algebraic rates and the frame.
    for j in range(chart.size):
        h = 1e-6*max(1., abs(rate[j]))
        plus, minus = rate.copy(), rate.copy()
        plus[j] += h; minus[j] -= h
        expected[:, j] = (function(plus)-function(minus))/(2*h)
    np.testing.assert_allclose(actual, expected, rtol=3e-6, atol=3e-7)
    ignored = np.setdiff1d(np.arange(chart.size), chart.dynamic_indices)
    np.testing.assert_array_equal(expected[:, ignored], 0.)
    np.testing.assert_array_equal(actual[:, ignored], 0.)
    np.testing.assert_array_equal(function(rate), original)
    record_property('maximum_full_rate_partial_error', float(np.max(abs(actual-expected))))

    # Independent SO(3) integral formula, including the opposite body-frame
    # chart sign; using an identity Jacobian would fail at these finite angles.
    def left_jacobian(v):
        angle = np.linalg.norm(v)
        cross = np.array([[0., -v[2], v[1]], [v[2], 0., -v[0]], [-v[1], v[0], 0.]])
        return np.eye(3)+(1-np.cos(angle))/angle**2*cross+(angle-np.sin(angle))/angle**3*(cross@cross)
    angles = z[:6*net.nn].reshape(net.nn, 6)[:, 3:]
    for node, angle in enumerate(angles):
        rows = slice(net.size+3*net.nn+3*node, net.size+3*net.nn+3*node+3)
        cols = slice(6*node+3, 6*node+6)
        np.testing.assert_allclose(actual[rows, cols], left_jacobian(angle)/chart.W, atol=3e-9, rtol=3e-9)
    fs = system.frame_start
    np.testing.assert_allclose(actual[fs:fs+9, fs:fs+9], np.eye(9)/chart.W, atol=3e-9, rtol=3e-9)
    np.testing.assert_allclose(actual[fs+9:fs+12, fs+9:fs+12],
        left_jacobian(-z[fs+9:fs+12])/chart.W, atol=3e-9, rtol=3e-9)

    # State Gamma and all frame/operating border columns must retain complete
    # fields, unlike the deliberately lagged local-geometry state columns.
    state_function = lambda value: chart.residual(value, rate, time)
    state, sp, _ = structured_time.jacobian(system, state_function, z, circulation_rate_factor=0.)
    np.testing.assert_array_equal(sp, p)
    state_dense = state.toarray()[np.ix_(inverse, inverse)]
    border = p[state.mechanical.shape[0]:]
    for j in border:
        h = 1e-6*max(1., abs(z[j])); plus, minus = z.copy(), z.copy()
        plus[j] += h; minus[j] -= h
        exact = (state_function(plus)-state_function(minus))/(2*h)
        np.testing.assert_allclose(state_dense[:, j], exact, rtol=8e-5, atol=3e-6)
    # A real physical chart also exercises the transformed factor's permutation
    # and singular descriptor-rate rows, beyond the small algebra-only fixture.
    factor = structured_radau.Factorization(state, matrix, p, INVERSE, .012)
    rhs = np.random.default_rng(71).normal(size=3*chart.size)
    correction = factor.solve(rhs).reshape(3, chart.size)
    full_product = correction@state_dense.T+(INVERSE@correction/.012)@actual.T
    np.testing.assert_allclose(full_product.ravel(), rhs, atol=2e-7, rtol=2e-7)
    assert net.iteration_fields is None and net.tangent_influences is None


def _compare_trajectories(actual, expected):
    assert actual['accepted_steps'] == expected['accepted_steps']
    assert actual['rejected_steps'] == expected['rejected_steps'] == 0
    for a, b in zip(actual['snapshots'], expected['snapshots']):
        assert a['time'] == b['time'] and a['residual'] <= 1e-8
        if a['time']:
            assert a['collocation']['maximum_stage_residual'] <= a['collocation']['stage_tolerance']
        for key in ('force', 'moment', 'support_force', 'support_moment', 'local_velocity',
                    'local_rates', 'local_acceleration', 'circulation_rate', 'force_balance',
                    'moment_balance', 'applied_force', 'applied_moment'):
            if key in b:
                np.testing.assert_allclose(a[key], b[key], rtol=2e-6, atol=3e-7, err_msg=key)
        for key in ('position_earth', 'velocity_origin_body', 'body_to_earth', 'rates_body',
                    'acceleration_reference_body', 'angular_acceleration_body'):
            np.testing.assert_allclose(a['frame'][key], b['frame'][key], rtol=2e-7, atol=2e-8, err_msg=key)
        np.testing.assert_allclose([row['position'] for row in a['nodes']],
                                   [row['position'] for row in b['nodes']], rtol=1e-8, atol=1e-8)


@pytest.mark.parametrize('frame', ['free', 'mixed'])
def test_free_and_mixed_radau_use_sparse_factor_without_dense_fallback(monkeypatch, frame, record_property):
    from test_time_integration import rigid_body
    from openswing import time_integration, radau_tangent
    args = dict(panels=4, duration=.02, dt=.01, order=5, frame=frame,
                position=[1., 2., 3.], velocity=[.2, -.1, .05], attitude=[17, 28, -41])
    if frame == 'mixed':
        args.update(gravity=[0, 0, 0], load_targets={'force.x': .3, 'moment.z': .2})
    successes, dense = [], []
    original_solve, original_lu = structured_radau.Factorization.solve, time_integration.lu_factor
    def solve(self, rhs):
        value = original_solve(self, rhs); successes.append(self.diagnostics); return value
    def lu(value, *a, **kw):
        dense.append(value.shape); return original_lu(value, *a, **kw)
    monkeypatch.setattr(structured_radau.Factorization, 'solve', solve)
    monkeypatch.setattr(time_integration, 'lu_factor', lu)
    actual = solve_time(rigid_body(), **args)
    assert successes and not dense
    record_property('successful_structured_corrections', len(successes))
    record_property('full_collocation_dense_factors', len(dense))
    monkeypatch.setattr(structured_radau, 'attach', lambda *a, **kw: False)
    monkeypatch.setattr(radau_tangent, 'attach', lambda *a, **kw: None)
    expected = solve_time(rigid_body(), **args)
    assert dense
    _compare_trajectories(actual, expected)
    if frame == 'free':
        first = actual['snapshots'][0]['frame']
        initial_velocity = np.asarray(first['body_to_earth'])@first['velocity_origin_body']
        for row in actual['snapshots']:
            t = row['time']; state = row['frame']
            np.testing.assert_allclose(state['position_earth'],
                np.array([1., 2., 3.])+t*initial_velocity+[0., 0., -.5*9.80665*t*t], atol=2e-9)
            np.testing.assert_allclose(np.asarray(state['body_to_earth'])@state['velocity_origin_body'],
                initial_velocity+[0., 0., -9.80665*t], atol=2e-9)
    else:
        for row in actual['snapshots']:
            # m=1 kg, Izz=4 kg m^2; prescribed net load includes inertia.
            np.testing.assert_allclose(row['frame']['acceleration_reference_body'], [-.3, 0., 0.], atol=2e-9)
            np.testing.assert_allclose(row['frame']['angular_acceleration_body'], [0., 0., -.05], atol=2e-9)
            np.testing.assert_allclose(row['frame']['rates_body'], [0., 0., -.05*row['time']], atol=2e-9)


def test_free_aerodynamic_radau_matches_full_collocation_after_flap_step(monkeypatch, record_property):
    from openswing import time_integration, radau_tangent
    source = Path('examples/transient-wing.asw').read_text()
    args = dict(condition=FlightCondition(speed=20, alpha=3, mach=.1), panels=4,
        duration=.02, dt=.01, order=5, frame='free',
        forcing='time +F1\n0 0\n.01 0\n.01 1\n.03 1')
    successes, dense = [], []
    original_solve, original_lu = structured_radau.Factorization.solve, time_integration.lu_factor
    def solve(self, rhs):
        value = original_solve(self, rhs); successes.append(self.diagnostics); return value
    def lu(value, *a, **kw):
        dense.append(value.shape); return original_lu(value, *a, **kw)
    monkeypatch.setattr(structured_radau.Factorization, 'solve', solve)
    monkeypatch.setattr(time_integration, 'lu_factor', lu)
    actual = solve_time(parse_asw(source), **args)
    assert successes and not dense
    record_property('successful_structured_corrections', len(successes))
    record_property('full_collocation_dense_factors', len(dense))
    # The accepted .01 endpoint belongs to the left side of the flap jump;
    # the following Radau stages use the changed control, with live Gamma.
    assert actual['snapshots'][1]['time'] == .01
    assert actual['snapshots'][1]['forcing_side'] == 'left'
    assert actual['snapshots'][1]['forcing_values']['F1'] == 0
    assert actual['snapshots'][-1]['forcing_values']['F1'] == 1
    assert np.max(abs(np.asarray(actual['snapshots'][-1]['circulation_rate']))) > 0
    monkeypatch.setattr(structured_radau, 'attach', lambda *a, **kw: False)
    monkeypatch.setattr(radau_tangent, 'attach', lambda *a, **kw: None)
    expected = solve_time(parse_asw(source), **args)
    assert dense
    _compare_trajectories(actual, expected)


@pytest.mark.parametrize('failure', ['assembly', 'factor', 'solve', 'direction'])
def test_physical_structured_failure_uses_original_full_collocation_tangent(monkeypatch, failure):
    from test_time_integration import rigid_body
    from openswing import time_integration, radau_tangent
    args = dict(panels=4, duration=.01, dt=.01, order=5, frame='free', gravity=[0, 0, 0],
                load_targets={'force.x': .3, 'moment.z': .2})
    calls, dense = [], []
    original_lu = time_integration.lu_factor
    def lu(value, *a, **kw):
        dense.append(value.shape); return original_lu(value, *a, **kw)
    def broken(*a, **kw):
        calls.append(True)
        if failure == 'direction': return np.zeros_like(a[1])
        raise ValueError('deliberate structured Radau unavailability')
    monkeypatch.setattr(time_integration, 'lu_factor', lu)
    if failure == 'assembly': monkeypatch.setattr(structured_time, 'jacobian', broken)
    elif failure == 'factor': monkeypatch.setattr(structured_radau.Factorization, '__init__', broken)
    else: monkeypatch.setattr(structured_radau.Factorization, 'solve', broken)
    actual = solve_time(rigid_body(), **args)
    assert calls and dense
    monkeypatch.setattr(structured_radau, 'attach', lambda *a, **kw: False)
    monkeypatch.setattr(radau_tangent, 'attach', lambda *a, **kw: None)
    expected = solve_time(rigid_body(), **args)
    _compare_trajectories(actual, expected)


def test_actual_chart_scope_keeps_inverse_history_controller_and_custom_fallback(monkeypatch):
    chart, _, _ = _loaded_chart('mixed', True, None)
    assert structured_radau.eligible(chart)
    system, operating = chart.system, chart.network.operating
    original = operating.constraints
    class Subclass(InitialSystem): pass
    derived = Subclass(system, chart.seed, 'mixed')
    assert not structured_radau.eligible(derived)
    for constraints in (
        [OperatingConstraint('control.1', 'force.z')],
        [OperatingConstraint('acceleration.x', 'force.y')],
        [TimeHistoryConstraint('acceleration.x', 'force.x')],
    ):
        with monkeypatch.context() as m:
            m.setattr(operating, 'constraints', constraints)
            m.setattr(operating, 'count', len(constraints))
            assert not structured_radau.eligible(chart)
    for attr in ('feedback', 'position_lift'):
        with monkeypatch.context() as m:
            m.setattr(system, attr, object())
            assert not structured_radau.eligible(chart)
    np.testing.assert_equal(operating.constraints, original)
