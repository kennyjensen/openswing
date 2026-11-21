"""Audit the full refined history and compare exact common ticks with the native-grid run."""
import argparse
from decimal import Decimal
import importlib.util
import json
import math
from pathlib import Path
import statistics

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('ffwt4_coarse_audit',ROOT/'scripts/assess-isae-ffwt4-time.py')
coarse_audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(coarse_audit)
pin,read,require=coarse_audit.pin,coarse_audit.read,coarse_audit.require
DT=Decimal('.0149')


def snapshot_value(snapshot,tick,divisor):
    require(divisor in (2,4),'Unsupported refinement ratio')
    require(abs(snapshot['time']-float(tick*DT/divisor))<=1e-10,'Refined state time differs')
    require(snapshot['converged'] and math.isfinite(snapshot['residual']) and snapshot['residual']<=1e-8,
            'Unconverged refined state')
    if tick:
        require(snapshot['restart']['accepted_method']['effective_order']==(1 if tick==1 else 2),
                'Refinement restarted integration order')
    sensors=[s for s in snapshot['sensors'] if s['index']==1]
    require(len(sensors)==1 and sensors[0]['load_trace']=='left','Refined root trace differs')
    value=sensors[0]['moment_local'][0];require(math.isfinite(value),'Nonfinite refined moment')
    return value


def refinement_checks(coarse,fine,divisor):
    """No interpolation, fitted offsets, or incomplete-history convergence claims."""
    require(sorted(coarse)==list(range(200)),'Coarse history is incomplete')
    require(sorted(fine)==list(range(199*divisor+1)),'Fine history is incomplete')
    c=[coarse[i] for i in range(200)];f=[fine[i*divisor] for i in range(200)]
    require(all(math.isfinite(x) for x in c+f),'Nonfinite history')
    gates={}
    for name,cv,fv in [('root_moment',c,f),('gust_increment',[x-c[0] for x in c],[x-f[0] for x in f])]:
        scale=max(map(abs,fv));require(scale>0,'Zero refinement scale')
        differences=[abs(a-b) for a,b in zip(cv,fv)];worst=max(range(200),key=differences.__getitem__)
        gates[name]=dict(maximum_absolute_difference=max(differences),scale=scale,
            maximum_percent_of_scale=100*max(differences)/scale,rms_percent_of_scale=
            100*math.sqrt(sum(d*d for d in differences)/200)/scale,
            relative_limit=.001,worst_row=worst+1,worst_time=float(worst*DT),
            passed=max(differences)<=.001*scale)
    return gates


def assess(folder,coarse_path):
    coarse=read(coarse_path);checked={}
    def verify(record):
        if record['path'] in checked:require(record==checked[record['path']],'Conflicting evidence pins')
        else:require(pin(record['path'])==record,'Changed evidence: '+record['path']);checked[record['path']]=record
    require(coarse['status']=='SAVED_HISTORY_ASSESSED' and coarse['accepted_steps']==199 and
            coarse['summary']['computed']==200 and coarse['rejected_steps']==0,'Incomplete coarse assessment')
    for record in coarse['inputs']+coarse['plans']+coarse['reports']+[coarse['helper']]:verify(record)
    coarse_first=read(coarse['plans'][0]['path']);chain=[];visited=set()
    while True:
        folder=folder.resolve();require(folder not in visited,'Cyclic refinement ancestry');visited.add(folder)
        plan,report=read(folder/'plan.json'),read(folder/'report.json')
        require(plan['schema']=='isae-ffwt4-fixed1-refinement-v1' and report['status']=='SEGMENT_COMPUTED',
                'Incomplete refinement segment')
        require(report['source_pins_unchanged'] and report['kernel_pins_unchanged'],'Unverified refinement sources')
        for record in plan['source_pins']+plan['kernel_pins']+[plan[k] for k in
                ('helper','initial_helper','initial_plan','initial_request','initial_result','initial_report')]:verify(record)
        for key in ('parent_plan','parent_report','parent_checkpoint','parent_time_helper'):
            if key in plan:verify(plan[key])
        for key in ('request','result','checkpoint'):verify(report[key])
        chain.append((folder,plan,report))
        if 'parent_checkpoint' not in plan:break
        folder=Path(plan['parent_checkpoint']['path']).parent
    chain.reverse();first=chain[0][1];divisor=first['divisor'];dt=DT/divisor
    require(divisor in (2,4) and first['nominal']==coarse['nominal'],'Refinement changed mesh')
    for key in ('source_pins','kernel_pins','initial_plan','initial_result','initial_report','initial_helper'):
        require(first[key]==coarse_first[key],'Refinement changed initial setup or equations: '+key)
    require(first['accuracy_gate']['relative']==.001,'Refinement tolerance changed')
    samples={};accepted=0;maximum_residual=0.;seconds=0.
    for index,(folder,plan,report) in enumerate(chain):
        for key in ('source_pins','kernel_pins','nominal','divisor','dt','native_dt','accuracy_gate','initial_request'):
            require(plan[key]==first[key],'Continuation changed configuration: '+key)
        require(Decimal(plan['dt'])==dt and Decimal(plan['native_dt'])==DT,'Time grid changed')
        start,end=plan['start_step'],plan['end_step']
        require(start==(chain[index-1][1]['end_step'] if index else 0) and start<end<=199*divisor,
                'Noncontiguous refined coverage')
        require(report['start_step']==start and report['end_step']==end and report['accepted_steps']==end-start and
                report['rejected_steps']==0 and Decimal(report['dt'])==dt,'Segment accounting differs')
        request=read(report['request']['path'])
        require(request['source']==Path(first['source_pins'][0]['path']).read_text(),'Changed literal model')
        require(request['time']['dt']==float(dt) and request['time']['duration']==float((end-start)*dt) and
                request['time']['order']==2,'Changed integration request')
        if not index:
            expected=read(plan['initial_request']['path']);expected.update(action='time',mode='time')
            expected.pop('tolerance');expected.pop('continuation_steps')
            expected['condition']['gust']=dict(type='cosine',amplitude=[0.,0.,.6978],
                origin=[-10.9366,0.,0.],normal=[-1.,0.,0.],length=10.9366,speed=0.)
            expected['time']=dict(frame='prescribed',duration=float(end*dt),dt=float(dt),order=2,
                                 tolerance=1e-8,continuation_steps=4,max_steps=end)
            require(request==expected,'Cold refinement altered more than time resolution')
        else:
            require(request['checkpoint']==read(plan['parent_checkpoint']['path']),'Edited parent checkpoint')
        del request
        data=read(report['result']['path'])
        require(data['converged'] and data['rejected_steps']==0 and data['accepted_steps']==end-start and
                len(data['snapshots'])==end-start+1 and abs(data['maximum_step']-float(dt))<1e-12,
                'Incomplete refined result')
        if index:require(data['checkpoint_validation']['discrete_replayed'],'Checkpoint not replayed')
        for offset,snapshot in enumerate(data['snapshots']):
            tick=start+offset;value=snapshot_value(snapshot,tick,divisor)
            if tick in samples:require(abs(value-samples[tick]['moment'])<=1e-8,'Restart changed shared state')
            samples[tick]=dict(time=snapshot['time'],moment=value,residual=snapshot['residual'])
            maximum_residual=max(maximum_residual,snapshot['residual'])
        del data
        accepted+=end-start;seconds+=report['seconds']
    require(sorted(samples)==list(range(accepted+1)),'Refined sample gap')
    require(abs(samples[0]['moment']-first['initial_moment'])<=1e-8,'Initial equilibrium differs')
    c={int(k):v['moment'] for k,v in coarse['samples'].items()}
    f={k:v['moment'] for k,v in samples.items()}
    complete=accepted==199*divisor
    gates=refinement_checks(c,f,divisor) if complete else None
    checks=[]
    outputs=[Path(p['path']) for p in first['source_pins'] if Path(p['path']).suffix=='.txt']
    require(len(outputs)==8,'Fixed target inventory changed')
    for path in outputs:
        for row in coarse_audit.native_rows(path):
            predicted=None
            if path.name=='FFWT_Fixed-1.txt':
                tick=(row['row']-1)*divisor;value=Decimal(row['time_token'])
                half=Decimal(10)**value.as_tuple().exponent/2
                require(abs(value-(row['row']-1)*DT)<=half,'Native times disagree')
                if tick in samples:predicted=samples[tick]['moment']
            value=Decimal(row['token']);half=Decimal(10)**value.as_tuple().exponent/2
            checks.append(dict(row,name=path.stem+':row'+str(row['row']),predicted=predicted,
                exact_decimal_expected=str(value),exact_decimal_tolerance=str(half),comparison='<=',
                passed=predicted is not None and abs(Decimal(str(predicted))-value)<=half))
    compared=coarse_audit.apply_reference_acceptance(dict(status='computed',numerical_pass=True,reference_checks=checks))
    computed=[c for c in compared['reference_checks'] if c['predicted'] is not None]
    errors=[100*c['relative_error'] for c in computed];failed=[100*c['relative_error'] for c in computed if not c['passed']]
    summary=dict(computed=len(computed),passed=sum(c['passed'] for c in computed),fixed_history_required=1600,
        uncomputed=1600-len(computed),median_error_percent=statistics.median(errors),maximum_error_percent=max(errors),
        failed_median_percent=statistics.median(failed) if failed else None,
        failed_max_percent=max(failed) if failed else None)
    return dict(status='REFINED_HISTORY_ASSESSED',summary=summary,complete=complete,divisor=divisor,dt=str(dt),
        nominal=first['nominal'],segments=len(chain),accepted_steps=accepted,rejected_steps=0,
        end_time=samples[accepted]['time'],maximum_residual=maximum_residual,segment_seconds=seconds,
        time_accuracy=gates,time_accuracy_passed=sum(g['passed'] for g in gates.values()) if gates else None,
        time_accuracy_required=2,samples=samples,checks=compared['reference_checks'],
        acceptance=compared['reference_acceptance_policy'],coarse_assessment=pin(coarse_path),
        plans=[pin(folder/'plan.json') for folder,_,_ in chain],reports=[pin(folder/'report.json') for folder,_,_ in chain],
        inputs=list(checked.values()),helper=pin(__file__),coarse_helper=pin(ROOT/'scripts/assess-isae-ffwt4-time.py'),
        physical_solves=0,full_family_validated=False,qualifications=first['qualifications'])


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--last-segment',required=True,type=Path)
    ap.add_argument('--coarse-assessment',required=True,type=Path)
    ap.add_argument('--output',required=True,type=Path)
    args=ap.parse_args();require(not args.output.exists(),'Preserve earlier assessments')
    result=assess(args.last_segment,args.coarse_assessment)
    with args.output.open('w') as stream:json.dump(result,stream,indent=2,allow_nan=False);stream.write('\n')
    print(json.dumps(dict(result['summary'],complete=result['complete'],time_accuracy=result['time_accuracy'])),flush=True)


if __name__=='__main__':main()
