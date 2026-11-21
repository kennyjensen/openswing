"""Audit the qualified AE-3 roll sweep and retain failed refinement attempts."""
import csv
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import statistics
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.probe_isae_ae2_cold_trace import read, write, pin
from scripts.isae_suite_ae3 import _checks
from scripts.isae_acceptance import apply_reference_acceptance

OUT = ROOT / 'artifacts/isae/ae3-roll-sweep-20261111'
REFINE = ROOT / 'artifacts/isae/ae3-roll-refine-20261111'
CANDIDATE = ROOT / 'artifacts/isae/ae3-rebuild-memory-20261111'


def assess():
    assert not (OUT / 'assessment.json').exists()
    plan, refine, candidate = [read(p / 'plan.json') for p in (OUT, REFINE, CANDIDATE)]
    sources = {}
    for current in (plan, refine, candidate):
        for p in current['pins']:
            assert sources.setdefault(p['path'], p) == p
    for p in sources.values():
        assert pin(p['path']) == p, p['path']
    evidence = [pin(p / 'plan.json') for p in (OUT, REFINE, CANDIDATE)]
    physical, receipts, rows, comparisons = [], [], [], []

    def load_case(folder, current_plan, expected_success):
        terminal = read(folder / 'terminal.json')
        witness = read(folder / 'sources-verified.json')
        started = read(folder / 'started.json')
        assert terminal['process_reaped'] and terminal['limits'] == plan['limits']
        assert witness['all_pins_checked'] and witness['plan'] == pin(current_plan)
        receipt = dict(folder=str(folder), started_utc=started['observed_utc'], **terminal)
        receipts.append(receipt)
        for p in folder.iterdir():
            if p.is_file(): evidence.append(pin(p))
        if expected_success:
            assert terminal['returncode'] == 0 and not terminal['supervisor_timeout']
            report, result = read(folder / 'report.json'), read(folder / 'result.json')
            assert report['numerical_pass'] and result['converged']
            assert not result['aerodynamic_influences']['frozen']
            assert result['mach'] == 0 and not any(s['stalled'] for s in result['strips'])
            for check in report['checks']:
                assert check['passed'] and math.isfinite(check['metric']) and check['metric'] <= check['gate']
            return report, result, receipt
        return None, None, receipt

    all_cases = [(c, OUT / 'cases' / c['name'], OUT / 'plan.json') for c in plan['cases']]
    for reused in plan['reused']:
        folder = Path(reused['folder'])
        prior_plan = folder.parents[1] / 'plan.json'
        original = next(c for c in read(prior_plan)['cases'] if c['name'] == reused['name'])
        all_cases.append((original, folder, prior_plan))
    assert len(all_cases) == 12
    for case, folder, current_plan in sorted(all_cases, key=lambda x:(x[0]['job']['nominal'], x[0]['job']['native_operating_point'])):
        report, result, receipt = load_case(folder, current_plan, True)
        job = case['job']; nominal = job['nominal']; op = job['native_operating_point']
        assert len(result['strips']) == nominal+2 and len(result['equilibrium_state']['positions']) == nominal+3
        assert report['changed_distributions'] == ['dCLdF1'] and not report['exact_historical_input_recovered']
        assert report['control_change'] == plan['control_change']
        physical.extend(dict(case=case['name'], **c) for c in report['checks'])
        checks = _checks(job, report['values'])
        strict = dict(status='computed', numerical_pass=True, reference_checks=checks,
            output_accounting=dict(required=6, missing=0, passed=sum(c['passed'] for c in checks)),
            reference_match=all(c['passed'] for c in checks),
            scope='Qualified alternative only; independently checked physical result, not a primary-adapter replay.')
        view = apply_reference_acceptance(strict)
        comparisons.extend(dict(case=case['name'], **c) for c in view['reference_checks'])
        rows.append(dict(name=case['name'], operating_point=op, nominal=nominal,
            intervals=nominal+2, speed=job['condition']['speed'],
            Cl=report['values']['Cl'], native_Cl=report['native']['Cl'],
            Cl_error_percent=report['error_percent']['Cl'],
            CX=report['values']['CX'], native_CX=report['native']['CX'],
            CX_error_percent=report['error_percent']['CX'],
            passed=view['output_accounting']['passed'], required=6,
            maximum_fresh_residual=next(c['metric'] for c in report['checks'] if c['name'] == 'fresh_full_residual'),
            angular_acceleration_x=report['angular_acceleration_body'][0],
            cpu_seconds=receipt['cpu_seconds'], wall_seconds=receipt['wall_seconds'], peak_rss_kib=receipt['peak_rss_kib']))
    assert len(physical) == 132 and len(comparisons) == 72
    meshes = []
    for op in range(1, 7):
        pair = sorted((r for r in rows if r['operating_point'] == op), key=lambda r:r['nominal'])
        assert len(pair) == 2
        for channel in ('Cl', 'CX'):
            coarse, fine = (r[channel] for r in pair)
            change = 100*abs(coarse-fine)/abs(fine)
            meshes.append(dict(operating_point=op, coefficient=channel, coarse=coarse, fine=fine,
                change_percent=change, gate_percent=plan['selected_mesh_comparison_gate_percent'],
                passed=change <= plan['selected_mesh_comparison_gate_percent']))

    failure_folder = REFINE / 'cases' / refine['cases'][0]['name']
    _, _, failed = load_case(failure_folder, REFINE / 'plan.json', False)
    assert failed['returncode'] == 1 and not failed['supervisor_timeout']
    failure = (failure_folder / 'stderr.log').read_text()
    assert 'geometry_field_partials.py' in failure and 'local_geometry_matrix.py' in failure
    assert 'Unable to allocate 2.01 MiB' in failure

    control = next(c for c in candidate['cases'] if 'parity_result' in c)
    control_report, _, _ = load_case(CANDIDATE / 'cases' / control['name'], CANDIDATE / 'plan.json', True)
    parity = control_report['candidate_parity_checks']
    assert len(parity) == 9 and all(c['passed'] and c['metric'] <= c['gate'] for c in parity)
    high = next(c for c in candidate['cases'] if 'parity_result' not in c)
    high_folder = CANDIDATE / 'cases' / high['name']
    high_terminal = read(high_folder / 'terminal.json')
    high_report, high_result, high_receipt = load_case(high_folder, CANDIDATE / 'plan.json', high_terminal['returncode'] == 0)
    high_summary = dict(completed=high_report is not None, terminal=high_receipt)
    if high_report is not None:
        assert len(high_result['strips']) == 322
        high_summary.update(Cl=high_report['values']['Cl'], CX=high_report['values']['CX'],
            error_percent=high_report['error_percent'], checks=high_report['checks'],
            actual_intervals=322, changed_distributions=high_report['changed_distributions'])
    else:
        high_summary['stderr'] = (high_folder / 'stderr.log').read_text()

    modified = []
    for src in (ROOT / 'openswing').rglob('*.py'):
        relative = src.relative_to(ROOT / 'openswing')
        clone = Path(candidate['candidate_root']) / 'openswing' / relative
        if src.read_bytes() != clone.read_bytes(): modified.append(str(relative))
    assert modified == ['structured_static.py']
    rebuilt = (ROOT / 'openswing/structured_static.py').read_text()
    for before, after in candidate['changes']:
        assert rebuilt.count(before) == 1
        rebuilt = rebuilt.replace(before, after)
    assert rebuilt == (Path(candidate['candidate_root']) / 'openswing/structured_static.py').read_text()

    # Recorded numerical-worker windows must be disjoint, including retained probes.
    chronology = sorted(receipts, key=lambda r:r['started_utc'])
    for left, right in zip(chronology, chronology[1:]):
        assert datetime.fromisoformat(right['started_utc']) >= datetime.fromisoformat(left['observed_utc'])
    failures = [c for c in comparisons if not c['passed']]
    summary = dict(observed_utc=datetime.now(timezone.utc).isoformat(),
        status='QUALIFIED_ROLL_SWEEP_COMPLETE_HISTORICAL_INPUT_AND_REFINEMENT_OPEN',
        assessor=pin(Path(__file__)), source_pins=list(sources.values()), evidence=evidence,
        rows=rows, reference_comparisons=comparisons, physical_checks=physical, mesh_checks=meshes,
        qualified_comparisons_passed=sum(c['passed'] for c in comparisons), qualified_comparisons_required=72,
        qualified_failures=failures, physical_checks_passed=132,
        first_five_Cl_max_error_percent=max(r['Cl_error_percent'] for r in rows if r['operating_point'] < 6),
        first_five_Cl_median_error_percent=statistics.median(r['Cl_error_percent'] for r in rows if r['operating_point'] < 6),
        maximum_fresh_residual=max(r['maximum_fresh_residual'] for r in rows),
        original_refinement_failure=dict(receipt=failed, location='LocalGeometryMatrix.columns -> sparse slice toarray',
            allocation='2.01 MiB', classification='Resource failure; no full-load result or reference comparison'),
        candidate=dict(production_adopted=False, modified_files=modified, changes=candidate['changes'],
            control_physical_checks=control_report['checks'], control_parity_checks=parity,
            maximum_control_parity_error=max(c['metric'] for c in parity), refinement=high_summary),
        receipts=receipts, serial_worker_windows_verified=True, production_changes=False, primary_votes_added=0,
        primary_scope=dict(passed=50, required=725, computed=72, mismatches=22, uncomputed=653),
        qualification='Fixed sibling lift-control slope .0686 and conditional zero-net-roll-moment constraint. Exact historical generating input, NODE arrays and MM derivative convention remain unrecovered; these comparisons are not primary passes.',
        next_step='Finish bounded validation of Newton rebuild storage, then resolve near-reversal mesh sensitivity and the archived MM derivative convention. Keep the original model/setup and all725 primary targets distinct.')
    with (OUT / 'comparison.csv').open('x') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    write(OUT / 'assessment.json', summary)
    print(json.dumps({k:summary[k] for k in ('qualified_comparisons_passed', 'qualified_comparisons_required',
        'physical_checks_passed', 'first_five_Cl_max_error_percent', 'maximum_fresh_residual', 'primary_votes_added')}))
    print(json.dumps(dict(candidate_control_parity=summary['candidate']['maximum_control_parity_error'],
        refinement_completed=high_summary['completed'], refinement=high_summary.get('error_percent'),
        mesh_failures=[m for m in meshes if not m['passed']], failures=[dict(case=c['case'], name=c['name'],
            relative_error_percent=100*c['relative_error']) for c in failures])))


def plot():
    import resource
    import signal
    resource.setrlimit(resource.RLIMIT_AS, (512*1024**2,)*2)
    resource.setrlimit(resource.RLIMIT_CPU, (15,)*2)
    signal.alarm(25)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    summary = read(OUT / 'assessment.json')
    rows = summary['rows']; ref = [r for r in rows if r['nominal'] == 80]
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.3), constrained_layout=True)
    for ax, channel, scale, label in ((axes[0], 'Cl', 1e3, 'Cl × 1000'), (axes[1], 'CX', 1e6, 'CX × 1,000,000')):
        ax.plot([r['speed'] for r in ref], [scale*r['native_'+channel] for r in ref], 'k-o', label='Archived original ASWING')
        for nominal, color, marker in ((80, '#0072B2', 's'), (160, '#D55E00', '^')):
            subset = [r for r in rows if r['nominal'] == nominal]
            ax.plot([r['speed'] for r in subset], [scale*r[channel] for r in subset],
                    color=color, marker=marker, label=f'Qualified setup, nominal {nominal}')
        high = summary['candidate']['refinement']
        if high['completed']:
            ax.scatter([ref[-1]['speed']], [scale*high[channel]], marker='D', color='#009E73',
                       label='Isolated memory candidate, nominal 320', zorder=4)
        ax.set(xlabel='Speed (m/s)', ylabel=label)
        ax.grid(True, alpha=.25); ax.legend(fontsize=8)
    axes[0].axhline(0, color='0.6', linewidth=.7)
    axes[0].set_title('Aileron rolling response')
    axes[1].set_title('Axial-force coefficient')
    fig.suptitle('Sibling lift slope + conditional roll constraint; historical setup unconfirmed', fontsize=11)
    fig.savefig(OUT / 'comparison.png', dpi=150); plt.close(fig)
    write(OUT / 'plot-receipt.json', dict(observed_utc=datetime.now(timezone.utc).isoformat(),
        assessment=pin(OUT / 'assessment.json'), plot=pin(OUT / 'comparison.png'), new_solves=0))
    print(str(OUT / 'comparison.png'))


if __name__ == '__main__':
    {'assess': assess, 'plot': plot}[sys.argv[1]]()
