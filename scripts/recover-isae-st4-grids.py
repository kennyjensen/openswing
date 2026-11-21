"""Finish original ST-4 grids serially, retaining verified coarse outputs.

Reuses the existing adapter's request, verification and mesh-comparison methods.
The only execution change is one mesh per child; no equation or gate changes.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'artifacts/isae/st1-st6-current-20261103/modes'
REC=BASE/'grid-recovery'
spec=importlib.util.spec_from_file_location('suite',ROOT/'scripts/run-isae-suite.py')
suite=importlib.util.module_from_spec(spec);spec.loader.exec_module(suite)
import isae_suite_modes as modes
read=lambda p:json.loads(Path(p).read_text())
write=suite.write_json


def verify(plan):
    assert suite.stable_code(ROOT,plan['code_sha256'])
    for p,d in plan['input_sha256'].items():assert suite.digest(ROOT/p)==d,p


def prepare():
    source=read(BASE/'plan.json');assert suite.stable_code(ROOT,source['code_sha256'])
    REC.mkdir();pins={str((BASE/'plan.json').relative_to(ROOT)):suite.digest(BASE/'plan.json')}
    folders={};units=[];original_paths={}
    for job in source['jobs']:
        key=hashlib.sha256(job['id'].encode()).hexdigest()[:20]
        path=BASE/'jobs'/key/'result.json';old=read(path)
        assert old['execution_completed'] and old['job_id']==job['id']
        pins[str(path.relative_to(ROOT))]=suite.digest(path)
        original_paths[job['id']]=str(path.relative_to(ROOT))
        if job['execution_route']=='unsupported':continue
        assert old['status']=='timeout'
        found=list((path.parent/'artifacts').glob('*/n16'));assert len(found)==1
        coarse=found[0];report=read(coarse/'report.json');grid=job['grids'][0]
        assert report['numerical_status']=='PASS' and all(c['passed'] for c in report['checks'])
        assert read(coarse/'request.json')==grid['request']==modes._request(Path(job['model_path']).read_text(),16)
        p=read(coarse/'plan.json')
        assert p['kernel_pins']=={Path(v['path']).name:v['sha256'] for v in job['kernel_pins']}
        assert p['pins']==job['source_pins'] and p['reference_rows']==job['reference_rows']
        for name in ('plan.json','request.json','report.json','result.json'):
            f=coarse/name;pins[str(f.relative_to(ROOT))]=suite.digest(f)
        folders[job['id']]={'16':str(coarse.relative_to(ROOT))}
        for count in (32,64):
            identifier=key+f'-n{count}'
            units.append(dict(id=identifier,job_id=job['id'],count=count))
            folders[job['id']][str(count)]=str((REC/identifier).relative_to(ROOT))
    code=dict(source['code_sha256']);code[str(Path(__file__).resolve().relative_to(ROOT))]=suite.digest(Path(__file__))
    plan=dict(source,code_sha256=code,input_sha256=pins,units=units,grid_folders=folders,retry_ids=list(folders),
        original_result_paths=original_paths,timeout_seconds=180,
        execution='Reuse five completed n16 grids; finish n32/n64 in separate children. Original timeouts retained.')
    write(REC/'plan.json',plan)
    print(json.dumps(dict(reused_grids=5,new_grid_requests=len(units),serial=True)),flush=True)


def run(index):
    plan=read(REC/'plan.json');verify(plan);unit=plan['units'][index]
    job=next(j for j in plan['jobs'] if j['id']==unit['job_id']);count=unit['count']
    folder=REC/unit['id'];folder.mkdir();grid=next(g for g in job['grids'] if g['count']==count)
    helper=modes._helper(ROOT,len(job['reference_rows']))
    request=grid['request'];assert request==modes._request(Path(job['model_path']).read_text(),count)
    p=dict(kernel_pins={Path(v['path']).name:v['sha256'] for v in job['kernel_pins']},pins=job['source_pins'],
        nominal_intervals=count,expected_elements=grid['expected_elements'],reference_rows=job['reference_rows'],
        policy=modes.POLICY,method=helper.METHOD,ordinal_scope=helper.ORDINAL_SCOPE)
    write(folder/'request.json',request);write(folder/'plan.json',p)
    report=dict(checks=[],numerical_status='NOT_RUN',reference_status='NOT_ESTABLISHED');start=time.monotonic()
    def progress(*values):
        write(folder/'progress.json',dict(seconds=time.monotonic()-start,progress=values))
    raw=modes._dispatch(request,progress);write(folder/'result.json',raw)
    helper.verify(raw,p,report)
    report['checks'].append(dict(name='frozen input pins retained',passed=modes._stable(job)))
    precision=modes._reference_checks(dict(job,grid_counts=[count]),{count:report})
    report['checks'].append(dict(name='binary and exact decimal precision accounting consistent',
        passed=all(c['passed']==c['exact_decimal_passed'] for c in precision)))
    passed=bool(report['checks']) and all(c['passed'] for c in report['checks'])
    report.update(numerical_status='PASS' if passed else 'FAIL',seconds=time.monotonic()-start)
    verify(plan);write(folder/'report.json',report)
    print(json.dumps(dict(job=job['id'],grid=count,numerical_pass=passed,seconds=report['seconds'])),flush=True)
    if not passed:raise SystemExit(1)


def run_jobs(maximum):
    plan=read(REC/'plan.json');verify(plan);completed=0
    for index,unit in enumerate(plan['units']):
        receipt=REC/(unit['id']+'-execution.json')
        if receipt.exists():continue
        if completed==maximum:break
        if unit['count']==64:
            previous=Path(plan['grid_folders'][unit['job_id']]['32']);p=ROOT/previous/'report.json'
            previous_receipt=read(REC/(previous.name+'-execution.json'))
            if previous_receipt['exit_code']!=0 or not p.exists() or read(p)['numerical_status']!='PASS':
                write(receipt,dict(exit_code=None,status='blocked_by_n32_failure'));continue
        assert not (REC/unit['id']).exists()
        start=time.monotonic();print(json.dumps(dict(starting=unit)),flush=True)
        with (REC/(unit['id']+'.log')).open('x') as log:
            try:
                process=subprocess.run([sys.executable,str(Path(__file__).resolve()),'run','--index',str(index)],
                    stdout=log,stderr=subprocess.STDOUT,timeout=180);code=process.returncode
            except subprocess.TimeoutExpired:code=124
        outputs={str(p.relative_to(ROOT)):suite.digest(p) for p in (REC/unit['id']).glob('*') if p.is_file()}
        write(receipt,dict(exit_code=code,status='completed' if code==0 else 'failed',
            wall_seconds=time.monotonic()-start,output_sha256=outputs))
        completed+=1;print(json.dumps(dict(job=unit['job_id'],grid=unit['count'],exit_code=code)),flush=True)


def combine():
    plan=read(REC/'plan.json');verify(plan);paths={};results={}
    for job in plan['jobs']:
        if job['execution_route']=='unsupported':
            path=ROOT/plan['original_result_paths'][job['id']];results[job['id']]=read(path)
            paths[job['id']]=str(path.relative_to(ROOT));continue
        helper=modes._helper(ROOT,len(job['reference_rows']));packets={};mesh=[];errors=[]
        key=hashlib.sha256(job['id'].encode()).hexdigest()[:20];folder=REC/key;folder.mkdir()
        for count in (16,32,64):
            sub=ROOT/plan['grid_folders'][job['id']][str(count)]
            if count!=16:
                receipt=read(REC/(key+f'-n{count}-execution.json'))
                for p,d in receipt.get('output_sha256',{}).items():assert suite.digest(ROOT/p)==d
                if receipt['exit_code']!=0:errors.append(dict(grid=count,execution=receipt))
            p=sub/'report.json'
            if p.exists():packets[count]=read(p)
        numerical=not errors and len(packets)==3 and all(p['numerical_status']=='PASS' for p in packets.values())
        if numerical:
            for coarse,fine in ((16,32),(32,64)):
                destination=folder/f'mesh-{coarse}-{fine}';destination.mkdir()
                mesh.append(helper.compare_pair(ROOT/plan['grid_folders'][job['id']][str(coarse)],
                    ROOT/plan['grid_folders'][job['id']][str(fine)],destination))
        checks=modes._reference_checks(job,packets);stable=modes._stable(job);numerical=numerical and stable
        result=dict(id=job['id'],case_id='ST-4',adapter='modes',status='computed' if numerical else 'numerical_failure',
            numerical_pass=numerical,reference_match=numerical and all(c['passed'] for c in checks),reference_checks=checks,
            physical_calls=2,reused_completed_physical_calls=1,additional_equilibrium_solves=0,
            original_timed_out_attempt_retained=True,errors=errors,source_pins_unchanged=stable,
            numerical_reports=packets,mesh_reports=mesh,
            mesh_gates_pass=bool(mesh) and mesh[-1]['numerical_status']=='PASS',
            complete_family_reproduction=False,qualifications=job['qualifications'],
            reference_status='NOT_ESTABLISHED',job_id=job['id'],execution_completed=True,
            execution_kind='serial_mesh_recovery',subprocess_started=True,process_reaped=True)
        result=suite.checked_result(job,result)
        write(folder/'request.json',dict(job=job,code_sha256=plan['code_sha256']))
        write(folder/'result.json',result);results[job['id']]=result;paths[job['id']]=str((folder/'result.json').relative_to(ROOT))
    verify(plan)
    write(REC/'assessment.json',dict(batch=dict(remaining=0),jobs=results,result_paths=paths,
        original_timeouts_retained=True,source_sha256=plan['code_sha256']))
    print(json.dumps(dict(statuses={s:sum(r['status']==s for r in results.values()) for s in {r['status'] for r in results.values()}})))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('prepare','run','run-jobs','combine'))
    parser.add_argument('--index',type=int);parser.add_argument('--max-new-jobs',type=int,default=1)
    args=parser.parse_args()
    if args.action=='prepare':prepare()
    elif args.action=='run':run(args.index)
    elif args.action=='run-jobs':run_jobs(args.max_new_jobs)
    else:combine()
