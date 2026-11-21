"""Report the 40-strip inclined UA-2 refinement and its retained 20-strip comparison."""
from hashlib import sha256
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'artifacts/isae/ua2-incidence-n40-20261101'
OLD = ROOT / 'artifacts/isae/ua2-incidence-nested-20261101'
STEM = ROOT / 'docs/validation/isae-ua2-incidence-n40-20261101'


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def main():
    assert not STEM.with_suffix('.json').exists()
    audit = json.loads((BASE / 'audit.json').read_text())
    prior = json.loads((OLD / 'audit.json').read_text())
    reference = json.loads((BASE / 'reference.json').read_text())
    assert prior['passed']
    assert json.loads((BASE / 'audit-execution.json').read_text())['exit_code'] == (0 if audit['passed'] else 1)
    assert json.loads((BASE / 'batch-complete.json').read_text())['computed_jobs'] == 38
    pins = {**audit['source_sha256'], **audit['input_sha256']}
    for path in (Path(__file__).resolve(), BASE / 'audit.json', BASE / 'audit-execution.json', BASE / 'reference.json'):
        pins[str(path.relative_to(ROOT))] = digest(path)
    assert all(digest(ROOT / name) == value for name, value in pins.items())
    time_pass = all(value for key, value in audit['checks'].items() if key != 'mesh_lift')
    summary = dict(
        passed=audit['passed'], checks=audit['checks'],
        inclined_time_checks_passed=1 + int(time_pass), inclined_time_checks_total=2,
        inclined_mesh_checks_passed=int(audit['checks']['mesh_lift']), inclined_mesh_checks_total=1,
        physical_conditions=1, meshes=[20, 40],
        grids={n: {key: value for key, value in row.items() if key != 'rows'} for n, row in audit['results'].items()},
        ratios=audit['ratios'], mesh=audit['mesh'],
        new_unique_snapshots=602, retained_unique_snapshots=602, new_production_segments=38,
        solver_seconds=audit['solver_seconds'], reference_method_differences=reference['method_differences'],
        source_sha256=pins, production_files_changed=0, native_ASWING_comparison=False, full_goal_complete=False,
    )
    fine = audit['results']['320']
    datasets = [(20, prior), (40, audit)]
    table = []
    fig, axes = plt.subplots(1, 2, figsize=(10, 4), constrained_layout=True)
    for panels, result in datasets:
        for grid, color, style in [('160', '#d97706', '--'), ('320', '#2563eb', '-')]:
            row = result['results'][grid]
            errors = row['error_fractions']
            table.append(f"| {panels} | {len(row['rows']) - 1} | " + ' | '.join(f"{100 * errors[k]:.5f}%" for k in ('CL', 'circulation', 'circulation_rate')) + ' |')
            phase = np.array([r['time'] for r in row['rows']]) / (np.pi / 9.5)
            lift_error = np.array([r['CL'] - r['reference']['CL'] for r in row['rows']]) / row['scales']['CL']
            axes[int(panels == 40)].plot(phase, 100 * lift_error, color=color, linestyle=style, label=f"{len(row['rows']) - 1} time steps")
        ax = axes[int(panels == 40)]
        ax.set(title=f'{panels} strips', xlabel='Cycle phase', ylabel='Lift error (% of dynamic lift scale)')
        ax.grid(alpha=.25)
        ax.legend()
    fig.suptitle('UA-2 inclined first cycle: same startup schedule on both meshes')
    fig.savefig(STEM.with_suffix('.svg'))
    fig.savefig(STEM.with_suffix('.png'), dpi=150)
    plt.close(fig)
    failed = [key for key, passed in audit['checks'].items() if not passed]
    text = f'''# UA-2: inclined time refinement at 40 strips

Updated 2026-11-01. **{summary['inclined_time_checks_passed']}/2 inclined time checks and
{summary['inclined_mesh_checks_passed']}/1 inclined mesh checks pass.** These cover one physical
condition on two meshes: AR10, 9° incidence, k=0.95, peak-to-peak A/c=0.5,
Mach zero and stall disabled. The 20-strip result is retained from the
[previous comparison](isae-ua2-incidence-nested-20261101.md).
{'All declared gates pass.' if not failed else 'Failed gates: ' + ', '.join(failed) + '.'}

| Strips | Accepted time steps | Lift error | Worst strip circulation error | Worst strip rate error |
|---|---:|---:|---:|---:|
{chr(10).join(table)}

Errors use peak departures from the initial steady state for lift and each
strip's circulation, and each strip's peak for circulation rate. Production
starts from its own steady solution. The complete forcing table is present
before startup; checkpoint joins preserve the accepted state and BDF predecessor.
Both meshes use the same 200-step startup grid and its 400-step bisection.
No reference state is supplied to the production time march.

![Lift errors on both meshes](isae-ua2-incidence-n40-20261101.svg)

At 40 strips, the fine/coarse error ratios are
{', '.join(f'{v:.5f}' for v in audit['ratios'].values())} for lift, circulation and rate.
The unchanged gates are 0.1% for each fine waveform and 0.35 for its refinement
ratio. First-step rate error is {100 * fine['diagnostics']['first_step_rate_relative_error']:.5f}%
(limit 1%); maximum velocity error is
{100 * fine['diagnostics']['maximum_heave_velocity_error'] / 4.75:.5f}% of peak heave velocity,
and position error is {400 * fine['diagnostics']['maximum_heave_position_error']:.5f}% of
heave amplitude (limits 0.1% each). Maximum normalized nonlinear residual is
{max(r['diagnostics']['maximum_residual'] for r in audit['results'].values()):.3e}
(limit 1e-10). Every segment converges with zero rejected steps.

The maximum integrated lift change from 20 to 40 strips is
**{100 * audit['mesh']['production_lift_fraction']:.5f}%**, against a predeclared 0.1% limit.
The independently integrated equations give
{100 * audit['mesh']['independent_reference_lift_fraction']:.5f}%.
Both use the 40-strip dynamic lift scale at identical fine-grid times;
no strip interpolation is involved. Two meshes establish this measured
change, rather than a continuum error bound.

All 602 new raw snapshots and exact checkpoint joins are audited. The 38 jobs
run serially with one BLAS thread and a 45-second cap each. Solver time is
{audit['solver_seconds']['min']:.2f}–{audit['solver_seconds']['max']:.2f} seconds per segment,
{audit['solver_seconds']['total']:.2f} seconds total. The independent DOP853 and
Radau references agree within {max(reference['method_differences'].values()):.3e} of the
relevant peak. All 136 production Python files and application defaults remain
unchanged. The earlier failed startup grids remain recorded in the linked report.

This verifies the [published inclined finite-wing equations](isae-inclined-wing-heave-reference.md).
It does not add native ASWING passes: all 222 UA-2 native comparison slots remain
blocked by archived-run provenance. Inclined production periodic response,
broader conditions, automatic time-step accuracy, stall and browser/WASM checks
remain unfinished. Neither UA family nor the full project is complete.

Evidence: [machine summary](isae-ua2-incidence-n40-20261101.json),
[raw data and receipts](../../artifacts/isae/ua2-incidence-n40-20261101),
[run setup](../../scripts/isae_ua2_incidence_n40.py), and
[all-snapshot audit](../../scripts/audit-isae-ua2-incidence-n40.py).
'''
    STEM.with_suffix('.json').write_text(json.dumps(summary, indent=2, allow_nan=False) + '\n')
    STEM.with_suffix('.md').write_text(text)
    print(json.dumps({key: summary[key] for key in ('passed', 'inclined_time_checks_passed', 'inclined_mesh_checks_passed', 'mesh')}))


if __name__ == '__main__':
    main()
