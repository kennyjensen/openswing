"""Align SA-11 paper curves to frozen influences in bounded serial batches.

Original baseline/extension data and minimum-spacing cosine meshes are fixed.
The upper-winglet follow-up fills its single missing CL=.7 interpolation
bracket; it retains the already disclosed report-derived input and mesh.
"""
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
import time

ROOT = Path(__file__).resolve().parents[1]
ORIGINAL = ROOT/'artifacts/isae/sa11-original-minimum-spacing-20261108'
UPPER = ROOT/'artifacts/isae/sa11-minimum-spacing-20261108'
REUSE = ROOT/'artifacts/isae/sa11-extension-drag-budget-r2-20261108'
FIELDS = dict(lift=75, drag=76, CL=77, CD=78, CDi=79, Cm_origin=80, efficiency=81)
read = lambda p: json.loads(p.read_text())
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
utc = lambda: datetime.now(timezone.utc).isoformat()


def bounded():
    for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):
        assert os.environ.get(key) == '1'
    resource.setrlimit(resource.RLIMIT_AS,(512*1024**2,512*1024**2))
    resource.setrlimit(resource.RLIMIT_CPU,(15,15))
    signal.alarm(25)


def write(path, value):
    text = json.dumps(value, indent=2, allow_nan=False)+'\n'
    with path.open('x') as stream:
        stream.write(text)


def check(pins):
    for name, digest in pins.items():
        assert sha(ROOT/name) == digest, name


def prepare(out):
    bounded()
    assert not out.exists()
    old = read(ORIGINAL/'plan.json')
    check(old['source_sha256'])
    pins = dict(old['source_sha256'])
    parent = read(UPPER/'plan.json')
    check(parent['pins'])
    for name,digest in parent['generated_pins'].items():
        assert sha(UPPER/name)==digest
        pins[str((UPPER/name).relative_to(ROOT))]=digest
    pins.update(parent['pins'])
    catalog = read(ROOT/'docs/validation/aswing-authoritative-sources.json')
    for entry in catalog['files']:
        if entry['id'] in ('isae-part-1','drela-steady'):
            for name,key in [('local_pdf','sha256'),('local_text','text_sha256')]:
                assert sha(ROOT/entry[name])==entry[key]
                pins[entry[name]]=entry[key]
    saved = read(REUSE/'analysis.json')
    assert saved['verified'] and saved['plan_sha256']==sha(REUSE/'plan.json')
    controls = {(r['settings']['speed'],r['settings']['alpha']):r for r in saved['cases'] if r['settings']['freeze_influences']}
    assert len(controls)==4
    cases=[]
    for job in old['jobs']:
        s=job['settings']
        if not (job['variant'] in ('wing_alone','wing_extension') and job['mach_label'] in ('0_70','0_80')
                and s['panels']==64 and 0<=s['alpha']<=5.5):
            continue
        condition={k:s[k] for k in ('speed','alpha','beta','density','mach','freeze_influences',
            'stall','stall_factor','stall_width','wake_core_ratio','aero_lag','body_added_mass_factor')}
        condition['freeze_influences']=True
        reuse=None
        if job['variant']=='wing_extension' and (s['speed'],s['alpha']) in controls:
            control=controls[(s['speed'],s['alpha'])]
            assert condition==control['settings']
            directory=REUSE/control['id']
            assert sha(directory/'report.json')==control['report_sha256']
            pins[str((directory/'report.json').relative_to(ROOT))]=control['report_sha256']
            for name,digest in control['artifacts'].items():
                assert sha(directory/name)==digest
                pins[str((directory/name).relative_to(ROOT))]=digest
            reuse=str((directory/'accepted.json').relative_to(ROOT))
        cases.append(dict(id=f"{job['variant']}-m{job['mach_label']}-a{job['row_index']:02d}",
            configuration=job['variant'],label=job['mach_label'],row=job['row_index'],alpha=s['alpha'],
            model_path=job['model_path'].replace('.reference/','reference/',1),
            mesh=old['meshes'][job['model_path']]['64'],condition=condition,
            table=job['table_path'].replace('.reference/','reference/',1),tokens=job['reference_row']['tokens'],
            reused_accepted=reuse))
    assert len(cases)==92
    upper_case=parent['cases'][0]
    tokens=[l.split() for l in (ROOT/upper_case['table']).read_text().splitlines()
            if len(l.split())==82 and l.split()[0].isdigit()][21]
    cases.append(dict(id='upper_winglet-m0_70-a21',configuration='upper_winglet',label='0_70',
        row=21,alpha=5.25,model_path=str((UPPER/'model.asw').relative_to(ROOT)),
        mesh=read(UPPER/'mesh-import.json')['panels'],condition=dict(upper_case['condition'],alpha=5.25),
        table=upper_case['table'],tokens=tokens,reused_accepted=None))
    import numpy as np
    sys.path.insert(0,str(ROOT))
    from openswing.asw import parse_asw
    from openswing.geometry import model_meshes
    preflight={}
    for case in cases:
        if case['configuration'] not in preflight:
            model=parse_asw((ROOT/case['model_path']).read_text(),beam_interpolation='natural-v1')
            meshes=model_meshes(model,case['mesh'])
            assert all(b.physical_index==1 for b in model.beams)
            assert np.array_equal(model.reference[0],[.9329,.37874,2.4852])
            preflight[case['configuration']]=[
                dict(beam=m.beam.index,nodes=[float(m.t0[0]),*map(float,m.t1)],intervals=len(m.tm),
                    minimum=float(min(m.length))) for m in meshes]
            assert sum(len(m.tm) for m in meshes)<=74
        rows=[l.split() for l in (ROOT/case['table']).read_text().splitlines()
              if len(l.split())==82 and l.split()[0].isdigit()]
        assert rows[case['row']]==case['tokens']
        assert float(case['tokens'][71])==case['alpha'] and float(case['tokens'][69])==case['condition']['speed']
        case['reference']={name:float(case['tokens'][col]) for name,col in FIELDS.items()}
        for name in ('model_path','table'):
            pins[case[name]]=sha(ROOT/case[name])
    for path in (Path(__file__),ORIGINAL/'plan.json',ORIGINAL/'verification.json',UPPER/'plan.json',
                 UPPER/'analysis.json',UPPER/'verification.json',REUSE/'plan.json',REUSE/'analysis.json',
                 ROOT/'docs/validation/sa11-paper-suite.json',ROOT/'reference/aswing_doc.txt',
                 ROOT/'docs/validation/aswing-authoritative-sources.json'):
        pins[str(path.relative_to(ROOT))]=sha(path)
    check(pins)
    out.mkdir(parents=True)
    (out/'driver-used.py').write_text(Path(__file__).read_text())
    write(out/'plan.json',dict(observed_utc=utc(),cases=cases,pins=pins,preflight=preflight,
        previous_goal_turn='Progress: new48-check paper suite, 568-pin independent audit and7 scoring guards complete; declared scope change recorded. Next action is matching frozen/current settings for the actual wingtip-benefit comparison.',
        protocol='Original baseline and extension at0..5.5degrees in0.25steps,240/272m/s. Change only freeze_influences to documentedTrue on the fixed cosine64 minimum-spacing meshes. Reuse four authenticated identical frozen extension states. Add upper-winglet240m/s5.25degree state on unchanged report-derived model/mesh. No parameter fits, defaults, equations or target/tolerance changes. All48 paper targets retained.',
        source_basis='Jan PartI p35 andFig22 p39; Drela UserGuide OPER Freeze VL matrices defaultT and steady section4.6 p36. This alignment does not authenticate historical startup settings.',
        requested_states=len(cases),physical_calls=89,reused_states=4,
        limits='One BLAS thread;512MiB address-space;15CPU/25wall seconds;at most3serial physical calls per foreground invocation. No browser, Vite, build or background solver jobs.'))
    signal.alarm(0)
    print(json.dumps(dict(states=len(cases),physical_calls=89,reused=4,preflight={k:[p['intervals'] for p in v] for k,v in preflight.items()})))


def batch(out,start,count):
    bounded()
    assert 1<=count<=3
    begin=time.monotonic()
    plan=read(out/'plan.json');check(plan['pins'])
    assert 0<=start and start+count<=len(plan['cases'])
    import numpy as np
    sys.path.insert(0,str(ROOT))
    from openswing.asw import parse_asw
    from openswing.geometry import model_meshes
    from openswing.aero import FlightCondition,AnalysisError,evaluate_aerodynamics
    from openswing.frozen_influence import lifting_geometry
    rows=[]
    for case in plan['cases'][start:start+count]:
        directory=out/case['id'];assert not directory.exists()
        model=parse_asw((ROOT/case['model_path']).read_text(),beam_interpolation='natural-v1')
        meshes=model_meshes(model,case['mesh'])
        for mesh,expected in zip(meshes,plan['preflight'][case['configuration']],strict=True):
            assert [float(mesh.t0[0]),*map(float,mesh.t1)]==expected['nodes']
        condition=FlightCondition(**case['condition'])
        assert condition.freeze_influences
        g=lifting_geometry(meshes,np.array([1.,0.,0.]))
        span=np.concatenate([m.frames[...,1] for m in meshes])
        clmax=np.concatenate([m.beam.value('CLmax',m.tm) for m in meshes])
        clmin=np.concatenate([m.beam.value('CLmin',m.tm) for m in meshes])
        directory.mkdir()
        np.savez(directory/'geometry.npz',**g,span=span)
        clock=time.monotonic()
        try:
            result=read(ROOT/case['reused_accepted']) if case['reused_accepted'] else evaluate_aerodynamics(model,condition,meshes)
        except AnalysisError as exc:
            assert exc.details and exc.details['kind']=='section_normal_mach',str(exc)
            write(directory/'rejected.json',dict(message=str(exc),details=exc.details))
            row=dict(status='rejected',values=None,residual=exc.details['circulation_residual'],
                maximum_normal_mach=exc.details['maximum']['normal_mach'])
        else:
            write(directory/'accepted.json',result)
            assert result['converged'] and result['residual']<1e-8
            e,_,ez=condition.vectors()
            values={key:float(result[key]) for key in ('CL','CD','CDi','Cm_origin','efficiency')}
            values.update(lift=float(np.dot(result['force'],ez)),drag=float(np.dot(result['force'],e)))
            cl=np.array([s['cl'] for s in result['strips']])
            row=dict(status='computed',values=values,residual=result['residual'],
                maximum_normal_mach=max(s['normal_mach'] for s in result['strips']),
                minimum_stall_margin_widths=float(min(np.minimum(clmax-cl,cl-clmin)/condition.stall_width)),
                errors_percent={key:100*(value/case['reference'][key]-1) for key,value in values.items()})
        row.update(id=case['id'],case=case,observed_utc=utc(),plan_sha256=sha(out/'plan.json'),
            physical_calls=0 if case['reused_accepted'] else 1,
            elapsed_seconds=time.monotonic()-clock,peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            artifacts={p.name:sha(p) for p in directory.iterdir()})
        write(directory/'report.json',row)
        rows.append(dict(id=case['id'],report_sha256=sha(directory/'report.json')))
        print(json.dumps(dict(id=case['id'],status=row['status'],physical_calls=row['physical_calls'],
            maximum_normal_mach=row['maximum_normal_mach'],CL_error=row.get('errors_percent',{}).get('CL'),
            CD_error=row.get('errors_percent',{}).get('CD'))),flush=True)
    write(out/f'batch-{start:03d}.json',dict(observed_utc=utc(),start=start,count=count,rows=rows,
        seconds=time.monotonic()-begin,peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss))
    signal.alarm(0)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('prepare','batch'))
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--start',type=int)
    parser.add_argument('--count',type=int,default=3)
    args=parser.parse_args()
    if args.action=='prepare':prepare(args.output.resolve())
    else:batch(args.output.resolve(),args.start,args.count)
