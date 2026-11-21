"""Refresh all original SA-11 polar targets using small serial foreground jobs."""
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import gc
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import signal
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
import isae_suite_sa11 as ADAPTER
from isae_acceptance import apply_reference_acceptance
SPEC=importlib.util.spec_from_file_location('suite_runner',ROOT/'scripts/run-isae-suite.py')
RUNNER=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(RUNNER)
read=lambda p:json.loads(p.read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
utc=lambda:datetime.now(timezone.utc).isoformat()


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x') as f:json.dump(value,f,indent=2,allow_nan=False);f.write('\n')


def check(plan):
    for path,expected in plan['source_sha256'].items():assert sha(ROOT/path)==expected,path


def prepare(out):
    assert not out.exists(),out
    jobs=ADAPTER.plan(ROOT)
    old_path=ROOT/'artifacts/isae/sa11-focus-20261107/plan.json';old_plan=read(old_path)
    old={j['id']:j for j in old_plan['jobs']}
    for j in jobs:
        if j['id'] not in old:continue
        assert all(j[k]==old[j['id']][k] for k in ('settings','model_path','table_path','driver_path','reference_row','expected_outputs','execution_route'))
    assert len(old)==656 and len(jobs)==1312
    jobs.sort(key=lambda j:(j['execution_route']!='unsupported',j['variant'],j['mach_label'],j['row_index'],j['settings']['panels']))
    pins={str(p.relative_to(ROOT)):sha(p) for p in (ROOT/'openswing').glob('*.py')}
    for p in [Path(__file__),*[ROOT/'scripts'/name for name in ('isae_suite_sa11.py','isae_suite_polars.py','isae_suite_extra_polars.py','isae_acceptance.py','run-isae-suite.py')],ROOT/'reference/aswing_doc.txt']:
        pins[str(p.relative_to(ROOT))]=sha(p)
    # Independent literal preflight: parse/mesh only, no aerodynamic calls.
    from openswing.asw import parse_asw
    from openswing.geometry import model_meshes
    preflight={}
    for variant in ADAPTER.VARIANTS:
        job=next(j for j in jobs if j['variant']==variant);path=ROOT/job['model_path']
        record=dict(model_path=job['model_path'],sha256=sha(path),stage='parse')
        try:
            model=parse_asw(path.read_text(),beam_interpolation='natural-v1');record['stage']='mesh'
            record['beam_domains']={str(b.index):[float(v) for v in b.domain] for b in model.beams}
            record['joint_rows']=[r.tolist() for r in model.records.get('joint',[])]
            meshes=model_meshes(model,64);record.update(status='ready',intervals=sum(len(m.tm) for m in meshes))
        except Exception as e:record.update(status='blocked',error_type=type(e).__name__,error=str(e))
        assert (record['status']=='blocked')==(variant in ADAPTER.INPUT_BLOCKS)
        preflight[variant]=record
    tables=[]
    for table in sorted({j['table_path'] for j in jobs}):
        group=[j for j in jobs if j['table_path']==table and j['settings']['panels']==64]
        assert len(group)==41
        literal=[line.split() for line in (ROOT/table).read_text().splitlines() if line.split() and len(line.split())==82 and line.split()[0].isdigit()]
        assert len(literal)==41 and all(r==j['reference_row']['tokens'] for r,j in zip(literal,group))
        tables.append(dict(path=table,sha256=sha(ROOT/table),variant=group[0]['variant'],label=group[0]['mach_label'],
            rows=41,required=574,blocker_codes=group[0]['blocker_codes'],
            settings_commands=group[0]['driver_declarations']['settings_commands'],
            normalization_area_range={c:[min(j['normalization_evidence']['channels'][c]['implied_area_at_literal_density'] for j in group),
                max(j['normalization_evidence']['channels'][c]['implied_area_at_literal_density'] for j in group)] for c in ('lift','drag')},
            normalization_interval_misses={c:[j['row_index'] for j in group if not j['normalization_evidence']['channels'][c]['literal_qS_inside']] for c in ('lift','drag')}))
    changed_old=[p for p,h in old_plan['source_sha256'].items() if sha(ROOT/p)!=h]
    plan=dict(observed_utc=utc(),jobs=jobs,source_sha256=pins,required_outputs=9184,physical_calls=328,unsupported=984,
        old_plan_sha256=sha(old_path),old_source_changes=changed_old,old_predictions_reused=False,
        preflight=preflight,tables=tables,threads=1,physical_calls_per_batch=8,per_solve_seconds=30,
        policy='All16 original tables, four paired inputs, all41 rows and seven outputs on64/128 requested meshes. Fresh current baseline/extension solves; no original winglet repair or alternative twist substitution. Existing5% reference allowance and numerical/local-Mach gates. New blocker classes retain every target; overlapping normalization/input blockers are explicit.',
        unpaired='Wing_tip_up_cant0/wingtip_up_cant0.asw has no paired archived polar. The extra Wing_tip_up/wing_alone_polar_Ma_0_80.sh is not the driver paired by filename/model/output with the upper-winglet table.')
    out.mkdir(parents=True);check(plan);write(out/'plan.json',plan)
    (out/'driver-used.py').write_text(Path(__file__).read_text())
    print(json.dumps(dict(prepared=True,jobs=len(jobs),required=9184,unsupported=984,physical_calls=328,preflight=preflight)))


def batch(out):
    assert all(os.environ.get(k)=='1' for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'))
    plan=read(out/'plan.json');check(plan)
    started=time.monotonic();calls=0;finished=[]
    def expired(*args):raise TimeoutError('Foreground per-solve30-second limit')
    signal.signal(signal.SIGALRM,expired)
    for i,j in enumerate(plan['jobs']):
        path=out/'jobs'/f'{i:04}'/'result.json'
        if path.exists():continue
        begin=time.monotonic();signal.alarm(30)
        try:strict=RUNNER.checked_result(j,ADAPTER.run(ROOT,j))
        finally:signal.alarm(0)
        scored=apply_reference_acceptance(strict)
        write(path,dict(job_id=j['id'],observed_utc=utc(),strict=strict,acceptance=scored,
                       seconds=time.monotonic()-begin,plan_sha256=sha(out/'plan.json')))
        finished.append(dict(index=i,path=str(path.relative_to(ROOT)),sha256=sha(path),status=strict['status'],passed=scored['output_accounting']['passed']))
        if j['execution_route']!='unsupported':calls+=1
        del strict,scored;gc.collect()
        if calls>=8 or len(finished)>=128 or time.monotonic()-started>=25:break
    check(plan)
    write(out/'batches'/f'{time.time_ns()}.json',dict(observed_utc=utc(),finished=finished,physical_calls=calls,
        seconds=time.monotonic()-started,plan_sha256=sha(out/'plan.json'),no_child_processes=True))
    done=sum((out/'jobs'/f'{i:04}'/'result.json').exists() for i in range(len(plan['jobs'])))
    print(json.dumps(dict(finished=done,required_jobs=len(plan['jobs']),batch_jobs=len(finished),physical_calls=calls,
        seconds=time.monotonic()-started,results=[{k:r[k] for k in ('index','status','passed')} for r in finished if r['status']!='unsupported'])),flush=True)


def analyze(out):
    plan=read(out/'plan.json');check(plan)
    groups={};statuses=Counter();error_kinds=Counter();passes=required=0;pins={};errors=defaultdict(list);timings=[]
    old_base=ROOT/'artifacts/isae/sa11-focus-20261107';old_plan=read(old_base/'plan.json')
    old_analysis=read(old_base/'analysis.json')
    old={j['id']:old_base/'jobs'/f'{i:03}'/'result.json' for i,j in enumerate(old_plan['jobs'])}
    changed_predictions=defaultdict(float);status_changes=[]
    for i,j in enumerate(plan['jobs']):
        path=out/'jobs'/f'{i:04}'/'result.json';r=read(path)
        assert r['job_id']==j['id'] and r['plan_sha256']==sha(out/'plan.json')
        assert r['strict']==RUNNER.checked_result(j,r['strict'])
        scored=apply_reference_acceptance(r['strict']);assert scored==r['acceptance']
        count=scored['output_accounting'];assert count['required']==7
        passes+=count['passed'];required+=7;statuses[r['strict']['status']]+=1
        key=j['variant']+':'+j['mach_label']
        g=groups.setdefault(key,dict(passed=0,required=0,statuses=Counter(),blocker_codes=j['blocker_codes']))
        g['passed']+=count['passed'];g['required']+=7;g['statuses'][r['strict']['status']]+=1
        pins[str(path.relative_to(ROOT))]=sha(path)
        if j['execution_route']!='unsupported':timings.append(r['seconds'])
        if r['strict']['status']=='error':
            error=str(r['strict'].get('error',''));error_kinds['section_normal_mach' if 'Local section-normal Mach' in error else error]+=1
        for c in scored.get('reference_checks',[]):
            if r['strict']['status']=='computed' and not c['passed'] and c.get('relative_error') is not None:
                errors[c['name']].append(100*c['relative_error'])
        if j['id'] in old:
            previous=old[j['id']];assert sha(previous)==old_analysis['result_sha256'][str(previous.relative_to(ROOT))]
            saved=read(previous)['strict']
            if saved['status']!=r['strict']['status']:status_changes.append(dict(id=j['id'],before=saved['status'],after=r['strict']['status']))
            before={c['name']:c for c in saved.get('reference_checks',[])}
            for c in r['strict'].get('reference_checks',[]):
                value=before.get(c['name'],{}).get('predicted')
                if value is not None and c.get('predicted') is not None:
                    changed_predictions[c['name']]=max(changed_predictions[c['name']],abs(c['predicted']-value)/max(1,abs(value)))
    assert required==9184 and len(pins)==1312
    import statistics
    result=dict(observed_utc=utc(),passed=passes,required=required,statuses=dict(statuses),error_kinds=dict(error_kinds),groups=groups,
        failed_percent_errors={k:dict(count=len(v),median=statistics.median(v),minimum=min(v),maximum=max(v)) for k,v in errors.items()},
        physical_seconds=sum(timings),maximum_physical_job_seconds=max(timings),fresh_physical_calls=len(timings),
        old_status_changes=status_changes,maximum_scaled_prediction_change=dict(changed_predictions),
        original_normalization_conflict_jobs=sum(j['normalization_conflict'] for j in plan['jobs']),
        original_input_blocker_jobs=sum(j['input_issue'] is not None for j in plan['jobs']),
        both_blockers_jobs=sum(j['normalization_conflict'] and j['input_issue'] is not None for j in plan['jobs']),
        result_sha256=pins,plan_sha256=sha(out/'plan.json'),source_sha256=plan['source_sha256'],
        production_equations_changed=False,comparison_scope_expanded=True,full_family_validated=False)
    write(out/'analysis.json',result)
    print(json.dumps({k:v for k,v in result.items() if k not in ('result_sha256','source_sha256')}))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    p.add_argument('action',choices=('prepare','batch','analyze'));args=p.parse_args()
    globals()[args.action](args.output.resolve())
