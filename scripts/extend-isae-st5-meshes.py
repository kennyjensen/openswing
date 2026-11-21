"""Extend the four completed ST-5 snapshots without repeating retained solves.

Each worker does one cold solve and one fresh saved-state residual. The frozen
full-row verifier supplies every recovery expression and original acceptance
gate; only execution bookkeeping changes. Numerical jobs are serial and bounded.
"""
import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import resource
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
PARENT = ROOT/'artifacts/isae/st1-st6-current-20261103/structure'
BASE = ROOT/'artifacts/isae/st5-mesh-extension-20261103'
CASES = ('20lb_80_20', '20lb_90_10', '30lb_90_10', '30lb_80_20')


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def stable(pins):
    for name, expected in pins.items():
        assert sha(ROOT/name) == expected, f'Changed input: {name}'


def pin(path):
    path = Path(path).resolve()
    return str(path.relative_to(ROOT)), sha(path)


def prepare():
    assert not (BASE/'plan.json').exists(), 'Do not overwrite a prepared study.'
    parent = read(PARENT/'assessment.json')
    rows, pins = {}, dict([pin(Path(__file__)), pin(PARENT/'plan.json'), pin(PARENT/'assessment.json')])
    for case in CASES:
        record = parent['jobs'][f'ST5-{case.upper()}-static-three-grids']
        assert record['numerical_pass'] and record['completed_grid_count'] == 3
        folder = Path(record['artifact_directory'])
        original = read(folder/'plan.json')
        stable(original['kernel_pins'])
        pins.update(original['kernel_pins'])
        assert sha(folder/'verifier.py') == original['script_sha256']
        for name in ('plan.json', 'verifier.py', 'summary.json', 'adapter-job.json'):
            pins.update([pin(folder/name)])
        job = read(folder/'adapter-job.json')
        for item in job['source_pins']:
            assert sha(item['path']) == item['sha256']
            pins.update([pin(item['path'])])
        for level in range(3):
            for name in ('comparison.json', 'result.json', 'fresh-fields.npz'):
                path = folder/f'level{level}'/name
                expected = next(item['sha256'] for item in record['artifact_files'] if item['path'] == str(path))
                assert sha(path) == expected
                pins.update([pin(path)])
        last = original['meshes'][-1]
        assert last['level'] == 2 and sum(last['intervals_by_beam'].values()) == 280
        nodes = {key: list(value['nodes']) for key, value in last['panels']['beams'].items()}
        meshes = []
        for level in (3, 4):
            nodes = {key: sorted(ts+[(a+b)/2 for a,b in zip(ts[:-1],ts[1:])]) for key,ts in nodes.items()}
            counts = {key:len(ts)-1 for key,ts in nodes.items()}
            meshes.append(dict(level=level, intervals_by_beam=counts,
                panels=dict(default=max(counts.values()), beams={key:dict(nodes=ts) for key,ts in nodes.items()})))
        assert [sum(m['intervals_by_beam'].values()) for m in meshes] == [560, 1120]
        rows[case] = dict(original_folder=str(folder.relative_to(ROOT)), meshes=meshes,
            original_required_pair=[1,2], extension_pairs=[[2,3],[3,4]],
            numerical_gates=original['numerical_gates'])
    BASE.mkdir(parents=True, exist_ok=True)
    study = dict(cases=rows, pins=pins, expected_cold_solves=8, expected_fresh_residuals=8,
        workers=1, blas_threads=1, child_timeout_seconds=180, child_address_space_bytes=512*1024**2,
        acceptance='All original 80 rows, 27 exported fields and 14 structural mesh measures retained. Original half-last-place and 0.1% mesh limits unchanged.',
        scope='A separately declared two-level convergence extension; original failed pairs and archived comparison counts remain unchanged.',
        physics_or_default_changes=False)
    write(BASE/'plan.json', study)
    print(json.dumps(dict(prepared=True,cases=list(rows),new_intervals=[560,1120],cold_solves=8)))


def prepare_child(study, case, level):
    row = study['cases'][case]
    old = ROOT/row['original_folder']
    stage = BASE/case/f'run-level{level}'
    assert not stage.exists(), 'Retain previous attempts; do not overwrite.'
    earlier = [old/f'level{i}/comparison.json' for i in range(3)]
    if level == 4:
        receipt = read(BASE/case/'run-level3/execution.json')
        assert receipt['exit_code'] == 0 and not receipt['timed_out']
        assert receipt['physical_checks_pass']
        stable(receipt['output_sha256'])
        earlier.append(BASE/case/'run-level3/level3/comparison.json')
    assert all(read(p)['numerical_gates_pass'] for p in earlier)
    old_text = (old/'verifier.py').read_text()
    assert old_text.count('    records = []') == 1
    text = old_text.replace('    records = []',
        '    records = [json.loads(Path(p).read_text()) for p in '+repr([str(p) for p in earlier])+']')
    assert text.count('cold_solves=3, fresh_residuals=3,') == 2
    text = text.replace('cold_solves=3, fresh_residuals=3,', 'cold_solves=1, fresh_residuals=1,')
    assert text.count("    write(stage/'summary.json', summary)") == 1
    text = text.replace("    write(stage/'summary.json', summary)",
        "    summary['retained_levels'] = "+repr(list(range(level)))+"\n"
        "    summary['original_required_pair'] = [1, 2]\n"
        "    summary['extension_pair'] = "+repr([level-1,level])+"\n"
        "    summary['original_acceptance_unchanged'] = True\n"
        "    write(stage/'summary.json', summary)")
    compile(text, '<st5-one-grid-extension>', 'exec')
    stage.mkdir(parents=True)
    (stage/'verifier.py').write_text(text)
    plan = deepcopy(read(old/'plan.json'))
    plan.update(script_sha256=sha(stage/'verifier.py'), cold_solves=1, fresh_residuals=1,
                meshes=[deepcopy(next(m for m in row['meshes'] if m['level']==level))],
                original_plan_sha256=sha(old/'plan.json'), extension_of=str(old.relative_to(ROOT)),
                original_required_pair=[1,2], extension_pair=[level-1,level])
    write(stage/'plan.json', plan)
    inputs = dict([pin(p) for p in earlier]+[pin(stage/'plan.json'),pin(stage/'verifier.py')])
    write(stage/'input-pins.json', inputs)
    return stage, inputs


def run(case, level):
    study = read(BASE/'plan.json')
    stable(study['pins'])
    stage, inputs = prepare_child(study, case, level)
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
    env.update({key:'1' for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS')})
    def limit():
        value = study['child_address_space_bytes']
        resource.setrlimit(resource.RLIMIT_AS, (value,value))
    start = time.monotonic()
    with (stage/'run.log').open('w') as log:
        process = subprocess.Popen([sys.executable,str(stage/'verifier.py'),'run','--stage',str(stage)],
            cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True,preexec_fn=limit)
        write(stage/'process.json',dict(pid=process.pid,case=case,level=level,started_unix=time.time()))
        timed_out = False
        try:
            code = process.wait(timeout=study['child_timeout_seconds'])
        except subprocess.TimeoutExpired:
            timed_out = True
            os.killpg(process.pid,signal.SIGTERM)
            try:
                code = process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid,signal.SIGKILL)
                code = process.wait()
    outputs = {**dict([pin(p) for p in stage.rglob('*') if p.is_file()])}
    physical = False
    if code == 0:
        summary = read(stage/'summary.json')
        physical = summary['all_numerical_gates_pass']
        assert summary['cold_solves'] == summary['fresh_residuals'] == 1
        assert summary['original_required_pair'] == [1,2]
        assert summary['extension_pair'] == [level-1,level]
        assert len(summary['meshes']) == level+1
    stable(study['pins']); stable(inputs)
    receipt = dict(case=case,level=level,exit_code=code,timed_out=timed_out,process_reaped=True,
        elapsed_seconds=time.monotonic()-start,peak_child_rss_KiB=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,
        physical_checks_pass=physical,output_sha256=outputs,input_sha256=inputs)
    write(stage/'execution.json',receipt)
    print(json.dumps({k:v for k,v in receipt.items() if not k.endswith('_sha256')}),flush=True)
    assert code == 0 and physical, 'Failed job retained; do not proceed to a dependent grid.'


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare','run'))
    parser.add_argument('--case', choices=CASES)
    parser.add_argument('--level', type=int, choices=(3,4))
    args = parser.parse_args()
    if args.action == 'prepare':
        prepare()
    else:
        assert args.case is not None and args.level is not None
        run(args.case,args.level)
