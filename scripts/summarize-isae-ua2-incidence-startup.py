"""Report the inclined-wing startup refinement and retain the failed uniform grid."""
from hashlib import sha256
import json
from pathlib import Path
import shutil
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'artifacts/isae/ua2-incidence-startup-20261101'
OLD=ROOT/'artifacts/isae/ua2-incidence-time-20261101'
STEM=ROOT/'docs/validation/isae-ua2-incidence-startup-20261101'


def digest(p):return sha256(p.read_bytes()).hexdigest()


def main():
    assert not STEM.with_suffix('.json').exists() and not (BASE/'summary-plan.json').exists()
    audit=json.loads((BASE/'audit.json').read_text());old=json.loads((OLD/'audit.json').read_text())
    reference=json.loads((BASE/'reference.json').read_text())
    assert json.loads((BASE/'audit-execution.json').read_text())['exit_code']==(0 if audit['passed'] else 1)
    assert json.loads((BASE/'batch-complete.json').read_text())['computed_jobs']==36
    for name,h in {**audit['source_sha256'],**audit['input_sha256']}.items():assert digest(ROOT/name)==h,name
    paths=[Path(__file__).resolve(),BASE/'audit.json',BASE/'audit-execution.json',BASE/'reference.json',
           BASE/'batch-plan.json',OLD/'audit.json',ROOT/'docs/validation/isae-ua2-incidence-20261101.json']
    pins={str(p.relative_to(ROOT)):digest(p) for p in paths}
    (BASE/'summary-plan.json').write_text(json.dumps(dict(source_sha256=pins),indent=2)+'\n')
    fine=audit['results']['320'];coarse=audit['results']['160'];previous=old['results']['160']
    failed=[k for k,v in audit['checks'].items() if not v]
    first_reference_errors={}
    for n in ('160','320'):
        rows_a=reference['reference']['DOP853']['cold']['rows']
        rows_b=reference['reference']['Radau']['cold']['rows']
        t=reference['grids'][n][1]
        i=min(range(len(rows_a)),key=lambda j:abs(rows_a[j]['time']-t))
        first_reference_errors[n]=max(abs(x-y)/abs(y) for x,y in
            zip(rows_a[i]['circulation_rate'],rows_b[i]['circulation_rate']))
    summary=dict(passed=audit['passed'],checks=audit['checks'],failed_gates=failed,
        inclined_time_checks_passed=int(audit['passed']),inclined_time_checks_total=1,
        grids={n:{k:v for k,v in r.items() if k!='rows'} for n,r in audit['results'].items()},
        original_uniform_fine={k:v for k,v in previous.items() if k!='rows'},ratios=audit['ratios'],
        audited_unique_snapshots=562,production_segments=36,solver_seconds=audit['solver_seconds'],
        reference_method_differences=reference['method_differences'],
        first_step_reference_method_differences=first_reference_errors,source_sha256=pins,
        production_files_changed=0,native_ASWING_comparison=False,full_goal_complete=False)
    datasets=[('Uniform 160',previous,'.4'),('Gradual 160',coarse,'#d97706'),('Gradual 320',fine,'#2563eb')]
    fig,axes=plt.subplots(1,2,figsize=(11,4.5),constrained_layout=True)
    for label,r,color in datasets:
        rows=r['rows'];phase=np.array([v['time'] for v in rows])/(np.pi/9.5)
        cl=np.array([v['CL']-v['reference']['CL'] for v in rows])/r['scales']['CL']
        rate=np.array([v['circulation_rate'] for v in rows]);target=np.array([v['reference']['circulation_rate'] for v in rows])
        axes[0].plot(phase,100*cl,color=color,label=label)
        axes[1].semilogy(phase[1:],100*np.max(abs(rate-target)/r['scales']['circulation_rate'],axis=1)[1:],color=color,label=label)
    axes[1].axhline(.1,color='.4',linestyle=':',label='Fine rate limit (0.1%)')
    axes[0].set(title='Lift waveform error',xlabel='Cycle phase',ylabel='% of reference dynamic lift')
    axes[1].set(title='Worst strip circulation-rate error',xlabel='Cycle phase',ylabel='% of each strip reference peak')
    for ax in axes:ax.grid(alpha=.2,which='both');ax.legend(fontsize=8)
    fig.suptitle('UA-2 inclined startup: unchanged equations, gradual timestep growth\nAR10, 20 strips, 9°, k=0.95, peak-to-peak A/c=0.5')
    fig.savefig(STEM.with_suffix('.svg'));fig.savefig(STEM.with_suffix('.png'),dpi=170);plt.close(fig)
    table='\n'.join(f"| {label} | {100*r['error_fractions']['CL']:.5f}% | {100*r['error_fractions']['circulation']:.5f}% | {100*r['error_fractions']['circulation_rate']:.5f}% | {100*r['diagnostics']['first_step_rate_relative_error']:.4f}% | {400*r['diagnostics']['maximum_heave_position_error']:.5f}% |" for label,r,_ in datasets)
    status='1/1 inclined first-cycle check passes' if audit['passed'] else '0/1 inclined first-cycle checks pass'
    gate_text='All declared gates pass.' if audit['passed'] else 'Failed gates: '+', '.join(failed)+'.'
    text=f'''# UA-2: resolving inclined-wing startup time error

Updated 2026-11-01. **{status}** for the 20-strip AR10 wing at 9°,
k=0.95 and peak-to-peak A/c=0.5. {gate_text} The
[original uniform-grid pilot](isae-ua2-incidence-20261101.md) remains saved,
including its failed circulation/rate limits. This follow-up uses the same
production equations and existing variable-step BDF implementation, with
a prescribed gradual startup grid already used in the zero-incidence UA-2 tests.

| Time grid | Lift error | Worst strip circulation error | Worst strip rate error | First-step relative rate error | Max position error, % heave amplitude |
|---|---:|---:|---:|---:|---:|---:|
{table}

The first step is nominal dt/256. Subsequent increments grow by at most 1.125
until reaching the nominal dt. The 160/320 nominal grids have 200/360 accepted
steps, respectively. The complete forcing table is present before the first
step. Every checkpoint preserves the accepted state and BDF predecessor;
only the initial step is first order. No analytic circulation or periodic
initial state is supplied to production.

All **562 unique snapshots** and all 36 serial segments are audited. Each
segment has at most 16 steps. Every solve converges without rejected steps.
The first-cycle check counts one physical case; it does not add a second
case for replacing the failed uniform-grid calculation.

![Lift and local-rate error under startup refinement](isae-ua2-incidence-startup-20261101.svg)

The original waveform gates remain: fine lift and each strip's circulation
and rate error below 0.1%, with fine/coarse ratios below 0.35 and normalized
nonlinear residuals below 1e-10. Lift/circulation are normalized by their
departures from pre-motion steady values; rate uses each strip's own peak.
Additional gates were declared before these runs: first-step rate error below
1% of that sample's reference, maximum velocity error below 0.1% of peak
heave velocity, and maximum position error below 0.1% of heave amplitude.
No tolerance was relaxed.

The fine/coarse lift/circulation/rate ratios are
{', '.join(f'{v:.4f}' for v in audit['ratios'].values())}. Fine velocity error is
{fine['diagnostics']['maximum_heave_velocity_error']:.7f} m/s, or
{100*fine['diagnostics']['maximum_heave_velocity_error']/4.75:.5f}% of peak velocity.
Maximum residual is {fine['diagnostics']['maximum_residual']:.3e}.
The initial circulation matches the independent steady finite-wing solution
within {fine['diagnostics']['initial_circulation_error']:.3e}.

The independent [inclined finite-wing equations](isae-inclined-wing-heave-reference.md)
are integrated by DOP853 and Radau at every requested time. Their largest
difference is {max(reference['method_differences'].values()):.3e} of the relevant
peak, below the unchanged 1e-8 reference gate. Tight reference tolerances are
1e-13 relative and 1e-15 absolute. At the fine first step, the two reference
rates agree within {100*first_reference_errors['320']:.3e}% of that sample's
own local rate. Production uses its own nonlinear solves.

Solver time is {audit['solver_seconds']['min']:.2f}–{audit['solver_seconds']['max']:.2f}
seconds per segment, totaling {audit['solver_seconds']['total']:.2f} seconds.
All jobs are serial, single-threaded and capped at 45 seconds each.
All 136 production Python files and application defaults remain unchanged.
This result demonstrates the effect of resolving startup in this verification
case; arbitrary-model automatic step selection is still unfinished.

The accompanying 64/64 inclined instantaneous checks and eight independent
reference pairs remain passing. Earlier zero-incidence UA-2 results are
unchanged. Production periodic response at nonzero incidence, 40-strip time
refinement, broader amplitudes/frequencies, stall and browser/WASM verification
remain incomplete. The 222 native UA-2 comparisons remain blocked by unresolved
archived-run provenance. Neither this family nor the full project goal is complete.

Evidence: [machine summary](isae-ua2-incidence-startup-20261101.json),
[full grids, reference, raw histories and receipts](../../artifacts/isae/ua2-incidence-startup-20261101),
[startup-grid setup](../../scripts/isae_ua2_incidence_startup.py), and
[all-snapshot audit](../../scripts/audit-isae-ua2-incidence-startup.py).
'''
    for p in (Path(__file__).resolve(),ROOT/'scripts/audit-isae-ua2-incidence-startup.py'):
        target=BASE/'frozen-code'/p.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,target)
    assert all(digest(ROOT/n)==h for n,h in pins.items())
    STEM.with_suffix('.json').write_text(json.dumps(summary,indent=2,allow_nan=False)+'\n')
    STEM.with_suffix('.md').write_text(text)
    print(json.dumps(dict(passed=audit['passed'],failed_gates=failed,fine_errors=fine['error_fractions'],
        first_step_percent=100*fine['diagnostics']['first_step_rate_relative_error'],position_percent=400*fine['diagnostics']['maximum_heave_position_error'])))


if __name__=='__main__':main()
