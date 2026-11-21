"""Append verified states to the same 48 SA-11 targets, preserving old evidence."""
import argparse
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import signal
import statistics

from sa11_paper_suite import bounded, decision, interpolate, write_new

ROOT = Path(__file__).resolve().parents[1]
read = lambda path: json.loads(path.read_text())
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--spec', type=Path, default=ROOT / 'docs/validation/sa11-paper-suite-v3.json')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    bounded()
    assert not args.output.exists()
    spec = read(args.spec)
    assert spec['version'] == 3
    base, supplement = (ROOT / spec[key] for key in ('base_assessment', 'supplement'))
    previous = read(base / 'analysis.json')
    proof = read(base / 'verification.json')
    assert proof['verified'] and proof['analysis_sha256'] == sha(base / 'analysis.json')
    plan = read(supplement / 'plan.json')
    pins = dict(previous['pins'])
    pins.update(plan['pins'])
    for path, digest in pins.items():
        assert sha(ROOT / path) == digest, path
    for path in (args.spec.resolve(), Path(__file__), base / 'analysis.json', base / 'verification.json', supplement / 'plan.json'):
        pins[str(path.relative_to(ROOT))] = sha(path)
    result = deepcopy(previous)
    result.update(observed_utc=datetime.now(timezone.utc).isoformat(), suite=spec['name'])
    result['protocol'].update(version=3, name=spec['name'], coverage_spec=spec)
    rows, audits, batches = [], [], []
    for index, case in enumerate(plan['cases']):
        directory = supplement / case['id']
        row = read(directory / 'report.json')
        audit = read(directory / 'verification.json')
        batch_path = supplement / f'batch-{index:03d}.json'
        batch = read(batch_path)
        assert row['case'] == case and row['plan_sha256'] == sha(supplement / 'plan.json')
        assert audit['verified'] and audit['report_sha256'] == sha(directory / 'report.json')
        assert audit['plan_sha256'] == row['plan_sha256']
        assert audit['checker_sha256'] == sha(ROOT / 'scripts/check_sa11_lower_coverage.py')
        assert batch['rows'] == [dict(id=case['id'], report_sha256=audit['report_sha256'])]
        for path in (directory / 'report.json', directory / 'verification.json', batch_path):
            pins[str(path.relative_to(ROOT))] = sha(path)
        for name, digest in row['artifacts'].items():
            assert sha(directory / name) == digest
            pins[str((directory / name).relative_to(ROOT))] = digest
        assert case['configuration'] == 'upper_lower_winglets'
        curve = next(c for c in result['curves'] if c['configuration'] == case['configuration'] and c['label'] == case['label'])
        assert case['alpha'] not in {p['alpha'] for p in curve['points']}
        valid = row['status'] == 'computed'
        curve['points'].append(dict(alpha=case['alpha'], valid=valid,
            CL=row['values']['CL'] if valid else None, CD=row['values']['CD'] if valid else None,
            status=row['status'], source=str((directory / 'report.json').relative_to(ROOT))))
        curve['points'].sort(key=lambda p: p['alpha'])
        rows.append(row)
        audits.append(audit)
        batches.append(batch)
    assert len(rows) == plan['physical_calls'] == sum(r['physical_calls'] for r in rows) == 6
    config = next(c for c in result['protocol']['configurations'] if c['id'] == 'upper_lower_winglets')
    config['supplement'] = spec['supplement']
    config['setup'] = config['setup'].replace('Sparse saved samples and rejected states remain visible;',
        'Six additional quarter-degree/3-degree states extend the saved coverage; rejected states remain visible;')
    for curve in result['curves']:
        if curve['configuration'] == config['id']:
            curve['setup'] = config['setup']
    transitions = []
    for check, before in zip(result['checks'], previous['checks'], strict=True):
        if check['configuration'] != 'upper_lower_winglets':
            continue
        curve = next(c for c in result['curves'] if c['configuration'] == check['configuration'] and c['label'] == check['label'])
        xkey, ykey = ('alpha', 'CL') if check['kind'] == 'lift' else ('CL', 'CD')
        value, bracket, reason = interpolate(curve['points'], check['x'], xkey, ykey,
                                            result['protocol']['maximum_interpolation_gap_degrees'])
        status, error = decision(value, check['target'], result['protocol']['relative_tolerance'])
        if check['kind'] == 'lift' and any(p['alpha'] == check['x'] and not p['valid'] for p in curve['points']):
            status = 'rejected'
        check.update(actual=value, bracket_alpha=bracket, reason=reason, status=status, error_percent=error)
        if status != before['status']:
            transitions.append(dict(id=check['id'], before=before['status'], after=status))
    assert len(result['checks']) == result['required'] == spec['required_checks'] == 48
    result['counts'] = dict(Counter(c['status'] for c in result['checks']))
    for group in result['groups']:
        checks = [c for c in result['checks'] if c['configuration'] == group['configuration']]
        errors = [abs(c['error_percent']) for c in checks if c['error_percent'] is not None]
        failed = [abs(c['error_percent']) for c in checks if c['status'] == 'mismatch']
        group.update(counts=dict(Counter(c['status'] for c in checks)), maximum_error_percent=max(errors, default=None),
            failed_error_percent=dict(median=statistics.median(failed), maximum=max(failed)) if failed else None,
            fields={kind: dict(Counter(c['status'] for c in checks if c['kind'] == kind))
                    for kind in ('lift', 'drag_at_equal_lift')})
    for increment in result['drag_increments']:
        if increment['configuration'] != 'upper_lower_winglets':
            continue
        checks = {c['configuration']: c for c in result['checks'] if c['kind'] == 'drag_at_equal_lift'
                  and c['label'] == increment['label'] and c['x'] == increment['CL']}
        base_check, tip = checks['wing_alone'], checks['upper_lower_winglets']
        actual = tip['actual'] - base_check['actual'] if tip['actual'] is not None and base_check['actual'] is not None else None
        increment.update(actual_delta_CD=actual, comparable_delta_CD=actual,
            reason=None if actual is not None else 'Missing accepted matched-lift bracket')
    accepted = [r for r in rows if r['status'] == 'computed']
    result['prior_solve_evidence'] = result['new_solve_evidence']
    result['new_solve_evidence'] = dict(physical_calls=6, reused_states=0, computed=len(accepted), rejected=6-len(accepted),
        maximum_residual=max(r['residual'] for r in rows),
        maximum_normal_mach=max(r['maximum_normal_mach'] for r in rows),
        minimum_stall_margin_widths=min(r['minimum_stall_margin_widths'] for r in accepted),
        peak_rss_kib=max(b['peak_rss_kib'] for b in batches),
        maximum_batch_seconds=max(b['seconds'] for b in batches), total_batch_seconds=sum(b['seconds'] for b in batches))
    result['coverage_update'] = dict(spec=spec, transitions=transitions,
        state_audits=audits, old_counts=previous['counts'], new_counts=result['counts'],
        maximum_independent_errors={key: max(a['errors'].get(key, 0.) for a in audits)
                                    for key in audits[0]['errors']})
    result.update(pins=pins, transitions=transitions, physical_calls=0)
    args.output.mkdir(parents=True)
    write_new(args.output / 'analysis.json', result)
    signal.alarm(0)
    print(json.dumps({key: result[key] for key in ('counts', 'groups', 'transitions', 'new_solve_evidence')}, indent=2))


if __name__ == '__main__':
    main()
