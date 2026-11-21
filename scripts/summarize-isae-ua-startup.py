"""Independent ODE audit of complete checkpoint-connected UA-2 startup runs."""
from hashlib import sha256
import gzip
import json
import math
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from scipy.integrate import solve_ivp

from isae_ua_startup import rate_metrics

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'artifacts/isae/ua2-startup-20261101'
PREVIOUS = ROOT/'artifacts/isae/ua2-time-20261101'


def load_segments(tag,panels):
    rows,reports,plans = [],[],[]
    boundary_jump = 0.
    for part in ('start','finish'):
        suffix='finish-v2' if tag=='k0475' and panels==20 and part=='finish' else part
        folder = BASE/f'{tag}-n{panels}-g1125-{suffix}'
        plan = json.loads((folder/'plan.json').read_text())
        report = json.loads((folder/'report.json').read_text())
        assert report['converged'] and report['source_unchanged'] and report['rejected_steps']==0
        assert report['checkpoint_history_retained']
        assert report['structural_operator']=='drela-moving-airflow-v1'
        assert report['temporal_policy']=='drela-euler-bdf-v1'
        for name,digest in plan['source_sha256'].items():
            producer=ROOT/name
            if sha256(producer.read_bytes()).hexdigest()!=digest:
                assert name=='scripts/verify-isae-ua-startup-segment.py'
                producer=BASE/'segment-driver-before-resume-fix.py'
                assert sha256(producer.read_bytes()).hexdigest()==digest,name
            if name.startswith(('openswing/','scripts/','.reference/')):
                frozen=BASE/'frozen-code-segmented'/name
                if sha256(frozen.read_bytes()).hexdigest()!=digest:
                    assert producer==BASE/'segment-driver-before-resume-fix.py'
        with gzip.open(folder/'trajectory.json.gz','rt') as stream:raw=json.load(stream)
        samples = [dict(time=s['time'],force=s['force'],rate=s['circulation_rate'],
            circulation=[r['circulation'] for r in s['strips']],frame=s['frame'],
            residual=s['residual'],order=s['order'],step=s['step']) for s in raw['snapshots']]
        del raw
        assert len(samples)==report['accepted_steps']+1==plan['expected_steps']+1
        if rows:
            assert rows[-1]['time']==samples[0]['time']
            for key in ('force','rate','circulation'):
                jump=float(np.max(np.abs(np.array(rows[-1][key])-samples[0][key])))
                boundary_jump=max(boundary_jump,jump)
                assert jump < 1e-11
            for key in ('position_earth','velocity_origin_body','rates_body','attitude'):
                np.testing.assert_allclose(rows[-1]['frame'][key],samples[0]['frame'][key],atol=1e-12,rtol=0)
            assert all(s['order']==2 for s in samples[1:])
            samples=samples[1:]
        rows.extend(samples)
        reports.append(report);plans.append(plan)
    np.testing.assert_allclose([s['time'] for s in rows],plans[0]['grid'],atol=1e-13,rtol=0)
    assert rows[1]['order']==1 and all(s['order']==2 for s in rows[2:])
    assert plans[0]['grid']==plans[1]['grid']
    return rows,reports,plans,boundary_jump


def audit_case(tag,k,panels):
    rows,reports,plans,jump=load_segments(tag,panels)
    reference=json.loads((PREVIOUS/f'reference-n{panels}.json').read_text())
    m=reference['matrices']
    K,M,rv,ra,fg,fd=[np.array(m[n]) for n in ('K','M','rv','ra','fg','fd')]
    times=np.array([s['time'] for s in rows]);period=plans[0]['full_period']
    omega,h,speed=20*k,.0005,10.
    def derivative(t,gamma):
        w,a=-h*omega*math.sin(omega*t),-h*omega**2*math.cos(omega*t)
        return np.linalg.solve(M,-K@gamma-rv*w-ra*a)
    ode=solve_ivp(derivative,(0.,period),np.zeros(panels),t_eval=times,
        method='DOP853',rtol=1e-12,atol=1e-14)
    assert ode.success
    rate=np.array([derivative(t,gamma) for t,gamma in zip(times,ode.y.T)])
    velocity=-h*omega*np.sin(omega*times);acceleration=-h*omega**2*np.cos(omega*times)
    expected=ode.y.T@fg+rate@fd+m['fv']*velocity+m['fa']*acceleration
    actual=np.array([s['force'][2]/(.5*1.225*100*10) for s in rows])
    actual_rate=np.array([s['rate'] for s in rows])
    actual_gamma=np.array([s['circulation'] for s in rows])
    peak=np.max(np.abs(rate),axis=0)
    rate_error=np.abs(actual_rate-rate)/peak
    first_relative=np.abs(actual_rate[1]-rate[1])/np.abs(rate[1])
    cl_error=float(np.max(np.abs(actual-expected))/np.max(np.abs(expected)))
    local_error=float(np.max(rate_error));first_error=float(np.max(first_relative))
    step=np.diff(times)
    assert np.max(step) <= (period/160)*(1+1e-12)
    assert np.max(step[1:]/step[:-1]) <= 1.125*(1+1e-10)
    assert abs(step[0]-period/(160*256)) < 1e-15
    for s,a in zip(rows,acceleration):
        assert s['residual'] < 1e-10
        assert abs(s['frame']['acceleration_reference_body'][2]-a) < 1e-14
        assert max(abs(x) for x in s['frame']['rates_body']+s['frame']['attitude']) < 1e-12
    baseline_path=PREVIOUS/f'{tag}-n{panels}-t160/report.json'
    baseline=json.loads(baseline_path.read_text())
    old=rate_metrics(baseline['comparison']['samples'],baseline['linear_wing_comparison']['rows'])
    passed=cl_error < .001 and local_error < .001 and first_error < .01
    record=dict(k=k,panels=panels,full_steps=len(rows)-1,unique_snapshots=len(rows),
        part_seconds=[r['seconds'] for r in reports],persistence_seconds=[r['persistence_seconds'] for r in reports],
        maximum_CL_waveform_error_percent=100*cl_error,
        maximum_per_strip_rate_waveform_error_percent=100*local_error,
        maximum_first_step_relative_rate_error_percent=100*first_error,
        maximum_circulation_waveform_error_percent=float(100*np.max(np.abs(actual_gamma-ode.y.T))/np.max(np.abs(ode.y))),
        maximum_rate_global_peak_error_percent=float(100*np.max(np.abs(actual_rate-rate))/np.max(np.abs(rate))),
        baseline_per_strip_rate_waveform_error_percent=100*old['maximum_per_strip_rate_waveform_error_fraction'],
        baseline_first_step_relative_rate_error_percent=100*old['maximum_first_step_relative_error_fraction'],
        baseline_report_sha256=sha256(baseline_path.read_bytes()).hexdigest(),
        maximum_residual=max(s['residual'] for s in rows),maximum_checkpoint_boundary_jump=jump,
        accuracy_gate_passed=passed,source_equations_unchanged=True)
    plot=dict(x=times/period,reference=rate[:,0]/peak[0],actual=actual_rate[:,0]/peak[0],
        baseline_x=np.array([s['time'] for s in baseline['comparison']['samples']])/period,
        baseline_y=np.array([s['circulation_rate'][0] for s in baseline['comparison']['samples']])/peak[0])
    return record,plot


def main():
    figure,axes=plt.subplots(2,2,figsize=(10,6.5),constrained_layout=True)
    cases=[]
    for row,(tag,k) in enumerate((('k0475',.475),('k095',.95))):
        for column,panels in enumerate((20,40)):
            record,curve=audit_case(tag,k,panels)
            cases.append(record)
            axis=axes[row,column]
            keep=(curve['x']>0)&(curve['x']<=.05)
            old=(curve['baseline_x']>0)&(curve['baseline_x']<=.05)
            axis.semilogx(curve['x'][keep],curve['reference'][keep],'k-',label='Matrix ODE reference',lw=1.2)
            axis.semilogx(curve['x'][keep],curve['actual'][keep],'.',label='Refined startup, BDF2',ms=4)
            axis.semilogx(curve['baseline_x'][old],curve['baseline_y'][old],'o',label='Uniform 160-step grid',ms=4)
            axis.set(title=f'k={k:g}, {panels} strips; first rate error {record["maximum_first_step_relative_rate_error_percent"]:.3f}%',
                xlabel='Time / period',ylabel='Tip circulation rate / reference peak')
            axis.grid(which='both',alpha=.25);axis.legend(fontsize=7)
    pilot=json.loads((BASE/'k0475-n40-t160-s32/report.json').read_text())
    intermediate=[]
    for name in ('k0475-n20-t160-s256-g120','k0475-n40-t160-s256-g120-v2'):
        r=json.loads((BASE/name/'report.json').read_text())
        intermediate.append(dict(directory=name,metrics=r['startup_rate_comparison']))
    result=dict(date='2026-11-01',scope='UA-2 small-amplitude local startup accuracy; four complete checkpoint-connected trajectories',
        cases=cases,checks_passed=sum(r['accuracy_gate_passed'] for r in cases),checks_total=len(cases),
        audited_unique_snapshots=sum(r['unique_snapshots'] for r in cases),
        nominal_steps=160,first_step_subdivisions=256,maximum_growth=1.125,checkpoint_split_index=32,
        production_files_unchanged=136,native_ASWING_comparison=False,independent_spatial_physics_reference=False,
        pilot32=pilot['startup_rate_comparison'],growth_120_diagnostics=intermediate,
        interrupted_run='k0475-n40-t160-s256-g120: solver reached final time; old writer left incomplete gzip at process timeout.',
        corrected_resume_request='The first finish request included a redundant condition; the source API rejected it before solving. Corrected request uses the checkpoint-owned condition.',
        limitations=['Only A/c=.001, alpha=0, k=.475/.95 and reconstructed AR10.',
            'Reference shares spatial physics; independent integration is the comparison.',
            'Refined forcing-table time grid is an explicit diagnostic; app defaults are unchanged.',
            'Finite amplitudes, periodic response and trustworthy native UA-2 provenance remain unfinished.'],
        summary_script_sha256=sha256(Path(__file__).read_bytes()).hexdigest())
    stem=ROOT/'docs/validation/isae-ua2-startup-20261101'
    stem.with_suffix('.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    figure.savefig(stem.with_suffix('.svg'));figure.savefig(stem.with_suffix('.png'),dpi=150);plt.close(figure)
    print(json.dumps(dict(checks_passed=result['checks_passed'],checks_total=len(cases),
        audited_unique_snapshots=result['audited_unique_snapshots'],
        first_step_errors_percent=[r['maximum_first_step_relative_rate_error_percent'] for r in cases],
        per_strip_waveform_errors_percent=[r['maximum_per_strip_rate_waveform_error_percent'] for r in cases],
        lift_errors_percent=[r['maximum_CL_waveform_error_percent'] for r in cases],
        maximum_checkpoint_jump=max(r['maximum_checkpoint_boundary_jump'] for r in cases))))
    if result['checks_passed'] != len(cases):raise SystemExit(1)


if __name__=='__main__':
    main()
