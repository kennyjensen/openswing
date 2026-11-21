"""Compare both conditional operating states with the unchanged level trim."""
import argparse
from pathlib import Path

from check_daedalus_load_sensitivity import ROOT, read, write, pin
from daedalus_bounded_job import run
import check_daedalus_pitch_balanced_base as study
import report_daedalus_untrimmed_base as unbalanced

STAGES = [name for name in unbalanced.STAGES if name != 'equilibrium-1']
PRIOR = ROOT/'artifacts/daedalus-untrimmed-base-20261114/report-v2'
LEVEL = unbalanced.level.STUDY/'report'


def report(folder, arguments):
    import csv
    import math
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.ticker import LogLocator, FuncFormatter, NullFormatter

    pins, receipts = {}, {}
    for name in STAGES:
        stage = study.STUDY/name
        terminal = read(stage/'terminal.json')
        assert terminal['returncode'] == 0 and terminal['process_reaped']
        assert terminal['inputs_unchanged'] and not terminal['timed_out']
        receipts[name] = terminal
        for path, digest in read(stage/'plan.json')['inputs_sha256'].items():
            assert path not in pins or pins[path] == digest, path
            pins[path] = digest
    for cohort in [pins, read(PRIOR/'source-pins.json')]:
        for path, digest in cohort.items():
            assert pin(Path(path)) == digest, path
    write(folder/'source-pins.json', pins)
    data = read(PRIOR/'result.json')
    comparisons = []
    samples = []
    for name in ['response', 'native-features']:
        response = read(study.STUDY/name/'result.json')
        assert response['channels'] == unbalanced.CHANNELS
        samples.extend(response['samples'])
    for row in data['comparisons']:
        point = next(s for s in samples if s['frequency_hz'] == row['frequency_hz'])
        i = unbalanced.CHANNELS.index(row['channel'])
        value = point['magnitude'][i]
        assert math.isclose(value, math.hypot(point['real'][i], point['imag'][i]), rel_tol=2e-14)
        comparisons.append(dict(row, pitch_balanced=value,
            pitch_balanced_error_percent=100*(value/row['reference']-1),
            change_from_unbalanced_percent=100*(value/row['conditional_untrimmed']-1)))
    with (folder/'comparison.csv').open('x', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(comparisons[0]))
        writer.writeheader()
        writer.writerows(comparisons)
    with (LEVEL/'comparison.csv').open() as stream:
        baseline = list(csv.DictReader(stream))
    native = read(LEVEL/'reference.json')
    fig, axes = plt.subplots(2, 2, figsize=(12, 8.4), constrained_layout=True)
    for i, (ax, channel, title) in enumerate(zip(axes.flat, unbalanced.CHANNELS,
            ['Yaw rate', 'Roll rate', 'Sideslip', 'Bank'])):
        ref = native['channels'][channel]['vertices']
        old = sorted((r for r in baseline if r['channel'] == channel), key=lambda r: float(r['frequency_hz']))
        selected = sorted((r for r in comparisons if r['channel'] == channel), key=lambda r: r['frequency_hz'])
        ax.loglog([r[2] for r in ref], [r[3] for r in ref], '--', color='#2378b5', lw=1.6,
            label='Drela drawing; operating point unknown')
        ax.loglog([float(r['frequency_hz']) for r in old], [float(r['magnitude']) for r in old],
            color='#b83439', lw=1.6, label='OpenSwing: trimmed level flight')
        for key, marker, color, label in [
                ('conditional_untrimmed', 'o', '#a46700', 'Zero-incidence: zero controls'),
                ('pitch_balanced', 'x', '#157a58', 'Zero-incidence: F2 solves pitch balance')]:
            ax.loglog([r['frequency_hz'] for r in selected], [r[key] for r in selected],
                linestyle='none', marker=marker, markersize=7, markerfacecolor='none',
                markeredgewidth=1.6, color=color, label=label)
        ax.set(title=title, xlabel='Frequency (Hz)', xlim=(.1, 10),
            ylabel='Magnitude ('+('deg/s/F3' if i < 2 else 'deg/F3')+')')
        for axis in (ax.xaxis, ax.yaxis):
            axis.set_major_locator(LogLocator(base=10))
            axis.set_major_formatter(FuncFormatter(lambda x, _: f'{x:g}'))
            axis.set_minor_locator(LogLocator(base=10, subs=range(2, 10)))
            axis.set_minor_formatter(NullFormatter())
        ax.grid(which='major', color='#bfc5cc', lw=.7)
        ax.grid(which='minor', color='#e5e8ec', lw=.45)
        ax.set_axisbelow(True)
    axes[0, 0].legend(fontsize=7.7, loc='upper left')
    fig.suptitle('Daedalus at 6.7 m/s: pitch-balance diagnostic\n'
        'Markers: eight samples of instantaneous accelerating states; all perturbation accelerations free', fontsize=12)
    fig.savefig(folder/'comparison.svg')
    fig.savefig(folder/'comparison.png', dpi=140)
    plt.close(fig)
    return dict(qualification=study.QUALIFICATION, comparisons=comparisons,
        base=read(study.STUDY/'base-audit/result.json'),
        assembly=read(study.STUDY/'assembled/result.json'), stage_receipts=receipts,
        maximum_scaled_matrix_residual=max(max(s['checks']['scaled_residuals']) for s in samples),
        largest_magnitude_change_percent=max(abs(r['change_from_unbalanced_percent']) for r in comparisons),
        interpretation=('The deeper low yaw dip survives mean pitch balance, '
            'with less than 1% change at the native dip frequency. Restoring '
            'pitch balance does not fix the other discrepancies. This does '
            'not isolate incidence, normal acceleration or preload, identify '
            'native settings, locate conditional extrema or validate a periodic trajectory.'))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tag', required=True)
    args = vars(parser.parse_args())
    inputs = [ROOT/'scripts/check_daedalus_pitch_balanced_base.py',
        ROOT/'scripts/report_daedalus_untrimmed_base.py',
        ROOT/'scripts/check_daedalus_untrimmed_base.py',
        ROOT/'scripts/check_daedalus_regular_mesh_response.py',
        LEVEL/'comparison.csv', LEVEL/'reference.json',
        PRIOR/'result.json', PRIOR/'source-pins.json']
    for name in STAGES:
        inputs.extend(study.STUDY/name/file for file in ['plan.json', 'result.json', 'terminal.json'])
    run(study.STUDY, args['tag'], inputs, report, args, __file__)
