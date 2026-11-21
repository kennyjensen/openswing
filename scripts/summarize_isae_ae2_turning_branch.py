"""Saved-only audit of AE-2's later tangent, backtracking and paired equilibria."""
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
    assert not out.exists()
    hashes = {}

    def pin(path):
        p = Path(path)
        p = (p if p.is_absolute() else ROOT / p).resolve()
        if str(p) not in hashes:
            hashes[str(p)] = hashlib.sha256(p.read_bytes()).hexdigest()
        return dict(path=str(p), sha256=hashes[str(p)])

    def validate(value):
        if isinstance(value, dict):
            if 'path' in value and 'sha256' in value:
                assert pin(value['path'])['sha256'] == value['sha256'], value['path']
            for v in value.values():
                validate(v)
        elif isinstance(value, list):
            for v in value:
                validate(v)

    roots = [BASE / ('ae2-' + name + '-20261110') for name in (
        'later-centered', 'extended-search', 'deflection-0202',
        'deflection-trace-0202', 'deflection-trace-0210', 'double-root')]
    processes = []
    for root in roots:
        plan = read(root / 'plan.json')
        validate(plan)
        for path in root.rglob('terminal.json'):
            terminal = read(path)
            proof = read(path.with_name('sources-verified.json'))
            assert terminal['process_reaped'] and not terminal['supervisor_timeout']
            assert proof['all_pins_checked_before_and_after']
            assert proof['plan'] == pin(root / 'plan.json') and proof['terminal'] == pin(path)
            processes.append(dict(path=str(path.relative_to(ROOT)), **terminal))
        for suffix in ('*.json', '*.log', '*.jsonl'):
            for path in root.rglob(suffix):
                pin(path)
    later = read(roots[0] / 'assessment.json')
    capture = read(roots[0] / 'capture/report.json')
    validate(later)
    validate(capture)
    assert later['status'] == 'DIRECTIONAL_GATE_PASS' and later['accepted_state'] is False
    assert capture['accepted'] is False and capture['maximum_history_absolute_difference'] == 0
    extended = read(roots[1] / 'assessment.json')
    validate(extended)
    assert extended['status'] == 'DIAGNOSTIC_ITERATIONS_COMPLETE'
    assert not extended['accepted_equilibrium'] and not extended['converged_candidate']
    records = []
    folders = [roots[3], roots[4], roots[5] / 'lower']
    for folder in folders:
        root = folder if (folder / 'plan.json').exists() else folder.parent
        plan = read(root / 'plan.json')
        for phase in ('solve', 'tangent', 'verify'):
            assert read(folder / phase / 'terminal.json')['returncode'] == 0
        report = read(folder / 'report.json')
        result = read(folder / 'result.json')
        validate(report)
        assert report['status'] == 'VERIFIED_WARM_EQUILIBRIUM'
        assert report['result'] == pin(folder / 'result.json')
        assert report['request'] == pin(folder / 'request.json')
        assert result['converged'] and result['residual'] <= 1e-12 and report['fresh_residual'] <= 1e-12
        assert all(c['passed'] for c in report['checks'])
        expected = deepcopy(plan['base_request'])
        expected['condition']['beta'] = report['beta']
        expected['tolerance'] = plan['physical_residual_gate']
        expected['initial_state'] = read(report['seed']['path'])['equilibrium_state']
        assert read(folder / 'request.json') == expected
        if folder == root:
            assert len(report['checks']) == 21
            assert abs(report['values']['RY_m']-plan['target_sensor_Y_m']) <= 1e-10
            tangent = read(folder / 'tangent/report.json')
            validate(tangent)
            assert tangent['status'] == 'COMPLETE_CENTERED_PHYSICAL_AND_BORDERED'
            assert result['diagnostic_deflection_continuation']['tangent'] == pin(folder / 'tangent/report.json')
        else:
            assert len(report['checks']) == 19
            tangent = read(folder / 'tangent.json')
            validate(tangent)
            assert tangent['status'] == 'COMPLETE_CENTERED_FINAL_TANGENT'
        pending = read(folder / 'candidate.json')
        validate(pending)
        records.append(dict(path=str(folder.relative_to(ROOT)), beta=report['beta'],
            values=report['values'], residual=report['fresh_residual'], checks=len(report['checks']),
            rank=result['equilibrium_initialization'],
            augmented_rank=report.get('continuation_parameter', {}).get('augmented_rank')))
    upper, lower = folders[1], folders[2]
    requests = [read(p / 'request.json') for p in (upper, lower)]
    for request in requests:
        request.pop('initial_state')
    assert requests[0] == requests[1], 'The two equilibria must have identical physical requests.'
    assert records[1]['beta'] == records[2]['beta']
    separation = records[1]['values']['RY_m']-records[2]['values']['RY_m']
    assert separation > .001, 'Distinctness must exceed numerical uncertainty by a wide margin.'
    previous_path = BASE / 'ae2-centered-audit-20261110/assessment.json'
    previous = read(previous_path)
    validate(previous)
    old = next(r for r in previous['records'] if r.get('beta') == 2.6875 and r['status'] == 'VERIFIED_DIAGNOSTIC')
    assert old['beta'] < records[0]['beta'] and records[1]['beta'] < records[0]['beta']
    assessment = dict(observed_utc=datetime.now(timezone.utc).isoformat(),
        status='VERIFIED_DISTINCT_EQUILIBRIA_AND_SAMPLED_TURN', records=records,
        earlier_branch=[r for r in previous['records'] if r['status'] == 'VERIFIED_DIAGNOSTIC'],
        later_tangent=later, captured_trial=capture, extended_search=extended,
        identical_physical_requests=True, paired_beta_deg=records[1]['beta'],
        sensor_Y_separation_m=separation, physical_checks=sum(r['checks'] for r in records),
        maximum_full_residual=max(r['residual'] for r in records),
        processes=processes, supervised_processes=len(processes),
        failed_processes=sum(p['returncode'] != 0 for p in processes), all_processes_reaped=True,
        primary_passed=708, primary_required=2200, primary_votes_added=0,
        qualifications=[
            'Both paired states satisfy the same fixed-incidence physical equations and full tangent rank gate.',
            'The additional sensor constraint selects a continuation point; no archived comparison is redefined.',
            'A sampled turn and multiple roots do not establish the exact fold, stability or historical branch selection.',
            'The original five-degree mismatch, unresolved executions and unrun comparisons remain open.',
            'Production sources and defaults remain unchanged.'])
    pin(previous_path)
    pin(Path(__file__))
    assessment['pins'] = [dict(path=p, sha256=h) for p, h in sorted(hashes.items())]
    out.mkdir()
    (out / 'assessment.json').write_text(json.dumps(assessment, indent=2) + '\n')
    print(json.dumps({k: assessment[k] for k in ('status', 'physical_checks',
        'paired_beta_deg', 'sensor_Y_separation_m', 'supervised_processes', 'failed_processes')}), flush=True)


def plot(out):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    d = read(out / 'assessment.json')
    fig, axes = plt.subplots(1, 2, figsize=(11.8, 4.8), constrained_layout=True)
    ax = axes[0]
    branch = d['earlier_branch'] + d['records'][:2]
    branch.sort(key=lambda r: r['values']['RY_m'])
    ax.plot([r['values']['RY_m'] for r in branch], [r['beta'] for r in branch],
            'o-', color='#2563eb', label='Verified positive-deflection states')
    pair = d['records'][1:]
    ax.plot([r['values']['RY_m'] for r in pair], [r['beta'] for r in pair],
            'D--', color='#d97706', label='Two equilibria at identical incidence')
    ax.axhline(2.75, color='gray', ls=':', label='Fixed-incidence solve still unresolved')
    ax.set(xlabel='Sensor Earth Y (m)', ylabel='Solved / prescribed beta (degrees)',
           title='The sampled equilibrium relation turns back')
    ax.legend(fontsize=8, loc='lower right')
    ax = axes[1]
    trace = d['extended_search']
    start = trace['records'][0]['before']
    errors = [start] + [r['after'] for r in trace['records']]
    ax.plot(range(len(errors)), [100*(1-e/start) for e in errors], 'o-', color='#2563eb')
    for k, row in enumerate(trace['records'], 1):
        ax.annotate('1/' + str(2**row['accepted_power']),
                    (k, 100*(1-row['after']/start)), xytext=(0, -17),
                    textcoords='offset points', ha='center', fontsize=8)
    ax.set(xlabel='Additional fresh Newton step at beta = 2.75°',
           ylabel='Reduction of stalled max residual (%)',
           title='More backtracking gives diminishing progress', xticks=range(5), ylim=(-.013, .075))
    ax.text(.04, .96, 'Final residual: 1.486 × 10⁻⁴\nRequired: ≤ 10⁻¹²\nLabels: accepted step fractions',
            transform=ax.transAxes, va='top', fontsize=9)
    for ax in axes:
        ax.grid(alpha=.25)
    fig.suptitle('AE-2 diagnostic: unchanged equations; no additional native-reference passes', fontsize=12)
    for extension in ('png', 'svg'):
        path = out / ('turning-branch.' + extension)
        assert not path.exists()
        fig.savefig(path, dpi=150)
    plt.close(fig)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['audit', 'plot'])
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    globals()[args.action](args.output.resolve())
