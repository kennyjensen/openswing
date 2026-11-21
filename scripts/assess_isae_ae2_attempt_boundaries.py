"""Audit the complete cold path of bounded AE-2 attempt diagnostics.

Saved files only. Controls and partial boundaries are never reference votes.
The result reports comparisons separately from the registered primary ledger.
"""
from datetime import datetime, timezone
from pathlib import Path
import json
import resource
import signal
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.probe_isae_ae2_cold_trace import read, write, pin
from scripts.recover_isae_ae2_saved import expected_request, CHECK_NAMES
from scripts import isae_suite_aeroelastic as adapter
from scripts.isae_acceptance import apply_reference_acceptance


def assess(out):
    pins = {}
    def remember(path):
        key = str(Path(path).resolve())
        if key not in pins:
            pins[key] = pin(key)
        return pins[key]
    def load(path):
        remember(path)
        return read(path)
    def plan_at(path):
        plan = load(path)
        for item in plan['pins']:
            assert remember(item['path']) == item
        return plan

    remember(__file__)
    parent = ROOT/'artifacts/isae/ae2-beta1-cold-stages-20261110'
    old = plan_at(parent/'plan.json'); plan = plan_at(out/'plan.json')
    policy = load(ROOT/'artifacts/isae/ae2-beta1-negative-extension-20261110/assessment-after-retries.json')['reference_acceptance']
    terminals = []
    for root in (parent, out):
        for started in sorted(root.glob('cases/*/*/started.json')):
            folder = started.parent
            t = load(folder/'terminal.json'); sources = load(folder/'sources-verified.json')
            assert t['process_reaped'] is True
            assert sources['all_pins_checked_before_and_after'] is True
            assert sources['plan'] == remember(root/'plan.json')
            assert sources['terminal'] == remember(folder/'terminal.json')
            terminals.append(dict(path=str(folder/'terminal.json'), **t))

    def chain(folders, original, previous=None):
        for folder in folders:
            t = load(folder/'terminal.json'); r = load(folder/'result.json')
            assert t['returncode'] == 0 and not t['supervisor_timeout']
            req = load(folder/'request.json'); rep = load(folder/'report.json')
            assert {k:v for k,v in req.items() if k != 'continuation'} == original
            options = dict(max_load_steps=1)
            if previous is not None:
                assert previous['continuation_status'] == 'pending'
                options['checkpoint'] = previous['checkpoint']
            assert req['continuation'] == options
            assert rep['result'] == remember(folder/'result.json')
            assert rep['original_request'] == remember(original_path)
            if r['continuation_status'] == 'pending':
                p = r['checkpoint']
                assert p['physical_residual'] <= 1e-12
                assert p['context']['solver']['physical_residual_target'] == 1e-12
                if rep.get('rejected_boundary'):
                    before = previous['checkpoint']
                    assert p['coordinates'] == before['coordinates']
                    assert p['load_fraction'] == before['load_fraction']
                    assert p['accepted_load_steps'] == before['accepted_load_steps']
                    assert p['rejected_load_attempts'] == before['rejected_load_attempts']+1
                    event, = rep['rejected_boundary']
                    assert p['next_increment'] == event['next_increment'] == before['next_increment']/2
                    assert event['next_target'] == min(1., p['load_fraction']+p['next_increment'])
            else:
                assert r['continuation_status'] == 'complete' and r['converged'] is True
                assert r['residual'] <= 1e-12 and rep['fresh_residual'] <= 1e-12
                assert all(c['passed'] is True for c in rep['checks'])
                assert tuple(c['name'] for c in rep['checks'][:18]) == CHECK_NAMES
            previous = r
        return previous

    controls = []
    for case in old['cases']:
        if 'control_result' not in case:
            continue
        original_path = case['request']; original = load(original_path)
        assert original == expected_request(case['job'])
        folders = sorted((parent/'cases'/case['name']).glob('*/report.json'))
        result = chain([p.parent for p in folders], original)
        assert result['continuation_status'] == 'complete'
        rep = load(folders[-1]); assert len(rep['checks']) == 20
        controls.append(dict(case=case['name'], **rep['parity']))

    candidates = []
    for case in plan['cases']:
        original_path = case['request']; original = load(original_path)
        assert original == expected_request(case['job'])
        boundary = Path(case['boundary']); last = int(boundary.parent.name)
        result = chain([boundary.parent.parent/f'{i:02d}' for i in range(last+1)], original)
        completed = []
        for folder in sorted((out/'cases'/case['name']).glob('*')):
            terminal = load(folder/'terminal.json')
            if terminal['returncode'] != 0:
                break
            completed.append(folder)
        if not completed:
            continue
        result = chain(completed, original, result)
        rep = load(completed[-1]/'report.json')
        if 'expected_boundary' in case:
            expected = load(case['expected_boundary'])['checkpoint']; actual = result['checkpoint']
            assert rep['status'] == 'control_pass'
            assert len(actual['coordinates']) == len(expected['coordinates'])
            difference = max(abs(a-b) for a,b in zip(actual['coordinates'],expected['coordinates']))
            assert difference == rep['maximum_coordinate_difference'] <= 1e-11
            for key in ('context','load_fraction','next_increment','accepted_load_steps','rejected_load_attempts','hinge_charts'):
                assert actual[key] == expected[key]
            controls.append(dict(case=case['name'],maximum_coordinate_difference=difference))
            continue
        record = dict(case=case['name'], job=case['job']['id'], status=rep['status'],
                      report=str(completed[-1]/'report.json'), primary_votes_added=0)
        if rep['status'] == 'computed':
            sensor = result['sensors'][0]
            values = dict(RY_m=sensor['position_earth'][1], Psi_deg=sensor['heading'],
                          sensor_V_m_s=sensor['speed'], sensor_beta_deg=sensor['beta'])
            assert values == rep['values']
            strict = dict(status='computed',numerical_pass=True,reference_checks=adapter._checks(case['job'],values),
                          output_accounting=dict(required=4,reported=4,finite=4,missing=0))
            compared = apply_reference_acceptance(strict, relative_tolerance=policy['relative_tolerance'],
                                                  tiny_reference=policy['tiny_reference'])
            record.update(values=values, comparisons=compared['reference_checks'],
                          fresh_residual=rep['fresh_residual'], physical_checks=len(rep['checks']))
        else:
            record['load_fraction'] = result['load_fraction']
        candidates.append(record)
    assert all(pin(p['path']) == p for p in pins.values())
    report = dict(status='COLD_ATTEMPT_DIAGNOSTIC_AUDIT_PASS', observed_utc=datetime.now(timezone.utc).isoformat(),
        controls=controls, candidates=candidates, terminals=terminals, source_pins=list(pins.values()),
        primary_votes_added=0, production_changes=False, physical_calls=0,
        qualification='Complete cold chains and physical checks verified. Comparisons are diagnostic until the registered collector supports this execution route; original failures remain intact.')
    assert not (out/'assessment.json').exists()
    write(out/'assessment.json', report)
    print(json.dumps(dict(status=report['status'], controls=len(controls), candidates=candidates,
                          reaped=len(terminals), failed=sum(t['returncode'] != 0 for t in terminals)),indent=2))


if __name__ == '__main__':
    resource.setrlimit(resource.RLIMIT_AS, (512*1024**2,)*2)
    resource.setrlimit(resource.RLIMIT_CPU, (15,)*2)
    signal.alarm(60)
    assess(Path(sys.argv[1]).resolve())
