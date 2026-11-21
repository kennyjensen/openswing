"""Freeze low-speed controls for the completed AE-1 spacing diagnostics.

Use the known positive 1 m/s command, never the unidentified startup row.
The same four meshes and worker are retained; no sweep or parameter fit.
"""
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import resource
import signal
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.probe_isae_ae1_spacing import checked_plan,read,sha,save
from scripts import isae_suite_ae1 as adapter


def prepare(out):
    parent=ROOT/'artifacts/isae/ae1-spacing-current-20261110'
    old=checked_plan(parent)
    assert read(parent/'assessment.json')['physical_checks_passed']==116
    sweep=read(ROOT/'artifacts/isae/ae1-full-current-20261110/plan.json')
    pins=dict(old['pins']);jobs=[]
    for p in (parent/'plan.json',parent/'assessment.json',Path(__file__)):
        pins[str(p)]=sha(p)
    for entry in old['jobs']:
        nominal=entry['job']['nominal'];identifier=f'AE-1-a05-row002-m{nominal}-frozen'
        canonical_entry=next(e for e in sweep['entries'] if e['id']==identifier)
        folder=Path(canonical_entry['folder']);canonical=read(folder/'job.json')
        adapter.verify_reference_sources(ROOT,canonical)
        assert canonical['condition']['speed']==1. and canonical['condition']['alpha']==5.
        for name in ('job.json','strict-result.json','receipt.json'):
            pins[str(folder/name)]=sha(folder/name)
        job=deepcopy(canonical)
        job['id']=f"AE-1-spacing-{entry['kind']}-m{nominal}-u01"
        job['panels']=deepcopy(entry['job']['panels'])
        job['reference_scope']='Unscored known-1m/s control for node-placement diagnostics; no primary acceptance votes.'
        assert {k for k in job if job[k]!=canonical[k]}=={'id','panels','reference_scope'}
        conditions=deepcopy(entry['job']['condition']);conditions['speed']=1.
        assert job['condition']==conditions
        jobs.append(dict(job=job,kind=entry['kind'],material_y=entry['material_y'],parent_folder=str(folder)))
    out.mkdir(parents=True)
    save(out/'plan.json',dict(observed_utc=datetime.now(timezone.utc).isoformat(),purpose=__doc__,
        pins=pins,jobs=jobs,primary_votes_added=0,limits=old['limits'],
        qualifications=old['qualifications']+['Known 1m/s controls separate baseline shape changes from the 1-to-17m/s response; startup remains unidentified.']))
    checked_plan(out)
    print('Prepared four known-1m/s controls; unchanged spacing and numerical worker.')


if __name__=='__main__':
    resource.setrlimit(resource.RLIMIT_AS,(512*1024**2,)*2)
    resource.setrlimit(resource.RLIMIT_CPU,(15,)*2);signal.alarm(25)
    prepare(Path(sys.argv[1]).resolve())
