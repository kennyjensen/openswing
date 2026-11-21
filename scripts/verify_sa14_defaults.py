"""Six serial SA-14 attached-flow checks of the documented startup reconstruction."""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import resource
import signal
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import isae_suite_extra_polars as adapter

def read(path): return json.loads(path.read_text())
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def utc(): return datetime.now(timezone.utc).isoformat()
def write(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')

def bounded():
    assert all(os.environ.get(name) == '1' for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'))
    resource.setrlimit(resource.RLIMIT_AS, (512*1024**2, 512*1024**2))
    resource.setrlimit(resource.RLIMIT_CPU, (15, 15))
    signal.alarm(25)

def authenticate(pins):
    for path, digest in pins.items():
        assert sha(ROOT/path) == digest, path

def prepare(out):
    before = read(out/'before/plan.json')
    jobs = adapter.plan(ROOT)
    assert len(jobs) == len(before) == 710
    # Every model, command, original target and denominator is preserved.
    for old, new in zip(before, jobs, strict=True):
        comparable = deepcopy(new)
        comparable['sources'] = deepcopy(old['sources'])
        assert new['sources'][:3] == old['sources'][:3]
        if old['case_id'] == 'SA-14':
            assert new['settings']['freeze_influences'] is True and new['settings']['mach'] is None
            comparable['settings']['freeze_influences'] = old['settings']['freeze_influences']
            comparable['settings']['mach'] = old['settings']['mach']
            comparable['qualifications'] = old['qualifications']
        assert comparable == old, new['id']
    selected = [j for j in jobs if j['case_id'] == 'SA-14' and j['settings']['alpha'] == 5.]
    assert len(selected) == 6 and {j['settings']['panels'] for j in selected} == {64, 128}
    assert all(j['reference_row']['fields']['conv']['value'] == 1 and
               j['reference_row']['fields']['stall']['value'] == 0 for j in selected)
    files = [*sorted((ROOT/'openswing').glob('*.py')), Path(__file__),
        ROOT/'scripts/isae_suite_extra_polars.py', ROOT/'scripts/isae_suite_polars.py',
        ROOT/'scripts/run-isae-suite.py', ROOT/'scripts/isae_acceptance.py',
        ROOT/'tests/test_isae_suite_extra_polars.py', ROOT/'reference/aswing_doc.txt',
        ROOT/'docs/validation/aswing-authoritative-references.md',
        ROOT/'docs/validation/aswing-authoritative-sources.json',
        ROOT/'docs/validation/isae-sa14-sources.json', out/'before/plan.json',
        out/'before/isae_suite_extra_polars.py', out/'before/test_isae_suite_extra_polars.py']
    pins = {p.relative_to(ROOT).as_posix():sha(p) for p in files}
    for job in selected:
        for p in job['sources']:
            path = p['path'].replace('.reference/', 'reference/', 1)
            assert sha(ROOT/path) == p['sha256']
            pins[path] = p['sha256']
    catalog = read(ROOT/'docs/validation/aswing-authoritative-sources.json')
    for entry in catalog['files']:
        if entry['id'] == 'isae-part-1' or entry['filename'] == 'drela-aswing-steady.pdf':
            for field, key in [('local_pdf', 'sha256'), ('local_text', 'text_sha256')]:
                assert sha(ROOT/entry[field]) == entry[key]
                pins[entry[field]] = entry[key]
    write(out/'plan.json', dict(observed_utc=utc(), jobs=selected, pins=pins,
        registered_sa14_required=360, pilot_required=6, primary_passes_added=0,
        protocol='Original three models at alpha5,speed70,rhoSL,64/128 cosine intervals. '
                 'Documented K/F true startup without F commands; one K/M toggle gives speed-derived PG. '
                 'All original section/mesh settings and strict numerical gates retained. '
                 'Historical binary startup remains unauthenticated; these six rows are not a full-family refresh.',
        limits=dict(blas_threads=1,address_space_mib=512,cpu_seconds=15,wall_seconds=25)))
    print('Prepared six SA14 jobs; original 360-target scope retained.')

def run(out, index):
    plan = read(out/'plan.json'); authenticate(plan['pins'])
    job = plan['jobs'][index]
    directory = out/f'job-{index:02d}'
    assert not directory.exists()
    from openswing import aero
    actual_solve = aero.solve_rigid
    captured = []
    def record(*args, **kwargs):
        result = actual_solve(*args, **kwargs)
        captured.append(result)
        return result
    # Instrument the return only; equations, arguments and result stay untouched.
    aero.solve_rigid = record
    started = time.monotonic()
    try: row = adapter.run(ROOT, job)
    finally: aero.solve_rigid = actual_solve
    spec = importlib.util.spec_from_file_location('sa14_runner', ROOT/'scripts/run-isae-suite.py')
    runner = importlib.util.module_from_spec(spec); spec.loader.exec_module(runner)
    row = runner.checked_result(job, row)
    from isae_acceptance import apply_reference_acceptance
    accepted = apply_reference_acceptance(row, relative_tolerance=.05)
    directory.mkdir()
    write(directory/'strict-result.json', row)
    write(directory/'accepted-result.json', accepted)
    if captured:
        assert len(captured) == 1
        raw = captured[0]
        # The raw strip ledger permits a separate force/section audit without
        # another solve. Do not reduce it to only the scalar acceptance target.
        write(directory/'physical-result.json', raw)
    report = dict(observed_utc=utc(), id=job['id'], numerical_pass=row['numerical_pass'],
        reference_match=accepted['reference_match'], seconds=time.monotonic()-started,
        peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        plan_sha256=sha(out/'plan.json'), physical_calls=row['physical_calls'],
        errors={k:row[k] for k in ('error_type', 'error') if k in row},
        artifacts={p.name:sha(p) for p in directory.iterdir()})
    write(directory/'report.json', report)
    print(json.dumps(report, indent=2))

def summarize(out):
    plan = read(out/'plan.json'); authenticate(plan['pins'])
    rows = []
    for i, job in enumerate(plan['jobs']):
        directory = out/f'job-{i:02d}'
        report = read(directory/'report.json')
        assert report['plan_sha256'] == sha(out/'plan.json')
        for file, digest in report['artifacts'].items(): assert sha(directory/file) == digest
        strict = read(directory/'strict-result.json')
        accepted = read(directory/'accepted-result.json')
        tokens = (ROOT/job['table_path']).read_text().splitlines()[job['reference_row']['line_number']-1].split()
        assert tokens == job['reference_row']['tokens']
        expected = Decimal(tokens[-1]); predicted = strict.get('result',{}).get('predicted',{}).get('CL')
        passed = bool(strict['numerical_pass'] and predicted is not None and
                      abs(Decimal(str(predicted))-expected) <= max(Decimal('0.0000005'), abs(expected)*Decimal('.05')))
        assert passed == accepted['reference_match']
        physical = read(directory/'physical-result.json') if (directory/'physical-result.json').exists() else None
        if physical:
            assert physical['aerodynamic_influences']['frozen'] is True
            assert physical['aerodynamic_influences']['pg_mach'] > 0
            assert abs(physical['CL']-predicted) < 2e-12
            checks = strict['numerical_checks']
            assert strict['numerical_pass'] == all(c['passed'] for c in checks)
        rows.append(dict(id=job['id'],model=Path(job['model_path']).name,panels=job['settings']['panels'],
            expected=float(expected),predicted=predicted,passed=passed,numerical_pass=strict['numerical_pass'],
            error_percent=None if predicted is None else float(100*(Decimal(str(predicted))-expected)/abs(expected)),
            pg_mach=physical['aerodynamic_influences']['pg_mach'] if physical else None,
            numerical_checks=len(strict['numerical_checks']),
            residual=physical['residual'] if physical else None,
            maximum_local_mach=physical['lifting_airflow']['maximum'] if physical else None,
            seconds=report['seconds'],peak_rss_kib=report['peak_rss_kib']))
    write(out/'analysis.json',dict(observed_utc=utc(),rows=rows,pilot_passed=sum(r['passed'] for r in rows),
        pilot_required=6,primary_passes_added=0,registered_sa14_required=360,
        source_pins_verified=len(plan['pins']),plan_sha256=sha(out/'plan.json'),
        full_family_refresh=False,production_physics_changed=False))
    print(json.dumps(rows,indent=2))

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['prepare','run','summary'])
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--index',type=int)
    args = parser.parse_args(); bounded()
    if args.action == 'run': run(args.output.resolve(),args.index)
    elif args.action == 'prepare': prepare(args.output.resolve())
    else: summarize(args.output.resolve())
