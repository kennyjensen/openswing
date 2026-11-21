#!/usr/bin/env python3
"""Bounded cold-start optimization check against retained original FFWT states.

Reuses the original reference verifier's fresh physical checks. Adds full saved
output parity, continuation diagnostics and measured startup-work comparisons.
"""
import argparse
from copy import deepcopy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('ffwt_reference', ROOT/'scripts/verify-isae-ffwt-reference.py')
reference = importlib.util.module_from_spec(spec); spec.loader.exec_module(reference)
read, write, pin, require = reference.read, reference.write, reference.pin, reference.require


def prepare(stage, baseline):
    require(not stage.exists(), 'Use a new stage.')
    stage.mkdir(parents=True)
    old = read(baseline/'plan.json'); prior = read(baseline/'summary.json')
    require(prior['status'] == 'PASS_PHYSICAL_CHECKS', 'Baseline physical checks did not pass.')
    inputs = [Path(__file__), ROOT/'scripts/verify-isae-ffwt-reference.py',
              baseline/'plan.json', baseline/'summary.json', ROOT/'examples/isae-ffwt-flare10.asw']
    cases = []
    for c in old['cases']:
        name = c['name']; folder = stage/'cases'/name
        for file in ('request.json', 'input-project.json'):
            write(folder/file, read(baseline/'cases'/name/file)); inputs.append(folder/file)
        for file in ('request.json', 'result.json', 'report.json', 'progress.jsonl'):
            inputs.append(baseline/'cases'/name/file)
        events = [json.loads(line) for line in (baseline/'cases'/name/'progress.jsonl').read_text().splitlines()]
        targets = [r['event'][1] for r in events if r['event'][0] == 'static_load' and r['event'][1] > 0]
        first = min(range(len(targets)), key=targets.__getitem__)
        require(all(a > b for a, b in zip(targets[:first], targets[1:first+1])), 'Baseline retry targets do not decrease.')
        require(all(a < b for a, b in zip(targets[first:], targets[first+1:])), 'Baseline accepted targets do not increase.')
        require(len(targets)-first == read(baseline/'cases'/name/'result.json')['continuation_steps'],
                'Baseline progress does not identify accepted stages.')
        cases.append(dict(name=name, request=str(folder/'request.json'), baseline=str(baseline/'cases'/name),
            baseline_initial_rejections=first,
            baseline_count_method='Inferred from decreasing/increasing target order and the saved accepted-stage count.'))
    inputs += sorted((ROOT/'openswing').glob('*.py'))
    inputs += [ROOT/'tests/test_initial_load_predictor.py']
    plan = dict(status='PREPARED', cases=cases, reference=old['reference'], gates=old['gates'],
        child_cap_seconds=180, thread_environment=reference.THREADS, cold_solves=2, fresh_residuals=2,
        parity=dict(absolute=2e-8, relative=2e-8, exclusions=['evaluations', 'continuation_steps'],
            exclusion_reason='Execution counters; final physical fields and original metadata remain compared.'),
        pins=[pin(p) for p in inputs],
        kernel_pins={p.name: pin(p)['sha256'] for p in sorted((ROOT/'openswing').glob('*.py'))})
    write(stage/'plan.json', plan); print(json.dumps(pin(stage/'plan.json')), flush=True)


def compare(expected, actual, parity):
    stats = dict(numeric=0, leaves=0, max_absolute=0., max_fraction=0., worst=None)
    def visit(a, b, path):
        if path in parity['exclusions']:
            return
        if isinstance(a, (int, float)) and not isinstance(a, bool):
            require(isinstance(b, (int, float)) and not isinstance(b, bool), 'Numeric type: '+path)
            delta = abs(b-a); limit = parity['absolute']+parity['relative']*abs(a)
            stats['numeric'] += 1; stats['leaves'] += 1
            stats['max_absolute'] = max(stats['max_absolute'], delta)
            if delta/limit > stats['max_fraction']:
                stats.update(max_fraction=delta/limit, worst=path)
            require(delta <= limit, 'Physical parity: '+path)
        elif isinstance(a, list):
            require(isinstance(b, list) and len(a) == len(b), 'Array shape: '+path)
            for i, (x, y) in enumerate(zip(a, b)):
                visit(x, y, path+'['+str(i)+']')
        elif isinstance(a, dict):
            require(isinstance(b, dict), 'Object type: '+path)
            for k, v in a.items():
                require(k in b, 'Missing key: '+path+'.'+k)
                visit(v, b[k], (path+'.' if path else '')+k)
        else:
            require(a == b, 'Metadata parity: '+path); stats['leaves'] += 1
    visit(expected, actual, '')
    return stats


def worker(stage, name):
    plan = read(stage/'plan.json'); folder = stage/'cases'/name
    case = next(c for c in plan['cases'] if c['name'] == name)
    baseline = Path(case['baseline'])
    require(read(folder/'request.json') == read(baseline/'request.json'), 'Original request changed.')
    sys.path.insert(0, str(ROOT))
    import numpy as np
    import openswing.structured_static as structured
    original = structured.equilibrate
    def observed(net, *args, **kwargs):
        started = time.monotonic()
        try:
            return original(net, *args, **kwargs)
        finally:
            write(folder/'continuation.json', dict(seconds=time.monotonic()-started,
                evaluations=net.nfev, rank=getattr(net, 'structured_rank_check', None),
                prediction=getattr(net, 'equilibrium_diagnostics', {}),
                iterations=getattr(net, 'structured_iterations', []),
                attempts=getattr(net, 'continuation_diagnostics', [])))
    structured.equilibrate = observed
    try:
        reference.worker(stage, name)
    finally:
        structured.equilibrate = original
    prior, result = read(baseline/'result.json'), read(folder/'result.json')
    report = read(folder/'report.json'); old_report = read(baseline/'report.json')
    diagnostics = read(folder/'continuation.json')
    checks = []
    def check(label, ok, **detail):
        checks.append(dict(name=label, passed=bool(ok), **detail))
    parity = compare(prior, result, plan['parity'])
    check('full_saved_physical_parity', parity['max_fraction'] <= 1, **parity)
    check('fresh_internal_target', report['fresh_residual'] <= 1e-12, residual=report['fresh_residual'])
    prediction = result['equilibrium_initialization']['cold_start_prediction']
    check('zero_load_prediction_used', prediction['applied'] and prediction['evaluations'] == 1,
          prediction=prediction)
    attempts = diagnostics['attempts']; first = next(i for i, r in enumerate(attempts) if r['accepted'])
    old_rejections = case['baseline_initial_rejections']
    check('fewer_initial_rejections', first < old_rejections, before=old_rejections, after=first)
    rotations = [r['accepted_load_rotation_increment_rad'] for r in attempts if r['accepted']]
    # Total travel over a converged stage sets the following increment. The
    # existing hard 5-degree guard applies to individual Newton trials, below.
    stage_rotation_maximum = max(rotations)
    for r in attempts:
        if not r['accepted']:
            check('rejected_chart_rollback', r['starting_charts'] == r['restored_charts'])
    for r in diagnostics['iterations']:
        if 'accepted_rotation_increment_rad' in r:
            check('accepted_newton_rotation_guard', r['accepted_rotation_increment_rad'] <= np.deg2rad(5)*(1+1e-12))
    check('lower_total_dispatch_time', report['solve_seconds'] < old_report['solve_seconds'],
          before=old_report['solve_seconds'], after=report['solve_seconds'])
    check('fewer_physical_residual_evaluations', result['evaluations'] < prior['evaluations'],
          before=prior['evaluations'], after=result['evaluations'])
    check('unchanged_inputs', reference.unchanged(plan))
    performance = dict(status='PASS' if all(c['passed'] for c in checks) else 'FAIL', case=name,
        checks=checks, parity=parity, baseline_seconds=old_report['solve_seconds'],
        candidate_seconds=report['solve_seconds'], speedup=old_report['solve_seconds']/report['solve_seconds'],
        initial_rejections_before=old_rejections, initial_rejections_after=first,
        maximum_completed_stage_rotation_rad=stage_rotation_maximum,
        physical_checks=report['checks_passed'], physical_checks_total=report['checks_total'])
    write(folder/'performance.json', performance)
    require(performance['status'] == 'PASS', 'Startup acceptance failed; do not launch the finer case.')


def run(stage):
    plan = read(stage/'plan.json'); require(reference.unchanged(plan), 'Inputs changed.')
    require(not (stage/'execution.json').exists(), 'No automatic retries.')
    execution = dict(status='RUNNING', children=[]); write(stage/'execution.json', execution)
    summaries = {}
    for case in plan['cases']:
        name = case['name']; folder = stage/'cases'/name
        with (folder/'run.log').open('w') as log:
            child = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), 'worker', str(stage), '--case', name],
                cwd=ROOT, env={**os.environ, **reference.THREADS}, stdout=log, stderr=subprocess.STDOUT)
            row = dict(case=name, pid=child.pid, state='RUNNING'); execution['children'].append(row)
            write(stage/'execution.json', execution)
            try:
                code = child.wait(timeout=plan['child_cap_seconds'])
            except subprocess.TimeoutExpired:
                child.terminate()
                try:
                    code = child.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    child.kill(); code = child.wait()
                row['timed_out'] = True
            row.update(state='TERMINAL', exit_code=code, reaped=True)
            write(stage/'execution.json', execution)
        if code:
            execution.update(status='FAILED', all_children_reaped=True); write(stage/'execution.json', execution)
            launched = [r['case'] for r in execution['children']]
            write(stage/'summary.json', dict(status='FAILED', execution=execution,
                launched=launched, unlaunched=[c['name'] for c in plan['cases'] if c['name'] not in launched],
                known_dispatch_attempts=sum((stage/'cases'/n/'progress.jsonl').exists() for n in launched),
                known_completed_fresh_residuals=sum((stage/'cases'/n/'fresh-fields.npz').exists() for n in launched),
                cases={n: read(stage/'cases'/n/'report.json') for n in launched
                       if (stage/'cases'/n/'report.json').exists()}, retries=0))
            raise RuntimeError('Worker failed: '+name)
        summaries[name] = dict(physical=read(folder/'report.json'), performance=read(folder/'performance.json'))
        print(json.dumps(summaries[name]['performance']), flush=True)
    pins_match = reference.unchanged(plan)
    execution.update(status='PASS' if pins_match else 'FAILED_INPUT_PINS', all_children_reaped=True)
    write(stage/'execution.json', execution); require(pins_match, 'Final input pins changed.')
    write(stage/'summary.json', dict(status='PASS_FFWT_STARTUP_PHYSICAL_PARITY_AND_PERFORMANCE',
        cases=summaries, operations=dict(cold_solves=2, fresh_residuals=2), plan=pin(stage/'plan.json'),
        reference_match=False, scope='Equivalent faster startup; original reference discrepancies remain.'))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('action', choices=('prepare', 'run', 'worker'))
    parser.add_argument('stage', type=Path); parser.add_argument('--baseline', type=Path); parser.add_argument('--case')
    args = parser.parse_args()
    if args.action == 'prepare':
        prepare(args.stage.resolve(), args.baseline.resolve())
    elif args.action == 'run':
        run(args.stage.resolve())
    else:
        try:
            worker(args.stage.resolve(), args.case)
        except Exception:
            write(args.stage/'cases'/args.case/'failure.json', dict(traceback=traceback.format_exc()))
            raise
