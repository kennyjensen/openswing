"""Check a closed-form self-wake sampling identity on the saved SA-11 fields."""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import shutil

import numpy as np

ROOT=Path(__file__).resolve().parents[1]
PRIOR=ROOT/'artifacts/isae/sa11-drag-closure-20261108'
read=lambda p:json.loads(p.read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    assert all(os.environ.get(k)=='1' for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'))
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True,type=Path)
    out=parser.parse_args().output.resolve();assert not out.exists(),out
    old=read(PRIOR/'analysis.json');checked=read(PRIOR/'verification.json')
    assert checked['analysis_sha256']==sha(PRIOR/'analysis.json')
    pins=dict(old['source_pins'])
    for p in [Path(__file__),PRIOR/'analysis.json',PRIOR/'verification.json']:
        pins[str(p.relative_to(ROOT))]=sha(p)
    for name,digest in pins.items():assert sha(ROOT/name)==digest,name
    spec=importlib.util.spec_from_file_location('closure',ROOT/'scripts/audit-sa11-drag-closure.py')
    closure=importlib.util.module_from_spec(spec);spec.loader.exec_module(closure)
    out.mkdir(parents=True);shutil.copyfile(__file__,out/'driver-used.py')
    (out/'plan.json').write_text(json.dumps(dict(source_pins=pins,alphas=[0,1,5],
        scope='Same saved whole-new Gamma on native and whole-beam receivers. Zero new solves; no source omission.',
        identity='Own finite-origin CD = rho Gamma^2 kappa [1/lambda - 1/(1-lambda)] / (4 pi q S); kappa = (dx/beta)/|P delta r|.',
        controls='Zero at lambda=1/2 or dx=0; sign reverses under lambda -> 1-lambda at fixed kappa.',
        qualifications='Requires a straight bound interval and a collinear interior receiver; both are checked. Own bound is already excluded; own trailing wake remains. This is not a replacement force law.'),indent=2)+'\n')
    beta=math.sqrt(1-(240/340.21)**2);rho=1.2256;scale=.5*rho*240**2*.9329
    errors=dict(collinearity=0.,own_term=0.,main_total=0.,partition=0.)
    rows=[]
    for case in old['cases']:
        path=ROOT/case['source_report'];report=read(path)
        with np.load(path.parent/'geometry.npz') as f:g={k:f[k].copy() for k in f.files}
        with np.load(path.parent/'whole-new.npz') as f:d={k:f[k].copy() for k in f.files}
        with np.load((ROOT/report['source_report']).parent/'native-fields.npz') as f:native=f['RV'].copy()
        delta=g['b']-g['a'];transformed=delta/np.array([beta,1.,1.])
        kappa=transformed[:,0]/np.linalg.norm(transformed,axis=1)
        gamma=d['gamma'];beam=d['beam'];main_indices=np.flatnonzero(beam==1)
        records={};pairs=[]
        for label,points in [('native',native),('whole',g['hv'])]:
            fraction=np.sum((points-g['a'])*delta,axis=1)/np.sum(delta*delta,axis=1)
            offset=points-(g['a']+fraction[:,None]*delta)
            errors['collinearity']=max(errors['collinearity'],float(np.max(np.linalg.norm(offset,axis=1))))
            assert np.all((fraction>0)&(fraction<1))
            formula=rho*gamma**2*kappa*(1/fraction-1/(1-fraction))/(4*math.pi*scale)
            bound,half,tail=closure.matrices(g,points,beta)
            pair=rho*gamma[:,None]*gamma[None,:]*np.cross(bound+tail,delta[:,None,:])[:,:,0]/scale
            errors['own_term']=max(errors['own_term'],float(np.max(abs(np.diag(pair)-formula))))
            pairs.append(pair)
            records[label]=dict(fraction=fraction.tolist(),own_finite_origin_CD=formula.tolist())
        change=pairs[1]-pairs[0];local=change[np.ix_(main_indices,main_indices)]
        own=float(np.trace(local));adjacent=float(np.diag(local,1).sum()+np.diag(local,-1).sum())
        others=float(local.sum())-own-adjacent
        expected=case['replays']['whole-new']['finite_part_by_beam_pair']['1-1']-case['replays']['native-new']['finite_part_by_beam_pair']['1-1']
        errors['main_total']=max(errors['main_total'],abs(float(local.sum())-expected))
        errors['partition']=max(errors['partition'],abs(own+adjacent+others-expected))
        # Geometric selection, not a threshold chosen by force error.
        inner=main_indices[np.argsort(abs(g['rm'][main_indices,1]),kind='stable')[:2]]
        inner_records=[dict(panel_index=int(i),whole_t=float(d['t'][i]),
            endpoints=[g['a'][i].tolist(),g['b'][i].tolist()],
            native_fraction=records['native']['fraction'][i],whole_fraction=records['whole']['fraction'][i],
            native_own_CD=records['native']['own_finite_origin_CD'][i],
            whole_own_CD=records['whole']['own_finite_origin_CD'][i],
            difference=float(change[i,i])) for i in inner]
        rows.append(dict(alpha=case['alpha'],same_circulation=True,
            main_pair_change=float(local.sum()),own_wake_change=own,adjacent_change=adjacent,
            other_change=others,innermost_main_intervals=inner_records,all_intervals=records))
    # Algebraic controls use the same factor but do not involve solved fields.
    law=lambda gamma,kappa,f:rho*gamma**2*kappa*(1/f-1/(1-f))/(4*math.pi*scale)
    assert law(7.,.6,.5)==0 and law(7.,0.,.25)==0
    assert abs(law(7.,.6,.25)+law(7.,.6,.75))<1e-16
    assert errors['collinearity']<1e-12 and errors['own_term']<2e-12,errors
    assert errors['main_total']<2e-12 and errors['partition']<2e-12,errors
    for name,digest in pins.items():assert sha(ROOT/name)==digest,name
    result=dict(observed_utc=datetime.now(timezone.utc).isoformat(),source_pins=pins,cases=rows,
        errors=errors,source_pins_verified=len(pins),physical_solves=0,accepted_loads=0,primary_passes_added=0,
        interpretation='Existing own trailing-wake sampling explains large terms; adjacent strips partly cancel them. Do not delete own wake or adopt a receiver rule to force near/far equality.')
    (out/'analysis.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps(dict(errors=errors,cases=[{k:v for k,v in c.items() if k!='all_intervals'} for c in rows])),flush=True)


if __name__=='__main__':main()
