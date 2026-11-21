"""Summarize inclined UA-2 reference, load identities and production time audit."""
from hashlib import sha256
import json
from pathlib import Path
import shutil
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
R2=ROOT/'artifacts/isae/ua2-incidence-20261101-r2'
R3=ROOT/'artifacts/isae/ua2-incidence-20261101-r3'
TIME=ROOT/'artifacts/isae/ua2-incidence-time-20261101'
STEM=ROOT/'docs/validation/isae-ua2-incidence-20261101'


def digest(p):return sha256(p.read_bytes()).hexdigest()


def main():
    assert not STEM.with_suffix('.json').exists() and not (R3/'summary-plan.json').exists()
    audit=json.loads((TIME/'audit.json').read_text())
    assert json.loads((TIME/'audit-execution.json').read_text())['exit_code']==(0 if audit['passed'] else 1)
    pins={};sources={};cases=[];selected=[]
    for n in (20,40):
        for alpha in (5,9):
            for k in (.475,.95):
                case=f'n{n}-a{alpha}-k{round(k*1000):04d}';base=R3 if n==40 and alpha==9 else R2
                selected.append(dict(case=case,folder=str(base.relative_to(ROOT))))
                reports={}
                for action in ('reference','probe'):
                    folder=base/f'{action}-{case}'
                    plan=json.loads((folder/'plan.json').read_text());report=json.loads((folder/'report.json').read_text())
                    assert report['passed'] and report['source_unchanged']
                    receipt_path=base/f'{action}-{case}-execution.json'
                    receipt=json.loads(receipt_path.read_text());assert receipt['exit_code']==0
                    if 'report_sha256' in receipt:assert receipt['report_sha256']==digest(folder/'report.json')
                    sources.update(plan['source_sha256'])
                    for p in (folder/'plan.json',folder/'report.json',receipt_path):pins[str(p.relative_to(ROOT))]=digest(p)
                    reports[action]=report
                ref=reports['reference'];probe=reports['probe']
                assert probe['physical_states']==8 and len(probe['checks'])==8 and all(r['passed'] for r in probe['checks'])
                assert all(digest(ROOT/p)==h for p,h in probe['reference_sha256'].items())
                cases.append(dict(panels=n,alpha_deg=alpha,k=k,passed=True,
                    reference_method_difference=max(ref['method_differences'].values()),
                    periodic_closure=max(ref['reference'][m]['periodic']['closure_fraction'] for m in ('DOP853','Radau')),
                    maximum_force_error=max(e['force'] for r in probe['checks'] for e in r['errors'].values()),
                    maximum_residual_error=max(e['residual'] for r in probe['checks'] for e in r['errors'].values()),
                    maximum_rotation_error=max(r['rotation_error'] for r in probe['checks']),
                    measured_periodic=ref['reference']['DOP853']['periodic']['measured'],
                    reference_rtol=ref['reference']['DOP853']['periodic']['rtol']))
    for n,h in {**sources,**audit['source_sha256'],**audit['input_sha256']}.items():assert digest(ROOT/n)==h,n
    for p in (Path(__file__).resolve(),TIME/'audit.json',TIME/'audit-execution.json',R2/'tests-execution.json',
        ROOT/'docs/validation/isae-inclined-wing-heave-reference.md',
        R2/'reference-n40-a9-k0475/report.json',ROOT/'artifacts/isae/ua2-incidence-20261101/startup-diagnostic.json'):
        pins[str(p.relative_to(ROOT))]=digest(p)
    (R3/'summary-plan.json').write_text(json.dumps(dict(selected_cases=selected,input_sha256=pins,source_sha256=sources),indent=2)+'\n')
    fine=audit['results']['160'];coarse=audit['results']['80'];failed=[k for k,v in audit['checks'].items() if not v]
    summary=dict(date='2026-11-01',cases=cases,reference_pairs_passed=8,physical_state_checks_passed=64,
        physical_state_checks_total=64,coordinate_evaluations=128,focused_tests_passed=7,
        inclined_time_checks_passed=int(audit['passed']),inclined_time_checks_total=1,
        time_failed_gates=failed,time_refinement_ratios=audit['ratios'],
        time_grids={n:{k:v for k,v in r.items() if k!='rows'} for n,r in audit['results'].items()},
        audited_time_snapshots=242,production_files_changed=0,native_ASWING_comparison=False,
        full_goal_complete=False,input_sha256=pins)
    fig,axes=plt.subplots(1,2,figsize=(11,4.5),constrained_layout=True)
    for steps,color in (('80','#d97706'),('160','#2563eb')):
        r=audit['results'][steps];rows=r['rows'];phase=np.array([v['time'] for v in rows])/(np.pi/9.5)
        actual=np.array([v['CL'] for v in rows]);expected=np.array([v['reference']['CL'] for v in rows])
        axes[0].plot(phase,actual,color=color,linestyle='--',label=f'Production {steps} steps')
        if steps=='160':axes[0].plot(phase,expected,color='.15',linewidth=.8,label='Independent cold reference')
        rate=np.array([v['circulation_rate'] for v in rows]);target=np.array([v['reference']['circulation_rate'] for v in rows])
        axes[1].plot(phase,100*np.max(abs(rate-target)/r['scales']['circulation_rate'],axis=1),color=color,label=f'{steps} steps')
    axes[1].axhline(.1,color='.4',linestyle=':',label='Fine rate limit (0.1%)')
    axes[0].set(title='First-cycle lift from steady initialization',xlabel='Cycle phase',ylabel='Fixed-axis CL')
    axes[1].set(title='Worst strip circulation-rate error',xlabel='Cycle phase',ylabel='% of each strip reference peak')
    for ax in axes:ax.grid(alpha=.2);ax.legend(fontsize=8)
    fig.suptitle('UA-2 inclined time pilot: AR10, 20 strips, 9°, k=0.95, A/c=0.5')
    fig.savefig(STEM.with_suffix('.svg'));fig.savefig(STEM.with_suffix('.png'),dpi=170);plt.close(fig)
    table='\n'.join(f"| {r['panels']} | {r['alpha_deg']}° | {r['k']} | {r['reference_method_difference']:.3e} | {r['maximum_force_error']:.3e} | {r['maximum_residual_error']:.3e} |" for r in cases)
    time_table='\n'.join(f"| {n} | {100*r['error_fractions']['CL']:.5f}% | {100*r['error_fractions']['circulation']:.5f}% | {100*r['error_fractions']['circulation_rate']:.5f}% | {100*r['diagnostics']['first_step_rate_relative_error']:.3f}% |" for n,r in audit['results'].items())
    passed='1/1 first-cycle refinement check passes' if audit['passed'] else '0/1 first-cycle refinement checks pass'
    gate_text='All declared time gates pass.' if audit['passed'] else 'Failed time gates: '+', '.join(failed)+'.'
    text=f'''# UA-2: nonzero-incidence reference and production checks

Updated 2026-11-01. **64/64 instantaneous-state checks pass**, spanning
20/40 strips, 5°/9°, k=0.475/0.95 and peak-to-peak A/c=0.5. Eight phases per
case are checked in both body and wind coordinates (128 production evaluations).
**{passed}** for the 20-strip, 9°, k=0.95 pilot. These are independently
implemented equation checks, not recovered native ASWING trajectories.

| Strips | Mean incidence | k | Maximum reference-method difference, fraction | Maximum vector-force coefficient error | Maximum residual error |
|---:|---:|---:|---:|---:|---:|
{table}

The [inclined-wing derivation](isae-inclined-wing-heave-reference.md) retains
finite-span bound-induced velocity, moving control-point direction, the
circulation-rate force and apparent-mass projection onto fixed lift axes.
The closed span integrals are independently derived from the horseshoes.
The nonzero steady circulation follows a direct finite-grid tangency solve.
Seven focused tests cover the zero-incidence limit, infinite-span section
limit, steady solutions, analytic Jacobian, coordinate rotation, off-solution
loads and the reference integrator's startup.

Each reference uses separate DOP853 and Radau cold and periodic integrations.
Their largest accepted difference is
**{max(r['reference_method_difference'] for r in cases):.3e}** of the relevant
peak, below the unchanged 1e-8 gate. Each strip's own peak is used for local
circulation and rate. The largest periodic closure fraction is
{max(r['periodic_closure'] for r in cases):.3e}. The largest body/wind coordinate
discrepancy is {max(r['maximum_rotation_error'] for r in cases):.3e}.

Instantaneous checks supply the independent circulation and rate to production
to isolate spatial residuals and loads. They do not themselves establish a
production time history or native solver parity. The following separate pilot
does evolve production circulation from production's own steady initial state.

## Production time-refinement pilot

| Nominal steps/cycle | Lift error | Worst strip circulation error | Worst strip rate error | First-step relative rate error |
|---:|---:|---:|---:|---:|
{time_table}

All 242 snapshots are audited, including startup, using the full forcing table
from the first step and preserving both BDF predecessors across 15 serial
16-step segments. Every segment converges without rejected steps. {gate_text}
Lift and each strip's circulation are normalized by their peak departure from
pre-motion steady values; rate uses each strip's peak. Fine errors must be
below 0.1%, fine/coarse ratios below 0.35, and nonlinear residuals below 1e-10.
The SA 3% tolerance is not used. Ratios for lift/circulation/rate are
{', '.join(f'{v:.4f}' for v in audit['ratios'].values())}.

![Production first-cycle lift and local-rate accuracy](isae-ua2-incidence-20261101.svg)

The fine maximum residual is {fine['diagnostics']['maximum_residual']:.3e};
initial circulation differs from the independent finite-grid steady solution
by at most {fine['diagnostics']['initial_circulation_error']:.3e}.
Maximum heave velocity error is {fine['diagnostics']['maximum_heave_velocity_error']:.7f} m/s;
maximum position error is {400*fine['diagnostics']['maximum_heave_position_error']:.5f}%
of heave amplitude. Motion and first-step relative-rate errors remain visible
diagnostics, without separate gates in this pilot. Solver time is
{audit['solver_seconds']['min']:.2f}–{audit['solver_seconds']['max']:.2f} seconds per
segment ({audit['solver_seconds']['total']:.2f} seconds total).

## Retained reference failures and scope

The first reference attempt let DOP853 choose an entire forcing period as its
first trial from equilibrium; the internal trial overflowed. The reference
now bounds trial steps while retaining adaptive error control. A subsequent
reporting-only list/array error is also retained. At 40 strips, 9°, k=0.475,
the original integration tolerances left a tip-rate method difference of
2.316e-8, above the 1e-8 limit. Tighter tolerances (1e-13 relative, 1e-15
absolute) resolve it. Both 40-strip 9° references use that tighter integration.
The original files, failed outcomes and frozen code are preserved; none of
these changes alter production equations or acceptance limits.

All 136 production Python files remain unchanged. Jobs run serially, use one
BLAS thread and have a 45-second cap. The previous 16/16 zero-incidence
first-cycle and 2/2 periodic checks remain intact. The 222 native UA-2 slots
remain blocked by unresolved archived-run provenance. This new first-cycle
pilot does not establish production periodic response at nonzero incidence,
time accuracy on the 40-strip mesh, stall, compressibility or browser/WASM
behavior. Broader conditions and the full project goal remain unfinished.

Evidence: [machine summary](isae-ua2-incidence-20261101.json),
[reference and load checks](../../artifacts/isae/ua2-incidence-20261101-r2),
[tighter references and selected-case provenance](../../artifacts/isae/ua2-incidence-20261101-r3),
[complete production histories and audit](../../artifacts/isae/ua2-incidence-time-20261101),
and [time audit implementation](../../scripts/audit-isae-ua2-incidence-time.py).
'''
    for p in (Path(__file__).resolve(),ROOT/'scripts/audit-isae-ua2-incidence-time.py'):
        target=R3/'frozen-code'/p.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,target)
    assert all(digest(ROOT/n)==h for n,h in pins.items())
    STEM.with_suffix('.json').write_text(json.dumps(summary,indent=2,allow_nan=False)+'\n')
    STEM.with_suffix('.md').write_text(text)
    print(json.dumps(dict(state_checks_passed=64,reference_pairs_passed=8,time_passed=audit['passed'],failed_time_gates=failed,
        fine_errors=fine['error_fractions'],maximum_reference_difference=max(r['reference_method_difference'] for r in cases))))


if __name__=='__main__':main()
