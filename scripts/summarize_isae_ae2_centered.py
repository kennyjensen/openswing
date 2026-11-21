"""Audit saved AE-2 derivative diagnostics and plot them without another solve."""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'artifacts/isae'


def read(path):
    return json.loads(Path(path).read_text())


def audit(out):
    assert not out.exists(), 'Preserve earlier observations.'
    checked = {}

    def pin(path):
        path = Path(path)
        if not path.is_absolute():
            path = ROOT / path
        path = path.resolve()
        if str(path) not in checked:
            checked[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
        return dict(path=str(path), sha256=checked[str(path)])

    def validate(item):
        if isinstance(item, dict):
            if 'path' in item and 'sha256' in item:
                assert pin(item['path'])['sha256'] == item['sha256'], item['path']
            for value in item.values():
                validate(value)
        elif isinstance(item, list):
            for value in item:
                validate(value)

    processes = []
    roots = [BASE / ('ae2-' + name + '-20261110') for name in (
        'stalled-tangent', 'stalled-replay', 'stalled-saved',
        'stalled-direction', 'stalled-blocks', 'centered-tangent',
        'centered-incidence', 'centered-refined', 'centered-near275')]
    for root in roots:
        plan = read(root / 'plan.json')
        validate(plan)
        for file in sorted(root.rglob('terminal.json')):
            terminal = read(file)
            proof = read(file.with_name('sources-verified.json'))
            assert terminal['process_reaped'] and not terminal['supervisor_timeout']
            assert proof['all_pins_checked_before_and_after']
            assert proof['plan'] == pin(root / 'plan.json')
            assert proof['terminal'] == pin(file)
            processes.append(dict(path=str(file.relative_to(ROOT)), **terminal))

    previous = read(BASE / 'ae2-incidence-staged-audit-20261110/assessment.json')
    validate(previous)
    old_matrix = read(BASE / 'ae2-stalled-saved-20261110/assessment.json')
    validate(old_matrix)
    direction = read(BASE / 'ae2-stalled-direction-20261110/assessment.json')
    blocks = read(BASE / 'ae2-stalled-blocks-20261110/assessment.json')
    validate(blocks)
    centered = read(BASE / 'ae2-centered-tangent-20261110/assessment.json')
    validate(centered)
    assert centered['status'] == 'DIRECTIONAL_GATE_PASS'
    assert old_matrix['status'] == 'TANGENTS_DIFFER'
    assert all(not d['accepted_state'] and d['primary_votes_added'] == 0
               for d in (old_matrix, direction, blocks, centered))
    records = []
    for root in roots[-3:]:
        plan = read(root / 'plan.json')
        for case in plan['cases']:
            folder = root / case['name']
            record = dict(run=str(root.relative_to(ROOT)), **case)
            terminal = folder / 'solve/terminal.json'
            if not terminal.exists():
                record['status'] = 'UNSTARTED'
            elif read(terminal)['returncode'] != 0:
                assert not (folder / 'result.json').exists()
                record['status'] = 'FAILED_EXECUTION'
                events = [json.loads(line) for line in
                          (folder / 'solve/progress.jsonl').read_text().splitlines()]
                errors = [e['total'] for e in events if e['stage'] == 'equilibrium_iteration']
                record['last_iteration_residual'] = errors[-1]
            else:
                for phase in ('solve', 'tangent', 'verify'):
                    assert read(folder / phase / 'terminal.json')['returncode'] == 0
                report = read(folder / 'report.json')
                validate(report)
                result = read(folder / 'result.json')
                seed = (root / case['predecessor'] / 'result.json'
                        if case['predecessor'] else Path(plan['seed_result']))
                expected = deepcopy(plan['base_request'])
                expected['condition']['beta'] = case['beta']
                expected['tolerance'] = plan['physical_residual_gate']
                expected['initial_state'] = read(seed)['equilibrium_state']
                assert read(folder / 'request.json') == expected
                assert report['seed'] == pin(seed)
                assert result['converged'] and result['residual'] <= 1e-12
                pending = read(folder / 'candidate.json')
                validate(pending)
                assert pending['status'] == 'PENDING_VERIFICATION' and pending['accepted'] is False
                tangent = read(folder / 'tangent.json')
                validate(tangent)
                assert tangent['status'] == 'COMPLETE_CENTERED_FINAL_TANGENT'
                assert tangent['shape'] == [2105, 2105]
                assert result['diagnostic_stages']['pending'] == pin(folder / 'candidate.json')
                assert result['diagnostic_stages']['final_tangent'] == pin(folder / 'tangent.json')
                assert report['status'] == 'VERIFIED_WARM_EQUILIBRIUM'
                assert report['fresh_residual'] <= 1e-12
                assert len(report['checks']) == (19 if case['predecessor'] else 21)
                assert all(check['passed'] for check in report['checks'])
                record.update(status='VERIFIED_DIAGNOSTIC', values=report['values'],
                    physical_checks=len(report['checks']), residual=report['fresh_residual'],
                    newton=pending['newton'], control=report['control'],
                    rank=result['equilibrium_initialization'])
            records.append(record)
    accepted = [r for r in records if r['status'] == 'VERIFIED_DIAGNOSTIC']
    assessment = dict(observed_utc=datetime.now(timezone.utc).isoformat(),
        status='AUDITED_DIAGNOSTIC_BRANCH_INCOMPLETE', records=records,
        prior_branch=previous, matrix_comparison=old_matrix,
        directional=direction, blocks=blocks, centered=centered,
        processes=processes, supervised_processes=len(processes),
        failed_processes=sum(p['returncode'] != 0 for p in processes),
        all_processes_reaped=True, physical_checks=sum(r['physical_checks'] for r in accepted),
        reached_beta=max(r['beta'] for r in accepted), reached_beta5=False,
        maximum_full_residual=max(r['residual'] for r in accepted),
        primary_passed=708, primary_required=2200, primary_votes_added=0,
        qualifications=[
            'Saved-only audit; no equilibrium is computed by this script.',
            'Derivative and continuation settings are diagnostic; production sources are unchanged.',
            'Intermediate incidences have no paired archived native values and add no votes.',
            'Two capture failures and both centered 2.75-degree solve failures remain recorded.',
            'Neither derivative accuracy nor incomplete continuation establishes branch uniqueness or stability.'])
    for path in [Path(__file__), BASE / 'ae2-incidence-staged-audit-20261110/assessment.json']:
        pin(path)
    for root in roots:
        for path in root.rglob('*.json'):
            pin(path)
        for path in root.rglob('*.log'):
            pin(path)
        for path in root.rglob('*.jsonl'):
            pin(path)
    assessment['pins'] = [dict(path=p, sha256=s) for p, s in sorted(checked.items())]
    out.mkdir()
    (out / 'assessment.json').write_text(json.dumps(assessment, indent=2) + '\n')
    print(json.dumps({k: assessment[k] for k in ('status', 'physical_checks',
        'reached_beta', 'maximum_full_residual', 'supervised_processes', 'failed_processes',
        'primary_votes_added')}), flush=True)


def plot(out):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    data = read(out / 'assessment.json')
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.6), constrained_layout=True)
    ax = axes[0]
    for record, color, label in [
            (data['directional']['records'][1], '#d97706', 'Original forward geometry'),
            (data['centered'], '#2563eb', 'Centered complete geometry')]:
        ax.loglog([p['step'] for p in record['probes']],
                  [100*p['relative_l2_error'] for p in record['probes']],
                  'o-', color=color, label=label)
    ax.axhline(.01, color='gray', ls='--', label='Declared centered gate')
    ax.set(xlabel='Independent directional FD step', ylabel='Directional derivative error (%)',
           title='Captured unconverged 2.75° trial')
    ax.legend(fontsize=8)
    ax = axes[1]
    original = data['matrix_comparison']['probe']['trials']
    for trials, color, label in [
            ([p for p in original if p['method'] == 'stencil'], '#d97706', 'Original forward'),
            (data['centered']['trials'], '#2563eb', 'Centered')]:
        ax.semilogy([p['power'] for p in trials], [p['ratio'] for p in trials],
                    'o-', color=color, label=label)
    ax.axhline(1, color='gray', ls='--')
    ax.axvspan(8.5, 12.5, alpha=.08, color='black', label='Outside original search')
    ax.set(xlabel='Halvings of Newton step (step = 2⁻ᵏ)', ylabel='Trial / baseline max residual',
           title='Same trial, physical residual evaluations', xlim=(-.3, 12.4))
    ax.legend(fontsize=8)
    ax = axes[2]
    prior = [r for r in data['prior_branch']['records'] if r['status'] == 'VERIFIED_DIAGNOSTIC']
    added = [r for r in data['records'] if r['status'] == 'VERIFIED_DIAGNOSTIC']
    ax.plot([r['beta'] for r in prior], [r['values']['RY_m'] for r in prior],
            'o-', color='gray', label='Earlier verified branch')
    ax.plot([r['beta'] for r in added], [r['values']['RY_m'] for r in added],
            'o-', color='#2563eb', label='Centered diagnostic')
    native = data['prior_branch']['native']
    # The native rows are plotted at their actual commanded conditions.
    for row in native:
        beta = row['beta_deg']
        ax.plot(beta, row['values']['RY_m'], 'k*', ms=12,
                label='Archived ASWING' if beta == 1 else None)
    ax.plot(5, data['prior_branch']['cold_beta5_values']['RY_m'], 'x',
            color='#d97706', ms=9, label='Original cold start')
    ax.set(xlabel='Commanded beta (degrees)', ylabel='Sensor Earth Y (m)',
           title='IAS 17 m/s, negative coupling, nominal 160')
    ax.legend(fontsize=8)
    for ax in axes:
        ax.grid(True, which='major', alpha=.3)
        ax.grid(True, which='minor', alpha=.1)
    fig.suptitle('AE-2: derivative accuracy improves; native mismatch remains open', fontsize=13)
    for extension in ('png', 'svg'):
        path = out / ('derivatives-and-branch.' + extension)
        assert not path.exists()
        fig.savefig(path, dpi=150)
    plt.close(fig)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['audit', 'plot'])
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    globals()[args.action](args.output.resolve())
