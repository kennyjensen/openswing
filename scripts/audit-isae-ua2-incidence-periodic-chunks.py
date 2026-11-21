"""Bound the periodic raw audit to four segments per job; retain its original metrics."""
import argparse
import gzip
from hashlib import sha256
import json
import os
from pathlib import Path
import numpy as np
from isae_ua2_incidence_periodic import GATES,PERIOD,CYCLES,grid,windows
from isae_ua_wing_incidence import InclinedWing
from isae_ua_periodic import fourier,phase_difference
from isae_ua2_periodic_records import records

ROOT=Path(__file__).resolve().parents[1]
BASE=Path(os.environ.get('OPENSWING_UA2_PERIODIC_BASE', ROOT/'artifacts/isae/ua2-incidence-periodic-20261101')).resolve()

def digest(p):return sha256(p.read_bytes()).hexdigest()

def setup():
    batch=json.loads((BASE/'batch-plan.json').read_text())
    assert batch['gates']==GATES
    assert json.loads((BASE/'batch-complete.json').read_text())['computed_jobs']==sum(len(records(BASE,n)) for n in (320,640))
    pins={**batch['source_sha256'],str(Path(__file__).resolve().relative_to(ROOT)):digest(Path(__file__).resolve())}
    extra=[ROOT/'scripts/isae_ua2_periodic_records.py',BASE/'batch-complete.json']
    if (BASE/'recovery-plan.json').exists():
        extra.append(BASE/'recovery-plan.json')
        for n,h in json.loads((BASE/'recovery-plan.json').read_text())['source_sha256'].items():
            if n in pins:assert pins[n]==h,n
            pins[n]=h
    pins.update({str(p.relative_to(ROOT)):digest(p) for p in extra})
    assert all(digest(ROOT/n)==h for n,h in pins.items())
    plan=dict(source_sha256=pins,gates=GATES,max_segments_per_chunk=4,metric_implementation='Unchanged algebra from the predeclared original auditor; raw reads split into bounded jobs.',
        chunks=[dict(steps=n,index=i) for n in (320,640) for i in range((len(records(BASE,n))+3)//4)],native_ASWING_comparison=False)
    path=BASE/'chunk-audit-plan.json'
    if path.exists():assert json.loads(path.read_text())==plan
    else:path.write_text(json.dumps(plan,indent=2)+'\n')
    return pins,plan

def verify_chunk(steps,index):
    pins,plan=setup();assert dict(steps=steps,index=index) in plan['chunks']
    output_path=BASE/f'audit-n{steps}-chunk{index:02d}.json';assert not output_path.exists()
    wing=InclinedWing(20,alpha_deg=9.);times=grid(steps);rows=[];durations=[];inputs={};previous=None
    reference=json.loads((BASE/'reference.json').read_text())['reference']['DOP853']['cold']['rows']
    reference_times=np.array([r['time'] for r in reference])
    jobs=records(BASE,steps);first=4*index;last=min(first+4,len(jobs))
    if first:
        path=BASE/jobs[first-1]['folder']/'trajectory.json.gz'
        inputs[str(path.relative_to(ROOT))]=digest(path)
        with gzip.open(path,'rt') as stream:previous=json.load(stream)['snapshots'][-1]
    for part in range(first,last):
        job=jobs[part];start,end=job['start_index'],job['end_index']
        expected_steps=end-start
        name=job['id'];folder=BASE/job['folder'];receipt_path=BASE/job['receipt']
        request=json.loads((folder/'plan.json').read_text());report=json.loads((folder/'report.json').read_text())
        receipt=json.loads(receipt_path.read_text())
        assert receipt['exit_code']==0 and receipt['report_sha256']==digest(folder/'report.json')
        assert report['accepted_steps']==expected_steps and report['rejected_steps']==0 and report['converged'] and report['source_unchanged']
        assert request['full_request']['panels']==20 and request['full_request']['condition']['alpha']==9.
        assert request['part']==job['logical_part']
        assert request['gates']==GATES and request['full_request']['time']['duration']==CYCLES*PERIOD
        for n,h in {**request['source_sha256'],**request['parent_sha256']}.items():
            if n in pins:assert pins[n]==h,n
            pins[n]=h
        for p in (folder/'plan.json',folder/'report.json',folder/'trajectory.json.gz',receipt_path):
            inputs[str(p.relative_to(ROOT))]=digest(p)
        with gzip.open(folder/'trajectory.json.gz','rt') as stream:raw=json.load(stream)
        samples=raw['snapshots'];assert len(samples)==len(report['rows'])==expected_steps+1
        if previous is not None:
            for key in ('force','circulation_rate','frame'):assert samples[0][key]==previous[key]
            assert [s['circulation'] for s in samples[0]['strips']]==[s['circulation'] for s in previous['strips']]
        for s,r in zip(samples,report['rows']):
            assert s['time']==r['time'] and s['residual']==r['residual']
            reference_index=int(np.argmin(abs(reference_times-s['time'])))
            assert abs(reference_times[reference_index]-s['time'])<1e-12
            for key in ('CL','circulation','circulation_rate','CF'):
                np.testing.assert_allclose(r['reference'][key],reference[reference_index][key],rtol=0,atol=2e-10)
            assert float(np.array(s['force'])@wing.heave/(.5*1.225*100*10))==r['CL']
            assert s['circulation_rate']==r['circulation_rate']
            assert [v['circulation'] for v in s['strips']]==r['circulation']
            assert float(np.array(s['frame']['velocity_origin_body'])@wing.heave)==r['heave_velocity']
            assert float(np.array(s['frame']['position_earth'])@wing.heave)==r['heave_position']
        previous=samples[-1];rows.extend(report['rows'] if part==0 else report['rows'][1:])
        durations.append(report['solver_seconds'])
        # Keep only the joining state before decoding the next full history.
        del raw,samples
    assert all(digest(ROOT/n)==h for n,h in {**pins,**inputs}.items())
    output=dict(passed=True,steps=steps,chunk=index,first_part=first,last_part_exclusive=last,rows=rows,solver_seconds=durations,source_sha256=pins,input_sha256=inputs)
    output_path.write_text(json.dumps(output,indent=2,allow_nan=False)+'\n')
    print(json.dumps(dict(passed=True,steps=steps,chunk=index,segments=last-first,snapshots=len(rows))))

def combine():
    assert not (BASE/'audit.json').exists()
    pins,plan=setup();results={};inputs={};durations=[]
    wing=InclinedWing(20,alpha_deg=9.);steady=wing.steady();steady_cl=wing.fields(steady,0.,0.)['CL']
    for steps in (320,640):
        times=grid(steps);rows=[];expected_part=0
        for chunk in [c for c in plan['chunks'] if c['steps']==steps]:
            path=BASE/f"audit-n{steps}-chunk{chunk['index']:02d}.json"
            receipt_path=path.with_name(path.stem+'-execution.json')
            receipt=json.loads(receipt_path.read_text());assert receipt['exit_code']==0 and receipt['report_sha256']==digest(path)
            data=json.loads(path.read_text());assert data['passed'] and data['steps']==steps and data['chunk']==chunk['index']
            assert data['first_part']==expected_part;expected_part=data['last_part_exclusive']
            rows.extend(data['rows']);durations.extend(data['solver_seconds'])
            for n,h in {**data['source_sha256'],**data['input_sha256']}.items():
                if n in pins:assert pins[n]==h,n
                pins[n]=h
            for p in (path,receipt_path):inputs[str(p.relative_to(ROOT))]=digest(p)
        assert expected_part==len(records(BASE,steps))
        assert len(rows)==len(times)
        np.testing.assert_allclose([r["time"] for r in rows],times,rtol=0,atol=1e-12)
        assert all(r['order']==(1 if i==1 else 2) for i,r in enumerate(rows) if i)
        expected={key:np.array([r['reference'][key] for r in rows]) for key in ('CL','circulation','circulation_rate')}
        actual={key:np.array([r[key] for r in rows]) for key in expected}
        scales=dict(CL=float(np.max(abs(expected['CL']-steady_cl))),
            circulation=np.max(abs(expected['circulation']-steady),axis=0),
            circulation_rate=np.max(abs(expected['circulation_rate']),axis=0))
        assert all(np.min(v)>0 for v in scales.values())
        errors={key:float(np.max(abs(actual[key]-expected[key])/scales[key])) for key in expected}
        diagnostics=dict(first_step_rate_relative_error=float(np.max(abs(actual['circulation_rate'][1]-expected['circulation_rate'][1])/abs(expected['circulation_rate'][1]))),
            maximum_heave_velocity_error=max(abs(r['heave_velocity']-r['reference']['velocity']) for r in rows),
            maximum_heave_position_error=max(abs(r['heave_position']-r['reference']['displacement']) for r in rows),
            maximum_residual=max(r['residual'] for r in rows),
            initial_circulation_error=float(np.max(abs(actual['circulation'][0]-steady))))
        results[str(steps)]=dict(rows=rows,error_fractions=errors,diagnostics=diagnostics,
            scales={k:(v.tolist() if isinstance(v,np.ndarray) else v) for k,v in scales.items()})
    periodic_rows=json.loads((BASE/'reference.json').read_text())['reference']['DOP853']['periodic']['rows']
    for steps in (320,640):
        result=results[str(steps)];rows=result['rows'];times=np.array([r['time'] for r in rows])
        refs=periodic_rows[::640//steps];phase=np.array([r['time'] for r in refs])
        target={key:np.array([r[key] for r in refs]) for key in ('CL','circulation','circulation_rate')}
        means={key:np.sum(np.diff(phase).reshape((-1,)+(1,)*(values.ndim-1))*(values[1:]+values[:-1])/2,axis=0)/PERIOD for key,values in target.items()}
        scales={key:np.max(abs(values-(0 if key=='circulation_rate' else means[key])),axis=0) for key,values in target.items()}
        measured_reference=fourier(phase,target['CL'],PERIOD)
        actual={key:np.array([r[key] for r in rows]) for key in target}
        cycles=[];previous_values=None
        for cycle in range(2,CYCLES+1):
            start=int(np.argmin(abs(times-(cycle-1)*PERIOD)));end=int(np.argmin(abs(times-cycle*PERIOD)))
            np.testing.assert_allclose(times[start:end+1]-(cycle-1)*PERIOD,phase,rtol=0,atol=1e-12)
            values={key:arr[start:end+1] for key,arr in actual.items()}
            errors={key:float(np.max(abs(values[key]-target[key])/scales[key])) for key in target}
            measured=fourier(phase,values['CL'],PERIOD)
            harmonics=[dict(order=a['order'],amplitude_error_fraction=a['amplitude']/b['amplitude']-1,phase_error_deg=phase_difference(a['phase_deg'],b['phase_deg'])) for a,b in zip(measured['harmonics'],measured_reference['harmonics'])]
            change=None if previous_values is None else {key:float(np.max(abs(values[key]-previous_values[key])/scales[key])) for key in target}
            cycles.append(dict(cycle=cycle,error_fractions=errors,measured=measured,harmonic_errors=harmonics,
                mean_CL_error_dynamic_fraction=float((measured['mean']-measured_reference['mean'])/scales['CL']),cycle_change_fractions=change))
            previous_values=values
        result.update(cycles=cycles,periodic_reference=measured_reference,
            periodic_scales={k:np.asarray(v).tolist() for k,v in scales.items()})
    fine=results['640'];coarse=results['320'];final=fine['cycles'][-1]
    ratios={'cold':{k:fine['error_fractions'][k]/coarse['error_fractions'][k] for k in fine['error_fractions']},
        'periodic':{k:final['error_fractions'][k]/coarse['cycles'][-1]['error_fractions'][k] for k in final['error_fractions']}}
    checks={}
    for key,label in (('CL','CL'),('circulation','circulation'),('circulation_rate','rate')):
        checks['cold_'+key]=fine['error_fractions'][key]<GATES['cold_'+label+'_fraction']
        checks['periodic_'+key]=final['error_fractions'][key]<GATES['periodic_'+label+'_fraction']
        checks['last_cycle_change_'+key]=final['cycle_change_fractions'][key]<GATES['last_cycle_change_fraction']
    checks.update(refinement=max(v for scope in ratios.values() for v in scope.values())<GATES['fine_to_coarse_ratio'],
        amplitude=abs(final['harmonic_errors'][0]['amplitude_error_fraction'])<GATES['amplitude_fraction'],
        phase=abs(final['harmonic_errors'][0]['phase_error_deg'])<GATES['phase_deg'],
        mean=abs(final['mean_CL_error_dynamic_fraction'])<GATES['mean_CL_dynamic_fraction'],
        residual=max(r['diagnostics']['maximum_residual'] for r in results.values())<GATES['normalized_residual'],
        first_step_rate=fine['diagnostics']['first_step_rate_relative_error']<GATES['first_step_rate_fraction'],
        velocity=fine['diagnostics']['maximum_heave_velocity_error']/4.75<GATES['velocity_fraction'],
        position=fine['diagnostics']['maximum_heave_position_error']/.25<GATES['position_fraction'])
    assert all(digest(ROOT/n)==h for n,h in {**pins,**inputs}.items())
    output=dict(passed=all(checks.values()),checks=checks,results=results,ratios=ratios,
        audited_unique_snapshots=sum(len(r['rows']) for r in results.values()),input_sha256=inputs,source_sha256=pins,
        solver_seconds=dict(min=min(durations),max=max(durations),total=sum(durations)),native_ASWING_comparison=False)
    (BASE/'audit.json').write_text(json.dumps(output,indent=2,allow_nan=False)+'\n')
    print(json.dumps(dict(passed=output['passed'],checks=checks,cold_errors=fine['error_fractions'],periodic_errors=final['error_fractions'],ratios=ratios,diagnostics=fine['diagnostics'],fundamental=final['harmonic_errors'][0],mean_error=final['mean_CL_error_dynamic_fraction'],cycle_change=final['cycle_change_fractions'])))
    if not output['passed']:raise SystemExit(1)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('chunk','combine'))
    parser.add_argument('--steps',type=int,choices=(320,640))
    parser.add_argument('--index',type=int)
    args=parser.parse_args()
    if args.action=='chunk':
        if args.steps is None or args.index is None:parser.error('Chunk needs steps and index')
        verify_chunk(args.steps,args.index)
    else:combine()
