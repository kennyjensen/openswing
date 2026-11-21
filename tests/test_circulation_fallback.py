"""Proposed tests: automatic fallback preserves the physical equations and gates.

Uses the repository's synthetic example. Archived third-party models are not
copied into this test; the separate artifact replay reads the pinned SA-4 file.
"""
from pathlib import Path
from types import SimpleNamespace
import numpy as np
import pytest

import openswing.aero as aero
import openswing.circulation_solve as continuation
from openswing.asw import parse_asw
from openswing.geometry import model_meshes

SOURCE = Path('examples/stall-branch.asw').read_text()


def fail_continuation(residual, regularizer, **kwargs):
    residual(np.zeros(len(regularizer)))
    raise continuation.CirculationContinuationError('Injected auxiliary-path failure')


@pytest.mark.parametrize('modes', [0, 4])
def test_auto_fallback_uses_original_linear_seed_and_analytic_physical_jacobian(monkeypatch, modes):
    model = parse_asw(SOURCE)
    condition = aero.FlightCondition(speed=47.9, alpha=18.091, mach=0., circulation_modes={1: modes})
    real_root = aero.root
    linear_seeds = []
    def direct(function, seed, *args, **kwargs):
        linear_seeds.append(np.asarray(seed).copy())
        return real_root(function, seed, *args, **kwargs)
    monkeypatch.setattr(aero, 'root', direct)
    expected = aero.solve_rigid(model, condition, 16, circulation_method='direct')
    assert len(linear_seeds) == 1
    monkeypatch.setattr(continuation, 'continue_circulation', fail_continuation)
    checked = []
    def fallback(function, seed, *args, **kwargs):
        np.testing.assert_array_equal(seed, linear_seeds[0])
        jacobian = kwargs['jac']
        assert callable(jacobian)
        direction = np.sin(.7*np.arange(len(seed)) + .3)
        h = 2e-6
        measured = (function(seed+h*direction)-function(seed-h*direction))/(2*h)
        np.testing.assert_allclose(jacobian(seed)@direction, measured, rtol=2e-7, atol=2e-8)
        checked.append(True)
        return real_root(function, seed, *args, **kwargs)
    monkeypatch.setattr(aero, 'root', fallback)
    actual = aero.solve_rigid(model, condition, 16)
    assert checked == [True]
    report = actual['circulation_solver']
    assert report['method'] == 'direct' and report['trigger'] == 'failed automatic continuation'
    assert report['failed_continuation']['error'] == 'Injected auxiliary-path failure'
    assert report['failed_continuation']['evaluations'] == 1
    assert report['fallback']['derivative'] == 'analytic'
    assert report['fallback']['physical_residual'] == actual['residual'] < 1e-8
    assert report['fallback']['evaluations'] >= report['fallback']['solver_evaluations'] > 0
    np.testing.assert_array_equal(report['fallback']['initial_coefficients'], linear_seeds[0])
    for key in ('CL', 'CD', 'CDi', 'Cm', 'efficiency'):
        assert actual[key] == pytest.approx(expected[key], rel=1e-8, abs=1e-8)
    gamma = np.array([s['circulation'] for s in actual['strips']])
    fresh = aero.evaluate_aerodynamics(model, condition, model_meshes(model, 16), circulation=gamma)
    assert fresh['residual'] < 1e-8
    np.testing.assert_allclose(fresh['force'], actual['force'], rtol=2e-10, atol=2e-10)


def test_requested_continuation_failure_never_tries_direct(monkeypatch):
    monkeypatch.setattr(continuation, 'continue_circulation', fail_continuation)
    def forbidden(*args, **kwargs):
        raise AssertionError('Explicit continuation must not switch solvers')
    monkeypatch.setattr(aero, 'root', forbidden)
    with pytest.raises(aero.AnalysisError, match='^Injected auxiliary-path failure$'):
        aero.solve_rigid(parse_asw(SOURCE), aero.FlightCondition(alpha=18.091, mach=0.), 16,
                         circulation_method='continuation')


def test_successful_automatic_continuation_does_not_try_direct(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('Successful continuation must retain its root')
    monkeypatch.setattr(aero, 'root', forbidden)
    result = aero.solve_rigid(parse_asw(SOURCE), aero.FlightCondition(alpha=18.091, mach=0.), 16)
    assert result['circulation_solver']['method'] == 'continuation'
    assert 'fallback' not in result['circulation_solver']


def test_failed_initial_direct_is_not_repeated_after_failed_continuation(monkeypatch):
    calls = []
    def unsuccessful(function, seed, **kwargs):
        calls.append(True)
        return SimpleNamespace(x=np.zeros_like(seed), nfev=1, success=False, message='injected')
    monkeypatch.setattr(aero, 'root', unsuccessful)
    monkeypatch.setattr(continuation, 'continue_circulation', fail_continuation)
    with pytest.raises(aero.AnalysisError, match='^Injected auxiliary-path failure$'):
        aero.solve_rigid(parse_asw(SOURCE), aero.FlightCondition(alpha=1., mach=0.), 16)
    assert calls == [True]


def test_singular_linear_seed_is_not_reused(monkeypatch):
    model = parse_asw(SOURCE)
    real_solve = np.linalg.solve
    calls = []
    def singular(matrix, right):
        if matrix.shape == (16, 16):
            calls.append(True)
            raise np.linalg.LinAlgError('Injected singular linear seed')
        return real_solve(matrix, right)
    def forbidden(*args, **kwargs):
        raise AssertionError('Singular linear seed must not initialize fallback')
    monkeypatch.setattr(np.linalg, 'solve', singular)
    monkeypatch.setattr(aero, 'root', forbidden)
    monkeypatch.setattr(continuation, 'continue_circulation', fail_continuation)
    with pytest.raises(aero.AnalysisError, match='^Injected auxiliary-path failure$'):
        aero.solve_rigid(model, aero.FlightCondition(alpha=18.091, mach=0.), 16)
    assert calls == [True]


@pytest.mark.parametrize('candidate', ['linear_unconverged', 'nonfinite', 'nonfinite_residual'])
def test_fallback_solver_success_flag_cannot_bypass_physical_residual(monkeypatch, candidate):
    force_nonfinite_residual = []
    real_leakage = aero._stall_leakage
    def leakage(cl, *args):
        if force_nonfinite_residual:
            return np.full_like(cl, np.nan), np.zeros_like(cl)
        return real_leakage(cl, *args)
    def false_success(function, seed, **kwargs):
        value = np.full_like(seed, np.nan) if candidate == 'nonfinite' else seed.copy()
        if candidate == 'nonfinite_residual':
            assert np.isfinite(value).all()
            force_nonfinite_residual.append(True)
        return SimpleNamespace(x=value, nfev=1, njev=0, success=True, message='untrusted success flag')
    monkeypatch.setattr(aero, '_stall_leakage', leakage)
    monkeypatch.setattr(aero, 'root', false_success)
    monkeypatch.setattr(continuation, 'continue_circulation', fail_continuation)
    with pytest.raises(aero.AnalysisError, match='Circulation solve failed.*Direct fallback') as caught:
        aero.solve_rigid(parse_asw(SOURCE), aero.FlightCondition(alpha=18.091, mach=0.), 16)
    assert caught.value.details['fallback']['reported_success'] is True
    assert caught.value.details['failed_continuation']['error'] == 'Injected auxiliary-path failure'


def test_fallback_does_not_intercept_local_mach_rejection(monkeypatch):
    # Synthetic fixture only: force the physical subsonic domain guard to fail.
    model = parse_asw(SOURCE.replace('340.21', '1.0'))
    monkeypatch.setattr(continuation, 'continue_circulation', fail_continuation)
    with pytest.raises(aero.AnalysisError, match='Local section-normal Mach reaches unity') as caught:
        aero.solve_rigid(model, aero.FlightCondition(speed=47.9, alpha=18.091, mach=0.), 16)
    assert caught.value.details['kind'] == 'section_normal_mach'


def test_fallback_does_not_swallow_timeout(monkeypatch):
    def timeout(*args, **kwargs):
        raise TimeoutError('Bounded observation cap')
    monkeypatch.setattr(aero, 'root', timeout)
    monkeypatch.setattr(continuation, 'continue_circulation', fail_continuation)
    with pytest.raises(TimeoutError, match='Bounded observation cap'):
        aero.solve_rigid(parse_asw(SOURCE), aero.FlightCondition(alpha=18.091, mach=0.), 16)
