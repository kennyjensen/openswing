"""Separate SA-11 endpoint placement, receiver sampling and section inputs.

Three saved states are reused. Two fresh circulation solves and one prescribed-
circulation profile-force replay complete the six-state factorial comparison.
No production equations, defaults, original inputs or acceptance targets change.
"""
import argparse
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import sys
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from openswing.aero import FlightCondition, evaluate_aerodynamics
from openswing.asw import parse_asw
from openswing.frozen_influence import lifting_geometry
from openswing.geometry import model_meshes, surface_frame

OLD = ROOT/'artifacts/isae/sa11-frozen-inputs-20261107'
NATIVE = ROOT/'artifacts/isae/sa11-avl-baseline-r1-20261108'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
utc=lambda:datetime.now(timezone.utc).isoformat()
read=lambda p:json.loads(p.read_text())
def write(p,value):p.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')


def prepare(out,parent=None):
    assert not out.exists(),out
    old=read(OLD/'plan.json'); previous=read(OLD/'analysis.json'); native=read(NATIVE/'plan.json')
    pins=dict(native['unchanged_pins'])
    inputs={}
    for variant,index in [('original',0),('combined',1)]:
        job=old['jobs'][index]; path=ROOT/job['input']
        assert sha(path)==old['source_sha256'][job['input']]
        result=OLD/f'result-{index}.json'
        assert sha(result)==previous['results_sha256'][str(result.relative_to(ROOT))]
        inputs[variant]=job['input']
        for p in [path,result]:pins[str(p.relative_to(ROOT))]=sha(p)
    for c in ['original-alpha1','extension_slope-alpha1']:
        report=read(NATIVE/c/'report.json')
        for name,pin in report['artifact_sha256'].items():
            p=NATIVE/c/name; assert sha(p)==pin,name; pins[str(p.relative_to(ROOT))]=pin
        pins[str((NATIVE/c/'report.json').relative_to(ROOT))]=sha(NATIVE/c/'report.json')
    for p in [OLD/'plan.json',OLD/'analysis.json',NATIVE/'plan.json',NATIVE/'analysis.json']:
        pins[str(p.relative_to(ROOT))]=sha(p)
    reused=[dict(id='default-original',sampling='default',variant='original',path=str((OLD/'result-0.json').relative_to(ROOT)),wrapper=True),
            dict(id='default-combined',sampling='default',variant='combined',path=str((OLD/'result-1.json').relative_to(ROOT)),wrapper=True),
            dict(id='native-original',sampling='native',variant='original',path=str((NATIVE/'original-alpha1/openswing.json').relative_to(ROOT)),wrapper=False)]
    jobs=[dict(id='whole_beam-original',sampling='whole_beam',variant='original'),
          dict(id='whole_beam-combined',sampling='whole_beam',variant='combined'),
          dict(id='native-combined',sampling='native',variant='combined')]
    recovered=None
    if parent is not None:
        prior_plan=read(parent/'plan.json');stable(prior_plan)
        assert sha(parent/'driver-used.py')==prior_plan['driver_sha256']
        result_path=parent/'whole_beam-original/openswing.json'
        result=read(result_path)
        assert result['converged'] and result['residual']<1e-8
        reused.append(dict(jobs[0],path=str(result_path.relative_to(ROOT)),wrapper=False))
        jobs=jobs[1:]
        for p in [parent/'plan.json',parent/'driver-used.py',result_path]:pins[str(p.relative_to(ROOT))]=sha(p)
        recovered=dict(path=str(result_path.relative_to(ROOT)),
            reason='Call completed and full output was saved before the recorder compared the strip beam position with the bound receiver. Correct checks use position versus rm and velocity_position versus hv. No physical rerun; original elapsed time was not retained.')
    out.mkdir(parents=True)
    write(out/'plan.json',dict(observed_utc=utc(),inputs=inputs,jobs=jobs,reused=reused,
        unchanged_pins=pins,driver_sha256=sha(Path(__file__)),recovered_completed_call=recovered,
        condition=dict(speed=240.,alpha=1.,density=1.2256,mach=None,freeze_influences=True),
        protocol='A: saved default whole-beam cosine64 request with required breaks (70 strips). B: native sectionwise endpoint grid (64 strips), generated whole-beam Glauert receivers. C: same64 endpoints, actual native sectionwise Glauert receivers. Original and independently sourced combined slope/drag inputs; preserve all other properties. Reuse saved A originals/combined and C original. Solve B original/combined; replay saved native slope-only circulation for C combined, verifying residual. All production stall and local Mach checks remain active.',
        limits='Original historical grid/settings are unknown. These are sampling and property diagnostics, not a new native ASWING result, calibrated mesh, force-law replacement or registered pass.'))
    shutil.copyfile(__file__,out/'driver-used.py')
    print(json.dumps(dict(prepared=True,fresh_calls=len(jobs),reused=len(reused))))


def stable(plan):
    for name,pin in plan['unchanged_pins'].items():assert sha(ROOT/name)==pin,name


def mesh(plan,case):
    model=parse_asw((ROOT/plan['inputs'][case['variant']]).read_text())
    assert len(model.beams)==1 and not model.diagnostics
    if case['sampling']=='default':return model,model_meshes(model,64)
    name='original-alpha1' if case['variant']=='original' else 'extension_slope-alpha1'
    f=np.load(NATIVE/name/'native-fields.npz')
    beam=model.beams[0]; ends=np.r_[f['RV1'][:,1],f['RV2'][-1,1]]
    ends[0],ends[-1]=beam.domain
    meshes=model_meshes(model,dict(default=64,beams={'1':dict(nodes=ends.tolist())}))
    assert len(meshes[0].tm)==64
    if case['sampling']=='native':
        tm=f['RV'][:,1]
        meshes=[replace(m,tm=tm,rm=beam.position(tm),frames=surface_frame(beam,tm)) for m in meshes]
    g=lifting_geometry(meshes,np.array([1.,0.,0.]))
    assert max(np.max(abs(g[k]-f[n])) for k,n in [('a','RV1'),('b','RV2')])<1e-12
    if case['sampling']=='native':
        assert max(np.max(abs(g[k]-f[n])) for k,n in [('hv','RV'),('cp','RC')])<1e-12
    return model,meshes


def run(out,index):
    plan=read(out/'plan.json');stable(plan)
    assert sha(Path(__file__))==plan['driver_sha256']
    case=plan['jobs'][index];directory=out/case['id'];assert not directory.exists();directory.mkdir()
    model,meshes=mesh(plan,case);condition=FlightCondition(**plan['condition'])
    options={}
    if case['sampling']=='native':
        prior=read(NATIVE/'extension_slope-alpha1/openswing.json')
        options['circulation']=np.array([s['circulation'] for s in prior['strips']])
    start=time.monotonic();result=evaluate_aerodynamics(model,condition,meshes,**options);seconds=time.monotonic()-start
    assert result['converged'] and result['residual']<1e-8
    assert not any(s['stalled'] for s in result['strips'])
    assert max(s['normal_mach'] for s in result['strips'])<1
    write(directory/'openswing.json',result)
    g=lifting_geometry(meshes,np.array([1.,0.,0.]))
    assert np.max(abs(np.array([s['position'] for s in result['strips']])-g['rm']))<1e-12
    assert np.max(abs(np.array([s['velocity_position'] for s in result['strips']])-g['hv']))<1e-12
    np.savez(directory/'geometry.npz',**g,t=meshes[0].tm,s=meshes[0].frames[...,1])
    stable(plan)
    write(directory/'receipt.json',dict(observed_utc=utc(),case=case,seconds=seconds,prescribed_circulation=bool(options),
        result_sha256=sha(directory/'openswing.json'),geometry_sha256=sha(directory/'geometry.npz'),
        residual=result['residual'],coefficients={k:result[k] for k in ['CL','CD','CDi','CDi_near','CDp']},
        CD_error_percent=100*(result['CD']/.0110238-1)))
    print(json.dumps(read(directory/'receipt.json')))


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--continue-from',type=Path)
    g=p.add_mutually_exclusive_group(required=True);g.add_argument('--prepare',action='store_true');g.add_argument('--case',type=int)
    a=p.parse_args()
    if a.prepare:prepare(a.output.resolve(),a.continue_from.resolve() if a.continue_from else None)
    else:run(a.output.resolve(),a.case)


if __name__=='__main__':main()
