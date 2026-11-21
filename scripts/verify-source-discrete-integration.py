#!/usr/bin/env python3
"""Replay the original ST3/ST5 full-output comparisons with explicit policies.

Prepare writes separately pinned verifier copies; it never imports production
physics. Run executes those copies once, retaining their original grids,
reference rows, precision checks and numerical/mesh gates. Historical scripts
and reports remain unchanged. Reference differences are not execution failures.
"""
import argparse
import difflib
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STAGE = Path('/tmp/openswing-source-discrete-integration-20261026')
INTERPOLATION = 'drela-segspl-v1'
OPERATOR = 'drela-steady-zero-offset-v1'
CASES = {
    'st3': 'scripts/verify-isae-st3-archived-output.py',
    'st5': 'scripts/verify-isae-st5-archived-output.py',
}


def pin(path):
    path = Path(path)
    value = path.read_bytes()
    return dict(path=str(path.resolve()), bytes=len(value), sha256=hashlib.sha256(value).hexdigest())


def write(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def metadata(case):
    return dict(
        study='Explicit source-discrete integration replay; archived ASWING outputs are the comparison target.',
        case=case, beam_interpolation=INTERPOLATION, structural_operator=OPERATOR,
        wrapper=pin(__file__), historical_verifier=pin(ROOT/CASES[case]),
        model_tables_changed=False, historical_verifier_changed=False,
        section_and_distributed_cg_offsets='Zero; original rotating point-weight pylons remain present.',
        source_equations='Absolute Eq48; Eq54 endpoint K and stiffness averages; symmetric endpoint distributed gravity.',
        interpretations='EA is averaged before inversion; ds=ds0 is unloaded material arc. Historical executable conventions remain unproven.',
        state_scope='Explicit interpolation/operator identities; no dynamic launch; no app-default change.',
        output_scope='Endpoint comparison channels are retained. Inherited midpoint elements/structure/sensor reports do not define the source-discrete constitutive law.',
        display_scope='Original comparison display formulas remain unchanged; separate endpoint-average/projected display hypotheses are not substituted.',
        reference_scope='No widened precision/mesh gates, fitted properties, historical-mesh reconstruction claim, or full-reference-pass claim.')


def generate(case):
    original = (ROOT/CASES[case]).read_text()
    text = original
    patches = []

    def replace(label, old, new):
        nonlocal text
        require(text.count(old) == 1, f'{case}: expected one source anchor for {label}')
        text = text.replace(old, new)
        patches.append(dict(label=label, before=old, after=new))

    replace('absolute repository root', 'ROOT = Path(__file__).resolve().parents[1]',
            f'ROOT = Path({str(ROOT)!r})')
    replace('historical helper import path', 'sys.path.insert(0, str(ROOT))',
            "sys.path.insert(0, str(ROOT))\nsys.path.insert(0, str(ROOT/'scripts'))\n"
            +f'SOURCE_POLICY = {metadata(case)!r}')
    replace('explicit beam interpolation', '    from openswing.asw import parse_asw',
            '    from openswing.asw import parse_asw as _parse_asw\n'
            '    def parse_asw(source):\n'
            f'        return _parse_asw(source, beam_interpolation={INTERPOLATION!r})')
    replace('explicit static source operator', '    from openswing.bridge import dispatch',
            '    from openswing.source_discrete import solve_source_discrete\n'
            '    def dispatch(request, progress=None):\n'
            "        assert set(request) == {'action', 'mode', 'source', 'panels'}\n"
            "        assert request['action'] == 'solve' and request['mode'] == 'structural'\n"
            "        model = parse_asw(request['source'])\n"
            "        result = solve_source_discrete(model, request['panels'], progress=progress,\n"
            '            allow_signed_point_weights=True, allow_signed_distributed_weights=True)\n'
            "        state = result['equilibrium_state']\n"
            f"        assert state['identity']['beam_interpolation'] == {INTERPOLATION!r}\n"
            f"        assert state['identity']['structural_operator'] == {OPERATOR!r}\n"
            "        assert 'launch' not in state and len(state['circulation']) == 0\n"
            f"        assert result['structural_operator'] == {OPERATOR!r}\n"
            # These are the structural-bridge presentation fields expected by
            # the historical verifier. The source API itself forbids airflow.
            "        result.update(structural_only=True, strips=[], source_policy=SOURCE_POLICY)\n"
            '        return result')
    replace('matching fresh-restore operator', '    from openswing.network import StaticNetwork',
            '    from openswing.source_discrete import SourceDiscreteNetwork as StaticNetwork')
    replace('plan policy description', "    write(stage/'plan.json', plan)",
            "    plan['source_policy'] = SOURCE_POLICY\n    write(stage/'plan.json', plan)")
    replace('summary policy description', "    write(stage/'summary.json', summary)",
            "    summary['source_policy'] = SOURCE_POLICY\n    write(stage/'summary.json', summary)")
    if case == 'st3':
        replace('retain existing fresh residual operands',
                "        pa, pb = network.geometry(data['r'], data['Q'])[:2]",
                "        pa, pb, ra, rb, *_ = network.geometry(data['r'], data['Q'])\n"
                "        np.savez_compressed(out/'fresh-fields.npz', residual=residual, r=data['r'], Q=data['Q'],\n"
                "            N=data['N'], M=data['M'], rj=network.rj, a=network.a, b=network.b,\n"
                '            pa=pa, pb=pb, ra=ra, rb=rb, R0a=network.R0a, R0b=network.R0b,\n'
                "            element_forces=data['element_forces'], element_moments=data['element_moments'])")
    compile(text, f'<generated-{case}>', 'exec')
    diff = ''.join(difflib.unified_diff(original.splitlines(True), text.splitlines(True),
                    fromfile=CASES[case], tofile=f'{case}/verifier.py'))
    return text, patches, diff


def prepare(stage):
    require(not stage.exists(), f'Refusing to overwrite an existing stage: {stage}')
    stage.mkdir(parents=True)
    case_plans = {}
    all_pins = [pin(__file__)]
    all_pins.extend(pin(p) for p in sorted((ROOT/'openswing').glob('*.py')))
    for case in CASES:
        folder = stage/case
        folder.mkdir()
        text, patches, diff = generate(case)
        (folder/'verifier.py').write_text(text)
        (folder/'wrapper.diff').write_text(diff)
        write(folder/'patches.json', patches)
        # Preparation executes stdlib-only plan generation, never run().
        completed = subprocess.run([sys.executable, str(folder/'verifier.py'), 'prepare', '--stage', str(folder)],
                                   text=True, capture_output=True, check=False)
        (folder/'prepare.log').write_text(completed.stdout+completed.stderr)
        write(folder/'prepare-receipt.json', dict(returncode=completed.returncode, reaped=True,
                                                 physics_solves=0, production_imports=0))
        require(completed.returncode == 0, f'{case} preparation failed; retained {folder}/prepare.log')
        p = json.loads((folder/'plan.json').read_text())
        case_plans[case] = p
        all_pins.extend(pin(folder/n) for n in ['verifier.py', 'wrapper.diff', 'patches.json', 'plan.json'])
        all_pins.extend([pin(ROOT/CASES[case]), pin(ROOT/p['source']),
                         pin(ROOT/f'docs/validation/isae-{case}-reference-target.json')])
    all_pins.append(pin(ROOT/'scripts/isae_st3_static_reference.py'))
    require([m['intervals'] for m in case_plans['st3']['meshes']] == [44, 88, 176], 'ST3 grids changed')
    require([sum(m['intervals_by_beam'].values()) for m in case_plans['st5']['meshes']] == [70, 140, 280], 'ST5 grids changed')
    unique = {p['path']: p for p in all_pins}
    require(all(pin(p['path']) == p for p in unique.values()), 'Inputs changed during preparation')
    plan = dict(status='PREPARED_SOURCE_DISCRETE_INTEGRATION_NOT_YET_RUN',
        source_policies=dict(beam_interpolation=INTERPOLATION, structural_operator=OPERATOR),
        cases={k: dict(plan=pin(stage/k/'plan.json'), cold_solves=3, fresh_restore_residuals=3,
                      family_cap_seconds=120, source_policy=v['source_policy']) for k, v in case_plans.items()},
        total_cold_solves=6, total_fresh_restore_residuals=6,
        counts_scope='Fresh restore residuals are separate from the solver internal residual evaluations recorded by each result.',
        concurrency=1, thread_environment={k:'1' for k in ['OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS']},
        automatic_retries=0, failure_policy='Stop after first failed family process; retain all partial outputs.',
        pins=list(unique.values()), reference_claim='Comparison only; strict precision and mesh failures stay explicit.',
        operations_at_prepare=dict(cold_solves=0, fresh_residuals=0, production_imports=0))
    write(stage/'plan.json', plan)
    print(json.dumps(dict(prepared=pin(stage/'plan.json'), cases=list(case_plans), pinned_files=len(unique))))


def run(stage):
    plan = json.loads((stage/'plan.json').read_text())
    require(not (stage/'execution.json').exists(), 'Execution already attempted; no automatic retry')
    for case in CASES:
        require(not (stage/case/'run.log').exists(), f'{case} was already launched')
        require(not list((stage/case).glob('n[0-9]*')) and not list((stage/case).glob('level[0-9]*')),
                f'{case} contains prior scientific outputs')
    require(all(pin(p['path']) == p for p in plan['pins']), 'Frozen input pin mismatch')
    env = dict(os.environ, **plan['thread_environment'])
    lifecycle = dict(status='RUNNING', pid=os.getpid(), plan=pin(stage/'plan.json'), cases={}, retries=0)
    write(stage/'execution.json', lifecycle)
    started = time.monotonic()
    try:
        for case in CASES:
            folder = stage/case
            began = time.monotonic()
            print(f'BEGIN {case}: three cold solves and three fresh restorations', flush=True)
            with (folder/'run.log').open('x') as log:
                child = subprocess.Popen([sys.executable, str(folder/'verifier.py'), 'run', '--stage', str(folder)],
                                         env=env, stdout=log, stderr=subprocess.STDOUT)
                receipt = dict(pid=child.pid, state='RUNNING', command=[sys.executable,str(folder/'verifier.py'),'run','--stage',str(folder)])
                lifecycle['cases'][case] = receipt
                write(folder/'process.json', receipt)
                write(stage/'execution.json', lifecycle)
                timed_out = False
                try:
                    code = child.wait(timeout=plan['cases'][case]['family_cap_seconds'])
                except subprocess.TimeoutExpired:
                    timed_out = True
                    child.kill()
                    code = child.wait()
                except BaseException:
                    child.kill()
                    child.wait()
                    receipt.update(state='INTERRUPTED', exit_code=child.returncode, reaped=True,
                                   timed_out=False, seconds=time.monotonic()-began)
                    write(folder/'process.json', receipt)
                    raise
            receipt.update(state='TERMINAL', exit_code=code, reaped=True, timed_out=timed_out,
                           seconds=time.monotonic()-began, log=pin(folder/'run.log'))
            if (folder/'summary.json').exists():
                receipt['summary'] = pin(folder/'summary.json')
            write(folder/'process.json', receipt)
            write(stage/'execution.json', lifecycle)
            require(code == 0 and not timed_out, f'{case} terminated unsuccessfully; no retry')
            require(all(pin(p['path']) == p for p in plan['pins']), 'Input changed during execution')
            print(f'DONE {case}: process exit0, results retained', flush=True)
        summaries = {case: json.loads((stage/case/'summary.json').read_text()) for case in CASES}
        require(all(v['cold_solves'] == 3 for v in summaries.values()), 'Wrong cold solve counts')
        require(summaries['st3']['fresh_residual_evaluations'] == summaries['st5']['fresh_residuals'] == 3,
                'Wrong fresh restore residual counts')
        summary = dict(status='INTEGRATION_COMPARISONS_COMPLETE', goal_complete=False,
            plan=pin(stage/'plan.json'), source_policies=plan['source_policies'],
            cold_solves=6, fresh_restore_residuals=6, seconds=time.monotonic()-started,
            all_numerical_gates_pass=all(v['all_numerical_gates_pass'] for v in summaries.values()),
            cases={case: dict(summary=pin(stage/case/'summary.json'),
                             numerical_gates_pass=v['all_numerical_gates_pass'],
                             fine_mesh_gates_pass=v['all_fine_mesh_gates_pass'],
                             reference_status=v['status']) for case, v in summaries.items()},
            reference_claim='No full ASWING reference pass claimed; inspect unchanged per-case precision/mesh results.',
            inherited_channels='Midpoint elements/structure/sensors are supplemental; endpoint comparisons and source_discrete_elements identify the relevant policy.')
        write(stage/'summary.json', summary)
        require(summary['all_numerical_gates_pass'], 'A physical numerical gate failed; full outputs retained')
        lifecycle['status'] = 'TERMINAL_COMPLETE'
    except BaseException as error:
        lifecycle.update(status='TERMINAL_FAILED_RETAINED', error=f'{type(error).__name__}: {error}')
        raise
    finally:
        lifecycle['seconds'] = time.monotonic()-started
        lifecycle['input_pins_unchanged'] = all(pin(p['path']) == p for p in plan['pins'])
        lifecycle['all_launched_children_reaped'] = all(v.get('reaped',False) for v in lifecycle['cases'].values())
        write(stage/'execution.json', lifecycle)
    print(json.dumps(dict(summary=pin(stage/'summary.json'), execution=pin(stage/'execution.json'))))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare', 'run'])
    parser.add_argument('--stage', type=Path, default=DEFAULT_STAGE)
    args = parser.parse_args()
    (prepare if args.action == 'prepare' else run)(args.stage.resolve())
