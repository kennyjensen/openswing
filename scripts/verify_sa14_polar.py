"""Bounded serial refresh of all 360 registered SA-14 CL comparisons.

Each invocation runs at most six cold solves, under one process resource cap.
No background scheduling, continuation seeds or changed acceptance gates.
"""
import argparse
from collections import Counter
from contextlib import redirect_stdout
from decimal import Decimal
import gc
import io
import json
from pathlib import Path
import resource
import statistics
import time

import verify_sa14_defaults as pilot

ROOT = pilot.ROOT


def prepare(out):
    prior_path = ROOT / 'artifacts/isae/sa14-body-pilot-20261109/plan.json'
    prior = pilot.read(prior_path)
    pilot.authenticate(prior['pins'])
    jobs = [j for j in pilot.adapter.plan(ROOT) if j['case_id'] == 'SA-14']
    assert len(jobs) == len({j['id'] for j in jobs}) == 360
    assert sum(j['reference_row']['fields']['conv']['value'] == 0 for j in jobs) == 128
    assert [j for j in jobs if j['settings']['alpha'] == 5.] == prior['jobs']
    for job in jobs:
        assert job['required_outputs'] == ['CL'] and job['expected_outputs'] == 1
        assert job['settings']['freeze_influences'] is True and job['settings']['mach'] is None
        assert job['settings']['panels'] in (64, 128)
    pins = dict(prior['pins'])
    for path in (Path(__file__), prior_path):
        pins[path.relative_to(ROOT).as_posix()] = pilot.sha(path)
    pilot.write(out / 'plan.json', dict(observed_utc=pilot.utc(), jobs=jobs, pins=pins,
        registered_sa14_required=360, reference_unconverged_slots=128,
        reference_acceptance=dict(relative_tolerance=.05, tiny_reference=1e-8),
        protocol=prior['protocol'].replace('at alpha5,speed70', 'at every archived angle,speed70').replace('these six rows are not a full-family refresh.',
            'all 360 existing CL slots are retained; native convergence flags are reported separately.'),
        limits=dict(blas_threads=1, address_space_mib=512, cpu_seconds=15,
                    wall_seconds=25, maximum_jobs_per_invocation=6),
        production_physics_changed=False))
    print('Prepared all 360 original CL comparisons; 128 have native conv=0.')


def batch(out, start, count):
    assert 1 <= count <= 6 and 0 <= start < 360 and start + count <= 360
    plan = pilot.read(out / 'plan.json')
    pilot.authenticate(plan['pins'])
    started = time.monotonic()
    rows = []
    for index in range(start, start + count):
        folder = out / f'job-{index:02d}'
        # Resume only a completed, authenticated result. An incomplete directory
        # requires inspection and cannot be mistaken for a finished job.
        if folder.exists():
            report = pilot.read(folder / 'report.json')
            assert report['plan_sha256'] == pilot.sha(out / 'plan.json')
            for name, digest in report['artifacts'].items():
                assert pilot.sha(folder / name) == digest
        else:
            with redirect_stdout(io.StringIO()):
                pilot.run(out, index)
            report = pilot.read(folder / 'report.json')
        row = pilot.read(folder / 'strict-result.json')
        assert row.get('sources_unchanged') is True
        rows.append(dict(index=index, id=report['id'], numerical_pass=report['numerical_pass'],
            passed=report['reference_match'], seconds=report['seconds'], errors=report['errors']))
        gc.collect()
    print(json.dumps(dict(rows=rows, batch_seconds=time.monotonic() - started,
        peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)))


def summarize(out):
    plan = pilot.read(out / 'plan.json')
    pilot.authenticate(plan['pins'])
    assert len(plan['jobs']) == 360
    rows = []
    for i, job in enumerate(plan['jobs']):
        folder = out / f'job-{i:02d}'
        report = pilot.read(folder / 'report.json')
        assert report['plan_sha256'] == pilot.sha(out / 'plan.json')
        for name, digest in report['artifacts'].items():
            assert pilot.sha(folder / name) == digest
        strict = pilot.read(folder / 'strict-result.json')
        accepted = pilot.read(folder / 'accepted-result.json')
        assert strict['id'] == accepted['id'] == job['id']
        assert strict['sources_unchanged'] is True
        fields = job['reference_row']['fields']
        tokens = (ROOT / job['table_path']).read_text().splitlines()[job['reference_row']['line_number'] - 1].split()
        assert tokens == job['reference_row']['tokens']
        expected = Decimal(tokens[-1])
        absolute = Decimal(str(fields['CL']['tolerance']))
        limit = absolute if abs(expected) <= Decimal('1e-8') else max(absolute, abs(expected) * Decimal('.05'))
        predicted = strict.get('result', {}).get('predicted', {}).get('CL')
        numerical = strict['numerical_pass'] is True
        passed = bool(numerical and predicted is not None and
                      abs(Decimal(str(predicted)) - expected) <= limit)
        assert accepted['reference_match'] is report['reference_match'] is passed
        physical_path = folder / 'physical-result.json'
        physical = pilot.read(physical_path) if physical_path.exists() else None
        if physical:
            assert physical['aerodynamic_influences']['frozen'] is True
            assert physical['aerodynamic_influences']['pg_mach'] > 0
            assert abs(physical['CL'] - predicted) < 2e-12
            assert numerical == all(c['passed'] for c in strict['numerical_checks'])
        error = None if predicted is None or expected == 0 else float(
            100 * (Decimal(str(predicted)) - expected) / abs(expected))
        rows.append(dict(index=i, id=job['id'], configuration=Path(job['table_path']).stem,
            alpha=job['settings']['alpha'], panels=job['settings']['panels'],
            reference_converged=fields['conv']['value'] == 1,
            reference_stalled=fields['stall']['value'] == 1,
            expected=float(expected), predicted=predicted, passed=passed,
            numerical_pass=numerical, status=strict['status'], error_percent=error,
            numerical_checks=len(strict['numerical_checks']),
            residual=physical['residual'] if physical else None,
            maximum_local_mach=physical['lifting_airflow']['maximum']['normal_mach'] if physical else None,
            current_stalled_strips=sum(s['stalled'] for s in physical['strips'] if s['lifting']) if physical else None,
            seconds=report['seconds'], peak_rss_kib=report['peak_rss_kib'],
            errors=report['errors']))

    def totals(selected):
        errors = [abs(r['error_percent']) for r in selected
                  if not r['passed'] and r['error_percent'] is not None]
        return dict(required=len(selected), passed=sum(r['passed'] for r in selected),
            numerical_passed=sum(r['numerical_pass'] for r in selected),
            failed_error_median_percent=statistics.median(errors) if errors else None,
            failed_error_max_percent=max(errors, default=None),
            statuses=dict(Counter(r['status'] for r in selected)),
            reference_unconverged=sum(not r['reference_converged'] for r in selected))

    groups = {name: totals([r for r in rows if r['configuration'] == name])
              for name in dict.fromkeys(r['configuration'] for r in rows)}
    subsets = {name: totals([r for r in rows if test(r)]) for name, test in (
        ('reference_converged', lambda r: r['reference_converged']),
        ('reference_unconverged', lambda r: not r['reference_converged']),
        ('reference_unstalled', lambda r: not r['reference_stalled']),
        ('reference_stalled', lambda r: r['reference_stalled']))}
    result = dict(observed_utc=pilot.utc(), totals=totals(rows), configurations=groups,
        diagnostic_subsets=subsets, rows=rows, plan_sha256=pilot.sha(out / 'plan.json'),
        source_pins_verified=len(plan['pins']), physical_calls=sum(
            pilot.read(out / f'job-{i:02d}/report.json')['physical_calls'] for i in range(360)),
        production_physics_changed=False, all_registered_cl_slots_refreshed=True,
        complete_family_validation=False,
        qualification='Native conv=0 rows retain their archived-number comparisons and denominator. '
            'Their agreement is not a converged-native validation claim. Exact historical mesh/startup and local-load agreement remain open.')
    pilot.write(out / 'analysis.json', result)
    print(json.dumps({key: result[key] for key in ('totals', 'configurations', 'diagnostic_subsets')}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'batch', 'summary'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--start', type=int, default=0)
    parser.add_argument('--count', type=int, default=6)
    args = parser.parse_args()
    pilot.bounded()
    out = args.output.resolve()
    if args.action == 'prepare':
        prepare(out)
    elif args.action == 'batch':
        batch(out, args.start, args.count)
    else:
        summarize(out)
