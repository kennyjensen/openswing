"""The primary direct solve differentiates the complete circulation residual."""
from pathlib import Path

import numpy as np
import pytest

import openswing.aero as aero
from openswing.asw import parse_asw
from openswing.circulation import CirculationBasis
from openswing.geometry import model_meshes


SOURCE = Path('examples/stall-branch.asw').read_text()


@pytest.mark.parametrize('modes', [0, 8])
@pytest.mark.parametrize('lag_rate', [0., .3])
def test_primary_direct_jacobian_matches_complete_residual_and_numerical_root(monkeypatch, modes, lag_rate):
    model = parse_asw(SOURCE)
    condition = aero.FlightCondition(speed=27., alpha=3., mach=.15,
        circulation_modes={1: modes})
    meshes = model_meshes(model, 16)
    basis = CirculationBasis(meshes, condition.circulation_modes)
    rate = basis.decode(lag_rate*np.cos(np.arange(basis.size)*.3))
    actual_root = aero.root
    calls = []

    def checked_root(residual, seed, **kwargs):
        derivative = kwargs['jac']
        assert callable(derivative)
        direction = np.sin(.7*np.arange(len(seed))+.3)
        # The displaced states exercise nonlinear stall leakage and its local
        # speed derivative even though this low-incidence solve starts directly.
        for state in [np.zeros_like(seed), seed, seed+20*direction, seed-20*direction]:
            h = 2e-6
            measured = (residual(state+h*direction)-residual(state-h*direction))/(2*h)
            jacobian = derivative(state)
            assert jacobian.shape == (basis.size, basis.size)
            np.testing.assert_allclose(jacobian@direction, measured, rtol=3e-7, atol=2e-8)
        calls.append(True)
        return actual_root(residual, seed, **kwargs)

    monkeypatch.setattr(aero, 'root', checked_root)
    analytic = aero.evaluate_aerodynamics(model, condition, meshes, circulation_rate=rate)
    assert calls == [True] and analytic['circulation_solver']['method'] == 'direct'
    assert analytic['residual'] < 1e-8

    def numerical_root(residual, seed, **kwargs):
        return actual_root(residual, seed, **{**kwargs, 'jac': None})

    monkeypatch.setattr(aero, 'root', numerical_root)
    numerical = aero.evaluate_aerodynamics(model, condition, meshes, circulation_rate=rate)
    for name in ('force', 'moment', 'CL', 'CD', 'CDi', 'Cm'):
        np.testing.assert_allclose(analytic[name], numerical[name], rtol=1e-10, atol=1e-10)
    np.testing.assert_allclose([s['circulation'] for s in analytic['strips']],
                              [s['circulation'] for s in numerical['strips']], rtol=1e-10, atol=1e-10)


def test_primary_direct_engine_feedback_keeps_complete_numerical_derivative(monkeypatch):
    row = np.zeros(25)
    row[:15] = [1, 0, 1, 0, -1.5, 0, -.3, -1, 0, 0, 1., -.03, 1.2, 150., .002]
    model = parse_asw(SOURCE+'\nEngine\n'+' '.join(map(str, row))+'\nEnd\n')
    condition = aero.FlightCondition(speed=27., alpha=3., mach=.15, powers={1: 250.})
    meshes = model_meshes(model, 16)
    actual_root = aero.root
    calls = []

    def checked_root(residual, seed, **kwargs):
        # The fixed-geometry analytic callback omits circulation-dependent jet
        # feedback; MINPACK must differentiate the full residual in this case.
        assert kwargs['jac'] is None
        calls.append(True)
        return actual_root(residual, seed, **kwargs)

    monkeypatch.setattr(aero, 'root', checked_root)
    result = aero.evaluate_aerodynamics(model, condition, meshes)
    assert calls == [True] and result['circulation_solver']['method'] == 'direct'
    assert result['residual'] < 1e-8 and result['engines'][0]['thrust'] > 0
    replay = aero.evaluate_aerodynamics(model, condition, meshes,
        circulation=np.array([s['circulation'] for s in result['strips']]))
    assert calls == [True] and replay['residual'] < 1e-8
    np.testing.assert_allclose(replay['force'], result['force'], rtol=1e-12, atol=1e-12)
