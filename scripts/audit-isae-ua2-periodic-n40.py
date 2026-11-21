"""Audit every N40 physical snapshot, then compare time accuracy and mesh lift."""
import argparse
import gzip
from hashlib import sha256
import json
from pathlib import Path
import numpy as np
from isae_ua2_incidence_periodic_n40 import ROOT,BASE,GATES,PERIOD,CYCLES,STEPS,grid,windows
from isae_ua_wing_incidence import InclinedWing
from isae_ua_periodic import fourier,phase_difference

JOBS_PER_CHUNK=8


def digest(p):
    h=sha256()
    with p.open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()


def write(path,data):
    assert not path.exists(),path
    path.write_text(json.dumps(data,indent=2,allow_nan=False)+'\n')


def setup():
    plan=json.loads((BASE/'production-plan.json').read_text())
    assert plan['audit_jobs_per_chunk']==JOBS_PER_CHUNK
    assert plan['gates']==GATES and json.loads((BASE/'production-complete.json').read_text())['computed_jobs']==len(windows())
    pins={**plan['source_sha256'],str((BASE/'production-plan.json').relative_to(ROOT)):digest(BASE/'production-plan.json')}
    assert all(digest(ROOT/n)==h for n,h in pins.items())
    return plan,pins


def chunk(index):
    plan,pins=setup();jobs=windows();first=index*JOBS_PER_CHUNK;last=min(first+JOBS_PER_CHUNK,len(jobs))
    assert 0<=first<last
    path=BASE/f'audit-chunk{index:03d}.json';assert not path.exists()
    reference=json.loads((BASE/'reference-verified.json').read_text());assert reference['passed']
    wing=InclinedWing(40,alpha_deg=9.);rows=[];durations=[];inputs={};previous=None
    if first:
        p=BASE/'production'/f'part{first-1:03d}'/'trajectory.json.gz';inputs[str(p.relative_to(ROOT))]=digest(p)
        with gzip.open(p,'rt') as stream:previous=json.load(stream)['snapshots'][-1]
    for part in range(first,last):
        folder=BASE/'production'/f'part{part:03d}';receipt_path=folder.with_name(folder.name+'-execution.json')
        receipt=json.loads(receipt_path.read_text());report=json.loads((folder/'report.json').read_text());request=json.loads((folder/'plan.json').read_text())
        assert receipt['exit_code']==0 and receipt['report_sha256']==digest(folder/'report.json')
        a,b=jobs[part];assert report['converged'] and report['accepted_steps']==b-a and report['rejected_steps']==0 and report['source_unchanged']
        assert request['part']==part and request['steps']==STEPS and request['full_request']==plan['full_request'] and request['gates']==GATES
        for n,h in {**request['source_sha256'],**request['parent_sha256']}.items():
            if n in pins:assert pins[n]==h,n
            pins[n]=h
        meta=reference['reference_parts'][str(part)];target_path=BASE/meta['path'];assert digest(target_path)==meta['sha256']
        target=json.loads(target_path.read_text());assert target['job']==dict(part=part,start_index=a,end_index=b)
        for p in (folder/'plan.json',folder/'report.json',folder/'trajectory.json.gz',receipt_path,target_path):inputs[str(p.relative_to(ROOT))]=digest(p)
        with gzip.open(folder/'trajectory.json.gz','rt') as stream:raw=json.load(stream)
        samples=raw['snapshots'];assert len(samples)==len(report['rows'])==len(target['rows'])==b-a+1
        if previous is not None:
            for key in ('force','circulation_rate','frame'):assert samples[0][key]==previous[key]
            assert [r['circulation'] for r in samples[0]['strips']]==[r['circulation'] for r in previous['strips']]
        for s,r,t in zip(samples,report['rows'],target['rows']):
            assert len(s['strips'])==40 and s['time']==r['time'] and s['residual']==r['residual']
            assert r['reference']==t
            assert float(np.array(s['force'])@wing.heave/(.5*1.225*100*10))==r['CL']
            assert s['circulation_rate']==r['circulation_rate'] and [x['circulation'] for x in s['strips']]==r['circulation']
            assert float(np.array(s['frame']['velocity_origin_body'])@wing.heave)==r['heave_velocity']
            assert float(np.array(s['frame']['position_earth'])@wing.heave)==r['heave_position']
            assert float(np.array(s['frame']['acceleration_reference_body'])@wing.heave)==r['heave_acceleration']
        previous=samples[-1];rows.extend(report['rows'] if part==0 else report['rows'][1:]);durations.append(report['solver_seconds'])
        del raw,samples
    assert all(digest(ROOT/n)==h for n,h in {**pins,**inputs}.items())
    write(path,dict(passed=True,index=index,first_part=first,last_part_exclusive=last,rows=rows,solver_seconds=durations,source_sha256=pins,input_sha256=inputs))
    print(json.dumps(dict(passed=True,index=index,jobs=last-first,snapshots=len(rows))))


def combine():
    plan,pins=setup();assert not (BASE/'audit.json').exists()
    rows=[];durations=[];inputs={};expected_part=0
    for index in range((len(windows())+JOBS_PER_CHUNK-1)//JOBS_PER_CHUNK):
        p=BASE/f'audit-chunk{index:03d}.json';receipt_path=BASE/f'audit-chunk{index:03d}-execution.json'
        receipt=json.loads(receipt_path.read_text());assert receipt['exit_code']==0 and receipt['report_sha256']==digest(p)
        data=json.loads(p.read_text());assert data['passed'] and data['index']==index and data['first_part']==expected_part
        expected_part=data['last_part_exclusive'];rows.extend(data['rows']);durations.extend(data['solver_seconds'])
        for n,h in {**data['source_sha256'],**data['input_sha256']}.items():
            if n in pins:assert pins[n]==h,n
            pins[n]=h
        for q in (p,receipt_path):inputs[str(q.relative_to(ROOT))]=digest(q)
    assert expected_part==len(windows()) and len(rows)==len(grid())
    times=np.array([r['time'] for r in rows]);np.testing.assert_allclose(times,grid(),rtol=0,atol=1e-12)
    assert all(r['order']==(1 if i==1 else 2) for i,r in enumerate(rows) if i)
    wing=InclinedWing(40,alpha_deg=9.);steady=wing.steady();steady_cl=wing.fields(steady,0.,0.)['CL']
    expected={k:np.array([r['reference'][k] for r in rows]) for k in ('CL','circulation','circulation_rate')}
    actual={k:np.array([r[k] for r in rows]) for k in expected}
    scales=dict(CL=float(np.max(abs(expected['CL']-steady_cl))),circulation=np.max(abs(expected['circulation']-steady),axis=0),circulation_rate=np.max(abs(expected['circulation_rate']),axis=0))
    assert all(np.min(v)>0 for v in scales.values())
    cold={k:float(np.max(abs(actual[k]-expected[k])/scales[k])) for k in expected}
    diagnostics=dict(first_step_rate_relative_error=float(np.max(abs(actual['circulation_rate'][1]-expected['circulation_rate'][1])/abs(expected['circulation_rate'][1]))),
        maximum_heave_velocity_error=max(abs(r['heave_velocity']-r['reference']['velocity']) for r in rows),
        maximum_heave_position_error=max(abs(r['heave_position']-r['reference']['displacement']) for r in rows),
        maximum_residual=max(r['residual'] for r in rows),initial_circulation_error=float(np.max(abs(actual['circulation'][0]-steady))))
    ref=json.loads((BASE/'periodic-reference.json').read_text());refs=ref['rows'];phase=np.array([r['time'] for r in refs])
    target={k:np.array([r[k] for r in refs]) for k in expected}
    means={k:np.sum(np.diff(phase).reshape((-1,)+(1,)*(values.ndim-1))*(values[1:]+values[:-1])/2,axis=0)/PERIOD for k,values in target.items()}
    periodic_scales={k:np.max(abs(v-(0 if k=='circulation_rate' else means[k])),axis=0) for k,v in target.items()}
    measured_reference=fourier(phase,target['CL'],PERIOD);cycles=[];previous_values=None
    for cycle in range(2,CYCLES+1):
        start=int(np.argmin(abs(times-(cycle-1)*PERIOD)));end=int(np.argmin(abs(times-cycle*PERIOD)))
        np.testing.assert_allclose(times[start:end+1]-(cycle-1)*PERIOD,phase,rtol=0,atol=1e-12)
        values={k:v[start:end+1] for k,v in actual.items()}
        errors={k:float(np.max(abs(values[k]-target[k])/periodic_scales[k])) for k in target}
        measured=fourier(phase,values['CL'],PERIOD)
        harmonics=[dict(order=a['order'],amplitude_error_fraction=a['amplitude']/b['amplitude']-1,phase_error_deg=phase_difference(a['phase_deg'],b['phase_deg'])) for a,b in zip(measured['harmonics'],measured_reference['harmonics'])]
        change=None if previous_values is None else {k:float(np.max(abs(values[k]-previous_values[k])/periodic_scales[k])) for k in target}
        cycles.append(dict(cycle=cycle,error_fractions=errors,measured=measured,harmonic_errors=harmonics,mean_CL_error_dynamic_fraction=float((measured['mean']-measured_reference['mean'])/periodic_scales['CL']),cycle_change_fractions=change));previous_values=values
    final=cycles[-1];checks={}
    for key,label in (('CL','CL'),('circulation','circulation'),('circulation_rate','rate')):
        checks['cold_'+key]=cold[key]<GATES['cold_'+label+'_fraction']
        checks['periodic_'+key]=final['error_fractions'][key]<GATES['periodic_'+label+'_fraction']
        checks['last_cycle_change_'+key]=final['cycle_change_fractions'][key]<GATES['last_cycle_change_fraction']
    checks.update(amplitude=abs(final['harmonic_errors'][0]['amplitude_error_fraction'])<GATES['amplitude_fraction'],
        phase=abs(final['harmonic_errors'][0]['phase_error_deg'])<GATES['phase_deg'],mean=abs(final['mean_CL_error_dynamic_fraction'])<GATES['mean_CL_dynamic_fraction'],
        residual=diagnostics['maximum_residual']<GATES['normalized_residual'],first_step_rate=diagnostics['first_step_rate_relative_error']<GATES['first_step_rate_fraction'],
        velocity=diagnostics['maximum_heave_velocity_error']/4.75<GATES['velocity_fraction'],position=diagnostics['maximum_heave_position_error']/.25<GATES['position_fraction'])
    baseline=json.loads((BASE/'baseline-n20.json').read_text())
    np.testing.assert_allclose(times,[r['time'] for r in baseline['cold']],rtol=0,atol=1e-12)
    np.testing.assert_allclose(phase,[r['time'] for r in baseline['periodic_reference']],rtol=0,atol=1e-12)
    old_actual=np.array([r['CL'] for r in baseline['cold']]);old_reference=np.array([r['reference_CL'] for r in baseline['cold']])
    mesh=dict(cold_production_lift_fraction=float(np.max(abs(actual['CL']-old_actual))/scales['CL']),
        cold_reference_lift_fraction=float(np.max(abs(expected['CL']-old_reference))/scales['CL']),
        periodic_production_lift_fraction=float(np.max(abs(actual['CL'][-STEPS-1:]-old_actual[-STEPS-1:]))/periodic_scales['CL']),
        periodic_reference_lift_fraction=float(np.max(abs(target['CL']-np.array([r['CL'] for r in baseline['periodic_reference']])))/periodic_scales['CL']))
    temporal_checks=checks.copy()
    checks.update(cold_mesh_lift=mesh['cold_production_lift_fraction']<GATES['mesh_lift_fraction'],periodic_mesh_lift=mesh['periodic_production_lift_fraction']<GATES['mesh_lift_fraction'])
    for n,h in plan['reference_input_sha256'].items():
        if n in pins:assert pins[n]==h,n
        pins[n]=h
    assert all(digest(ROOT/n)==h for n,h in {**pins,**inputs}.items())
    output=dict(passed=all(checks.values()),checks=checks,periodic_case_passed=all(temporal_checks.values()),mesh_check_passed=checks['cold_mesh_lift'] and checks['periodic_mesh_lift'],
        rows=rows,cold_error_fractions=cold,cycles=cycles,diagnostics=diagnostics,mesh=mesh,
        scales={k:np.asarray(v).tolist() for k,v in scales.items()},periodic_scales={k:np.asarray(v).tolist() for k,v in periodic_scales.items()},
        periodic_reference=measured_reference,audited_unique_snapshots=len(rows),comparison_baseline_snapshots=len(baseline['cold']),
        solver_seconds=dict(min=min(durations),max=max(durations),total=sum(durations)),source_sha256=pins,input_sha256=inputs,
        native_ASWING_comparison=False,production_changed=False,new_temporal_refinement_claim=False)
    write(BASE/'audit.json',output)
    print(json.dumps(dict(passed=output['passed'],checks=checks,cold_errors=cold,periodic_errors=final['error_fractions'],mesh=mesh,diagnostics=diagnostics)))
    if not output['passed']:raise SystemExit(1)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('action',choices=('chunk','combine'));parser.add_argument('--index',type=int)
    args=parser.parse_args()
    if args.action=='combine':combine()
    elif args.index is None:parser.error('Chunk index required')
    else:chunk(args.index)
