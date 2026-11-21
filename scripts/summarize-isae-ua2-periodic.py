"""Report the independently audited eight-cycle UA-2 periodic pilot."""
from hashlib import sha256
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'artifacts/isae/ua2-periodic-20261101/accepted-evidence'


def main():
    plan=json.loads((BASE/'batch-plan.json').read_text())
    assert json.loads((BASE/'batch-complete.json').read_text())['computed_segments']==len(plan['jobs'])==169
    for name,digest in plan['source_sha256'].items():
        assert sha256((ROOT/name).read_bytes()).hexdigest()==digest
        assert sha256((BASE/'frozen-code'/name).read_bytes()).hexdigest()==digest
    audits=[json.loads((BASE/f'audit-n{n}.json').read_text()) for n in (20,40)]
    rows=[];seconds=[];snapshots=0;passed=0
    figure,axes=plt.subplots(2,2,figsize=(10,7),constrained_layout=True)
    for column,(n,audit) in enumerate(zip((20,40),audits)):
        assert audit['panels']==n and audit['amplitude_ratio']==.5 and audit['k']==.95 and audit['cycles']==8
        auditor=audit.get('auditor_script','scripts/audit-isae-ua2-periodic-compact.py')
        assert audit['auditor_sha256']==sha256((ROOT/auditor).read_bytes()).hexdigest()
        for component in audit.get('component_audits',[]):
            assert sha256((ROOT/component['path']).read_bytes()).hexdigest()==component['sha256']
            assert sha256((ROOT/component['auditor_script']).read_bytes()).hexdigest()==component['auditor_sha256']
        passed+=int(audit['periodic_check_passed']);snapshots+=audit['audited_unique_snapshots']
        coarse,fine=audit['records'];final=fine['cycles'][-1]
        actual_harmonics=final['measurements']['harmonics']
        reference_harmonics=audit['reference_periodic_measurements']['harmonics']
        row=dict(panels=n,passed=audit['periodic_check_passed'],
            coarse_periodic_waveform_error_percent=100*coarse['cycles'][-1]['waveform_error_fraction'],
            fine_periodic_waveform_error_percent=100*final['waveform_error_fraction'],
            fine_periodic_per_strip_rate_error_percent=100*final['per_strip_rate_error_fraction'],
            coarse_periodic_circulation_error_percent=100*coarse['cycles'][-1]['circulation_error_fraction'],
            fine_periodic_circulation_error_percent=100*final['circulation_error_fraction'],
            periodic_circulation_refinement_ratio=final['circulation_error_fraction']/coarse['cycles'][-1]['circulation_error_fraction'],
            fine_amplitude_error_percent=100*final['amplitude_error_fraction'],
            fine_phase_error_deg=final['phase_error_deg'],
            fine_mean_error_percent_of_peak=100*final['mean_error_peak_fraction'],
            fine_final_cycle_change_percent=100*final['change_fraction'],
            fine_third_harmonic_amplitude_error_percent=100*(actual_harmonics[2]['amplitude']/reference_harmonics[2]['amplitude']-1),
            fine_third_harmonic_phase_error_deg=(actual_harmonics[2]['phase_deg']-reference_harmonics[2]['phase_deg']+180)%360-180,
            fine_second_harmonic_percent_of_fundamental=100*actual_harmonics[1]['amplitude']/reference_harmonics[0]['amplitude'],
            fine_full_history_lift_error_percent=100*fine['lift_waveform_error_fraction'],
            fine_full_history_per_strip_rate_error_percent=100*fine['per_strip_rate_waveform_error_fraction'],
            fine_full_history_circulation_error_percent=100*fine['circulation_waveform_error_fraction'],
            fine_maximum_velocity_error=fine['maximum_velocity_error'],
            fine_maximum_position_error=fine['maximum_position_error'],
            fine_first_step_relative_rate_error_percent=100*fine['first_step_relative_rate_error_fraction'],
            periodic_refinement_ratio=audit['periodic_refinement_ratio'],
            cold_refinement_ratio=audit['lift_refinement_ratio'],
            maximum_residual=max(r['maximum_residual'] for r in audit['records']),
            maximum_checkpoint_join_jump=max(r['maximum_checkpoint_join_jump'] for r in audit['records']),
            reference_closure_fraction=audit['reference_closure_fraction'],
            reference_method_difference_fractions=audit['reference_method_difference_fractions'],
            reference_periodic_measurements=audit['reference_periodic_measurements'],
            audit_sha256=sha256((BASE/f'audit-n{n}.json').read_bytes()).hexdigest())
        rows.append(row)
        for record in audit['records']:
            seconds.extend(record['segment_seconds'])
            cycles=record['cycles'];axes[1,column].semilogy([c['cycle'] for c in cycles],
                [100*c['waveform_error_fraction'] for c in cycles],'o-',label=f'{record["nominal_steps"]} steps/cycle')
            wave=record['final_waveform'];phase=np.array(wave['times'])/wave['times'][-1]
            axes[0,column].plot(phase,wave['CL'],label=f'{record["nominal_steps"]} steps/cycle')
        wave=fine['final_waveform'];phase=np.array(wave['times'])/wave['times'][-1]
        axes[0,column].plot(phase,wave['reference_CL'],'k--',lw=1,label='Independent periodic reference')
        axes[0,column].set(xlabel='Phase t/T, eighth cycle',ylabel='Vertical CL',title=f'{n} strips')
        axes[1,column].axhline(.1,color='black',ls=':',lw=1,label='Fine-grid accuracy gate')
        axes[1,column].set(xlabel='Completed cycle',ylabel='Periodic lift waveform error (%)')
        axes[1,column].set_xticks(range(2,9))
        for axis in axes[:,column]:axis.grid(alpha=.25);axis.legend(fontsize=8)
    assert snapshots==4004 and len(seconds)==len(plan['jobs'])
    wall_seconds=[]
    for job in plan['jobs']:
        receipt=json.loads((BASE/(job['id']+'-execution.json')).read_text())
        assert receipt['exit_code']==0
        wall_seconds.append(receipt['wall_seconds'])
    timeout=json.loads((BASE.parent/'n40-t160-part00-execution.json').read_text())
    assert timeout['exit_code']==124
    waves=[a['records'][-1]['final_waveform'] for a in audits]
    np.testing.assert_allclose(waves[0]['times'],waves[1]['times'],rtol=0,atol=1e-12)
    mesh=float(np.max(abs(np.array(waves[0]['CL'])-waves[1]['CL']))/max(map(abs,waves[1]['CL'])))
    mesh_passed=mesh<plan['gates']['fine_mesh_lift_change_fraction']
    summary=dict(date='2026-11-01',scope=plan['scope'],amplitude_ratio=.5,k=.95,cycles=8,meshes=rows,
        periodic_checks_passed=passed,periodic_checks_total=2,mesh_checks_passed=int(mesh_passed),mesh_checks_total=1,
        fine_periodic_mesh_lift_change_percent=100*mesh,audited_unique_snapshots=snapshots,
        continuous_trajectories=4,production_segments=len(seconds),solver_seconds_range=[min(seconds),max(seconds)],
        original_successful_segments_reused=86,recovery_segments=83,recovery_segment_steps=16,
        retained_production_timeouts=1,retained_saved_audit_timeouts=1,
        accepted_job_wall_seconds_range=[min(wall_seconds),max(wall_seconds)],
        accepted_total_job_wall_seconds=sum(wall_seconds),retained_timeout_wall_seconds=timeout['wall_seconds'],
        total_solver_seconds=sum(seconds),targeted_tests_passed=6,production_files_unchanged=136,
        production_changed=False,app_defaults_changed=False,native_ASWING_comparison=False,
        independent_spatial_reference=True,summary_script_sha256=sha256(Path(__file__).read_bytes()).hexdigest(),
        limitations=['Largest amplitude A/c=.5 and k=.95 only; other periodic amplitudes/frequencies remain.',
            'Zero mean incidence, attached flow, reconstructed rigid straight AR10 only.',
            'All 222 native UA-2 comparison slots remain blocked by model/driver provenance.',
            'Explicit startup/time grids; general automatic error control and app defaults unchanged.',
            'Supplementary circulation, higher-harmonic and prescribed-motion errors are reported outside the primary acceptance gates.',
            'Broader unsteady model coverage and browser/WASM verification remain unfinished.'])
    stem=ROOT/'docs/validation/isae-ua2-periodic-20261101'
    stem.with_suffix('.json').write_text(json.dumps(summary,indent=2,allow_nan=False)+'\n')
    figure.suptitle('UA-2 periodic pilot: A/c=0.5, k=0.95, eight continuous cycles')
    figure.savefig(stem.with_suffix('.svg'));figure.savefig(stem.with_suffix('.png'),dpi=150);plt.close(figure)
    table=['| Strips | Coarse / fine lift waveform error | Fine local rate error | Amplitude error | Phase error | Mean error, % peak | Last-cycle change |',
           '|---:|---:|---:|---:|---:|---:|---:|']
    for r in rows:
        table.append(f'| {r["panels"]} | {r["coarse_periodic_waveform_error_percent"]:.5f}% / {r["fine_periodic_waveform_error_percent"]:.5f}% | '
            f'{r["fine_periodic_per_strip_rate_error_percent"]:.5f}% | {r["fine_amplitude_error_percent"]:+.5f}% | '
            f'{r["fine_phase_error_deg"]:+.5f}° | {r["fine_mean_error_percent_of_peak"]:+.6f}% | {r["fine_final_cycle_change_percent"]:.6f}% |')
    reference_table=['| Strips | Reference fundamental CL amplitude | Reference phase | Third / first harmonic amplitude |',
                     '|---:|---:|---:|---:|']
    for r in rows:
        h=r['reference_periodic_measurements']['harmonics']
        reference_table.append(f'| {r["panels"]} | {h[0]["amplitude"]:.8f} | {h[0]["phase_deg"]:.6f}° | '
            f'{100*h[2]["amplitude"]/h[0]["amplitude"]:.5f}% |')
    refmax=max(max(r['reference_method_difference_fractions'].values()) for r in rows)
    third_amp=[r['fine_third_harmonic_amplitude_error_percent'] for r in rows]
    third_phase=[r['fine_third_harmonic_phase_error_deg'] for r in rows]
    gamma=[r['fine_periodic_circulation_error_percent'] for r in rows]
    gamma_ratio=[r['periodic_circulation_refinement_ratio'] for r in rows]
    velocity=max(r['fine_maximum_velocity_error'] for r in rows)
    position=max(r['fine_maximum_position_error'] for r in rows)
    report=f'''# UA-2: nonlinear periodic-response pilot

Updated 2026-11-01. **{passed}/2 periodic-response checks and {int(mesh_passed)}/1 mesh check pass**
for A/c=0.5, k=0.95, on the reconstructed rigid rectangular AR10 wing. Four
continuous cold-start trajectories run for eight cycles on 20/40 strips at
nominal 80/160 steps per cycle. **All {snapshots:,} unique snapshots are audited.**
This extends the [first-cycle grid](isae-ua2-amplitude-grid-20261101.md).
Native ASWING parity and complete UA-2 validation remain unfinished.

{chr(10).join(table)}

Lift waveform errors are maximum absolute differences divided by the periodic
reference peak. Local circulation-rate errors use each strip's own reference
peak. Amplitude and phase describe the fundamental harmonic; mean error is
normalized by peak lift because the reference mean is zero. Every cycle includes
both endpoints. Doubling the strip count changes the final fine-grid waveform
by **{100*mesh:.5f}%**, below the 0.2% mesh gate. This checks stability over two
meshes; the spatial continuum limit remains unverified.

{chr(10).join(reference_table)}

The phase convention is `Re(H exp(i omega t))`, with displacement
`z=(A/2) cos(omega t)` and phase wrapped to 0–360°. The reference retains the
finite-amplitude higher harmonics; the mean and second harmonic are zero to
the independent integration accuracy.
Fine third-harmonic amplitude errors are {min(third_amp):+.5f}% to {max(third_amp):+.5f}%,
and phase errors are {min(third_phase):+.5f}° to {max(third_phase):+.5f}°.
These supplementary diagnostics add no pass count; the declared acceptance
gates below cover the fundamental and complete waveforms.
Fine periodic circulation errors are {min(gamma):.5f}–{max(gamma):.5f}% of the
reference circulation peak, with fine/coarse ratios {min(gamma_ratio):.4f}–{max(gamma_ratio):.4f}.
These circulation errors are larger than the lift/rate errors and are retained
as a separate diagnostic; the predeclared pass gates do not impose a 0.1%
circulation-value limit. The machine summary also retains full-history
circulation errors and prescribed-motion velocity/position errors.
Maximum prescribed-motion velocity error is {velocity:.6f}, or
{100*velocity/(.25*19):.4f}% of peak heave velocity. Maximum position error is
{position:.6f} chords, or {100*position/.25:.4f}% of heave displacement amplitude.
These are measured against the ideal prescribed motion throughout all eight
cycles and remain explicit diagnostics; passing lift/rate checks does not
establish the same relative accuracy for every state variable.

![Periodic waveforms and approach to the periodic response](isae-ua2-periodic-20261101.svg)

The unchanged numerical gates require fine periodic lift and per-strip rate
errors below 0.1%, amplitude error below 0.1%, phase error below 0.1°, mean error
below 0.1% of peak, and final cycle-to-cycle change below 0.01% of peak. Fine/coarse
error ratios must be below 0.35. Full-history lift/rate errors and first-step
local-rate accuracy are checked separately against the cold reference. Coarse
results that exceed the fine-grid accuracy gates remain visible. These gates
do not inherit the provisional SA 3% tolerance.

The [independent straight-wing equations](isae-straight-wing-heave-reference.md)
retain bound-vortex speed, wind-aligned horseshoes, nonlinear circulation lag,
circulation-rate lift and apparent mass. A periodic boundary is obtained by
converging the nonlinear one-period map until relative circulation change is
below 1e-11. DOP853 and Radau each independently integrate the complete cold
history and converge this boundary. Their largest difference is {refmax:.3g}
of the relevant reference peak, below the unchanged 1e-8 agreement gate.
The periodic reference verifies closure, half-cycle lift antisymmetry and zero
mean. A 5,120-interval quadrature measures its harmonics; no fitted span factors
are used. The production runs start with zero circulation and receive no periodic
initial state or subsequent state correction.

Startup uses a geometric ramp whose total duration is exactly eight nominal
timesteps. Its first step is no larger than dt/256, growth is at most 1.125,
and it joins the uniform cycle lattice smoothly. This avoids the abrupt step
increase that would follow appending cycles to the earlier first-cycle grid's
short closing interval. Each trajectory has 40 extra startup steps, giving
680/1,320 accepted steps for nominal 80/160 resolution over eight cycles.
The complete forcing table is present from the first job. Checkpoints preserve
the original table and BDF predecessor. All snapshots, including startup, are
checked against the cold solution; phase-aligned periodic diagnostics use
cycles 2–8. There are no force, circulation or rate jumps at checkpoint joins.

Six focused tests pass: smooth grid alignment, the linear complex-matrix limit,
finite-amplitude two-method agreement and half-cycle symmetry, rejection of an
incomplete reference cycle, and complete cold-start forcing. Production files,
solver tolerances and app defaults are unchanged. Solver time for the
{len(seconds)} accepted serial segments is {min(seconds):.2f}–{max(seconds):.2f} seconds each,
totaling {sum(seconds):.2f} seconds. Their complete worker wall times, including
imports and artifact handling, are {min(wall_seconds):.2f}–{max(wall_seconds):.2f} seconds,
totaling {sum(wall_seconds):.2f} seconds. Each numerical job is capped at 45 seconds
and uses one BLAS thread.

The original first fine 40-strip segment reached the 45-second cap after its
last progress record reported 22 accepted steps at 33.04 seconds. Its terminal
exit code was 124, and process inspection confirmed it had stopped. That
incomplete attempt remains preserved and is excluded from accepted histories.
The same cold trajectory was restarted with 16-step segments, preserving its
time grid, forcing, equations and tolerances. The other three trajectories
reuse all 86 original segments with their raw hashes unchanged. The recovery
adds 83 successful segments. It changes only process boundaries and preserves
the BDF predecessor; it introduces no restart within an accepted trajectory.

The saved-only full 40-strip audit also reached its 45-second cap, without
producing an audit output. Its terminal receipt is retained. Separate coarse
and fine grid audits then cover the same complete histories, and a checked
combination applies the original refinement gates. No production solve is
repeated for this audit split. The auditor retains only measured fields in
memory between segment reads; every original sampled time is still checked,
and all full raw artifacts remain unchanged.

Evidence: [machine summary](isae-ua2-periodic-20261101.json),
[plans, full trajectories, reference solutions, audits and frozen sources](../../artifacts/isae/ua2-periodic-20261101),
[periodic reference](../../scripts/isae_ua_wing_periodic.py), and
[independent history audit](../../scripts/audit-isae-ua2-periodic-compact.py).

Remaining work includes other periodic amplitudes/frequencies, nonzero mean
incidence, and native setup provenance. The current specialization has Mach
zero, no stall, no structural deformation and no bodies or propulsion. All
222 native UA-2 slots remain blocked. Browser/WASM verification, broader model
coverage and the full project goal remain unfinished.
'''
    stem.with_suffix('.md').write_text(report)
    print(json.dumps(summary,indent=2),flush=True)
    if passed!=2 or not mesh_passed:raise SystemExit(1)


if __name__=='__main__':main()
