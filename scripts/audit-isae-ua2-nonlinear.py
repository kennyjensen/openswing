"""Audit complete finite-amplitude UA-2 histories against independent equations."""
import argparse
import gzip
from hashlib import sha256
import json
from pathlib import Path

import numpy as np

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'artifacts/isae/ua2-nonlinear-20261101'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--panels',type=int,choices=(20,40),required=True)
    parser.add_argument('--base-dir',type=Path,default=BASE)
    args=parser.parse_args();base=args.base_dir.resolve();output=base/f'audit-n{args.panels}.json'
    if output.exists():parser.error('Preserve completed audits')
    batch=json.loads((base/'batch-plan.json').read_text());gates=batch['gates']
    for name,digest in batch['source_sha256'].items():
        # Historical tooling is verified against its preserved producer.
        # Current production equations must still match exactly for reuse.
        assert sha256((base/'frozen-code'/name).read_bytes()).hexdigest()==digest,name
        if name.startswith('openswing/'):
            assert sha256((ROOT/name).read_bytes()).hexdigest()==digest,name
    reference=json.loads((base/f'reference-n{args.panels}.json').read_text())
    amplitude,k=reference['plan']['amplitude_ratio'],reference['plan']['k']
    assert amplitude in (.05,.1,.3,.5) and k in (.475,.95)
    assert reference['numerical_passed'] and max(reference['method_difference_fractions'].values())<1e-8
    reference_rows=reference['reference']['DOP853']['rows'];reference_times=np.array([r['time'] for r in reference_rows])
    records=[];count=0
    for steps in (80,160):
        snapshots=[];maximum_join=0.;seconds=[];persist=[];last=None
        jobs=[j for j in batch['jobs'] if j['panels']==args.panels and j['steps']==steps]
        for job in jobs:
            folder=base/job['id'];plan=json.loads((folder/'plan.json').read_text());report=json.loads((folder/'report.json').read_text())
            receipt=json.loads((base/(job['id']+'-execution.json')).read_text())
            assert receipt['exit_code']==0 and receipt['report_sha256']==sha256((folder/'report.json').read_bytes()).hexdigest()
            assert report['converged'] and report['rejected_steps']==0 and report['source_unchanged']
            assert plan['steps']==steps and plan['panels']==args.panels and plan['amplitude_ratio']==amplitude and plan['k']==k
            assert all(batch['source_sha256'][n]==h for n,h in plan['source_sha256'].items())
            for name,digest in plan['parent_sha256'].items():
                assert sha256((Path(plan['parent'])/name).read_bytes()).hexdigest()==digest
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
        assert len(times)==len(grid);np.testing.assert_allclose(times,grid,atol=1e-12,rtol=0)
        count+=len(times)
        indices=[int(np.argmin(abs(reference_times-t))) for t in times]
        assert max(abs(reference_times[i]-t) for i,t in zip(indices,times))<1e-12
        expected=[reference_rows[i] for i in indices]
        cl=np.array([s['force'][2]/(.5*1.225*100*10) for s in snapshots]);ref_cl=np.array([r['CL'] for r in expected])
        gamma=np.array([[r['circulation'] for r in s['strips']] for s in snapshots]);ref_gamma=np.array([r['circulation'] for r in expected])
        rate=np.array([s['circulation_rate'] for s in snapshots]);ref_rate=np.array([r['circulation_rate'] for r in expected])
        lift_error=float(np.max(abs(cl-ref_cl))/np.max(abs(ref_cl)))
        strip_peak=np.max(abs(ref_rate),axis=0)
        rate_error=float(np.max(abs(rate-ref_rate)/strip_peak))
        assert np.min(abs(ref_rate[1]))>1e-14
        first_error=float(np.max(abs(rate[1]-ref_rate[1])/abs(ref_rate[1])))
        maximum_acceleration_error=maximum_velocity_error=maximum_residual=0.
        for i,(s,r) in enumerate(zip(snapshots,expected)):
            assert s['residual']<1e-10
            if i>0:assert s['order']==(1 if i==1 else 2)
            assert max(abs(v) for v in s['frame']['rates_body']+s['frame']['attitude'])<1e-12
            maximum_residual=max(maximum_residual,s['residual'])
            maximum_acceleration_error=max(maximum_acceleration_error,abs(s['frame']['acceleration_reference_body'][2]-r['acceleration']))
            maximum_velocity_error=max(maximum_velocity_error,abs(s['frame']['velocity_origin_body'][2]-r['velocity']))
        assert maximum_acceleration_error<1e-10
        passed=(lift_error<gates['fine_lift_waveform_error_fraction'] and rate_error<gates['fine_per_strip_rate_waveform_error_fraction']
            and first_error<gates['fine_first_step_relative_rate_error_fraction'])
        records.append(dict(nominal_steps=steps,accepted_steps=len(times)-1,unique_snapshots=len(times),
            lift_waveform_error_fraction=lift_error,per_strip_rate_waveform_error_fraction=rate_error,
            first_step_relative_rate_error_fraction=first_error,
            circulation_waveform_error_fraction=float(np.max(abs(gamma-ref_gamma))/np.max(abs(ref_gamma))),
            fine_accuracy_gates_passed=passed,maximum_residual=maximum_residual,maximum_checkpoint_join_jump=maximum_join,
            maximum_acceleration_error=maximum_acceleration_error,maximum_velocity_error=maximum_velocity_error,
            segment_seconds=seconds,persistence_seconds=persist,
            waveform=dict(times=times.tolist(),CL=cl.tolist(),reference_CL=ref_cl.tolist(),
                circulation=gamma.tolist(),reference_circulation=ref_gamma.tolist(),
                circulation_rate=rate.tolist(),reference_rate=ref_rate.tolist())))
    ratio=records[-1]['lift_waveform_error_fraction']/records[0]['lift_waveform_error_fraction']
    passed=records[-1]['fine_accuracy_gates_passed'] and ratio<gates['successive_lift_error_ratio_maximum']
    result=dict(scope=batch['scope'],panels=args.panels,amplitude_ratio=amplitude,k=k,records=records,
        audited_unique_snapshots=count,lift_refinement_ratio=ratio,refinement_check_passed=passed,
        independent_spatial_reference=True,native_ASWING_comparison=False,
        reference_method_difference_fractions=reference['method_difference_fractions'],
        auditor_sha256=sha256(Path(__file__).read_bytes()).hexdigest())
    output.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps(dict(panels=args.panels,passed=passed,audited_snapshots=count,lift_error_ratio=ratio,
        lift_error_percent=100*records[-1]['lift_waveform_error_fraction'],
        local_rate_error_percent=100*records[-1]['per_strip_rate_waveform_error_fraction'],
        first_step_relative_rate_error_percent=100*records[-1]['first_step_relative_rate_error_fraction'])),flush=True)
    if not passed:raise SystemExit(1)


if __name__=='__main__':main()
