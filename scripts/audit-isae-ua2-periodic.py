"""Audit every UA-2 snapshot and seven phase-aligned post-startup cycles."""
import argparse
import gzip
from hashlib import sha256
import json
import math
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[1]


def measurements(times,values,period):
    weights=np.diff(times)/period
    def integral(y):return np.sum(weights*(y[:-1]+y[1:])/2)
    phase=2*math.pi*(times-times[0])/period
    harmonics=[]
    for order in (1,2,3):
        h=2*integral(values*np.exp(-1j*order*phase))
        harmonics.append(dict(order=order,cosine=float(h.real),sine=float(-h.imag),
            amplitude=float(abs(h)),phase_deg=float(np.angle(h,deg=True)%360)))
    return dict(mean=float(integral(values)),harmonics=harmonics)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--panels',type=int,choices=(20,40),required=True)
    parser.add_argument('--base-dir',type=Path,required=True)
    args=parser.parse_args();base=args.base_dir.resolve();output=base/f'audit-n{args.panels}.json'
    if output.exists():parser.error('Preserve completed audits')
    batch=json.loads((base/'batch-plan.json').read_text());gates=batch['gates']
    for name,digest in batch['source_sha256'].items():
        assert sha256((base/'frozen-code'/name).read_bytes()).hexdigest()==digest,name
        assert sha256((ROOT/name).read_bytes()).hexdigest()==digest,name
    reference=json.loads((base/f'reference-n{args.panels}.json').read_text())
    assert reference['numerical_passed'] and max(reference['method_difference_fractions'].values())<1e-8
    assert reference['plan']['cycles']==8 and reference['plan']['panels']==args.panels
    period=math.pi/9.5;records=[];audited=0
    reference_rows=reference['reference']['DOP853']['cold']['rows']
    reference_times=np.array([r['time'] for r in reference_rows])
    periodic=reference['reference']['DOP853']['periodic']
    for method in ('DOP853','Radau'):
        p=reference['reference'][method]['periodic']
        assert p['closure_fraction']<1e-11 and p['half_cycle_lift_symmetry_error_fraction']<1e-9
        assert abs(p['measurements']['mean'])<1e-10
    for steps in (80,160):
        snapshots=[];maximum_join=0.;seconds=[];persist=[];last=None
        jobs=[j for j in batch['jobs'] if j['panels']==args.panels and j['steps']==steps]
        for job in jobs:
            folder=base/job['id'];plan=json.loads((folder/'plan.json').read_text());report=json.loads((folder/'report.json').read_text())
            receipt=json.loads((base/(job['id']+'-execution.json')).read_text())
            assert receipt['exit_code']==0 and receipt['report_sha256']==sha256((folder/'report.json').read_bytes()).hexdigest()
            assert report['converged'] and report['rejected_steps']==0 and report['source_unchanged']
            assert plan['steps']==steps and plan['panels']==args.panels and plan['amplitude_ratio']==.5 and plan['k']==.95 and plan['cycles']==8
            assert all(batch['source_sha256'][n]==h for n,h in plan['source_sha256'].items())
            for name,digest in plan['parent_sha256'].items():assert sha256((Path(plan['parent'])/name).read_bytes()).hexdigest()==digest
            full=plan['full_request'];assert full['condition']['stall'] is False and full['condition']['aero_lag'] is True
            assert full['condition']['mach']==0 and full['condition']['gravity_magnitude']==0
            assert report['structural_operator']=='drela-moving-airflow-v1' and report['temporal_policy']=='drela-euler-bdf-v1'
            with gzip.open(folder/'trajectory.json.gz','rt') as stream:raw=json.load(stream)
            part=raw['snapshots'];assert len(part)==report['accepted_steps']+1
            assert report['accepted_steps']==plan['end_index']-plan['start_index']
            if last is not None:
                jump=max(float(np.max(np.abs(np.array(last[n])-np.array(part[0][n])))) for n in ('force','circulation_rate'))
                maximum_join=max(maximum_join,jump);assert jump<1e-12
                assert [r['circulation'] for r in last['strips']]==[r['circulation'] for r in part[0]['strips']]
            snapshots.extend(part if last is None else part[1:]);last=part[-1]
            seconds.append(report['seconds']);persist.append(report['persistence_seconds'])
        grid=np.array(reference['grids'][str(steps)]);times=np.array([s['time'] for s in snapshots])
        assert len(times)==len(grid)==8*steps+41
        np.testing.assert_allclose(times,grid,atol=1e-12,rtol=0);audited+=len(times)
        indices=[int(np.argmin(abs(reference_times-t))) for t in times]
        assert max(abs(reference_times[i]-t) for i,t in zip(indices,times))<1e-12
        expected=[reference_rows[i] for i in indices]
        cl=np.array([s['force'][2]/(.5*1.225*100*10) for s in snapshots]);ref_cl=np.array([r['CL'] for r in expected])
        gamma=np.array([[r['circulation'] for r in s['strips']] for s in snapshots]);ref_gamma=np.array([r['circulation'] for r in expected])
        rate=np.array([s['circulation_rate'] for s in snapshots]);ref_rate=np.array([r['circulation_rate'] for r in expected])
        lift_error=float(np.max(abs(cl-ref_cl))/np.max(abs(ref_cl)))
        rate_error=float(np.max(abs(rate-ref_rate)/np.max(abs(ref_rate),axis=0)))
        first_error=float(np.max(abs(rate[1]-ref_rate[1])/abs(ref_rate[1])))
        max_acceleration_error=max_velocity_error=max_position_error=max_residual=0.
        for i,(s,r) in enumerate(zip(snapshots,expected)):
            assert s['residual']<1e-10
            if i>0:assert s['order']==(1 if i==1 else 2)
            assert max(abs(v) for v in s['frame']['rates_body']+s['frame']['attitude'])<1e-12
            max_residual=max(max_residual,s['residual'])
            max_acceleration_error=max(max_acceleration_error,abs(s['frame']['acceleration_reference_body'][2]-r['acceleration']))
            max_velocity_error=max(max_velocity_error,abs(s['frame']['velocity_origin_body'][2]-r['velocity']))
            max_position_error=max(max_position_error,abs(s['frame']['position_earth'][2]-.25*math.cos(19*s['time'])))
        assert max_acceleration_error<1e-10
        cycles=[];previous=None
        ref_periodic=periodic['rows'][::160//steps]
        phase_times=np.array([r['time'] for r in ref_periodic]);p_cl=np.array([r['CL'] for r in ref_periodic])
        p_rate=np.array([r['circulation_rate'] for r in ref_periodic]);p_gamma=np.array([r['circulation'] for r in ref_periodic])
        peak=float(np.max(abs(p_cl)));fundamental=periodic['measurements']['harmonics'][0]
        # The first cycle's graded samples remain in the complete cold audit.
        # Cycles 2-8 have identical phase samples and can be compared directly.
        for cycle in range(2,9):
            ix=[int(np.argmin(abs(times-((cycle-1)*period+t)))) for t in phase_times]
            local=times[ix]-(cycle-1)*period
            np.testing.assert_allclose(local,phase_times,rtol=0,atol=1e-12)
            actual=cl[ix];measured=measurements(local,actual,period);a=measured['harmonics'][0]
            change=None if previous is None else float(np.max(abs(actual-previous))/peak)
            row=dict(cycle=cycle,waveform_error_fraction=float(np.max(abs(actual-p_cl))/peak),
                per_strip_rate_error_fraction=float(np.max(abs(rate[ix]-p_rate)/np.max(abs(p_rate),axis=0))),
                circulation_error_fraction=float(np.max(abs(gamma[ix]-p_gamma))/np.max(abs(p_gamma))),
                amplitude_error_fraction=a['amplitude']/fundamental['amplitude']-1,
                phase_error_deg=(a['phase_deg']-fundamental['phase_deg']+180)%360-180,
                mean_error_peak_fraction=(measured['mean']-periodic['measurements']['mean'])/peak,
                change_fraction=change,measurements=measured)
            cycles.append(row);previous=actual
        final=cycles[-1]
        accuracy=(lift_error<gates['fine_lift_waveform_error_fraction'] and rate_error<gates['fine_per_strip_rate_waveform_error_fraction']
            and first_error<gates['fine_first_step_relative_rate_error_fraction']
            and final['waveform_error_fraction']<gates['final_cycle_waveform_error_fraction']
            and final['per_strip_rate_error_fraction']<gates['fine_per_strip_rate_waveform_error_fraction']
            and abs(final['amplitude_error_fraction'])<gates['final_cycle_amplitude_error_fraction']
            and abs(final['phase_error_deg'])<gates['final_cycle_phase_error_deg']
            and abs(final['mean_error_peak_fraction'])<gates['final_cycle_mean_error_peak_fraction']
            and final['change_fraction']<gates['final_cycle_change_fraction'])
        records.append(dict(nominal_steps=steps,accepted_steps=len(times)-1,unique_snapshots=len(times),
            lift_waveform_error_fraction=lift_error,per_strip_rate_waveform_error_fraction=rate_error,
            first_step_relative_rate_error_fraction=first_error,
            circulation_waveform_error_fraction=float(np.max(abs(gamma-ref_gamma))/np.max(abs(ref_gamma))),
            periodic_accuracy_gates_passed=accuracy,maximum_residual=max_residual,maximum_checkpoint_join_jump=maximum_join,
            maximum_acceleration_error=max_acceleration_error,maximum_velocity_error=max_velocity_error,maximum_position_error=max_position_error,
            segment_seconds=seconds,persistence_seconds=persist,cycles=cycles,
            waveform=dict(times=times.tolist(),CL=cl.tolist(),reference_CL=ref_cl.tolist()),
            final_waveform=dict(times=phase_times.tolist(),CL=actual.tolist(),reference_CL=p_cl.tolist())))
    ratio=records[-1]['cycles'][-1]['waveform_error_fraction']/records[0]['cycles'][-1]['waveform_error_fraction']
    cold_ratio=records[-1]['lift_waveform_error_fraction']/records[0]['lift_waveform_error_fraction']
    passed=records[-1]['periodic_accuracy_gates_passed'] and max(ratio,cold_ratio)<gates['successive_lift_error_ratio_maximum']
    result=dict(scope=batch['scope'],panels=args.panels,amplitude_ratio=.5,k=.95,cycles=8,records=records,
        audited_unique_snapshots=audited,lift_refinement_ratio=cold_ratio,periodic_refinement_ratio=ratio,
        periodic_check_passed=passed,independent_spatial_reference=True,native_ASWING_comparison=False,
        reference_periodic_measurements=periodic['measurements'],reference_closure_fraction=periodic['closure_fraction'],
        reference_method_difference_fractions=reference['method_difference_fractions'],
        auditor_sha256=sha256(Path(__file__).read_bytes()).hexdigest())
    output.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps(dict(panels=args.panels,passed=passed,audited_snapshots=audited,periodic_error_ratio=ratio,
        fine_final_cycle=records[-1]['cycles'][-1],fine_cold_error_percent=100*records[-1]['lift_waveform_error_fraction'])),flush=True)
    if not passed:raise SystemExit(1)


if __name__=='__main__':main()
