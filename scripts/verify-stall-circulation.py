"""Unchanged stall equations: branch selection, units and independent 2D limit.

This is a numerical verification study, not experimental validation. The 2D
reference follows the wind-aligned vortex/CP equations literally; it is not a
fit to the approximate high-incidence sketch in the formulation.
"""
import hashlib
import json
import platform
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import numpy as np
import scipy
from scipy.optimize import brentq
from openswing.aero import FlightCondition, solve_rigid, evaluate_aerodynamics, AnalysisError
from openswing.asw import parse_asw
from openswing.geometry import model_meshes
from openswing.circulation_solve import continue_circulation


def source_for(source, span=5.9, units=(1., 1., 1.)):
    """Change physical span and express the original SI wing in L/T/F units."""
    length, time, force = units
    return (source.replace('L 1 m\nT 1 s\nF 1 N', f'L {length:.17g} m\nT {time:.17g} s\nF {force:.17g} N')
        .replace('9.81 1.2256 340.21', f'{9.81*time*time/length:.17g} {1.2256*length**4/(force*time*time):.17g} {340.21*time/length:.17g}')
        .replace('5.9 1 5.9', f'{span/length**2:.17g} {1/length:.17g} {span/length:.17g}')
        .replace('0 0 0 0 1 0', f'0 0 0 0 {1/length:.17g} 0')
        .replace('2.95 0 2.95 0 1 0', f'2.95 0 {span/2/length:.17g} 0 {1/length:.17g} 0'))


def two_dimensional(alpha):
    """Independent scalar root, with a strict monotone bracket for |alpha|<=90."""
    angle = np.deg2rad(alpha)
    a0, width, strength = 6.2832, .05, 40.
    def f(cl):
        return width*np.logaddexp(0., (cl-1.2)/width)-width*np.logaddexp(0., (-1.2-cl)/width)
    # Infinite bound vortex at wind-aligned distance h*c from the CP gives
    # Vcp.n/U = sin(alpha)-cl*cos(alpha)/a0. There is no far-wake downwash.
    cl = brentq(lambda cl: a0*np.sin(angle)-cl*np.cos(angle)-strength*f(cl), -10., 10., xtol=1e-14)
    return dict(CL=float(cl), CD=float(.00352562+.00771413+4*(np.sin(angle)-cl*np.cos(angle)/a0)**2))


def compute(source, spec):
    units = spec.get('units', [1., 1., 1.])
    length, time, force = units
    span = spec.get('span', 5.9)
    model = parse_asw(source_for(source, span, units))
    assert not model.diagnostics
    condition = FlightCondition(speed=47.9*time/length, alpha=spec['alpha'], mach=spec.get('mach'),
                                circulation_modes={1: spec.get('modes', 0)})
    def continuation(*args, **kwargs):
        return continue_circulation(*args, **kwargs, max_step=spec.get('step', .04))
    with patch('openswing.circulation_solve.continue_circulation', continuation):
        result = solve_rigid(model, condition, spec['panels'], circulation_method=spec.get('method', 'auto'))
    gamma = np.array([s['circulation'] for s in result['strips']])
    # Independently call the physical residual with fixed circulation, bypassing
    # all initial guesses, continuation parameters and nonlinear root solvers.
    physical = evaluate_aerodynamics(model, condition, model_meshes(model, spec['panels']), circulation=gamma)
    assert physical['residual'] < 1e-8
    np.testing.assert_allclose(physical['force'], result['force'], rtol=2e-12, atol=1e-10/force)
    # Wrench integration and dimensional normalization do not use solver totals.
    summed_force = np.sum([s['force'] for s in result['strips']], axis=0)*force
    summed_moment = np.sum([np.cross(s['position'], s['force'])+s['moment'] for s in result['strips']], axis=0)*force*length
    np.testing.assert_allclose(summed_moment, np.array(result['moment'])*force*length, rtol=2e-12, atol=1e-8)
    a = np.deg2rad(spec['alpha'])
    qS = .5*1.2256*47.9**2*span
    np.testing.assert_allclose([summed_force@[-np.sin(a), 0, np.cos(a)]/qS,
                               summed_force@[np.cos(a), 0, np.sin(a)]/qS],
                              [result['CL'], result['CD']], rtol=2e-12, atol=1e-12)
    report = result['circulation_solver']
    if report['method'] == 'continuation':
        assert report['final_regularization'] == 0 and report['trace'][-1]['parameter'] == 1
    return dict(coefficients={k: result[k] for k in ['CL', 'CD', 'Cm', 'CY', 'Cl', 'Cn']},
                force_N=summed_force.tolist(), moment_Nm=summed_moment.tolist(),
                reference_scales=dict(force_N=qS, moment_Nm=[qS*span, qS, qS*span], circulation_m2_s=.5*47.9),
                circulation_m2_s=(gamma*length**2/time).tolist(), physical_residual=physical['residual'], solver=report)


def physical_values(result):
    # Near-zero moments on extremely long wings subtract O(q*S*span) terms.
    # Use the physical reference scales, not a dimensional absolute floor of 1.
    scales = result['reference_scales']
    return np.r_[list(result['coefficients'].values()), np.array(result['force_N'])/scales['force_N'],
                 np.array(result['moment_Nm'])/scales['moment_Nm'],
                 np.array(result['circulation_m2_s'])/scales['circulation_m2_s']]


def main():
    source = (ROOT/'examples/stall-branch.asw').read_text()
    cases = []
    def run(**spec):
        result = compute(source, spec)
        cases.append(dict(specification=spec, result=result))
        print(spec, result['coefficients']['CL'], result['coefficients']['CD'], flush=True)
        return result
    symmetry = []
    for mach in [0., None]:
        for panels in [24, 48, 96, 200]:
            a = run(alpha=60., mach=mach, panels=panels)
            b = run(alpha=-60., mach=mach, panels=panels)
            error = max(abs(a['coefficients'][k]-sign*b['coefficients'][k])
                        for k, sign in [('CL', -1), ('CD', 1), ('Cm', -1)])
            np.testing.assert_allclose(a['circulation_m2_s'], -np.array(b['circulation_m2_s']), rtol=2e-8, atol=2e-7)
            assert error < 1e-8
            symmetry.append(dict(mach=mach, panels=panels, error=error))
    # Full pointwise/Fourier equivalence and arbitrary consistent units.
    base = run(alpha=60., mach=0., panels=48)
    variants = []
    for extra in [dict(modes=48), dict(units=[.3048, .1, 4.4482216152605]), dict(units=[1000., 60., 1000.])]:
        other = run(alpha=60., mach=0., panels=48, **extra)
        error = float(np.max(abs(physical_values(other)-physical_values(base))/np.maximum(1., abs(physical_values(base)))))
        assert error < 2e-8
        variants.append(dict(settings=extra, maximum_scaled_difference=error))
    unchanged = []
    for alpha in [0., 8., 18.091, 25.]:
        a = run(alpha=alpha, mach=0., panels=48, method='direct')
        b = run(alpha=alpha, mach=0., panels=48, method='continuation')
        error = float(np.max(abs(physical_values(a)-physical_values(b))/np.maximum(1., abs(physical_values(a)))))
        assert error < 2e-8
        unchanged.append(dict(alpha=alpha, maximum_scaled_difference=error))
    limit = []
    for alpha in [-90., -85., -60., 60., 85., 90.]:
        reference = two_dimensional(alpha)
        errors = []
        for span in [5900., 59000.]:
            result = run(alpha=alpha, mach=0., panels=16, span=span)
            errors.append(max(abs(result['coefficients'][k]-reference[k]) for k in ['CL', 'CD']))
        assert errors[1] < 1e-4 and errors[1] < .2*errors[0]
        limit.append(dict(alpha=alpha, reference=reference, spans=[5900., 59000.], errors=errors))
    step_refinement = []
    for alpha, mach in [(75., 0.), (75., None), (85., None)]:
        results = [run(alpha=alpha, mach=mach, panels=96, step=step) for step in [.04, .02, .01]]
        values = [physical_values(r) for r in results]
        errors = [float(np.max(abs(a-values[-1])/np.maximum(1., abs(values[-1])))) for a in values[:-1]]
        assert max(errors) < 2e-8
        step_refinement.append(dict(alpha=alpha, mach=mach, steps=[.04, .02, .01], maximum_scaled_differences=errors))
    unresolved = []
    for alpha in [75., 85., 90.]:
        spec = dict(alpha=alpha, panels=96, mach=None)
        try:
            result = compute(source, spec)
            unresolved.append(dict(specification=spec, status='solved', result=result))
        except AnalysisError as error:
            unresolved.append(dict(specification=spec, status='unresolved', error=str(error)))
        print('Finite-wing diagnostic', spec, unresolved[-1]['status'], unresolved[-1].get('error', ''), flush=True)
    files = sorted(ROOT.glob('openswing/*.py'))+[Path(__file__), ROOT/'examples/stall-branch.asw', ROOT/'tests/test_circulation_solve.py']
    hashes = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    report = dict(scope='Numerical branch/units/2D verification of unchanged equations; not uniqueness, aircraft stability or experimental validation.',
                  comparison_scaling='Dimensionless coefficients; force/(q*S), moments/(q*S*[span,chord,span]), circulation/(U*chord/2).',
                  versions=dict(python=platform.python_version(), numpy=np.__version__, scipy=scipy.__version__),
                  source_sha256=hashes, cases=cases, reflection=symmetry, representation_and_units=variants,
                  direct_comparison=unchanged, two_dimensional_limit=limit, step_refinement=step_refinement,
                  finite_wing_diagnostics=unresolved)
    (ROOT/'docs/validation/stall-circulation.json').write_text(json.dumps(report, indent=2, allow_nan=False)+'\n')
    print(f'{len(cases)} verified cases; finite-wing diagnostics retained separately.', flush=True)


if __name__ == '__main__':
    main()
