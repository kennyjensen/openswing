#!/usr/bin/env python3
"""Compare two further original ST-5 static exports with the source operator.

Preparation pins each separately decoded archive, unchanged model, generated
verifier, and kernel. Execution makes three cold solves per case and one fresh
restoration per solve. Mesh/printed-output failures stay separate from physical
solver failures. There are no experimental data or fitted parameters here.
"""
import argparse
import difflib
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
CASES = ('20lb_90_10', '30lb_90_10')
TEMPLATE = ROOT/'scripts/verify-isae-st5-archived-output.py'
POLICY = dict(beam_interpolation='drela-segspl-v1', structural_operator='drela-steady-section-v1')
THREADS = {key: '1' for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS')}


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')


def pin(path):
    path = Path(path).resolve()
    data = path.read_bytes()
    return dict(path=str(path), bytes=len(data), sha256=hashlib.sha256(data).hexdigest())


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def generate(source, target):
    original = TEMPLATE.read_text()
    text, edits = original, []

    def replace(label, old, new):
        nonlocal text
        require(text.count(old) == 1, 'Expected one source anchor: '+label)
        text = text.replace(old, new)
        edits.append(dict(label=label, before=old, after=new))

    replace('repository root', 'ROOT = Path(__file__).resolve().parents[1]', f'ROOT = Path({str(ROOT)!r})')
    replace('case target', "TARGET = ROOT / 'docs/validation/isae-st5-reference-target.json'", f'TARGET = Path({str(target)!r})')
    replace('unchanged case model', "SOURCE = ROOT / 'examples/isae-st5-static-20lb_80_20.asw'", f'SOURCE = Path({str(source)!r})')
    replace('external target path', "target=str(TARGET.relative_to(ROOT))", 'target=str(TARGET)')
    replace('explicit interpolation', '    from openswing.asw import parse_asw',
            '    from openswing.asw import parse_asw as original_parse\n'
            '    def parse_asw(source):\n'
            f'        return original_parse(source, beam_interpolation={POLICY["beam_interpolation"]!r})')
    replace('real browser bridge request', '    from openswing.bridge import dispatch',
            '    from openswing.bridge import dispatch as bridge_dispatch\n'
            '    def dispatch(request, progress=None):\n'
            f'        return bridge_dispatch(dict(request, condition=None, gravity=None, numerics={POLICY!r}), progress=progress)')
    replace('same restored structural operator', '    from openswing.network import StaticNetwork',
            '    from openswing.source_discrete import SourceSectionNetwork as StaticNetwork')
    replace('plan equation identity', "    write(stage/'plan.json', plan)",
            f"    plan['numerics'] = {POLICY!r}\n    write(stage/'plan.json', plan)")
    replace('following archived row endpoint echo',
            "                display = [0.]*7 if midpoint is None else [float(beam.value('chord', midpoint)), 0.,\n"
            "                    float(beam.value('Cm', midpoint)), 0.,",
            "                following = None if midpoint is None else coordinate(block['rows'][k+1])\n"
            "                def echo(prop):\n"
            "                    return float((beam.value(prop, t)+beam.value(prop, following))/2)\n"
            "                display = [0.]*7 if midpoint is None else [echo('chord'), 0., echo('Cm'), 0.,")
    replace('echo interpretation in plan',
            "display_rule='chord/cm use the midpoint of successive archived t rows, including zero-width display intervals; final seven display columns are dummy zeros. f_reac scalar signed weight is diagnostic only.'",
            "display_rule='chord/cm use the average endpoint values at successive archived rows, retaining duplicate rows and final dummy zeros. Properties are continuous here; no resultant trace convention is inferred. This display hypothesis has prior independent archive support, not recovered exporter source. f_reac retains the parameter-midpoint signed-weight diagnostic and is unresolved.'")
    replace('stop before refining a physically failed state', "        write(out/'comparison.json', packet)",
            "        write(out/'comparison.json', packet)\n"
            "        assert passed, 'Physical numerical gate failed; state retained, no finer solve.'")
    replace('summary equation identity', "    write(stage/'summary.json', summary)",
            f"    summary['numerics'] = {POLICY!r}\n    write(stage/'summary.json', summary)")
    compile(text, '<st5-load-case-verifier>', 'exec')
    diff = ''.join(difflib.unified_diff(original.splitlines(True), text.splitlines(True),
                                      fromfile=str(TEMPLATE), tofile='generated-verifier.py'))
    return text, edits, diff


def prepare(stage, targets):
    require(not stage.exists(), 'Refusing to replace existing stage')
    stage.mkdir(parents=True)
    decoder_report = read(targets/'report.json')
    require(decoder_report['checks_passed'] == decoder_report['checks_total'], 'Decoder audit failed')
    inputs = [Path(__file__), TEMPLATE, ROOT/'scripts/extract-isae-st5-load-cases.py', targets/'report.json']
    inputs.extend(ROOT/'docs/validation'/name for name in
                  ('isae-st5-spline-diagnostic.json', 'isae-st5-spline-20261025-evidence.zip'))
    for p in decoder_report['pins']:
        require(pin(p['path']) == p, 'Changed decoder dependency: '+p['path'])
        inputs.append(Path(p['path']))
    inputs.extend(sorted((ROOT/'openswing').glob('*.py')))
    cases = []
    for name in CASES:
        source = ROOT/f'examples/isae-st5-static-{name}.asw'
        target_source = targets/f'JW_1_{name}-target.json'
        target = read(target_source)
        require(target['source_pins'][0]['sha256'] == pin(source)['sha256'], 'Literal model mismatch: '+name)
        require([b['row_count'] for b in target['beams']] == [44, 36], 'Unexpected archive row counts')
        require(len(target['columns']) == 28 and len(target['beams']) == 2, 'Unexpected archive layout')
        require(target['checks_passed'] == target['checks_total'], 'Source decoder checks failed')
        for p in target['source_pins']:
            require(pin(p['path']) == p, 'Changed decoder source: '+p['path'])
            inputs.append(Path(p['path']))
        folder = stage/name
        folder.mkdir()
        target_copy = folder/'target.json'
        target_copy.write_bytes(target_source.read_bytes())
        text, edits, diff = generate(source, target_copy)
        (folder/'verifier.py').write_text(text)
        write(folder/'patches.json', edits)
        (folder/'verifier.diff').write_text(diff)
        command = [sys.executable, str(folder/'verifier.py'), 'prepare', '--stage', str(folder)]
        preparation = subprocess.run(command, capture_output=True, text=True, check=False, timeout=30)
        (folder/'prepare.log').write_text(preparation.stdout+preparation.stderr)
        write(folder/'prepare-receipt.json', dict(exit_code=preparation.returncode, reaped=True,
                                                production_imports=0, physics_calls=0))
        require(preparation.returncode == 0, 'Case plan preparation failed: '+name)
        case_plan = read(folder/'plan.json')
        require([sum(m['intervals_by_beam'].values()) for m in case_plan['meshes']] == [70, 140, 280],
                'Unexpected archive/refined station counts')
        inputs.extend([source, target_source, target_copy, folder/'verifier.py', folder/'plan.json',
                       folder/'patches.json', folder/'verifier.diff'])
        cases.append(dict(name=name, plan=str(folder/'plan.json'), cold_solves=3, fresh_residuals=3))
    unique = sorted(set(p.resolve() for p in inputs))
    plan = dict(status='PREPARED_NOT_RUN', cases=cases, numerics=POLICY,
                acceptance='Reproduce the original tested ASWING output; experimental agreement optional.',
                scope='Two additional rigid-joint load cases. Keep their actual rear-wing self-weight and all signed Dmg inputs.',
                cold_solves=6, fresh_residuals=6, concurrency=1, retries=0,
                child_cap_seconds=120, termination_grace_seconds=5, thread_environment=THREADS,
                source_pins=[pin(p) for p in unique],
                reference_rule='All 80 rows and 27 output fields accounted for. Strict printed precision and mesh sensitivity reported separately.',
                historical_grid='Exact anchors plus printed node centers; unrounded historical grid not recovered.',
                failure_policy='Stop on first failed process or physical gate; retain partial results. Reference/mesh differences are findings.')
    require(all(pin(p['path']) == p for p in plan['source_pins']), 'Inputs changed while preparing')
    write(stage/'plan.json', plan)
    print(json.dumps(dict(status=plan['status'], plan=pin(stage/'plan.json'), cases=list(CASES))), flush=True)


def run(stage):
    plan = read(stage/'plan.json')
    require(not (stage/'execution.json').exists(), 'Execution already attempted')
    require(all(pin(p['path']) == p for p in plan['source_pins']), 'Prepared input changed')
    execution = dict(status='RUNNING', pid=os.getpid(), children=[], plan=pin(stage/'plan.json'))
    write(stage/'execution.json', execution)
    env = dict(os.environ, **plan['thread_environment'])
    start = time.monotonic()
    try:
        for case in plan['cases']:
            folder = stage/case['name']
            command = [sys.executable, str(folder/'verifier.py'), 'run', '--stage', str(folder)]
            began = time.monotonic()
            with (folder/'run.log').open('x') as log:
                child = subprocess.Popen(command, env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
                receipt = dict(case=case['name'], pid=child.pid, state='RUNNING', command=command)
                execution['children'].append(receipt)
                write(stage/'execution.json', execution)
                print('BEGIN '+case['name'], flush=True)
                timed_out = False
                try:
                    code = child.wait(timeout=plan['child_cap_seconds'])
                except subprocess.TimeoutExpired:
                    timed_out = True
                    os.killpg(child.pid, signal.SIGTERM)
                    try:
                        code = child.wait(timeout=plan['termination_grace_seconds'])
                    except subprocess.TimeoutExpired:
                        os.killpg(child.pid, signal.SIGKILL)
                        code = child.wait()
                except BaseException:
                    os.killpg(child.pid, signal.SIGKILL)
                    child.wait()
                    receipt.update(state='INTERRUPTED', exit_code=child.returncode, reaped=True)
                    raise
            receipt.update(state='TERMINAL', exit_code=code, reaped=True, timed_out=timed_out,
                           seconds=time.monotonic()-began, log=pin(folder/'run.log'))
            write(stage/'execution.json', execution)
            require(code == 0 and not timed_out, 'Case execution failed: '+case['name'])
            require(read(folder/'summary.json')['all_numerical_gates_pass'], 'Physical gates failed')
            require(all(pin(p['path']) == p for p in plan['source_pins']), 'Input changed during execution')
            print('DONE '+case['name'], flush=True)
        summary = dict(status='PASS_PHYSICAL_CHECKS_REFERENCE_COMPARISON_COMPLETE', full_goal_complete=False,
                       cold_solves=6, fresh_residuals=6, numerics=POLICY, plan=pin(stage/'plan.json'),
                       cases={c['name']: read(stage/c['name']/'summary.json') for c in plan['cases']})
        write(stage/'summary.json', summary)
        execution['status'] = 'PASS'
    except BaseException as exc:
        execution.update(status='FAILURE_RETAINED', error=f'{type(exc).__name__}: {exc}')
        raise
    finally:
        execution.update(seconds=time.monotonic()-start,
                         all_children_reaped=all(c.get('reaped', False) for c in execution['children']),
                         input_pins_unchanged=all(pin(p['path']) == p for p in plan['source_pins']))
        write(stage/'execution.json', execution)
    print(json.dumps(dict(status=execution['status'], summary=pin(stage/'summary.json'))), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare', 'run'])
    parser.add_argument('--stage', required=True, type=Path)
    parser.add_argument('--targets', type=Path)
    args = parser.parse_args()
    if args.action == 'prepare':
        if args.targets is None:
            parser.error('--targets is required to prepare')
        prepare(args.stage.resolve(), args.targets.resolve())
    else:
        run(args.stage.resolve())
