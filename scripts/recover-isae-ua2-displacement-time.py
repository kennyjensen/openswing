"""Finish the two pending UA-2 legacy intervals in owned eight-step segments."""
import argparse
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'artifacts/isae/ua2-displacement-time-20261103'
REC=BASE/'recovery'
spec=importlib.util.spec_from_file_location('ua2_current',ROOT/'scripts/verify-isae-ua2-current-time.py')
study=importlib.util.module_from_spec(spec);spec.loader.exec_module(study)
read,write,pins,verify,digest=study.read,study.write,study.pins,study.verify,study.digest


def prepare():
    plan=read(BASE/'plan.json');verify(plan['source_sha256'])
    assert read(BASE/'n20-part290-execution.json')['exit_code']==124
    assert not (BASE/'n20-part290/trajectory.json.gz').exists()
    assert not (BASE/'n20-part300').exists()
    REC.mkdir()
    jobs=[]
    for job in [j for j in plan['jobs'] if j['panels']==20 and j['part'] in (290,300)]:
        assert digest(ROOT/job['target'])==job['target_sha256']
        for half in (0,1):
            jobs.append(dict(job,id=job['id']+f'-half{half}',logical_id=job['id'],half=half,
                start_index=job['start_index']+half*8,end_index=job['start_index']+(half+1)*8))
    output=dict(jobs=jobs,gates=plan['gates'],times=plan['times'],
        source_sha256=plan['source_sha256'],execution_source_sha256=pins([Path(__file__).resolve(),
            ROOT/'scripts/isae_ua2_browser_cutoff.py']),
        input_sha256=pins([BASE/'plan.json',BASE/'n20-part290-execution.json']),
        child_timeout_seconds=45,serial=True,threads=1,native_ASWING_comparison=False,
        unchanged_time_grid=True,continuation_requires='Converged finite state; physical gate failures remain recorded and are never converted to passes.')
    write(REC/'plan.json',output)
    print(json.dumps(dict(prepared=True,requests=4,steps_per_request=8,logical_intervals=2)))


def run(index):
    import numpy as np
    from openswing.bridge import dispatch
    from openswing.time_state import checkpoint
    from isae_ua_artifacts import write_trajectory
    from isae_ua2_browser_cutoff import validate_checkpoint
    plan=read(REC/'plan.json');verify(plan['source_sha256']);verify(plan['execution_source_sha256'])
    job=plan['jobs'][index];folder=REC/job['id'];folder.mkdir()
    target=read(ROOT/job['target']);assert digest(ROOT/job['target'])==job['target_sha256']
    references=target['rows'][job['half']*8:job['half']*8+9]
    dependencies=pins([REC/'plan.json',ROOT/job['target']])
    if job['half']==0:
        saved=read(ROOT/job['checkpoint']);join=read(ROOT/job['join'])
        assert digest(ROOT/job['checkpoint'])==job['checkpoint_sha256']
        assert digest(ROOT/job['join'])==job['join_sha256']
        dependencies.update(pins([ROOT/job['checkpoint'],ROOT/job['join']]))
    else:
        parent=REC/(job['logical_id']+'-half0');receipt=read(REC/(parent.name+'-execution.json'))
        assert receipt['exit_code'] in (0,1);verify(receipt['output_sha256'])
        report=read(parent/'report.json');assert report['accepted_steps']==8 and report['rejected_steps']==0
        saved=read(parent/'checkpoint.json');join=report['physical_rows'][-1]
        dependencies.update(pins([parent/'report.json',parent/'checkpoint.json',REC/(parent.name+'-execution.json')]))
    assert abs(saved['state']['time']-plan['times'][job['start_index']])<1e-12
    request={k:v for k,v in deepcopy(job['full_request']).items() if k not in ('condition','time')}
    request.update(action='resume_time',checkpoint=saved,
        time=dict(duration=plan['times'][job['end_index']]-saved['state']['time'],max_steps=64))
    write(folder/'request.json',request)
    start=time.monotonic()
    def progress(*values):
        if len(values)==2 and isinstance(values[0],(float,int)):
            (folder/'progress.json').write_text(json.dumps(dict(time=values[0],steps=values[1],seconds=time.monotonic()-start))+'\n')
    raw=dispatch(request,progress=progress);seconds=time.monotonic()-start
    write_trajectory(folder/'trajectory.json.gz',raw)
    assert raw['converged'] and raw['accepted_steps']==8 and raw['rejected_steps']==0
    rows=[study.physical(s,20) for s in raw['snapshots']];assert len(rows)==len(references)==9
    np.testing.assert_allclose([r['time'] for r in rows],[r['time'] for r in references],atol=1e-12,rtol=0)
    errors={k:float(np.max(abs(np.array([r[k] for r in rows])-np.array([r[k] for r in references]))/
        np.asarray(target['scales'][k]))) for k in ('CL','circulation','circulation_rate')}
    velocity=max(abs(a['velocity']-b['velocity'])/4.75 for a,b in zip(rows,references))
    position=max(abs(a['position']-b['displacement'])/.25 for a,b in zip(rows,references))
    acceleration=max(abs(a['acceleration']-b['acceleration']) for a,b in zip(rows,references))
    local={k:max(abs(v) for r in rows for v in study.flatten(r[k])) for k in study.LOCAL}
    join_error=max(study.difference(rows[0][k],join[k]) for k in rows[0] if k not in ('order','residual'))
    chart_count=sum(study.charts(s['restart']) for s in raw['snapshots'])
    saved=checkpoint(raw);assert saved['context']['setup']['forcing']==job['full_request']['time']['forcing']
    validate_checkpoint(raw,final=False,expected_end=raw['snapshots'][-1]['time'])
    write(folder/'checkpoint.json',saved)
    limits=study.LIMITS;assert limits==plan['gates']
    checks=dict(waveforms=max(errors.values())<=limits['waveform_fraction'],
        velocity=velocity<=limits['velocity_fraction'],position=position<=limits['position_fraction'],
        acceleration=acceleration<1e-10,first_rate=True,
        local_motion=max(local.values())<=limits['local_motion'],
        checkpoint_join=join_error<=limits['join_scaled'],
        residual=max(r['residual'] for r in rows)<limits['normalized_residual'],charts=chart_count>0)
    verify(plan['source_sha256']);verify(plan['execution_source_sha256']);verify(dependencies)
    report=dict(passed=all(checks.values()),checks=checks,job=job['id'],kind='legacy_replay',panels=20,
        accepted_steps=8,rejected_steps=0,solver_seconds=seconds,error_fractions=errors,
        local_motion_maxima=local,maximum_join_scaled_difference=join_error,
        velocity_error_fraction=velocity,position_error_fraction=position,
        first_step_rate_error_fraction=None,position_charts_checked=chart_count,physical_rows=rows,
        source_sha256=plan['source_sha256'],execution_source_sha256=plan['execution_source_sha256'],
        input_sha256=dependencies,native_ASWING_comparison=False)
    write(folder/'report.json',report)
    print(json.dumps({k:v for k,v in report.items() if k not in ('physical_rows','source_sha256','execution_source_sha256','input_sha256')}),flush=True)
    if not report['passed']:raise SystemExit(1)


def run_jobs():
    plan=read(REC/'plan.json')
    for index,job in enumerate(plan['jobs']):
        path=REC/(job['id']+'-execution.json')
        if path.exists():
            receipt=read(path);assert receipt['exit_code'] in (0,1)
            verify(receipt['output_sha256']);assert (REC/job['id']/'report.json').exists();continue
        assert not (REC/job['id']).exists()
        print(json.dumps(dict(starting=job['id'])),flush=True);start=time.monotonic()
        with (REC/(job['id']+'.log')).open('x') as stream:
            try:
                child=subprocess.run([sys.executable,str(Path(__file__).resolve()),'run','--index',str(index)],
                    stdout=stream,stderr=subprocess.STDOUT,timeout=45);code=child.returncode
            except subprocess.TimeoutExpired:code=124
        outputs=pins([p for p in (REC/job['id']).glob('*') if p.is_file()])
        write(path,dict(exit_code=code,wall_seconds=time.monotonic()-start,output_sha256=outputs))
        print(json.dumps(dict(job=job['id'],exit_code=code,seconds=time.monotonic()-start)),flush=True)
        if code not in (0,1) or not (REC/job['id']/'report.json').exists():raise SystemExit(code or 1)


def combine():
    plan=read(REC/'plan.json');verify(plan['source_sha256']);verify(plan['execution_source_sha256']);verify(plan['input_sha256'])
    reports=[]
    for logical in ('n20-part290','n20-part300'):
        pair=[];dependencies=pins([REC/'plan.json'])
        for half in (0,1):
            folder=REC/(logical+f'-half{half}');receipt_path=REC/(folder.name+'-execution.json');receipt=read(receipt_path)
            assert receipt['exit_code'] in (0,1);verify(receipt['output_sha256'])
            report=read(folder/'report.json');assert report['passed']==(receipt['exit_code']==0)
            verify(report['input_sha256']);pair.append(report)
            dependencies.update(pins([folder/'report.json',receipt_path]))
        checks={key:all(r['checks'][key] for r in pair) for key in pair[0]['checks']}
        rows=pair[0]['physical_rows']+pair[1]['physical_rows'][1:];assert len(rows)==17
        result=dict(pair[0],passed=all(checks.values()),checks=checks,job=logical,accepted_steps=16,
            solver_seconds=sum(r['solver_seconds'] for r in pair),physical_rows=rows,input_sha256=dependencies,
            error_fractions={k:max(r['error_fractions'][k] for r in pair) for k in pair[0]['error_fractions']},
            local_motion_maxima={k:max(r['local_motion_maxima'][k] for r in pair) for k in study.LOCAL},
            maximum_join_scaled_difference=max(r['maximum_join_scaled_difference'] for r in pair),
            velocity_error_fraction=max(r['velocity_error_fraction'] for r in pair),
            position_error_fraction=max(r['position_error_fraction'] for r in pair),
            position_charts_checked=sum(r['position_charts_checked'] for r in pair),
            execution='Two eight-step requests; original timed-out attempt retained.',original_interval_preserved=True)
        folder=REC/logical;folder.mkdir();write(folder/'report.json',result);reports.append(result)
    write(REC/'complete.json',dict(all_intervals_computed=True,intervals_passed=sum(r['passed'] for r in reports),
        intervals_required=2,request_count=4,accepted_steps=32,rejected_steps=0,new_native_passes=0,
        output_sha256=pins([REC/r['job']/'report.json' for r in reports])))
    print(json.dumps(dict(all_intervals_computed=True,intervals_passed=sum(r['passed'] for r in reports),intervals_required=2)))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('action',choices=('prepare','run','run-jobs','combine'))
    parser.add_argument('--index',type=int);args=parser.parse_args()
    if args.action=='prepare':prepare()
    elif args.action=='run':run(args.index)
    elif args.action=='run-jobs':run_jobs()
    else:combine()
