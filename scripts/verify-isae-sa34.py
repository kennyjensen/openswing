"""Compare literal ISAE SA-3/4 models with archived ASWING and experiment.

Run fetch-isae-validation.py first. No input parameters are fitted. PG and K/F
settings are sensitivity cases because the original startup state is unknown.
The report's experimental geometry differs from the literal archived models;
this script measures discrepancies and does not assert experimental agreement.
"""
from pathlib import Path
import argparse
import csv
import hashlib
import io
import json
import os
import platform
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
KERNEL = Path(os.environ.get('OPENSWING_KERNEL', ROOT))
sys.path.insert(0, str(KERNEL))
import numpy as np
import scipy
from openswing.asw import parse_asw
from openswing.aero import FlightCondition, solve_rigid, AnalysisError

REVISION = 'f62943df20e9e4d7d9f50e070477b22426b5f865'
CACHE = ROOT / '.reference/isae-validation' / REVISION
COEFFICIENTS = ['CL', 'CD', 'Cm', 'CDi', 'CDp', 'CDi_near', 'CY', 'Cl', 'Cn']
MODES = {f'{flow}_{pg}': dict(mach=mach, freeze_influences=frozen)
         for flow, frozen in [('current', False), ('frozen', True)]
         for pg, mach in [('PG0', 0.), ('PGspeed', None)]}


def references(number):
    folder = next((CACHE / '1 - Aerodynamics/SA - Steady Aerodynamics Cases').glob(f'SA - {number} - *'))
    source = folder / f'Aswing_Simulation_V5_96_Only/SA_{number}.asw'
    experiment = {}
    for key in ['CL', 'CD']:
        path = folder / f'Experimental_Data/SA_{number}_{key}.csv'
        rows = list(csv.reader(io.StringIO(path.read_text())))
        assert rows[0][0] == 'Expe' and rows[1] == ['X', 'Y', 'X', 'Y']
        # The other columns are separate lifting-line predictions, not data.
        experiment[key] = [[float(r[0]), float(r[1])] for r in rows[2:] if r and r[0] and r[1]]
    aswing = []
    for path in sorted((folder / 'Aswing_Simulation_V5_96_Only').glob('*.txt')):
        text = path.read_text()
        assert 'alpha' in text and 'span eff.' in text
        rows = np.loadtxt(io.StringIO(text), ndmin=2)
        assert rows.shape[1] == 10
        aswing.append(dict(file=path.relative_to(CACHE).as_posix(),
            rows=[dict(zip(['index', 'time', 'alpha', 'lift', 'drag', 'CL', 'CD', 'CDi', 'Cm', 'efficiency'], r)) for r in rows]))
    return folder, source, experiment, aswing


def compute(source, spec):
    model = parse_asw(source)
    assert not model.diagnostics
    condition = FlightCondition(speed=89.4, alpha=spec['alpha'], density=1.2256,
                                **MODES[spec['mode']])
    result = solve_rigid(model, condition, panels=spec['panels'])
    if not result['converged'] or result['residual'] >= 1e-8:
        raise ValueError('Physical circulation residual failed')
    forces = np.array([s['force'] for s in result['strips']])
    moments = np.array([np.cross(np.asarray(s['position']) - model.reference[1], s['force']) + s['moment']
                        for s in result['strips']])
    force, moment = forces.sum(axis=0), moments.sum(axis=0)
    alpha = np.deg2rad(spec['alpha'])
    qS = .5 * condition.density * condition.speed**2 * model.reference[0, 0]
    checks = [abs(force @ [-np.sin(alpha), 0, np.cos(alpha)] / qS - result['CL']),
              abs(force @ [np.cos(alpha), 0, np.sin(alpha)] / qS - result['CD']),
              abs(moment[1] / (qS * model.reference[0, 1]) - result['Cm']),
              abs(result['CD'] - result['CDi_near'] - result['CDp']),
              float(np.max(abs(force - result['force']))) / qS,
              float(np.max(abs(moment - result['moment']))) / (qS * model.reference[0, 1])]
    assert max(checks) < 2e-10, checks
    return {**{k: float(result[k]) for k in COEFFICIENTS},
            'residual': result['residual'], 'mach': result['mach'], 'panels': result['panels'],
            'wrench_and_normalization_error': max(checks),
            'span_samples': [[s['t'], s['circulation'], s['cl']] for s in
                [result['strips'][i] for i in np.linspace(0, len(result['strips']) - 1, 9).astype(int)]]}


def stats(pairs):
    error = np.array([a - b for a, b in pairs])
    return dict(count=len(error), bias=float(error.mean()), rmse=float(np.sqrt(np.mean(error**2))),
                maximum_absolute_error=float(np.max(abs(error)))) if len(error) else None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cases', nargs='+', type=int, default=[3, 4])
    parser.add_argument('--meshes', nargs='+', type=int, default=[50, 100, 200])
    parser.add_argument('--output', type=Path, default=ROOT / 'docs/validation/isae-sa34.json')
    args = parser.parse_args()
    assert set(args.cases) <= {3, 4} and len(args.meshes) >= 2 and args.meshes == sorted(set(args.meshes))
    manifest = json.loads((CACHE.parent / 'manifest.json').read_text())
    pins = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((KERNEL / 'openswing').glob('*.py'))}
    identity = dict(modules=pins, script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                    revision=REVISION, meshes=args.meshes)
    digest = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    output_cache = ROOT / '.reference/isae-sa34-runs' / digest
    output_cache.mkdir(parents=True, exist_ok=True)
    summaries = []
    for number in args.cases:
        folder, path, experiment, aswing = references(number)
        source = path.read_text()
        used = {p.relative_to(CACHE).as_posix(): manifest['files'][p.relative_to(CACHE).as_posix()]
                for p in folder.rglob('*') if p.is_file() and p.suffix in ['.asw', '.sh', '.csv', '.txt']}
        for name, record in used.items():
            assert hashlib.sha256((CACHE / name).read_bytes()).hexdigest() == record['sha256']
        cases, lookup = [], {}
        def run(alpha, panels, mode):
            spec = dict(case=number, alpha=float(alpha), panels=panels, mode=mode)
            key = json.dumps(spec, sort_keys=True)
            if key in lookup:
                return lookup[key]
            saved = output_cache / (hashlib.sha256(key.encode()).hexdigest() + '.json')
            if saved.exists():
                row = json.loads(saved.read_text())
                assert row['specification'] == spec
            else:
                start = time.monotonic()
                try:
                    row = dict(specification=spec, status='computed', result=compute(source, spec))
                except AnalysisError as exc:
                    row = dict(specification=spec, status='rejected', error=str(exc))
                row['seconds'] = time.monotonic() - start
                saved.write_text(json.dumps(row, indent=2) + '\n')
            lookup[key] = len(cases)
            cases.append(row)
            if len(cases) % 25 == 0:
                print(f'SA-{number}: {len(cases)} recorded solves, latest {mode} N={panels}', flush=True)
            return lookup[key]
        for mode in MODES:
            for table in aswing:
                for panels in args.meshes:
                    for row in table['rows']:
                        run(row['alpha'], panels, mode)
            for points in experiment.values():
                for alpha, _ in points:
                    run(alpha, args.meshes[-1], mode)
        comparisons, convergence = {}, {}
        for mode in MODES:
            comparisons[mode] = dict(aswing=[], experiment={})
            for table in aswing:
                entries = [cases[run(row['alpha'], args.meshes[-1], mode)] for row in table['rows']]
                comparisons[mode]['aswing'].append(dict(file=table['file'], requested=len(entries),
                    computed=sum(r['status'] == 'computed' for r in entries),
                    errors={k: stats([(a['result'][k], b[k]) for a, b in zip(entries, table['rows'])
                                     if a['status'] == 'computed']) for k in ['CL', 'CD', 'Cm', 'CDi']}))
            for key, points in experiment.items():
                entries = [cases[run(alpha, args.meshes[-1], mode)] for alpha, _ in points]
                comparisons[mode]['experiment'][key] = dict(requested=len(entries),
                    computed=sum(r['status'] == 'computed' for r in entries),
                    errors=stats([(a['result'][key], value) for a, (_, value) in zip(entries, points)
                                  if a['status'] == 'computed']))
            convergence[mode] = []
            alphas = sorted({row['alpha'] for table in aswing for row in table['rows']})
            for lo, hi in zip(args.meshes, args.meshes[1:]):
                pairs = [(cases[run(alpha, lo, mode)], cases[run(alpha, hi, mode)]) for alpha in alphas]
                good = [(a, b) for a, b in pairs if a['status'] == b['status'] == 'computed']
                convergence[mode].append(dict(coarse=lo, fine=hi, requested=len(pairs), computed=len(good),
                    maximum_change={k: max([abs(a['result'][k] - b['result'][k]) for a, b in good], default=None)
                                    for k in ['CL', 'CD', 'Cm']}))
        model = parse_asw(source)
        summaries.append(dict(case=number, source=path.relative_to(CACHE).as_posix(), sources=used,
            reference=model.reference.tolist(), reference_aspect_ratio=float(model.reference[0, 2]**2 / model.reference[0, 0]),
            experiment=experiment, archived_aswing=aswing, cases=cases, comparisons=comparisons, convergence=convergence))
    result = dict(status='COMPARISONS_RECORDED_NOT_FULLY_VALIDATED', full_suite_validated=False,
        provenance=identity, runtime=dict(python=platform.python_version(), numpy=np.__version__, scipy=scipy.__version__),
        settings=dict(speed=89.4, density=1.2256, meshes=args.meshes, modes=MODES, circulation='pointwise',
                      stall_factor=40., stall_width=.05),
        limitations=[
            'Literal archived inputs are unchanged. Their span/reference area differ from the experimental geometry described in the ISAE report; matched experimental validation is not established.',
            'Both PG choices and K/F choices are sensitivity cases; the original startup state and exact ASWING discretization are unknown.',
            'CSV first column pairs are ISAE experimental digitizations; LLT columns are excluded. Original measurement reduction and digitization uncertainty are not established.',
            'All comparisons use each reference series at its own incidence samples. Missing archived rows and rejected solves remain absent, not zero.',
            'Finite-mesh changes, physical residuals, and native/WASM agreement do not establish experimental agreement. No parameters or acceptance thresholds were fitted.'],
        cases=summaries)
    assert pins == {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (KERNEL / 'openswing').glob('*.py')}
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print('Recorded SA-3/4 comparisons:', args.output, flush=True)


if __name__ == '__main__':
    main()
