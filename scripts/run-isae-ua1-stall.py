"""Serial, bounded UA-1 stall/lag verification with retained complete histories."""
import argparse
from dataclasses import asdict, replace
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

import numpy as np

from isae_ua_stall_reference import Section, trajectory
from isae_ua_stall_production import request, evaluate_point
from isae_ua_artifacts import write_trajectory
from isae_ua1_periodic_study import check_restart_join
from isae_ua1_periodic_boundary import check_boundary
from isae_ua2_browser_cutoff import validate_checkpoint

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = Path(__file__).resolve()
sys.path.insert(0, str(ROOT))
GATES = dict(reference_fraction=1e-9, instantaneous_force_absolute=5e-5,
    instantaneous_residual_absolute=5e-5, instantaneous_pressure_peak_fraction=1e-4,
    apparent_absolute=1e-12, rotation_absolute=2e-12,
    time_waveform_fraction=.001, time_pressure_peak_fraction=.001,
    fine_to_coarse_ratio=.35, motion_fraction=.001, residual=1e-10)
KEYS = ('CL', 'circulation', 'circulation_rate', 'CDp_fixed')


def read(path):
    return json.loads(path.read_text())


def write(path, value):
    with path.open('x') as stream:
        stream.write(json.dumps(value, indent=2, allow_nan=False)+'\n')


def digest(path):
    result = sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            result.update(block)
    return result.hexdigest()


def verify(pins):
    for name, value in pins.items():
        assert digest(ROOT/name) == value, name


def prepare(base):
    section = Section()
    names = ['isae_ua_stall_reference.py', 'isae_ua_stall_production.py', 'isae_ua_artifacts.py',
        'isae_suite_unsteady.py', 'isae_ua1_periodic_study.py', 'isae_ua1_periodic_boundary.py',
        'isae_ua2_browser_cutoff.py', 'isae_ua_incidence_reference.py', 'isae_ua_incidence_periodic.py',
        'isae_ua_periodic.py', 'isae_ua_section_reference.py']
    paths = [*sorted((ROOT/'openswing').glob('*.py')), SCRIPT,
        *[ROOT/'scripts'/name for name in names], ROOT/'tests/test_isae_ua_stall_reference.py',
        ROOT/'.reference/asw_theory.txt', ROOT/'.reference/asw_uns_theory.txt']
    pins = {str(path.relative_to(ROOT)): digest(path) for path in paths}
    plan = dict(section=asdict(section), grids=[160, 320, 640], segment_steps=40,
        probe_meshes=[4, 8], probe_blocks=2, gates=GATES, time_atol=1e-12,
        source_sha256=pins, serial=True, threads=1, subprocess_timeout_seconds=45,
        production_changed=False, native_ASWING_comparison=False, browser_validation=False,
        scope='Supplemental documented stall leakage plus circulation lag; one cold heave cycle. Declared CL bounds are not recovered native UA-1 settings.',
        normalization='Lift/circulation: peak departure from pre-motion steady. Rate and pressure drag: own reference peaks. Every strip participates.',
        full_forcing_before_startup=True,
        registered_rows=[line for line in (ROOT/'docs/validation/ISAE_STATUS.md').read_text().splitlines() if line.startswith('| [')])
    write(base/'plan.json', plan)
    shutil.copyfile(ROOT/'docs/validation/ISAE_STATUS.md', base/'status-before.md')
    for path in paths:
        target = base/'frozen-code'/path.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
    times = np.array([section.period*i/640 for i in range(641)])
    references = {method: trajectory(section, times, method) for method in ('DOP853', 'Radau')}
    differences = {}
    for key in KEYS:
        a, b = [np.array([row[key] for row in references[m]['rows']]) for m in ('DOP853', 'Radau')]
        differences[key] = float(np.max(abs(a-b))/np.max(abs(b)))
    rows = references['DOP853']['rows']
    passed = max(differences.values()) < GATES['reference_fraction']
    assert min(r['section_cl'] for r in rows) < section.clmax-.1 < section.clmax < max(r['section_cl'] for r in rows)
    write(base/'reference.json', dict(passed=passed, references=references, error_fractions=differences,
        section_cl_range=[min(r['section_cl'] for r in rows), max(r['section_cl'] for r in rows)],
        peak_pressure_drag=max(r['CDp_fixed'] for r in rows)))
    for steps in plan['grids']:
        write(base/f'request-n{steps}.json', request(section, steps))
    verify(pins)
    print(json.dumps(dict(reference_passed=passed, differences=differences,
        section_cl_range=[min(r['section_cl'] for r in rows), max(r['section_cl'] for r in rows)],
        peak_pressure_drag=max(r['CDp_fixed'] for r in rows))), flush=True)
    assert passed


def probe(base, plan, panels, block):
    section = Section(**plan['section'])
    reference = read(base/'reference.json')
    assert reference['passed'] and panels in plan['probe_meshes'] and block in (0, 1)
    rows = reference['references']['DOP853']['rows']
    checks = []
    for index in range(8*block, 8*(block+1)):
        row = rows[index*40]
        # Both stall signs, plus off-equation states at the velocity extrema.
        for sign in (1, -1):
            reflected = replace(section, alpha_deg=sign*section.alpha_deg)
            g, rate, w, a = [sign*row[key] for key in ('circulation', 'circulation_rate', 'velocity', 'acceleration')]
            for offset in ([0., 10.*sign] if index in (4, 12) else [0.]):
                target = reflected.fields(g, w, a, rate=rate+offset)
                actual = {rep: evaluate_point(reflected, g, rate+offset, w, a, panels=panels, representation=rep)
                          for rep in ('body', 'wind')}
                errors = {}
                for rep, result in actual.items():
                    errors[rep] = dict(
                        force=max(float(np.max(abs(np.array(result[key])-target[key]))) for key in ('CF', 'CF_rate', 'CL_instantaneous')),
                        apparent=float(np.max(abs(np.array(result['CF_apparent'])-target['CF_apparent']))),
                        # Production scales by instantaneous reference speed;
                        # this section reference uses the fixed mean speed.
                        residual=float(np.max(abs(np.array(result['circulation_residual'])*
                            math.hypot(section.speed, w)/section.speed-target['residual']))),
                        pressure_fraction=abs(result['CDp_fixed']-target['CDp_fixed'])/reference['peak_pressure_drag'])
                rotation = max(float(np.max(abs(np.array(actual['body'][key])-actual['wind'][key])))
                               for key in ('CF', 'CF_rate', 'CF_apparent', 'circulation_residual', 'CDp_fixed'))
                passed = rotation < GATES['rotation_absolute'] and all(
                    e['force'] < GATES['instantaneous_force_absolute'] and
                    e['apparent'] < GATES['apparent_absolute'] and
                    e['residual'] < GATES['instantaneous_residual_absolute'] and
                    e['pressure_fraction'] < GATES['instantaneous_pressure_peak_fraction'] for e in errors.values())
                checks.append(dict(index=index, sign=sign, rate_offset=offset, reference=target,
                    production=actual, errors=errors, rotation_error=rotation, passed=bool(passed)))
    verify(plan['source_sha256'])
    report = dict(checks=checks, passed=all(c['passed'] for c in checks),
        checks_total=len(checks), checks_passed=sum(c['passed'] for c in checks))
    write(base/f'probe-n{panels}-part{block:03d}.json', report)
    print(json.dumps({key: report[key] for key in ('passed', 'checks_passed', 'checks_total')}), flush=True)
    assert report['passed']


def completed(base, name):
    receipt = read(base/(name+'-execution.json'))
    assert receipt['exit_code'] == 0, name
    verify(receipt['output_sha256'])
    return receipt


def name_for(steps, part):
    return f'n{steps}-part{part:03d}'


def segment(base, plan, steps, part):
    from openswing.bridge import dispatch
    from openswing.time_state import checkpoint
    section, size = Section(**plan['section']), plan['segment_steps']
    assert steps in plan['grids'] and part in range(steps//size)
    full = read(base/f'request-n{steps}.json')
    assert full == request(section, steps)
    end = section.period*(size*(part+1))/steps
    folder = base/name_for(steps, part)
    folder.mkdir()
    calculation = {**full, 'time': {**full['time'], 'duration': end}}
    prior = None
    if part:
        name = name_for(steps, part-1)
        completed(base, name)
        prior = read(base/name/'checkpoint.json')
        calculation = {key: value for key, value in full.items() if key not in ('condition', 'time')}
        calculation.update(action='resume_time', checkpoint=prior,
            time=dict(duration=end-prior['state']['time'], max_steps=4*steps))
    write(folder/'request.json', calculation)
    start = time.monotonic()
    raw = dispatch(calculation)
    seconds = time.monotonic()-start
    # Retain complete solver output even if a subsequent validation assertion fails.
    write_trajectory(folder/'trajectory.json.gz', raw)
    assert raw['converged'] and raw['accepted_steps'] == size and raw['rejected_steps'] == 0
    samples = raw['snapshots']
    assert len(samples) == size+1 and abs(samples[-1]['time']-end) < plan['time_atol']
    validate_checkpoint(raw, final=(part == steps//size-1), expected_end=samples[-1]['time'])
    rounding = check_boundary(prior, samples) if prior else []
    write(folder/'checkpoint.json', checkpoint(raw))
    write(folder/'report.json', dict(seconds=seconds, maximum_residual=max(r['residual'] for r in samples),
        accepted_steps=size, rejected_steps=0, restart_rounding=rounding))
    verify(plan['source_sha256'])
    print(json.dumps(dict(job=folder.name, seconds=seconds)), flush=True)


def audit(base, plan, steps, part):
    section, size = Section(**plan['section']), plan['segment_steps']
    name = name_for(steps, part)
    receipt = completed(base, name)
    with gzip.open(base/name/'trajectory.json.gz', 'rt') as stream:
        raw = json.load(stream)
    samples = raw['snapshots']
    assert raw['converged'] and raw['accepted_steps'] == size and raw['rejected_steps'] == 0
    assert len(samples) == size+1
    validate_checkpoint(raw, final=(part == steps//size-1), expected_end=samples[-1]['time'])
    rounding = []
    inputs = dict(receipt['output_sha256'])
    if part:
        prior_path = base/name_for(steps, part-1)/'checkpoint.json'
        prior = read(prior_path)
        rounding = check_boundary(prior, samples)
        inputs[str(prior_path.relative_to(ROOT))] = digest(prior_path)
    targets = read(base/'reference.json')['references']['DOP853']['rows']
    rows = []
    for local, sample in enumerate(samples):
        index = part*size+local
        target = targets[index*(640//steps)]
        assert abs(sample['time']-target['time']) < plan['time_atol']
        if part and local == 0:
            continue
        if index:
            assert sample['order'] == (1 if index == 1 else 2)
        frame = sample['frame']
        assert max(abs(x) for x in frame['attitude']+frame['rates_body']) < 1e-12
        velocity = np.array(frame['velocity_origin_body'])
        acceleration = np.array(frame['acceleration_reference_body'])
        assert abs(velocity@section.wind+section.speed) < 1e-10
        assert abs(acceleration@section.heave-target['acceleration']) < 1e-10
        rows.append(dict(time=sample['time'], CL=float(np.array(sample['force'])@section.heave/(.5*1.225*section.speed**2*200000)),
            CDp_fixed=sample['CDp']*(sample['operating_values']['speed']/section.speed)**2,
            circulation=[s['circulation'] for s in sample['strips']], circulation_rate=sample['circulation_rate'],
            section_cl=[s['cl'] for s in sample['strips']], residual=sample['residual'],
            velocity=float(velocity@section.heave), position=float(np.array(frame['position_earth'])@section.heave)))
    verify({**plan['source_sha256'], **inputs})
    write(base/f'audit-{name}.json', dict(rows=rows, input_sha256=inputs, boundary_checks=int(part>0), restart_rounding=rounding))
    print(json.dumps(dict(audited=len(rows), grid=steps, part=part)), flush=True)


def combine(base, plan):
    section = Section(**plan['section'])
    reference = read(base/'reference.json')
    targets = reference['references']['DOP853']['rows']
    initial = section.fields(reference['references']['DOP853']['initial_circulation'], 0., 0., rate=0.)
    scales = {key: max(abs(r[key]-(initial[key] if key in ('CL', 'circulation') else 0.)) for r in targets) for key in KEYS}
    results, inputs, checks = {}, {}, {}
    for panels in plan['probe_meshes']:
        for block in range(plan['probe_blocks']):
            name = f'probe-n{panels}-part{block:03d}'
            inputs.update(completed(base, name)['output_sha256'])
            checks[name] = read(base/(name+'.json'))['passed']
    for steps in plan['grids']:
        rows, boundaries = [], 0
        for part in range(steps//plan['segment_steps']):
            name = 'audit-'+name_for(steps, part)
            inputs.update(completed(base, name)['output_sha256'])
            report = read(base/(name+'.json'))
            rows.extend(report['rows'])
            inputs.update(report['input_sha256'])
            boundaries += report['boundary_checks']
        assert len(rows) == steps+1 and boundaries == steps//plan['segment_steps']-1
        expected = targets[::640//steps]
        errors = {}
        for key in KEYS:
            actual = np.array([r[key] for r in rows])
            target = np.array([r[key] for r in expected])
            if key in ('circulation', 'circulation_rate'):
                target = target[:, None]
            errors[key] = float(np.max(abs(actual-target))/scales[key])
        results[str(steps)] = dict(samples=len(rows), error_fractions=errors, boundary_checks=boundaries,
            residual=max(r['residual'] for r in rows),
            velocity_fraction=max(abs(r['velocity']-t['velocity']) for r,t in zip(rows, expected))/(section.speed*section.k*section.amplitude_ratio),
            position_fraction=max(abs(r['position']-t['displacement']) for r,t in zip(rows, expected))/(section.amplitude_ratio/2),
            section_cl_range=[min(min(r['section_cl']) for r in rows), max(max(r['section_cl']) for r in rows)])
    fine = results['640']
    ratios = {f'{coarse}:{fine_steps}': {key: results[str(fine_steps)]['error_fractions'][key]/results[str(coarse)]['error_fractions'][key] for key in KEYS}
              for coarse, fine_steps in zip(plan['grids'][:-1], plan['grids'][1:])}
    checks.update({key: value < GATES['time_pressure_peak_fraction' if key == 'CDp_fixed' else 'time_waveform_fraction']
                   for key, value in fine['error_fractions'].items()})
    checks.update(refinement=all(v < GATES['fine_to_coarse_ratio'] for group in ratios.values() for v in group.values()),
        residual=max(r['residual'] for r in results.values()) < GATES['residual'],
        motion=max(fine['velocity_fraction'], fine['position_fraction']) < GATES['motion_fraction'])
    verify({**plan['source_sha256'], **inputs})
    output = dict(passed=all(checks.values()), checks=checks, results=results, refinement_ratios=ratios,
        scales=scales, source_sha256=plan['source_sha256'], input_sha256=inputs,
        audited_unique_states=sum(r['samples'] for r in results.values()),
        production_changed=False, native_ASWING_comparison=False, browser_validation=False)
    write(base/'audit.json', output)
    print(json.dumps({k: output[k] for k in ('passed', 'checks', 'results', 'refinement_ratios', 'audited_unique_states')}), flush=True)
    assert output['passed'], 'Retain failed accuracy gates; do not relax them'


def run(base, plan, phase, max_jobs):
    assert read(base/'reference.json')['passed']
    if phase == 'probe':
        jobs = [(f'probe-n{n}-part{p:03d}', 'probe', n, p) for n in plan['probe_meshes'] for p in range(plan['probe_blocks'])]
    else:
        for n in plan['probe_meshes']:
            for p in range(plan['probe_blocks']):
                completed(base, f'probe-n{n}-part{p:03d}')
        jobs = [(('audit-' if phase == 'audit' else '')+name_for(n,p), 'audit' if phase == 'audit' else 'segment', n, p)
                for n in plan['grids'] for p in range(n//plan['segment_steps'])]
    env = dict(os.environ, OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1', MKL_NUM_THREADS='1', PYTHONDONTWRITEBYTECODE='1')
    count = 0
    for name, action, steps, part in jobs:
        if (base/(name+'-execution.json')).exists():
            completed(base, name)
            continue
        assert not (base/name).exists() and not (base/(name+'.json')).exists(), 'Unreceipted work: inspect live process first'
        command = ['timeout', '45s', sys.executable, str(SCRIPT), action, '--base', str(base), '--steps', str(steps), '--part', str(part)]
        start = time.monotonic()
        print(json.dumps(dict(starting=name)), flush=True)
        with (base/(name+'.log')).open('x') as log:
            child = subprocess.Popen(command, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
            live = dict(status='running', runner_pid=os.getpid(), child_pid=child.pid, command=command)
            (base/'live-job.json').write_text(json.dumps(live)+'\n')
            code = child.wait()
        receipt = dict(**live, exit_code=code, seconds=time.monotonic()-start)
        receipt['status'] = 'terminal'
        if code == 0:
            paths = [base/name/file for file in ('request.json','trajectory.json.gz','checkpoint.json','report.json')] if action == 'segment' else [base/(name+'.json')]
            receipt['output_sha256'] = {str(p.relative_to(ROOT)): digest(p) for p in paths}
        write(base/(name+'-execution.json'), receipt)
        (base/'live-job.json').write_text(json.dumps(receipt)+'\n')
        print(json.dumps(dict(job=name, exit_code=code, seconds=receipt['seconds'])), flush=True)
        if code != 0:
            raise SystemExit(code if code > 0 else 1)
        count += 1
        if max_jobs and count >= max_jobs:
            break


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare','probe','segment','audit','combine','run'])
    parser.add_argument('--base', type=Path, default=ROOT/'artifacts/isae/ua1-stall-20261102')
    parser.add_argument('--steps', type=int)
    parser.add_argument('--part', type=int)
    parser.add_argument('--phase', choices=['probe','production','audit'])
    parser.add_argument('--max-jobs', type=int)
    args = parser.parse_args()
    base = args.base.resolve()
    assert base.is_relative_to(ROOT/'artifacts/isae')
    if args.action == 'prepare':
        prepare(base)
        return
    plan = read(base/'plan.json')
    assert plan['gates'] == GATES
    verify(plan['source_sha256'])
    if args.action == 'run':
        run(base, plan, args.phase, args.max_jobs)
    elif args.action == 'combine':
        combine(base, plan)
    else:
        {'probe':probe, 'segment':segment, 'audit':audit}[args.action](base, plan, args.steps, args.part)


if __name__ == '__main__':
    main()
