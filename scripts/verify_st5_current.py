"""Refresh one original ST-5 rigid snapshot, one bounded mesh per invocation.

Reuses the existing full-row recovery and source-discrete setup. This pilot
does not replace the family ledger or treat a coarse-grid match as convergence.
"""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import resource
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


helper = load_module(ROOT/'scripts/verify-isae-st5-load-cases.py', 'st5_generator')
read, write, pin = helper.read, helper.write, helper.pin


def unchanged(pins):
    for item in pins:
        current = pin(item['path'])
        assert Path(current['path']) == Path(item['path']).resolve()
        assert all(current[k] == item[k] for k in ('bytes', 'sha256')), item['path']


def prepare(out):
    assert not out.exists(), 'Keep all previous attempts.'
    source = ROOT/'examples/isae-st5-static-20lb_80_20.asw'
    target_path = ROOT/'docs/validation/isae-st5-reference-target.json'
    target = read(target_path)
    unchanged(target['source_pins'])
    catalog_path = ROOT/'docs/validation/aswing-authoritative-sources.json'
    catalog = read(catalog_path)
    references = []
    for item in catalog['files']:
        if item['id'] not in ('isae-part-3', 'drela-steady'):
            continue
        for key, digest in [('local_pdf', 'sha256'), ('local_text', 'text_sha256')]:
            p = pin(ROOT/item[key])
            assert p['sha256'] == item[digest]
            references.append(Path(p['path']))
    assert len(references) >= 2
    text, edits, diff = helper.generate(source, target_path)

    def replace(old, new):
        nonlocal text
        assert text.count(old) == 1, old
        text = text.replace(old, new)
        edits.append(dict(before=old, after=new))

    replace('    records = []',
            "    records = [json.loads(Path(p).read_text()) for p in plan['retained_comparisons']]")
    replace("all_fine_mesh_gates_pass=all(v['passes'] for v in changes[-1]['measures'].values()),",
            "all_fine_mesh_gates_pass=(all(v['passes'] for v in changes[-1]['measures'].values()) if changes else None),")
    assert text.count('cold_solves=3, fresh_residuals=3,') == 2
    text = text.replace('cold_solves=3, fresh_residuals=3,', 'cold_solves=1, fresh_residuals=1,')
    compile(text, '<st5-current-single-mesh>', 'exec')
    out.mkdir(parents=True)
    (out/'verifier.py').write_text(text)
    write(out/'patches.json', edits)
    (out/'source-operator.diff').write_text(diff)
    verifier = load_module(out/'verifier.py', 'st5_current_generated')
    verifier.prepare(out)
    common = read(out/'plan.json')
    plans = []
    for mesh in common['meshes'][:2]:
        level = mesh['level']
        folder = out/f'run-{level}'
        folder.mkdir()
        plan = deepcopy(common)
        plan.update(meshes=[mesh], retained_comparisons=[
            str(out/f'run-{j}/level{j}/comparison.json') for j in range(level)])
        write(folder/'plan.json', plan)
        plans.append(folder/'plan.json')
    paths = [Path(__file__), ROOT/'scripts/verify-isae-st5-load-cases.py', helper.TEMPLATE,
             source, target_path, catalog_path, *references, out/'verifier.py',
             out/'plan.json', *plans, out/'patches.json', out/'source-operator.diff',
             *sorted((ROOT/'openswing').glob('*.py'))]
    write(out/'study.json', dict(observed_utc=datetime.now(timezone.utc).isoformat(),
        source_pins=target['source_pins'], pins=[pin(p) for p in paths],
        limits=dict(address_space_bytes=512*1024**2, cpu_seconds=15, wall_seconds=25),
        comparison=dict(relative=0.05, absolute='original printed half-last-place',
            purpose='Supplementary current pilot; original strict counts also retained.',
            primary_votes_added=0),
        scope='All 80 original rows and all 27 output fields retained; 14 computed structural fields reported separately.',
        meshes=[m['intervals_by_beam'] for m in common['meshes'][:2]],
        reference='Part III §4.5 pp40–44. Rigid type1 input; no substitution for modified in-plane link.'))
    print('Prepared two independent serial jobs; no numerical solve performed.')


def worker(out, level):
    assert all(os.environ.get(k) == '1' for k in helper.THREADS)
    study = read(out/'study.json')
    limits = study['limits']
    resource.setrlimit(resource.RLIMIT_AS, (limits['address_space_bytes'],)*2)
    resource.setrlimit(resource.RLIMIT_CPU, (limits['cpu_seconds'],)*2)
    signal.alarm(limits['wall_seconds'])
    unchanged(study['pins']); unchanged(study['source_pins'])
    load_module(out/'verifier.py', 'st5_single_mesh_worker').run(out/f'run-{level}')
    unchanged(study['pins']); unchanged(study['source_pins'])


def run(out, level):
    study = read(out/'study.json')
    unchanged(study['pins']); unchanged(study['source_pins'])
    folder = out/f'run-{level}'
    assert not (folder/'execution.json').exists() and not (folder/'run.log').exists()
    retained = []
    for j in range(level):
        receipt = read(out/f'run-{j}/execution.json')
        assert receipt['exit_code'] == 0 and receipt['reaped'] and not receipt['timed_out']
        unchanged(receipt['outputs'])
        retained.append(pin(out/f'run-{j}/level{j}/comparison.json'))
    command = [sys.executable, str(Path(__file__).resolve()), 'worker', '--output', str(out), '--level', str(level)]
    started = time.monotonic()
    receipt = dict(observed_utc=datetime.now(timezone.utc).isoformat(), command=command,
                   retained=retained, timed_out=False)
    with (folder/'run.log').open('x') as log:
        child = subprocess.Popen(command, cwd=ROOT, env=dict(os.environ, **helper.THREADS),
                                 stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        receipt.update(pid=child.pid, reaped=False)
        write(folder/'execution.json', receipt)
        try:
            child.wait(timeout=30)
        except subprocess.TimeoutExpired:
            receipt['timed_out'] = True
            os.killpg(child.pid, signal.SIGKILL)
            child.wait()
        except BaseException:
            os.killpg(child.pid, signal.SIGKILL)
            child.wait()
            raise
        finally:
            receipt.update(exit_code=child.returncode, reaped=child.returncode is not None,
                elapsed_seconds=time.monotonic()-started,
                peak_child_rss_kib=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,
                outputs=[pin(p) for p in sorted(folder.rglob('*'))
                         if p.is_file() and p.name != 'execution.json'])
            write(folder/'execution.json', receipt)
    unchanged(study['pins']); unchanged(study['source_pins']); unchanged(retained)
    print(json.dumps({k:v for k,v in receipt.items() if k not in ('outputs','retained','command')}))
    assert child.returncode == 0 and not receipt['timed_out'], 'Retained failed attempt; no retry.'


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare', 'run', 'worker'])
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--level', type=int, choices=[0,1], default=0)
    args = parser.parse_args()
    out = args.output.resolve()
    if args.action == 'prepare': prepare(out)
    elif args.action == 'run': run(out, args.level)
    else: worker(out, args.level)
