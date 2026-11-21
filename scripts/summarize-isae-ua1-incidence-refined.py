"""Report UA-1 time refinement without hiding the original failed grid."""
from hashlib import sha256
import json
from pathlib import Path
import shutil

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'artifacts/isae/ua1-incidence-periodic-refined-20261101'
OLD=ROOT/'artifacts/isae/ua1-incidence-periodic-20261101'
STEM=ROOT/'docs/validation/isae-ua1-incidence-periodic-refined-20261101'


def digest(path):return sha256(path.read_bytes()).hexdigest()


def main():
    if STEM.with_suffix('.json').exists() or (BASE/'summary-plan.json').exists():
        raise SystemExit('Preserve completed report')
    audit=json.loads((BASE/'audit.json').read_text())
    old=json.loads((OLD/'audit.json').read_text())
    reference=json.loads((BASE/'reference.json').read_text())
    old_reference=json.loads((OLD/'reference.json').read_text())['reference']
    assert reference['reference']['periodic']['rows'][::2]==old_reference['periodic']['rows']
    assert reference['reference']['cold_rows'][::2]==old_reference['cold_rows']
    batch=json.loads((BASE/'batch-plan.json').read_text())
    assert json.loads((BASE/'batch-complete.json').read_text())['computed_jobs']==32
    assert json.loads((BASE/'audit-execution.json').read_text())['exit_code']==(0 if audit['passed'] else 1)
    inputs={**batch['source_sha256'],**audit['input_sha256'],**audit['plan']['source_sha256']}
    for name,value in inputs.items():assert digest(ROOT/name)==value,name
    paths=[Path(__file__).resolve(),BASE/'audit.json',BASE/'audit-execution.json',
        BASE/'reference.json',BASE/'batch-complete.json',OLD/'audit.json',OLD/'reference.json']
    pins={str(p.relative_to(ROOT)):digest(p) for p in paths}
    (BASE/'summary-plan.json').write_text(json.dumps(dict(source_sha256=pins),indent=2)+'\n')
    for p in (Path(__file__).resolve(),ROOT/'scripts/audit-isae-ua1-incidence-refined.py'):
        target=BASE/'frozen-code'/p.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(p,target)
    results={'80':old['results']['80'],**audit['results']}
    fine=results['320'];final=fine['cycles'][-1]
    failed=[k for k,v in audit['checks'].items() if not v]
    new_receipts=[json.loads(p.read_text()) for p in sorted(BASE.glob('n320-part*-execution.json'))]
    new_reports=[json.loads(p.read_text()) for p in sorted(BASE.glob('n320-part*/report.json'))]
    assert len(new_receipts)==len(new_reports)==32
    assert all(r['exit_code']==0 for r in new_receipts)
    seconds=[r['solver_seconds'] for r in new_reports]
    wall=[r['wall_seconds'] for r in new_receipts]
    summary=dict(passed=audit['passed'],checks=audit['checks'],failed_gates=failed,
        periodic_checks_passed=int(audit['passed']),periodic_checks_total=1,
        fine_to_coarse_ratios=audit['fine_to_coarse_ratios'],source_sha256=pins,
        grids={n:{k:v for k,v in r.items() if k!='rows'} for n,r in results.items()},
        new_production_snapshots=2561,refinement_audited_snapshots=3842,
        total_unique_snapshots_all_three_grids=4483,new_segments=32,
        new_solver_seconds=dict(min=min(seconds),max=max(seconds),total=sum(seconds)),
        new_wall_seconds=dict(min=min(wall),max=max(wall),total=sum(wall)),
        production_files_changed=0,native_ASWING_comparison=False,full_goal_complete=False)
    fig,axes=plt.subplots(2,2,figsize=(11,8),constrained_layout=True)
    colors={'80':'#d97706','160':'#2563eb','320':'#059669'}
    targets=reference['reference']['periodic']['rows']
    axes[0,0].plot(np.linspace(0,1,321),[r['CL'] for r in targets],color='.15',label='Independent reference')
    for n,r in results.items():
        count=int(n);phase=np.linspace(0,1,count+1);last=r['rows'][-count-1:]
        actual=np.array([v['CL'] for v in last]);expected=np.array([v['CL'] for v in targets[::320//count]])
        axes[0,0].plot(phase,actual,color=colors[n],linestyle='--',label=f'{n} steps/cycle')
        axes[0,1].plot(phase,100*(actual-expected)/r['periodic_scales']['CL'],color=colors[n],label=n)
        axes[1,1].plot(range(1,9),400*np.array(r['diagnostics']['cycle_end_heave_position_errors']),color=colors[n],marker='o',label=n)
    for key,color,label in (('CL','#2563eb','Lift'),('circulation','#d97706','Circulation'),('circulation_rate','#059669','Circulation rate')):
        axes[1,0].loglog([80,160,320],[100*r['cycles'][-1]['error_fractions'][key] for r in results.values()],color=color,marker='o',label=label)
    axes[1,0].axhline(.1,color='.4',linestyle=':',label='Fine waveform limit (0.1%)')
    axes[0,0].set(title='Final-cycle lift',xlabel='Cycle phase',ylabel='Fixed-axis CL')
    axes[0,1].set(title='Final-cycle lift error',xlabel='Cycle phase',ylabel='% of reference lift variation')
    axes[1,0].set(title='Time refinement',xlabel='Steps per cycle',ylabel='Final waveform error (%)',xticks=[80,160,320])
    axes[1,0].set_xticklabels(['80','160','320'])
    axes[1,1].set(title='Cycle-end position error',xlabel='Completed cycle',ylabel='% of heave amplitude',xticks=range(1,9))
    for ax in axes.flat:ax.grid(alpha=.2,which='both');ax.legend(fontsize=8)
    fig.suptitle('UA-1 inclined heave: unchanged equations and acceptance limits\n9°, k=0.94, peak-to-peak A/c=0.5; eight continuous cycles',fontsize=12)
    fig.savefig(STEM.with_suffix('.svg'));fig.savefig(STEM.with_suffix('.png'),dpi=170);plt.close(fig)
    table='\n'.join(f"| {n} | {100*r['cycles'][-1]['error_fractions']['CL']:.5f}% | {100*r['cycles'][-1]['error_fractions']['circulation']:.5f}% | {100*r['cycles'][-1]['error_fractions']['circulation_rate']:.5f}% | {100*r['cycles'][-1]['harmonic_errors'][0]['amplitude_error_fraction']:+.5f}% | {r['cycles'][-1]['harmonic_errors'][0]['phase_error_deg']:+.5f}° |" for n,r in results.items())
    harmonics='\n'.join(f"| {h['order']} | {100*h['amplitude_error_fraction']:+.5f}% | {h['phase_error_deg']:+.5f}° |" for h in final['harmonic_errors'])
    status='1/1 inclined periodic check passes' if audit['passed'] else '0/1 inclined periodic checks pass'
    gate_text='All original acceptance gates pass.' if audit['passed'] else 'Failed gates: '+', '.join(failed)+'.'
    text=f'''# UA-1: inclined periodic time refinement

Updated 2026-11-01. **{status}** at 9°, k=0.94, A/c=0.5.
{gate_text} The [original 80/160-step comparison](isae-ua1-incidence-periodic-20261101.md)
is retained, including its 0.1273% circulation error above the 0.1% limit.
This follow-up adds 320 steps per cycle using the same equations, initialization,
geometry and limits. It adds no production correction or tolerance change.
The resulting evidence is an attached-flow equation check, not native ASWING output.

| Steps/cycle | Periodic lift error | Circulation error | Circulation-rate error | Fundamental amplitude error | Phase error |
|---:|---:|---:|---:|---:|---:|
{table}

Lift and circulation errors use the peak departure from the reference cycle mean;
rate uses its peak. Every strip is checked. A nonzero mean therefore does not
dilute the reported dynamic error. The error ratios between 160 and 320 steps
are {', '.join(f"{v:.4f}" for v in audit['fine_to_coarse_ratios']['periodic_error_fractions'].values())}
for lift, circulation and rate respectively.

![Time refinement, waveform and motion accuracy](isae-ua1-incidence-periodic-refined-20261101.svg)

The 320-step run starts from its own production steady equilibrium, with the
complete eight-cycle forcing table present from startup. All 2,561 new snapshots
are retained. The audit rereads the retained 160-step raw history as well:
3,842 snapshots in this comparison, or 4,483 unique snapshots across all three
grids. The shared 160-step trajectory is not counted as a new production run.
Its recomputed rows and metrics exactly reproduce the earlier audit.

The [independent reference](isae-inclined-section-heave-reference.md) uses
integrating-factor quadrature plus the exact homogeneous startup transient.
Direct DOP853 integration of the full cold history agrees within
{max(reference['agreement_fractions'].values()):.3e} of the relevant peak.
The refined reference is exactly identical at the old grid's sample times.

## Acceptance and remaining numerical errors

All original gates remain: fine lift/circulation/rate errors below 0.1% in both
the complete cold history and final periodic cycle; fine/coarse ratios below
0.35; fundamental amplitude below 0.1%; phase below 0.1°; mean lift error below
0.1% of dynamic lift variation; final cycle changes below 0.01%; and normalized
nonlinear residual below 1e-10. The SA 3% tolerance is not used here.

Fine whole-cold-history lift/circulation/rate errors are
**{100*fine['cold_error_fractions']['CL']:.5f}% /
{100*fine['cold_error_fractions']['circulation']:.5f}% /
{100*fine['cold_error_fractions']['circulation_rate']:.5f}%**.
Reference mean CL is **{fine['periodic_reference']['mean']:.8f}**; production
mean CL is **{final['measured']['mean']:.8f}**. Mean error is
{100*final['mean_CL_error_dynamic_fraction']:+.6f}% of dynamic lift variation.
The largest final cycle-to-cycle change is
{100*max(final['cycle_change_fractions'].values()):.6f}%.

Additional diagnostics: first-step rate error
{100*fine['diagnostics']['first_step_rate_relative_error']:.3f}% of its own small
reference value; maximum heave velocity error
{fine['diagnostics']['maximum_heave_velocity_error']:.7f} m/s; maximum position
error {400*fine['diagnostics']['maximum_heave_position_error']:.5f}% of heave
amplitude. These have no separate acceptance gates in this pilot.

| Harmonic | Fine amplitude error | Fine phase error |
|---:|---:|---:|
{harmonics}

Only the fundamental has separate harmonic gates. Higher harmonics also enter
the full-waveform comparison. This is one spatial mesh with four circulation
unknowns and AR200000; finite-tip effects remain and general spatial accuracy
is not established by this time-refinement check.

The 32 new segments each advance 80 steps, preserving both BDF predecessors.
All converge without rejected steps. Solver time is
{min(seconds):.2f}–{max(seconds):.2f} seconds per segment ({sum(seconds):.2f} seconds
total); worker wall time is {min(wall):.2f}–{max(wall):.2f} seconds. Jobs run
serially with one BLAS thread and a 45-second cap. All 136 production Python
files remain unchanged. No browser/WASM or application-default validation is claimed.

Broader nonzero-incidence frequencies/amplitudes, the 5° production histories,
stall and native reference provenance remain unfinished. UA-2's previous
equation checks and 222 blocked native comparisons are unchanged. This refines
one existing UA-1 periodic case; it does not add a second physical case or
complete either validation family or the full project goal.

Evidence: [machine summary](isae-ua1-incidence-periodic-refined-20261101.json),
[saved plans, reference, trajectories and receipts](../../artifacts/isae/ua1-incidence-periodic-refined-20261101),
[refinement audit](../../scripts/audit-isae-ua1-incidence-refined.py).
'''
    assert all(digest(ROOT/n)==h for n,h in pins.items())
    STEM.with_suffix('.json').write_text(json.dumps(summary,indent=2,allow_nan=False)+'\n')
    STEM.with_suffix('.md').write_text(text)
    print(json.dumps(dict(passed=audit['passed'],failed_gates=failed,final_errors=final['error_fractions'],
        mean_CL=final['measured']['mean'],position_error_percent=400*fine['diagnostics']['maximum_heave_position_error'])))


if __name__=='__main__':main()
