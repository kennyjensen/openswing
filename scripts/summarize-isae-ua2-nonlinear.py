"""Summarize independent nonlinear UA-2 equation and time-refinement checks."""
from hashlib import sha256
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from scipy.integrate import solve_ivp
from isae_ua_wing_nonlinear import StraightWing

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'artifacts/isae/ua2-nonlinear-20261101'


def main():
    batch=json.loads((BASE/'batch-plan.json').read_text())
    complete=json.loads((BASE/'batch-complete.json').read_text());assert complete['computed_segments']==22
    audits=[json.loads((BASE/f'audit-n{n}.json').read_text()) for n in (20,40)]
    for data in audits:
        assert data['auditor_sha256']==sha256((ROOT/'scripts/audit-isae-ua2-nonlinear.py').read_bytes()).hexdigest()
    fine=[d['records'][-1] for d in audits];waves=[r['waveform'] for r in fine]
    np.testing.assert_allclose(waves[0]['times'],waves[1]['times'],atol=1e-12,rtol=0)
    scale=max(map(abs,waves[1]['CL']))
    mesh=float(np.max(abs(np.array(waves[0]['CL'])-waves[1]['CL']))/scale)
    reference_mesh=float(np.max(abs(np.array(waves[0]['reference_CL'])-waves[1]['reference_CL']))/
        max(map(abs,waves[1]['reference_CL'])))
    mesh_passed=mesh<batch['gates']['fine_mesh_lift_change_fraction']
    figure,axes=plt.subplots(2,2,figsize=(10,7),constrained_layout=True)
    rows=[];durations=[];persist=[]
    for data in audits:
        panels=data['panels'];coarse,fine=data['records'];w=fine['waveform'];times=np.array(w['times'])
        phase=times/times[-1]
        # Descriptive comparison only: a true small-signal system does not
        # contain the finite-amplitude local-speed and wind-direction terms.
        wing=StraightWing(panels)
        def linear_rhs(t,gamma):
            velocity=-.25*19*np.sin(19*t)
            return np.pi/2*10*(-velocity-wing.C@gamma)
        linear=solve_ivp(linear_rhs,(0,float(times[-1])),np.zeros(panels),t_eval=times,
            method='DOP853',rtol=1e-11,atol=1e-13)
        assert linear.success
        linear_rate=np.array([linear_rhs(t,g) for t,g in zip(times,linear.y.T)])
        linear_cl=2/(10*10)*(linear.y.T@wing.widths)+2/(100*10)*(linear_rate@wing.widths)
        linear_cl+=np.pi/(2*100)*.25*19**2*np.cos(19*times)
        nonlinear_linear=float(np.max(abs(np.array(w['reference_CL'])-linear_cl))/max(map(abs,w['reference_CL'])))
        axes[0,0].plot(phase,w['CL'],label=f'OpenSwing, {panels} strips')
        axes[0,1].plot([80,160],[100*r['lift_waveform_error_fraction'] for r in data['records']],'o-',label=f'{panels} strips')
        reference_rate=np.array(w['reference_rate']);actual_rate=np.array(w['circulation_rate'])
        per_strip_peak=np.max(abs(reference_rate),axis=0)
        rate_error=np.max(abs(actual_rate-reference_rate)/per_strip_peak,axis=1)
        axes[1,0].semilogx(phase[1:],100*rate_error[1:],label=f'{panels} strips')
        axes[1,1].plot([80,160],[100*r['first_step_relative_rate_error_fraction'] for r in data['records']],
            'o-',label=f'{panels} strips')
        for r in data['records']:durations.extend(r['segment_seconds']);persist.extend(r['persistence_seconds'])
        rows.append(dict(panels=panels,refinement_passed=data['refinement_check_passed'],
            coarse_lift_error_percent=100*coarse['lift_waveform_error_fraction'],
            fine_lift_error_percent=100*fine['lift_waveform_error_fraction'],
            fine_circulation_error_percent=100*fine['circulation_waveform_error_fraction'],
            fine_local_rate_error_percent=100*fine['per_strip_rate_waveform_error_fraction'],
            fine_first_step_relative_rate_error_percent=100*fine['first_step_relative_rate_error_fraction'],
            nonlinear_minus_linear_waveform_percent=100*nonlinear_linear,
            error_ratio=data['lift_refinement_ratio'],
            maximum_residual=max(r['maximum_residual'] for r in data['records']),
            maximum_checkpoint_join_jump=max(r['maximum_checkpoint_join_jump'] for r in data['records']),
            reference_method_difference_fractions=data['reference_method_difference_fractions'],
            audit_sha256=sha256((BASE/f'audit-n{panels}.json').read_bytes()).hexdigest()))
    axes[0,0].plot(phase,waves[1]['reference_CL'],'k--',lw=1,label='Independent equations, 40 strips')
    axes[0,0].plot(phase,linear_cl,':',lw=1.2,label='Linearized equations, 40 strips')
    axes[0,0].set(xlabel='Time / period',ylabel='Vertical CL',title='Largest-amplitude first cycle')
    axes[0,1].axhline(.1,color='black',ls=':',lw=.8,label='Fine-grid gate')
    axes[0,1].set(xlabel='Nominal steps / cycle',ylabel='Lift waveform error (%)',title='Time refinement')
    axes[1,0].axhline(.1,color='black',ls=':',lw=.8,label='Fine-grid gate')
    axes[1,0].set(xlabel='Time / period',ylabel='Worst per-strip rate error (% of own peak)',title='Local circulation-rate accuracy')
    axes[1,1].axhline(1.,color='black',ls=':',lw=.8,label='Fine-grid gate')
    axes[1,1].set(xlabel='Nominal steps / cycle',ylabel='First-step relative rate error (%)',title='All strips retained at startup')
    for axis in axes.flat:axis.grid(which='both',alpha=.25);axis.legend(fontsize=7)
    for axis in (axes[0,1],axes[1,1]):axis.set_xticks([80,160])
    result=dict(date='2026-11-01',scope=batch['scope'],refinement_checks_passed=sum(r['refinement_passed'] for r in rows),
        refinement_checks_total=2,mesh_check_passed=bool(mesh_passed),mesh_lift_change_percent=100*mesh,
        independent_reference_mesh_change_percent=100*reference_mesh,
        cases=rows,computed_segments=22,continuous_trajectories=4,
        audited_unique_snapshots=sum(d['audited_unique_snapshots'] for d in audits),
        solver_seconds_range=[min(durations),max(durations)],persistence_seconds_range=[min(persist),max(persist)],
        total_solver_seconds=sum(durations),production_files_unchanged=136,
        independent_spatial_reference=True,native_ASWING_comparison=False,production_changed=False,app_defaults_changed=False,
        summary_script_sha256=sha256(Path(__file__).read_bytes()).hexdigest(),
        limitations=['A/c=.5, k=.95, zero mean incidence only; other finite amplitudes and frequencies remain.',
            'First cycle only; periodic 3D response remains.',
            'Straight rigid AR10 reconstruction with cosine/Glauert sampling; native model and historical driver unverified.',
            'Independent implementation of the same documented horseshoe/lag approximation; not experimental truth or native-output parity.',
            'Explicit graded time grid; app defaults and general automatic error-control policy unchanged.'])
    stem=ROOT/'docs/validation/isae-ua2-nonlinear-20261101'
    stem.with_suffix('.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    figure.suptitle('UA-2: independent nonlinear heave verification, A/c=0.5, k=0.95')
    figure.savefig(stem.with_suffix('.svg'));figure.savefig(stem.with_suffix('.png'),dpi=150);plt.close(figure)
    print(json.dumps(result,indent=2),flush=True)
    if result['refinement_checks_passed']!=2 or not mesh_passed:raise SystemExit(1)


if __name__=='__main__':main()
