"""Explicit current-wind Fourier checks for the bundled SA-11 winglet models.

Eight serial solves. Reuse the four pointwise junction checks only after checking
their source, complete condition and production-module pins. This diagnostic
does not select a default, substitute reference data or count validation passes.
"""
from dataclasses import asdict
from datetime import datetime, timezone
import argparse
import gc
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scripts'))
from openswing.aero import FlightCondition

HELPER = ROOT / 'scripts/verify-isae-sa11-circulation.py'
spec = importlib.util.spec_from_file_location('sa11_circulation_diagnostic', HELPER)
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)

EXAMPLES = ('isae-sa11-wingtip-up', 'isae-sa11-wingtip-up-and-down')
GRIDS = (48, 96)
MODES = (5, 19)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def utc():
    return datetime.now(timezone.utc).isoformat()


def normalized(value):
    return json.loads(json.dumps(value))


def write(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def load_baselines(folder, modules, sources):
    plan_path, rows_path = folder / 'unfrozen-plan.json', folder / 'unfrozen-results.json'
    plan, rows = json.loads(plan_path.read_text()), json.loads(rows_path.read_text())
    if plan['modules'] != modules or len(rows) != 4:
        raise ValueError('Pointwise study has different production modules or scope.')
    expected = normalized(asdict(FlightCondition(speed=30., alpha=5., freeze_influences=False)))
    keys = [(row['example'], row['panels']) for row in rows]
    if len(set(keys)) != 4 or set(keys) != {(name, n) for name in EXAMPLES for n in GRIDS}:
        raise ValueError('Missing or repeated pointwise state.')
    for row in rows:
        if row['condition'] != expected or row['input_sha256'] != sources[row['example']]['sha256']:
            raise ValueError('Pointwise source or applied condition differs.')
        if row['status'] not in ('computed', 'rejected'):
            raise ValueError('Unrecognized pointwise terminal state.')
        if row['status'] == 'rejected' and row['details']['kind'] != 'section_normal_mach':
            raise ValueError('Pointwise rejection did not reach the local-Mach check.')
    return rows, {p.name: sha(p) for p in (plan_path, rows_path)}


def maximum(row):
    if row['status'] == 'computed':
        return row['result']['lifting_airflow']['maximum']
    return (row.get('details') or {}).get('maximum')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--pointwise-study', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Output must be a new directory; prior observations are never overwritten.')
    modules = {p.name: sha(p) for p in (ROOT / 'openswing').glob('*.py')}
    sources = {name: dict(path=str(ROOT / 'examples' / (name + '.asw')),
                         sha256=sha(ROOT / 'examples' / (name + '.asw'))) for name in EXAMPLES}
    baselines, baseline_pins = load_baselines(args.pointwise_study, modules, sources)
    requests = [dict(case=name, panels=n, modes_per_beam=k, alpha=5., speed=30.,
                     pg='speed', frozen=False) for name in EXAMPLES for n in GRIDS for k in MODES]
    args.output.mkdir(parents=True)
    shutil.copyfile(__file__, args.output / 'driver-used.py')
    shutil.copyfile(HELPER, args.output / 'circulation-helper-used.py')
    for name, source in sources.items():
        shutil.copyfile(source['path'], args.output / (name + '.asw'))
    plan = dict(utc=utc(), modules=modules, sources=sources, requests=requests,
                driver_sha256=sha(Path(__file__)), helper_sha256=sha(HELPER),
                pointwise_study=str(args.pointwise_study.resolve()), pointwise_pins=baseline_pins,
                purpose='Test explicit existing Fourier truncations at the winglet failure settings; '
                        'no geometry/core/stall changes, reference comparisons or default selection.')
    write(args.output / 'plan.json', plan)
    write(args.output / 'pointwise-baselines.json', baselines)
    rows = []
    for request in requests:
        name = request['case']
        case = dict(source=Path(sources[name]['path']).read_text())
        started = helper.time.monotonic()
        row = helper.run(case, request)
        row.update(utc=utc(), seconds=helper.time.monotonic() - started,
                   input_sha256=sources[name]['sha256'])
        condition = row['applied_condition']
        assert condition['freeze_influences'] is False and condition['mach'] is None
        assert set(condition['circulation_modes'].values()) == {request['modes_per_beam']}
        rows.append(row)
        write(args.output / 'results.json', rows)
        peak = maximum(row)
        print(len(rows), '/8', name, request['panels'], request['modes_per_beam'], row['status'],
              'Mmax', None if peak is None else peak['normal_mach'],
              'local residual', row.get('maximum_local_residual'), flush=True)
        gc.collect()
    assert modules == {p.name: sha(p) for p in (ROOT / 'openswing').glob('*.py')}
    assert all(sha(Path(source['path'])) == source['sha256'] for source in sources.values())
    assert sha(HELPER) == plan['helper_sha256'] and sha(Path(__file__)) == plan['driver_sha256']
    table = []
    for row in rows:
        request = row['specification']
        base = next(b for b in baselines if (b['example'], b['panels']) == (request['case'], request['panels']))
        peak, base_peak = maximum(row), maximum(base)
        table.append(dict(example=request['case'], panels=request['panels'], modes=request['modes_per_beam'],
            status=row['status'], maximum=peak, weighted_residual=row.get('weighted_residual'),
            maximum_local_residual=row.get('maximum_local_residual'),
            pointwise_status=base['status'], pointwise_maximum=base_peak,
            local_mach_ratio_to_pointwise=None if peak is None else peak['normal_mach']/base_peak['normal_mach']))
    write(args.output / 'analysis.json', dict(utc=utc(), rows=table,
        computed=sum(row['status'] == 'computed' for row in rows),
        rejected=sum(row['status'] == 'rejected' for row in rows),
        limitations=['Local residual is normalized by FlightCondition.speed; it need not vanish under Fourier testing.',
                     'These are per-logical-beam sine modes, not a recovered native connected-surface mapping.',
                     'No documented original SA-11 mode count or NODE grid has been recovered.',
                     'Low-speed execution does not establish the archived transonic comparisons.']))
    write(args.output / 'verification.json', dict(utc=utc(), completed=len(rows), expected=8,
        modules_unchanged=True, sources_unchanged=True, helper_unchanged=True,
        verified_pointwise_baselines=4, requested_conditions_applied=True,
        artifacts={p.name: sha(p) for p in args.output.iterdir() if p.is_file()}))
    print('COMPLETE eight explicit Fourier states and four verified saved pointwise baselines', flush=True)


if __name__ == '__main__':
    main()
