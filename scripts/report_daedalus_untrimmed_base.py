"""Compare the conditional accelerating-state samples without another solve."""
import argparse
from pathlib import Path

from check_daedalus_load_sensitivity import ROOT, read, write, pin
from daedalus_bounded_job import run
import check_daedalus_untrimmed_base as study
import check_daedalus_regular_mesh_response as level

CHANNELS = ['yaw_rate', 'roll_rate', 'sideslip', 'bank']
STAGES = ['init', *[f'trim-geometry-{i:02d}' for i in range(7)],
          'trim-other', 'trim-joined', 'trim-ranked', 'equilibrium-0',
          'equilibrium-1', 'base-audit', *[f'geometry-{i:02d}' for i in range(7)],
          'geometry', 'other', 'mass', 'assembled', 'response', 'native-features']


def report(folder, arguments):
    import csv
    import math
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.ticker import LogLocator, FuncFormatter, NullFormatter

    sources, receipts = {}, {}
    for name in STAGES:
        stage = study.STUDY/name
        terminal = read(stage/'terminal.json')
        assert terminal['returncode'] == 0 and terminal['process_reaped']
        assert terminal['inputs_unchanged'] and not terminal['timed_out']
        receipts[name] = terminal
        for path, digest in read(stage/'plan.json')['inputs_sha256'].items():
            assert path not in sources or sources[path] == digest, path
            sources[path] = digest
    for path, digest in sources.items():
        assert pin(Path(path)) == digest, path
    write(folder/'source-pins.json', sources)
    with (level.STUDY/'report/comparison.csv').open() as stream:
        baseline = list(csv.DictReader(stream))
    samples = []
    for name in ['response', 'native-features']:
        data = read(study.STUDY/name/'result.json')
        assert data['channels'] == CHANNELS
        samples.extend(data['samples'])
    samples.sort(key=lambda r: r['frequency_hz'])
    comparisons = []
    for sample in samples:
        for i, channel in enumerate(CHANNELS):
            old = min((r for r in baseline if r['channel'] == channel),
                key=lambda r: abs(float(r['frequency_hz'])-sample['frequency_hz']))
            # A few CLI frequencies are rounded at the 11th decimal place.
            # No curve interpolation or nearest distant sample is accepted.
            assert abs(float(old['frequency_hz'])-sample['frequency_hz']) < 1e-9
            value = sample['magnitude'][i]
            assert math.isclose(value, math.hypot(sample['real'][i], sample['imag'][i]), rel_tol=2e-14)
            reference, prior = float(old['reference_magnitude']), float(old['magnitude'])
            comparisons.append(dict(channel=channel, frequency_hz=sample['frequency_hz'],
                reference_frequency_hz=float(old['frequency_hz']), unit=old['unit'],
                level_flight=prior, conditional_untrimmed=value,
                reference=reference, reference_graphic_min=float(old['reference_graphic_min']),
                reference_graphic_max=float(old['reference_graphic_max']),
                level_error_percent=100*(prior/reference-1),
                conditional_error_percent=100*(value/reference-1),
                change_from_level_percent=100*(value/prior-1)))
    with (folder/'comparison.csv').open('x', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(comparisons[0]))
        writer.writeheader()
        writer.writerows(comparisons)

    native = read(level.STUDY/'report/reference.json')
    fig, axes = plt.subplots(2, 2, figsize=(12, 8.4), constrained_layout=True)
    for i, (ax, channel, title) in enumerate(zip(axes.flat, CHANNELS,
            ['Yaw rate', 'Roll rate', 'Sideslip', 'Bank'])):
        vertices = native['channels'][channel]['vertices']
        old = sorted((r for r in baseline if r['channel'] == channel), key=lambda r: float(r['frequency_hz']))
        ax.loglog([r[2] for r in vertices], [r[3] for r in vertices], '--',
            color='#2378b5', lw=1.6, label='Drela drawing; operating point unknown')
        ax.loglog([float(r['frequency_hz']) for r in old], [float(r['magnitude']) for r in old],
            color='#b83439', lw=1.6, label='OpenSwing: trimmed level flight')
        ax.loglog([r['frequency_hz'] for r in samples], [r['magnitude'][i] for r in samples],
            linestyle='none', marker='o', markersize=6, markerfacecolor='none',
            markeredgewidth=1.7, color='#a46700', label='Conditional accelerating state: 8 samples')
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
    axes[0, 0].legend(fontsize=8, loc='upper left')
    fig.suptitle('Daedalus at 6.7 m/s: operating-state diagnostic\n'
        'Orange markers: zero incidence, attitude, controls and power; solved accelerations', fontsize=12)
    fig.savefig(folder/'comparison.svg')
    fig.savefig(folder/'comparison.png', dpi=140)
    plt.close(fig)
    return dict(qualification=study.QUALIFICATION, frequency_samples=len(samples),
        reference_frequency_matching_tolerance_hz=1e-9, comparisons=comparisons,
        base=read(study.STUDY/'base-audit/result.json'),
        assembly=read(study.STUDY/'assembled/result.json'),
        maximum_scaled_matrix_residual=max(max(r['checks']['scaled_residuals']) for r in samples),
        stage_receipts=receipts, interpretation=(
            'The low yaw dip is sensitive to the operating state. This conditional '
            'case improves that sampled feature but worsens the low-frequency yaw '
            'and high-frequency roll response. It does not match the complete '
            'native response or identify native settings. No extrema of the '
            'conditional response were located and no physical parameters were fitted.'))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tag', required=True)
    args = vars(parser.parse_args())
    inputs = [ROOT/'scripts/check_daedalus_untrimmed_base.py',
        ROOT/'scripts/check_daedalus_regular_mesh_response.py',
        level.STUDY/'report/comparison.csv', level.STUDY/'report/reference.json']
    for name in STAGES:
        inputs.extend(study.STUDY/name/file for file in ['plan.json', 'result.json', 'terminal.json'])
    run(study.STUDY, args['tag'], inputs, report, args, __file__)
