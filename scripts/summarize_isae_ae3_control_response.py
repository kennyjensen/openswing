"""Assess saved AE-3 response diagnostics without new solves or native votes."""
import csv
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.probe_isae_ae2_cold_trace import read, write, pin

BASE = ROOT / 'artifacts/isae'
OUT = BASE / 'ae3-control-response-20261111'
DIRS = {
    'initial': BASE / 'ae3-control-derivative-20261111',
    'first_order': BASE / 'ae3-control-derivative-r2-20261111',
    'fourth_order': BASE / 'ae3-control-derivative-r3-20261111',
    'initial_roll': BASE / 'ae3-roll-constraint-20261111',
    'roll': BASE / 'ae3-roll-constraint-r2-20261111',
    'sibling_roll': BASE / 'ae3-roll-control-20261111',
}
COEFFICIENTS = ['CX', 'CY', 'CL', 'Cl', 'Cm', 'Cn']


def assess():
    assert not OUT.exists(), 'Preserve existing observations.'
    plans = {key: read(path / 'plan.json') for key, path in DIRS.items()}
    source_pins = {}
    for plan in plans.values():
        for source in plan['pins']:
            old = source_pins.setdefault(source['path'], source)
            assert old == source, source['path']
    for source in source_pins.values():
        assert pin(source['path']) == source, source['path']

    evidence = [pin(path / 'plan.json') for path in DIRS.values()]
    receipts, accepted_checks, derivative_checks, rows = [], [], [], []

    def case(group, name, accept=True):
        folder = DIRS[group] / 'cases' / name
        terminal = read(folder / 'terminal.json')
        witness = read(folder / 'sources-verified.json')
        assert terminal['process_reaped'] and not terminal['supervisor_timeout']
        assert terminal['limits'] == plans[group]['limits']
        assert witness['all_pins_checked']
        assert witness['plan'] == pin(DIRS[group] / 'plan.json')
        receipts.append(dict(group=group, name=name, **terminal))
        for path in sorted(folder.iterdir()):
            if path.is_file():
                evidence.append(pin(path))
        report = read(folder / 'report.json') if (folder / 'report.json').exists() else None
        if accept:
            assert terminal['returncode'] == 0 and report['numerical_pass']
            for check in report['checks']:
                assert check['passed'] and math.isfinite(check['metric']) and check['metric'] <= check['gate']
                accepted_checks.append(dict(group=group, case=name, **check))
        return report, terminal

    def check(name, metric, gate, **context):
        value = dict(name=name, metric=metric, gate=gate,
                     passed=math.isfinite(metric) and metric <= gate, **context)
        derivative_checks.append(value)
        assert value['passed'], value

    fine = {}
    for op in (1, 6):
        tangent, _ = case('fourth_order', f'tangent-op{op}-m80')
        assert tangent['coefficient_rows'] == COEFFICIENTS
        derivatives = {}
        for h in (.001, .0005):
            samples = [case('first_order', f'nonlinear-op{op}-h{h:g}-{sign}')[0]
                       for sign in ('plus', 'minus')]
            assert samples[0]['increment'] == h and samples[1]['increment'] == -h
            fd = [(a-b)/(2*h) for a, b in zip(samples[0]['coefficients'], samples[1]['coefficients'])]
            derivatives[h] = fd
            for name, actual, expected in zip(COEFFICIENTS, tangent['coefficient_derivative'], fd):
                gate = max(plans['fourth_order']['gates']['nonlinear_derivative_absolute'],
                           plans['fourth_order']['gates']['nonlinear_derivative_relative']*abs(expected))
                check('implicit_vs_reconverged', abs(actual-expected), gate,
                      operating_point=op, step=h, coefficient=name)
                rows.append(dict(operating_point=op, speed=tangent['speed'], coefficient=name,
                                 step=h, implicit=actual, reconverged=expected,
                                 absolute_error=abs(actual-expected), gate=gate))
        for name, coarse, refined in zip(COEFFICIENTS, derivatives[.001], derivatives[.0005]):
            gate = max(plans['fourth_order']['gates']['nonlinear_derivative_absolute'],
                       plans['fourth_order']['gates']['nonlinear_derivative_relative']*abs(refined))
            check('nonlinear_step_refinement', abs(coarse-refined), gate,
                  operating_point=op, coefficient=name)
        fine[op] = dict(tangent=tangent, finite_difference=derivatives[.0005])

    assert len(accepted_checks) == 96 and len(derivative_checks) == 36
    derivative_total = len(accepted_checks) + len(derivative_checks)

    # Independently retained failures and superseded diagnostic approximation.
    initial, terminal = case('initial', 'tangent-op1-m80', accept=False)
    assert initial is None and terminal['returncode'] == 1
    assert "missing 1 required positional argument: 'loads'" in (
        DIRS['initial'] / 'cases/tangent-op1-m80/stderr.log').read_text()
    first, terminal = case('first_order', 'tangent-op1-m80', accept=False)
    assert terminal['returncode'] == 0 and first['numerical_pass']
    first_error = abs(first['coefficient_derivative'][2] - fine[1]['finite_difference'][2])
    assert first_error > plans['fourth_order']['gates']['nonlinear_derivative_absolute']
    old_roll, terminal = case('initial_roll', 'roll-free-op1-m80', accept=False)
    assert terminal['returncode'] == 1 and not old_roll['numerical_pass']
    assert [v['name'] for v in old_roll['checks'] if not v['passed']] == ['independent_coefficients']

    source = Path(plans['fourth_order']['cases'][0]['job']['source']).resolve()
    native = []
    for op in range(1, 7):
        path = source.with_name(f'Straight_20O.fmat_{op:03d}')
        text = path.read_text()
        def extract(pattern):
            found = re.findall(pattern, text)
            assert len(found) == 1, pattern
            return float(found[0])
        number = r'([-+]?\d+\.\d+)'
        row = dict(operating_point=op,
                   speed=extract(r'speed\s+V\s*=\s*'+number),
                   Cl=extract(r'Mx /qSb\s*=\s*Cl\s*=\s*'+number),
                   CldF1=extract(r'CldF1\s*=\s*'+number))
        row['finite_to_derivative_ratio'] = row['Cl']/row['CldF1']
        native.append(row)
        evidence.append(pin(path))

    roll_rows = []
    for op in (1, 6):
        literal, _ = case('roll', f'roll-free-op{op}-m80')
        sibling, _ = case('sibling_roll', f'sibling-lift-roll-free-op{op}-m80')
        assert sibling['changed_distributions'] == ['dCLdF1']
        assert not sibling['exact_historical_input_recovered']
        assert sibling['control_change']['literal'] == .0581
        assert sibling['control_change']['alternate'] == .0686
        assert sibling['native'] == literal['native']
        t = fine[op]['tangent']
        assert literal['fixed_acceleration']['Cl'] == t['base_coefficients'][3]
        assert sibling['literal_fixed_acceleration'] == literal['fixed_acceleration']
        ref = native[op-1]
        assert literal['native']['Cl'] == ref['Cl']
        roll_rows.append(dict(
            operating_point=op, speed=t['speed'], native_Cl=ref['Cl'], native_CldF1=ref['CldF1'],
            literal_fixed_Cl=t['base_coefficients'][3],
            literal_fixed_CldF1=t['coefficient_derivative'][3],
            literal_roll_Cl=literal['values']['Cl'],
            sibling_roll_Cl=sibling['values']['Cl'],
            literal_roll_error_percent=literal['error_percent']['Cl'],
            sibling_roll_error_percent=sibling['error_percent']['Cl'],
            sibling_roll_CX_error_percent=sibling['error_percent']['CX'],
            native_finite_to_derivative_ratio=ref['finite_to_derivative_ratio'],
            literal_roll_to_fixed_derivative_ratio=literal['values']['Cl']/t['coefficient_derivative'][3],
            derivative_absolute_error=abs(t['coefficient_derivative'][3]-fine[op]['finite_difference'][3])))

    assert len(accepted_checks) == 140 and derivative_total == 132
    assert len(receipts) == 17 and sum(r['returncode'] != 0 for r in receipts) == 2
    assert not (DIRS['first_order'] / 'cases/tangent-op6-m80').exists()
    OUT.mkdir()
    for name, data in [('derivative-comparison.csv', rows), ('constraint-comparison.csv', roll_rows),
                       ('native-finite-derivative.csv', native)]:
        with (OUT / name).open('x') as stream:
            writer = csv.DictWriter(stream, fieldnames=list(data[0]))
            writer.writeheader(); writer.writerows(data)
    assessment = dict(
        observed_utc=datetime.now(timezone.utc).isoformat(),
        status='COUPLED_CONTROL_DERIVATIVE_VERIFIED_SETUP_HYPOTHESIS_REMAINS_OPEN',
        assessor=pin(Path(__file__)), source_pins=list(source_pins.values()), evidence=evidence,
        accepted_worker_checks=accepted_checks, derivative_comparison_checks=derivative_checks,
        verified_derivative_checks=derivative_total, roll_constraint_checks=44,
        total_accepted_checks=len(accepted_checks)+len(derivative_checks),
        receipts=receipts, native=native, endpoints=roll_rows,
        primary_votes_added=0, production_changes=False,
        primary_scope=dict(passed=50, required=725, computed=72, mismatches=22, uncomputed=653),
        previous_attempts=dict(
            initial_derivative='Missing required loads argument in diagnostic constructor; exit1 retained.',
            first_order_geometry=dict(CL_derivative_error=first_error, gate=1e-8,
                accepted=False, reason='Internal checks passed, independent near-zero derivative check failed. Not a production derivative regression.'),
            first_order_high_speed='Unexecuted; superseded by fourth-order diagnostic.',
            initial_roll='Converged solve; static test oracle incorrectly included apparent-fluid loads in distributed coefficients. Re-audited saved solution with independent fluid/distributed decomposition; exit1 retained.'),
        interpretation=dict(
            constraint='Conditional manual/script interpretation: angular_acceleration.x is free and net moment.x is zero; angular rate remains zero.',
            derivative='Implicit full current source equations at fixed acceleration, F1=1; literal file-unit derivative. Fourth-order local geometry stencils plus analytic circulation/control and exact mechanical blocks, with full moving-field geometry terms.',
            ratio='Native finite/derivative gap resembles free-roll/fixed-acceleration response. Similar ratios are evidence for constraint audit, not recovered native derivative semantics.',
            sibling='Only lift-control scale .0581 -> .0686 in copied model; independently supplied by sibling files, not fitted or adopted.'),
        limitations=[
            'Only two endpoint speeds, nominal80 (82 intervals). No finer-mesh or complete-speed validation of these alternatives.',
            'Archived constraint mask/default toggle behavior and exact generating file remain unrecovered.',
            'Report mount1 fixes roll, mount2 permits steady roll; neither description alone authenticates this zero-rate accelerating diagnostic.',
            'A successful full derivative diagnostic is not a general production derivative implementation or a fully analytic path.',
            'High-speed sibling rolling error remains 28.50%; no primary pass or scope change.',
            'Original ASWING, ASWING-m and experiment remain distinct.'],
        next_step='Audit the archived constraint mask and MM derivative convention, then run the independently sourced alternative at remaining speeds and a second mesh before changing benchmark setup. Preserve original failures and all 725 targets.')
    write(OUT / 'assessment.json', assessment)
    print(json.dumps({k: assessment[k] for k in ('verified_derivative_checks', 'roll_constraint_checks',
        'total_accepted_checks', 'primary_votes_added')}))
    print(json.dumps(roll_rows))


def plot():
    import resource
    import signal
    resource.setrlimit(resource.RLIMIT_AS, (512*1024**2,)*2)
    resource.setrlimit(resource.RLIMIT_CPU, (15,)*2)
    signal.alarm(25)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    data = read(OUT / 'assessment.json')
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5), constrained_layout=True)
    ref, ends = data['native'], data['endpoints']
    axes[0].plot([r['speed'] for r in ref], [1e3*r['Cl'] for r in ref], 'k-o',
                 label='Archived ASWING finite Cl')
    for key, label, marker, color in (
        ('literal_fixed_Cl', 'Literal model, fixed acceleration', 's', '#0072B2'),
        ('literal_roll_Cl', 'Literal model, free roll acceleration', '^', '#D55E00'),
        ('sibling_roll_Cl', 'Sibling lift slope + free roll acceleration', 'D', '#009E73')):
        axes[0].scatter([r['speed'] for r in ends], [1e3*r[key] for r in ends],
                        marker=marker, color=color, label=label, s=48, zorder=3)
    axes[0].set(ylabel='Rolling coefficient Cl × 1000', title='Two diagnostic endpoints; original targets retained')
    axes[0].axhline(0, color='0.6', linewidth=.7)
    axes[0].legend(fontsize=7.3, loc='upper left')
    axes[1].plot([r['speed'] for r in ref], [r['finite_to_derivative_ratio'] for r in ref],
                 'k-o', label='Archived finite Cl / CldF1')
    axes[1].scatter([r['speed'] for r in ends], [r['literal_roll_to_fixed_derivative_ratio'] for r in ends],
                    marker='s', color='#0072B2', s=48,
                    label='Literal free-roll Cl / fixed-acceleration CldF1')
    axes[1].set(ylabel='Ratio (F1 = 1 file unit)', title='Constraint mechanism: suggestive, not authenticated')
    axes[1].legend(fontsize=7.3, loc='upper left')
    for axis in axes:
        axis.set_xlabel('Speed (m/s)')
        axis.grid(True, alpha=.25)
    fig.savefig(OUT / 'control-response.png', dpi=150)
    plt.close(fig)
    write(OUT / 'plot-receipt.json', dict(observed_utc=datetime.now(timezone.utc).isoformat(),
        assessment=pin(OUT / 'assessment.json'), plot=pin(OUT / 'control-response.png'),
        new_solves=0))
    print(str(OUT / 'control-response.png'))


if __name__ == '__main__':
    {'assess': assess, 'plot': plot}[sys.argv[1]]()
