"""Two serial SA-11 solves isolating native versus whole-beam receiver rules."""
import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import signal
import sys
import time

import numpy as np

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
def module(name,file):
    spec=importlib.util.spec_from_file_location(name,ROOT/'scripts'/file)
    value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value
FIXED=module('fixed_moment','verify-sa11-fixed-pg-candidate.py')
AUDIT=module('moment_audit','audit-sa11-moment-speed.py')
from openswing.aero import FlightCondition, evaluate_aerodynamics
from openswing.frozen_influence import lifting_geometry
from openswing.geometry import model_meshes

PRIOR=ROOT/'artifacts/isae/sa11-moment-speed-20261108'
read=AUDIT.read;sha=AUDIT.sha;dump=AUDIT.dump
utc=lambda:datetime.now(timezone.utc).isoformat()


def prepare(out):
    assert not out.exists();out.mkdir(parents=True)
    previous=read(PRIOR/'analysis.json')
    for name,digest in previous['source_sha256'].items():assert sha(ROOT/name)==digest,name
    pins=dict(previous['source_sha256'])
    for p in (Path(__file__),PRIOR/'analysis.json'):
        pins[str(p.relative_to(ROOT))]=sha(p)
    cases=[dict(id=f'whole-beam-a{a:g}',alpha=a,choice='baseline_slope634',
                source_case=f'baseline_slope634-a{a:.1f}-pg0') for a in (0.,1.)]
    dump(out/'plan.json',dict(observed_utc=utc(),cases=cases,pins=pins,
        protocol='Retain native64 vortex endpoints and source-backed input hypothesis. Use whole-logical-beam Glauert receivers at255m/s, fixedPG0. Compare archived255/266 moment increment via unchanged equations. Two fresh production calls, normal stall and Mach guards.',
        limits='Receiver rule is documented, but these endpoints and producing input are not authenticated for archived ASWING. Diagnostic comparisons do not change primary passes or justify a velocity substitution.'))
    (out/'driver-used.py').write_bytes(Path(__file__).read_bytes())
    print(json.dumps(dict(prepared=True,physical_calls=2)),flush=True)


def run(out,index):
    plan=read(out/'plan.json')
    for name,digest in plan['pins'].items():assert sha(ROOT/name)==digest,name
    spec=plan['cases'][index];folder=out/spec['id'];folder.mkdir()
    old=AUDIT.FIXED/spec['source_case'];old_report=read(old/'report.json')
    for name,digest in old_report['artifact_sha256'].items():assert sha(old/name)==digest,name
    model,choice=FIXED.model_for(spec['choice'])
    assert choice==read(old/'input-choice.json')
    settings=dict(default=64,beams=read(old/'mapped-mesh.json')['settings'])
    meshes=model_meshes(model,settings);assert sum(len(m.tm) for m in meshes)==64
    geometry=lifting_geometry(meshes,np.array([1.,0.,0.]))
    with np.load(old/'native-fields.npz') as native:
        endpoints=max(float(np.max(abs(geometry[k]-native[f]))) for k,f in [('a','RV1'),('b','RV2')])
        assert endpoints<2e-14
        movement={k:float(np.max(np.linalg.norm(geometry[k]-native[f],axis=1))) for k,f in [('hv','RV'),('cp','RC')]}
    condition=FlightCondition(**read(old/'u255/condition.json'))
    assert condition.alpha==spec['alpha']
    dump(folder/'condition.json',asdict(condition));dump(folder/'input-choice.json',choice)
    dump(folder/'mesh-settings.json',settings);np.savez(folder/'geometry.npz',**geometry)
    def timeout(*args):raise TimeoutError('Two-case receiver diagnostic exceeded its15second per-call bound')
    previous=signal.signal(signal.SIGALRM,timeout);signal.alarm(15)
    start=time.monotonic()
    try:
        result=evaluate_aerodynamics(model,condition,meshes)
        seconds=time.monotonic()-start
        dump(folder/'openswing.json',result)
    finally:signal.alarm(0);signal.signal(signal.SIGALRM,previous)
    strips=result['strips'];gamma=np.array([s['circulation'] for s in strips]);cl=np.array([s['cl'] for s in strips])
    velocity=np.array([s['relative_velocity'] for s in strips]);beam=model.beams[0];t=np.array([s['t'] for s in strips])
    margins=np.minimum(beam.value('CLmax',t)-cl,cl-beam.value('CLmin',t))
    assert result['residual']<1e-8 and np.min(margins)>0
    np.savez(folder/'state.npz',gamma=gamma,velocity=velocity,cl=cl,stall_margin=margins)
    report=dict(case=spec,production=dict(status='computed',seconds=seconds,residual=result['residual'],
        minimum_stall_margin_widths=float(np.min(margins)/.05),stalled_strips=0),
        endpoint_max_error=endpoints,receiver_max_displacement=movement,
        artifact_sha256={p.name:sha(p) for p in folder.iterdir() if p.is_file()})
    dump(folder/'report.json',report)
    pins={};primary=read(AUDIT.PRIMARY/'plan.json')
    record,data=AUDIT.evaluate(dict(id=spec['id'],folder=str(folder.relative_to(ROOT)),
        alpha=spec['alpha'],low_directory='.'),primary,pins)
    assert record['status']=='valid moment replay'
    old_record=next(r for r in read(PRIOR/'analysis.json')['cases'] if r['id']==spec['source_case'])
    with np.load(PRIOR/(spec['source_case']+'.npz')) as saved:
        old_data={k:saved[k].copy() for k in saved.files}
    # Exact symmetric decomposition into geometric section weights and the
    # local-speed-dependent dynamic-pressure/PG factor, with no fitted terms.
    def factors(d):
        f=d['speed']/255
        return d['weight']/f**2, f**2*(1/np.sqrt(1-(d['mach']*266/255)**2)-1/np.sqrt(1-d['mach']**2))
    gc,hc=factors(old_data);gb,hb=factors(data)
    flow=.5*(gc+gb)*(hc-hb);weights=.5*(hc+hb)*(gc-gb)
    delta=old_record['predicted_delta_Cm']-record['predicted_delta_Cm']
    assert abs(float(np.sum(flow+weights))-delta)<1e-16
    record.update(native_receiver_delta_Cm=old_record['predicted_delta_Cm'],
        native_receiver_error_percent=old_record['delta_error_percent'],
        native_minus_whole_delta=delta,
        flow_factor_contribution=float(flow.sum()),geometric_weight_contribution=float(weights.sum()),
        values={k:result[k] for k in ('CL','CD','CDi','CDp','CDi_near','Cm_origin')},
        endpoint_max_error=endpoints,receiver_max_displacement=movement,
        physical_seconds=seconds,source_sha256=pins)
    np.savez(folder/'moment-replay.npz',**data,flow_factor_difference=flow,geometry_weight_difference=weights)
    dump(folder/'moment-comparison.json',record)
    for name,digest in plan['pins'].items():assert sha(ROOT/name)==digest,name
    print(json.dumps({k:v for k,v in record.items() if k!='source_sha256'}),flush=True)


def main():
    assert all(os.environ.get(k)=='1' for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'))
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--output',type=Path,required=True)
    group=ap.add_mutually_exclusive_group(required=True);group.add_argument('--prepare',action='store_true');group.add_argument('--case',type=int,choices=[0,1])
    args=ap.parse_args();out=args.output.resolve()
    prepare(out) if args.prepare else run(out,args.case)


if __name__=='__main__':main()
