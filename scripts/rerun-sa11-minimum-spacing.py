"""Rerun the full original SA-11 scope with only a minimum mesh interval.

All original 1,312 requests / 9,184 targets remain. One foreground process at
a time: up to three solves, or 128 unsupported records. No model repair.
"""
import argparse
from collections import Counter, defaultdict
from copy import deepcopy
from datetime import datetime, timezone
import gc
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import resource
import signal
import statistics
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
import isae_suite_sa11 as ADAPTER
from isae_acceptance import apply_reference_acceptance
spec=importlib.util.spec_from_file_location('suite_runner',ROOT/'scripts/run-isae-suite.py')
RUNNER=importlib.util.module_from_spec(spec);spec.loader.exec_module(RUNNER)
OLD=ROOT/'artifacts/isae/sa11-complete-scope-20261108'
MINIMUM=0.0164659927127284
read=lambda p:json.loads(p.read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
utc=lambda:datetime.now(timezone.utc).isoformat()


def bounded():
    for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):assert os.environ.get(key)=='1'
    resource.setrlimit(resource.RLIMIT_AS,(512*1024**2,512*1024**2))
    resource.setrlimit(resource.RLIMIT_CPU,(15,15));signal.alarm(25)


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x') as stream:json.dump(value,stream,indent=2,allow_nan=False);stream.write('\n')


def check(plan):
    for name,digest in plan['source_sha256'].items():assert sha(ROOT/name)==digest,name


def applied(job,meshes):
    result=deepcopy(job);count=job['settings']['panels']
    result['settings']['panels']=deepcopy(meshes[job['model_path']][str(count)])
    result['settings']['mesh_source']=f'Original cosine {count} request with minimum material interval {MINIMUM} model length units on every logical beam; mandatory stations retained.'
    result['minimum_spacing']=MINIMUM
    return result


def prepare(out):
    bounded();assert not out.exists(),out
    jobs=ADAPTER.plan(ROOT);old_plan=read(OLD/'plan.json');old={j['id']:j for j in old_plan['jobs']}
    for job in jobs:
        assert all(job[k]==old[job['id']][k] for k in ('settings','model_path','table_path','driver_path','reference_row','expected_outputs','execution_route','blocker_codes'))
    jobs.sort(key=lambda j:(j['execution_route']!='unsupported',j['variant'],j['mach_label'],j['row_index'],j['settings']['panels']))
    meshes={}
    for name in {j['model_path'] for j in jobs}:
        indices=re.findall(r'^\s*Beam\s+(\d+)',(ROOT/name).read_text(),re.M|re.I)
        assert len(set(indices))==len(indices) and indices
        meshes[name]={str(n):dict(default=n,beams={i:dict(count=n,spacing='cosine',min_spacing=MINIMUM) for i in indices}) for n in ADAPTER.GRIDS}
    pins={str(p.relative_to(ROOT)):sha(p) for p in (ROOT/'openswing').glob('*.py')}
    for p in [Path(__file__),OLD/'plan.json',OLD/'analysis.json',ROOT/'reference/aswing_doc.txt',
              *[ROOT/'scripts'/s for s in ('isae_suite_sa11.py','isae_suite_polars.py','isae_suite_extra_polars.py','isae_acceptance.py','run-isae-suite.py')],
              ROOT/'docs/validation/aswing-authoritative-sources.json',ROOT/'docs/validation/isae-sa11-sources.json']:
        pins[str(p.relative_to(ROOT))]=sha(p)
    for j in jobs:
        for s in j['sources']:pins[s['path']]=s['sha256']
    from openswing.asw import parse_asw
    from openswing.geometry import model_meshes
    preflight={}
    for variant in ADAPTER.VARIANTS:
        job=next(j for j in jobs if j['variant']==variant);name=job['model_path'];record=dict(stage='parse',model=name)
        try:
            model=parse_asw((ROOT/name).read_text(),beam_interpolation='natural-v1');record['stage']='mesh';grids={}
            for n in ADAPTER.GRIDS:
                grid=model_meshes(model,meshes[name][str(n)])
                assert all(min(m.length)>=MINIMUM-1e-12 for m in grid)
                grids[str(n)]=dict(intervals=[len(m.tm) for m in grid],minimum_interval=min(float(min(m.length)) for m in grid))
            record.update(status='ready',grids=grids)
        except Exception as exc:record.update(status='blocked',error_type=type(exc).__name__,error=str(exc))
        assert (record['status']=='blocked')==(variant in ADAPTER.INPUT_BLOCKS)
        preflight[variant]=record
    assert len(jobs)==1312 and sum(j['expected_outputs'] for j in jobs)==9184
    plan=dict(observed_utc=utc(),jobs=jobs,meshes=meshes,minimum_spacing=MINIMUM,source_sha256=pins,preflight=preflight,
              required_outputs=9184,physical_calls=328,unsupported=984,old_plan_sha256=sha(OLD/'plan.json'),
              previous_goal_turn='Progress: minimum spacing is implemented, upper-only diagnostic passes294/294, and upper/lower tests isolate separate source/stall/root issues.',
              request='User explicitly requested rerunning the original comparison with the new meshing limit.',
              policy='Only meshing gains minimum interval 0.0164659927127284 on all logical beams. All16 original tables, four inputs,41rows,seven fields,cosine64/128 requests, natural-v1, current-wind influences, true-speed PG, density, stall, force conventions,5% and numerical gates unchanged. Original input and normalization blockers remain required; no joint/twist repair or rescaling.',
              limits='One process, BLAS1,512MiB AS,15sCPU,25s wall; max3 physical calls or128 blocked rows per batch. No background jobs or browser/build tests.')
    out.mkdir(parents=True);check(plan);write(out/'plan.json',plan)
    (out/'driver-used.py').write_text(Path(__file__).read_text());signal.alarm(0)
    print(json.dumps(dict(prepared=True,required=9184,physical_calls=328,unsupported=984,preflight=preflight)),flush=True)


def batch(out,start,count):
    bounded();begin=time.monotonic();plan=read(out/'plan.json');check(plan);digest=sha(out/'plan.json')
    selected=plan['jobs'][start:start+count]
    assert len(selected)==count and 0<=start and 1<=count<=128
    physical=sum(j['execution_route']!='unsupported' for j in selected)
    assert physical<=3 and (physical==0 or count<=3)
    results=[]
    for index,base in enumerate(selected,start):
        folder=out/'jobs'/f'{index:04d}';assert not folder.exists(),folder
        job=applied(base,plan['meshes']);clock=time.monotonic()
        if base['execution_route']=='unsupported':
            strict=ADAPTER.validate_blocked(ROOT,base)
            strict['requested_mesh']=job['settings']['panels']
        else:
            # Authenticate the complete original target/settings before applying
            # the one predeclared meshing change. Never relax adapter validation.
            ADAPTER._canonical(ROOT,base)
            strict=ADAPTER.polar.run(ROOT,job)
            strict.update(required_outputs=list(ADAPTER.OUTPUTS),expected_outputs=7,complete_family_reproduction=False,
                          normalization_evidence=base['normalization_evidence'],normalization_conflict=False,
                          archived_stall_flag=base['archived_stall_flag'],minimum_spacing=MINIMUM)
        strict=RUNNER.checked_result(job,strict);scored=apply_reference_acceptance(strict)
        assert scored['output_accounting']['required']==7
        write(folder/'result.json',dict(job_id=job['id'],observed_utc=utc(),strict=strict,acceptance=scored,
            seconds=time.monotonic()-clock,plan_sha256=digest,minimum_spacing=MINIMUM))
        results.append(dict(index=index,sha256=sha(folder/'result.json'),status=strict['status'],passed=scored['output_accounting']['passed']))
        del strict,scored;gc.collect()
    write(out/'batches'/f'{start:04d}.json',dict(observed_utc=utc(),start=start,count=count,results=results,physical_calls=physical,
        seconds=time.monotonic()-begin,maxrss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,plan_sha256=digest))
    signal.alarm(0)
    print(json.dumps(dict(start=start,count=count,physical_calls=physical,passed=sum(r['passed'] for r in results),
        statuses=dict(Counter(r['status'] for r in results)),seconds=time.monotonic()-begin)),flush=True)


def analyze(out):
    bounded();plan=read(out/'plan.json');check(plan);digest=sha(out/'plan.json')
    old_plan=read(OLD/'plan.json');old_by_id={j['id']:i for i,j in enumerate(old_plan['jobs'])};old_analysis=read(OLD/'analysis.json')
    groups={};statuses=Counter();error_kinds=Counter();errors=defaultdict(list);pins={};changes=[];timings=[];passed=0;gained=lost=0;counts=Counter()
    for i,base in enumerate(plan['jobs']):
        path=out/'jobs'/f'{i:04d}'/'result.json';r=read(path);assert r['job_id']==base['id'] and r['plan_sha256']==digest
        job=applied(base,plan['meshes']);assert r['strict']==RUNNER.checked_result(job,r['strict'])
        scored=apply_reference_acceptance(r['strict']);assert scored==r['acceptance'];accounting=scored['output_accounting'];assert accounting['required']==7
        passed+=accounting['passed'];statuses[r['strict']['status']]+=1;pins[str(path.relative_to(ROOT))]=sha(path)
        key=base['variant']+':'+base['mach_label'];g=groups.setdefault(key,dict(passed=0,required=0,statuses=Counter(),blocker_codes=base['blocker_codes']))
        g['passed']+=accounting['passed'];g['required']+=7;g['statuses'][r['strict']['status']]+=1
        if base['execution_route']!='unsupported':timings.append(r['seconds'])
        if r['strict']['status']=='error':
            message=r['strict'].get('error','');error_kinds['section_normal_mach' if 'Local section-normal Mach' in message else message]+=1
        if r['strict']['status']=='computed':
            assert r['strict']['settings']==job['settings']
            counts[str(r['strict']['result']['panels'])]+=1
            for c in scored['reference_checks']:
                if not c['passed'] and c.get('relative_error') is not None:errors[c['name']].append(100*c['relative_error'])
        old_path=OLD/'jobs'/f"{old_by_id[base['id']]:04d}"/'result.json'
        assert sha(old_path)==old_analysis['result_sha256'][str(old_path.relative_to(ROOT))]
        before=read(old_path);old_checks={c['name']:c for c in before['acceptance']['reference_checks']}
        new_checks={c['name']:c for c in scored.get('reference_checks',[])}
        old_numerical=before['strict'].get('numerical_pass') is True;new_numerical=r['strict'].get('numerical_pass') is True
        for name in ADAPTER.OUTPUTS:
            old_pass=bool(old_numerical and old_checks.get(name,{}).get('passed'));new_pass=bool(new_numerical and new_checks.get(name,{}).get('passed'))
            gained+=new_pass and not old_pass;lost+=old_pass and not new_pass
        if before['strict']['status']!=r['strict']['status']:changes.append(dict(id=base['id'],before=before['strict']['status'],after=r['strict']['status']))
    batches=[read(p) for p in sorted((out/'batches').glob('*.json'))]
    assert sorted(r['index'] for b in batches for r in b['results'])==list(range(1312))
    for b in batches:
        assert b['plan_sha256']==digest
        for r in b['results']:assert sha(out/'jobs'/f"{r['index']:04d}"/'result.json')==r['sha256']
    assert len(pins)==1312 and sum(g['required'] for g in groups.values())==9184
    assert passed==old_analysis['passed']+gained-lost
    result=dict(observed_utc=utc(),passed=passed,required=9184,previous_passed=old_analysis['passed'],gained=gained,lost=lost,statuses=dict(statuses),error_kinds=dict(error_kinds),groups=groups,
        failed_percent_errors={k:dict(count=len(v),median=statistics.median(v),minimum=min(v),maximum=max(v)) for k,v in errors.items()},
        computed_actual_panel_counts=dict(counts),physical_seconds=sum(timings),maximum_physical_job_seconds=max(timings),fresh_physical_calls=len(timings),
        status_changes=changes,maximum_batch_seconds=max(b['seconds'] for b in batches),peak_rss_kib=max(b['maxrss_kib'] for b in batches),
        result_sha256=pins,plan_sha256=digest,source_sha256=plan['source_sha256'],production_equations_changed=False,
        comparison_targets_changed=False,full_family_validated=False,minimum_spacing=MINIMUM)
    write(out/'analysis.json',result);signal.alarm(0)
    print(json.dumps({k:v for k,v in result.items() if k not in ('result_sha256','source_sha256','status_changes')},indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('action',choices=('prepare','batch','analyze'));parser.add_argument('--start',type=int);parser.add_argument('--count',type=int)
    args=parser.parse_args();out=args.output.resolve()
    if args.action=='batch':batch(out,args.start,args.count)
    else:globals()[args.action](out)
