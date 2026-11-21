"""Independent saved-field audit, one SA-11 configuration per bounded job."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import resource
import signal
import sys

ROOT=Path(__file__).resolve().parents[1]
read=lambda p:json.loads(p.read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
utc=lambda:datetime.now(timezone.utc).isoformat()


def write(path,value):
    text=json.dumps(value,indent=2,allow_nan=False)+'\n'
    with path.open('x') as f:f.write(text)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--configuration',choices=('wing_alone','wing_extension','upper_winglet'))
    parser.add_argument('--aggregate',action='store_true')
    args=parser.parse_args();out=args.output.resolve()
    for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):assert os.environ.get(key)=='1'
    resource.setrlimit(resource.RLIMIT_AS,(512*1024**2,512*1024**2))
    resource.setrlimit(resource.RLIMIT_CPU,(15,15));signal.alarm(25)
    plan=read(out/'plan.json');digest=sha(out/'plan.json')
    for name,value in plan['pins'].items():assert sha(ROOT/name)==value,name
    if args.aggregate:
        audits=[read(out/f'verification-{c}.json') for c in plan['preflight']]
        assert all(a['verified'] and a['plan_sha256']==digest for a in audits)
        rows=[]
        for case in plan['cases']:
            path=out/case['id']/'report.json';r=read(path)
            a=next(a for a in audits if a['configuration']==case['configuration'])
            assert sha(path)==a['report_sha256'][case['id']]
            r['report_sha256']=sha(path);rows.append(r)
        batches=[read(p) for p in sorted(out.glob('batch-*.json'))]
        assert [r['id'] for b in batches for r in b['rows']]==[c['id'] for c in plan['cases']]
        assert sum(r['physical_calls'] for r in rows)==plan['physical_calls']==89
        report=dict(observed_utc=utc(),verified=True,cases=rows,plan_sha256=digest,
            computed=sum(r['status']=='computed' for r in rows),rejected=sum(r['status']=='rejected' for r in rows),
            physical_calls=89,reused_states=4,maximum_batch_seconds=max(b['seconds'] for b in batches),
            total_batch_seconds=sum(b['seconds'] for b in batches),peak_rss_kib=max(b['peak_rss_kib'] for b in batches),
            maximum_residual=max(r['residual'] for r in rows),
            maximum_normal_mach=max(r['maximum_normal_mach'] for r in rows),
            minimum_stall_margin_widths=min(r['minimum_stall_margin_widths'] for r in rows if r['status']=='computed'),
            maximum_independent_errors={k:max(a['errors'][k] for a in audits) for k in audits[0]['errors']},
            pins=dict(plan['pins']),configuration_verification_sha256={a['configuration']:sha(out/f"verification-{a['configuration']}.json") for a in audits})
        report['pins'][str(Path(__file__).relative_to(ROOT))]=sha(Path(__file__))
        write(out/'analysis.json',report)
        print(json.dumps({k:v for k,v in report.items() if k not in ('cases','pins')},indent=2))
        signal.alarm(0);return
    assert args.configuration
    import numpy as np
    sys.path.insert(0,str(ROOT/'scripts'))
    from avl_vorvelc_reference import matrix
    errors=dict(velocity_relative=0.,force=0.,moment=0.,normal_mach=0.,reference_percent=0.)
    hashes={};n=0;tables={}
    for case in plan['cases']:
        if case['configuration']!=args.configuration:continue
        folder=out/case['id'];row=read(folder/'report.json')
        assert row['case']==case and row['plan_sha256']==digest
        for name,value in row['artifacts'].items():assert sha(folder/name)==value,name
        tokens=tables.setdefault(case['table'],[l.split() for l in (ROOT/case['table']).read_text().splitlines()
            if len(l.split())==82 and l.split()[0].isdigit()])[case['row']]
        assert tokens==case['tokens'] and float(tokens[71])==case['alpha']
        assert case['condition']['freeze_influences'] is True
        assert row['status']=='computed','Retain rejection and extend this audit to its saved details before scoring'
        raw=read(folder/'accepted.json')
        assert raw['converged'] and raw['residual']<1e-8
        if case['reused_accepted']:
            assert raw==read(ROOT/case['reused_accepted']) and row['physical_calls']==0
        else:assert row['physical_calls']==1
        with np.load(folder/'geometry.npz') as saved:g={k:saved[k] for k in saved}
        gamma=np.array([s['circulation'] for s in raw['strips']])
        v=np.array([s['relative_velocity'] for s in raw['strips']])
        speed=case['condition']['speed'];alpha=math.radians(case['alpha'])
        # Frozen zero-incidence body-x wake/PG directions. Actual flight velocity
        # still follows the specified incidence. No production influence helper.
        operator=matrix(g['hv'],g['a'],g['b'],speed/340.21,exclude_self=True,core_fraction=0.,dtype=np.longdouble)
        velocity=np.einsum('ijq,j->iq',operator,gamma)
        velocity*=np.longdouble(1)/(4*np.arccos(np.longdouble(-1))*np.longdouble('.079577472'))
        velocity+=speed*np.array([math.cos(alpha),0,math.sin(alpha)])
        errors['velocity_relative']=max(errors['velocity_relative'],float(np.max(abs(v-velocity))/speed))
        del operator
        perp=v-np.sum(v*g['span'],axis=1)[:,None]*g['span']
        mach=np.linalg.norm(perp,axis=1)/340.21
        errors['normal_mach']=max(errors['normal_mach'],float(max(abs(mach-np.array([s['normal_mach'] for s in raw['strips']])))))
        assert max(mach)<1 and abs(max(mach)-row['maximum_normal_mach'])<1e-12
        force=[math.fsum(s['force'][k] for s in raw['strips']) for k in range(3)]
        qs=.5*1.2256*speed**2*.9329
        lift=force[2]*math.cos(alpha)-force[0]*math.sin(alpha)
        drag=force[0]*math.cos(alpha)+force[2]*math.sin(alpha)
        moment=math.fsum(s['moment'][1]+s['position'][2]*s['force'][0]-s['position'][0]*s['force'][2] for s in raw['strips'])
        values=dict(lift=lift,drag=drag,CL=lift/qs,CD=drag/qs,Cm_origin=moment/(qs*.37874))
        errors['force']=max(errors['force'],abs(values['CL']-row['values']['CL']),abs(values['CD']-row['values']['CD']))
        errors['moment']=max(errors['moment'],abs(values['Cm_origin']-row['values']['Cm_origin']))
        for key,col in dict(lift=75,drag=76,CL=77,CD=78,CDi=79,Cm_origin=80,efficiency=81).items():
            target=float(tokens[col]);assert target==case['reference'][key]
            value=values.get(key,raw[key] if key in raw else row['values'][key])
            # Recorder reports 100*(actual/reference - 1): for negative Cm this
            # is an error in moment magnitude, with the opposite signed sense.
            errors['reference_percent']=max(errors['reference_percent'],abs(100*(value/target-1)-row['errors_percent'][key]))
        hashes[case['id']]=sha(folder/'report.json');n+=1
    assert errors['velocity_relative']<2e-10 and errors['force']<2e-12 and errors['moment']<2e-12
    assert errors['normal_mach']<2e-12 and errors['reference_percent']<2e-10,errors
    report=dict(observed_utc=utc(),verified=True,configuration=args.configuration,states=n,errors=errors,
        source_pins_verified=len(plan['pins']),report_sha256=hashes,plan_sha256=digest,checker_sha256=sha(Path(__file__)))
    write(out/f'verification-{args.configuration}.json',report)
    signal.alarm(0)
    print(json.dumps({k:v for k,v in report.items() if k!='report_sha256'},indent=2))


if __name__=='__main__':main()
