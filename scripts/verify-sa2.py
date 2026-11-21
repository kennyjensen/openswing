"""Unchanged archived SA-2 input: mesh, K/F and PG sensitivity, without fitting.

This is not a geometrically matched 45-degree-wing validation. The original
experiment's missing drag datum and pressure-only force convention are retained.
"""
from decimal import Decimal
import hashlib
import io
import json
from pathlib import Path
import platform
import runpy
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import numpy as np
import scipy
from openswing.aero import FlightCondition, solve_rigid, evaluate_aerodynamics, AnalysisError
from openswing.asw import parse_asw, Distribution
from openswing.geometry import model_meshes

MESHES = [24, 48, 100, 200, 400]
MODES = {f'{influence}_{pg}': dict(freeze_influences=frozen, mach=mach)
         for influence, frozen in [('current', False), ('frozen', True)]
         for pg, mach in [('fixed_zero', 0.), ('speed_derived', None)]}
COEFFICIENTS = ['CL', 'CD', 'CDi', 'CDi_near', 'CDp', 'Cm', 'CY', 'Cl', 'Cn',
                'CL_pressure', 'CD_pressure', 'Cm_pressure', 'CD_friction']


def reference_data(directory):
    path = directory/'SA_2_DATA.txt'
    assert path.read_text().splitlines()[0].split() == ['alpha', 'CL', 'CD', 'CL_LLT', 'CD_LLT']
    table = np.loadtxt(path, skiprows=1)
    assert table.shape == (5, 5)
    assert np.array_equal(table[:, 0], [2.1, 4.2, 6.3, 8.4, 10.5])
    # Independently transcribed and visually checked in ARC R&M 2882, Part I,
    # Table 4, printed p.17 / PDF p.18. A dash means missing, NOT zero drag.
    primary = [dict(alpha_deg=a, CL=cl, CD_pressure=cd) for a, cl, cd in
               [(2.1, .121, None), (4.2, .238, .005), (6.3, .350, .012),
                (8.4, .456, .022), (10.5, .559, .035)]]
    assert np.array_equal(table[:, 1], [r['CL'] for r in primary])
    assert table[0, 2] == 0 and np.array_equal(table[1:, 2], [r['CD_pressure'] for r in primary[1:]])
    text = (directory/'SA_2_CL.txt').read_text()
    assert 'alpha' in text and 'span eff.' in text
    rows = np.loadtxt(io.StringIO(text))
    assert rows.shape == (5, 10) and np.array_equal(rows[:, 0], np.arange(1, 6))
    aswing = [dict(zip(['index', 'sequence_time', 'alpha_deg', 'lift_N', 'drag_N',
                       'CL', 'CD', 'CDi', 'Cm', 'efficiency'], map(float, r))) for r in rows]
    assert np.array_equal(rows[:, 2], table[:, 0])
    qS = .5*1.2256*49.9**2*1.549
    printed = [line.split() for line in text.splitlines() if line.strip() and not line.startswith('#')]
    def half_digit(token):
        return .5*10.**Decimal(token).as_tuple().exponent
    for tokens, row in zip(printed, aswing):
        for fi, ci, force, coefficient in [(3, 5, 'lift_N', 'CL'), (4, 6, 'drag_N', 'CD')]:
            assert abs(row[force]/qS-row[coefficient]) <= half_digit(tokens[fi])/qS+half_digit(tokens[ci])+1e-14
    return dict(aswing_5_96=aswing, primary_table_4=primary,
                repository_table=table.tolist(), repository_columns=['alpha', 'CL', 'CD', 'CL_LLT', 'CD_LLT'],
                missing_drag={'alpha_deg': 2.1, 'repository_value': 0., 'primary_value': None},
                force_convention='Primary coefficients integrate pressure. They exclude skin-friction force; CL_LLT/CD_LLT are separate numerical data and excluded.')


def geometry_audit(source):
    model = parse_asw(source)
    assert not model.diagnostics and len(model.beams) == 1
    assert np.allclose(model.reference[0], [1.549, .508, 2.4892], rtol=0, atol=1e-14)
    assert np.allclose(model.constants, [9.81, 1.2256, 340.21], rtol=0, atol=1e-14)
    beam = model.beams[0]
    # Analytic straight segments from the literal file coordinates, independent
    # of production mesh/frame integration. Chord is normal to the beam axis.
    locations = beam.position(np.array([-1.2446, 0, 1.2446]))
    expected = [[.8801, -1.2446, 0], [0, 0, 0], [.8801, 1.2446, 0]]
    assert np.allclose(locations, expected, rtol=0, atol=1e-14)
    for name, value in dict(chord=.508, Xax=0., twist=0., alpha=0., dCLda=6.28,
                            CLmin=-1.2, CLmax=1.2, Cdf=.000771413, Cdp=.000352562).items():
        assert np.allclose(beam.value(name, [-1.2446, -.2, 0, .2, 1.2446]), value, rtol=0, atol=1e-14)
    length = 2*np.hypot(.8801, 1.2446)
    sweep = np.arctan2(.8801, 1.2446)
    return dict(axis_endpoints=expected, beam_length=float(length), normal_chord=.508,
                beam_sweep_deg=float(np.rad2deg(sweep)), strip_area=float(length*.508),
                reference_area=1.549, reference_chord=.508, reference_span=2.4892,
                streamwise_chord_away_from_root_tip=float(.508/np.cos(sweep)),
                nominal_reference_aspect_ratio=2.4892**2/1.549,
                zero_incidence_CD=float(length*.508/1.549*(.000771413+.000352562*np.cos(sweep)**3)),
                primary_experiment=dict(sweep_deg=45., streamwise_chord=.508, span=2.4892,
                                        nominal_aspect_ratio=5., speed=163*.3048,
                                        tip='Curved leading edge beyond 0.90 semispan; not reproduced by the archived input.'))


def compute(source, spec):
    geometry = geometry_audit(source)
    model = parse_asw(source)
    condition = FlightCondition(speed=spec.get('speed', 49.9), density=spec.get('density', 1.2256),
                               alpha=spec['alpha_deg'], mach=spec['mach'],
                               freeze_influences=spec['freeze_influences'])
    result = solve_rigid(model, condition, panels=spec['panels'])
    strips = result['strips']
    force = np.sum([s['force'] for s in strips], axis=0)
    moment = np.sum([np.cross(s['position'], s['force'])+s['moment'] for s in strips], axis=0)
    alpha = np.deg2rad(spec['alpha_deg'])
    lift_axis, drag_axis = [-np.sin(alpha), 0, np.cos(alpha)], [np.cos(alpha), 0, np.sin(alpha)]
    qS = .5*condition.density*condition.speed**2*1.549
    errors = [abs(force@lift_axis/qS-result['CL']), abs(force@drag_axis/qS-result['CD']),
              abs(moment[1]/(qS*.508)-result['Cm']), np.max(abs(force-result['force']))/qS,
              np.max(abs(moment-result['moment']))/(qS*.508),
              abs(result['CD']-result['CDi_near']-result['CDp']),
              abs(sum(s['length'] for s in strips)-geometry['beam_length'])/geometry['beam_length']]
    assert result['converged'] and result['residual'] < 1e-8
    assert max(errors) < 2e-10, errors
    assert result['CD'] > 0 and result['CDi'] >= -1e-12
    assert result['aerodynamic_influences']['frozen'] == spec['freeze_influences']
    lateral = max(abs(result[k]) for k in ['CY', 'Cl', 'Cn'])
    assert lateral < 2e-10
    # Pressure-only diagnostic: remove JUST Cdf from a separately parsed model,
    # reuse its identical circulation, and check flow residual invariance. This
    # separates the specified friction force without tuning any pressure/stall
    # parameter or altering the archived source. It does not correct geometry.
    pressure_model = parse_asw(source)
    for beam in pressure_model.beams:
        d = beam.distributions['Cdf']
        beam.distributions['Cdf'] = Distribution('Cdf', d.t.copy(), np.zeros_like(d.values), d.line)
    pressure = evaluate_aerodynamics(pressure_model, condition, model_meshes(pressure_model, spec['panels']),
                                    circulation=np.array([s['circulation'] for s in strips]))
    assert pressure['residual'] < 1e-8
    assert abs(pressure['CDi']-result['CDi']) < 1e-12
    friction = result['CD']-pressure['CD']
    assert friction > 0
    out = {k: float(result[k]) for k in COEFFICIENTS if k in result}
    out.update({k+'_pressure': float(pressure[k]) for k in ['CL', 'CD', 'Cm']})
    out.update(CD_friction=float(friction), force=result['force'], moment=result['moment'],
               mach=result['mach'], panels=result['panels'], residual=result['residual'],
               maximum_section_cl=float(max(abs(s['cl']) for s in strips)),
               stalled_panels=sum(s['stalled'] for s in strips), lateral_symmetry_error=lateral,
               strip_wrench_and_normalization_error=float(max(errors)), checks=16,
               span_samples=[[s['t'], s['circulation'], s['cl']] for s in
                             [strips[i] for i in np.linspace(0, len(strips)-1, 9).astype(int)]])
    if spec['alpha_deg'] == 0:
        error = max(abs(out['CL']), abs(out['Cm']), abs(out['CD']-geometry['zero_incidence_CD']))
        assert error < 1e-13
        out.update(zero_incidence_analytical_error=error, checks=19)
    return out


def physical(result):
    return np.r_[*[result[k] for k in COEFFICIENTS], result['force'], result['moment'], np.ravel(result['span_samples'])]


def outcome(source, spec):
    try:
        return dict(status='computed', result=compute(source, spec))
    except AnalysisError as exc:
        # Retain rejected physical cases; implementation/test errors still fail
        # the study. A rejected case is never given a fabricated numeric value.
        return dict(status='rejected', error=str(exc))


def statistics(predicted, observed):
    error = np.asarray(predicted)-observed
    return dict(count=len(error), bias=float(np.mean(error)), rmse=float(np.sqrt(np.mean(error**2))),
                maximum_absolute_error=float(max(abs(error))))


def main(output=None):
    manifest_path = ROOT/'docs/validation/sa2-sources.json'
    manifest = json.loads(manifest_path.read_text())
    directory = ROOT/'.reference/isae-sa2'
    checker = runpy.run_path(str(ROOT/'scripts/fetch-sa2.py'))['checked_bytes']
    for name, spec in manifest['files'].items():
        checker(name, spec, (directory/name).read_bytes())
    source = (directory/'SA_2.asw').read_text()
    reference = reference_data(directory)
    geometry = geometry_audit(source)
    hashes = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in
              [Path(__file__), ROOT/'scripts/fetch-sa2.py', manifest_path, *sorted((ROOT/'openswing').glob('*.py'))]}
    cases, lookup = [], {}
    def run(name, alpha, n, mode, **extra):
        spec = dict(name=name, alpha_deg=float(alpha) if alpha else 0., panels=n, **MODES[mode], **extra)
        key = json.dumps({k: v for k, v in spec.items() if k != 'name'}, sort_keys=True)
        if key not in lookup:
            start = time.monotonic()
            record = outcome(source, spec)
            lookup[key] = len(cases)
            cases.append(dict(specification=spec, **record))
            message = (f'CL={record["result"]["CL"]:.7f} CD={record["result"]["CD"]:.7f}'
                       if record['status'] == 'computed' else 'REJECTED: '+record['error'])
            print(f'{name}: N={n} alpha={alpha:g} {message} ({time.monotonic()-start:.2f}s)', flush=True)
        return lookup[key]

    comparisons, convergence, symmetry, similarity = {}, {}, [], []
    for mode in MODES:
        grid = [[run(f'{mode}/polar/{n}/{i}', row['alpha_deg'], n, mode)
                 for i, row in enumerate(reference['aswing_5_96'])] for n in MESHES]
        complete = [i for i, indices in enumerate(grid) if all(cases[j]['status'] == 'computed' for j in indices)]
        assert complete, 'No complete polar at any mesh'
        selected = grid[complete[-1]]
        comparisons[mode] = dict(case_indices=selected, panels=MESHES[complete[-1]], mesh_case_indices=grid,
                                 rejected_case_indices=[i for row in grid for i in row if cases[i]['status'] == 'rejected'])
        convergence[mode] = []
        for n0, n1, lo, hi in zip(MESHES, MESHES[1:], grid, grid[1:]):
            pairs = [(a, b) for a, b in zip(lo, hi) if cases[a]['status'] == cases[b]['status'] == 'computed']
            delta = {k: float(max(abs(cases[a]['result'][k]-cases[b]['result'][k]) for a, b in pairs))
                     for k in ['CL', 'CD', 'Cm', 'CD_pressure']}
            convergence[mode].append(dict(coarse=n0, fine=n1, compared_cases=len(pairs),
                                          complete=len(pairs) == 5, maximum_absolute_change=delta))
        # Record achieved resolution without treating it as a physical-error or
        # original-discretization gate. Mesh sensitivity can be nonmonotone.
        comparisons[mode]['aswing_errors'] = {k: statistics([cases[i]['result'][k] for i in selected],
            [r[k] for r in reference['aswing_5_96']]) for k in ['CL', 'CD', 'CDi', 'Cm']}
        comparisons[mode]['experiment_pressure_errors'] = {
            'CL_pressure': statistics([cases[i]['result']['CL_pressure'] for i in selected],
                                     [r['CL'] for r in reference['primary_table_4']]),
            'CD_pressure': statistics([cases[i]['result']['CD_pressure'] for i in selected[1:]],
                                     [r['CD_pressure'] for r in reference['primary_table_4'][1:]])}
        for alpha in [0., 2.1, 10.5]:
            pos = run(f'{mode}/symmetry/{alpha}', alpha, 100, mode)
            neg = run(f'{mode}/symmetry/{-alpha}', -alpha, 100, mode)
            a, b = cases[pos]['result'], cases[neg]['result']
            error = max(abs(a[k]+b[k]) for k in ['CL', 'Cm', 'CL_pressure', 'Cm_pressure'])
            error = max(error, *[abs(a[k]-b[k]) for k in ['CD', 'CD_pressure', 'CDi', 'CDp']])
            assert error < 1e-8
            symmetry.append(dict(mode=mode, alpha_deg=alpha, positive_case=pos, negative_case=neg, maximum_error=error))
    for mode in ['current_fixed_zero', 'frozen_fixed_zero']:
        base = run(f'{mode}/similarity/base', 10.5, 100, mode)
        changed = run(f'{mode}/similarity/scaled', 10.5, 100, mode, speed=24.95, density=2.4512)
        a, b = cases[base]['result'], cases[changed]['result']
        error = max(abs(a[k]-b[k]) for k in COEFFICIENTS)
        wrench_error = float(np.max(abs(np.r_[b['force'], b['moment']]-.5*np.r_[a['force'], a['moment']])))
        assert error < 1e-8 and wrench_error < 1e-7
        similarity.append(dict(base_case=base, scaled_case=changed, coefficient_error=error, wrench_error=wrench_error))
    result = dict(description=__doc__, source_sha256=hashes, provenance=manifest, reference=reference,
                  versions=dict(python=platform.python_version(), numpy=np.__version__, scipy=scipy.__version__),
                  settings=dict(meshes=MESHES, modes=MODES, speed=49.9, density=1.2256,
                                spacing='cosine in material arc length', circulation='pointwise',
                                stall_factor=40., stall_width=.05, Cdf=.000771413, Cdp=.000352562),
                  geometry=geometry, cases=cases, comparisons=comparisons, convergence=convergence,
                  symmetry=symmetry, dynamic_pressure_similarity=similarity,
                  limitations=[
                      'The archived input describes 35.26546-degree straight segments with 0.508 normal chord, not the 45-degree experimental planform with 0.508 streamwise chord and curved tips.',
                      'The script toggles K/F once; slow mode is inferred only if startup used the guide default fast=T. Startup settings and PG Mach are not recovered. Both choices are reported.',
                      'The script requests 100 nodes; exact node/interval placement and circulation settings of the original executable are not established.',
                      'Report prose gives different drag parameters, 40 nodes and an inconsistent conversion of 163 ft/s. The unchanged archived input and script speed 49.9 are used.',
                      'The primary experiment Table 4 contains a dash at 2.1 degrees for drag. The repository zero is retained as provenance but excluded from physical error statistics.',
                      'Pressure-only diagnostics remove Cdf at unchanged circulation; remaining geometry, airfoil, viscous and normalization differences prevent matched experimental validation.',
                      'CDi is a far-wake diagnostic; total CD uses near-field forces. It must not be added again to total CD. Frozen CDi uses zero-angle wake axes.',
                      'Finite-mesh changes, residuals and native/WASM agreement do not prove original ASWING or physical accuracy. No parameter is fitted to the polar.'])
    target = Path(output).resolve() if output else ROOT/'docs/validation/sa2.json'
    target.write_text(json.dumps(result, indent=2, allow_nan=False)+'\n')
    print(f'Wrote {target.relative_to(ROOT)}: {len(cases)} cases; discrepancies retained.', flush=True)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', help='Write a fresh study without replacing the historical report.')
    main(parser.parse_args().output)
