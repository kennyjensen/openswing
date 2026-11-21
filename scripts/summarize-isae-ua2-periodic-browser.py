"""Render the completed built-worker audit, retaining its exact scope and gates."""
from hashlib import sha256
import json
from pathlib import Path
from isae_ua2_browser_cutoff import assessment_sources

ROOT = Path(__file__).resolve().parents[1]
ORIGINAL = ROOT / 'artifacts/isae/ua2-incidence-periodic-browser-20261101'
BASE = ORIGINAL / 'assessment'
STEM = ROOT / 'docs/validation/isae-ua2-incidence-periodic-browser-20261101'


def digest(path):
    result = sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


def main():
    assert not STEM.with_suffix('.json').exists(), 'Preserve an existing final report'
    audit = json.loads((BASE / 'audit.json').read_text())
    receipt = json.loads((BASE / 'audit-execution.json').read_text())
    plan = json.loads((BASE / 'plan.json').read_text())
    completion = json.loads((BASE / 'production-complete.json').read_text())
    assert receipt['exit_code'] == (0 if audit['passed'] else 1)
    assert receipt['report_sha256'] == digest(BASE / 'audit.json')
    assert completion['computed_jobs'] == len(plan['jobs']) == 330
    assert audit['audited_unique_snapshots'] == 5281 and len(audit['checks']) == 17
    assert not audit['native_ASWING_comparison'] and not audit['full_history_UI_validation']
    assert all(digest(ROOT / name) == value for name, value in plan['source_sha256'].items())
    input_pins = {str(path.relative_to(ROOT)): digest(path) for path in (
        Path(__file__).resolve(), BASE / 'audit.json', BASE / 'audit-execution.json',
        BASE / 'plan.json', BASE / 'production-complete.json', BASE / 'periodic-reference.json')}
    input_pins.update(assessment_sources(BASE, ROOT))
    assert audit['original_producer_exit_code'] == 1 and audit['terminal_cutoff_reassessment']
    final_rows, baseline_rows, durations, wall_times, run_ids = [], [], [], [], set()
    provenance = None
    for job in plan['jobs']:
        part = job['part']
        folder = BASE / 'production' / f'part{part:03d}'
        record_path, report_path = folder / 'receipt.json', folder / 'report.json'
        record = json.loads(record_path.read_text())
        report = json.loads(report_path.read_text())
        assert record['outcome'] == 'success' and record['job'] == report['job'] == job
        assert report['accepted_steps'] == 16 and report['rejected_steps'] == 0
        assert digest(report_path) == record['output_sha256']['report.json']
        assert report['software_provenance']['fingerprint'] == audit['fingerprint']
        if provenance is not None:
            assert provenance == report['software_provenance']
        provenance = report['software_provenance']
        if report['worker_seconds'] is not None:
            durations.append(report['worker_seconds'])
        wall_times.append(record['wall_seconds'])
        run_ids.add(record['run_id'])
        for path in (record_path, report_path):
            key = str(path.relative_to(ROOT))
            value = digest(path)
            assert audit['source_sha256'][key] == value
            input_pins[key] = value
        if part >= 290:
            target_path = BASE / plan['targets'][part]['path']
            assert digest(target_path) == plan['targets'][part]['sha256']
            target = json.loads(target_path.read_text())
            start = 0 if part == 290 else 1
            final_rows.extend(report['rows'][start:])
            baseline_rows.extend(target['rows'][start:])
            input_pins[str(target_path.relative_to(ROOT))] = digest(target_path)
    assert len(final_rows) == len(baseline_rows) == 641
    assert provenance is not None and len(provenance['modules']) == 136
    assert digest(BASE / 'periodic-reference.json') == plan['periodic_reference_sha256']
    periodic = json.loads((BASE / 'periodic-reference.json').read_text())
    final = audit['cycles'][-1]
    failed = [name for name, passed in audit['checks'].items() if not passed]
    summary = dict(passed=audit['passed'], checks=audit['checks'],
        browser_periodic_checks_passed=int(audit['passed']), browser_periodic_checks_total=1,
        panels=20, cycles=8, alpha_deg=9, reduced_frequency=.95, peak_to_peak_amplitude_ratio=.5,
        nominal_steps_per_cycle=640, cold_error_fractions=audit['cold_error_fractions'],
        periodic_error_fractions=final['error_fractions'], fundamental=final['harmonic_errors'][0],
        mean_CL_error_dynamic_fraction=final['mean_CL_error_dynamic_fraction'],
        last_cycle_change_fractions=final['cycle_change_fractions'], diagnostics=audit['diagnostics'],
        audited_unique_snapshots=5281, completed_requests=330, accepted_steps=5280, rejected_steps=0,
        raw_audit_batches=42, runner_invocations=len(run_ids),
        worker_seconds=dict(min=min(durations), max=max(durations), total=sum(durations),
            recorded_requests=len(durations), unknown_requests=330-len(durations)),
        original_producer_exit_code=1, original_successful_requests=329,
        reassessed_requests=1, numerical_reexecution=False,
        request_wall_seconds_total=sum(wall_times), software_provenance=provenance,
        input_sha256=input_pins, production_changed=False,
        full_periodic_browser_validation=audit['passed'], full_history_UI_validation=False,
        new_temporal_refinement_claim=False, native_ASWING_comparison=False, full_goal_complete=False)

    memory_text = ''
    memory_path = BASE / 'memory-observations.jsonl'
    if memory_path.exists():
        observations = [json.loads(line) for line in memory_path.read_text().splitlines()]
        measured = [row for row in observations if row.get('complete_pss_measurement')]
        input_pins[str(memory_path.relative_to(ROOT))] = digest(memory_path)
        summary['memory_observations'] = dict(
            completed_samples=len(measured), unavailable_samples=len(observations)-len(measured),
            samples=[{key: row[key] for key in (
                'observed_utc', 'completed_requests', 'process_count', 'summed_pss_mib',
                'summed_swap_pss_mib') if key in row}
                for row in measured],
            measured_peak=False, full_history_UI_measurement=False)
        if measured:
            low = min(row['summed_pss_mib'] for row in measured)/1024
            high = max(row['summed_pss_mib'] for row in measured)/1024
            first = min(row['completed_requests'] for row in measured)
            last = max(row['completed_requests'] for row in measured)
            memory_text = f'''
{len(measured)} successful process-tree memory samples, taken after
{first}–{last} requests, measured **{low:.2f}–{high:.2f} GiB** of proportional
resident memory (PSS) for Chromium and the test driver together. PSS allocates
shared pages proportionally across processes. These intermittent observations
are not a measured peak, a memory-leak test or a full-history UI measurement.
The [raw memory observations](../../artifacts/isae/ua2-incidence-periodic-browser-20261101/memory-observations.jsonl)
retain unsuccessful sampling attempts separately; missing measurements are
excluded from the range.
'''
            swap_samples = [row for row in measured if 'summed_swap_pss_mib' in row]
            if swap_samples:
                latest = swap_samples[-1]
                memory_text += f'''
The sample after {latest['completed_requests']} requests also measured
{latest['summed_swap_pss_mib']/1024:.2f} GiB of proportional swapped pages.
The resident-memory figures above exclude swapped pages.
'''

    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np

    phase = np.array([row['time'] for row in periodic['rows']])
    for rows in (final_rows, baseline_rows):
        np.testing.assert_allclose(np.array([r['time'] for r in rows]) - 7*plan['period'], phase, rtol=0, atol=1e-12)
    scale = plan['baseline_fine_summary']['periodic_scales']['CL']
    target_lift = np.array([row['CL'] for row in periodic['rows']])
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.2), constrained_layout=True)
    for rows, cycles, color, style, label in (
        (final_rows, audit['cycles'], '#2563eb', '-', 'Built browser worker'),
        (baseline_rows, plan['baseline_fine_summary']['cycles'], '#d97706', '--', 'CPython baseline')):
        lift = np.array([row['CL'] for row in rows])
        axes[0].plot(phase/plan['period'], 100*(lift-target_lift)/scale, color=color, linestyle=style, label=label)
        settled = [c for c in cycles if c['cycle_change_fractions'] is not None]
        axes[1].semilogy([c['cycle'] for c in settled],
            [100*max(c['cycle_change_fractions'].values()) for c in settled],
            color=color, linestyle=style, marker='o', label=label)
    axes[0].set(title='Eighth-cycle lift error', xlabel='Cycle phase', ylabel='% of reference periodic lift scale')
    axes[1].set(title='Largest change from preceding cycle', xlabel='Cycle', ylabel='% of corresponding reference scale')
    axes[1].axhline(.01, color='.5', linestyle=':', label='Settling limit: 0.01%')
    for ax in axes:
        ax.grid(alpha=.25, which='both')
        ax.legend(fontsize=8)
    fig.suptitle('UA-2: built worker and CPython on the same time grid\nAR10, 20 strips, 9°, k=0.95, peak-to-peak A/c=0.5')
    fig.savefig(STEM.with_suffix('.svg'))
    fig.savefig(STEM.with_suffix('.png'), dpi=150)
    plt.close(fig)
    error_table = '\n'.join(
        f"| {label} | {100*audit['cold_error_fractions'][key]:.6f}% | {100*final['error_fractions'][key]:.6f}% |"
        for key, label in (('CL', 'Lift'), ('circulation', 'Worst strip circulation'), ('circulation_rate', 'Worst strip circulation rate')))
    d = audit['diagnostics']
    text = f'''# UA-2: built-browser inclined periodic comparison

Updated 2026-11-01. **{int(audit['passed'])}/1 full-period built-worker checks pass.**
{sum(audit['checks'].values())}/17 declared gates pass.
{'All gates pass.' if not failed else 'Failed gates: '+', '.join(failed)+'.'}
This covers the actual built app worker through eight cycles on a reconstructed
rigid AR10 wing: 20 strips, 9° incidence, k=0.95, peak-to-peak A/c=0.5,
Mach zero and disabled stall. Native ASWING provenance remains unresolved;
the 222 native comparison slots remain blocked.

| Quantity | Full cold-history error | Eighth-cycle periodic error |
|---|---:|---:|
{error_table}

The maximum scaled difference from the completed CPython trajectory is
**{d['maximum_CPython_scaled_difference']:.3e}**, below 2e-8. Compared fields are
fixed-axis lift, all force coefficients, per-strip circulation/rate and projected
heave velocity/position/acceleration. Each difference is normalized by
`max(1, abs(CPython value))`. The comparison uses identical times, without interpolation.

![Browser accuracy and settling](isae-ua2-incidence-periodic-browser-20261101.svg)

Production starts from its own browser-computed steady equilibrium with the
complete forcing table present. No reference or CPython state seeds production.
All **5,280 physical steps** and **5,281 unique snapshots** are retained.
The 330 serial 16-step requests preserve their full accepted state and BDF
history across every continuation join. At the final forcing cutoff, the
accepted BDF2 record retains both prior states while the history for a future
continuation is cleared. A passing startup pilot precedes the full runner; a new browser
invocation resumes the saved browser checkpoint. The worker persists between
requests within each invocation. Each worker request has a 45-second cap.
All numerical requests converge with no rejected steps. The original producer
exits 1 after its final solve because it incorrectly requires continuation
history at the forcing cutoff. Its 329 successful request receipts and the
[failed final receipt](../../artifacts/isae/ua2-incidence-periodic-browser-20261101/production/part329/receipt.json)
remain intact. A separate assessment verifies the retained final output without
recomputing any trajectory. It requires the exact terminal cutoff, the left-side
endpoint, cleared continuation history, and both prior states and coefficients
of the accepted BDF2 step. The Python baseline has the same cutoff behavior.
The original assertion is corrected only in this assessment and audit; all
physical accuracy gates are unchanged. Forty-two bounded raw-audit
batches verify every reported quantity, saved checkpoint and join before
the combined accuracy calculation.

The first physical step is BDF1, followed by documented variable-step BDF2.
The grid has 640 nominal steps/cycle and refined startup, exactly matching the
[CPython study](isae-ua2-incidence-periodic-20261101.md). This verifies the browser
runtime on that grid; it makes no new temporal-order or spatial-refinement claim.
The [40-strip CPython spatial study](isae-ua2-incidence-periodic-n40-20261101.md)
provides the separate mesh comparison.

Periodic fundamental lift amplitude error is
{100*final['harmonic_errors'][0]['amplitude_error_fraction']:.6f}%, phase error
{final['harmonic_errors'][0]['phase_error_deg']:.6f}°, and mean-lift error
{100*final['mean_CL_error_dynamic_fraction']:.6f}% of the periodic dynamic scale.
The largest seventh-to-eighth-cycle change is
{100*max(final['cycle_change_fractions'].values()):.6f}%.
First-step rate error is {100*d['first_step_rate_relative_error']:.6f}% of that
sample's continuous reference rate. Maximum velocity and position errors are
{100*d['maximum_heave_velocity_error']/4.75:.6f}% of peak heave velocity and
{400*d['maximum_heave_position_error']:.6f}% of heave amplitude.
The largest normalized nonlinear residual is {d['maximum_residual']:.3e}.

Sixteen applicable physical accuracy gates are unchanged from the CPython
study: 0.1% for each cold/periodic lift, circulation and rate waveform;
0.1% for amplitude, dynamic-scale mean and motion; 0.1° phase; 0.01% cycle
change; 1% first-step rate; and 1e-10 nonlinear residual. The seventeenth gate
checks CPython agreement. Cold scales use departures from initial steady;
periodic lift/circulation scales use departures from their periodic means.
Every strip has its own scale. Rate scales use peak absolute rates. The
previously verified DOP853/Radau references and their limits are unchanged.

All 136 loaded solver modules match the pinned source. The actual runtime is
Pyodide {provenance['runtime']['pyodide']}, Python {provenance['runtime']['python']},
NumPy {provenance['runtime']['numpy']} and SciPy {provenance['runtime']['scipy']}.
The same source/runtime fingerprint is retained across all requests.
Recorded worker time is {min(durations):.2f}–{max(durations):.2f} seconds per
request, {sum(durations):.2f} seconds summed over the {len(durations)} requests
with recorded worker timings. The final request has no saved worker timing
because the original assertion preceded that report write; its retained wall
time includes output processing. There are
{len(run_ids)} runner invocations. Each invocation's first request includes
runtime initialization; every request includes checkpoint restoration and
result transport. These are bounded-validation timings, not an uninterrupted
solve benchmark. No production code, physical equation, default or acceptance
limit changed during this browser study.
{memory_text}

The worker uses the app's lossless compact transport. The validation harness
saves one segment at a time to bound resident history. It therefore does
**not** establish that the full trajectory can be retained, plotted and
manipulated in the UI on a phone. Full-history UI memory/rendering, broader
conditions, arbitrary-model time-step accuracy and native ASWING provenance
remain unfinished. Neither UA family nor the full project is complete.

Evidence: [machine summary](isae-ua2-incidence-periodic-browser-20261101.json),
[raw audit](../../artifacts/isae/ua2-incidence-periodic-browser-20261101/assessment/audit.json),
[cutoff assessment](../../artifacts/isae/ua2-incidence-periodic-browser-20261101/assessment/assessment.json),
[original producer exit](../../artifacts/isae/ua2-incidence-periodic-browser-20261101/production-execution.json),
[frozen plan](../../artifacts/isae/ua2-incidence-periodic-browser-20261101/plan.json),
[pilot verification](../../artifacts/isae/ua2-incidence-periodic-browser-20261101/pilot-verification.json),
[built-worker runner](../../scripts/run-isae-ua2-periodic-browser.mjs),
[auditor](../../scripts/audit-isae-ua2-periodic-browser-cutoff.py), and
[serial audit supervisor](../../scripts/run-isae-ua2-periodic-browser-cutoff-audits.py).
'''
    STEM.with_suffix('.json').write_text(json.dumps(summary, indent=2, allow_nan=False)+'\n')
    STEM.with_suffix('.md').write_text(text)
    print(json.dumps(dict(passed=audit['passed'], gates_passed=sum(audit['checks'].values()),
        failed_gates=failed, periodic_errors=final['error_fractions'],
        maximum_CPython_scaled_difference=d['maximum_CPython_scaled_difference'])))


if __name__ == '__main__':
    main()
