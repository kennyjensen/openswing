"""Record completed UA-1 browser accuracy without changing native-ASWING counts."""
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'artifacts/isae/ua1-incidence-periodic-browser-20261102-r1'
DOC = ROOT / 'docs/validation/isae-ua1-incidence-periodic-browser-20261102.md'


def digest(path):
    h = sha256()
    with path.open('rb') as stream:
        while block := stream.read(1024 * 1024):
            h.update(block)
    return h.hexdigest()


def main():
    assert not DOC.exists() and not DOC.with_suffix('.json').exists(), 'Preserve completed summary'
    read = lambda name: json.loads((BASE / name).read_text())
    audit, plan = read('audit.json'), read('plan.json')
    execution = read('audit-execution.json')
    assert execution['exit_code'] == 0 and execution['report_sha256'] == digest(BASE / 'audit.json')
    assert audit['passed'] and all(audit['checks'].values()) and len(audit['checks']) == 14
    assert audit['audited_unique_snapshots'] == 2561
    assert read('pilot-execution.json')['exit_code'] == read('production-execution.json')['exit_code'] == 0
    assert read('production-complete.json')['computed_jobs'] == 128
    pins = {**audit['source_sha256'], **audit['input_sha256']}
    for name, value in pins.items():
        assert digest(ROOT / name) == value, name
    reports = []
    for job in plan['jobs']:
        folder = BASE / 'production' / f'part{job["part"]:03d}'
        receipt = json.loads((folder / 'receipt.json').read_text())
        assert receipt['outcome'] == 'success' and receipt['job'] == job
        for name, value in receipt['output_sha256'].items():
            assert digest(folder / name) == value
        report = json.loads((folder / 'report.json').read_text())
        assert report['accepted_steps'] == 20 and report['rejected_steps'] == 0
        reports.append(report)
    runtimes = [r['worker_seconds'] for r in reports]
    final, diagnostics = audit['cycles'][-1], audit['diagnostics']
    gates = plan['gates']
    table = '\n'.join(f"| {label} | {100*audit['cold_error_fractions'][key]:.5f}% | {100*final['error_fractions'][key]:.5f}% | 0.1% |"
                      for key, label in [('CL', 'Lift'), ('circulation', 'Circulation'), ('circulation_rate', 'Circulation rate')])
    source_pins = {name: value for name, value in plan['source_sha256'].items() if name.startswith('openswing/')}
    assert len(source_pins) == 136
    for name, value in source_pins.items():
        for folder in ['public/kernel', 'dist/kernel']:
            assert digest(ROOT / folder / Path(name).name) == value
    outcomes = [json.loads(p.read_text()) for p in sorted((BASE / 'runs').glob('*/outcome.json'))]
    browsers = [json.loads(p.read_text()) for p in sorted((BASE / 'runs').glob('*/browser.json'))]
    warmups = [json.loads(p.read_text()) for p in sorted((BASE / 'runs').glob('*/warmup.json'))]
    assert len(warmups) == len(outcomes)
    original = ROOT / 'artifacts/isae/ua1-incidence-periodic-browser-20261102'
    failed = json.loads((original / 'production-execution.json').read_text())
    assert failed['exit_code'] == 1
    for name in ['pilot-execution.json', 'production-execution.json', 'plan.json']:
        pins[str((original / name).relative_to(ROOT))] = digest(original / name)
    assert sum(x['new_jobs'] for x in outcomes) == 128 and all(x['success'] for x in outcomes)
    assert all(not x['browser_errors'] for x in outcomes)
    tests = read('focused-tests-execution.json')
    assert tests['exit_code'] == 0
    test_results = read('focused-tests-results.json')
    assert test_results['passed_tests'] == tests['passed_tests']
    assert test_results['exit_code'] == 0 and test_results['serial']
    for item in test_results['receipts']:
        assert item['exit_code'] == 0 and item['failed_tests'] == 0
        assert digest(BASE / f"focused-{item['name']}-tests.xml") == item['junit_sha256']
    for path in [BASE / 'focused-tests-attempt01-execution.json', BASE / 'focused-tests-execution.json',
                 BASE / 'focused-tests-results.json', ROOT / 'scripts/run-isae-ua1-browser-focused-tests.py']:
        pins[str(path.relative_to(ROOT))] = digest(path)
    summary = dict(passed=True, updated_utc=datetime.now(timezone.utc).isoformat(),
                   browser_periodic_checks_passed=1, browser_periodic_checks_total=1,
                   checks=audit['checks'], gates=gates, cold_error_fractions=audit['cold_error_fractions'],
                   final_cycle=final, diagnostics=diagnostics, snapshots=2561, accepted_steps=2560,
                   rejected_steps=0, serial_segments=128, steps_per_segment=20,
                   worker_seconds=dict(min=min(runtimes), max=max(runtimes), sum=sum(runtimes)),
                   runs=outcomes, browsers=browsers, warmups=warmups, original_failed_attempt=failed, focused_tests=tests,
                   retained_CPython_kernel_changes=plan['retained_CPython_kernel_changes'],
                   source_sha256={**pins, str(Path(__file__).resolve().relative_to(ROOT)): digest(Path(__file__).resolve())},
                   production_changed=False, native_ASWING_comparison=False,
                   full_history_UI_validation=False, new_temporal_refinement_claim=False, full_goal_complete=False)
    DOC.with_suffix('.json').write_text(json.dumps(summary, indent=2) + '\n')
    DOC.write_text(f'''# UA-1: inclined periodic calculation in the built browser worker

Updated 2026-11-02. **1/1 browser periodic check passes**, with all **14 accuracy
and runtime gates passing**. The actual distributed worker computes eight
continuous cycles at 9°, k=0.94, peak-to-peak A/c=0.5 and 320 steps/cycle.
All **2,561 unique snapshots** are audited; all **2,560 steps** converge with
zero rejected steps. No production code or numerical tolerance changes in this
increment. This verifies an existing physical case in WASM; it adds no new
frequency, amplitude, mesh-refinement or native-ASWING comparison pass.

| Quantity | Full cold-history error | Final periodic-cycle error | Limit |
|---|---:|---:|---:|
{table}

Errors use dynamic variation, not the nonzero steady mean: lift and circulation
are normalized by peak departures from their reference means in the periodic
cycle, and from the steady initial value for the cold history. Rate uses its
reference peak. Every strip participates. The independent target is the
[published section-equation reference](isae-inclined-section-heave-reference.md),
using integrating-factor quadrature and the exact homogeneous startup transient.
Its separate direct DOP853 check and original acceptance limits remain intact.
The provisional 3% steady-aerodynamics allowance is not used.

Fundamental amplitude error is **{100*final['harmonic_errors'][0]['amplitude_error_fraction']:+.5f}%**;
phase error is **{final['harmonic_errors'][0]['phase_error_deg']:+.5f}°**. Mean-lift
error is **{100*final['mean_CL_error_dynamic_fraction']:+.6f}%** of dynamic lift
variation. Maximum final cycle-to-cycle change is
**{100*max(final['cycle_change_fractions'].values()):.6f}%**, below 0.01%.
Maximum normalized nonlinear residual is **{diagnostics['maximum_residual']:.4e}**,
below 1e-10. First-step rate and motion errors remain diagnostics with the same
definitions as the native study; no easier limits are introduced.

## Runtime and retained-history verification

The built worker loads its own Pyodide, NumPy/SciPy and 136 packaged solver
modules. Their exact bytes and runtime provenance are recorded. It starts from
its own production steady equilibrium, with the complete forcing table present
from startup. The independent reference is never supplied as an initial state.
There are 128 serial requests of 20 steps, each capped at 45 seconds. Both BDF
predecessors survive continuation. The final forcing cutoff correctly clears
next-step history while retaining the complete accepted BDF2 method record.
The audit checks those records, coefficients, force axes, all circulation/rate
values, frame motion, times, solver orders and exact checkpoint joins.

Request times are **{min(runtimes):.2f}–{max(runtimes):.2f} seconds**;
their sum is {sum(runtimes):.2f} seconds. Runtime/model inspection is a separate request capped at 45 seconds before
the first solve in each worker lifetime. Its timings are recorded separately. This is a segmented validation measurement,
not an uninterrupted solve benchmark or full application UI timing.
Chromium {browsers[0]['version']} reports no page errors.

Maximum scaled difference from the retained CPython calculation is
**{diagnostics['maximum_CPython_scaled_difference']:.4e}**, below 2e-8.
That historical calculation predates the separately verified
[forcing-endpoint rounding repair](isae-ua2-time-endpoint-fix-20261101.md).
Exactly one module, `forcing.py`, differs; the other 135 match. Both versions
are pinned, and the old frozen source and outputs are preserved. This is
agreement with the retained earlier Python result; it is not described as a
comparison of identical source versions. The browser also independently passes
the unchanged waveform, amplitude, phase, mean, settling and residual gates.

The first preparation attempt caught that source difference and started no
solver. A second prepared plan was superseded before execution when pre-run
review caught an obsolete assumption about terminal continuation history.
Both preparations remain recorded. The original 40-step browser pilot passed,
but its first resumed request exceeded the combined startup/solve deadline.
That failed batch remains separate. This fresh study starts from production
equilibrium again, separates runtime loading, and uses smaller 20-step requests
on the identical physical time grid. Its pilot and all remaining browser
requests finish successfully. {tests['passed_tests']} focused setup, reference,
endpoint and checkpoint-verifier tests pass.
The initial combined regression command reached its 90-second shell limit;
that incomplete attempt is preserved. All selected tests subsequently finish
in separate serial jobs, each with a 60-second limit and an individual result.

## Remaining scope

This uses four circulation unknowns and AR200000 to approximate the 2D section;
finite-tip effects remain. It closes the browser-runtime gap for one refined
inclined periodic case. Broader frequencies/amplitudes/incidences, stall,
arbitrary-model timestep accuracy and native UA-2 reference provenance remain
unfinished. The earlier 160-step circulation failure remains recorded, and
neither UA family nor the full project is complete. The workbench/archive
checks from the [UA-2 follow-up](isae-ua2-archive-ui-20261102.md) remain separate.

Evidence: [machine report](isae-ua1-incidence-periodic-browser-20261102.json),
[plan and source pins](../../artifacts/isae/ua1-incidence-periodic-browser-20261102-r1/plan.json),
[full-history audit](../../artifacts/isae/ua1-incidence-periodic-browser-20261102-r1/audit.json),
[producer receipt](../../artifacts/isae/ua1-incidence-periodic-browser-20261102-r1/production-execution.json),
[audit receipt](../../artifacts/isae/ua1-incidence-periodic-browser-20261102-r1/audit-execution.json),
[runner](../../scripts/run-isae-ua1-periodic-browser-r1.mjs),
[audit](../../scripts/audit-isae-ua1-periodic-browser-r1.py).
''')
    paragraph = (f'The [UA-1 built-worker check](docs/validation/{DOC.name}) now passes **1/1 browser periodic checks and all 14 gates** '
                 'at 9°, k=.94, A/c=.5 and 320 steps/cycle. All **2,561 snapshots** are audited; '
                 '2,560 steps converge without rejection. Periodic lift/circulation/rate errors are '
                 + ' / '.join(f"**{100*final['error_fractions'][key]:.5f}%**" for key in ['CL', 'circulation', 'circulation_rate'])
                 + f'; maximum scaled difference from the retained Python result is **{diagnostics["maximum_CPython_scaled_difference"]:.3e}**. '
                 'The historical forcing-endpoint source difference is explicitly pinned. This adds runtime coverage for the existing case; '
                 'broader physical conditions, stall and native reference provenance remain unfinished.')
    status = ROOT / 'docs/validation/ISAE_STATUS.md'
    text = status.read_text()
    assert paragraph not in text
    text = text.replace('Current priority is [UA-1 and UA-2]', paragraph + '\n\nCurrent priority is [UA-1 and UA-2]', 1)
    text = text.replace('All 32 new serial segments converge without rejected steps. Broader conditions,\nstall and browser/WASM validation remain unfinished.',
                        'All 32 new serial segments converge without rejected steps. The browser follow-up\nabove now verifies this same refined case. Broader conditions and stall remain unfinished.', 1)
    lines = text.splitlines()
    i = next(i for i, line in enumerate(lines) if line.startswith('| [UA-1]'))
    lines[i] = lines[i].replace('1/1 inclined periodic checks pass', '1/1 inclined periodic; 1/1 browser periodic checks pass')
    lines[i] = lines[i].replace('Broader conditions, stall and browser/WASM validation remain unfinished.',
        f'The built browser worker now passes all 14 gates for the same refined eight-cycle case, with 2,561 snapshots audited and maximum scaled retained-Python difference {diagnostics["maximum_CPython_scaled_difference"]:.3e}. Broader conditions, stall and native reference provenance remain unfinished.')
    text = '\n'.join(lines) + '\n'
    other = lambda text: [line for line in text.splitlines() if re.match(r'\| \[?[A-Z]+-\d+', line) and not line.startswith('| [UA-1]')]
    assert other(text) == other((BASE / 'status-before.md').read_text()) and len(other(text)) == 41
    status.write_text(text)
    status = ROOT / 'docs/STATUS.md'
    text = status.read_text().replace('# Current implementation record\n', '# Current implementation record\n\n' + paragraph.replace('docs/validation/', 'validation/') + '\n', 1)
    text = text.replace('Broader incidence/frequency/amplitude coverage, stall, native reference\nprovenance and browser/WASM verification remain unfinished.',
                        'The browser follow-up above now verifies this same refined case. Broader\nincidence/frequency/amplitude coverage, stall and native reference provenance remain unfinished.', 1)
    status.write_text(text)
    backlog = ROOT / 'docs/validation/isae-suite-backlog.md'
    lines = backlog.read_text().splitlines()
    i = next(i for i, line in enumerate(lines) if '**UA-1**' in line and line.startswith('|'))
    lines[i] = lines[i].replace('Native provenance and browser/WASM validation remain unresolved.', 'Native provenance remains unresolved.')
    lines[i] = lines[i].rstrip().removesuffix('|').rstrip() + f' The [built-worker follow-up]({DOC.name}) closes runtime coverage for the refined 9° case: 14/14 gates, 2,561 states and zero rejected steps. Broader physical conditions and stall remain. |'
    backlog.write_text('\n'.join(lines) + '\n')
    print(json.dumps(dict(passed=True, runtime_checks=1, gates=14, snapshots=2561,
                          scientific_modules_unchanged=136, other_ISAE_rows_preserved=41)))


if __name__ == '__main__':
    main()
