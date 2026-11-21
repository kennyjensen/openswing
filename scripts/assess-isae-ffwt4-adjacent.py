"""Compare independently audited adjacent FFWT-4 grids at every shared physical tick."""
import argparse
from decimal import Decimal
import importlib.util
import json
import math
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('ffwt4_audit',ROOT/'scripts/assess-isae-ffwt4-time.py')
audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)
pin,read,require=audit.pin,audit.read,audit.require
NATIVE_DT=Decimal('.0149')


def compare(coarser,finer,coarser_divisor,finer_divisor,*,native_ticks=False):
    require(coarser_divisor==2 and finer_divisor==4,'Expected independently computed half and quarter grids')
    require(sorted(coarser)==list(range(199*coarser_divisor+1)),'Incomplete coarser history')
    require(sorted(finer)==list(range(199*finer_divisor+1)),'Incomplete finer history')
    require(all(math.isfinite(v) for v in list(coarser.values())+list(finer.values())),'Nonfinite saved moment')
    indices=[i*coarser_divisor for i in range(200)] if native_ticks else list(range(len(coarser)))
    ratio=finer_divisor//coarser_divisor
    c=[coarser[i] for i in indices];f=[finer[i*ratio] for i in indices]
    gates={}
    for name,cv,fv in [('root_moment',c,f),('gust_increment',[v-c[0] for v in c],[v-f[0] for v in f])]:
        scale=max(map(abs,fv));require(scale>0,'Zero accuracy scale')
        difference=[abs(a-b) for a,b in zip(cv,fv)]
        worst=max(range(len(indices)),key=difference.__getitem__)
        gates[name]=dict(maximum_absolute_difference=max(difference),scale=scale,
            maximum_percent_of_scale=100*max(difference)/scale,
            rms_percent_of_scale=100*math.sqrt(sum(d*d for d in difference)/len(difference))/scale,
            relative_limit=.001,passed=max(difference)<=.001*scale,
            worst_coarser_tick=indices[worst],worst_time=float(indices[worst]*NATIVE_DT/coarser_divisor))
    return dict(common_samples=len(indices),gates=gates,passed=sum(g['passed'] for g in gates.values()),required=2)


def verified_samples(data):
    require(data['status']=='REFINED_HISTORY_ASSESSED' and data['complete'] and data['divisor'] in (2,4),
            'Complete refinement assessment required')
    divisor=data['divisor'];dt=NATIVE_DT/divisor
    require(Decimal(data['dt'])==dt and data['accepted_steps']==199*divisor and data['rejected_steps']==0,
            'Incomplete or changed time grid')
    samples={int(k):v for k,v in data['samples'].items()}
    require(sorted(samples)==list(range(199*divisor+1)),'Incomplete sample coverage')
    for tick,value in samples.items():
        require(abs(value['time']-float(tick*dt))<=1e-10,'Saved time differs')
        require(math.isfinite(value['residual']) and value['residual']<=1e-8 and math.isfinite(value['moment']),
                'Invalid saved state')
    return {k:v['moment'] for k,v in samples.items()}


def assess(coarser_path,finer_path):
    coarser,finer=read(coarser_path),read(finer_path);checked={}
    for data in (coarser,finer):
        for record in data['inputs']+data['plans']+data['reports']+[data[k] for k in
                ('helper','coarse_helper','coarse_assessment')]:
            if record['path'] in checked:require(record==checked[record['path']],'Conflicting evidence pins')
            else:
                require(pin(record['path'])==record,'Changed evidence: '+record['path'])
                checked[record['path']]=record
    c,f=verified_samples(coarser),verified_samples(finer)
    cp,fp=(read(data['plans'][0]['path']) for data in (coarser,finer))
    for key in ('source_pins','kernel_pins','nominal','initial_plan','initial_request','initial_result','initial_report','initial_helper'):
        require(cp[key]==fp[key],'Time refinement changed physical setup: '+key)
    require(cp['accuracy_gate']==fp['accuracy_gate'] and cp['accuracy_gate']['relative']==.001,'Accuracy gate changed')
    require(coarser['coarse_assessment']==finer['coarse_assessment'],'Original-grid evidence differs')
    require(abs(c[0]-f[0])<=1e-8,'Initial equilibrium differs')
    all_common=compare(c,f,coarser['divisor'],finer['divisor'])
    native_common=compare(c,f,coarser['divisor'],finer['divisor'],native_ticks=True)
    combined={key:all_common['gates'][key]['passed'] and native_common['gates'][key]['passed']
              for key in all_common['gates']}
    ratios={}
    for key,g in native_common['gates'].items():
        previous=coarser['time_accuracy'][key]['maximum_absolute_difference']
        ratios[key]=previous/g['maximum_absolute_difference'] if g['maximum_absolute_difference'] else None
    return dict(status='ADJACENT_GRIDS_ASSESSED',coarser_assessment=pin(coarser_path),finer_assessment=pin(finer_path),
        steps=[coarser['dt'],finer['dt']],native_summary=finer['summary'],all_shared_ticks=all_common,
        original_native_ticks=native_common,combined_accuracy=dict(gates=combined,passed=sum(combined.values()),required=2),
        successive_maximum_change_ratio=ratios,
        coarser_native_grid_comparison=coarser['time_accuracy'],finer_native_grid_comparison=finer['time_accuracy'],
        inputs=list(checked.values()),helper=pin(__file__),physical_solves=0,full_family_validated=False,
        qualifications=[
            'Both histories start independently from the same equilibrium; only dt differs.',
            'The original 200-tick accuracy gates remain; every one of the 399 shared half-grid ticks is checked additionally.',
            'Strict 0.1% accuracy is separate from the 5% native-reference comparison.',
            'No interpolation, fitted phase/amplitude, or extrapolation is used.',
            'The change ratio is a diagnostic, not a measured global order or an extrapolated solution.',
            'Root-moment time accuracy does not certify all state variables, mesh accuracy, other histories or full-family validation.'])


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--coarser',required=True,type=Path)
    ap.add_argument('--finer',required=True,type=Path)
    ap.add_argument('--output',required=True,type=Path)
    args=ap.parse_args();require(not args.output.exists(),'Preserve earlier assessments')
    result=assess(args.coarser,args.finer)
    with args.output.open('w') as stream:json.dump(result,stream,indent=2,allow_nan=False);stream.write('\n')
    print(json.dumps({k:result[k] for k in ('native_summary','combined_accuracy','all_shared_ticks','original_native_ticks','successive_maximum_change_ratio')}),flush=True)


if __name__=='__main__':main()
