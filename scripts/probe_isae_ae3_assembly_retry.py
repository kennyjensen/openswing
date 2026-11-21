"""One unchanged bounded retry; preserve the original terminal evidence."""
from copy import deepcopy
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts import probe_isae_ae3_assembly_storage as run
from scripts.probe_isae_ae2_cold_trace import read,write,pin

BASE=ROOT/'artifacts/isae/ae3-assembly-storage-r3-20261111'
name=sys.argv[2]
run.OUT=BASE/'retries'/name
run.run.OUT=run.run.run.OUT=run.run.run.supervisor.OUT=run.OUT
run.run.run.supervisor.__file__=__file__

if __name__=='__main__':
    if sys.argv[1]=='prepare':
        assert not run.OUT.exists()
        plan=deepcopy(read(BASE/'plan.json'))
        previous=BASE/'cases'/name/'terminal.json';terminal=read(previous)
        assert terminal['process_reaped'] and terminal['returncode']!=0
        for p in plan['pins']:assert pin(p['path'])==p,p['path']
        plan['cases']=[next(c for c in plan['cases'] if c['name']==name)]
        plan['pins'] += [pin(Path(__file__)),pin(BASE/'plan.json'),pin(previous)]
        plan['retry']='Identical equations, test selection, tolerances and resource limits; original attempt retained.'
        write(run.OUT/'plan.json',plan)
        print('Prepared one unchanged bounded retry.')
    elif sys.argv[1]=='launch':run.run.run.supervisor.launch(name)
    elif sys.argv[1]=='worker':run.worker(name)
    else:raise ValueError(sys.argv[1])
