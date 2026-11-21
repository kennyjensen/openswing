"""Repeat the unchanged candidate after correcting test ground clearance."""
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts import probe_isae_ae3_assembly_storage as run
from scripts.probe_isae_ae2_cold_trace import read,write,pin

run.OUT=ROOT/'artifacts/isae/ae3-assembly-storage-r2-20261111'
run.run.OUT=run.run.run.OUT=run.run.run.supervisor.OUT=run.OUT
run.run.run.supervisor.__file__=__file__

if __name__=='__main__':
    if sys.argv[1]=='prepare':
        run.prepare()
        plan=read(run.OUT/'plan.json')
        plan['pins'] += [pin(Path(__file__)),pin(ROOT/'artifacts/isae/ae3-assembly-storage-20261111/harness-failure.json')]
        plan['cases'][0]['selection']='1-True'
        plan['prior_attempt']='Ground-clearance fixture failures retained separately; candidate code unchanged.'
        write(run.OUT/'plan.json',plan)
    elif sys.argv[1]=='launch':run.run.run.supervisor.launch(sys.argv[2])
    elif sys.argv[1]=='worker':run.worker(sys.argv[2])
    else:raise ValueError(sys.argv[1])
