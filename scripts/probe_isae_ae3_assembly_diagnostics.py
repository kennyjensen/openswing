"""Bounded original-code failure check and unchanged joint-column retry."""
from copy import deepcopy
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts import probe_isae_ae3_assembly_storage as run
from scripts.probe_isae_ae2_cold_trace import read,write,pin

BASE=ROOT/'artifacts/isae/ae3-assembly-storage-r3-20261111'
run.OUT=BASE/'diagnostics'
run.run.OUT=run.run.run.OUT=run.run.run.supervisor.OUT=run.OUT
run.run.run.supervisor.__file__=__file__

if __name__=='__main__':
    if sys.argv[1]=='prepare':
        assert not run.OUT.exists()
        plan=deepcopy(read(BASE/'plan.json'))
        for p in plan['pins']:assert pin(p['path'])==p,p['path']
        original=deepcopy(next(c for c in plan['cases'] if c['name']=='matrix-fallback'))
        original.update(name='fallback-original',candidate=False,selection='unavailable_composition and constructor',expected_exit=1)
        retry=deepcopy(next(c for c in plan['cases'] if c['name']=='matrix-torsion'))
        retry['name']='torsion-candidate'
        plan['cases']=[original,retry]
        plan['pins'] += [pin(Path(__file__)),pin(BASE/'plan.json')]
        plan['environment']={'PYTEST_DISABLE_PLUGIN_AUTOLOAD':'1','PYTEST_ADDOPTS':'--tb=short'}
        plan['purpose']='Check whether startup equilibrium failure also occurs in the unchanged kernel; rerun the identical joint-column comparison after timeouts. No test/equation/gate changes.'
        write(run.OUT/'plan.json',plan)
        print('Prepared original-code comparison and one unchanged bounded joint test.')
    elif sys.argv[1]=='launch':run.run.run.supervisor.launch(sys.argv[2])
    elif sys.argv[1]=='worker':run.worker(sys.argv[2])
    else:raise ValueError(sys.argv[1])
