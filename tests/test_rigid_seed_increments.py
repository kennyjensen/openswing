"""Nearly zero physical seeds must not collapse the circulation Newton step."""
from copy import deepcopy
import json
from pathlib import Path

import numpy as np
import pytest

from openswing import bridge
from openswing.aero import FlightCondition, evaluate_aerodynamics, solve_rigid
from openswing.asw import parse_asw
from openswing.circulation import CirculationBasis
from openswing.geometry import model_meshes

WITNESS = json.loads(Path('tests/fixtures/rigid-subnormal-seed.json').read_text())


def test_literal_browser_seed_converges_directly_without_changing_the_seed():
    request = dict(deepcopy(WITNESS['request']), initial_circulation=WITNESS['seed'])
    original = deepcopy(request)
    result = bridge.dispatch(request)
    assert request == original and result['residual'] < 1e-10
    start = result['circulation_solver']['initialization']
    assert start['seed_attempt']['accepted'] and not start['cold_fallback']
    assert start['initial_circulation'] == WITNESS['seed']
    control = bridge.dispatch(dict(request, initial_circulation=[0.]*len(WITNESS['seed'])))
    for key in ('force', 'moment', 'CL', 'CD', 'CDi', 'Cm'):
        np.testing.assert_allclose(result[key], control[key], rtol=1e-10, atol=1e-10)


@pytest.mark.parametrize('modes', [0, 4])
@pytest.mark.parametrize('amplitude', [0., 5e-324, -1e-300, 1e-18, -1e-5, .3])
def test_small_seed_magnitude_does_not_change_the_unstalled_root(modes, amplitude):
    model = parse_asw(WITNESS['request']['source'])
    condition = FlightCondition(speed=30., alpha=5., mach=0., circulation_modes={1:modes})
    meshes = model_meshes(model, 12)
    basis = CirculationBasis(meshes, condition.circulation_modes)
    seed = basis.decode(amplitude*np.cos(.7*np.arange(basis.size)))
    seeded = solve_rigid(model, condition, 12, initial_circulation=seed, circulation_method='direct')
    cold = solve_rigid(model, condition, 12, circulation_method='direct')
    assert seeded['residual'] < 1e-10
    assert seeded['circulation_solver']['initialization']['seed_attempt']['accepted']
    gamma = [strip['circulation'] for strip in seeded['strips']]
    fresh = evaluate_aerodynamics(model, condition, meshes, circulation=gamma)
    assert fresh['residual'] < 1e-10
    for key in ('force','moment','CL','CD','CDi','Cm'):
        np.testing.assert_allclose(seeded[key], cold[key], rtol=1e-10, atol=1e-10)
        np.testing.assert_allclose(seeded[key], fresh[key], rtol=1e-12, atol=1e-12)


def dimensional_wing(length_unit, time_unit, force_unit):
    u, t, f = length_unit, time_unit, force_unit
    density = 1.225*u**4/(f*t**2)
    source = f'''Name
Dimensional seed check
End
Unit
L {u} m
T {t} s
F {f} N
End
Constant
{9.80665*t*t/u} {density} {340.294*t/u}
End
Reference
{12/u**2} {1/u} {12/u}
End
Beam 1
Wing
t y chord Xax
0 0 {1/u} .25
{6/u} {6/u} {1/u} .25
t Cdf dCLda CLmax CLmin
0 .008 6.283185307179586 1.2 -1.2
{6/u} .008 6.283185307179586 1.2 -1.2
End
'''
    return parse_asw(source), FlightCondition(speed=30*t/u, alpha=5., mach=0., density=density)


@pytest.mark.parametrize('units', [(.001,1.,1.), (.3048,1.,4.4482216152605), (1000.,100.,10000.)])
@pytest.mark.parametrize('modes', [0, 4])
def test_increment_scale_and_solution_transform_with_consistent_input_units(units, modes):
    results = []
    for u,t,f in ((1.,1.,1.), units):
        model, condition = dimensional_wing(u,t,f)
        condition.circulation_modes = {1:modes}
        meshes = model_meshes(model, 12)
        basis = CirculationBasis(meshes, condition.circulation_modes)
        seed = basis.decode(np.full(basis.size, 15.*t/u**2*1e-18))
        result = solve_rigid(model, condition, 12, initial_circulation=seed, circulation_method='direct')
        assert result['residual'] < 1e-10
        assert result['circulation_solver']['initialization']['coefficient_scale'] == pytest.approx(15.*t/u**2)
        results.append(dict(CL=result['CL'], CD=result['CD'], CDi=result['CDi'], Cm=result['Cm'],
            force=np.asarray(result['force'])*f, moment=np.asarray(result['moment'])*f*u,
            circulation=np.array([s['circulation'] for s in result['strips']])*u*u/t))
    for key in results[0]:
        np.testing.assert_allclose(results[0][key], results[1][key], rtol=1e-10, atol=1e-10)


def test_empty_seed_on_a_nonlifting_model_stays_a_valid_no_unknowns_solve():
    model = parse_asw(Path('examples/instrumented-oscillator.asw').read_text())
    result = solve_rigid(model, FlightCondition(speed=10., mach=0.), 4,
                         initial_circulation=np.empty(0), circulation_method='direct')
    assert result['converged']
    assert result['circulation_solver']['initialization']['seed_attempt']['solver_evaluations'] == 0


@pytest.mark.parametrize('modes', [0,4])
@pytest.mark.parametrize('alpha', [0.,1e-12,1e-18])
def test_finishing_preserves_relative_accuracy_of_tiny_nonzero_roots(alpha,modes):
    model,condition=dimensional_wing(1.,1.,1.)
    condition.alpha=alpha;condition.circulation_modes={1:modes}
    basis=CirculationBasis(model_meshes(model,12),condition.circulation_modes)
    seed=basis.decode(np.ones(basis.size))
    result=solve_rigid(model,condition,12,initial_circulation=seed,circulation_method='direct')
    expected=solve_rigid(model,condition,12,circulation_method='direct')
    actual_gamma=np.array([s['circulation'] for s in result['strips']])
    expected_gamma=np.array([s['circulation'] for s in expected['strips']])
    if alpha:
        assert np.max(abs(actual_gamma))>0.
        np.testing.assert_allclose(actual_gamma,expected_gamma,rtol=2e-10,atol=0.)
        assert result['efficiency']==pytest.approx(expected['efficiency'],rel=2e-10)
    else:
        assert np.max(abs(actual_gamma))<1e-300
        assert result['efficiency']==expected['efficiency']==0.
