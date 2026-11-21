"""Physical Gamma seeds are corrected, audited, and separate from prescription.

Only small synthetic wings are used. No archived aircraft or startup history
is inferred from these numerical initialization tests.
"""
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

import openswing.aero as aero
import openswing.circulation_solve as continuation
import openswing.circulation_polish as polish
from openswing.asw import parse_asw
from openswing.circulation import CirculationBasis
from openswing.geometry import model_meshes

SOURCE = Path('examples/stall-branch.asw').read_text()


def setup(modes=0, alpha=18., *, powered=False):
    source = SOURCE
    if powered:
        row = np.zeros(25)
        row[:15] = [1, 0, 1, 0, -1.5, 0, -.3, -1, 0, 0, 1., -.03, 1.2, 150., .002]
        source += '\nEngine\n'+' '.join(map(str, row))+'\nEnd\n'
    model = parse_asw(source)
    condition = aero.FlightCondition(speed=27., alpha=alpha, mach=.15,
        circulation_modes={1: modes}, powers={1: 250.} if powered else {})
    meshes = model_meshes(model, 12)
    return model, condition, meshes, CirculationBasis(meshes, condition.circulation_modes)


def physical_gamma(result):
    return np.array([s['circulation'] for s in result['strips'] if s.get('lifting')])


@pytest.mark.parametrize('modes', [0, 4])
@pytest.mark.parametrize('method', ['auto', 'direct'])
def test_seed_is_corrected_with_exact_jacobian_and_fresh_physical_residual(monkeypatch, modes, method):
    model, condition, meshes, basis = setup(modes)
    seed = basis.decode(np.linspace(1., 2., basis.size))
    original = seed.copy()
    seed.setflags(write=False)
    calls = []
    actual_root = aero.root

    def checked_root(fun, x0, **kwargs):
        if not calls:
            np.testing.assert_array_equal(x0, np.zeros(basis.size))
        assert kwargs['method'] == 'hybr' and kwargs['options'] == {'xtol': 1e-10}
        direction = np.cos(.7*np.arange(len(x0))+.2)
        h = 2e-6
        centered = (fun(x0+h*direction)-fun(x0-h*direction))/(2*h)
        np.testing.assert_allclose(kwargs['jac'](x0)@direction, centered, rtol=3e-7, atol=2e-9)
        calls.append(True)
        return actual_root(fun, x0, **kwargs)

    monkeypatch.setattr(aero, 'root', checked_root)
    result = aero.solve_rigid(model, condition, 12, circulation_method=method, initial_circulation=seed)
    assert 1 <= len(calls) <= 2
    np.testing.assert_array_equal(seed, original)
    gamma = physical_gamma(result)
    assert np.max(abs(gamma-original)) > .1
    fresh = aero.evaluate_aerodynamics(model, condition, meshes, circulation=gamma)
    assert result['residual'] <= 1e-8 and fresh['residual'] <= 1e-8
    for name in ('force', 'moment', 'CL', 'CD', 'CDi', 'Cm'):
        np.testing.assert_allclose(result[name], fresh[name], rtol=1e-12, atol=1e-12)
    report = result['circulation_solver']
    assert report['method'] == 'direct'
    init = report['initialization']
    assert not init['cold_fallback'] and init['seed_attempt']['accepted']
    assert init['seed_attempt']['derivative'] == 'analytic'
    assert init['seed_attempt']['final_physical_residual'] == result['residual']
    assert report['evaluations'] == result['evaluations'] >= init['seed_attempt']['evaluations'] > 0
    np.testing.assert_array_equal(init['initial_circulation'], original)


@pytest.mark.parametrize('invalid', [None, 'shape', 'matrix', 'nan', 'infinity', 'complex', 'text'])
def test_invalid_seed_rejected_before_root(monkeypatch, invalid):
    model, condition, meshes, basis = setup()
    values = {'shape': np.zeros(basis.panels-1), 'matrix': np.zeros((basis.panels, 1)),
        'nan': np.full(basis.panels, np.nan), 'infinity': np.full(basis.panels, np.inf),
        'complex': np.full(basis.panels, 1j), 'text': ['bad']*basis.panels,
        None: 1.}
    def forbidden(*args, **kwargs):
        raise AssertionError('Invalid initial circulation must not reach a solve')
    monkeypatch.setattr(aero, 'root', forbidden)
    with pytest.raises(aero.AnalysisError, match='Invalid initial circulation'):
        aero.evaluate_aerodynamics(model, condition, meshes, initial_circulation=values[invalid])


def test_seed_outside_fourier_space_is_not_projected(monkeypatch):
    model, condition, meshes, basis = setup(2)
    def forbidden(*args, **kwargs):
        raise AssertionError('An invalid Fourier seed must not be projected and solved')
    monkeypatch.setattr(aero, 'root', forbidden)
    with pytest.raises(aero.AnalysisError, match='outside the selected Fourier space'):
        aero.evaluate_aerodynamics(model, condition, meshes, initial_circulation=np.ones(basis.panels))


@pytest.mark.parametrize('extra,message', [({'circulation': []}, 'prescribed circulation'),
                                         ({'circulation_method': 'continuation'}, 'explicit continuation')])
def test_incompatible_seed_requests_rejected(extra, message):
    model, condition, meshes, basis = setup()
    with pytest.raises(aero.AnalysisError, match=message):
        aero.evaluate_aerodynamics(model, condition, meshes, initial_circulation=np.zeros(basis.panels), **extra)


@pytest.mark.parametrize('modes', [0, 4])
@pytest.mark.parametrize('failure', ['residual', 'nonfinite', 'exception'])
def test_auto_seed_failure_runs_same_cold_algorithm_and_preserves_attempt(monkeypatch, modes, failure):
    model, condition, meshes, basis = setup(modes)
    cold = aero.evaluate_aerodynamics(model, condition, meshes)
    actual_root = aero.root
    calls = []
    def fail_once(fun, x0, **kwargs):
        if not calls:
            calls.append(True)
            fun(x0)
            if failure == 'exception':
                raise np.linalg.LinAlgError('Injected seeded solve failure')
            value = np.full_like(x0, np.nan) if failure == 'nonfinite' else x0.copy()
            return SimpleNamespace(x=value, nfev=1, njev=0, success=True, message='Injected false success')
        return actual_root(fun, x0, **kwargs)
    monkeypatch.setattr(aero, 'root', fail_once)
    result = aero.evaluate_aerodynamics(model, condition, meshes, initial_circulation=np.zeros(basis.panels))
    init = result['circulation_solver']['initialization']
    assert init['cold_fallback'] and not init['seed_attempt']['accepted']
    assert result['circulation_solver']['method'] == cold['circulation_solver']['method']
    for name in ('force', 'moment', 'CL', 'CD', 'CDi', 'Cm', 'circulation_residual', 'strips'):
        assert result[name] == cold[name]
    assert result['evaluations'] == cold['evaluations']+init['seed_attempt']['evaluations']


@pytest.mark.parametrize('candidate', ['finite', 'nonfinite'])
def test_direct_seed_false_success_cannot_bypass_residual_gate(monkeypatch, candidate):
    # Truncated Fourier uses its declared projected residual and has no polish.
    model, condition, meshes, basis = setup(4)
    def unsuccessful(fun, x0, **kwargs):
        fun(x0)
        return SimpleNamespace(x=x0.copy() if candidate == 'finite' else np.full_like(x0, np.nan),
            success=True, nfev=1, njev=0, message='Injected false success')
    def forbidden(*args, **kwargs):
        raise AssertionError('Explicit direct must not run cold continuation')
    monkeypatch.setattr(aero, 'root', unsuccessful)
    monkeypatch.setattr(continuation, 'continue_circulation', forbidden)
    with pytest.raises(aero.AnalysisError, match='Circulation solve failed: normalized residual') as caught:
        aero.evaluate_aerodynamics(model, condition, meshes, initial_circulation=np.zeros(basis.panels),
                                  circulation_method='direct')
    init = caught.value.details['initialization']
    assert not init['seed_attempt']['accepted'] and not init['cold_fallback']
    assert init['seed_attempt']['reported_success'] is True


def test_seed_attempt_does_not_require_a_cold_linear_solve(monkeypatch):
    model, condition, meshes, basis = setup()
    def forbidden(*args, **kwargs):
        raise AssertionError('An accepted user seed must precede the cold linear solve')
    monkeypatch.setattr(np.linalg, 'solve', forbidden)
    result = aero.evaluate_aerodynamics(model, condition, meshes,
        initial_circulation=np.zeros(basis.panels), circulation_method='direct')
    assert result['residual'] < 1e-8


def test_engine_seed_uses_complete_numerical_feedback(monkeypatch):
    model, condition, meshes, basis = setup(alpha=7., powered=True)
    actual_root = aero.root
    calls = []
    def checked(fun, x0, **kwargs):
        assert kwargs['jac'] is None
        calls.append(True)
        return actual_root(fun, x0, **kwargs)
    monkeypatch.setattr(aero, 'root', checked)
    result = aero.evaluate_aerodynamics(model, condition, meshes,
        initial_circulation=np.zeros(basis.panels), circulation_method='direct')
    assert 1 <= len(calls) <= 2 and result['residual'] < 1e-8
    assert result['circulation_solver']['initialization']['seed_attempt']['derivative'] == 'numerical engine feedback'
    replay = aero.evaluate_aerodynamics(model, condition, meshes, circulation=physical_gamma(result))
    np.testing.assert_allclose(replay['force'], result['force'], atol=1e-12)


def test_seed_failure_remains_in_cold_failure_details(monkeypatch):
    model, condition, meshes, basis = setup(alpha=1.)
    def unsuccessful(fun, x0, **kwargs):
        fun(x0)
        return SimpleNamespace(x=np.zeros_like(x0), success=False, nfev=1, njev=0, message='Injected failure')
    def failed_continuation(*args, **kwargs):
        raise continuation.CirculationContinuationError('Injected cold failure')
    monkeypatch.setattr(aero, 'root', unsuccessful)
    monkeypatch.setattr(continuation, 'continue_circulation', failed_continuation)
    with pytest.raises(aero.AnalysisError, match='Injected cold failure') as caught:
        aero.evaluate_aerodynamics(model, condition, meshes, initial_circulation=np.zeros(basis.panels))
    assert caught.value.details['initialization']['cold_fallback']
    assert not caught.value.details['initialization']['seed_attempt']['accepted']


def test_seed_does_not_swallow_external_deadline(monkeypatch):
    model, condition, meshes, basis = setup()
    def timed_out(*args, **kwargs):
        raise TimeoutError('External bounded deadline')
    monkeypatch.setattr(aero, 'root', timed_out)
    with pytest.raises(TimeoutError, match='External bounded deadline'):
        aero.evaluate_aerodynamics(model, condition, meshes, initial_circulation=np.zeros(basis.panels))


def test_accepted_seed_keeps_section_mach_rejection():
    model, condition, meshes, basis = setup()
    model.constants[2] = 1.
    with pytest.raises(aero.AnalysisError, match='Local section-normal Mach reaches unity') as caught:
        aero.evaluate_aerodynamics(model, condition, meshes, initial_circulation=np.zeros(basis.panels))
    assert caught.value.details['kind'] == 'section_normal_mach'


@pytest.mark.parametrize('stall', [False, True])
def test_explicit_none_preserves_default_results_and_metadata(stall):
    model, condition, meshes, _ = setup(alpha=7.)
    condition = replace(condition, stall=stall)
    default = aero.evaluate_aerodynamics(model, condition, meshes)
    explicit = aero.evaluate_aerodynamics(model, condition, meshes, initial_circulation=None)
    assert explicit == default
    assert 'initialization' not in default['circulation_solver']


def test_prescribed_circulation_remains_unsolved(monkeypatch):
    model, condition, meshes, basis = setup()
    def forbidden(*args, **kwargs):
        raise AssertionError('Prescribed Gamma must not trigger a solve or polish')
    monkeypatch.setattr(aero, 'root', forbidden)
    monkeypatch.setattr(polish, 'polish_circulation', forbidden)
    supplied = np.zeros(basis.panels)
    result = aero.evaluate_aerodynamics(model, condition, meshes, circulation=supplied)
    np.testing.assert_array_equal(physical_gamma(result), supplied)
    assert result['residual'] > 1e-8
    assert result['circulation_solver'] == {'method': 'prescribed', 'evaluations': 0}


@pytest.mark.parametrize('failure', ['nonlocal', 'nonfinite', 'exception'])
def test_finishing_failure_preserves_the_converged_incremental_solution(monkeypatch,failure):
    model,condition,meshes,basis=setup(modes=4,alpha=7.)
    seed=basis.decode(np.ones(basis.size))
    actual_root=aero.root
    candidates=[]
    def checked(fun,x0,**kwargs):
        if not candidates:
            result=actual_root(fun,x0,**kwargs)
            scale=max(.5*mesh.beam.value('chord',mesh.tm).max()*condition.speed for mesh in meshes if mesh.beam.lifting)
            candidates.append(basis.decode(basis.encode(seed)+scale*result.x))
            return result
        if failure=='exception':raise np.linalg.LinAlgError('Injected local refinement failure')
        value=np.full_like(x0,np.nan if failure=='nonfinite' else 100.)
        return SimpleNamespace(x=value,nfev=1,njev=0,success=True,message='Injected false finishing success')
    monkeypatch.setattr(aero,'root',checked)
    result=aero.evaluate_aerodynamics(model,condition,meshes,initial_circulation=seed,circulation_method='direct')
    assert result['residual']<1e-10
    assert not result['circulation_solver']['initialization']['seed_attempt']['refinement']['accepted']
    np.testing.assert_array_equal(physical_gamma(result),candidates[0])
