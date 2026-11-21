"""Bounded current-source UA-2 cold, owned-restart and legacy-restart checks.

This is a regression of selected intervals, not a fresh eight-cycle study or
native ASWING reproduction. Run numerical children serially with one BLAS thread.
"""
import argparse
from copy import deepcopy
import difflib
import gzip
import json
import math
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from isae_ua1_stall_browser import read, write, digest, pins, verify, flatten, difference

BASE = ROOT/'artifacts/isae/ua2-time-current-20261103'
OLD20 = ROOT/'artifacts/isae/ua2-incidence-periodic-browser-20261101'
OLD40 = ROOT/'artifacts/isae/ua2-incidence-periodic-n40-20261101'
PARTS = (0, 1, 290, 300)
LOCAL = ('local_velocity', 'local_rates', 'local_acceleration', 'local_rate_derivative')
LIMITS = dict(waveform_fraction=.001, velocity_fraction=.001,
    position_fraction=.001, first_step_rate_fraction=.01,
    normalized_residual=1e-10, local_motion=2e-8, join_scaled=2e-8)


def unzip(path):
    with gzip.open(path, 'rt') as stream:
        return json.load(stream)


def physical(sample, panels):
    import numpy as np
    angle = math.radians(9.)
    direction = np.array([-math.sin(angle), 0., math.cos(angle)])
    wind = np.array([math.cos(angle), 0., math.sin(angle)])
    frame = sample['frame']; qs = .5*1.225*100*10
    assert len(sample['strips']) == panels
    assert max(map(abs, frame['attitude'] + frame['rates_body'])) < 1e-12
    assert abs(np.dot(frame['velocity_origin_body'], wind)+10) < 1e-10
    net = sample['restart']['state']['network']
    return dict(time=sample['time'], order=sample['order'], residual=sample['residual'],
        CL=float(np.dot(sample['force'], direction)/qs),
        circulation=[s['circulation'] for s in sample['strips']],
        circulation_rate=sample['circulation_rate'],
        force_coefficient=(np.array(sample['force'])/qs).tolist(),
        moment_coefficient=(np.array(sample['moment'])/(qs*10)).tolist(),
        velocity=float(np.dot(frame['velocity_origin_body'], direction)),
        position=float(np.dot(frame['position_earth'], direction)),
        acceleration=float(np.dot(frame['acceleration_reference_body'], direction)),
        node_positions=net['positions'], node_rotations=net['rotations'],
        internal_force=(np.array(net['internal_force'])/qs).tolist(),
        internal_moment=(np.array(net['internal_moment'])/(qs*10)).tolist(),
        **{key: sample[key] for key in LOCAL},
        **{'frame_'+key: value for key, value in frame.items()})


def charts(value):
    """Check every present chart, including accepted-method predecessors."""
    import numpy as np
    count = 0
    if isinstance(value, dict):
        if 'position_chart' in value:
            c = value['position_chart']
            assert c['scheme'] == 'jig-relative-translation-v1' and c['scale'] > 0
            represented = np.asarray(c['origin']) + c['scale']*np.asarray(c['coordinates'])
            assert np.isfinite(represented).all()
            assert np.array_equal(represented, value['network']['positions'])
            count += 1
        count += sum(charts(v) for v in value.values())
    elif isinstance(value, list):
        count += sum(charts(v) for v in value if isinstance(v, (dict, list)))
    return count


def prepare():
    import numpy as np
    from openswing.time_state import checkpoint
    from isae_ua2_incidence_periodic import full_request, grid
    assert not (BASE/'plan.json').exists()
    (BASE/'targets').mkdir()
    delta_path = ROOT/'artifacts/isae/ua2-harmonic-matrix-20261103/time-followup-source-delta.json'
    delta = read(delta_path)
    prior_path = ROOT/'docs/validation/isae-ua2-incidence-periodic-browser-20261101.json'
    prior = read(prior_path)['software_provenance']['modules']
    assert len(prior) == len(list((ROOT/'openswing').glob('*.py'))) == 136
    changed = sorted('openswing/'+name for name, value in prior.items()
        if digest(ROOT/'openswing'/name) != value)
    assert changed == sorted(row['path'] for row in delta['changed_solver_modules'])
    diff = []
    for row in delta['changed_solver_modules']:
        old = OLD20/'frozen-code'/row['path']; current = ROOT/row['path']
        assert digest(old) == row['prior_sha256'] and digest(current) == row['current_sha256']
        diff.extend(difflib.unified_diff(old.read_text().splitlines(True), current.read_text().splitlines(True),
            fromfile=str(old.relative_to(ROOT)), tofile=row['path']))
    (BASE/'reviewed-source.diff').write_text(''.join(diff))
    paths = [Path(__file__).resolve(), delta_path, prior_path, BASE/'reviewed-source.diff',
        *[ROOT/'scripts'/n for n in ('isae_ua1_stall_browser.py', 'isae_ua2_incidence_periodic.py',
            'isae_ua2_incidence_time.py', 'isae_suite_unsteady.py', 'isae_ua_artifacts.py')]]
    source = pins([*sorted((ROOT/'openswing').glob('*.py')), *paths])
    inputs = {}; jobs = []; times = grid(640)
    for panels in (20, 40):
        audit_path = (ROOT/'artifacts/isae/ua2-incidence-periodic-20261101-r1/audit.json'
            if panels == 20 else OLD40/'audit.json')
        audit = read(audit_path); assert audit['passed']
        inputs.update(pins([audit_path]))
        result = audit['results']['640'] if panels == 20 else audit
        scales = result['scales']
        # The historical audit retains both independently integrated targets
        # and their verified full-history normalizations. Select without fitting.
        all_rows = result['rows']
        assert len(all_rows) == len(times) == 5281
        full = full_request(640); full['panels'] = panels
        for part in PARTS:
            name = f'n{panels}-part{part:03d}'
            selected = all_rows[part*16:part*16+17]
            reference = [r['reference'] for r in selected]
            assert np.max(abs(np.array([r['time'] for r in reference])-times[part*16:part*16+17])) < 1e-12
            target = dict(rows=reference, scales=scales, source_audit_sha256=digest(audit_path))
            target_path = BASE/'targets'/f'{name}.json'; write(target_path, target)
            job = dict(id=name, panels=panels, part=part, start_index=part*16, end_index=(part+1)*16,
                full_request=full, target=str(target_path.relative_to(ROOT)), target_sha256=digest(target_path),
                kind='cold' if part == 0 else 'owned_continuation' if part == 1 else 'legacy_replay')
            if part >= 290:
                parent = (OLD20 if panels == 20 else OLD40)/'production'/f'part{part-1:03d}'
                raw_path = parent/'trajectory.json.gz'
                raw = unzip(raw_path)
                assert raw['converged'] and raw['accepted_steps'] == 16 and raw['rejected_steps'] == 0
                saved = checkpoint(raw)
                assert 'position_chart' not in saved['state']
                assert abs(saved['state']['time']-times[part*16]) < 1e-12
                checkpoint_path = BASE/'targets'/f'{name}-legacy.json'
                write(checkpoint_path, saved)
                join_path = BASE/'targets'/f'{name}-join.json'
                write(join_path, physical(raw['snapshots'][-1], panels))
                job.update(checkpoint=str(checkpoint_path.relative_to(ROOT)), checkpoint_sha256=digest(checkpoint_path),
                    join=str(join_path.relative_to(ROOT)), join_sha256=digest(join_path))
                inputs.update(pins([raw_path]))
            jobs.append(job)
        del audit, result, all_rows
    plan = dict(jobs=jobs, times=times, gates=LIMITS, source_sha256=source, input_sha256=inputs,
        previous_goal_turn='progress', serial=True, threads=1, child_timeout_seconds=45,
        expected_jobs=8, expected_new_steps=128, new_native_passes=0,
        scope='Selected current-source intervals plus explicitly labelled legacy replays; not new eight-cycle histories.',
        native_ASWING_comparison=False, new_time_refinement_claim=False)
    write(BASE/'plan.json', plan)
    print(json.dumps(dict(prepared=True, jobs=len(jobs), new_steps=128)))


def run(name):
    import numpy as np
    from openswing.bridge import dispatch
    from openswing.time_state import checkpoint
    from isae_ua_artifacts import write_trajectory
    plan = read(BASE/'plan.json'); verify(plan['source_sha256'])
    job = next(j for j in plan['jobs'] if j['id'] == name)
    folder = BASE/name; folder.mkdir()
    target_path = ROOT/job['target']; assert digest(target_path) == job['target_sha256']
    target = read(target_path); request = deepcopy(job['full_request'])
    end = plan['times'][job['end_index']]; join = None
    dependencies = pins([BASE/'plan.json', target_path])
    if job['kind'] == 'cold':
        request['time']['duration'] = end
    else:
        if job['kind'] == 'owned_continuation':
            parent = BASE/f'n{job["panels"]}-part000'
            parent_report = read(parent/'report.json'); assert parent_report['passed']
            assert read(BASE/f'{parent.name}-execution.json')['exit_code'] == 0
            saved = read(parent/'checkpoint.json')
            join = parent_report['physical_rows'][-1]
            dependencies.update(pins([parent/'report.json', parent/'checkpoint.json', BASE/f'{parent.name}-execution.json']))
        else:
            assert digest(ROOT/job['checkpoint']) == job['checkpoint_sha256']
            assert digest(ROOT/job['join']) == job['join_sha256']
            saved = read(ROOT/job['checkpoint']); join = read(ROOT/job['join'])
            dependencies.update(pins([ROOT/job['checkpoint'], ROOT/job['join']]))
        request = {key: value for key, value in request.items() if key not in ('condition', 'time')}
        request.update(action='resume_time', checkpoint=saved,
            time=dict(duration=end-saved['state']['time'], max_steps=128))
    write(folder/'request.json', request)
    started = time.monotonic()
    raw = dispatch(request)
    solver_seconds = time.monotonic()-started
    write_trajectory(folder/'trajectory.json.gz', raw)  # Retain before all gates.
    assert raw['converged'] and raw['accepted_steps'] == 16 and raw['rejected_steps'] == 0
    samples = raw['snapshots']; rows = [physical(s, job['panels']) for s in samples]
    assert len(rows) == len(target['rows']) == 17
    np.testing.assert_allclose([r['time'] for r in rows], [r['time'] for r in target['rows']], rtol=0, atol=1e-12)
    error = {}
    for key in ('CL', 'circulation', 'circulation_rate'):
        actual = np.array([r[key] for r in rows]); expected = np.array([r[key] for r in target['rows']])
        scale = np.asarray(target['scales'][key]); assert np.min(scale) > 0
        error[key] = float(np.max(abs(actual-expected)/scale))
    velocity_error = max(abs(a['velocity']-b['velocity'])/4.75 for a,b in zip(rows,target['rows']))
    position_error = max(abs(a['position']-b['displacement'])/.25 for a,b in zip(rows,target['rows']))
    acceleration_error = max(abs(a['acceleration']-b['acceleration']) for a,b in zip(rows,target['rows']))
    local = {key: max(abs(v) for r in rows for v in flatten(r[key])) for key in LOCAL}
    join_error = 0. if join is None else max(difference(rows[0][k],join[k]) for k in rows[0] if k not in ('order','residual'))
    first_error = None
    if job['kind'] == 'cold':
        reference_rate = np.array(target['rows'][1]['circulation_rate'])
        first_error = float(np.max(abs(np.array(rows[1]['circulation_rate'])-reference_rate)/abs(reference_rate)))
    chart_count = sum(charts(s['restart']) for s in samples)
    saved = checkpoint(raw)
    assert 'position_chart' in saved['state'] and 'position_chart' in saved['older']
    assert saved['context']['setup']['forcing'] == job['full_request']['time']['forcing']
    write(folder/'checkpoint.json', saved)
    gates = dict(waveforms=max(error.values()) <= LIMITS['waveform_fraction'],
        velocity=velocity_error <= LIMITS['velocity_fraction'], position=position_error <= LIMITS['position_fraction'],
        acceleration=acceleration_error < 1e-10,
        first_rate=first_error is None or first_error <= LIMITS['first_step_rate_fraction'],
        local_motion=max(local.values()) <= LIMITS['local_motion'],
        checkpoint_join=join_error <= LIMITS['join_scaled'],
        residual=max(r['residual'] for r in rows) < LIMITS['normalized_residual'],
        charts=chart_count > 0)
    verify(plan['source_sha256']); verify(dependencies)
    report = dict(passed=all(gates.values()), checks=gates, kind=job['kind'], panels=job['panels'],
        solver_seconds=solver_seconds, accepted_steps=16, rejected_steps=0,
        error_fractions=error, velocity_error_fraction=velocity_error, position_error_fraction=position_error,
        first_step_rate_error_fraction=first_error, maximum_join_scaled_difference=join_error,
        local_motion_maxima=local, position_charts_checked=chart_count,
        physical_rows=rows, native_ASWING_comparison=False,
        source_sha256=plan['source_sha256'], input_sha256=dependencies)
    write(folder/'report.json', report)
    print(json.dumps({k:v for k,v in report.items() if k not in ('physical_rows','source_sha256','input_sha256')}), flush=True)
    if not report['passed']:
        raise SystemExit(1)


def run_jobs(max_jobs):
    plan = read(BASE/'plan.json'); completed = 0
    for job in plan['jobs']:
        receipt_path = BASE/f'{job["id"]}-execution.json'
        if receipt_path.exists():
            receipt = read(receipt_path); assert receipt['exit_code'] == 0
            verify(receipt['output_sha256'])
            continue
        assert not (BASE/job['id']).exists(), 'Preserve and inspect interrupted evidence'
        print(json.dumps(dict(starting=job['id'])), flush=True)
        started = time.monotonic()
        with (BASE/f'{job["id"]}.log').open('x') as stream:
            try:
                child = subprocess.run([sys.executable, str(Path(__file__).resolve()), 'run', '--job', job['id']],
                    stdout=stream, stderr=subprocess.STDOUT, timeout=45)
                code = child.returncode
            except subprocess.TimeoutExpired:
                code = 124
        outputs = [p for p in (BASE/job['id']).glob('*') if p.is_file()] if (BASE/job['id']).exists() else []
        receipt = dict(exit_code=code, wall_seconds=time.monotonic()-started, output_sha256=pins(outputs))
        write(receipt_path, receipt)
        print(json.dumps(dict(job=job['id'], exit_code=code, seconds=receipt['wall_seconds'])), flush=True)
        if code:
            raise SystemExit(code)
        completed += 1
        if completed == max_jobs:
            break


def combine():
    plan = read(BASE/'plan.json'); verify(plan['source_sha256']); verify(plan['input_sha256'])
    reports = []
    for job in plan['jobs']:
        receipt_path = BASE/f'{job["id"]}-execution.json'; receipt = read(receipt_path)
        assert receipt['exit_code'] == 0; verify(receipt['output_sha256'])
        report = read(BASE/job['id']/'report.json'); assert report['passed']
        verify(report['source_sha256']); verify(report['input_sha256'])
        reports.append(report)
    result = dict(passed=True, checks_passed=len(reports), accepted_steps=sum(r['accepted_steps'] for r in reports),
        rejected_steps=0, cold_start_jobs=2, owned_continuation_jobs=2, legacy_replay_jobs=4,
        maximum_error_fractions={key:max(r['error_fractions'][key] for r in reports) for key in ('CL','circulation','circulation_rate')},
        maximum_local_motion={key:max(r['local_motion_maxima'][key] for r in reports) for key in LOCAL},
        maximum_join_scaled_difference=max(r['maximum_join_scaled_difference'] for r in reports),
        source_sha256=plan['source_sha256'], input_sha256=pins([BASE/'plan.json',
            *[BASE/j['id']/'report.json' for j in plan['jobs']], *[BASE/f'{j["id"]}-execution.json' for j in plan['jobs']]]),
        native_ASWING_comparison=False, new_native_passes=0, new_eight_cycle_study=False,
        new_time_refinement_claim=False)
    write(BASE/'summary.json', result)
    print(json.dumps({k:v for k,v in result.items() if k not in ('source_sha256','input_sha256')}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare','run','run-jobs','combine'))
    parser.add_argument('--job'); parser.add_argument('--max-jobs', type=int, default=1)
    args = parser.parse_args()
    if args.action == 'prepare': prepare()
    elif args.action == 'run': run(args.job)
    elif args.action == 'run-jobs': run_jobs(args.max_jobs)
    else: combine()
