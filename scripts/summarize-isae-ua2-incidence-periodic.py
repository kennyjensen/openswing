"""Report the full inclined UA-2 periodic time-refinement audit."""
from hashlib import sha256
import json
import os
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
BASE=Path(os.environ.get('OPENSWING_UA2_PERIODIC_BASE', ROOT/'artifacts/isae/ua2-incidence-periodic-20261101')).resolve()
STEM=ROOT/'docs/validation/isae-ua2-incidence-periodic-20261101'


def digest(p): return sha256(p.read_bytes()).hexdigest()


def main():
    assert not STEM.with_suffix('.json').exists()
    audit=json.loads((BASE/'audit.json').read_text())
    reference=json.loads((BASE/'reference.json').read_text())
    plan=json.loads((BASE/'batch-plan.json').read_text())
    completion=json.loads((BASE/'batch-complete.json').read_text())
    assert completion.get('logical_intervals',completion['computed_jobs'])==len(plan['jobs'])
    assert json.loads((BASE/'audit-execution.json').read_text())['exit_code']==(0 if audit['passed'] else 1)
    pins={**audit['source_sha256'],**audit['input_sha256']}
    for p in (Path(__file__).resolve(),BASE/'audit.json',BASE/'audit-execution.json',BASE/'reference-plan.json',BASE/'chunk-audit-plan.json'):
        pins[str(p.relative_to(ROOT))]=digest(p)
    assert all(digest(ROOT/n)==h for n,h in pins.items())
    fine=audit['results']['640'];final=fine['cycles'][-1]
    summary=dict(passed=audit['passed'],checks=audit['checks'],inclined_periodic_checks_passed=int(audit['passed']),
        inclined_periodic_checks_total=1,panels=20,cycles=8,alpha_deg=9,k=.95,amplitude_ratio=.5,
        grids={n:{k:v for k,v in r.items() if k!='rows'} for n,r in audit['results'].items()},
        ratios=audit['ratios'],audited_unique_snapshots=audit['audited_unique_snapshots'],
        new_production_segments=completion['computed_jobs'],raw_audit_chunks=len(json.loads((BASE/'chunk-audit-plan.json').read_text())['chunks']),retained_failed_attempts=completion.get('retained_failed_attempts',0),solver_seconds=audit['solver_seconds'],
        reference_method_differences=reference['method_differences'],source_sha256=pins,
        production_files_changed=1,native_ASWING_comparison=False,full_goal_complete=False)
    fig,axes=plt.subplots(1,2,figsize=(10,4.2),constrained_layout=True)
    table=[]
    for steps,color in ((320,'#d97706'),(640,'#2563eb')):
        r=audit['results'][str(steps)];last=r['cycles'][-1]
        rows=r['rows'][-steps-1:]
        target=reference['reference']['DOP853']['periodic']['rows'][::640//steps]
        phase=np.arange(steps+1)/steps
        error=np.array([a['CL']-b['CL'] for a,b in zip(rows,target)])/r['periodic_scales']['CL']
        axes[0].plot(phase,100*error,color=color,label=f'{steps} steps/cycle')
        cycles=r['cycles'][1:]
        axes[1].semilogy([c['cycle'] for c in cycles],
            [100*max(c['cycle_change_fractions'].values()) for c in cycles],color=color,marker='o',label=f'{steps} steps/cycle')
        table.append(f"| {steps} | "+' | '.join(f"{100*last['error_fractions'][k]:.5f}%" for k in ('CL','circulation','circulation_rate'))+f" | {400*r['diagnostics']['maximum_heave_position_error']:.5f}% |")
    axes[0].set(title='Eighth-cycle lift error',xlabel='Cycle phase',ylabel='% of reference periodic lift scale')
    axes[1].set(title='Largest change from preceding cycle',xlabel='Cycle',ylabel='% of the corresponding reference scale')
    axes[1].axhline(.01,color='.5',linestyle=':',label='Settling limit: 0.01%')
    for ax in axes: ax.grid(alpha=.25,which='both');ax.legend(fontsize=8)
    fig.suptitle('UA-2: eight cycles from the production steady state\nAR10, 20 strips, 9°, k=0.95, peak-to-peak A/c=0.5')
    fig.savefig(STEM.with_suffix('.svg'));fig.savefig(STEM.with_suffix('.png'),dpi=150);plt.close(fig)
    failed=[k for k,v in audit['checks'].items() if not v]
    text=f'''# UA-2: inclined periodic response

Updated 2026-11-01. **{int(audit['passed'])}/1 inclined periodic checks pass** at 20 strips,
9° incidence, k=0.95 and peak-to-peak A/c=0.5 on the reconstructed rigid AR10
wing. Mach is zero and stall is disabled. {'All declared gates pass.' if not failed else 'Failed gates: '+', '.join(failed)+'.'}
This is a comparison with independently integrated published equations.
The 222 native ASWING comparisons remain blocked by archived-run provenance.

| Nominal steps/cycle | Periodic lift error | Worst strip circulation error | Worst strip rate error | Maximum position error, % heave amplitude |
|---|---:|---:|---:|---:|
{chr(10).join(table)}

Every production trajectory starts from its own steady equilibrium, with the
complete eight-cycle acceleration table present before startup. No periodic
reference state is supplied to production. The variable-step BDF2 equations
are the documented unsteady-theory Eqs. 123–128. The initial step is first order.
Checkpoint joins preserve the full accepted state and its BDF predecessor.
The coarse and fine grids have 2,640 and 5,280 accepted steps; every coarse
interval, including startup, is bisected to form the fine grid. Later cycles
share uniformly spaced phase samples.

The saved independent motion-only calculation predicted 0.1385% position error
at 320 nominal steps/cycle over eight cycles. This exceeds the existing 0.1%
fine-result limit, so the declared production comparison uses 320/640 grids.
The 320-step result is retained as the coarse result; no acceptance limit or
physical equation was changed. Event-window filtering now retains a terminal knot within rounding distance of the requested endpoint.

![Periodic lift accuracy and settling](isae-ua2-incidence-periodic-20261101.svg)

The fine fundamental amplitude error is
{100*final['harmonic_errors'][0]['amplitude_error_fraction']:.6f}%, phase error
{final['harmonic_errors'][0]['phase_error_deg']:.6f}°, and mean-lift error
{100*final['mean_CL_error_dynamic_fraction']:.6f}% of the periodic dynamic lift scale.
The largest seventh-to-eighth-cycle change is
{100*max(final['cycle_change_fractions'].values()):.6f}%.
Fine/coarse periodic lift/circulation/rate error ratios are
{', '.join(f'{v:.5f}' for v in audit['ratios']['periodic'].values())}.
All cold-start samples are also checked: fine lift/circulation/rate errors
are {', '.join(f'{100*v:.5f}%' for v in fine['error_fractions'].values())}.
First-step rate error is {100*fine['diagnostics']['first_step_rate_relative_error']:.5f}%,
and maximum velocity error is {100*fine['diagnostics']['maximum_heave_velocity_error']/4.75:.5f}%
of peak heave velocity.

The gates retain the earlier inclined periodic limits: 0.1% for each cold and
periodic lift/circulation/rate waveform, 0.35 for fine/coarse error ratios,
0.1% fundamental amplitude error, 0.1° phase error, 0.1% dynamic-scale mean
error, 0.01% cycle change and 1e-10 normalized nonlinear residual. The inclined
startup motion gates also apply: first-step rate error below 1% of that sample,
velocity and position errors below 0.1% of their motion amplitudes. Every strip
uses its own reference scale. Periodic lift and circulation scales are peak
departures from their periodic means; cold scales use the pre-motion steady state.

Independent DOP853 and Radau cold and periodic references agree within
{max(reference['method_differences'].values()):.3e} of the relevant peak.
Each method uses its own previously verified periodic boundary for its reference
integration; both freshly computed periodic closures are below 1e-10.
Reference tolerances are 1e-13 relative and 1e-15 absolute. The independent
[inclined finite-wing derivation](isae-inclined-wing-heave-reference.md) is unchanged.

All **{audit['audited_unique_snapshots']:,} unique production snapshots** are audited.
All {completion['computed_jobs']} completed serial segments converge with no rejected steps. Each runs
with one BLAS thread and a 45-second cap. Solver time is
{audit['solver_seconds']['min']:.2f}–{audit['solver_seconds']['max']:.2f} seconds per segment,
{audit['solver_seconds']['total']:.2f} seconds total.
The fresh run's segment 42 hit its 45-second cap after reporting 102 accepted
steps. That incomplete attempt is retained and contributes no samples or pass
count. Recovery resumes the last complete checkpoint in 32-step jobs on the
same physical grid, retaining the full forcing and BDF predecessor. The raw
audit verifies every additional checkpoint join. Its numerical metrics and
acceptance limits are unchanged.
The only production change since the original attempt is the endpoint event-filter fix in forcing.py; the other 135 production files, physical equations, application defaults and accuracy limits are unchanged. The original fine-grid failure and its direct replay remain recorded in the [checkpoint repair](isae-ua2-time-endpoint-fix-20261101.md).

The [20/40-strip first-cycle comparison](isae-ua2-incidence-n40-20261101.md) remains
passing. The periodic result covers one condition at 20 strips. Periodic mesh
refinement, broader conditions, full periodic browser/WASM verification, app time-accuracy
behavior and native ASWING provenance remain unfinished. Neither UA family nor
the full project is complete.

The [checkpoint browser replay](isae-ua2-time-endpoint-wasm-20261101.md)
passes under Node WASM and in the built browser worker. Desktop/mobile startup
also passes, and the app and both download archives contain all 136 current
production modules. That one-step replay verifies the repair in the packaged
runtime; it does not establish full periodic browser accuracy.

Evidence: [machine summary](isae-ua2-incidence-periodic-20261101.json),
[references, raw histories and receipts](../../{BASE.relative_to(ROOT).as_posix()}),
[setup](../../scripts/isae_ua2_incidence_periodic.py), and
[full raw-history audit](../../scripts/audit-isae-ua2-incidence-periodic-chunks.py), and
[serial audit runner](../../scripts/run-isae-ua2-incidence-periodic-audits.py).
'''
    STEM.with_suffix('.json').write_text(json.dumps(summary,indent=2,allow_nan=False)+'\n')
    STEM.with_suffix('.md').write_text(text)
    print(json.dumps(dict(passed=audit['passed'],failed_gates=failed,periodic_errors=final['error_fractions'],
        fundamental=final['harmonic_errors'][0],position_percent=400*fine['diagnostics']['maximum_heave_position_error'])))


if __name__=='__main__': main()
