"""Publish the inclined-section reference, load probes and cold time pilot."""
from hashlib import sha256
import json
import math
from pathlib import Path
import shutil

import matplotlib
matplotlib.use('Agg')
from matplotlib.lines import Line2D
import matplotlib.pyplot as plt
import numpy as np

from isae_ua_phase import source_curve

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'artifacts/isae/ua1-incidence-20261101'
TIME=ROOT/'artifacts/isae/ua1-incidence-time-20261101'
STEM=ROOT/'docs/validation/isae-ua1-incidence-20261101'


def digest(p):return sha256(p.read_bytes()).hexdigest()


def main():
    if STEM.with_suffix('.json').exists() or (BASE/'summary-plan.json').exists():
        raise SystemExit('Preserve the completed report')
    inputs={};references={};probes={};seconds={}
    names=[f'ref-k{k:03d}-a{alpha}' for k in (47,94) for alpha in (0,5,9)]+['production-n4','production-n8']
    for name in names:
        folder=BASE/name
        report=json.loads((folder/'report.json').read_text())
        assert report['passed'] and report['source_unchanged']
        assert report['plan']==json.loads((folder/'plan.json').read_text())
        assert json.loads((BASE/(name+'-execution.json')).read_text())['exit_code']==0
        for n,h in {**report['plan']['source_sha256'],**report['plan']['reference_input_sha256']}.items():
            assert digest(ROOT/n)==h,n
        for p in (folder/'report.json',folder/'plan.json',BASE/(name+'-execution.json')):
            inputs[str(p.relative_to(ROOT))]=digest(p)
        seconds[name]=report['seconds']
        if name.startswith('ref-'):
            settings=report['plan']['settings'];references[(settings['alpha'],settings['k'])]=report
        else:probes[report['plan']['settings']['panels']]=report
    audit=json.loads((TIME/'audit.json').read_text())
    assert audit['refinement_check_passed'] and audit['audited_unique_snapshots']==242
    assert json.loads((TIME/'audit-execution.json').read_text())['exit_code']==0
    for n,h in {**audit['input_sha256'],**audit['plan']['source_sha256']}.items():assert digest(ROOT/n)==h,n
    for p in (TIME/'audit.json',TIME/'audit-plan.json',TIME/'audit-execution.json',BASE/'tests-execution.json',
              ROOT/'docs/validation/isae-inclined-section-heave-reference.md',Path(__file__).resolve()):
        inputs[str(p.relative_to(ROOT))]=digest(p)
    assert json.loads((BASE/'tests-execution.json').read_text())['tests_passed']==13
    plan=dict(input_sha256=inputs,native_ASWING_comparison=False,
        scope='Six nonlinear attached-flow section references; 96 instantaneous production states; one alpha9 k.94 cold time-refinement check.',
        production_periodic_checks_added=0)
    (BASE/'summary-plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    frozen=BASE/'frozen-code/scripts'/Path(__file__).name
    frozen.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(__file__,frozen)
    maximum_agreement=max(max(c['fractions'].values()) for r in references.values() for c in r['agreement_checks'])
    differences=[dict(alpha_deg=alpha,k=k,**r['differences_from_linear_source']) for (alpha,k),r in sorted(references.items())]
    summary=dict(date='2026-11-01',plan=plan,instantaneous_checks_passed=sum(p['checks_passed'] for p in probes.values()),
        instantaneous_checks_total=sum(p['checks_total'] for p in probes.values()),
        reference_agreement_checks_passed=sum(sum(c['passed'] for c in r['agreement_checks']) for r in references.values()),
        maximum_reference_method_difference_fraction=maximum_agreement,
        maximum_periodic_closure_fraction=max(r['periodic_closure_fraction'] for r in references.values()),
        production_probes={str(n):{key:r[key] for key in ('maximum_force_coefficient_error','maximum_normalized_residual',
            'maximum_apparent_coefficient_error','maximum_coordinate_rotation_error','seconds')} for n,r in probes.items()},
        differences_from_linear_source=differences,first_cycle_refinement_checks_passed=1,
        first_cycle={**{k:v for k,v in audit.items() if k not in ('results','input_sha256','plan')},
            'grids':{n:{k:v for k,v in r.items() if k!='rows'} for n,r in audit['results'].items()}},
        focused_tests_passed=13,native_ASWING_comparison=False,production_periodic_checks_added=0,
        production_files_changed=0,reference_and_probe_seconds=seconds,
        remaining=['Nonzero-incidence production periodic response; other amplitudes/frequencies and the 5-degree time histories.',
            'Stall, compressibility and native output provenance are outside this attached-flow reference.',
            'Browser/WASM verification and full project coverage remain unfinished.'])
    fig,axes=plt.subplots(2,2,figsize=(11.5,8),constrained_layout=True)
    colors={0:'#2563eb',5:'#d97706',9:'#059669'}
    for col,k in enumerate((.47,.94)):
        for alpha in (0,5,9):
            r=references[(alpha,k)]['references']['periodic']['quadrature']
            phase=np.array([x['time'] for x in r['rows']])/r['period']
            axes[0,col].plot(phase,[x['CL'] for x in r['rows']],color=colors[alpha],label=f'{alpha}° nonlinear')
            axes[0,col].plot(phase,source_curve(k,alpha,phase)['CL'],color=colors[alpha],linestyle='--',alpha=.7)
            points=[c for c in probes[8]['checks'] if c['alpha_deg']==alpha and c['k']==k]
            direction=np.array([-math.sin(math.radians(alpha)),0.,math.cos(math.radians(alpha))])
            axes[0,col].scatter([p['phase'] for p in points],
                [np.array(p['production']['body']['CF'])@direction for p in points],marker='x',color=colors[alpha],s=24)
        handles,labels=axes[0,col].get_legend_handles_labels()
        handles.extend([Line2D([0],[0],color='.35',linestyle='--',label='Linear source'),
                        Line2D([0],[0],color='.35',marker='x',linestyle='none',label='Production load probes')])
        axes[0,col].legend(handles=handles,fontsize=7.5,ncol=2)
        axes[0,col].set(title=f'Periodic reference, k={k:g}',xlabel='Cycle phase',ylabel='Fixed-axis lift coefficient CL')
    for steps,color in (('80','#d97706'),('160','#2563eb')):
        r=audit['results'][steps];rows=r['rows']
        phase=np.array([x['time'] for x in rows])/(math.pi/9.4)
        actual=np.array([x['CL'] for x in rows]);expected=np.array([x['reference']['CL'] for x in rows])
        axes[1,0].plot(phase,actual,color=color,linestyle='--',label=f'Production {steps} steps')
        axes[1,1].plot(phase,100*(actual-expected)/r['scales']['CL'],color=color,label=f'{steps} steps')
        if steps=='160':axes[1,0].plot(phase,expected,color='.15',linewidth=.8,label='Independent cold reference')
    axes[1,0].set(title='Production first cycle: 9°, k=0.94',xlabel='Cycle phase',ylabel='Fixed-axis lift coefficient CL')
    axes[1,1].set(title='First-cycle lift error',xlabel='Cycle phase',ylabel='Error (% of cold lift variation)')
    for ax in axes[1]:ax.legend(fontsize=8)
    for ax in axes.flat:ax.grid(alpha=.2)
    fig.suptitle('UA-1: nonlinear freestream-normal plunge at nonzero incidence\nAttached-flow equations; A/c=0.5; no native ASWING trajectory claim',fontsize=12)
    fig.savefig(STEM.with_suffix('.svg'));fig.savefig(STEM.with_suffix('.png'),dpi=170);plt.close(fig)
    time_rows='\n'.join(f"| {n} | {100*r['error_fractions']['CL']:.5f}% | {100*r['error_fractions']['circulation']:.5f}% | "
        f"{100*r['error_fractions']['rate']:.5f}% |" for n,r in audit['results'].items())
    diff_rows='\n'.join(f"| {r['k']:g} | {r['alpha_deg']:g}° | {r['waveform_percent_of_linear_amplitude']:.3f}% | "
        f"{r['nonlinear_mean_CL']:.6f} | {r['mean_CL']:+.6f} | {r['fundamental_amplitude_percent']:+.3f}% | "
        f"{r['fundamental_phase_deg']:+.3f}° |" for r in differences)
    probe_rows='\n'.join(f"| {n} | {r['checks_passed']}/48 | {r['maximum_force_coefficient_error']:.3e} | "
        f"{r['maximum_normalized_residual']:.3e} | {r['maximum_coordinate_rotation_error']:.3e} |" for n,r in probes.items())
    fine=audit['results']['160'];coarse=audit['results']['80']
    report=f'''# UA-1: nonlinear section response at nonzero incidence

Updated 2026-11-01. **96/96 instantaneous production-state checks pass**, and
**1/1 nonzero-incidence first-cycle time-refinement check passes** at 9°,
k=0.94, A/c=0.5. All **242 unique time snapshots** are audited. This extends
the earlier [linear phase-curve checks](isae-ua1-phase-20261101.md) using the
[independently derived nonlinear section equations](isae-inclined-section-heave-reference.md).
Nonzero-incidence production periodic response remains unfinished.

| Steps in first cycle | Lift waveform error | Per-strip circulation error | Per-strip circulation-rate error |
|---:|---:|---:|---:|
{time_rows}

Lift and circulation errors use the cold reference's maximum departure from
its pre-motion steady value, so the nonzero mean does not hide dynamic error.
Rate uses its reference peak. Every strip and every original sample time is
checked. Fine/coarse error ratios are {audit['fine_to_coarse_ratios']['CL']:.4f},
{audit['fine_to_coarse_ratios']['circulation']:.4f} and {audit['fine_to_coarse_ratios']['rate']:.4f}.
The predeclared gates require all fine errors below 0.1% and ratios below 0.35.
The provisional SA 3% tolerance does not apply.

![Nonlinear periodic references, production probes and first-cycle refinement](isae-ua1-incidence-20261101.svg)

The [primary paper](https://purehost.bath.ac.uk/ws/files/152831878/aiaa_2017_Nicola_Chiereghin_BathUni_full_paper.pdf),
Sections II and II.B, specifies plunge and measured lift normal to the fixed
freestream. The reconstruction follows that direction at each mean incidence.
Acceleration is projected onto the section normal before applying apparent
mass; force is then projected onto the fixed measurement direction. This
produces a cos²α factor in the apparent-mass contribution to fixed-axis lift.

The independent circulation ODE has a time-dependent coefficient because the
control point follows the instantaneous incident wind. An integrating-factor
quadrature and independently integrated DOP853/Radau solutions agree within
**{maximum_agreement:.3e} of the relevant peak** over both a steady-initialized
first cycle and a periodic cycle for all six frequency/incidence combinations.
All 24 method comparisons pass. Periodic closure is below
{summary['maximum_periodic_closure_fraction']:.3e}. The implementation uses no
production mesh, vortex, residual, force or time-integration function.

## Instantaneous production checks

Both 4- and 8-unknown AR200000 reconstructions are checked at eight phases for
each of the six cases: k=0.47/0.94, mean incidence 0°/5°/9°, A/c=0.5. Each state
is evaluated in chord axes and in an equivalent rotated-wing/wind-axis
representation. Circulatory, circulation-rate and apparent-mass force vectors
are checked separately. The direction and dynamic pressure used by the
production instantaneous CL output are also checked explicitly.

| Circulation unknowns | Passing states | Max absolute force-coefficient error | Max normalized tangency residual | Max coordinate-rotation difference |
|---:|---:|---:|---:|---:|
{probe_rows}

These probes impose infinite-section circulation on a finite-span reconstruction;
they do not solve its finite-wing circulation equations. The small residuals
therefore include finite-tip effects. Their declared gates are 5e-5 for force
coefficients and tangency residual, 1e-12 for apparent force, and 2e-12 for
coordinate covariance. The closer tip sampling on the finer mesh can increase
the maximum local residual. This is a section-limit check, not a demonstrated
spatial-continuum convergence limit or a native model reconstruction.

Thirteen focused tests pass, including the existing zero-incidence limit,
steady `CL=2π tan α`, zero-amplitude periodic behavior, sign-reversal/half-cycle
symmetry, three-method integration agreement, and force-component covariance.
A frozen-wind variant fails the same finite-motion tangency test as expected.

## Production time pilot

The production JSON time path starts from its own solved steady state at 9°.
No analytic circulation is inserted. Ax and Az jointly prescribe the physical
plunge direction, with exact cosine accelerations at all requested time knots.
Both trajectories run continuously for one cycle; the full forcing table is
present from startup. Six serial 40-step segments retain the BDF predecessor,
complete frame state and original forcing. All joins are exact, with no rejected
steps or repeated solves. Solver time is **{audit['solver_seconds']['min']:.2f}–{audit['solver_seconds']['max']:.2f}
seconds per segment**, totaling {audit['solver_seconds']['total']:.2f} seconds.
Each process has one BLAS thread and a 45-second cap.

The largest accepted nonlinear residual is {fine['diagnostics']['maximum_residual']:.3e}.
The initial finite-wing circulation differs from the infinite-section steady
value by up to {fine['diagnostics']['initial_circulation_absolute_error']:.6f};
that spatial difference is retained in every history comparison.
The fine first-step rate error is **{100*fine['diagnostics']['first_step_rate_relative_error']:.3f}%**,
larger than the whole-waveform rate error because it uses that first sample's
own small reference value. Maximum heave velocity error is
{fine['diagnostics']['maximum_velocity_error']:.6f} m/s; maximum position error is
{fine['diagnostics']['maximum_position_error']:.7f} chords;
position error is {400*fine['diagnostics']['maximum_position_error']:.4f}% of heave amplitude.
These startup/motion diagnostics are explicit and have no additional pass gate
in this pilot. The accepted lift/circulation/rate gates are unchanged.

## Difference from the published linear curves

The source phase curves use linear superposition. The nonlinear attached-flow
reference has finite-motion changes in mean lift, phase and higher harmonics.
The following are **differences between approximation levels**, not failures
against verified native ASWING output. Waveform difference uses the linear
oscillatory amplitude; mean differences are in absolute CL units.

| k | Mean incidence | Max waveform difference | Nonlinear mean CL | Mean change from linear source | Fundamental amplitude change | Phase change |
|---:|---:|---:|---:|---:|---:|---:|
{diff_rows}

For example, at 9° and k=0.94, the nonlinear reference mean is 1.05513 versus
0.98696 from the linear source, and the complete waveform differs by 9.82% of
the source oscillatory amplitude. The independent nonlinear reference agrees
with production instantaneous loads and the first-cycle solver. Forcing those
nonlinear results to equal the linear curve would change the verified equations.
These means are model predictions with stall disabled; they do not reproduce
or fit the experimental leading-edge-vortex mean offsets.

All 136 production Python files remain unchanged. Native output provenance,
stall, other amplitudes/frequencies, nonzero-incidence production periodic
response, and browser/WASM verification remain unfinished. The existing UA-1
and UA-2 passing scopes remain intact; all 222 native UA-2 slots remain blocked.

Evidence: [machine summary](isae-ua1-incidence-20261101.json),
[reference and instantaneous-probe artifacts](../../artifacts/isae/ua1-incidence-20261101),
[complete time trajectories, plans and audit](../../artifacts/isae/ua1-incidence-time-20261101),
[derivation](isae-inclined-section-heave-reference.md),
[reference/probe runner](../../scripts/verify-isae-ua1-incidence.py), and
[time runner](../../scripts/verify-isae-ua1-incidence-time.py).
'''
    assert all(digest(ROOT/n)==h for n,h in inputs.items())
    STEM.with_suffix('.json').write_text(json.dumps(summary,indent=2,allow_nan=False)+'\n')
    STEM.with_suffix('.md').write_text(report)
    print(json.dumps({k:summary[k] for k in ('instantaneous_checks_passed','reference_agreement_checks_passed',
        'maximum_reference_method_difference_fraction','first_cycle_refinement_checks_passed','focused_tests_passed')}))


if __name__=='__main__':main()
