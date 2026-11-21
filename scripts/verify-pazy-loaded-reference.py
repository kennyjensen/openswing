"""Independent primary Pazy rod references for self-weight and large bench loads."""
from pathlib import Path
import hashlib
import json
import time
import numpy as np
from pazy_primary_conm2 import ROOT,source,sha
from pazy_loaded import GRAVITY,observables
from pazy_loaded_reference import solve


def main():
    scripts={p.name:sha(p) for p in [Path(__file__),ROOT/'scripts/pazy_loaded_reference.py',ROOT/'scripts/pazy_loaded.py',
        ROOT/'scripts/pazy_primary_conm2.py',ROOT/'scripts/pazy_primary.py']}
    cases=[]
    for skin,kind,maximum in [(0,'bending',3.5),(0,'torsion',3.25),(1,'bending',3.),(1,'torsion',2.8)]:
        for mass in [0.,2.,maximum]:
            cases.append(dict(analysis='static',skin=skin,kind=kind,mass_kg=mass,orientation='horizontal',gravity=GRAVITY))
    cases.extend(dict(analysis='static',skin=skin,kind='bending',mass_kg=0.,orientation='upright',gravity=GRAVITY) for skin in [0,1])
    cache=ROOT/'.reference/pazy-loaded-reference';cache.mkdir(exist_ok=True)
    report=ROOT/'docs/validation/pazy-loaded-reference.json';out=dict(status='RUNNING',scripts=scripts,requested=2*len(cases),runs=[])
    for spec in cases:
        data=source(spec['skin']);s=data['coordinates'][:,1]
        stations=np.unique(np.concatenate([np.linspace(a,b,9) for a,b in zip(s[:-1],s[1:])]))
        for projected in [False,True]:
            identity=dict(specification=spec,projected=projected,scripts=scripts,sources=data['sources'])
            key=hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest();path=cache/(key+'.json')
            if path.exists():run=json.loads(path.read_text());assert run['identity']==identity
            else:
                start=time.perf_counter();run=solve(spec,projected,stations);run['seconds']=time.perf_counter()-start
                run['identity']=identity;run['observables']=observables(run['positions'][-1],run['rotations'][-1])
                path.write_text(json.dumps(run,indent=2)+'\n')
            out['runs'].append(dict(specification=spec,projected=projected,cache=path.relative_to(ROOT).as_posix(),sha256=sha(path),
                observables=run['observables'],boundary_error_Nm=run['tip_boundary_error_Nm']))
            report.write_text(json.dumps(out,indent=2)+'\n')
            print(len(out['runs']),out['requested'],spec,'projected',projected,run['observables'],flush=True)
    out['status']='PASS_INDEPENDENT_STATIC_REFERENCES';report.write_text(json.dumps(out,indent=2)+'\n')


if __name__=='__main__':main()
