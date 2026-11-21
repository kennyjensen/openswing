"""Third-resolution AE-1 comparison; retain the original spacing probes intact.

Three serial nominal-160 states at 5deg/17m/s. No primary votes or defaults change.
"""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import math
from pathlib import Path
import resource
import signal
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts import probe_isae_ae1_spacing as common
from scripts import isae_suite_ae1 as adapter
from scripts.finalize_isae_ae1_saved import RAW_FILES,validate_saved

read,save,sha=common.read,common.save,common.sha


def prepare(out):
    parent=ROOT/'artifacts/isae/ae1-spacing-current-20261110'
    old=common.checked_plan(parent)
    pins=dict(old['pins'])
    for p in [parent/'plan.json',parent/'assessment.json',parent/'verification.json',Path(__file__)]:
        pins[str(p)]=sha(p)
    folder=ROOT/'artifacts/isae/ae1-full-current-20261110/AE-1-a05-row018-m80-frozen'
    canonical=read(folder/'job.json');adapter.verify_reference_sources(ROOT,canonical)
    jobs=[];n=160
    for kind in ('cosine','whole','mirror-half'):
        if kind=='cosine':
            s=[.55*(1-math.cos(math.pi*j/n))/2 for j in range(n+1)]
            t=[.0001+v*(.52-.0001)/.52 if v<=.52 else v for v in s]
            t[0],t[-1]=.0001,.55
        else:
            t,s=common.nodes(kind,n)
        job=deepcopy(canonical)
        job.update(id=f'AE-1-refinement-{kind}-m160',nominal=n,mesh='m160',
            panels=dict(default=n,beams={'1':dict(nodes=t)}),expected_elements=n+1,expected_nodes=n+2,
            mesh_scope='Unscored third resolution; original native NODE I40 mesh remains unknown.',
            reference_scope='Unscored same-condition refinement; original targets retained.')
        assert {k for k in job if job[k]!=canonical[k]}=={
            'id','nominal','mesh','panels','expected_elements','expected_nodes','mesh_scope','reference_scope'}
        jobs.append(dict(job=job,kind=kind,material_y=s,parent_folder=str(folder)))
    out.mkdir(parents=True)
    save(out/'plan.json',dict(observed_utc=datetime.now(timezone.utc).isoformat(),purpose=__doc__,
        pins=pins,jobs=jobs,parent=str(parent),primary_votes_added=0,limits=old['limits'],
        required_preflight='cosine-check.json',qualifications=old['qualifications']+[
            'Only one nominal-160 state per named grid; no new speed sweep.',
            'Require independent default-versus-explicit cosine mesh equivalence before numerical launches.',
            'Report successive changes and grid spread; do not fit or apply a continuum correction.']))
    common.checked_plan(out)
    print('Prepared three nominal-160 states with unchanged physical settings.')


def check_cosine(out):
    plan=common.checked_plan(out);job=plan['jobs'][0]['job']
    import numpy as np
    from openswing.asw import parse_asw
    from openswing.geometry import mesh_beam
    model=parse_asw(Path(job['source']).read_text(),beam_interpolation=job['settings']['beam_interpolation'])
    beam=model.beams[0];explicit=mesh_beam(beam,job['panels'])
    generated=mesh_beam(beam,dict(default=160,beams={'1':dict(count=160,spacing='cosine')}))
    errors={name:float(np.max(abs(getattr(explicit,name)-getattr(generated,name))))
            for name in ('t0','t1','tm','ts','r0','r1','rm','frames','length','theta')}
    assert all(value<2e-12 for value in errors.values()),errors
    assert len(explicit.t0)==len(generated.t0)==161
    common.checked_plan(out)
    save(out/'cosine-check.json',dict(observed_utc=datetime.now(timezone.utc).isoformat(),passed=True,
        max_errors=errors,tolerance=2e-12,elements=161,plan_sha256=sha(out/'plan.json'),physical_solves=0))
    print(errors)


def check_preflight(out):
    plan=common.checked_plan(out);record=read(out/'cosine-check.json')
    assert record['passed'] and record['physical_solves']==0
    assert record['plan_sha256']==sha(out/'plan.json')
    assert all(e<2e-12 for e in record['max_errors'].values())
    return plan


def assess(out):
    plan=check_preflight(out);rows=[];checks=0;receipts=[];pins={}
    parent=read(Path(plan['parent'])/'assessment.json')
    rows.extend(dict(kind=r['kind'],mesh=r['mesh'],name=r['name'],expected=r['expected'],predicted=r['predicted'])
                for r in parent['rows'])
    rows.extend(dict(kind='cosine',mesh=r['mesh'],name=r['name'],expected=r['expected'],predicted=r['cosine_predicted'])
                for r in parent['rows'] if r['kind']=='whole')
    for index,entry in enumerate(plan['jobs']):
        folder=out/f'job-{index:02d}';job=entry['job']
        assert read(folder/'terminal.json')['returncode']==0
        packet={name:read(folder/'raw'/name) for name in RAW_FILES}
        values,physical=validate_saved(job,packet);checks+=len(physical)
        receipt=read(folder/'receipt.json');assert receipt['values']==values;receipts.append(receipt)
        for target in job['observations']:
            rows.append(dict(kind=entry['kind'],mesh=160,name=target['name'],expected=target['expected'],predicted=values[target['name']]))
        pins.update({str(p):sha(p) for p in folder.rglob('*') if p.is_file()})
    assert checks==87 and len(rows)==54
    assert len({(r['kind'],r['mesh'],r['name']) for r in rows})==54
    changes=[]
    for kind in ('cosine','whole','mirror-half'):
        for name in adapter.NAMES:
            selected=sorted((r for r in rows if r['kind']==kind and r['name']==name),key=lambda r:r['mesh'])
            assert [r['mesh'] for r in selected]==[40,80,160]
            assert len({r['expected'] for r in selected})==1
            values=[r['predicted'] for r in selected];coarse=values[1]-values[0];fine=values[2]-values[1]
            changes.append(dict(kind=kind,name=name,coarse_change=coarse,fine_change=fine,
                same_direction=coarse*fine>0,change_ratio=abs(fine/coarse) if coarse else None))
    for r in rows:
        r['signed_error']=r['predicted']-r['expected']
        r['error_percent']=100*abs(r['signed_error'])/abs(r['expected'])
    spread=[dict(name=name,mesh=n,spread=max(r['predicted'] for r in rows if r['name']==name and r['mesh']==n)
                -min(r['predicted'] for r in rows if r['name']==name and r['mesh']==n))
            for name in adapter.NAMES for n in (40,80,160)]
    assert not any(n=='openswing' or n.startswith('openswing.') for n in sys.modules)
    save(out/'assessment.json',dict(observed_utc=datetime.now(timezone.utc).isoformat(),status='REFINEMENT_AUDIT_PASS',
        plan_sha256=sha(out/'plan.json'),physical_checks_passed=87,rows=rows,successive_changes=changes,
        grid_spread=spread,receipts=receipts,artifact_sha256=pins,physical_calls=0,production_imports=0,
        primary_votes_added=0,continuum_correction_applied=False,historical_mesh_recovered=False))
    print('All 87 physical checks pass; three-grid refinement audited.')
    for r in rows:
        if r['name']=='sensor3_RZ_earth_m':print(r['kind'],r['mesh'],'tip Z error (um):',1e6*r['signed_error'])
    print('Tip-Z successive changes:',[r for r in changes if r['name']=='sensor3_RZ_earth_m'])


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=['prepare','check-cosine','launch','assess'])
    p.add_argument('--output',type=Path,required=True);p.add_argument('--index',type=int,default=0)
    a=p.parse_args();out=a.output.resolve()
    if a.action=='launch':
        check_preflight(out);raise SystemExit(common.launch(out,a.index))
    resource.setrlimit(resource.RLIMIT_AS,(512*1024**2,)*2)
    resource.setrlimit(resource.RLIMIT_CPU,(15,)*2);signal.alarm(25)
    {'prepare':prepare,'check-cosine':check_cosine,'assess':assess}[a.action](out)
