"""Independent saved-field reductions and literal-reference checks; no solve."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import resource
import signal

resource.setrlimit(resource.RLIMIT_AS,(512*1024**2,512*1024**2))
resource.setrlimit(resource.RLIMIT_CPU,(15,15)); signal.alarm(25)
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--input',type=Path,required=True)
FOLDER=parser.parse_args().input.resolve()
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
read=lambda p:json.loads(p.read_text())
analysis=read(FOLDER/'analysis.json'); plan=read(FOLDER/'plan.json')
assert analysis['plan_sha256']==sha(FOLDER/'plan.json')
for name,digest in plan['pins'].items(): assert sha(ROOT/name)==digest,name
for name,digest in plan['generated_pins'].items(): assert sha(FOLDER/name)==digest,name
manifest_path=ROOT/'reference/isae-validation/manifest.json'
manifest=read(manifest_path)
cache=manifest_path.parent/manifest['revision']
tables={}
for path in {c['table'] for c in plan['cases']}:
    p=ROOT/path; content=p.read_bytes(); entry=manifest['files'][str(p.relative_to(cache))]
    assert len(content)==entry['bytes'] and sha(p)==entry['sha256']
    assert hashlib.sha1(f'blob {len(content)}\0'.encode()+content).hexdigest()==entry['git_blob_sha1']
    tables[path]=[line.split() for line in p.read_text().splitlines() if len(line.split())==82 and line.split()[0].isdigit()]

def block_first(name):
    lines=(FOLDER/'model.asw').read_text().splitlines()
    for line in lines[lines.index(name)+1:]:
        line=line.split('#')[0].strip()
        if line: return list(map(float,line.split()))
    raise AssertionError(name)

_,rho,sound=block_first('Constant'); area,chord,_=block_first('Reference')
assert rho==1.2256 and sound==340.21 and area==.9329
errors=dict(force_coefficients=0.,moment_coefficient=0.,local_mach=0.,reported_percent=0.,geometry=0.)
first_geometry=None; accepted_count=0; passing_count=0; rejected=[]
fields=dict(lift=75,drag=76,CL=77,CD=78,CDi=79,Cm_origin=80,efficiency=81)
for row,case in zip(analysis['cases'],plan['cases'],strict=True):
    folder=FOLDER/case['id']; assert sha(folder/'report.json')==row['report_sha256']
    assert row['case']==case and case['tokens']==tables[case['table']][case['row']]
    for name,digest in row['artifacts'].items(): assert sha(folder/name)==digest
    raw=list(map(float,case['tokens']))
    speed,alpha=raw[69],math.radians(raw[71]); qs=.5*rho*speed**2*area
    is_valid=row['status']=='COMPUTED_DIAGNOSTIC'
    if is_valid:
        result=read(folder/'accepted.json'); assert result['converged']; accepted_count+=1
    else:
        error=read(folder/'rejected.json'); assert error['details']['kind']=='section_normal_mach'
        assert not (folder/'accepted.json').exists() and row['values']['Cm_origin'] is None
    with np.load(folder/'state.npz') as data:
        assert bool(data['section_moment_available'])==is_valid
        assert len(data['force'])==plan['total_intervals']
        assert np.all(np.isfinite(data['section_moment'])) if is_valid else np.all(np.isnan(data['section_moment']))
        force=[math.fsum(map(float,data['force'][:,i])) for i in range(3)]
        lift=-math.sin(alpha)*force[0]+math.cos(alpha)*force[2]
        drag=math.cos(alpha)*force[0]+math.sin(alpha)*force[2]
        predicted=dict(lift=lift,drag=drag,CL=lift/qs,CD=drag/qs)
        if is_valid:
            moment=math.fsum(float(m[1])+float(r[2])*float(f[0])-float(r[0])*float(f[2])
                            for r,f,m in zip(data['position'],data['force'],data['section_moment']))
            predicted['Cm_origin']=moment/(qs*chord)
            errors['moment_coefficient']=max(errors['moment_coefficient'],abs(predicted['Cm_origin']-result['Cm_origin']))
        for name in ('CL','CD'): errors['force_coefficients']=max(errors['force_coefficients'],abs(predicted[name]-row['values'][name]))
        mach=[]
        for v,s in zip(data['velocity'],data['span']):
            dot=math.fsum(float(x)*float(y) for x,y in zip(v,s))
            mach.append(math.sqrt(math.fsum((float(x)-dot*float(y))**2 for x,y in zip(v,s)))/sound)
        errors['local_mach']=max(errors['local_mach'],max(abs(x-y) for x,y in zip(mach,data['mach'])))
        invalid=[i for i,m in enumerate(mach) if m>=1]
        assert len(invalid)==row['rejected_sections'] and (not invalid)==is_valid
        if invalid:
            assert sorted(invalid)==sorted(s['panel_index'] for s in error['details']['rejected_sections'])
            rejected.append(dict(case=case['id'],alpha=raw[71],speed=speed,indices=invalid,mach=[mach[i] for i in invalid]))
        g=np.concatenate([data['position'],data['span']],axis=1)
        if first_geometry is None: first_geometry=g.copy()
        else: errors['geometry']=max(errors['geometry'],float(np.max(abs(g-first_geometry))))
        for key,column in fields.items():
            assert raw[column]==case['reference'][key]
            value=predicted.get(key,row['values'][key])
            err=None if value is None else 100*(value/raw[column]-1)
            if err is not None: errors['reported_percent']=max(errors['reported_percent'],abs(err-row['reference_error_percent'][key]))
            passes=bool(is_valid and abs(err)<=5)
            assert passes==row['passes'][key]
            passing_count+=passes
assert accepted_count==sum(g['computed'] for g in analysis['groups'].values())
assert passing_count==sum(g['passing_scalar_targets'] for g in analysis['groups'].values())
assert len(rejected)+accepted_count==len(plan['cases'])==42
assert errors['geometry']==0 and errors['force_coefficients']<3e-14 and errors['moment_coefficient']<2e-12
assert errors['local_mach']<3e-14 and errors['reported_percent']<3e-10
result=dict(verified_utc=datetime.now(timezone.utc).isoformat(),cases=42,accepted=accepted_count,
    passing_diagnostic_scalar_targets=passing_count,required_diagnostic_scalar_targets=294,rejected=rejected,
    errors=errors,source_pins_verified=len(plan['pins']),analysis_sha256=sha(FOLDER/'analysis.json'),
    checker_sha256=sha(Path(__file__)),source_manifest_sha256=sha(manifest_path),primary_passes_added=0,
    finding='Literal source row identities and scalar force/moment/local-Mach reductions verified. Frozen sampled geometry identical across all42 calls. Missing moments have explicit unavailable flags and NaN arrays, never zero loads.')
path=FOLDER/'verification.json'; assert not path.exists(); path.write_text(json.dumps(result,indent=2)+'\n')
signal.alarm(0)
print(json.dumps({k:result[k] for k in ('cases','accepted','passing_diagnostic_scalar_targets','errors','source_pins_verified')},indent=2))
