"""Read-only audit of the nine matched native AVL / OpenSwing controls."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys

import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from openswing.factored_influence import FactoredInfluence


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def write(path,value):path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();out=a.output.resolve();assert not out.exists();out.mkdir(parents=True)
    parents=[ROOT/'artifacts/isae/avl-matched-fields-r1-20261108',ROOT/'artifacts/isae/avl-matched-swept-r1-20261108']
    build=ROOT/'artifacts/isae/avl-native-build-20261108'
    source=build/'source/src/aic.f';text=source.read_text()
    literal=float(re.search(r'DATA PI4INV\s*/\s*([0-9.]+)',text).group(1))
    factor=literal*4*np.pi
    source_pins=json.loads((build/'plan.json').read_text())['source_build_pins']
    for name,pin in source_pins.items():assert sha(build/'source'/name)==pin,name
    cases=[];pins={};input_pins={};checks=[]
    def check(name,value):
        checks.append(dict(name=name,passed=bool(value)))
        assert value,name
    for parent in parents:
        plan=json.loads((parent/'plan.json').read_text());pins.update(plan['unchanged_pins'])
        input_pins[str((parent/'plan.json').relative_to(ROOT))]=sha(parent/'plan.json')
        check(parent.name+' driver snapshot',sha(parent/'driver-used.py')==plan['driver_sha256'])
        patched=(parent/'aoutmrf.f').read_text()
        check(parent.name+' only output writes added',hashlib.sha256(patched.replace(plan['patch'],'').encode()).hexdigest()==plan['original_output_source_sha256'])
        for name,pin in plan['native_objects'].items():check(parent.name+' native object '+name,sha(build/'objects'/name)==pin)
        for spec in plan['cases']:
            directory=parent/spec['id'];record=json.loads((directory/'comparison.json').read_text())
            input_pins[str((directory/'comparison.json').relative_to(ROOT))]=sha(directory/'comparison.json')
            for name,pin in record['artifacts'].items():check(spec['id']+' artifact '+name,sha(directory/name)==pin)
            with np.load(directory/'native-fields.npz') as archive:
                f={k:archive[k] for k in archive.files}
            result=json.loads((directory/'openswing.json').read_text())
            gamma=np.array([s['circulation'] for s in result['strips']]);native_gamma=f['GAM'].ravel()
            count=len(gamma);vector=f['RV2']-f['RV1'];span=vector/np.linalg.norm(vector,axis=1)[:,None]
            hv=FactoredInfluence(f['RV'],f['RV1'],f['RV2'],[1.,0.,0.],np.eye(3),exclude_bound=np.eye(count,dtype=bool))
            cp=FactoredInfluence(f['RC'],f['RV1'],f['RV2'],[1.,0.,0.],np.eye(3))
            v=f['VINF']+f['VV'];vp=v-np.sum(v*span,axis=1)[:,None]*span
            peak=int(np.argmax(np.linalg.norm(vp,axis=1)))
            bound=np.einsum('ijk,j->ik',hv.bound,native_gamma)*factor
            wake=np.einsum('ijk,j->ik',hv.rays,hv.wake_strengths(native_gamma))*factor
            corrected_gamma=float(np.max(abs(gamma-factor*native_gamma))/np.max(abs(native_gamma)))
            corrected_field=float(np.max(abs(bound+wake-f['VV'])))
            corrected_cp=float(np.max(abs(np.sum((factor*cp.apply(native_gamma)+f['VINF'])*f['ENC'],axis=1))))
            coefficient_errors={k:float(abs(v['openswing']-v['native']*(factor**2 if k=='CDi' else factor))) for k,v in record['coefficients'].items()}
            check(spec['id']+' matched geometry',max(record['geometry'][k] for k in ('a','b','hv','cp','normals'))<2e-12)
            check(spec['id']+' original exported totals unchanged',all(record['native_original_output_identical'].values()))
            check(spec['id']+' circulation after literal constant',corrected_gamma<2e-10)
            check(spec['id']+' bound velocity after literal constant',corrected_field<2e-9)
            check(spec['id']+' control residual after literal constant',corrected_cp<2e-9)
            check(spec['id']+' coefficients after literal constant',max(coefficient_errors.values())<2e-10)
            row=dict(case=spec,coefficients=record['coefficients'],geometry=record['geometry'],
                native_seconds=record['native_seconds'],openswing_seconds=record['openswing_seconds'],
                max_relative_gamma_difference=record['relative_gamma_linf'],
                corrected_gamma_relative_error=corrected_gamma,corrected_field_absolute_error=corrected_field,
                corrected_cp_residual=corrected_cp,corrected_coefficient_absolute_errors=coefficient_errors,
                peak=dict(index=peak,position=f['RV'][peak].tolist(),speed=float(np.linalg.norm(v[peak])),
                    normal_speed=float(np.linalg.norm(vp[peak])),freestream=f['VINF'][peak].tolist(),
                    bound_velocity=bound[peak].tolist(),wake_velocity=wake[peak].tolist(),native_velocity=v[peak].tolist()),
                interpretation='Peak is selected independently on each refined grid; receiver positions move. Not a fixed-position convergence claim.')
            if spec['geometry']=='winglets':
                row['peak']['distance_to_nearest_junction']=float(min(np.linalg.norm(f['RV'][peak]-[.25,y,0]) for y in (-5,5)))
            cases.append(row)
    for name,pin in pins.items():check('unchanged '+name,sha(ROOT/name)==pin)
    check('all nine comparisons',len(cases)==9)
    report=dict(observed_utc=datetime.now(timezone.utc).isoformat(),status='verified',
        native_kernel_constant=literal,mathematical_constant=1/(4*np.pi),kernel_ratio=factor,
        constant_source=str(source.relative_to(ROOT)),constant_source_sha256=sha(source),
        explanation='Native VORVELC uses literal PI4INV=0.079577472. At negligible core its entire influence matrix scales by k=4*pi*PI4INV; hence OpenSwing/native Gamma and near forces scale by k. Trefftz drag uses the squared circulation and scales by k^2. This is a source-derived identity, not a fitted correction; no predictions or pass fractions were changed.',
        cases=cases,checks=checks,unchanged_pins=pins,input_pins=input_pins,
        source_files_verified=len(source_pins),
        preserved_harness_failures=['artifacts/isae/avl-matched-fields-20261108/rectangle-c1-s16/diagnostic-failure.json','artifacts/isae/avl-matched-swept-20261108/swept-c1-s16/diagnostic-failure.json'],
        limits='Original native AVL output only establishes these matched incompressible, inviscid, one-row fixed-wake controls. It is not ASWING validation or a winglet repair.')
    write(out/'report.json',report);shutil.copyfile(__file__,out/'driver-used.py')
    print(json.dumps(dict(status='verified',cases=len(cases),checks=len(checks),kernel_ratio=factor,
        max_corrected_gamma_relative_error=max(r['corrected_gamma_relative_error'] for r in cases),
        max_corrected_field_error=max(r['corrected_field_absolute_error'] for r in cases),
        max_corrected_coefficient_error=max(max(r['corrected_coefficient_absolute_errors'].values()) for r in cases))))


if __name__=='__main__':main()
