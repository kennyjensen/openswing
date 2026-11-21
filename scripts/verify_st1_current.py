"""Refresh the existing ST-1 scope with one bounded foreground job at a time."""
import argparse
from collections import Counter
from decimal import Decimal
import importlib.util
from pathlib import Path
import resource
import shutil
import time

import verify_sa14_defaults as common
import isae_suite_st1 as adapter
from isae_acceptance import apply_reference_acceptance

ROOT = common.ROOT


def runner():
    spec = importlib.util.spec_from_file_location('isae_runner', ROOT/'scripts/run-isae-suite.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def prepare(out):
    jobs = adapter.plan(ROOT)
    pins = {p.relative_to(ROOT).as_posix(): common.sha(p) for p in [
        Path(__file__), ROOT/'scripts/verify_sa14_defaults.py', ROOT/'scripts/isae_suite_st1.py',
        ROOT/'scripts/isae_acceptance.py', ROOT/'scripts/run-isae-suite.py',
        ROOT/'docs/validation/aswing-authoritative-sources.json',
        ROOT/'docs/validation/aswing-authoritative-references.md',
        *sorted((ROOT/'openswing').glob('*.py'))]}
    for job in jobs:
        for item in job['source_pins']:
            pins[Path(item['path']).relative_to(ROOT).as_posix()] = item['sha256']
    for entry in common.read(ROOT/'docs/validation/aswing-authoritative-sources.json')['files']:
        if entry['id'] in ('isae-part-3', 'drela-steady', 'drela-unsteady'):
            for key, digest in (('local_pdf', 'sha256'), ('local_text', 'text_sha256')):
                pins[entry[key]] = entry[digest]
    common.authenticate(pins)
    common.write(out/'plan.json', dict(observed_utc=common.utc(), jobs=jobs, pins=pins,
        required=200, relative_tolerance=.05, tiny_reference=1e-8,
        limits=dict(blas_threads=1, address_space_mib=512, cpu_seconds=15, wall_seconds=25),
        qualification='Same 37 jobs and 200 original scalar slots. Two current static solves; '
        '35 unsupported/inventory records retain all 194 unavailable slots. Original strict checks '
        'and historical setup uncertainties remain separate from the user-authorized 5% allowance.'))
    print('Prepared 37 ST-1 jobs, 200 original slots; two runnable static states.')


def run(out, index):
    plan = common.read(out/'plan.json'); common.authenticate(plan['pins'])
    job = plan['jobs'][index]
    folder = out/f'job-{index:02d}'; folder.mkdir()
    common.write(folder/'job.json', job)
    started = time.monotonic()
    raw = adapter.run(ROOT, job)
    common.write(folder/'adapter-result.json', raw)
    strict = runner().checked_result(job, raw)
    assert strict['status'] in ('computed', 'unsupported'), strict.get('error', strict.get('contract_error'))
    accepted = apply_reference_acceptance(strict)
    common.write(folder/'strict-result.json', strict)
    common.write(folder/'accepted-result.json', accepted)
    if raw.get('artifact_directory'):
        shutil.copytree(raw['artifact_directory'], folder/'physical')
    common.authenticate(plan['pins'])
    report = dict(observed_utc=common.utc(), index=index, id=job['id'], status=strict['status'],
        seconds=time.monotonic()-started, peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        strict=strict['output_accounting'], accepted=accepted['output_accounting'],
        plan_sha256=common.sha(out/'plan.json'),
        artifacts={p.relative_to(folder).as_posix():common.sha(p) for p in sorted(folder.rglob('*')) if p.is_file()})
    common.write(folder/'report.json', report)
    print(report['id'], report['status'], report['accepted'], 'seconds', round(report['seconds'],3))


def summarize(out):
    plan = common.read(out/'plan.json'); common.authenticate(plan['pins'])
    rows, states, physical = [], [], 0
    for i, job in enumerate(plan['jobs']):
        folder = out/f'job-{i:02d}'; report = common.read(folder/'report.json')
        assert report['plan_sha256'] == common.sha(out/'plan.json')
        for name, digest in report['artifacts'].items():
            assert common.sha(folder/name) == digest
        strict = common.read(folder/'strict-result.json')
        assert runner().checked_result(job, common.read(folder/'adapter-result.json')) == strict
        accepted = common.read(folder/'accepted-result.json')
        assert apply_reference_acceptance(strict) == accepted
        physical += len(strict['physical_checks'])
        states.append(dict(index=i, id=job['id'], status=strict['status'], seconds=report['seconds'],
            peak_rss_kib=report['peak_rss_kib']))
        for check in accepted['reference_checks']:
            expected = Decimal(check['exact_decimal_expected'])
            absolute = Decimal(check['exact_decimal_tolerance'])
            limit = absolute if abs(expected) <= Decimal('1e-8') else max(absolute, abs(expected)*Decimal('.05'))
            value = check['predicted']
            error = None if value is None else abs(Decimal(str(value))-expected)
            passed = bool(strict['numerical_pass'] and error is not None and error <= limit)
            assert passed == check['passed']
            rows.append(dict(id=job['id'], name=check['name'], expected_token=check['expected_token'],
                predicted=value, passed=passed, strict_passed=check['strict_passed'],
                abs_error=None if error is None else float(error),
                error_percent=None if error is None or expected == 0 else float(100*error/abs(expected))))
    assert len(rows) == 200 and sum(r['predicted'] is None for r in rows) == 194
    summary = dict(observed_utc=common.utc(), required=len(rows), passed=sum(r['passed'] for r in rows),
        strict_passed=sum(r['strict_passed'] for r in rows), unavailable=194, physical_checks=physical,
        statuses=dict(Counter(s['status'] for s in states)), rows=rows, states=states,
        plan_sha256=common.sha(out/'plan.json'), pins_verified=len(plan['pins']),
        production_physics_changed=False, complete_family_validation=False)
    common.write(out/'summary.json', summary)
    print({k:v for k,v in summary.items() if k not in ('rows','states')})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'run', 'summary'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--index', type=int)
    args = parser.parse_args()
    common.bounded()
    if args.action == 'prepare': prepare(args.output.resolve())
    elif args.action == 'run': run(args.output.resolve(), args.index)
    else: summarize(args.output.resolve())
