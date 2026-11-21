"""Saved-field decomposition of the SA-11 sampling comparison; no solves."""
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

import numpy as np

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from openswing.factored_influence import FactoredInfluence
from openswing.frozen_influence import lifting_geometry
SPEC=importlib.util.spec_from_file_location('sampling',ROOT/'scripts/verify-sa11-drag-sampling.py')
DRIVER=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(DRIVER)
BASE=ROOT/'artifacts/isae/sa11-drag-sampling-r1-20261108'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
read=lambda p:json.loads(p.read_text())


def main():
    plan=read(BASE/'plan.json');DRIVER.stable(plan)
    assert sha(BASE/'driver-used.py')==plan['driver_sha256']
    states={}; rows=[]; pins={}
    for case in plan['reused']+plan['jobs']:
        path=ROOT/case['path'] if 'path' in case else BASE/case['id']/'openswing.json'
        value=read(path);r=value['result'] if case.get('wrapper') else value
        if 'path' not in case:
            assert sha(path)==read(path.parent/'receipt.json')['result_sha256']
        pins[str(path.relative_to(ROOT))]=sha(path)
        model,meshes=DRIVER.mesh(plan,case);g=lifting_geometry(meshes,np.array([1.,0.,0.]))
        assert len(r['strips'])==len(g['a'])
        assert np.max(abs(np.array([s['t'] for s in r['strips']])-meshes[0].tm))<1e-12
        assert np.max(abs(np.array([s['position'] for s in r['strips']])-g['rm']))<1e-12
        assert np.max(abs(np.array([s['velocity_position'] for s in r['strips']])-g['hv']))<1e-12
        assert r['converged'] and r['residual']<1e-8
        assert not any(s['stalled'] for s in r['strips'])
        assert max(s['normal_mach'] for s in r['strips'])<1
        assert abs(r['CD']-r['CDi_near']-r['CDp'])<1e-12
        gamma=np.array([s['circulation'] for s in r['strips']]);v=np.array([s['relative_velocity'] for s in r['strips']])
        direction=np.array([np.cos(np.deg2rad(1.)),0.,np.sin(np.deg2rad(1.))])
        span=meshes[0].frames[...,1];speed=240.;area=model.reference[0,0]
        def near(gamma,velocity,span=span,ds=g['ds'],area=area):
            return float(np.sum(2*gamma[:,None]*np.cross(velocity,span)*ds[:,None],axis=0)@direction/(speed**2*area))
        assert abs(near(gamma,v)-r['CDi_near'])<1e-12
        states[case['id']]=dict(model=model,g=g,gamma=gamma,velocity=v,span=span,result=r,near=near)
        rows.append(dict(id=case['id'],sampling=case['sampling'],variant=case['variant'],strips=len(gamma),
            coefficients={k:r[k] for k in ['CL','CD','CDi','CDi_near','CDp']},
            CD_error_percent=100*(r['CD']/.0110238-1),maximum_normal_mach=max(s['normal_mach'] for s in r['strips']),
            residual=r['residual']))
    assert len(rows)==6
    decompositions=[]
    for variant in ['original','combined']:
        b=states['whole_beam-'+variant];c=states['native-'+variant]
        assert all(np.array_equal(b['g'][key],c['g'][key]) for key in ['a','b','ds'])
        assert np.max(abs(b['span']-c['span']))<1e-12
        pg=np.diag([1/np.sqrt(1-(240/340.21)**2),1.,1.])
        matrices=[]
        for state in [b,c]:
            g=state['g'];n=len(g['a'])
            influence=FactoredInfluence(g['hv'],g['a'],g['b'],[1.,0.,0.],pg,exclude_bound=np.eye(n,dtype=bool))
            matrix=influence.matrix();matrices.append(matrix)
            reconstructed=speed*direction+np.einsum('ijk,j->ik',matrix,state['gamma'])
            assert np.max(abs(reconstructed-state['velocity']))<2e-9
        delta=matrices[1]-matrices[0]
        gamma=c['gamma'];v_at_b=speed*direction+np.einsum('ijk,j->ik',matrices[0],gamma)
        receiver=c['near'](gamma,c['velocity'])-b['near'](gamma,v_at_b)
        resolving=b['near'](gamma,v_at_b)-b['result']['CDi_near']
        diagonal=delta[np.arange(len(gamma)),np.arange(len(gamma))]*gamma[:,None]
        self_wake=c['near'](gamma,diagonal)
        mutual=c['near'](gamma,np.einsum('ijk,j->ik',delta,gamma)-diagonal)
        actual=c['result']['CDi_near']-b['result']['CDi_near']
        assert abs(receiver+resolving-actual)<1e-12
        assert abs(self_wake+mutual-receiver)<1e-12
        decompositions.append(dict(variant=variant,near_CD_change=actual,receiver_change_at_fixed_gamma=receiver,
            circulation_resolve_change=resolving,self_wake_receiver_change=self_wake,mutual_receiver_change=mutual,
            receiver_share_percent=100*receiver/actual,self_wake_share_of_receiver_percent=100*self_wake/receiver,
            max_receiver_displacement_m=float(np.max(np.linalg.norm(c['g']['hv']-b['g']['hv'],axis=1))),
            relative_gamma_linf=float(np.max(abs(c['gamma']-b['gamma']))/np.max(abs(c['gamma']))),
            profile_CD_change=c['result']['CDp']-b['result']['CDp'],
            note='Mixed receiver/circulation fields isolate terms algebraically; they are not claimed to solve the mixed control-point equations. Self-wake is an existing term, not a proposed deletion.'))
    changes=[]
    for variant in ['original','combined']:
        a,b,c=[states[p+'-'+variant]['result'] for p in ['default','whole_beam','native']]
        changes.append(dict(variant=variant,node_grid_step={k:b[k]-a[k] for k in ['CL','CD','CDi','CDi_near','CDp']},
            receiver_step={k:c[k]-b[k] for k in ['CL','CD','CDi','CDi_near','CDp']},
            total_step={k:c[k]-a[k] for k in ['CL','CD','CDi','CDi_near','CDp']}))
    DRIVER.stable(plan)
    result=dict(observed_utc=datetime.now(timezone.utc).isoformat(),cases=rows,receiver_decompositions=decompositions,
        endpoint_and_receiver_steps=changes,source_sha256=pins,unchanged_pins=plan['unchanged_pins'],
        script_sha256=sha(Path(__file__)),primary_status='SA-11 remains163/4592 at5%; no production, source model or registered scope changes.',
        limits=plan['limits'])
    p=BASE/'analysis.json';assert not p.exists();p.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps(dict(cases=rows,decompositions=decompositions)))


if __name__=='__main__':main()
