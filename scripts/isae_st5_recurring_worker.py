"""One capped ST-5 solve, or a saved-field audit, in a fresh process."""
import importlib.util
import os
from pathlib import Path
import resource
import signal
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/'scripts'))
import isae_suite_st5_mechanics as adapter


def solve(folder,level):
    job = adapter.read(folder/'job.json'); entry = job['reference_input']
    path = ROOT/entry['verifier']; adapter.require(adapter.sha(path) == entry['verifier_sha256'],'verifier changed')
    spec = importlib.util.spec_from_file_location('st5_frozen_recovery',path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    module.ROOT = ROOT; module.SOURCE = ROOT/entry['source']; module.TARGET = ROOT/entry['target']
    plan = adapter.read(ROOT/entry['reference_plan'])
    plan.update(kernel_pins=adapter.read(folder/'kernel-pins.json'), script_sha256=adapter.sha(path),
        target=str(module.TARGET), source=entry['source'], meshes=[job['meshes'][level]],
        retained_comparisons=[str(folder/f'run-{i}/level{i}/comparison.json') for i in range(level)])
    adapter.save(folder/f'run-{level}/plan.json',plan)
    began=time.monotonic();cpu=time.process_time();module.run(folder/f'run-{level}')
    adapter.save(folder/f'run-{level}/timing.json',dict(wall_seconds=time.monotonic()-began,
        cpu_seconds=time.process_time()-cpu,peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss))


def audit(folder):
    import numpy as np
    job=adapter.read(folder/'job.json')
    for i in range(5):
        out=folder/f'run-{i}/level{i}';packet=adapter.read(out/'comparison.json');result=adapter.read(out/'result.json')
        adapter.require(result['converged'] and result['structural_only'] and not result['strips'] and
            result['structural_operator']=='drela-steady-section-v1' and
            result['structural_elements']==sum(job['meshes'][i]['intervals_by_beam'].values()) and
            result['equilibrium_state']['identity']['model_sha256']==job['reference_input']['source_sha256'],'wrong physical state')
        with np.load(out/'fresh-fields.npz') as fields:
            adapter.require(float(np.max(abs(fields['residual'])))==packet['checks']['fresh_residual'],'saved residual changed')
            adapter.require(fields['r'].shape==(result['structural_nodes'],3),'saved node fields missing')
            for row in packet['rows']:
                adapter.require(np.array_equal(fields['r'][row['node']],row['position']),'position differs from saved state')
        checks=packet['checks']
        adapter.require(checks['stored_residual']==result['residual'] and
            checks['force_balance']==max(map(abs,result['force_balance'])) and
            checks['moment_balance']==max(map(abs,result['moment_balance'])),'physical check detached from result')
        if 'roller' in job['configuration']:
            joint=adapter.read(out/'joint-mechanics.json')
            adapter.require(joint['type']==2 and joint['force_max']==joint['couple_balance']==0 and
                joint['rotation_max']==checks['joint_rotation'],'roller law changed')
        adapter.require(adapter.physical(job,packet),'physical requirement failed')
    adapter.save(folder/'audit.json',dict(states=5,saved_residuals=5,saved_position_fields=5,passed=True))


if __name__=='__main__':
    adapter.require(all(os.environ.get(k)=='1' for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS')),'one BLAS thread required')
    resource.setrlimit(resource.RLIMIT_AS,(512*1024**2,)*2)
    resource.setrlimit(resource.RLIMIT_CPU,(15,)*2);signal.alarm(25)
    action,folder=sys.argv[1],Path(sys.argv[2])
    if action=='solve':solve(folder,int(sys.argv[3]))
    elif action=='audit':audit(folder)
    else:raise ValueError('Unknown ST5 worker action')
