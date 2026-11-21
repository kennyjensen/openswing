"""Independently audit all eight UA-1 cycles at one amplitude, two timesteps."""
import argparse
import gzip
from hashlib import sha256
import json
import math
from pathlib import Path

import numpy as np
from scipy.integrate import solve_ivp

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'artifacts/isae/ua1-periodic-20261101'


def measurements(times,values,period):
    # Independent complex trapezoidal integral, including both endpoints.
    weights=np.diff(times)/period
    def integral(y):return np.sum(weights*(y[:-1]+y[1:])/2)
    phase=2*math.pi*(times-times[0])/period
    harmonics=[]
    for n in (1,2,3):
        h=2*integral(values*np.exp(-1j*n*phase))
        harmonics.append(dict(order=n,cosine=float(h.real),sine=float(-h.imag),
            amplitude=float(abs(h)),phase_deg=float(np.angle(h,deg=True)%360)))
    return dict(mean=float(integral(values)),harmonics=harmonics)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--amplitude-ratio',type=float,choices=(.05,.1,.3,.5),required=True)
    args=parser.parse_args();amplitude=args.amplitude_ratio
    tag={.05:'005',.1:'010',.3:'030',.5:'050'}[amplitude]
    output=BASE/f'audit-a{tag}.json'
    if output.exists():parser.error('Preserve completed audits')
    batch=json.loads((BASE/'plan.json').read_text());gates=batch['gates']
    for name,digest in batch['source_sha256'].items():
        assert sha256((ROOT/name).read_bytes()).hexdigest()==digest,name
        assert sha256((BASE/'frozen-code'/name).read_bytes()).hexdigest()==digest,name
    speed,k=10.,.95;period=math.pi/(speed*k);omega=2*speed*k;qs=.5*1.225*speed**2*200000
    def derivative(t,y):
        w=-amplitude/2*omega*math.sin(omega*t)
        return [-speed*y[0]/2-math.pi*math.hypot(speed,w)*w/2]
    initial_cold=solve_ivp(derivative,(0,period),[0.],method='DOP853',rtol=1e-12,atol=1e-13)
    assert initial_cold.success
    initial_periodic=initial_cold.y[0,-1]/(-math.expm1(-5*period))
    periodic=solve_ivp(derivative,(0,period),[initial_periodic],method='DOP853',rtol=1e-12,atol=1e-13,dense_output=True)
    assert periodic.success and abs(periodic.y[0,-1]-initial_periodic)<1e-10
    def loads(times,gamma):
        velocity=-amplitude/2*omega*np.sin(omega*times)
        acceleration=-amplitude/2*omega**2*np.cos(omega*times)
        crossflow=np.hypot(speed,velocity)
        rate=-speed*gamma/2-math.pi*crossflow*velocity/2
        cl=2*gamma/speed+2*rate/(speed*crossflow)-math.pi*acceleration/(2*speed**2)
        return cl,rate
    dense_times=np.linspace(0,period,4097)
    dense_cl,_=loads(dense_times,periodic.sol(dense_times)[0])
    dense_measurements=measurements(dense_times,dense_cl,period)
    assert abs(dense_measurements['mean'])<1e-10
    refinements=[];audited=0
    for steps in (80,160):
        cycles=[];all_times=[];all_cl=[];all_gamma=[];all_rate=[]
        last=None;previous=None;maximum_join=0.;max_residual=0.;max_acceleration_error=0.
        for cycle in range(1,9):
            folder=BASE/f'a{tag}-n{steps}-cycle{cycle:02}'
            plan=json.loads((folder/'plan.json').read_text());report=json.loads((folder/'report.json').read_text())
            execution=json.loads((BASE/(folder.name+'-execution.json')).read_text())
            assert execution['exit_code']==0 and execution['report_sha256']==sha256((folder/'report.json').read_bytes()).hexdigest()
            assert report['converged'] and report['source_unchanged'] and report['rejected_steps']==0
            assert plan['cycle']==cycle and plan['steps']==steps and plan['amplitude_ratio']==amplitude
            assert plan['k']==.95 and plan['panels']==4 and plan['aspect_ratio']==200000.
            assert all(batch['source_sha256'][name]==digest for name,digest in plan['source_sha256'].items())
            assert report['accepted_steps']==steps and report['maximum_residual']<1e-10
            assert report['structural_operator']=='drela-moving-airflow-v1' and report['temporal_policy']=='drela-euler-bdf-v1'
            for name,digest in plan['parent_sha256'].items():
                assert sha256((Path(plan['parent'])/name).read_bytes()).hexdigest()==digest
            with gzip.open(folder/'trajectory.json.gz','rt') as stream:raw=json.load(stream)
            samples=raw['snapshots'];assert len(samples)==steps+1
            times=np.array([s['time'] for s in samples]);local=times-(cycle-1)*period
            np.testing.assert_allclose(times,np.arange((cycle-1)*steps,cycle*steps+1)*period/steps,rtol=0,atol=1e-12)
            cl=np.array([s['force'][2]/qs for s in samples])
            gamma=np.array([[r['circulation'] for r in s['strips']] for s in samples])
            rate=np.array([s['circulation_rate'] for s in samples])
            expected_cl,expected_rate=loads(local,periodic.sol(local)[0])
            scale=float(np.max(np.abs(expected_cl)))
            actual_measurements=measurements(local,cl,period)
            reference_measurements=measurements(local,expected_cl,period)
            for a,b in zip(actual_measurements['harmonics'],report['measured']['harmonics']):
                assert abs(a['amplitude']-b['amplitude'])<1e-12
                if a['amplitude']>1e-10:assert abs((a['phase_deg']-b['phase_deg']+180)%360-180)<1e-7
            assert abs(actual_measurements['mean']-report['measured']['mean'])<1e-12
            for a,b in zip(reference_measurements['harmonics'],report['reference']['harmonics']):
                assert abs(a['amplitude']-b['amplitude'])<1e-10
            if last is not None:
                join=max(float(np.max(np.abs(np.asarray(last[key])-np.asarray(samples[0][key]))))
                         for key in ('force','circulation_rate'))
                assert join<1e-12
                assert [r['circulation'] for r in last['strips']]==[r['circulation'] for r in samples[0]['strips']]
                maximum_join=max(maximum_join,join)
            last=samples[-1]
            for index,s in enumerate(samples):
                assert s['residual']<1e-10
                if index>0:assert s['order']==(1 if cycle==1 and index==1 else 2)
                assert max(abs(v) for v in s['frame']['attitude']+s['frame']['rates_body'])<1e-12
                acc=-amplitude/2*omega**2*math.cos(omega*s['time'])
                max_acceleration_error=max(max_acceleration_error,abs(s['frame']['acceleration_reference_body'][2]-acc))
                max_residual=max(max_residual,s['residual'])
            assert max_acceleration_error<1e-10
            # Keep every original time; remove only shared checkpoint endpoints.
            start=0 if cycle==1 else 1
            all_times.extend(times[start:]);all_cl.extend(cl[start:]);all_gamma.extend(gamma[start:]);all_rate.extend(rate[start:])
            a=actual_measurements['harmonics'][0];b=dense_measurements['harmonics'][0]
            change=None if previous is None else float(np.max(np.abs(cl-previous))/scale)
            wave=float(np.max(np.abs(cl-expected_cl))/scale)
            assert abs(wave-report['periodic_waveform_error_fraction'])<1e-9
            if change is not None:assert abs(change-report['previous_cycle_waveform_change_fraction'])<1e-9
            cycles.append(dict(cycle=cycle,solver_seconds=report['seconds'],persistence_seconds=report['persistence_seconds'],
                waveform_error_fraction=wave,change_fraction=change,
                amplitude_error_fraction=a['amplitude']/b['amplitude']-1,
                phase_error_deg=(a['phase_deg']-b['phase_deg']+180)%360-180,
                mean_error_peak_fraction=(actual_measurements['mean']-dense_measurements['mean'])/scale,
                measurements=actual_measurements,maximum_velocity_error=float(np.max(np.abs(
                    np.array([s['frame']['velocity_origin_body'][2] for s in samples])+amplitude/2*omega*np.sin(omega*times)))),
                maximum_position_error=float(np.max(np.abs(np.array([s['frame']['position_earth'][2] for s in samples])-
                    amplitude/2*np.cos(omega*times)))),
                reference_quadrature_amplitude_difference=reference_measurements['harmonics'][0]['amplitude']-b['amplitude']))
            previous=cl
        times=np.asarray(all_times);actual=np.asarray(all_cl);gamma=np.asarray(all_gamma);rate=np.asarray(all_rate)
        audited+=len(times);assert len(times)==8*steps+1
        cold=solve_ivp(derivative,(0,float(times[-1])),[0.],t_eval=times,method='DOP853',rtol=1e-12,atol=1e-13)
        assert cold.success
        cold_cl,cold_rate=loads(times,cold.y[0])
        cold_error=float(np.max(np.abs(actual-cold_cl))/np.max(np.abs(cold_cl)))
        final=cycles[-1]
        passed=(final['waveform_error_fraction']<gates['final_cycle_waveform_error_fraction']
            and abs(final['amplitude_error_fraction'])<gates['final_cycle_amplitude_error_fraction']
            and abs(final['phase_error_deg'])<gates['final_cycle_phase_error_deg']
            and abs(final['mean_error_peak_fraction'])<gates['final_cycle_mean_error_peak_fraction']
            and final['change_fraction']<gates['final_cycle_change_fraction'])
        refinements.append(dict(steps=steps,cycles=cycles,unique_snapshots=len(times),
            periodic_accuracy_gates_passed=passed,maximum_checkpoint_join_jump=maximum_join,
            maximum_residual=max_residual,maximum_acceleration_error=max_acceleration_error,
            full_history_cold_waveform_error_fraction=cold_error,
            full_history_circulation_error_fraction=float(np.max(np.abs(gamma-cold.y[0][:,None]))/np.max(np.abs(cold.y[0]))),
            full_history_rate_error_fraction=float(np.max(np.abs(rate-cold_rate[:,None]))/np.max(np.abs(cold_rate))),
            final_waveform=dict(times=local.tolist(),predicted=cl.tolist(),reference=expected_cl.tolist())))
    ratio=refinements[1]['cycles'][-1]['waveform_error_fraction']/refinements[0]['cycles'][-1]['waveform_error_fraction']
    passed=refinements[-1]['periodic_accuracy_gates_passed'] and ratio<gates['successive_waveform_error_ratio_maximum']
    linear=-amplitude*(2*math.pi*1j*k*(1+2j*k)/(1+4j*k)-math.pi*k*k)
    fundamental=dense_measurements['harmonics'][0]
    result=dict(amplitude_ratio=amplitude,k=k,scope='UA-1 eight-cycle periodic section-equation verification',
        native_ASWING_comparison=False,experimental_comparison=False,checks_passed=int(passed),checks_total=1,
        audited_unique_snapshots=audited,refinements=refinements,final_waveform_error_ratio=ratio,
        independent_periodic_reference=dense_measurements,
        nonlinear_vs_linear_amplitude_difference_fraction=fundamental['amplitude']/abs(linear)-1,
        nonlinear_vs_linear_phase_difference_deg=(fundamental['phase_deg']-math.degrees(np.angle(linear))+180)%360-180,
        auditor_sha256=sha256(Path(__file__).read_bytes()).hexdigest(),production_files_unchanged=136,
        note='A failed coarse-grid accuracy gate is retained; acceptance requires fine-grid gates and refinement ratio.')
    output.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps(dict(amplitude_ratio=amplitude,passed=passed,audited_snapshots=audited,
        final_waveform_error_percent=100*refinements[-1]['cycles'][-1]['waveform_error_fraction'],
        error_ratio=ratio,final_cycle=refinements[-1]['cycles'][-1])),flush=True)
    if not passed:raise SystemExit(1)


if __name__=='__main__':
    main()
