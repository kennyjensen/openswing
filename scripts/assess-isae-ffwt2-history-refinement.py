"""Audit the full original-start histories and compare their common native rows."""
import argparse
from decimal import Decimal
import hashlib
import json
import math
from pathlib import Path
import statistics
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.isae_acceptance import apply_reference_acceptance

NAMES = ['roll_acceleration_deg_s2', 'roll_rate_deg_s', 'bank_deg', 'sensor2_bank_deg', 'sensor3_bank_deg']


def pin(path):
    path = Path(path).resolve(); raw = path.read_bytes()
    return dict(path=str(path), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def values(s):
    sensors = {r['index']: r for r in s['sensors']}
    return [math.degrees(s['frame']['angular_acceleration_body'][0]),
        math.degrees(s['frame']['rates_body'][0]),
        math.degrees(s['restart']['state']['source_attitude'][0]), sensors[2]['bank'], sensors[3]['bank']]


def history(folder, dt):
    chain = []; checked = {}; visited = set()
    def verify(item):
        previous = checked.get(item['path'])
        if previous is not None:assert item == previous
        else:
            assert pin(item['path']) == item
            checked[item['path']] = item
    while True:
        folder = folder.resolve(); assert folder not in visited; visited.add(folder)
        plan = json.loads((folder/'plan.json').read_text())
        report = json.loads((folder/'report.json').read_text())
        assert report['status'] == 'SEGMENT_COMPUTED'
        assert plan['startup'] == 'jig-zero-motion-zero-circulation'
        assert plan['nominal'] == 16
        assert plan.get('time_step', .01) == dt
        assert plan['continuation_version'] == (2 if dt == .01 else 3)
        for item in plan['source_pins']+plan['kernel_pins']+[plan['helper'], plan['preparation_helper']]:verify(item)
        for key in ('result', 'checkpoint'):verify(report[key])
        if report.get('segment_helper'):verify(report['segment_helper'])
        chain.append((folder, plan, report))
        if 'parent_checkpoint' not in plan:break
        parent = plan['parent_checkpoint']; verify(parent)
        folder = Path(parent['path']).parent
    chain.reverse()
    first_plan = chain[0][1]; last_plan = chain[-1][1]
    assert last_plan['command_restarts'] == [2.]
    assert first_plan['declared_segment_start'] == dt
    for key in ('first_step_result', 'first_checkpoint'):verify(first_plan[key])
    paths = [Path(first_plan['first_step_result']['path'])]+[Path(r['result']['path']) for _, _, r in chain]
    samples = {}; residuals = []; accepted = 0; seeds = 0
    for index, path in enumerate(paths):
        result = json.loads(path.read_text())
        assert result['converged'] and result['rejected_steps'] == 0
        assert result['maximum_step'] == dt
        if index:
            assert result['checkpoint_validation']['discrete_replayed']
            assert result['checkpoint_validation']['residual'] <= 1e-8
        accepted += result['accepted_steps']
        for s in result['snapshots']:
            if s['time'] == 0:
                assert index == 0; seeds += 1; continue
            tick = round(s['time']/dt)
            assert abs(s['time']-tick*dt) < 1e-12 and s['converged'] and s['residual'] <= 1e-8
            order = s['restart']['accepted_method']['effective_order']
            assert order == (1 if tick in (1, round(2/dt)+1) else 2)
            row = values(s); assert all(math.isfinite(v) for v in row)
            if tick in samples:assert max(abs(a-b) for a, b in zip(row, samples[tick])) < 1e-8
            samples[tick] = row; residuals.append(s['residual'])
    total = round(2.04/dt)
    assert sorted(samples) == list(range(1, total+1)) and accepted == total and seeds == 1
    return dict(dt=dt, accepted_steps=accepted, rejected_steps=0, unique_states=len(samples),
        maximum_residual=max(residuals), segments=len(chain), source_pins=first_plan['source_pins'],
        kernel_pins=first_plan['kernel_pins'], first_seed_residual=first_plan['seed_residual'],
        common_rows={str(t): samples[round(t*.01/dt)] for t in range(1, 205)},
        accuracy_gate=last_plan.get('accuracy_gate'), inputs=list(checked.values()),
        plans=[pin(f/'plan.json') for f, _, _ in chain], reports=[pin(f/'report.json') for f, _, _ in chain])


def native(level):
    checks = []
    for line, raw in enumerate(Path(level['source_pins'][2]['path']).read_text().splitlines(), 1):
        if not raw.strip() or raw.startswith('#'):continue
        tokens = raw.split(); assert len(tokens) == 7
        t = float(tokens[1]); tick = round(t*100)
        assert abs(t-tick*.01) < 1e-12
        row = level['common_rows'].get(str(tick), [None]*5)
        for name, predicted, token in zip(NAMES, row, tokens[2:]):
            expected = Decimal(token); tolerance = Decimal(5).scaleb(expected.as_tuple().exponent-1)
            checks.append(dict(name=f'line{line}/{name}', channel=name, time=t, predicted=predicted,
                expected=float(expected), tolerance=float(tolerance), exact_decimal_expected=str(expected),
                exact_decimal_tolerance=str(tolerance),
                passed=predicted is not None and abs(Decimal(str(predicted))-expected) <= tolerance))
    assert len(checks) == 4005
    result = apply_reference_acceptance(dict(status='computed', numerical_pass=True, reference_checks=checks,
        output_accounting=dict(required=4005, computed=25, missing=3980)))
    channels = {}
    for name in NAMES:
        rows = [r for r in result['reference_checks'] if r['channel'] == name and r['predicted'] is not None]
        failed = [100*r['relative_error'] for r in rows if not r['passed']]
        channels[name] = dict(computed=len(rows), passed=sum(r['passed'] for r in rows),
            failed_median_percent=statistics.median(failed) if failed else None,
            failed_max_percent=max(failed) if failed else None)
    return dict(accounting=result['output_accounting'], channels=channels,
                checks=result['reference_checks'], policy=result['reference_acceptance_policy'])


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--coarse', type=Path, required=True)
    p.add_argument('--fine', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    coarse, fine = history(a.coarse, .01), history(a.fine, .005)
    assert coarse['source_pins'] == fine['source_pins'] and coarse['kernel_pins'] == fine['kernel_pins']
    assert fine['accuracy_gate']['relative'] == .001
    assert coarse['first_seed_residual'] == fine['first_seed_residual']
    channels = {}
    for i, name in enumerate(NAMES):
        differences = [abs(coarse['common_rows'][str(t)][i]-fine['common_rows'][str(t)][i]) for t in range(200, 205)]
        scale = max(abs(fine['common_rows'][str(t)][i]) for t in range(200, 205))
        channels[name] = dict(maximum_absolute_difference=max(differences), fine_window_scale=scale,
            maximum_percent_of_scale=100*max(differences)/scale, relative_limit=.001,
            passed=max(differences) <= .001*scale)
    for level in (coarse, fine):level['native'] = native(level)
    output = dict(status='FULL_STARTUP_REFINEMENT_ASSESSED', levels=[coarse, fine],
        channels=channels, accuracy_passed=sum(c['passed'] for c in channels.values()), accuracy_required=5,
        original_startup_authenticated=False, full_family_validated=False, helper=pin(__file__))
    assert not a.output.exists()
    a.output.write_text(json.dumps(output, indent=2, allow_nan=False)+'\n')
    print(json.dumps(dict(channels=channels, native=fine['native']['accounting']), indent=2))


if __name__ == '__main__':main()
