"""Publish the complete inclined-periodic audit, including any failed gates."""
from hashlib import sha256
import json
from pathlib import Path
import shutil

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'artifacts/isae/ua1-incidence-periodic-20261101'
STEM=ROOT/'docs/validation/isae-ua1-incidence-periodic-20261101'


def digest(p):return sha256(p.read_bytes()).hexdigest()


def main():
    if STEM.with_suffix('.json').exists() or (BASE/'summary-plan.json').exists():raise SystemExit('Preserve completed summary')
    audit=json.loads((BASE/'audit.json').read_text())
    batch=json.loads((BASE/'batch-plan.json').read_text())
    reference=json.loads((BASE/'reference.json').read_text())
    assert json.loads((BASE/'batch-complete.json').read_text())['computed_jobs']==48
    receipt=json.loads((BASE/'audit-execution.json').read_text())
    assert receipt['exit_code']==(0 if audit['passed'] else 1)
    for n,h in {**batch['source_sha256'],**audit['input_sha256'],**audit['plan']['source_sha256']}.items():assert digest(ROOT/n)==h,n
    paths=[Path(__file__).resolve(),BASE/'audit.json',BASE/'audit-plan.json',BASE/'audit-execution.json',
           BASE/'batch-plan.json',BASE/'reference.json',BASE/'tests-execution.json',BASE/'batch-complete.json']
    pins={str(p.relative_to(ROOT)):digest(p) for p in paths}
    (BASE/'summary-plan.json').write_text(json.dumps(dict(source_sha256=pins,native_ASWING_comparison=False),indent=2)+'\n')
    frozen=BASE/'frozen-code/scripts'/Path(__file__).name;frozen.parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(__file__,frozen)
    fine=audit['results']['160'];coarse=audit['results']['80'];final=fine['cycles'][-1]
    failed=[k for k,v in audit['checks'].items() if not v]
    summary=dict(date='2026-11-01',passed=audit['passed'],periodic_response_checks_passed=int(audit['passed']),
        periodic_response_checks_total=1,failed_gates=failed,source_sha256=pins,
        checks=audit['checks'],fine_to_coarse_ratios=audit['fine_to_coarse_ratios'],
        grids={n:{k:v for k,v in r.items() if k!='rows'} for n,r in audit['results'].items()},
        audited_unique_snapshots=audit['audited_unique_snapshots'],accepted_segments=48,
        solver_seconds=audit['solver_seconds'],worker_wall_seconds=audit['worker_wall_seconds'],
        independent_reference_agreement_fractions=reference['agreement_fractions'],
        native_ASWING_comparison=False,production_files_changed=0,
        remaining=['Other nonzero-incidence periodic amplitudes/frequencies and the 5-degree production histories.',
            'Stall, compressibility, native ASWING provenance and browser/WASM verification.',
            'Accumulated position and higher-harmonic diagnostics do not have separate acceptance gates in this pilot.'])
    fig,axes=plt.subplots(2,2,figsize=(11.5,8),constrained_layout=True)
    for steps,color in (('80','#d97706'),('160','#2563eb')):
        r=audit['results'][steps];n=int(steps);rows=r['rows'][-n-1:]
        phase=np.linspace(0,1,n+1)
        target=np.array([x['CL'] for x in reference['reference']['periodic']['rows'][::160//n]])
        actual=np.array([x['CL'] for x in rows])
        axes[0,0].plot(phase,actual,color=color,linestyle='--',label=f'Production {steps} steps/cycle')
        axes[0,1].plot(phase,100*(actual-target)/r['periodic_scales']['CL'],color=color,label=f'{steps} steps/cycle')
        axes[1,1].plot(range(1,9),400*np.array(r['diagnostics']['cycle_end_heave_position_errors']),
                       color=color,marker='o',label=f'{steps} steps/cycle')
        if steps=='160':axes[0,0].plot(phase,target,color='.15',linewidth=.8,label='Independent periodic reference')
    for key,color,label in (('CL','#2563eb','Lift'),('circulation','#d97706','Circulation'),
                            ('circulation_rate','#059669','Circulation rate')):
        axes[1,0].semilogy(range(1,9),[100*c['error_fractions'][key] for c in fine['cycles']],
                           color=color,marker='o',label=label)
    axes[1,0].axhline(.1,color='.4',linestyle=':',label='Fine waveform gate (0.1%)')
    axes[0,0].set(title='Final cycle: fixed-axis lift',xlabel='Cycle phase',ylabel='Lift coefficient CL')
    axes[0,1].set(title='Final-cycle lift error',xlabel='Cycle phase',ylabel='Error (% of periodic lift variation)')
    axes[1,0].set(title='Fine-grid approach to the periodic response',xlabel='Completed cycle',ylabel='Waveform error (%)',xticks=range(1,9))
    axes[1,1].set(title='Cycle-end position error',xlabel='Completed cycle',ylabel='Error (% of heave amplitude)',xticks=range(1,9))
    for ax in axes.flat:ax.grid(alpha=.2,which='both');ax.legend(fontsize=7.5)
    fig.suptitle('UA-1: eight continuous cycles at 9°, k=0.94, A/c=0.5\nAttached-flow equations; production steady initialization; fixed freestream-normal plunge',fontsize=12)
    fig.savefig(STEM.with_suffix('.svg'));fig.savefig(STEM.with_suffix('.png'),dpi=170);plt.close(fig)
    table='\n'.join(f"| {n} | {100*r['cycles'][-1]['error_fractions']['CL']:.5f}% | "
        f"{100*r['cycles'][-1]['error_fractions']['circulation']:.5f}% | "
        f"{100*r['cycles'][-1]['error_fractions']['circulation_rate']:.5f}% | "
        f"{100*r['cycles'][-1]['harmonic_errors'][0]['amplitude_error_fraction']:+.5f}% | "
        f"{r['cycles'][-1]['harmonic_errors'][0]['phase_error_deg']:+.5f}° | "
        f"{100*r['cycles'][-1]['mean_CL_error_dynamic_fraction']:+.6f}% |" for n,r in audit['results'].items())
    harmonics='\n'.join(f"| {r['order']} | {100*r['amplitude_error_fraction']:+.5f}% | {r['phase_error_deg']:+.5f}° |"
                        for r in final['harmonic_errors'])
    status='1/1 periodic-response check passes' if audit['passed'] else 'The periodic-response check remains unpassed'
    gate_status='All declared gates pass.' if audit['passed'] else 'Failed gates: '+', '.join(failed)+'.'
    text=f'''# UA-1: nonlinear periodic response at nonzero incidence

Updated 2026-11-01. **{status}** at 9°, k=0.94, A/c=0.5.
Two continuous eight-cycle production trajectories use 80/160 steps per cycle
and four circulation unknowns in the AR200000 section reconstruction.
**All 1,922 unique snapshots are audited.** This extends the
[first-cycle and instantaneous-load checks](isae-ua1-incidence-20261101.md).
It is an attached-flow equation comparison, not a native ASWING trajectory.

| Steps/cycle | Periodic lift error | Periodic circulation error | Periodic rate error | Fundamental amplitude error | Phase error | Mean CL error, % dynamic scale |
|---:|---:|---:|---:|---:|---:|---:|
{table}

Periodic lift and circulation errors use maximum departures from their
reference cycle means; rate uses its reference peak. Every strip is checked.
This prevents the nonzero mean from reducing the reported relative dynamic
error. Harmonic amplitude uses its own reference amplitude. The mean-lift error
uses the periodic lift-variation scale. {gate_status}

![Final waveform, errors, settling and motion drift](isae-ua1-incidence-periodic-20261101.svg)

The independent reference predicts mean CL
**{fine['periodic_reference']['mean']:.8f}**; production gives
**{final['measured']['mean']:.8f}** on the fine grid. The largest final
cycle-to-cycle change is **{100*max(final['cycle_change_fractions'].values()):.6f}%**
across lift, circulation and rate. The fine/coarse error ratios are retained
for both the complete cold history and the final periodic cycle in the machine
summary; no initial-cycle samples are discarded from the cold audit.

## Equations, initialization and acceptance

The [independent inclined-section equations](isae-inclined-section-heave-reference.md)
retain the instantaneous wind direction, nonlinear velocity magnitudes,
circulation-rate lift and the apparent-mass force projection. The periodic
boundary comes from integrating-factor quadrature. The cold solution adds
the exact homogeneous transient from the pre-motion steady circulation.
A direct adaptive integration of the entire eight-cycle cold history agrees
within **{max(reference['agreement_fractions'].values()):.3e} of the relevant peak**.
The prior three-method periodic reference also remains pinned; its 512-interval
harmonics and the present 160-interval reference differ by at most
{reference['maximum_harmonic_quadrature_change']:.3e} in coefficient units.

OpenSwing starts from its own steady equilibrium. No reference circulation,
periodic state or mean correction is supplied to it. The complete eight-cycle
Ax/Az table is present before the first step. The original first-cycle pilot
had a shorter forcing table; the present first cycle reproduces its production
states within **{max(r['diagnostics']['first_cycle_replay_maximum_absolute_difference'] for r in audit['results'].values()):.3e}**
in the audited quantities, despite the additional future forcing.

Declared gates require fine periodic and whole-cold-history lift, circulation
and rate errors below 0.1%; corresponding fine/coarse error ratios below 0.35;
fundamental amplitude error below 0.1%; phase error below 0.1°; mean-lift error
below 0.1% of periodic lift variation; and last-cycle changes below 0.01% for
lift, circulation and rate. Nonlinear residuals remain below 1e-10.
The provisional SA 3% tolerance does not apply.

Fine whole-cold-history lift/circulation/rate errors are
**{100*fine['cold_error_fractions']['CL']:.5f}% /
{100*fine['cold_error_fractions']['circulation']:.5f}% /
{100*fine['cold_error_fractions']['circulation_rate']:.5f}%**.
All checkpoints preserve both the accepted state and the BDF predecessor;
the first step is backward Euler and all remaining steps are second order.

## Additional diagnostics and scope

The fine first-step circulation-rate error is
**{100*fine['diagnostics']['first_step_rate_relative_error']:.3f}%** relative
to that sample's own small reference value. Maximum heave velocity error is
{fine['diagnostics']['maximum_heave_velocity_error']:.6f} m/s. Maximum position
error over eight cycles is {fine['diagnostics']['maximum_heave_position_error']:.7f}
chords, or **{400*fine['diagnostics']['maximum_heave_position_error']:.4f}% of
heave amplitude**. These remain separate diagnostics, without additional
acceptance gates in this pilot.

| Harmonic | Fine amplitude error | Fine phase error |
|---:|---:|---:|
{harmonics}

Only the fundamental has separate amplitude/phase gates; the higher harmonics
also contribute to the complete-waveform gates. Their individual errors remain
visible here. Finite-tip effects remain in the high-aspect-ratio reconstruction;
this single spatial mesh does not prove spatial convergence or general-wing accuracy.

The 48 serial 40-step segments all terminate successfully with no rejected
steps. Solver time is **{audit['solver_seconds']['min']:.2f}–{audit['solver_seconds']['max']:.2f}
seconds per segment**, totaling {audit['solver_seconds']['total']:.2f} seconds.
Worker wall times including imports, source checks and artifact handling are
{audit['worker_wall_seconds']['min']:.2f}–{audit['worker_wall_seconds']['max']:.2f}
seconds. Each process uses one BLAS thread and has a 45-second cap. Three
focused tests verify the full forcing direction, long-horizon transient and
cycle-boundary continuity. All 136 production Python files are unchanged.

Remaining work includes 5° production time histories, other periodic frequencies
and amplitudes, stall, native ASWING provenance and browser/WASM verification.
The full project goal remains incomplete. This result neither fits the
experimental mean shifts nor changes the 222 blocked native UA-2 comparisons.

Evidence: [machine summary](isae-ua1-incidence-periodic-20261101.json),
[full trajectories, plans, receipts, reference and audit](../../artifacts/isae/ua1-incidence-periodic-20261101),
[periodic setup and reference](../../scripts/isae_ua_incidence_periodic.py),
[bounded segment runner](../../scripts/verify-isae-ua1-incidence-periodic-segment.py), and
[complete-history audit](../../scripts/audit-isae-ua1-incidence-periodic.py).
'''
    assert all(digest(ROOT/n)==h for n,h in pins.items())
    STEM.with_suffix('.json').write_text(json.dumps(summary,indent=2,allow_nan=False)+'\n')
    STEM.with_suffix('.md').write_text(text)
    print(json.dumps(dict(passed=audit['passed'],failed_gates=failed,final_errors=final['error_fractions'],
        fundamental=final['harmonic_errors'][0],mean_error=final['mean_CL_error_dynamic_fraction'],
        position_error_percent_of_amplitude=400*fine['diagnostics']['maximum_heave_position_error'])))


if __name__=='__main__':main()
