"""SA-1 straight-wing comparison with archived ASWING and experimental data.

Run fetch-sa1.py first. Reference discrepancies are measured, never asserted away.
Both fixed-zero and speed-derived PG Mach are reported because the original run
does not explicitly choose a PG setting. No aerodynamic parameters are fitted.
"""
import csv
from decimal import Decimal
import hashlib
import io
import json
import platform
import runpy
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import numpy as np
import scipy
from openswing.aero import FlightCondition, solve_rigid, evaluate_aerodynamics
from openswing.asw import parse_asw
from openswing.geometry import model_meshes

MESHES = [24, 48, 96, 200, 400]
COEFFICIENTS = ['CL', 'CD', 'CDi', 'CDi_near', 'CDp', 'Cm', 'CY', 'Cl', 'Cn']
MODES = {'fixed_zero': 0., 'speed_derived': None}


def reference_data(directory):
    # The second column pair is a DIFFERENT numerical series, not an experiment.
    experiment = {}
    for key in ['CL', 'CD']:
        rows = list(csv.reader(io.StringIO((directory/f'SA_1_{key}.csv').read_text())))
        assert rows[0][0] in ('Exp', 'Expe') and rows[0][2] == 'Lifting_Line'
        assert rows[1] == ['X', 'Y', 'X', 'Y']
        experiment[key] = [dict(alpha_deg=float(r[0]), value=float(r[1])) for r in rows[2:] if r]
        assert len(experiment[key]) == 11
        assert np.all(np.diff([r['alpha_deg'] for r in experiment[key]]) > 0)
    text = (directory/'SA_1_CL.txt').read_text()
    assert 'alpha' in text and 'span eff.' in text
    rows = np.loadtxt(io.StringIO(text))
    assert rows.shape == (11, 10) and np.array_equal(rows[:, 0], np.arange(1, 12))
    aswing = [dict(zip(['index', 'sequence_time', 'alpha_deg', 'lift_N', 'drag_N',
                       'CL', 'CD', 'CDi', 'Cm', 'efficiency'], map(float, r))) for r in rows]
    assert np.all(np.diff(rows[:, 2]) > 0)
    # Independent dimensional normalization catches a wrong column or unit mapping.
    qS = .5*1.2256*47.9**2*5.9
    printed = [line.split() for line in text.splitlines() if line.strip() and not line.startswith('#')]
    def half_last_digit(token):
        return .5*10.**Decimal(token).as_tuple().exponent
    for tokens, r in zip(printed, aswing):
        for force_index, coefficient_index, force, coefficient in [(3, 5, 'lift_N', 'CL'), (4, 6, 'drag_N', 'CD')]:
            rounding_bound = half_last_digit(tokens[force_index])/qS + half_last_digit(tokens[coefficient_index])
            assert abs(r[force]/qS-r[coefficient]) <= rounding_bound+1e-14
    return dict(experiment=experiment, aswing_5_96=aswing)


def compute(source, spec):
    model = parse_asw(source)
    assert not model.diagnostics
    assert np.allclose(model.reference[0], [5.9, 1., 5.9], rtol=0, atol=1e-14)
    assert np.allclose(model.constants, [9.81, 1.2256, 340.21], rtol=0, atol=1e-14)
    condition = FlightCondition(speed=spec.get('speed', 47.9), alpha=spec['alpha_deg'],
                                mach=spec['mach'], density=spec.get('density', 1.2256))
    r = solve_rigid(model, condition, panels=spec['panels'])
    # Straight rectangular geometry, no point objects/engines: integrate every
    # reported strip wrench independently at the specified zero moment reference.
    strips = r['strips']
    force = np.sum([s['force'] for s in strips], axis=0)
    moment = np.sum([np.cross(s['position'], s['force'])+s['moment'] for s in strips], axis=0)
    alpha = np.deg2rad(spec['alpha_deg'])
    qS = .5*condition.density*condition.speed**2*5.9
    lift = force @ [-np.sin(alpha), 0, np.cos(alpha)]/qS
    drag = force @ [np.cos(alpha), 0, np.sin(alpha)]/qS
    errors = [abs(lift-r['CL']), abs(drag-r['CD']), abs(moment[1]/qS-r['Cm']),
              np.max(abs(force-r['force']))/qS, np.max(abs(moment-r['moment']))/qS,
              abs(r['CD']-r['CDi_near']-r['CDp']),
              abs(sum(s['length'] for s in strips)-5.9)/5.9]
    assert r['converged'] and r['residual'] < 1e-8
    assert max(errors) < 2e-10, errors
    assert r['CD'] > 0 and r['CDi'] >= -1e-12
    result = {k: float(r[k]) for k in COEFFICIENTS}
    result.update(force=r['force'], moment=r['moment'], mach=r['mach'],
                  residual=r['residual'], panels=r['panels'],
                  maximum_section_cl=float(max(abs(s['cl']) for s in strips)),
                  stalled_panels=sum(s['stalled'] for s in strips),
                  strip_wrench_and_normalization_error=float(max(errors)),
                  checks=7,
                  lateral_symmetry_error=max(abs(r[k]) for k in ['CY', 'Cl', 'Cn']),
                  # Selected spatial samples allow cross-platform shape checks
                  # without copying full solver reports into every polar row.
                  span_samples=[[s['t'], s['circulation'], s['cl']] for s in
                                [strips[i] for i in np.linspace(0, len(strips)-1, 9).astype(int)]])
    if spec['alpha_deg'] == 0:
        assert abs(result['CL']) < 1e-13 and abs(result['Cm']) < 1e-13
        assert abs(result['CD']-(.00352562+.00771413)) < 1e-13
        result['zero_incidence_analytical_error'] = abs(result['CD']-.01123975)
        result['checks'] += 3
    if abs(spec['alpha_deg']) <= 30:
        assert result['lateral_symmetry_error'] < 2e-10
        result['checks'] += 3
    return result


def branch_probe(source):
    """Distinguish residual asymmetry from different roots of symmetric equations."""
    model = parse_asw(source)
    positive = FlightCondition(speed=47.9, alpha=60., density=1.2256)
    negative = FlightCondition(speed=47.9, alpha=-60., density=1.2256)
    a = solve_rigid(model, positive, 96)
    b = solve_rigid(model, negative, 96)
    ga = np.array([s['circulation'] for s in a['strips']])
    gb = np.array([s['circulation'] for s in b['strips']])
    reflected = evaluate_aerodynamics(model, negative, model_meshes(model, 96), circulation=-ga)
    return dict(alpha_deg=60., panels=96, mach=a['mach'],
                positive_residual=a['residual'], independently_solved_negative_residual=b['residual'],
                mirrored_positive_root_negative_residual=reflected['residual'],
                maximum_circulation_difference=float(max(abs(ga+gb))),
                positive_CD=a['CD'], independently_solved_negative_CD=b['CD'],
                mirrored_positive_root_negative_CD=reflected['CD'],
                interpretation='Distinct low-residual roots can be selected in deep stall. Reflection preserves a root; small residual alone does not establish branch identity or physical validity.')


def physical(result):
    return np.r_[*[result[k] for k in COEFFICIENTS], result['force'], result['moment'],
                 np.ravel(result['span_samples'])]


def statistics(predicted, observed):
    error = np.asarray(predicted)-observed
    return dict(count=len(error), bias=float(np.mean(error)),
                rmse=float(np.sqrt(np.mean(error**2))), maximum_absolute_error=float(max(abs(error))))


def main(output=None):
    manifest_path = ROOT/'docs/validation/sa1-sources.json'
    manifest = json.loads(manifest_path.read_text())
    directory = ROOT/'.reference/isae-sa1'
    checker = runpy.run_path(str(ROOT/'scripts/fetch-sa1.py'))['checked_bytes']
    for name, spec in manifest['files'].items():
        checker(name, spec, (directory/name).read_bytes())
    source = (directory/'SA_1.asw').read_text()
    ref = reference_data(directory)
    hashes = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in [Path(__file__), ROOT/'scripts/fetch-sa1.py', manifest_path,
                        *sorted((ROOT/'openswing').glob('*.py'))]}
    cases, lookup = [], {}

    def run(name, alpha, n, mach, **extra):
        if alpha == 0:
            alpha = 0.  # Canonicalize signed zero for duplicate-case reuse.
        spec = dict(name=name, alpha_deg=float(alpha), panels=n, mach=mach, **extra)
        key = json.dumps({k: v for k, v in spec.items() if k != 'name'}, sort_keys=True)
        if key not in lookup:
            start = time.monotonic()
            result = compute(source, spec)
            lookup[key] = len(cases)
            cases.append(dict(specification=spec, result=result))
            print(f'{name}: N={n} alpha={alpha:g} M={result["mach"]:.5f} '
                  f'CL={result["CL"]:.7f} CD={result["CD"]:.7f} '
                  f'({time.monotonic()-start:.2f}s)', flush=True)
        return lookup[key]

    comparisons, convergence, parity, scale = {}, {}, [], []
    for mode, mach in MODES.items():
        grid = [[run(f'{mode}/ASWING/{n}/{i}', p['alpha_deg'], n, mach)
                 for i, p in enumerate(ref['aswing_5_96'])] for n in MESHES]
        comparisons[mode] = dict(aswing_case_indices=grid[-1], experiment_case_indices={})
        convergence[mode] = []
        for n0, n1, lo, hi in zip(MESHES, MESHES[1:], grid, grid[1:]):
            difference = {k: float(max(abs(cases[a]['result'][k]-cases[b]['result'][k])
                                      for a, b in zip(lo, hi))) for k in ['CL', 'CD', 'Cm']}
            convergence[mode].append(dict(coarse=n0, fine=n1, maximum_absolute_change=difference))
        # Numerical-resolution criteria only; these do NOT bound model/reference error.
        last = convergence[mode][-1]['maximum_absolute_change']
        assert last['CL'] < 1e-4 and last['CD'] < 1e-5 and last['Cm'] < 1e-4
        for k in ['CL', 'CD', 'Cm']:
            assert last[k] < convergence[mode][0]['maximum_absolute_change'][k]/8
        aswing_stats = {k: statistics([cases[i]['result'][k] for i in grid[-1]],
                                     [r[k] for r in ref['aswing_5_96']])
                       for k in ['CL', 'CD', 'CDi', 'Cm']}
        comparisons[mode]['aswing_errors'] = aswing_stats
        comparisons[mode]['experiment_errors'] = {}
        for coefficient, points in ref['experiment'].items():
            indices = [run(f'{mode}/experiment/{coefficient}/{i}', p['alpha_deg'], 400, mach)
                       for i, p in enumerate(points)]
            comparisons[mode]['experiment_case_indices'][coefficient] = indices
            comparisons[mode]['experiment_errors'][coefficient] = statistics(
                [cases[i]['result'][coefficient] for i in indices], [p['value'] for p in points])
        for alpha in [0., 8.1351, 18.091, 30., 60.]:
            pos = run(f'{mode}/symmetry/{alpha}', alpha, 96, mach)
            neg = run(f'{mode}/symmetry/{-alpha}', -alpha, 96, mach)
            a, b = cases[pos]['result'], cases[neg]['result']
            error = max(abs(a['CL']+b['CL']), abs(a['Cm']+b['Cm']), abs(a['CD']-b['CD']))
            if alpha <= 30:
                assert error < 1e-8
            parity.append(dict(mode=mode, alpha_deg=alpha, positive_case=pos, negative_case=neg,
                               maximum_absolute_error=error, passed=bool(error < 1e-8),
                               tolerance=1e-8, scope='measured-range/30-degree check' if alpha <= 30 else 'deep-stall diagnostic'))
    # Dynamic-pressure similarity at fixed PG Mach; Cm=0 section input avoids
    # the separate section-moment local-Mach correction in this geometry.
    for alpha in [0., 8.1351, 18.091]:
        base = run('similarity/base', alpha, 96, 0.)
        changed = run('similarity/half-speed-double-density', alpha, 96, 0., speed=23.95, density=2.4512)
        a, b = cases[base]['result'], cases[changed]['result']
        error = max(abs(a[k]-b[k]) for k in COEFFICIENTS)
        wrench_error = float(np.max(abs(np.r_[b['force'], b['moment']]-.5*np.r_[a['force'], a['moment']]))/10000)
        assert error < 1e-8 and wrench_error < 1e-8
        scale.append(dict(base_case=base, scaled_case=changed, coefficient_error=error,
                          normalized_wrench_error=wrench_error))
    # This is a robustness probe outside the measured range, not an experimental
    # case or an accepted approximation. Preserve an explicit failure if present.
    try:
        deep = compute(source, dict(alpha_deg=90., panels=96, mach=0.))
        deep_stall = dict(alpha_deg=90., status='computed_unvalidated', result=deep)
    except Exception as exc:
        from openswing.aero import AnalysisError
        if not isinstance(exc, AnalysisError):
            raise
        deep_stall = dict(alpha_deg=90., status='failed', error=str(exc))
    result = dict(description='SA-1 unchanged archived input: ASWING 5.96 and digitized experimental comparison; no parameter fitting.',
        source_sha256=hashes, versions=dict(python=platform.python_version(), numpy=np.__version__, scipy=scipy.__version__),
        reference=ref, provenance=manifest, settings=dict(speed=47.9, density=1.2256, stall_factor=40., stall_width=.05,
            meshes=MESHES, mesh_spacing='cosine in material arc length', circulation='pointwise',
            pg_mach_modes=MODES, section_lift_limits=[-1.2, 1.2], section_drag=[.00352562, .00771413]),
        assumptions=[
            'Use the archived .asw unchanged, not the report prose setup (which gives limits +/-1.5, Cdf=0, Cdp=.01 and 40 nodes).',
            'The script specifies 47.9 speed and 200 nodes but no PG Mach mode; fixed M=0 and M=V/a are separate sensitivity cases, not identified original settings.',
            'Only the first two CSV columns are experimental data. The other pair is labelled Lifting_Line and is excluded.',
            'Experimental values are the ISAE digitization/integration attributed to Applin (1995), not independently reduced raw pressure measurements.',
            'Each experimental coefficient uses its own recorded incidence angles; no interpolation or angle alignment.',
            'Original executable version, exact discretization, stall settings and experimental digitization uncertainty are not fully established.'],
        limitations=[
            'Successful numerical checks and native/WASM agreement do not establish physical or ASWING parity.',
            'The measured drag discrepancy near stall is retained; empirical lifting-line stall is not a resolved separated-flow model.',
            'The 30/60-degree symmetry checks and 90-degree robustness probe have no experimental reference in this study.',
            'At 60 degrees separate solves can choose different low-residual roots; the failed symmetry diagnostic and reflected-root probe are retained as an open branch-selection issue.',
            'The 200-to-400 interval changes are finite-mesh differences, not rigorous continuum error bounds.'],
        comparisons=comparisons, convergence=convergence, symmetry=parity, dynamic_pressure_similarity=scale,
        deep_stall_branch_probe=branch_probe(source), deep_stall_probe=deep_stall, cases=cases)
    target = Path(output).resolve() if output else ROOT/'docs/validation/sa1.json'
    target.write_text(json.dumps(result, indent=2, allow_nan=False)+'\n')
    print(f'Wrote {target.relative_to(ROOT)}: {len(cases)} cases; discrepancies retained.', flush=True)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', help='Write a fresh study without replacing the historical report.')
    main(parser.parse_args().output)
