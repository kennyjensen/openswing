"""Independently audit a saved FFWT-4 continuation chain and every fixed target."""
import argparse
from decimal import Decimal
import hashlib
import json
import math
from pathlib import Path
import statistics
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.isae_acceptance import apply_reference_acceptance

DT=Decimal('.0149')


def require(value,message):
    if not value:raise ValueError(message)


def pin(path):
    path=Path(path).resolve();h=hashlib.sha256();size=0
    with path.open('rb') as stream:
        while data:=stream.read(1024*1024):h.update(data);size+=len(data)
    return dict(path=str(path),bytes=size,sha256=h.hexdigest())


def read(path):
    with Path(path).open() as stream:return json.load(stream)


def native_rows(path):
    rows=[]
    for line,raw in enumerate(path.read_text().splitlines(),1):
        if not raw.strip() or raw.startswith('#'):continue
        tokens=raw.split();require(len(tokens)==3,'Native columns changed')
        require(int(tokens[0])==len(rows)+1,'Native row gap or duplicate')
        t,value=map(Decimal,tokens[1:])
        require(t.is_finite() and value.is_finite(),'Nonfinite native entry')
        require(not rows or t>Decimal(rows[-1]['time_token']),'Nonmonotonic native time')
        rows.append(dict(row=int(tokens[0]),source=str(path),source_line=line,time_token=tokens[1],token=tokens[2],
            time=float(t),expected=float(value),tolerance=float(Decimal(10)**value.as_tuple().exponent/2)))
    require(len(rows)==200,'Fixed history denominator changed')
    return rows


def snapshot_value(snapshot,tick):
    require(abs(snapshot['time']-float(tick*DT))<=1e-10,'Saved time does not match the command grid')
    require(snapshot['converged'] and math.isfinite(snapshot['residual']) and snapshot['residual']<=1e-8,
            'Unconverged saved state')
    if tick:
        require(snapshot['restart']['accepted_method']['effective_order']==(1 if tick==1 else 2),
                'Ordinary segment boundary changed integration order')
    sensors=[s for s in snapshot['sensors'] if s['index']==1]
    require(len(sensors)==1 and sensors[0]['load_trace']=='left','Root moment trace changed')
    value=sensors[0]['moment_local'][0];require(math.isfinite(value),'Nonfinite root moment')
    return value


def assess(folder):
    chain=[];visited=set();checked={}
    def verify(record):
        if record['path'] in checked:require(record==checked[record['path']],'Conflicting source pins')
        else:require(pin(record['path'])==record,'Changed evidence: '+record['path']);checked[record['path']]=record
    while True:
        folder=folder.resolve();require(folder not in visited,'Cyclic checkpoint ancestry');visited.add(folder)
        plan,report=read(folder/'plan.json'),read(folder/'report.json')
        require(plan['schema']=='isae-ffwt4-fixed1-time-v1' and report['status']=='SEGMENT_COMPUTED','Incomplete segment')
        require(report['source_pins_unchanged'] and report['kernel_pins_unchanged'],'Unverified sources')
        for p in plan['source_pins']+plan['kernel_pins']+[plan['helper'],plan['initial_helper']]:verify(p)
        for key in ('initial_plan','initial_result','initial_report','parent_time_helper','parent_plan','parent_report','parent_checkpoint'):
            if key in plan:verify(plan[key])
        verify(report['result']);verify(report['checkpoint'])
        chain.append((folder,plan,report))
        if 'parent_checkpoint' not in plan:break
        folder=Path(plan['parent_checkpoint']['path']).parent
    chain.reverse();first=chain[0][1];samples={};maximum_residual=0.;accepted=0
    for i,(folder,plan,report) in enumerate(chain):
        require(plan['source_pins']==first['source_pins'] and plan['kernel_pins']==first['kernel_pins'] and
                plan['nominal']==first['nominal'],'Continuation changed model, kernel or mesh')
        start,end=plan['start_step'],plan['end_step']
        require(start==(chain[i-1][1]['end_step'] if i else 0) and start<end<=199,'Noncontiguous segment coverage')
        require(report['start_step']==start and report['end_step']==end and report['accepted_steps']==end-start and
                report['rejected_steps']==0,'Segment accounting differs')
        data=read(report['result']['path'])
        require(data['converged'] and data['rejected_steps']==0 and data['accepted_steps']==end-start and
                len(data['snapshots'])==end-start+1 and abs(data['maximum_step']-float(DT))<1e-12,'Incomplete saved history')
        if i:require(data['checkpoint_validation']['discrete_replayed'],'Checkpoint was not replayed')
        for j,snapshot in enumerate(data['snapshots']):
            tick=start+j;value=snapshot_value(snapshot,tick)
            if tick in samples:require(abs(value-samples[tick]['moment'])<=1e-8,'Restart changed the shared output state')
            samples[tick]=dict(time=snapshot['time'],moment=value,residual=snapshot['residual'],
                               reference_gust=snapshot.get('gust',{}).get('reference_velocity_earth'))
            maximum_residual=max(maximum_residual,snapshot['residual'])
        accepted+=end-start
        del data
    require(sorted(samples)==list(range(accepted+1)),'History samples are not contiguous')
    outputs=[Path(p['path']) for p in first['source_pins'] if Path(p['path']).suffix=='.txt']
    require(len(outputs)==8,'Fixed-wing history inventory changed')
    checks=[]
    for path in outputs:
        for row in native_rows(path):
            predicted=None
            if path.name=='FFWT_Fixed-1.txt':
                tick=row['row']-1;value=Decimal(row['time_token']);half=Decimal(10)**value.as_tuple().exponent/2
                require(abs(value-tick*DT)<=half,'Driver and native time grid disagree')
                if tick in samples:predicted=samples[tick]['moment']
            value=Decimal(row['token']);half=Decimal(10)**value.as_tuple().exponent/2
            checks.append(dict(row,name=path.stem+':row'+str(row['row']),predicted=predicted,
                exact_decimal_expected=str(value),exact_decimal_tolerance=str(half),comparison='<=',
                passed=predicted is not None and abs(Decimal(str(predicted))-value)<=half))
    result=apply_reference_acceptance(dict(status='computed',numerical_pass=True,reference_checks=checks,
        output_accounting=dict(required=1600,computed=len(samples),missing=1600-len(samples))))
    computed=[c for c in result['reference_checks'] if c['predicted'] is not None]
    failed=[100*c['relative_error'] for c in computed if not c['passed']]
    summary=dict(computed=len(computed),passed=sum(c['passed'] for c in computed),selected_history_required=200,
        fixed_history_required=1600,uncomputed=1600-len(computed),
        maximum_error_percent=max(100*c['relative_error'] for c in computed),
        median_error_percent=statistics.median(100*c['relative_error'] for c in computed),
        failed_median_percent=statistics.median(failed) if failed else None,failed_max_percent=max(failed) if failed else None)
    return dict(status='SAVED_HISTORY_ASSESSED',summary=summary,checks=result['reference_checks'],
        acceptance=result['reference_acceptance_policy'],segments=len(chain),accepted_steps=accepted,rejected_steps=0,
        end_time=samples[accepted]['time'],maximum_residual=maximum_residual,nominal=first['nominal'],
        samples=samples,inputs=list(checked.values()),
        plans=[pin(f/'plan.json') for f,_,_ in chain],reports=[pin(f/'report.json') for f,_,_ in chain],
        physical_solves=0,full_family_validated=False,
        seed_study_qualifications=first['qualifications'],
        qualifications=[q for q in first['qualifications'] if not q.startswith('Only one initial native value')]+[
            'Computed coverage is exactly the contiguous saved prefix reported in summary; later rows are never extrapolated.',
            'Other fixed histories, hinged models, shared registration and strict time/mesh convergence remain required.'],
        helper=pin(__file__))


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--last-segment',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args();require(not args.output.exists(),'Preserve previous assessments; choose a new output')
    result=assess(args.last_segment)
    with args.output.open('w') as stream:json.dump(result,stream,indent=2,allow_nan=False);stream.write('\n')
    print(json.dumps(dict(result['summary'],end_time=result['end_time'],maximum_residual=result['maximum_residual'])),flush=True)


if __name__=='__main__':main()
