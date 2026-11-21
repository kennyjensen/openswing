"""Summarize the bounded native AE-3 comparison; never add ASWING votes."""
from datetime import datetime, timezone
import csv
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.probe_isae_ae2_cold_trace import read, write, pin

OUT = ROOT/'artifacts/isae/ae3-native-avl-r2-20261111'


def assess():
    assert not (OUT/'assessment.json').exists()
    plan = read(OUT/'plan.json')
    plan_pin = pin(OUT/'plan.json')
    rows, evidence, checks = [], [], []
    for case in plan['cases']:
        folder = OUT/'cases'/case['name']
        terminal = read(folder/'terminal.json')
        native = read(folder/'native-process.json')
        sources = read(folder/'sources-verified.json')
        report = read(folder/'report.json')
        assert terminal['returncode'] == 0 and terminal['process_reaped']
        assert not terminal['supervisor_timeout'] and terminal['limits'] == plan['limits']
        assert native['returncode'] == 0 and native['process_reaped']
        assert sources['all_pins_checked'] and sources['plan'] == plan_pin
        assert report['numerical_pass'] and report['stalled_strips'] == 0
        for check in report['checks']:
            assert check['passed'] and check['metric'] <= check['gate']
            checks.append(dict(case=case['name'], **check))
        rows.append(dict(mesh=case['name'], intervals=case['job']['expected_elements'],
            native_Cl=report['native_Cl_stability'],
            original_Cl=report['original']['Cl_total'],
            matched_Cl=report['matched_receivers']['Cl_total'],
            matched_vortex_Cl=report['matched_receivers']['Cl_circulation_force'],
            native_fields_asw_arm_Cl=report['native_fields_on_asw_force_arm_Cl'],
            matched_gamma_relative_linf=report['native_vs_matched_circulation_relative_linf'],
            original_gamma_relative_linf=report['native_vs_original_circulation_relative_linf'],
            original_Cl_error_percent=report['native_vs_original_Cl_percent'],
            matched_vortex_Cl_error_percent=report['native_vs_matched_vortex_Cl_percent'],
            same_force_arm_error_percent=report['native_vs_asw_arm_vortex_Cl_percent'],
            normal_only_gamma_relative_linf=report['normals_only_circulation_relative_linf'],
            receiver_shift_m=report['native_receiver_shift_max'],
            numerical_checks=len(report['checks']),
            cpu_seconds=terminal['cpu_seconds'], wall_seconds=terminal['wall_seconds'],
            peak_rss_kib=terminal['peak_rss_kib']))
        for name in ('report.json','terminal.json','native-process.json','sources-verified.json',
                     'native-fields.npz','total.txt','elements.txt','model.avl','commands.txt',
                     'conversion.json','openswing-native-receivers.json','openswing-fresh.json',
                     'phases.jsonl','started.json'):
            evidence.append(pin(folder/name))
    assert len(rows) == 2 and len(checks) == 26 and plan['primary_votes_added'] == 0
    for source in plan['runtime_pins']:
        assert pin(source['path']) == source, source['path']
    with (OUT/'comparison.csv').open('x') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)
    first = ROOT/'artifacts/isae/ae3-native-avl-20261111/cases/m80'
    first_receipt = read(first/'terminal.json')
    assert first_receipt['process_reaped'] and first_receipt['supervisor_timeout']
    write(OUT/'assessment.json', dict(
        observed_utc=datetime.now(timezone.utc).isoformat(),
        status='ACTUAL_RIGID_AE3_NATIVE_AVL_COMPARISON_COMPLETE_NOT_ASWING_VALIDATION',
        plan=plan_pin, assessor=pin(Path(__file__)), cases=rows, checks=checks,
        numerical_checks_passed=len(checks), primary_votes_added=0,
        primary_scope=dict(passed=50, required=725, computed=72, mismatches=22, uncomputed=653),
        original_startup_attempt=dict(receipt=pin(first/'terminal.json'),
            explanation='Timed out before AVL input generation or execution; preserved, not a numerical disagreement.'),
        source_check_policy=plan['startup_change'], evidence=evidence,
        conclusion='Matched actual rigid AE-3 circulation agrees with native AVL to 4.34e-9 relative Linf. Receiver sampling and documented force/arm/section-moment conventions explain integrated rigid differences. No aerodynamic equation change is justified by these cases.',
        limitations=['Rigid, planar, incompressible, F1=1 only; no flexible ASWING validation.',
            'Equivalent section-normal incidence is not a physical hinged-flap AVL model.',
            'The original ASW receiver rule and all original native failures are retained.',
            'Native tiny core and rounded Biot-Savart constant are not copied into production.',
            'No claim of exact archived generating inputs or continuum convergence.'],
        next_step='Audit native finite-control versus local-derivative behavior and establish the corresponding quasi-steady coupled derivative path, while preserving report/model coefficient conflicts.'))
    print(json.dumps(dict(cases=2, checks=len(checks), primary_votes_added=0,
                         maximum_matched_gamma_relative_linf=max(r['matched_gamma_relative_linf'] for r in rows))))


def plot():
    import resource
    import signal
    resource.setrlimit(resource.RLIMIT_AS, (512*1024**2,)*2)
    resource.setrlimit(resource.RLIMIT_CPU, (15,)*2)
    signal.alarm(25)
    import numpy as np
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    summary = read(OUT/'assessment.json')
    plan = read(OUT/'plan.json')
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.9), sharey=True, constrained_layout=True)
    for axis, case in zip(axes, plan['cases']):
        folder = OUT/'cases'/case['name']
        native = np.load(folder/'native-fields.npz')
        report = read(folder/'report.json')
        conversion = read(folder/'conversion.json')
        axis.plot(native['RV'][:, 1], native['GAM'].ravel(), color='#0072B2', linewidth=2.5, label='Native AVL')
        axis.plot(native['RV'][:, 1], report['matched_receivers']['circulation'], '--', color='#E69F00', linewidth=1.8, label='OpenSwing, matched receivers')
        axis.plot(conversion['original_sample_stations'], report['original']['circulation'], ':', color='#009E73', linewidth=1.8, label='OpenSwing, original receivers')
        axis.set(title=f"{case['job']['expected_elements']} intervals", xlabel='Span station y (m)')
        axis.grid(alpha=.22)
    axes[0].set_ylabel('Circulation / freestream speed (m)')
    axes[0].legend(fontsize=8, loc='upper left')
    fig.suptitle('AE-3 rigid wing: matched circulation agrees to 4.34 × 10⁻⁹ relative\nDiagnostic only; archived flexible-ASWING tally remains 50/725', fontsize=11)
    for ext in ('png','svg'):
        path=OUT/f'circulation.{ext}'
        assert not path.exists()
        fig.savefig(path, dpi=160)
    plt.close(fig)
    write(OUT/'plot-receipt.json', dict(observed_utc=datetime.now(timezone.utc).isoformat(),
        assessment=pin(OUT/'assessment.json'), plotter=pin(Path(__file__)),
        artifacts=[pin(OUT/f'circulation.{ext}') for ext in ('png','svg')]))
    print('Wrote circulation.png and circulation.svg from saved results; no solver run.')


if __name__ == '__main__':
    {'assess': assess, 'plot': plot}[sys.argv[1]]()
