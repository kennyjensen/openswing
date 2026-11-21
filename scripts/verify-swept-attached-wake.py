"""Field-only control with chordwise attached legs before the free wake.

Same prescribed Gamma and straight bound geometry as swept-wake-limit.
No force closure, circulation solve, core, SA-11 mapping or production change.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import sys
import time

import numpy as np
from scipy.integrate import quad_vec

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from openswing.aero import semi_infinite_vortex, finite_vortex


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def portable(x):
    if isinstance(x,np.ndarray): return x.tolist()
    if isinstance(x,np.generic): return x.item()
    if isinstance(x,dict): return {k:portable(v) for k,v in x.items()}
    if isinstance(x,(tuple,list)): return [portable(v) for v in x]
    return x


def write(path,value): path.write_text(json.dumps(portable(value),indent=2,allow_nan=False)+'\n')


def ray(origin,direction):
    """Independent point=0, unit-strength ray with stable upstream formula."""
    r=-origin
    axial=float(r@direction)
    transverse=r-axial*direction
    h2=float(transverse@transverse)
    distance=float(np.linalg.norm(r))
    if axial<0:
        multiplier=1/(distance*(distance-axial))
    else:
        assert h2>0.
        multiplier=(1+axial/distance)/h2
    return np.cross(direction,r)*multiplier/(4*np.pi)


def reference(sweep,asymmetry,length):
    span=np.array([np.sin(sweep),np.cos(sweep),0.])
    chord=np.array([np.cos(sweep),-np.sin(sweep),0.])
    wind=np.array([1.,0.,0.])
    def regular(s):
        origin=s*span+length*chord
        gradient=asymmetry-2*s-3*asymmetry*s*s
        return -gradient*(ray(origin,wind)-ray(origin,chord))
    remainder,error=quad_vec(regular,-1.,1.,epsabs=2e-12,epsrel=2e-12,limit=500)
    assert error<2e-10
    # Infinite orthogonal legs have K_z=-1/(4*pi*s). For the prescribed
    # polynomial, its symmetric principal value is exactly -1/pi.
    return np.array([0.,0.,-1/np.pi])+remainder,float(error)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists(): parser.error('Use a fresh output directory.')
    sources={};pins=None;plans={};inputs={}
    for spacing in ('cosine','uniform'):
        p=ROOT/f'artifacts/isae/swept-wake-limit-20261108-{spacing}'
        manifest=json.loads((p/'verification.json').read_text())
        for name,digest in manifest['artifacts'].items(): assert sha(p/name)==digest,name
        plan=json.loads((p/'plan.json').read_text())
        if pins is None: pins=plan['unchanged_pins']
        assert pins==plan['unchanged_pins']
        for name,digest in pins.items(): assert sha(ROOT/name)==digest,name
        sources[str(p.relative_to(ROOT))]=sha(p/'verification.json')
        plans[spacing]=plan;inputs[spacing]=json.loads((p/'results.json').read_text())
    args.output.mkdir(parents=True)
    shutil.copyfile(__file__,args.output/'driver-used.py')
    plan=dict(observed_utc=datetime.now(timezone.utc).isoformat(),unchanged_pins=pins,
        input_manifests=sources,chord=1.,attached_length=.75,
        geometry='Quarter-chord line unchanged. Each trailing leg follows local chord for 0.75 chord, then the +x wind to infinity.',
        analytic_control='Orthogonal infinite-leg PV (-z/pi) plus a nonsingular integral of shifted free-minus-orthogonal rays.',
        source='Gaunaa, Li and Pirrung 2026, section 3; the authors explicitly call the attachment direction a modeling choice.',
        source_url='https://backend.orbit.dtu.dk/ws/portalfiles/portal/446323265/Gaunaa_2026_J._Phys._Conf._Ser._3224_042030.pdf',
        scope='Velocity mechanism only. Added attached-vortex forces and inner/outer circulation coupling are NOT implemented here.',
        core=0.,mach=0.,new_circulation_solves=0,
        gates=dict(ray_difference_identity_atol=2e-11,final_continuous_reference_error=2e-4))
    write(args.output/'plan.json',plan)
    started=time.monotonic();records=[];references={}
    try:
        for spacing,data in inputs.items():
            for row in data['records']:
                sweep=np.deg2rad(row['sweep_degrees']);asymmetry=row['asymmetry']
                span=np.array([np.sin(sweep),np.cos(sweep),0.])
                chord=np.array([np.cos(sweep),-np.sin(sweep),0.]);wind=np.array([1.,0.,0.])
                nodes=np.asarray(row['nodes'])[:,None]*span
                rear=nodes+plan['attached_length']*chord
                strengths=np.asarray(row['ray_strengths'])
                attached=finite_vortex(np.zeros(3),nodes,rear)
                split=semi_infinite_vortex(np.zeros(3),nodes,chord)-semi_infinite_vortex(np.zeros(3),rear,chord)
                np.testing.assert_allclose(attached,split,atol=2e-11,rtol=2e-11)
                free=semi_infinite_vortex(np.zeros(3),rear,wind)
                velocity=np.sum((attached+free)*strengths[:,None],axis=0)
                key=(row['sweep_degrees'],asymmetry)
                if key not in references:
                    value,error=reference(sweep,asymmetry,plan['attached_length'])
                    references[key]=dict(sweep_degrees=row['sweep_degrees'],asymmetry=asymmetry,
                                         velocity=value,quadrature_estimate=error)
                expected=references[key]['velocity'];error=float(np.linalg.norm(velocity-expected))
                if row['sweep_degrees']==0.:
                    np.testing.assert_allclose(velocity,row['wake'][0],atol=2e-11,rtol=2e-11)
                if row['panels']==511: assert error<plan['gates']['final_continuous_reference_error']
                records.append(dict(spacing=spacing,sweep_degrees=row['sweep_degrees'],asymmetry=asymmetry,
                    panels=row['panels'],native_velocity=row['wake'][0],attached_velocity=velocity,
                    continuous_reference=expected,continuous_error=error,
                    finite_ray_difference_max_error=float(np.max(abs(attached-split)))))
        for name,digest in pins.items(): assert sha(ROOT/name)==digest,name
        result=dict(observed_utc=datetime.now(timezone.utc).isoformat(),records=records,
                    continuous_references=list(references.values()),new_circulation_solves=0,
                    total_seconds=time.monotonic()-started,production_and_primary_counts_unchanged=True)
        write(args.output/'results.json',result)
        write(args.output/'verification.json',dict(status='verified',observed_utc=datetime.now(timezone.utc).isoformat(),
            artifacts={p.name:sha(p) for p in sorted(args.output.iterdir()) if p.is_file()},unchanged_pin_count=len(pins)))
        print(json.dumps(portable(dict(status='verified',fields=len(records),
            final_reference_error=max(r['continuous_error'] for r in records if r['panels']==511),
            seconds=result['total_seconds'],references=list(references.values())))))
    except Exception as exc:
        write(args.output/'failure.json',dict(error_type=type(exc).__name__,error=str(exc),
            observed_utc=datetime.now(timezone.utc).isoformat(),records=records))
        raise


if __name__=='__main__': main()
