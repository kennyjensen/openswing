"""Terminal circulation correction preserves the physical residual and scope."""
import numpy as np
import pytest

import openswing.aero as aero
import openswing.circulation_polish as polish
import openswing.circulation_solve as continuation
from openswing.asw import parse_asw
from openswing.circulation import CirculationBasis
from openswing.geometry import model_meshes


def test_resolved_state_does_not_evaluate_residual_or_derivative():
    def forbidden(*args):
        raise AssertionError('An already resolved state needs no evaluation.')
    gamma = np.array([.3, -.2])
    value = np.zeros(2)
    actual, residual, report = polish.polish_circulation(forbidden, forbidden, gamma, value, scale=1.)
    np.testing.assert_array_equal(actual, gamma)
    np.testing.assert_array_equal(residual, value)
    assert report['evaluations'] == report['jacobians'] == report['accepted_steps'] == 0
    assert report['target_met']


@pytest.mark.parametrize('scale', [1e-6, 1., 1e6])
def test_coupled_analytic_root_is_invariant_under_circulation_units(scale):
    matrix = np.array([[2., 1.], [-1., 3.]])
    exact = np.array([.4, -.2])
    residual = lambda gamma: matrix@(gamma/scale-exact)
    initial = scale*(exact+np.array([1e-10, -2e-10]))
    saved = initial.copy()
    gamma, value, report = polish.polish_circulation(
        residual, lambda _: matrix/scale, initial, residual(initial), scale=scale)
    np.testing.assert_array_equal(initial, saved)
    np.testing.assert_allclose(gamma/scale, exact, rtol=0., atol=2*np.finfo(float).eps)
    assert report['target_met'] and report['accepted_steps'] == 1
    np.testing.assert_array_equal(value, residual(gamma))


@pytest.mark.parametrize('start,accepted', [(1.+2e-10, True), (0., False)])
def test_three_root_polynomial_only_accepts_a_local_correction(start, accepted):
    residual = lambda gamma: -(gamma-1)*(gamma-2)*(gamma-3)
    derivative = lambda gamma: np.diag(-3*gamma**2+12*gamma-11)
    initial = np.array([start])
    gamma, value, report = polish.polish_circulation(
        residual, derivative, initial, residual(initial), scale=1.)
    if accepted:
        np.testing.assert_array_equal(gamma, [1.])
        assert report['target_met']
    else:
        np.testing.assert_array_equal(gamma, initial)
        np.testing.assert_array_equal(value, residual(initial))
        assert report['status'] == 'NONLOCAL_CORRECTION_RETAINED'


@pytest.mark.parametrize('failure', ['singular', 'nonfinite_derivative', 'wrong_sign', 'nonfinite_trial'])
def test_failed_correction_keeps_original_state_and_residual(failure):
    initial = np.array([2e-10])
    residual = (lambda gamma: np.full_like(gamma, np.nan)) if failure == 'nonfinite_trial' else (lambda gamma: gamma)
    derivative = {
        'singular': lambda _: np.zeros((1, 1)),
        'nonfinite_derivative': lambda _: np.full((1, 1), np.nan),
        'wrong_sign': lambda _: -np.eye(1),
        'nonfinite_trial': lambda _: np.eye(1),
    }[failure]
    gamma, value, report = polish.polish_circulation(residual, derivative, initial, initial, scale=1.)
    np.testing.assert_array_equal(gamma, initial)
    np.testing.assert_array_equal(value, initial)
    assert not report['target_met'] and report['accepted_steps'] == 0


@pytest.mark.parametrize('location', ['derivative', 'residual'])
def test_domain_rejection_retains_state_and_records_failure(location):
    def rejected(*args):
        raise ValueError('Deliberate domain rejection')
    initial = np.array([2e-10])
    gamma, value, report = polish.polish_circulation(
        rejected if location == 'residual' else lambda gamma: gamma,
        rejected if location == 'derivative' else lambda _: np.eye(1),
        initial, initial, scale=1.)
    np.testing.assert_array_equal(gamma, initial)
    np.testing.assert_array_equal(value, initial)
    if location == 'derivative':
        assert report['status'] == 'JACOBIAN_DOMAIN_FAILURE_RETAINED'
    else:
        trials = report['corrections'][0]['trials']
        assert len(trials) == 7
        assert all(row['status'] == 'RESIDUAL_DOMAIN_FAILURE_RETAINED' for row in trials)


@pytest.mark.parametrize('location', ['derivative', 'residual'])
def test_observation_timeout_is_never_swallowed(location):
    def timeout(*args):
        raise TimeoutError('Observation cap')
    initial = np.array([2e-10])
    with pytest.raises(TimeoutError, match='Observation cap'):
        polish.polish_circulation(
            timeout if location == 'residual' else lambda gamma: gamma,
            timeout if location == 'derivative' else lambda _: np.eye(1),
            initial, initial, scale=1.)


SOURCE = '''Name
Small circulation correction control
End
Unit
L 1 m
T 1 s
F 1 N
End
Constant
9.81 1.2256 340
End
Reference
4 1 4
End
Beam 1
Wing
t y chord Xax
1 -2 1 .25
5 2 1 .25
t dCLda CLmax CLmin
1 6.283185307179586 1.2 -1.2
5 6.283185307179586 1.2 -1.2
End
'''


def setup(*, modes=None, powered=False, frozen=False):
    source = SOURCE
    if powered:
        row = np.zeros(25)
        row[:15] = [1, 0, 1, 3, -1.5, 0, -.3, -1, 0, 0, 1., -.03, 1.2, 150., .002]
        source += '\nEngine\n'+' '.join(map(str, row))+'\nEnd\n'
    model = parse_asw(source)
    meshes = model_meshes(model, 6)
    condition = aero.FlightCondition(speed=27., alpha=7., beta=3., mach=.2,
        stall=False, freeze_influences=frozen, circulation_modes=modes or {},
        powers={1:250.} if powered else {})
    basis = CirculationBasis(meshes, condition.circulation_modes)
    rate = basis.decode(np.linspace(.03, .07, basis.size))
    return model, condition, meshes, basis, rate


def inexact_endpoint(monkeypatch):
    """Perturb a genuine continuation endpoint without changing its equations."""
    original = continuation.continue_circulation
    records = []
    def wrapped(residual, regularizer, **kwargs):
        solved, report = original(residual, regularizer, **kwargs)
        perturbed = solved+1e-9*np.linspace(.7, 1.3, len(solved))
        records.append(dict(gamma_scaled=perturbed.copy(), residual=residual(perturbed).copy()))
        return perturbed, report
    monkeypatch.setattr(continuation, 'continue_circulation', wrapped)
    return records


@pytest.mark.parametrize('frozen', [False, True])
def test_inexact_continuation_endpoint_is_corrected_before_physical_loads(monkeypatch, frozen):
    model, condition, meshes, basis, rate = setup(frozen=frozen)
    endpoints = inexact_endpoint(monkeypatch)
    result = aero.evaluate_aerodynamics(model, condition, meshes,
        circulation_rate=rate, circulation_method='continuation')
    assert len(endpoints) == 1
    assert np.max(abs(endpoints[0]['residual'])) > 1e-12
    metadata = result['circulation_solver']['terminal_polish']
    assert metadata['accepted_steps'] > 0 and metadata['target_met']
    assert result['residual'] <= 1e-12
    gamma = np.array([strip['circulation'] for strip in result['strips']])
    initial = endpoints[0]['gamma_scaled']*(.5*condition.speed)
    assert np.max(abs(gamma-initial)) > 0
    replay = aero.evaluate_aerodynamics(model, condition, meshes,
        circulation=gamma, circulation_rate=rate)
    stale = aero.evaluate_aerodynamics(model, condition, meshes,
        circulation=initial, circulation_rate=rate)
    for key in ['circulation_residual', 'circulation_local_residual', 'force', 'moment',
                'circulation_rate_force', 'circulation_rate_moment', 'strips']:
        assert result[key] == replay[key]
    assert np.linalg.norm(np.array(result['force'])-stale['force']) > 0
    assert replay['residual'] <= 1e-12 < stale['residual']


@pytest.mark.parametrize('modes,powered,frozen', [({},False,False),({1:3},False,True),({},True,True)])
def test_supplied_circulation_and_loads_are_untouched(monkeypatch, modes, powered, frozen):
    def forbidden(*args, **kwargs):
        raise AssertionError('Supplied Gamma must never invoke terminal polish.')
    monkeypatch.setattr(polish, 'polish_circulation', forbidden)
    model, condition, meshes, basis, rate = setup(modes=modes,powered=powered,frozen=frozen)
    gamma = basis.decode(np.linspace(.7,1.3,basis.size))
    original = gamma.copy()
    result = aero.evaluate_aerodynamics(model,condition,meshes,circulation=gamma,circulation_rate=rate)
    np.testing.assert_array_equal(gamma,original)
    np.testing.assert_array_equal([strip['circulation'] for strip in result['strips']],original)
    assert result['residual'] > 1e-12
    assert result['circulation_solver'] == dict(method='prescribed',evaluations=0)


@pytest.mark.parametrize('modes,powered', [({1:3},False),({},True)])
def test_fourier_and_engine_terminal_states_skip_polishing(monkeypatch, modes, powered):
    def forbidden(*args, **kwargs):
        raise AssertionError('Fourier and engine states are outside polish scope.')
    monkeypatch.setattr(polish, 'polish_circulation', forbidden)
    model,condition,meshes,basis,rate = setup(modes=modes,powered=powered)
    endpoints = inexact_endpoint(monkeypatch)
    result = aero.evaluate_aerodynamics(model,condition,meshes,circulation_rate=rate,
                                       circulation_method='continuation')
    assert len(endpoints) == 1
    assert 1e-12 < result['residual'] < 1e-8
    assert 'terminal_polish' not in result['circulation_solver']
    expected = basis.decode(endpoints[0]['gamma_scaled']*(.5*condition.speed))
    np.testing.assert_array_equal([strip['circulation'] for strip in result['strips']],expected)
