"""Build bounded independent references and exact per-job targets for UA-2 N40."""
import argparse
import gc
import gzip
from hashlib import sha256
import json
from pathlib import Path
import shutil
import time
import numpy as np
from isae_ua2_incidence_periodic_n40 import (
    ROOT,BASE,OLD,SEED,STEPS,CYCLES,PERIOD,GATES,
    REFERENCE_INTERVALS_PER_FILE,grid,windows,full_request,
)
from isae_ua_wing_incidence_refined import AccurateInclinedWing
from isae_ua_periodic import fourier


def digest(path):
    result=sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):result.update(chunk)
    return result.hexdigest()


def write_json(path,data):
    assert not path.exists(),path
    path.write_text(json.dumps(data,indent=2,allow_nan=False)+'\n')


def write_gzip(path,data):
    assert not path.exists() and not path.with_suffix(path.suffix+'.partial').exists(),path
    partial=path.with_suffix(path.suffix+'.partial')
    with gzip.open(partial,'wt',compresslevel=1) as stream:
        stream.write(json.dumps(data,separators=(',',':'),allow_nan=False))
    partial.replace(path)


def read_gzip(path):
    with gzip.open(path,'rt') as stream:return json.load(stream)


def checked_plan():
    plan=json.loads((BASE/'reference-plan.json').read_text())
    assert plan['gates']==GATES and plan['times']==grid()
    for n,h in plan['source_sha256'].items():assert digest(ROOT/n)==h,n
    return plan


def prepare():
    assert not BASE.exists(),BASE
    previous=json.loads((ROOT/'docs/validation/isae-ua2-incidence-periodic-20261101.json').read_text())
    assert previous['passed'] and previous['audited_unique_snapshots']==7922
    production=sorted((ROOT/'openswing').glob('*.py'));assert len(production)==136
    for p in production:assert digest(p)==previous['source_sha256'][str(p.relative_to(ROOT))]
    assert json.loads((SEED.parent.parent/(SEED.parent.name+'-execution.json')).read_text())['exit_code']==0
    request=full_request();assert request['panels']==40
    from isae_ua2_incidence_periodic import full_request as original_request
    assert {k:v for k,v in request.items() if k!='panels'}=={k:v for k,v in original_request(STEPS).items() if k!='panels'}
    assert [float(line.split()[0]) for line in request['time']['forcing'].splitlines()[1:]]==grid()
    paths=[Path(__file__).resolve(),SEED,SEED.parent.parent/(SEED.parent.name+'-execution.json'),
        OLD/'audit.json',OLD/'reference.json',ROOT/'docs/validation/isae-ua2-incidence-periodic-20261101.json',
        *[ROOT/'scripts'/n for n in ('isae_ua2_incidence_periodic_n40.py','isae_ua2_incidence_periodic.py',
        'isae_ua2_incidence_time.py','isae_ua_incidence_periodic.py','isae_ua_wing_incidence_refined.py',
        'isae_ua_wing_incidence.py','isae_ua_wing_nonlinear.py','isae_ua_wing_periodic.py','isae_ua_periodic.py',
        'isae_ua_section_reference.py','isae_suite_unsteady.py')],
        ROOT/'tests/test_isae_ua_wing_incidence.py',ROOT/'.reference/asw_theory.txt',ROOT/'.reference/asw_uns_theory.txt']
    pins={str(p.relative_to(ROOT)):digest(p) for p in paths}
    BASE.mkdir(parents=True)
    plan=dict(panels=40,alpha_deg=9,k=.95,amplitude_ratio=.5,span=10.,cycles=CYCLES,
        nominal_steps=STEPS,times=grid(),gates=GATES,source_sha256=pins,
        production_sha256={str(p.relative_to(ROOT)):digest(p) for p in production},
        jobs=[dict(part=i,start_index=a,end_index=b) for i,(a,b) in enumerate(windows())],
        reference_jobs=[dict(method=m,kind=k) for m in ('DOP853','Radau') for k in ('cold','periodic')],
        per_job_timeout_seconds=45,threads=1,
        scope='Spatial refinement at the previously verified fine temporal grid; no new 40-strip temporal-order claim.',
        initial_state='Production steady equilibrium; independent periodic seeds are used only by reference methods.',
        normalization='Same cold and periodic per-strip scales and motion gates as the 20-strip study. Cold and periodic mesh comparisons use integrated fixed-axis lift at identical times, without strip interpolation.',
        native_ASWING_comparison=False,production_changed=False)
    write_json(BASE/'reference-plan.json',plan)
    for p in paths:
        if p.suffix!='.py' and p not in (ROOT/'.reference/asw_theory.txt',ROOT/'.reference/asw_uns_theory.txt'):continue
        target=BASE/'frozen-code'/p.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,target)
    # Keep an auditable, small projection of the completed 20-strip lift history.
    old=json.loads((OLD/'audit.json').read_text());assert old['passed']
    fine=old['results']['640']
    baseline=dict(cold=[dict(time=r['time'],CL=r['CL'],reference_CL=r['reference']['CL']) for r in fine['rows']],
        periodic_scale=fine['periodic_scales']['CL'],cold_scale=fine['scales']['CL'],
        source_sha256={str((OLD/'audit.json').relative_to(ROOT)):digest(OLD/'audit.json')})
    del fine,old;gc.collect()
    old_ref=json.loads((OLD/'reference.json').read_text());assert old_ref['passed']
    baseline['periodic_reference']=[dict(time=r['time'],CL=r['CL']) for r in old_ref['reference']['DOP853']['periodic']['rows']]
    baseline['source_sha256'][str((OLD/'reference.json').relative_to(ROOT))]=digest(OLD/'reference.json')
    del old_ref;gc.collect()
    write_json(BASE/'baseline-n20.json',baseline)
    print(json.dumps(dict(prepared=True,production_jobs=len(windows()),physical_steps=len(grid())-1,nominal_steps=STEPS,panels=40)))


def method_reference(method,kind):
    plan=checked_plan();folder=BASE/f'reference-{method}-{kind}'
    assert dict(method=method,kind=kind) in plan['reference_jobs']
    assert not folder.exists();folder.mkdir()
    times=grid() if kind=='cold' else (PERIOD*np.arange(STEPS+1)/STEPS).tolist()
    seed=None
    if kind=='periodic':
        old=json.loads(SEED.read_text());assert old['passed']
        seed=old['reference'][method]['periodic']['rows'][0]['circulation']
        del old;gc.collect()
    started=time.monotonic()
    result=AccurateInclinedWing(40,alpha_deg=9.).integrate(times,amplitude_ratio=.5,k=.95,method=method,initial=seed)
    seconds=time.monotonic()-started
    metadata={k:v for k,v in result.items() if k!='rows'}
    if kind=='periodic':
        states=np.array([r['circulation'] for r in result['rows']])
        closure=float(np.max(abs(states[-1]-states[0])/np.max(abs(states),axis=0)))
        assert closure<1e-10
        metadata.update(closure_fraction=closure,measured=fourier(times,[r['CL'] for r in result['rows']],PERIOD))
    chunks=[]
    for a in range(0,len(times)-1,REFERENCE_INTERVALS_PER_FILE):
        b=min(a+REFERENCE_INTERVALS_PER_FILE,len(times)-1);path=folder/f'rows-{a:05d}-{b:05d}.json.gz'
        write_gzip(path,dict(start_index=a,end_index=b,rows=result['rows'][a:b+1]))
        chunks.append(dict(path=str(path.relative_to(BASE)),start_index=a,end_index=b,sha256=digest(path)))
    checked_plan()
    output=dict(passed=True,method=method,kind=kind,seconds=seconds,metadata=metadata,chunks=chunks,
        reference_plan_sha256=digest(BASE/'reference-plan.json'),native_ASWING_comparison=False)
    write_json(folder/'report.json',output)
    print(json.dumps(dict(passed=True,method=method,kind=kind,seconds=seconds,rows=len(times),chunks=len(chunks),closure=metadata.get('closure_fraction'))))


def verify():
    plan=checked_plan();assert not (BASE/'reference-verified.json').exists()
    reports={};inputs={};differences={};targets={};periodic=[]
    for item in plan['reference_jobs']:
        name=f"reference-{item['method']}-{item['kind']}";p=BASE/name/'report.json';receipt=BASE/(name+'-execution.json')
        execution=json.loads(receipt.read_text());assert execution['exit_code']==0
        r=json.loads(p.read_text());assert r['passed'] and r['reference_plan_sha256']==digest(BASE/'reference-plan.json')
        reports[(item['method'],item['kind'])]=r
        for q in (p,receipt):inputs[str(q.relative_to(ROOT))]=digest(q)
    for kind in ('cold','periodic'):
        numerators={k:0. for k in ('CL','circulation','circulation_rate')};denominators={k:0. for k in numerators}
        pair=[reports[(m,kind)] for m in ('DOP853','Radau')]
        assert len(pair[0]['chunks'])==len(pair[1]['chunks'])
        for left,right in zip(pair[0]['chunks'],pair[1]['chunks']):
            assert (left['start_index'],left['end_index'])==(right['start_index'],right['end_index'])
            data=[]
            for c in (left,right):
                p=BASE/c['path'];assert digest(p)==c['sha256'];inputs[str(p.relative_to(ROOT))]=digest(p);data.append(read_gzip(p)['rows'])
            for key in numerators:
                x,y=(np.array([r[key] for r in rows]) for rows in data)
                numerators[key]=np.maximum(numerators[key],np.max(abs(x-y),axis=0))
                denominators[key]=np.maximum(denominators[key],np.max(abs(y),axis=0))
            trimmed=[{k:r[k] for k in ('time','displacement','velocity','acceleration','circulation','circulation_rate','CL','CF')} for r in data[0]]
            if kind=='cold':
                for job in plan['jobs']:
                    a,b=job['start_index'],job['end_index']
                    if a>=left['start_index'] and b<=left['end_index']:
                        rows=trimmed[a-left['start_index']:b-left['start_index']+1]
                        assert [r['time'] for r in rows]==plan['times'][a:b+1]
                        path=BASE/'reference-parts'/f"part{job['part']:03d}.json"
                        path.parent.mkdir(exist_ok=True);write_json(path,dict(job=job,rows=rows,source_chunk_sha256=left['sha256']))
                        targets[str(job['part'])]=dict(path=str(path.relative_to(BASE)),sha256=digest(path))
            else:periodic.extend(trimmed if left['start_index']==0 else trimmed[1:])
        for key in numerators:
            assert np.min(denominators[key])>0
            differences[kind+'_'+key]=float(np.max(numerators[key]/denominators[key]))
    assert len(targets)==len(windows()) and len(periodic)==STEPS+1
    assert max(differences.values())<GATES['reference_agreement_fraction']
    write_json(BASE/'periodic-reference.json',dict(rows=periodic,metadata=reports[('DOP853','periodic')]['metadata']))
    for n,h in inputs.items():assert digest(ROOT/n)==h,n
    checked_plan()
    output=dict(passed=True,method_differences=differences,reference_parts=targets,input_sha256=inputs,
        source_sha256=plan['source_sha256'],reference_plan_sha256=digest(BASE/'reference-plan.json'),
        periodic_reference_sha256=digest(BASE/'periodic-reference.json'),baseline_n20_sha256=digest(BASE/'baseline-n20.json'),
        native_ASWING_comparison=False)
    write_json(BASE/'reference-verified.json',output)
    print(json.dumps(dict(passed=True,differences=differences,production_reference_parts=len(targets))))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('action',choices=('prepare','method','verify'))
    parser.add_argument('--method',choices=('DOP853','Radau'));parser.add_argument('--kind',choices=('cold','periodic'))
    args=parser.parse_args()
    if args.action=='prepare':prepare()
    elif args.action=='verify':verify()
    else:
        if not args.method or not args.kind:parser.error('Method and kind required')
        method_reference(args.method,args.kind)
