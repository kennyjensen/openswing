"""Bounded preparation and raw-history audits for the UA-1 stalled browser case.

Production starts cold in the built worker. Targets never seed that worker.
Each task is serial, has a 45-second process cap, and retains failures.
"""
import argparse
import gzip
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'artifacts/isae/ua1-stall-periodic-browser-20261102'
OLD = ROOT/'artifacts/isae/ua1-stall-periodic-20261102'
FINE = ROOT/'artifacts/isae/ua1-stall-periodic-20261102-fine20'
SCRIPT = Path(__file__).resolve()
FIELDS = ('CL', 'force_coefficient', 'CDp_fixed', 'circulation', 'circulation_rate',
          'section_cl', 'velocity', 'position', 'acceleration')


def read(path):
    return json.loads(path.read_text())


def write(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def digest(path):
    result = sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1048576), b''):
            result.update(block)
    return result.hexdigest()


def pins(paths):
    return {str(p.relative_to(ROOT)): digest(p) for p in paths}


def verify(values):
    for name, value in values.items():
        assert digest(ROOT/name) == value, name


def flatten(value):
    if isinstance(value, list):
        for item in value:
            yield from flatten(item)
    else:
        assert isinstance(value, (float, int)) and not isinstance(value, bool)
        assert math.isfinite(value), 'Nonfinite physical value'
        yield value


def difference(actual, expected):
    assert isinstance(actual, list) == isinstance(expected, list), 'Physical shape changed'
    if isinstance(actual, list):
        assert len(actual) == len(expected), 'Physical shape changed'
        return max((difference(a, b) for a, b in zip(actual, expected)), default=0.)
    a, b = next(flatten(actual)), next(flatten(expected))
    return abs(a-b)/max(1., abs(b))


def physical_row(sample, section):
    alpha = math.radians(section['alpha_deg'])
    heave = [-math.sin(alpha), 0., math.cos(alpha)]
    wind = [math.cos(alpha), 0., math.sin(alpha)]
    dot = lambda a, b: sum(x*y for x, y in zip(a, b, strict=True))
    frame = sample['frame']
    assert len(sample['strips']) == 4
    assert max(abs(x) for x in frame['attitude']+frame['rates_body']) < 1e-12
    assert abs(dot(frame['velocity_origin_body'], wind)+section['speed']) < 1e-10
    qs = .5*1.225*section['speed']**2*200000
    result = dict(time=sample['time'], CL=dot(sample['force'], heave)/qs,
        force_coefficient=[x/qs for x in sample['force']],
        CDp_fixed=sample['CDp']*(sample['operating_values']['speed']/section['speed'])**2,
        circulation=[s['circulation'] for s in sample['strips']],
        circulation_rate=sample['circulation_rate'], section_cl=[s['cl'] for s in sample['strips']],
        velocity=dot(frame['velocity_origin_body'], heave),
        position=dot(frame['position_earth'], heave),
        acceleration=dot(frame['acceleration_reference_body'], heave),
        residual=sample['residual'], order=sample['order'])
    assert len(result['circulation_rate']) == 4
    for value in result.values():
        list(flatten(value))
    return result


def prepare():
    assert not BASE.exists(), 'Preserve existing plans and interrupted evidence'
    original, fine, audit = [read(p) for p in (OLD/'plan.json', FINE/'plan.json', OLD/'audit.json')]
    assert audit['passed'] and all(audit['checks'].values())
    assert read(OLD/'delivery-complete-execution.json')['exit_code'] == 0
    assert read(OLD/'reference-check.json')['passed']
    assert fine['segment_steps'] == 20 and fine['cycles'] == 4 and fine['grids'] == [640]
    for key in ('section', 'cycles', 'gates', 'reference_steps'):
        assert fine[key] == original[key]
    production = {k:v for k,v in fine['source_sha256'].items() if k.startswith('openswing/')}
    assert len(production) == len(list((ROOT/'openswing').glob('*.py'))) == 136
    verify(production)
    manifest = read(ROOT/'dist/kernel/manifest.json')
    assert sorted(manifest) == sorted(Path(n).name for n in production)
    for name in manifest:
        assert digest(ROOT/'dist/kernel'/name) == production['openswing/'+name]
    workers = list((ROOT/'dist/assets').glob('worker-*.js'))
    assert len(workers) == 1
    scripts = ['isae_time_browser_compare.mjs', 'isae_ua1_stall_periodic.py',
        'isae_ua_stall_reference.py', 'isae_ua_stall_production.py', 'isae_ua_periodic.py',
        'isae_ua1_periodic_boundary.py', 'isae_ua1_periodic_study.py', 'isae_ua2_browser_cutoff.py',
        'run-isae-ua1-stall-periodic-browser.mjs']
    paths = [SCRIPT, *[ROOT/'scripts'/s for s in scripts],
        ROOT/'tests/test_isae_ua1_stall_browser.py', ROOT/'web/saved-state-data.js', workers[0],
        ROOT/'dist/kernel/manifest.json', *[ROOT/'dist/kernel'/n for n in manifest],
        *sorted(p for p in (ROOT/'dist/runtime').rglob('*') if p.is_file())]
    inputs = [OLD/'audit.json', OLD/'plan.json', OLD/'delivery-complete-execution.json',
        OLD/'reference-check.json', OLD/'reference-check-execution.json',
        OLD/'reference-DOP853.json', OLD/'reference-Radau.json',
        FINE/'plan.json', FINE/'request-n640.json']
    section = fine['section']
    period = math.pi*section['chord']/(section['speed']*section['k'])
    setup = dict(section=section, cycles=4, nominal_steps_per_cycle=640, period=period,
        times=[period*i/640 for i in range(2561)], full_request=read(FINE/'request-n640.json'),
        gates={**fine['gates'], 'CPython_scaled_difference':2e-8},
        jobs=[dict(part=p, start_index=p*8, end_index=(p+1)*8) for p in range(320)],
        max_steps_per_job=8, worker_request_timeout_seconds=45, panels=4,
        audit_jobs_per_chunk=8, target_chunks=32, target_original_jobs_per_chunk=4,
        source_sha256={**production, **pins(paths)}, input_sha256=pins(inputs),
        worker_url='/assets/'+workers[0].name, serial=True, threads=1,
        initial_state='Own browser steady equilibrium, with complete four-cycle forcing before startup.',
        scope='Four-cycle UA-1 supplemental stall/lag case: actual built worker, every physical time node and every strip.',
        normalization=original['normalization'],
        production_changed=False, native_ASWING_comparison=False, full_history_UI_validation=False,
        new_browser_temporal_refinement_claim=False,
        refinement_note='Browser fine-grid errors are also checked against the retained CPython coarse errors. This mixed-runtime diagnostic does not constitute a two-grid browser refinement study.')
    assert setup['full_request']['condition']['stall']
    assert setup['full_request']['time']['duration'] == 4*period
    BASE.mkdir()
    (BASE/'targets').mkdir()
    for name in setup['source_sha256']:
        if name.startswith('dist/runtime/'):
            continue
        dest = BASE/'frozen-code'/name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT/name, dest)
    shutil.copyfile(ROOT/'docs/validation/ISAE_STATUS.md', BASE/'status-before.md')
    write(BASE/'setup.json', setup)
    print(json.dumps(dict(prepared=True, target_chunks=32, browser_jobs=320, numerical_jobs_started=0)), flush=True)


def target(index, setup):
    assert 0 <= index < 32
    rows = []; inputs = {}
    for part in range(index*4, index*4+4):
        folder = FINE/f'n640-part{part:03d}'
        receipt_path = FINE/(folder.name+'-execution.json')
        receipt = read(receipt_path)
        assert receipt['exit_code'] == 0
        verify(receipt['output_sha256'])
        inputs.update(receipt['output_sha256']); inputs.update(pins([receipt_path]))
        with gzip.open(folder/'trajectory.json.gz', 'rt') as stream:
            raw = json.load(stream)
        assert raw['converged'] and raw['accepted_steps'] == 20 and raw['rejected_steps'] == 0
        assert len(raw['snapshots']) == 21
        reduced = read(folder/'audit.json')['rows']
        current = [physical_row(s, setup['section']) for s in raw['snapshots']]
        del raw
        for local, row in enumerate(current):
            assert abs(row['time']-setup['times'][part*20+local]) < 1e-12
            if part and not local:
                continue
            expected = reduced[local if part == 0 else local-1]
            for key in expected:
                assert difference(row[key], expected[key]) < 1e-12, key
        if rows:
            for field in FIELDS:
                assert difference(rows[-1][field], current[0][field]) == 0, field
        rows.extend(current if not rows else current[1:])
    assert len(rows) == 81
    targets = []
    for offset in range(10):
        part = index*10+offset
        path = BASE/'targets'/f'part{part:03d}.json'
        write(path, dict(job=setup['jobs'][part], rows=rows[offset*8:offset*8+9]))
        targets.append(dict(path=str(path.relative_to(BASE)), sha256=digest(path)))
    write(BASE/f'target-chunk{index:03d}.json', dict(targets=targets, input_sha256=inputs,
        setup_sha256=digest(BASE/'setup.json')))
    print(json.dumps(dict(target_chunk=index, target_jobs=10, physical_states=81)), flush=True)


def completed(name):
    output = BASE/(name+'.json')
    receipt_path = BASE/(name+'-execution.json')
    receipt = read(receipt_path)
    assert receipt['exit_code'] == 0 and receipt['report_sha256'] == digest(output), name
    return read(output), pins([output, receipt_path])


def freeze(setup):
    inputs = dict(setup['input_sha256']); targets = []
    for index in range(32):
        chunk, bound = completed(f'target-chunk{index:03d}')
        assert chunk['setup_sha256'] == digest(BASE/'setup.json')
        inputs.update(bound); inputs.update(chunk['input_sha256']); targets.extend(chunk['targets'])
    assert len(targets) == 320
    for job, item in zip(setup['jobs'], targets, strict=True):
        path = BASE/item['path']
        assert digest(path) == item['sha256'] and read(path)['job'] == job
    verify({**setup['source_sha256'], **inputs})
    write(BASE/'plan.json', dict(**{**setup, 'input_sha256':inputs}, targets=targets,
        setup_sha256=digest(BASE/'setup.json')))
    print(json.dumps(dict(frozen=True, jobs=320, states=2561, sources_unchanged=True)), flush=True)


def audit(index, plan):
    from isae_ua1_periodic_boundary import check_boundary
    from isae_ua2_browser_cutoff import validate_checkpoint
    assert 0 <= index < 40
    inputs = {}; rows = []; boundaries = 0; rounding = []; largest = 0.; fingerprint = None
    previous = None
    if index:
        prior = BASE/'production'/f'part{index*8-1:03d}'
        receipt = read(prior/'receipt.json'); assert receipt['outcome'] == 'success'
        assert digest(prior/'checkpoint.json') == receipt['output_sha256']['checkpoint.json']
        previous = read(prior/'checkpoint.json'); inputs.update(pins([prior/'checkpoint.json', prior/'receipt.json']))
    for job in plan['jobs'][index*8:(index+1)*8]:
        part = job['part']; folder = BASE/'production'/f'part{part:03d}'
        receipt = read(folder/'receipt.json')
        assert receipt['outcome'] == 'success' and receipt['plan_sha256'] == digest(BASE/'plan.json')
        assert receipt['job'] == job
        for name, value in receipt['output_sha256'].items():
            assert digest(folder/name) == value, name
            inputs[str((folder/name).relative_to(ROOT))] = value
        inputs.update(pins([folder/'receipt.json']))
        report = read(folder/'report.json')
        assert report['accepted_steps'] == 8 and report['rejected_steps'] == 0
        with gzip.open(folder/'trajectory.json.gz', 'rt') as stream:
            raw = json.load(stream)
        assert raw['converged'] and raw['accepted_steps'] == 8 and raw['rejected_steps'] == 0
        assert len(raw['snapshots']) == 9
        provenance = raw['software_provenance']
        assert provenance == report['software_provenance']
        assert len(provenance['modules']) == 136
        for name, value in provenance['modules'].items():
            assert value == plan['source_sha256']['openswing/'+name], name
        if fingerprint is not None:
            assert fingerprint == provenance['fingerprint']
        fingerprint = provenance['fingerprint']
        end = raw['snapshots'][-1]['time']
        assert abs(end-plan['times'][job['end_index']]) < 1e-12
        validate_checkpoint(raw, final=part==319, expected_end=end)
        if previous:
            rounding.extend(check_boundary(previous, raw['snapshots'])); boundaries += 1
        target_path = BASE/plan['targets'][part]['path']
        assert digest(target_path) == plan['targets'][part]['sha256']
        inputs.update(pins([target_path]))
        expected = read(target_path); assert expected['job'] == job
        assert report['job'] == job and report['segment_passed']
        assert len(report['rows']) == 9
        for local, sample in enumerate(raw['snapshots']):
            row = physical_row(sample, plan['section'])
            n = job['start_index']+local
            assert abs(row['time']-plan['times'][n]) < 1e-12
            assert row['order'] == (0 if local == 0 else 1 if n == 1 else 2)
            assert 0 <= row['residual'] < plan['gates']['residual']
            for key in row:
                assert difference(row[key], report['rows'][local][key]) < 1e-12, key
            for key in FIELDS:
                d = difference(row[key], expected['rows'][local][key])
                assert d < plan['gates']['CPython_scaled_difference'], (part, key, d)
                largest = max(largest, d)
            if local or part == 0:
                rows.append(row)
        previous = read(folder/'checkpoint.json')
        saved = raw['snapshots'][-1]['restart']
        context = raw['snapshots'][-1].get('restart_context', raw['restart_context'])
        assert previous == dict(format='openswing-time-checkpoint', context=context,
                                **{**saved, 'version':saved.get('version', 1)})
        del raw
    write(BASE/f'audit-chunk{index:03d}.json', dict(rows=rows, boundary_checks=boundaries,
        restart_rounding=rounding, maximum_CPython_scaled_difference=largest,
        runtime_fingerprint=fingerprint, input_sha256=inputs, plan_sha256=digest(BASE/'plan.json')))
    print(json.dumps(dict(chunk=index, unique_states=len(rows), boundaries=boundaries,
        maximum_CPython_scaled_difference=largest)), flush=True)


def combine(plan):
    from isae_ua1_stall_periodic import summarize, checks, GATES
    from isae_ua_stall_reference import Section
    assert {k:v for k,v in plan['gates'].items() if k != 'CPython_scaled_difference'} == GATES
    assert read(BASE/'production-complete.json')['computed_jobs'] == 320
    rows = []; inputs = dict(plan['input_sha256']); boundaries = 0; largest = 0.; fingerprints = set()
    for index in range(40):
        chunk, bound = completed(f'audit-chunk{index:03d}')
        assert chunk['plan_sha256'] == digest(BASE/'plan.json')
        rows.extend(chunk['rows']); inputs.update(bound); inputs.update(chunk['input_sha256'])
        boundaries += chunk['boundary_checks']; fingerprints.add(chunk['runtime_fingerprint'])
        largest = max(largest, chunk['maximum_CPython_scaled_difference'])
    assert len(rows) == 2561 and boundaries == 319 and len(fingerprints) == 1
    section = Section(**plan['section'])
    fine = summarize(section, 640, 4, rows, read(OLD/'reference-DOP853.json'))
    coarse = read(OLD/'audit.json')['results']['320']
    gates, ratios = checks({'320':coarse, '640':fine}, read(OLD/'reference-check.json')['passed'], section)
    gates['mixed_runtime_refinement_consistency'] = gates.pop('refinement')
    gates['CPython_agreement'] = largest < plan['gates']['CPython_scaled_difference']
    verify({**plan['source_sha256'], **inputs})
    result = dict(passed=all(gates.values()), checks=gates, fine=fine, unique_states=len(rows),
        boundary_checks=boundaries, accepted_steps=2560, rejected_steps=0,
        maximum_CPython_scaled_difference=largest, mixed_runtime_refinement_ratios=ratios,
        source_sha256=plan['source_sha256'], input_sha256=inputs, plan_sha256=digest(BASE/'plan.json'),
        new_browser_temporal_refinement_claim=False, production_changed=False,
        native_ASWING_comparison=False, full_history_UI_validation=False, full_goal_complete=False)
    write(BASE/'audit.json', result)
    print(json.dumps({k:v for k,v in result.items() if k not in ('source_sha256','input_sha256','fine')}), flush=True)
    assert result['passed']


def run(phase, max_jobs):
    setup = read(BASE/'setup.json')
    verify(setup['source_sha256'])
    if phase == 'targets':
        jobs = [(f'target-chunk{i:03d}', ['target', '--index', str(i)]) for i in range(32)]
    else:
        jobs = [(f'audit-chunk{i:03d}', ['audit', '--index', str(i)]) for i in range(40)]
    env = dict(os.environ, OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1', MKL_NUM_THREADS='1', PYTHONDONTWRITEBYTECODE='1')
    count = 0
    for name, arguments in jobs:
        output, receipt_path, log = [BASE/(name+s) for s in ('.json','-execution.json','.log')]
        if receipt_path.exists():
            completed(name); continue
        if phase == 'audits':
            index = int(name[-3:])
            if not (BASE/'production'/f'part{index*8+7:03d}'/'receipt.json').exists():
                break
        assert not output.exists() and not log.exists(), 'Inspect interrupted work: '+name
        command = ['timeout','45s',sys.executable,str(SCRIPT),*arguments]
        print(json.dumps(dict(starting=name)), flush=True)
        start = time.monotonic()
        with log.open('x') as stream:
            child = subprocess.Popen(command, cwd=ROOT, env=env, stdout=stream, stderr=subprocess.STDOUT)
            live = dict(status='running', job=name, runner_pid=os.getpid(), child_pid=child.pid, command=command)
            live_path = BASE/('live-'+phase+'.json')
            live_path.write_text(json.dumps(live)+'\n')
            code = child.wait()
        live.update(status='terminal', exit_code=code, seconds=time.monotonic()-start)
        if output.exists():
            live['report_sha256'] = digest(output)
        write(receipt_path, live); live_path.write_text(json.dumps(live)+'\n')
        print(json.dumps(dict(job=name, exit_code=code, seconds=live['seconds'])), flush=True)
        if code:
            raise SystemExit(code if code > 0 else 1)
        count += 1
        if max_jobs and count >= max_jobs:
            break


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare','target','freeze','audit','combine','run-targets','run-audits'])
    parser.add_argument('--index', type=int)
    parser.add_argument('--max-jobs', type=int)
    args = parser.parse_args()
    if args.max_jobs is not None and args.max_jobs < 1:
        parser.error('Positive job count required')
    if args.action == 'prepare':
        prepare(); return
    if args.action.startswith('run-'):
        run(args.action[4:], args.max_jobs); return
    setup = read(BASE/('plan.json' if args.action in ('audit','combine') else 'setup.json'))
    verify({k:v for k,v in setup['source_sha256'].items() if not k.startswith('dist/runtime/')})
    if args.action == 'target':
        target(args.index, setup)
    elif args.action == 'freeze':
        freeze(setup)
    elif args.action == 'audit':
        audit(args.index, setup)
    else:
        combine(setup)


if __name__ == '__main__':
    main()
