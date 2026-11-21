"""Reconstruct Durrant Case 4 instability without fitting the published boundary.

This preliminary study retains local-search coverage and source/setup gaps.
An eigenvalue crossing is not automatically the experimental destruction speed.
"""
import argparse
import hashlib
import json
import platform
import runpy
import sys
import time
import traceback
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import numpy as np
import scipy
from openswing.asw import parse_asw
from openswing.aero import FlightCondition
from openswing.linear_dynamics import make_system,linearize,eigensystem,complex_data

LOW=runpy.run_path(str(ROOT/'scripts/verify-durrant-low-speed.py'))


def fingerprints():
    files=[*sorted((ROOT/'openswing').glob('*.py')),
           *sorted((ROOT/'scripts').glob('*.py')),
           *sorted((ROOT/'docs/validation').glob('*reference.json'))]
    return {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}


def setup(spec):
    allowed={'wing','panels','speed_m_s','incidence_deg','variant','nea','time_unit_s',
             'mach','aero_lag','gravity_m_s2','step','shifts','count','stall','freeze_influences'}
    if set(spec)-allowed:
        raise ValueError('Unknown study options: '+', '.join(sorted(set(spec)-allowed)))
    scale=spec.get('time_unit_s',1.)
    if not np.isfinite(scale) or scale<=0:
        raise ValueError('Input time unit must be finite and positive.')
    source=LOW['configuration'](spec)
    model=parse_asw(source)
    condition=FlightCondition(speed=spec['speed_m_s']*scale,alpha=0.,beta=spec['incidence_deg'],
        mach=spec.get('mach',0.),density=1.225,aero_lag=spec.get('aero_lag',True),
        stall=spec.get('stall',True),freeze_influences=spec.get('freeze_influences',False))
    panels={'default':spec['panels'],'beams':{'1':{'count':spec['panels'],'spacing':'uniform'}}}
    gravity=[0.,0.,-spec.get('gravity_m_s2',9.805)*scale**2]
    return source,model,condition,panels,gravity,scale


def compute(spec):
    started=time.monotonic()
    source,model,condition,panels,gravity,scale=setup(spec)
    print('Equilibrium',spec,flush=True)
    system,continuation=make_system(model,condition,panels=panels,gravity=gravity,
                                    tolerance=1e-9,continuation_steps=4)
    base=system.base_report()
    assert base['modal_base']['continuous_residual']<1e-7
    print('Linearization',spec,'base residual',base['modal_base']['continuous_residual'],flush=True)
    a,m=linearize(system,step=spec.get('step',1e-5))
    searches=[]
    for shift in spec.get('shifts',[[-.1,100.]]):
        print('Eigenvalue search',shift,flush=True)
        modes,metadata=eigensystem(a,m,time_scale=system.W,count=spec.get('count',24),
            method='full_shift_invert',shift=np.asarray(shift)*scale)
        rows=[];n=system.network
        for mode in modes:
            error=max(mode['right_backward_error'],mode['left_backward_error'])
            assert error<1e-9,error
            shape=mode['right'][:6*n.nn].reshape(n.nn,6).copy();shape[:,:3]*=system.L
            rows.append(dict(eigenvalue_per_s=(np.asarray(mode['eigenvalue'])/scale).tolist(),frequency_Hz=mode['eigenvalue'][1]/(scale*2*np.pi),
                right_backward_error=mode['right_backward_error'],left_backward_error=mode['left_backward_error'],
                mechanical_shape=complex_data(shape)))
        searches.append(dict(shift=shift,shift_units='1/s',metadata=metadata,modes=rows))
    return dict(status='computed',spec=spec,source=source,condition=vars(condition),panels=panels,gravity=gravity,
        input_time_unit_s=scale,base_units='Input units; roots and mechanical shapes above are SI.',
        actual_elements=system.network.ne,base=base,jig_positions=system.network.rj.tolist(),
        searches=searches,elapsed_seconds=time.monotonic()-started,
        scope='Loaded nonlinear Case 4 equilibrium and local full-descriptor eigenvalue searches. Mesh, tangent/search invariance, critical-speed refinement and exact published setup/parity are not yet established.')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    assert not args.output.exists(),'Use a fresh output directory for each recorded pilot.'
    args.output.mkdir(parents=True)
    plan=json.loads(args.plan.read_text());sources=fingerprints()
    record=dict(started=time.time(),source_sha256=sources,plan=plan,
        plan_sha256=hashlib.sha256(args.plan.read_bytes()).hexdigest(),
        versions=dict(python=platform.python_version(),numpy=np.__version__,scipy=scipy.__version__),cases=[])
    def save():
        p=args.output/'run.json';tmp=p.with_suffix('.part');tmp.write_text(json.dumps(record,indent=2,allow_nan=False)+'\n');tmp.replace(p)
    save()
    for i,spec in enumerate(plan['cases']):
        assert sources==fingerprints(),'Study source changed during the run.'
        try:case=compute(spec)
        except Exception as exc:
            case=dict(status='rejected',spec=spec,error=repr(exc),traceback=traceback.format_exc())
            print(case['traceback'],flush=True)
        assert sources==fingerprints(),'Study source changed during the run.'
        raw=(json.dumps(case,indent=2,allow_nan=False)+'\n').encode()
        name=f'case-{i:02d}.json';(args.output/name).write_bytes(raw)
        record['cases'].append(dict(file=name,status=case['status'],sha256=hashlib.sha256(raw).hexdigest()))
        save()
        if case['status']=='computed':
            print('Computed',spec,'roots',[(m['eigenvalue_per_s'],m['frequency_Hz']) for m in case['searches'][0]['modes'] if m['frequency_Hz']>0],flush=True)
    record['ended']=time.time();record['status']='computed' if all(c['status']=='computed' for c in record['cases']) else 'contains rejected cases';save()
    raise SystemExit(0 if record['status']=='computed' else 1)


if __name__=='__main__':main()
