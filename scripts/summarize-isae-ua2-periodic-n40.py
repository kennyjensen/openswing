"""Report the audited UA-2 periodic spatial study without adding test gates."""
from hashlib import sha256
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'artifacts/isae/ua2-incidence-periodic-n40-20261101'
STEM = ROOT / 'docs/validation/isae-ua2-incidence-periodic-n40-20261101'


def digest(path):
    result = sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


def main():
    assert not STEM.with_suffix('.json').exists()
    audit = json.loads((BASE / 'audit.json').read_text())
    receipt = json.loads((BASE / 'audit-execution.json').read_text())
    plan = json.loads((BASE / 'production-plan.json').read_text())
    completion = json.loads((BASE / 'production-complete.json').read_text())
    reference = json.loads((BASE / 'reference-verified.json').read_text())
    periodic = json.loads((BASE / 'periodic-reference.json').read_text())
    baseline = json.loads((BASE / 'baseline-n20.json').read_text())
    assert receipt['exit_code'] == (0 if audit['passed'] else 1)
    assert receipt['report_sha256'] == digest(BASE / 'audit.json')
    assert completion['computed_jobs'] == len(plan['jobs']) == 330
    assert audit['audited_unique_snapshots'] == 5281
    assert audit['comparison_baseline_snapshots'] == 5281
    assert len(audit['checks']) == 18
    assert all(digest(ROOT / name) == value for name, value in plan['source_sha256'].items())
    pins = {str(path.relative_to(ROOT)): digest(path) for path in (
        Path(__file__).resolve(), BASE / 'audit.json', BASE / 'audit-execution.json',
        BASE / 'production-plan.json', BASE / 'production-complete.json',
        BASE / 'reference-verified.json', BASE / 'periodic-reference.json',
        BASE / 'baseline-n20.json')}
    final = audit['cycles'][-1]
    failed = [name for name, passed in audit['checks'].items() if not passed]
    summary = dict(
        passed=audit['passed'], checks=audit['checks'],
        inclined_periodic_cases_passed=int(audit['periodic_case_passed']),
        inclined_periodic_cases_total=1,
        inclined_periodic_mesh_checks_passed=int(audit['mesh_check_passed']),
        inclined_periodic_mesh_checks_total=1,
        panels=40, baseline_panels=20, cycles=8, alpha_deg=9,
        reduced_frequency=.95, peak_to_peak_amplitude_ratio=.5,
        nominal_steps_per_cycle=640,
        cold_error_fractions=audit['cold_error_fractions'],
        periodic_error_fractions=final['error_fractions'],
        fundamental=final['harmonic_errors'][0],
        mean_CL_error_dynamic_fraction=final['mean_CL_error_dynamic_fraction'],
        last_cycle_change_fractions=final['cycle_change_fractions'],
        diagnostics=audit['diagnostics'], mesh=audit['mesh'],
        audited_unique_snapshots=audit['audited_unique_snapshots'],
        comparison_baseline_snapshots=audit['comparison_baseline_snapshots'],
        completed_production_jobs=completion['computed_jobs'], raw_audit_chunks=42,
        solver_seconds=audit['solver_seconds'],
        reference_method_differences=reference['method_differences'],
        input_sha256=pins, production_changed=False,
        new_temporal_refinement_claim=False, native_ASWING_comparison=False,
        full_goal_complete=False)

    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np

    new_rows = audit['rows'][-641:]
    old_rows = baseline['cold'][-641:]
    reference_rows = periodic['rows']
    phase = np.arange(641) / 640
    scale = audit['periodic_scales']['CL']
    lift = np.array([r['CL'] for r in new_rows])
    old_lift = np.array([r['CL'] for r in old_rows])
    ref_lift = np.array([r['CL'] for r in reference_rows])
    old_ref = np.array([r['CL'] for r in baseline['periodic_reference']])
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.2), constrained_layout=True)
    axes[0].plot(phase, 100 * (lift - ref_lift) / scale, color='#2563eb')
    axes[0].set(title='40-strip lift error, eighth cycle', xlabel='Cycle phase',
                ylabel='% of 40-strip periodic lift scale')
    axes[1].plot(phase, 100 * (lift - old_lift) / scale, color='#2563eb', label='Production, cycle 8')
    axes[1].plot(phase, 100 * (ref_lift - old_ref) / scale, color='#d97706',
                 linestyle='--', label='Independent periodic references')
    axes[1].set(title='Lift change from 20 to 40 strips', xlabel='Cycle phase',
                ylabel='% of 40-strip periodic lift scale')
    axes[1].legend(fontsize=8)
    for ax in axes:
        ax.grid(alpha=.25)
    fig.suptitle('UA-2: fixed time grid, 640 nominal steps/cycle\nAR10, 9°, k=0.95, peak-to-peak A/c=0.5')
    fig.savefig(STEM.with_suffix('.svg'))
    fig.savefig(STEM.with_suffix('.png'), dpi=150)
    plt.close(fig)

    error_table = '\n'.join(
        f"| {label} | {100*audit['cold_error_fractions'][key]:.6f}% | "
        f"{100*final['error_fractions'][key]:.6f}% |"
        for key, label in (('CL', 'Lift'), ('circulation', 'Worst strip circulation'),
                           ('circulation_rate', 'Worst strip circulation rate')))
    mesh_table = '\n'.join(
        f"| {label} | {100*audit['mesh'][key+'_production_lift_fraction']:.6f}% | "
        f"{100*audit['mesh'][key+'_reference_lift_fraction']:.6f}% |"
        for key, label in (('cold', 'Full cold history'), ('periodic', 'Eighth cycle / periodic reference')))
    d = audit['diagnostics']
    text = f'''# UA-2: inclined periodic spatial refinement to 40 strips

Updated 2026-11-01. **{int(audit['periodic_case_passed'])}/1 new inclined periodic cases
and {int(audit['mesh_check_passed'])}/1 periodic mesh checks pass.**
{sum(audit['checks'].values())}/18 predeclared gates pass.
{'All gates pass.' if not failed else 'Failed gates: '+', '.join(failed)+'.'}
The reconstructed rigid AR10 wing uses 9° incidence, k=0.95, peak-to-peak
A/c=0.5, Mach zero and disabled stall. This compares independently integrated
published equations; the 222 native ASWING slots remain blocked by archived-run
provenance.

| Quantity | Full cold-history error | Eighth-cycle periodic error |
|---|---:|---:|
{error_table}

| Mesh comparison | Production lift change, 20 to 40 strips | Independent reference change |
|---|---:|---:|
{mesh_table}

Errors use the 40-strip reference scales: departures from the initial steady
state for the cold history, and from the periodic mean for periodic lift and
circulation. Each strip has its own scale. Rate scales are their respective
peak absolute rates. Both mesh gates retain the existing 0.1% limit.
Only integrated fixed-axis lift is compared between meshes; strip states are
not interpolated.

![Periodic accuracy and spatial refinement](isae-ua2-incidence-periodic-n40-20261101.svg)

The time grid is exactly the fine grid from the
[20-strip study](isae-ua2-incidence-periodic-20261101.md): 640 nominal steps/cycle
with refined startup, 5,280 physical steps over eight cycles. Production starts
from its own steady equilibrium with the complete forcing table present.
All 330 serial jobs preserve the accepted state and BDF predecessor; every
checkpoint join and all 5,281 unique snapshots are audited in 42 bounded batches.
The first physical step is first order, followed by variable-step BDF2.
This is a spatial refinement at fixed temporal resolution. It makes no new
40-strip temporal-order claim. Time-refinement evidence remains in the preceding
20-strip periodic and [40-strip first-cycle](isae-ua2-incidence-n40-20261101.md) studies.

The fundamental lift amplitude error is
{100*final['harmonic_errors'][0]['amplitude_error_fraction']:.6f}%, phase error
{final['harmonic_errors'][0]['phase_error_deg']:.6f}°, and mean-lift error
{100*final['mean_CL_error_dynamic_fraction']:.6f}% of the periodic dynamic scale.
The largest seventh-to-eighth-cycle change is
{100*max(final['cycle_change_fractions'].values()):.6f}%.
First-step rate error is {100*d['first_step_rate_relative_error']:.6f}% of that
sample's reference rate. Maximum velocity and position errors are
{100*d['maximum_heave_velocity_error']/4.75:.6f}% of peak velocity and
{400*d['maximum_heave_position_error']:.6f}% of heave amplitude.
The largest normalized nonlinear residual is {d['maximum_residual']:.3e}.

The 16 applicable single-grid gates are unchanged: 0.1% for cold and periodic
lift/circulation/rate waveforms, amplitude, dynamic-scale mean lift and motion;
0.1° phase; 0.01% cycle change; 1% first-step rate; and 1e-10 normalized residual.
The two additional mesh gates use 0.1%. No failed check is removed or retuned.

Independent DOP853 and Radau integrations agree within
{max(reference['method_differences'].values()):.3e} of the relevant peak, below
the unchanged 1e-8 agreement limit. Both use relative/absolute tolerances
1e-13/1e-15. Their exact samples are used without time interpolation.
The [inclined-wing derivation](isae-inclined-wing-heave-reference.md) is unchanged.

All completed production jobs converge without rejected steps. Each uses one
BLAS thread and a 45-second cap. Recorded solver time is
{audit['solver_seconds']['min']:.2f}–{audit['solver_seconds']['max']:.2f} seconds per
16-step segment, {audit['solver_seconds']['total']:.2f} seconds summed across jobs.
These timings include repeated setup; they are not an uninterrupted-run benchmark.
No production code, equation, application default or acceptance limit changed
in this spatial study. The earlier endpoint repair remains in place.

Broader frequency/incidence/amplitude coverage, full periodic browser validation,
arbitrary-model time-step accuracy and native ASWING provenance remain unfinished.
The existing [built-browser checkpoint replay](isae-ua2-time-endpoint-wasm-20261101.md)
covers one continuation step. Neither UA family nor the full project is complete.

Evidence: [machine summary](isae-ua2-incidence-periodic-n40-20261101.json),
[raw audit](../../artifacts/isae/ua2-incidence-periodic-n40-20261101/audit.json),
[predeclared plan](../../artifacts/isae/ua2-incidence-periodic-n40-20261101/production-plan.json),
[reference verification](../../artifacts/isae/ua2-incidence-periodic-n40-20261101/reference-verified.json),
[serial runner](../../scripts/run-isae-ua2-periodic-n40.py), and
[auditor](../../scripts/audit-isae-ua2-periodic-n40.py).
'''
    STEM.with_suffix('.json').write_text(json.dumps(summary, indent=2, allow_nan=False) + '\n')
    STEM.with_suffix('.md').write_text(text)
    print(json.dumps(dict(passed=audit['passed'], checks_passed=sum(audit['checks'].values()),
                          failed_gates=failed, periodic_errors=final['error_fractions'], mesh=audit['mesh'])))


if __name__ == '__main__':
    main()
