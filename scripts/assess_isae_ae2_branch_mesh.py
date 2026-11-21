"""Audit saved AE-2 branch points on two meshes; add no native-reference votes."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads(Path(path).read_text())


def assess(out):
    assert not (out / 'assessment.json').exists()
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

    plan = read(out / 'plan.json')
    validate(plan)
    processes = []
    records = []

    def checked(folder, expected_checks, new):
        local = read(folder / 'plan.json')
        validate(local)
        for phase in ('solve', 'tangent', 'verify'):
            path = folder / phase / 'terminal.json'
            terminal = read(path)
            proof = read(path.with_name('sources-verified.json'))
            assert terminal['returncode'] == 0 and terminal['process_reaped']
            assert not terminal['supervisor_timeout'] and proof['all_pins_checked_before_and_after']
            assert proof['plan'] == pin(folder / 'plan.json') and proof['terminal'] == pin(path)
            if new:
                processes.append(dict(path=str(path.relative_to(ROOT)), **terminal))
        report = read(folder / 'report.json')
        result = read(folder / 'result.json')
        request = read(folder / 'request.json')
        validate(report)
        validate(read(folder / 'candidate.json'))
        validate(read(folder / 'tangent/report.json'))
        assert report['status'] == 'VERIFIED_WARM_EQUILIBRIUM'
        assert result['converged'] and result['residual'] <= 1e-12 and report['fresh_residual'] <= 1e-12
        assert report['result'] == pin(folder / 'result.json') and report['request'] == pin(folder / 'request.json')
        assert len(report['checks']) == expected_checks and all(c['passed'] for c in report['checks'])
        assert len(result['equilibrium_state']['identity']['elements']) == local['expected_elements']
        for suffix in ('*.json', '*.log'):
            for path in folder.rglob(suffix):
                pin(path)
        if new:
            records.append(dict(path=str(folder.relative_to(ROOT)), beta=report['beta'],
                values=report['values'], residual=report['fresh_residual'], checks=len(report['checks']),
                control=report['control'], physical_rank=result['equilibrium_initialization'],
                augmented_rank=report['continuation_parameter']['augmented_rank']))
        return report, request

    control, _ = checked(Path(plan['control']), 23, True)
    assert control['control']['maximum_coordinate_difference'] <= 1e-10
    assert max(control['control']['value_differences'].values()) <= 1e-10
    intermediate, _ = checked(Path(plan['intermediate']), 21, True)
    comparisons = []
    for pair in plan['comparisons']:
        fine, fine_request = checked(Path(pair['fine']), 21, False)
        coarse, coarse_request = checked(Path(pair['coarse']), 21, True)
        for r in (fine, coarse):
            assert abs(r['values']['RY_m']-pair['target_sensor_Y_m']) <= 1e-10
        # Beta is solved and mesh density is intentionally changed. Compare
        # every other physical input, rather than numerical launch metadata.
        for key in ('source', 'numerics', 'operating_constraints', 'mode', 'strut_mode', 'controller'):
            assert coarse_request.get(key) == fine_request.get(key), key
        conditions = [{k: v for k, v in q['condition'].items() if k != 'beta'}
                      for q in (fine_request, coarse_request)]
        assert conditions[0] == conditions[1] and conditions[0]['speed'] == 17
        fine_values = dict(beta_deg=fine['beta'], **fine['values'])
        coarse_values = dict(beta_deg=coarse['beta'], **coarse['values'])
        changes = {}
        for key in plan['channels']:
            delta = abs(coarse_values[key]-fine_values[key]) / abs(fine_values[key])
            changes[key] = dict(coarse=coarse_values[key], fine=fine_values[key],
                relative_change=delta, passed=delta <= plan['relative_mesh_limit'])
        comparisons.append(dict(target_sensor_Y_m=pair['target_sensor_Y_m'], channels=changes,
            passed=all(c['passed'] for c in changes.values())))
    changes = [c for r in comparisons for c in r['channels'].values()]
    coarse_turn = intermediate['beta'] < comparisons[0]['channels']['beta_deg']['coarse'] > comparisons[1]['channels']['beta_deg']['coarse']
    fine_turn = comparisons[0]['channels']['beta_deg']['fine'] > comparisons[1]['channels']['beta_deg']['fine']
    pin(Path(__file__))
    pin(out / 'plan.json')
    assessment = dict(observed_utc=datetime.now(timezone.utc).isoformat(),
        status='BRANCH_MESH_CHECK_PASS' if all(c['passed'] for c in changes) and coarse_turn and fine_turn else 'BRANCH_MESH_CHECK_FAIL',
        records=records, comparisons=comparisons, relative_mesh_limit=plan['relative_mesh_limit'],
        mesh_checks_passed=sum(c['passed'] for c in changes), mesh_checks_required=len(changes),
        maximum_mesh_change_percent=100*max(c['relative_change'] for c in changes),
        sampled_turn_order_preserved=bool(coarse_turn and fine_turn),
        physical_checks=sum(r['checks'] for r in records), maximum_full_residual=max(r['residual'] for r in records),
        supervised_processes=len(processes), processes=processes, all_processes_reaped=True,
        primary_votes_added=0, qualifications=plan['qualifications'],
        pins=[dict(path=p, sha256=h) for p, h in sorted(hashes.items())])
    (out / 'assessment.json').write_text(json.dumps(assessment, indent=2) + '\n')
    print(json.dumps({k: assessment[k] for k in ('status', 'mesh_checks_passed',
        'mesh_checks_required', 'maximum_mesh_change_percent', 'physical_checks',
        'maximum_full_residual', 'supervised_processes')}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    assess(parser.parse_args().output.resolve())
