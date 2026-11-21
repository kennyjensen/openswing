"""Attribute UA-2 state errors using independent discrete and continuous equations."""
import argparse
from hashlib import sha256
import json
import math
from pathlib import Path
import shutil
import time
import numpy as np
from isae_ua_discrete_reference import derivative_weights,kinematics,discrete_trajectory,circulation_residual_jacobian
from isae_ua_wing_nonlinear import StraightWing

ROOT=Path(__file__).resolve().parents[1]
ORIGINAL=ROOT/'artifacts/isae/ua2-periodic-20261101'


def peak_error(actual,reference):
    scale=np.max(abs(reference),axis=0)
    assert np.min(scale)>0
    return float(np.max(abs(actual-reference)/scale))


def decomposition(a,b,c,*,periodic=None):
    """Keep signed waveforms; separate infinity norms do not add arithmetically."""
    target=c if periodic is None else periodic
    scale=np.max(abs(target),axis=0)
    terms=dict(motion=a-b,circulation_integration=b-c,startup_transient=c-target)
    total=a-target;reconstructed=sum(terms.values())
    return dict(total_error_percent=100*float(np.max(abs(total)/scale)),
        component_error_percent={k:100*float(np.max(abs(v)/scale)) for k,v in terms.items()},
        reconstruction_absolute_error=float(np.max(abs(total-reconstructed))),
        normalization='Each strip uses its own target peak; scalar lift uses its target peak.')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();plan_path=args.output.with_suffix('.plan.json')
    if args.output.exists() or plan_path.exists():parser.error('Preserve completed analysis; use a fresh path')
    data=json.loads(args.input.read_text());panels=data['plan']['panels'];steps=data['plan']['nominal_steps']
    assert data['unique_snapshots']==8*steps+41 and data['all_checkpoint_joins_exact']
    assert data['plan']['amplitude_ratio']==.5 and data['plan']['k']==.95 and data['plan']['cycles']==8
    batch_path=ORIGINAL/'accepted-evidence/batch-plan.json';batch=json.loads(batch_path.read_text())
    assert sha256(batch_path.read_bytes()).hexdigest()==data['plan']['batch_plan_sha256']
    for name,digest in batch['source_sha256'].items():
        assert sha256((ROOT/name).read_bytes()).hexdigest()==digest,name
    reference_path=ORIGINAL/f'reference-n{panels}.json';reference=json.loads(reference_path.read_text())
    paths=[Path(__file__).resolve(),ROOT/'scripts/isae_ua_discrete_reference.py',ROOT/'scripts/isae_ua_wing_nonlinear.py',
        ROOT/'tests/test_isae_ua_discrete_reference.py',ROOT/'.reference/asw_uns_theory.txt',ROOT/'.reference/asw_theory.txt',
        args.input.resolve(),reference_path]
    pins={str(p.relative_to(ROOT)):sha256(p.read_bytes()).hexdigest() for p in paths}
    plan=dict(panels=panels,nominal_steps=steps,source_sha256=pins,
        normalized_discrete_identity_gate=1e-7,normalized_circulation_equation_gate=2e-10,
        experiment='A: independent discrete motion+circulation; B: ideal motion+discrete circulation; C: saved continuous cold ODE.',
        production_changed=False,acceptance_gates_changed=False,native_ASWING_comparison=False)
    args.output.parent.mkdir(parents=True,exist_ok=True);plan_path.write_text(json.dumps(plan,indent=2)+'\n')
    for p in paths:
        target=args.output.parent/'frozen-code'/p.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True)
        if target.exists():assert sha256(target.read_bytes()).hexdigest()==pins[str(p.relative_to(ROOT))]
        else:shutil.copyfile(p,target)
    started=time.monotonic();rows=data['rows'];times=np.array([r['time'] for r in rows]);omega=19.;height=.25;period=math.pi/9.5
    ideal_velocity=-height*omega*np.sin(omega*times);ideal_acceleration=-height*omega**2*np.cos(omega*times)
    ideal_position=height*np.cos(omega*times)
    velocity,position=kinematics(times,ideal_acceleration)
    actual={k:np.array([r[k] for r in rows]) for k in ('velocity','position','acceleration','CL','circulation','circulation_rate')}
    assert np.max(abs(actual['acceleration']-ideal_acceleration))<1e-10
    wing=StraightWing(panels)
    a=discrete_trajectory(wing,times,velocity,ideal_acceleration)
    b=discrete_trajectory(wing,times,ideal_velocity,ideal_acceleration)
    source_rows=reference['reference']['DOP853']['cold']['rows'];source_times=np.array([r['time'] for r in source_rows])
    indices=[int(np.argmin(abs(source_times-t))) for t in times]
    assert max(abs(source_times[i]-t) for i,t in zip(indices,times))<1e-12
    c={key:np.array([source_rows[i][key] for i in indices]) for key in ('CL','circulation','circulation_rate')}
    identity={key:peak_error(actual[key],a[key]) for key in ('CL','circulation','circulation_rate')}
    identity.update(velocity=float(np.max(abs(actual['velocity']-velocity))/(height*omega)),
        position=float(np.max(abs(actual['position']-position))/height))
    load_identity=[];maximum_equation=0.;maximum_rate_identity=0.
    for i,row in enumerate(rows):
        g=actual['circulation'][i];v=actual['velocity'][i];r=actual['circulation_rate'][i]
        fields=wing.fields(g,v,actual['acceleration'][i],rate=r)
        load_identity.append(fields['CL']-actual['CL'][i])
        if i==0:continue
        weights=derivative_weights(times,i)
        derivative=weights[0]*(g-actual['circulation'][i-1])+weights[2]*(actual['circulation'][max(0,i-2)]-actual['circulation'][i-1])
        maximum_rate_identity=max(maximum_rate_identity,float(np.max(abs(derivative-r))))
        residual,_=circulation_residual_jacobian(wing,g,actual['circulation'][i-1],actual['circulation'][max(0,i-2)],weights,v)
        normalized=2/np.pi*residual/(fields['local_speed']*math.hypot(10.,v))
        maximum_equation=max(maximum_equation,float(np.max(abs(normalized))))
    identity['load_replay']=float(np.max(abs(np.array(load_identity)))/np.max(abs(actual['CL'])))
    identity['stored_rate']=maximum_rate_identity/float(np.max(abs(actual['circulation_rate'])))
    full={key:decomposition(a[key],b[key],c[key]) for key in ('CL','circulation','circulation_rate')}
    last=slice(len(times)-steps-1,None)
    periodic_rows=reference['reference']['DOP853']['periodic']['rows'][::160//steps]
    phase=np.array([r['time'] for r in periodic_rows]);np.testing.assert_allclose(times[last]-7*period,phase,rtol=0,atol=1e-12)
    periodic={key:np.array([r[key] for r in periodic_rows]) for key in ('CL','circulation','circulation_rate')}
    final={key:decomposition(a[key][last],b[key][last],c[key][last],periodic=periodic[key]) for key in periodic}
    def mean(values):return float(np.sum(np.diff(phase)*(values[:-1]+values[1:])/2)/period)
    cl_peak=float(np.max(abs(periodic['CL'])))
    means={name:mean(value['CL'][last]) for name,value in (('discrete_motion',a),('ideal_motion',b),('continuous_cold',c))}
    means['periodic']=mean(periodic['CL'])
    mean_parts=dict(motion=means['discrete_motion']-means['ideal_motion'],
        circulation_integration=means['ideal_motion']-means['continuous_cold'],
        startup_transient=means['continuous_cold']-means['periodic'])
    motion=dict(maximum_velocity_error=float(np.max(abs(velocity-ideal_velocity))),
        maximum_position_error=float(np.max(abs(position-ideal_position))),
        final_cycle_mean_velocity_error=mean((velocity-ideal_velocity)[last]),
        final_cycle_position_change=float(position[-1]-position[-steps-1]),
        cycle_end_position_errors=[])
    for cycle in range(1,9):
        index=int(np.argmin(abs(times-cycle*period)));assert abs(times[index]-cycle*period)<1e-12
        motion['cycle_end_position_errors'].append(float(position[index]-ideal_position[index]))
    passed=max(identity.values())<plan['normalized_discrete_identity_gate'] and maximum_equation<plan['normalized_circulation_equation_gate']
    output=dict(plan=plan,discrete_identity_passed=passed,identity_error_fractions=identity,
        maximum_normalized_circulation_equation_residual=maximum_equation,
        full_history_error_decomposition=full,final_cycle_error_decomposition=final,
        final_cycle_mean_lift=means,final_cycle_mean_lift_error_parts=mean_parts,
        final_cycle_mean_lift_error_parts_percent_of_peak={k:100*v/cl_peak for k,v in mean_parts.items()},
        motion=motion,independent_solver={name:{key:value[key] for key in ('maximum_equation_residual','maximum_newton_iterations','total_newton_updates')}
            for name,value in (('discrete_motion',a),('ideal_motion',b))},
        waveforms=dict(times=times.tolist(),production_CL=actual['CL'].tolist(),discrete_CL=a['CL'].tolist(),
            ideal_motion_discrete_CL=b['CL'].tolist(),continuous_cold_CL=c['CL'].tolist(),
            velocity_error=(velocity-ideal_velocity).tolist(),position_error=(position-ideal_position).tolist()),
        seconds=time.monotonic()-started,production_changed=False,native_ASWING_comparison=False,
        note='The ideal-motion run is a diagnostic input substitution only. No state correction, input replacement or fitted term is adopted in production.')
    assert all(sha256((ROOT/n).read_bytes()).hexdigest()==h for n,h in pins.items())
    args.output.write_text(json.dumps(output,indent=2,allow_nan=False)+'\n')
    print(json.dumps(dict(panels=panels,steps=steps,passed=passed,seconds=output['seconds'],
        identity=identity,circulation_equation_residual=maximum_equation,
        final_CL_parts=final['CL'],mean_lift_parts=output['final_cycle_mean_lift_error_parts_percent_of_peak'],motion=motion)),flush=True)
    if not passed:raise SystemExit(1)


if __name__=='__main__':main()
