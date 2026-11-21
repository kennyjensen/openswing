"""Repeat the unchanged UA-2 intervals after stable source displacement algebra.

The failed original study and every original gate/reference remain intact.
Only the tested source kernel changes; use separate artifact paths and hashes.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
ORIGINAL = ROOT/'artifacts/isae/ua2-time-current-20261103'
BASE = ROOT/'artifacts/isae/ua2-displacement-time-20261103'
spec = importlib.util.spec_from_file_location('ua2_current_time', ROOT/'scripts/verify-isae-ua2-current-time.py')
study = importlib.util.module_from_spec(spec); spec.loader.exec_module(study)
study.BASE = BASE
read, write, digest, pins, verify = study.read, study.write, study.digest, study.pins, study.verify


def prepare():
    BASE.mkdir()
    before = read(ORIGINAL/'plan.json')
    failed = read(ORIGINAL/'n40-part000/report.json')
    assert not failed['passed'] and not failed['checks']['local_motion']
    assert all(value for key, value in failed['checks'].items() if key != 'local_motion')
    changes = [name for name, value in before['source_sha256'].items() if digest(ROOT/name) != value]
    assert changes == ['openswing/source_discrete.py'], changes
    after = dict(before)
    after['jobs'] = sorted(before['jobs'], key=lambda j: (-j['panels'], j['part']))
    after['source_sha256'] = pins([ROOT/name for name in before['source_sha256']])
    after['source_sha256'].update(pins([Path(__file__).resolve(),ROOT/'tests/test_source_displacement_precision.py']))
    after['input_sha256'] = {**before['input_sha256'], **pins([ORIGINAL/'plan.json',
        ORIGINAL/'n40-part000/report.json', ORIGINAL/'n40-part000-execution.json'])}
    after['source_change'] = dict(path=changes[0], before_sha256=before['source_sha256'][changes[0]],
        after_sha256=after['source_sha256'][changes[0]],
        description='Algebraically identical Eq.48 translation residual evaluated in jig-relative displacement coordinates; strain retained separately from the unit span tangent.')
    after['unchanged_gates_and_requests'] = True
    write(BASE/'plan.json', after)
    for name in after['source_sha256']:
        target = BASE/'frozen-code'/name; target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes((ROOT/name).read_bytes())
    print(json.dumps(dict(prepared=True,jobs=len(after['jobs']),changed_production_modules=changes)))


def run_jobs(max_jobs):
    plan = read(BASE/'plan.json'); completed = 0
    for job in plan['jobs']:
        receipt_path = BASE/f'{job["id"]}-execution.json'
        if receipt_path.exists():
            receipt = read(receipt_path); assert receipt['exit_code'] == 0
            verify(receipt['output_sha256']); continue
        assert not (BASE/job['id']).exists(), 'Preserve interrupted evidence'
        print(json.dumps(dict(starting=job['id'])),flush=True)
        started = time.monotonic()
        with (BASE/f'{job["id"]}.log').open('x') as stream:
            try:
                child = subprocess.run([sys.executable,str(Path(__file__).resolve()),'run','--job',job['id']],
                    stdout=stream,stderr=subprocess.STDOUT,timeout=45)
                code = child.returncode
            except subprocess.TimeoutExpired:
                code = 124
        outputs = [p for p in (BASE/job['id']).glob('*') if p.is_file()] if (BASE/job['id']).exists() else []
        receipt = dict(exit_code=code,wall_seconds=time.monotonic()-started,output_sha256=pins(outputs))
        write(receipt_path,receipt)
        print(json.dumps(dict(job=job['id'],exit_code=code,seconds=receipt['wall_seconds'])),flush=True)
        if code: raise SystemExit(code)
        completed += 1
        if completed == max_jobs: break


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('prepare','run','run-jobs','combine'))
    parser.add_argument('--job');parser.add_argument('--max-jobs',type=int,default=1)
    args=parser.parse_args()
    if args.action=='prepare':prepare()
    elif args.action=='run':study.run(args.job)
    elif args.action=='run-jobs':run_jobs(args.max_jobs)
    else:study.combine()
