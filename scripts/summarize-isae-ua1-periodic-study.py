"""Publish one completed parameterized UA-1 study without changing other cases."""
import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    value = sha256()
    with path.open('rb') as stream:
        while block := stream.read(1024*1024):
            value.update(block)
    return value.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', type=Path, required=True)
    parser.add_argument('--document', required=True)
    args = parser.parse_args()
    base = args.base.resolve()
    assert base.is_relative_to(ROOT/'artifacts/isae')
    assert re.fullmatch(r'isae-ua1-[a-z0-9-]+', args.document)
    document = ROOT/'docs/validation'/(args.document+'.md')
    assert not document.exists() and not document.with_suffix('.json').exists(), 'Preserve completed report'
    read = lambda path: json.loads(path.read_text())
    plan, audit = read(base/'plan.json'), read(base/'audit.json')
    receipts = {name: read(base/(name+'-execution.json')) for name in ['prepare', 'adoption', 'pilot', 'production', 'audits', 'combine']}
    assert all(value['exit_code'] == 0 for name, value in receipts.items() if name != 'combine')
    assert receipts['combine']['exit_code'] == (0 if audit['passed'] else 1)
    assert len(audit['checks']) == 14 and audit['passed'] == all(audit['checks'].values())
    tests_dir = ROOT/'artifacts/isae/ua1-periodic-study-preparation-20261102'
    tests = read(tests_dir/'tests-attempt03-execution.json')
    boundary_tests = read(tests_dir/'boundary-tests-execution.json')
    diagnostic = read(tests_dir/'restart-diagnostic-execution.json')
    assert tests['exit_code'] == diagnostic['exit_code'] == 0 and tests['passed_tests'] == 11
    assert boundary_tests['exit_code'] == 0 and boundary_tests['passed_tests'] == 5
    test_count = tests['passed_tests']+boundary_tests['passed_tests']
    pins = {**audit['source_sha256'], **audit['input_sha256']}
    for path in [base/'audit.json', *[base/(name+'-execution.json') for name in receipts],
                 tests_dir/'tests-attempt03-execution.json', tests_dir/'tests-attempt03.xml',
                 tests_dir/'boundary-tests-execution.json', tests_dir/'boundary-tests.xml',
                 tests_dir/'restart-diagnostic-execution.json', tests_dir/'restart-diagnostic/report.json',
                 base.parent/'a5-k047-A05/pilot-execution.json', Path(__file__).resolve()]:
        pins[str(path.relative_to(ROOT))] = digest(path)
    for name, value in pins.items():
        assert digest(ROOT/name) == value, name
    science = {name: value for name, value in plan['source_sha256'].items() if name.startswith('openswing/')}
    assert len(science) == 136
    for name, value in science.items():
        for folder in ['public/kernel', 'dist/kernel']:
            assert digest(ROOT/folder/Path(name).name) == value
    grids = plan['grids']
    expected = sum(plan['case']['cycles']*steps+1 for steps in grids)
    assert audit['audited_unique_snapshots'] == expected
    jobs = sum(plan['case']['cycles']*steps//plan['segment_steps'] for steps in grids)
    assert read(base/'production-complete.json')['completed_jobs'] == jobs
    assert audit['boundary_history_checks'] == jobs-len(grids)
    case = plan['case']
    coarse, fine = [audit['results'][str(n)] for n in grids]
    final = fine['cycles'][-1]
    errors = final['error_fractions']
    names = [('CL', 'Lift'), ('circulation', 'Circulation'), ('circulation_rate', 'Circulation rate')]
    table = '\n'.join(f"| {label} | {100*coarse['cycles'][-1]['error_fractions'][key]:.5f}% | {100*errors[key]:.5f}% | 0.1% |"
                      for key, label in names)
    cold = ' / '.join(f"{100*fine['cold_error_fractions'][key]:.5f}%" for key, _ in names)
    ratios = [value for group in audit['fine_to_coarse_ratios'].values() for value in group.values()]
    checks = '\n'.join(f"| {name} | {'Pass' if value else 'Fail'} |" for name, value in audit['checks'].items())
    reference = read(base/'reference.json')
    ref_error = max(value for group in reference['comparisons'].values() for value in group['error_fractions'].values())
    rounding = audit['restart_scale_roundoff']
    max_ulps = max((r['difference_in_ulps'] for r in rounding), default=0)
    verdict = 'passes' if audit['passed'] else 'does not pass'
    passed_gates = sum(audit['checks'].values())
    updated = datetime.now(timezone.utc).date().isoformat()
    paragraph = (f'The [additional UA-1 periodic study](docs/validation/{document.name}) **{verdict} overall**, with **{passed_gates}/14 gates passing** '
        f'at {case["alpha_deg"]:g}°, k={case["k"]:g}, peak-to-peak A/c={case["amplitude_ratio"]:g}, with {grids[0]}/{grids[1]} steps per cycle. '
        f'All **{expected:,} states** across two eight-cycle histories are audited. Fine periodic lift/circulation/rate errors are '
        + ' / '.join(f'**{100*errors[key]:.5f}%**' for key, _ in names)
        + f'. The initial checkpoint-verifier failure was isolated to one-ULP dimensional internal-moment rounding; the corrected audit limits only scale-converted internal fields to four ULPs and keeps other state fields exact. '
        f'All {test_count} setup/audit tests pass. Production equations and physical accuracy limits are unchanged. This adds a physical condition in CPython; browser coverage for it, broader conditions, stall and native-ASWING agreement remain unfinished.')
    summary = dict(**audit, report_source_sha256=pins, reference_comparisons=reference['comparisons'],
        focused_tests=tests, boundary_tests=boundary_tests, total_focused_tests=test_count,
        restart_diagnostic=diagnostic, terminal_executions=receipts,
        current_condition_passes=int(audit['passed']), current_condition_total=1,
        updated_utc=datetime.now(timezone.utc).isoformat(), full_goal_complete=False)
    document.with_suffix('.json').write_text(json.dumps(summary, indent=2)+'\n')
    document.write_text(f'''# UA-1: nonlinear periodic heave at {case['alpha_deg']:g}°, k={case['k']:g}

Updated {updated}. This additional physical condition **{verdict} overall**, with
**{passed_gates}/14 accuracy and refinement gates passing**. It uses the published UA-1 mean-incidence and
frequency labels, with peak-to-peak A/c={case['amplitude_ratio']:g}. The existing
linear source-curve comparison remains separate. This study checks the full
nonlinear attached-flow response against independently integrated section
equations; it is not native ASWING executable output.

| Quantity | {grids[0]} steps/cycle: periodic error | {grids[1]} steps/cycle: periodic error | Fine limit |
|---|---:|---:|---:|
{table}

Fine full cold-history errors are **{cold}** for lift, circulation and rate.
Errors use oscillatory variation: the cold history is measured from the
pre-motion steady value, and the periodic lift/circulation from their periodic
means. Rate uses its reference peak. Every strip participates; no strip average
or nonzero mean can hide an error. All three cold and periodic limits remain
0.1%. The provisional SA 3% policy does not apply.

The fine/coarse error ratios range from **{min(ratios):.5f} to {max(ratios):.5f}**;
each must be below 0.35. Fundamental lift-amplitude error is
**{100*final['harmonic_errors'][0]['amplitude_error_fraction']:+.5f}%** and phase
error is **{final['harmonic_errors'][0]['phase_error_deg']:+.5f}°**. Mean lift
error is **{100*final['mean_CL_error_dynamic_fraction']:+.6f}%** of dynamic lift.
The maximum final cycle-to-cycle change is
**{100*max(final['cycle_change_fractions'].values()):.6f}%**, against 0.01%.
Maximum residual over both grids is
**{max(coarse['diagnostics']['maximum_residual'], fine['diagnostics']['maximum_residual']):.4e}**.

| Gate | Result |
|---|---|
{checks}

## Physical setup and independent reference

The rigid unit-chord rectangular model has AR200000 and four circulation
unknowns. Mean speed is {case['speed']:g}, Mach is zero, gravity is zero, and
stall is disabled. Heave follows the fixed mean-freestream normal, including
the corresponding body-X and body-Z accelerations. Lift is projected onto that
same fixed normal and normalized by the fixed mean dynamic pressure.

Both production histories start from their own steady equilibrium and continue
for eight cycles. The complete acceleration table is supplied before startup.
No reference circulation or periodic initial condition initializes production.
The reference uses one-period integrating-factor quadrature plus the exact
homogeneous transient from the steady initial circulation. Independent direct
DOP853 and Radau integrations cover the entire cold history. Their largest
normalized disagreement is **{ref_error:.4e}**, below 1e-9. A separate 512-interval
quadrature changes the mean and first three lift amplitudes by at most
**{reference['maximum_harmonic_quadrature_change']:.4e}**.

The general setup reproduces the previous 9°, k=.94 request and reference
exactly. The new tests also check changed physical parameters, transient
continuity and detection of a discrepancy confined to one strip. An initial
setup test's bitwise endpoint-clock assertion was corrected to the already
declared 1e-12 clock tolerance; no physical acceptance limit changed.

## Continuation and retained evidence

There are {jobs} retained segments of {plan['segment_steps']} steps each, all run
serially with a 45-second cap per numerical subprocess and one BLAS thread.
Every complete snapshot is retained. Separate bounded readers audit all
**{expected:,} unique states** on both grids, including exact force, frame-motion,
circulation and rate joins, integration order, endpoint BDF coefficients,
accepted predecessors, full forcing cutoff and source hashes.

The original second-segment verifier rejected two internal moments that changed
by one ULP when restored from physical units into solver-scaled units and then
recaptured. A separate two-step reproduction retained the complete result and
isolated those fields; all compared aerodynamic and frame outputs were exact.
The corrected verifier allows at most four ULPs only in dimensional internal
force, internal moment and reaction fields. All remaining restart-state fields
remain exact. Deliberately changing circulation by one ULP or an internal moment
by sixteen ULPs fails its tests. The complete audit observes a maximum of
**{max_ulps:g} ULPs** in the allowed fields. This is validation-tool rounding
handling, not a solver or physical-accuracy relaxation.

The failed pilot and its frozen source remain intact. Its successful initial
segment is reused byte for byte after checking identical physical requests and
all 136 production-module hashes. No solve is repeated for that retained
segment. The failed second segment's output was not published before the old
assertion; the resumed study computes that interval and the remaining history.
All accepted segments converge without rejected integration steps. {test_count}
focused tests pass. The final report retains all source and input hashes.

The first full-history reader also incorrectly treated the duplicate initial
record of a resumed segment as a newly integrated step. Its display order is
zero, while its accepted-method record preserves BDF2. The original audit
failure remains recorded. The corrected reader checks both physical BDF
predecessors and the first continued step's coefficients at all
**{audit['boundary_history_checks']} boundaries**, then excludes only the already
checked duplicate from new-step order assertions. Five targeted tests cover
valid continuation and reject lost history, an Euler restart, altered
circulation and incorrect coefficients.
This reassessment reads the retained trajectories and performs no new solve.

## Remaining scope

This adds one physical condition and its temporal-refinement evidence. It does
not add spatial convergence, stall, a browser run of this condition or native
ASWING agreement. The earlier 9°, k=.94 browser and temporal studies retain
their own counts and qualifications. Other frequency/incidence/amplitude
combinations and UA-2 native-reference provenance remain open. Neither UA
family nor the full project is complete.

Evidence: [machine report]({document.with_suffix('.json').name}),
[plan](../../{base.relative_to(ROOT)}/plan.json),
[full-history audit](../../{base.relative_to(ROOT)}/audit.json),
[parameterized study](../../scripts/isae_ua1_periodic_study.py),
[corrected history reader](../../scripts/audit-isae-ua1-periodic-study.py),
[serial runner](../../scripts/run-isae-ua1-periodic-study.py).
''')
    status = ROOT/'docs/validation/ISAE_STATUS.md'
    text = status.read_text()
    pending = 'The additional UA-1 nonlinear periodic study at 5°, k=0.47 is in progress. Its independent reference and 11 setup/audit tests pass; full production-history and refinement acceptance remain pending. No new physical-condition pass is counted yet.\n\n'
    text = text.replace(pending, '')
    text = text.replace('Current priority is [UA-1 and UA-2]', paragraph+'\n\nCurrent priority is [UA-1 and UA-2]', 1)
    lines = text.splitlines()
    i = next(i for i, line in enumerate(lines) if line.startswith('| [UA-1]'))
    match = re.search(r'(\d+)/(\d+) inclined periodic', lines[i])
    assert match
    a, b = map(int, match.groups())
    lines[i] = lines[i][:match.start()]+f'{a+int(audit["passed"])}/{b+1} inclined periodic'+lines[i][match.end():]
    columns = lines[i].split('|')
    columns[4] += f' New {case["alpha_deg"]:g}°, k={case["k"]:g} fine periodic errors: '+', '.join(f'{100*errors[key]:.5f}%' for key, _ in names)+f'; {passed_gates}/14 gates pass. '
    columns[5] += f' The [additional condition](docs/validation/{document.name}) audits {expected:,} states on {grids[0]}/{grids[1]} steps/cycle with unchanged physical limits. Its browser coverage remains pending. '
    lines[i] = '|'.join(columns)
    updated_text = '\n'.join(lines)+'\n'
    others = lambda text: [line for line in text.splitlines() if re.match(r'\| \[?[A-Z]+-\d+', line) and not line.startswith('| [UA-1]')]
    assert others(updated_text) == others((base/'status-before.md').read_text()) and len(others(updated_text)) == 41
    status.write_text(updated_text)
    path = ROOT/'docs/STATUS.md'
    path.write_text(path.read_text().replace('# Current implementation record\n', '# Current implementation record\n\n'+paragraph.replace('docs/validation/', 'validation/')+'\n', 1))
    path = ROOT/'docs/validation/isae-suite-backlog.md'
    lines = path.read_text().splitlines()
    i = next(i for i, line in enumerate(lines) if line.startswith('|') and '**UA-1**' in line)
    lines[i] = lines[i].replace('Extend periodic frequencies/amplitudes and 5° production histories.', 'Extend remaining periodic frequencies/amplitudes and 5° histories at k=.94.')
    lines[i] = lines[i].rstrip().removesuffix('|').rstrip()+f' The [{case["alpha_deg"]:g}°, k={case["k"]:g} study]({document.name}) has {passed_gates}/14 gates passing on two time grids and {verdict} overall; {expected:,} states audited. Browser coverage of this condition remains pending. |'
    path.write_text('\n'.join(lines)+'\n')
    print(json.dumps(dict(passed=audit['passed'], gates_passed=passed_gates, audited_states=expected,
                         inclined_conditions_passed=a+int(audit['passed']), inclined_conditions_total=b+1,
                         unchanged_scientific_modules=136, other_ISAE_rows_preserved=41)), flush=True)


if __name__ == '__main__':
    main()
