"""Preserve stencil class methods in the lifetime spy; unchanged candidate."""
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts import probe_isae_ae3_assembly_storage as run
from scripts.probe_isae_ae2_cold_trace import read,write,pin

run.OUT=ROOT/'artifacts/isae/ae3-assembly-storage-r3-20261111'
run.run.OUT=run.run.run.OUT=run.run.run.supervisor.OUT=run.OUT
run.run.run.supervisor.__file__=__file__

if __name__=='__main__':
    if sys.argv[1]=='prepare':
        run.prepare()
        plan=read(run.OUT/'plan.json')
        plan['pins'] += [pin(Path(__file__)),pin(ROOT/'artifacts/isae/ae3-assembly-storage-r2-20261111/harness-failure.json')]
        plan['cases'][0]['selection']='1-True'
        # Each independent full-residual comparison gets its own bounded job.
        original=plan['cases'];cases=original[:2]
        for name,selection in [('rectangular-fixed','rectangular-fixed'),('flexible','flexible-free'),
            ('body-ground','wing-body-free-extra2'),('body-frozen','stepped-wing-body-fixed'),
            ('jet','jet-2-free'),('torsion','torsion-joint')]:
            cases.append(dict(name='matrix-'+name,kind='pytest',candidate=True,test='test_direct_geometry_matrix.py',
                selection='complete_geometry and '+selection,expected_exit=0))
        cases.extend(c for c in original if c['name'] in ('matrix-steady','matrix-fallback','newton-fallback') or c['kind']=='solve')
        plan['cases']=cases
        plan['prior_attempt']='R1 ground fixture error and R2 constructor-spy error/timeout retained; numerical candidate unchanged.'
        write(run.OUT/'plan.json',plan)
    elif sys.argv[1]=='launch':run.run.run.supervisor.launch(sys.argv[2])
    elif sys.argv[1]=='worker':run.worker(sys.argv[2])
    else:raise ValueError(sys.argv[1])
