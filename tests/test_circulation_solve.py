"""Independent roots, branch termination, and physical stalled-wing checks."""
from dataclasses import replace
from pathlib import Path
import numpy as np
import pytest
from openswing.circulation_solve import continue_circulation, CirculationContinuationError
from openswing.aero import FlightCondition, solve_rigid, evaluate_aerodynamics, AnalysisError
from openswing.asw import parse_asw
from openswing.geometry import model_meshes
from openswing.circulation import CirculationBasis

SOURCE = Path('examples/stall-branch.asw').read_text()


def test_continuation_recovers_independent_nonlinear_roots_and_removes_regularization():
    # R = [2-sinh(x), 3-y^3] has exactly these real roots. Its homotopy
    # preserves positive x,y from zero and has no fold along that path.
    events = []
    z, report = continue_circulation(lambda z: np.array([2-np.sinh(z[0]), 3-z[1]**3]),
                                    np.diag([2., .7]), progress=lambda *event: events.append(event))
    np.testing.assert_allclose(z, [np.arcsinh(2), np.cbrt(3)], atol=2e-10)
    assert report['final_regularization'] == 0
    assert report['trace'][-1]['parameter'] == 1
    assert all(a['parameter'] < b['parameter'] for a,b in zip(report['trace'], report['trace'][1:]))
    assert report['physical_residual'] < 1e-10
    assert events[-1] == ('static_circulation_continuation', report['attempts'], 600)


@pytest.mark.parametrize('radius', [0, .15])
def test_engine_without_a_plume_at_lifting_sections_uses_analytic_jacobian(monkeypatch, radius):
    from openswing import aero
    source = Path('examples/rectangular.asw').read_text()
    model = parse_asw(source + f'\nEngine\n1 0 1 0 4 0 0 -1 0 0 1 0 {radius} 0 0\nEnd\n')
    condition = FlightCondition(speed=30, alpha=4, powers={1:2})
    native_root = aero.root
    seen = []

    def checked_root(function, guess, *, jac, **options):
        assert jac is not None
        seen.append(True)
        return native_root(function, guess, jac=jac, **options)

    monkeypatch.setattr(aero, 'root', checked_root)
    result = solve_rigid(model, condition, 8, circulation_method='direct')
    assert seen
    assert result['residual'] < 1e-8
    assert result['engines'][0]['thrust'] == 2
    assert result['engines'][0]['jet_enabled'] == (radius > 0)


def test_regularized_zero_branch_selects_first_of_three_known_roots():
    z, report = continue_circulation(lambda z: -(z-1)*(z-2)*(z-3), np.eye(1))
    assert z[0] == pytest.approx(1., abs=1e-10)
    assert report['steps'] > 1


@pytest.mark.parametrize('spread', [.01, .2])
def test_continuation_resolves_nearby_corners_with_independent_unique_roots(spread):
    # Sixteen independent piecewise-linear equations have closely spaced
    # slope changes along the homotopy and unique positive final roots.
    # The former fixed minimum step stopped short of these corners.
    forcing = 2.6+spread*np.cos(np.arange(16)*.3)
    z, report = continue_circulation(
        lambda z: forcing-z-40*np.maximum(z-1.2, 0), np.eye(16),
        derivative=lambda z: np.diag(-1-40*(z > 1.2)))
    np.testing.assert_allclose(z, (forcing+48)/41, rtol=0, atol=2e-12)
    assert report['trace'][-1]['parameter'] == 1
    assert report['final_regularization'] == 0
    assert report['physical_residual'] < 1e-11


def test_fold_without_real_endpoint_never_returns_partial_solution():
    # H=lambda(x²+1)-(1-lambda)x folds at lambda=1/3, x=1.
    with pytest.raises(CirculationContinuationError, match='no full physical solution'):
        continue_circulation(lambda z: z*z+1, np.eye(1))


def test_arclength_crosses_two_folds_to_independently_known_endpoint():
    # R=(3-x)(x²-x+.5) has exactly one real zero, x=3. Lambda=x/(R+x)
    # has two interior turning points where R-x R'=2x³-4x²+1.5=0.
    traces = []
    for step in [.1, .02]:
        z, report = continue_circulation(lambda x: (3-x)*(x*x-x+.5), np.eye(1), max_step=step)
        assert z[0] == pytest.approx(3., abs=1e-10)
        parameters = [r['parameter'] for r in report['trace']]
        assert any(b < a for a, b in zip(parameters, parameters[1:]))
        assert report['final_regularization'] == 0
        traces.append(report)
    assert traces[1]['steps'] > traces[0]['steps']


@pytest.mark.parametrize('panels,alpha', [(24, 60.), (96, 75.)])
def test_stall_path_refinement_recovers_the_same_physical_root(monkeypatch, panels, alpha):
    import openswing.circulation_solve as solver
    original = solver.continue_circulation
    model = parse_asw(SOURCE)
    condition = FlightCondition(speed=47.9, alpha=alpha, mach=0.)
    a = solve_rigid(model, condition, panels)
    def refined(*args, **kwargs):
        return original(*args, **kwargs, max_step=.02)
    monkeypatch.setattr(solver, 'continue_circulation', refined)
    b = solve_rigid(model, condition, panels)
    np.testing.assert_allclose(a['force'], b['force'], rtol=2e-10, atol=1e-8)
    np.testing.assert_allclose([s['circulation'] for s in a['strips']],
                              [s['circulation'] for s in b['strips']], rtol=2e-9, atol=2e-8)


@pytest.mark.parametrize('mach', [0., None])
def test_stalled_incidence_reflection_selects_same_branch(mach):
    model = parse_asw(SOURCE)
    positive = FlightCondition(speed=47.9, alpha=60, mach=mach, density=1.2256)
    a = solve_rigid(model, positive, 96)
    b = solve_rigid(model, replace(positive, alpha=-60), 96)
    assert a['circulation_solver']['method'] == b['circulation_solver']['method'] == 'continuation'
    for k in ['CL', 'Cm']:
        assert a[k] == pytest.approx(-b[k], abs=1e-8)
    assert a['CD'] == pytest.approx(b['CD'], abs=1e-8)
    np.testing.assert_allclose([s['circulation'] for s in a['strips']],
                              [-s['circulation'] for s in b['strips']], atol=2e-7)
    # Re-evaluate through the original physical residual with gamma prescribed:
    # no regularizer, solver iteration, averaging or symmetry projection remains.
    r = evaluate_aerodynamics(model, positive, model_meshes(model, 96),
                              circulation=np.array([s['circulation'] for s in a['strips']]))
    assert r['residual'] < 1e-9
    np.testing.assert_allclose(r['force'], a['force'], atol=1e-9)


def test_regularization_does_not_change_resolved_measured_range_root():
    model = parse_asw(SOURCE)
    condition = FlightCondition(speed=47.9, alpha=18.091, mach=0.)
    a = solve_rigid(model, condition, 48, circulation_method='direct')
    b = solve_rigid(model, condition, 48, circulation_method='continuation')
    for k in ['CL', 'CD', 'Cm']:
        assert a[k] == pytest.approx(b[k], abs=1e-8)


def test_invalid_method_is_not_silently_ignored():
    with pytest.raises(AnalysisError, match='Circulation method'):
        solve_rigid(parse_asw(SOURCE), FlightCondition(), 8, circulation_method='guess')


@pytest.mark.parametrize('modes,rate', [(0, 0.), (0, .3), (8, .3)])
@pytest.mark.parametrize('width', [1e-310, .05, 1e100])
def test_analytic_tangent_matches_perturbed_complete_flow_residual(monkeypatch, modes, rate, width):
    import openswing.circulation_solve as solver
    original = solver.continue_circulation
    checked = []
    def inspect(residual, regularizer, *, derivative, **kwargs):
        assert derivative is not None
        n = len(regularizer)
        for amplitude in [-1.8, -.6, 0., .6, 1.8]:
            z = amplitude*np.cos(np.arange(n)*.37)
            direction = np.sin(np.arange(n)*.73+.4)
            h = 2e-6
            measured = (residual(z+h*direction)-residual(z-h*direction))/(2*h)
            np.testing.assert_allclose(derivative(z)@direction, measured, rtol=2e-7, atol=2e-8)
            checked.append(amplitude)
        return original(residual, regularizer, derivative=derivative, **kwargs)
    monkeypatch.setattr(solver, 'continue_circulation', inspect)
    model = parse_asw(SOURCE)
    meshes = model_meshes(model, 16)
    condition = FlightCondition(speed=47.9, alpha=25, circulation_modes={1: modes}, stall_width=width)
    basis = CirculationBasis(meshes, condition.circulation_modes)
    result = evaluate_aerodynamics(model, condition, meshes,
        circulation_rate=basis.decode(rate*np.cos(np.arange(basis.size)*.3)),
        circulation_method='continuation')
    assert len(checked) == 5 and result['residual'] < 1e-9
