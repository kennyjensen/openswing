"""Render the saved Daedalus coupling diagnostic without evaluating a model.

The seven coefficient-2 markers are samples, not an interpolated new sweep.
Signed beam contributions are an algebraic decomposition of the saved elastic
solution, not responses obtained by changing one beam at a time.
"""
import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter, LogLocator, NullFormatter
import numpy as np


def value(row):
    return complex(row['real'], row['imag'])


def log_axis(axis):
    axis.set_major_locator(LogLocator(base=10))
    axis.set_major_formatter(FuncFormatter(lambda number, _: f'{number:g}'))
    axis.set_minor_locator(LogLocator(base=10, subs=np.arange(2, 10)))
    axis.set_minor_formatter(NullFormatter())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--output-prefix', type=Path, required=True)
    args = parser.parse_args()
    report = json.loads(args.report.read_text())
    baseline = report['baseline_samples']
    reference = report['reference_samples']
    alternative = report['body_convention']['samples']
    contribution = next(row for row in report['elastic_contributions']['samples']
                        if row['frequency_Hz'] == 1.)
    frequency = np.array([row['frequency_Hz'] for row in baseline])
    assert len(frequency) == 203 and np.all(np.diff(frequency) > 0)
    assert len(alternative) == 7
    assert all(row['frequency_Hz'] in frequency for row in alternative)
    degrees = 180 / np.pi
    magnitude = np.array([abs(value(row['yaw'])) * degrees if row['available']
                          else np.nan for row in baseline])
    assert all(row['available'] for row in baseline)

    with plt.rc_context({'font.size': 10, 'axes.titlesize': 11,
                         'svg.fonttype': 'none'}):
        fig, axes = plt.subplots(1, 2, figsize=(12, 4.8),
                                 gridspec_kw={'width_ratios': [1.15, 1]})
        ax, signed = axes
        ax.loglog([row['frequency_Hz'] for row in reference],
                  [row['magnitude_deg_s_per_F3'] for row in reference],
                  color='#62666d', linestyle='--', linewidth=1.3,
                  label='Drela drawing (operating point unknown)')
        ax.loglog(frequency, magnitude, color='#ff4a3d', linewidth=1.5,
                  label='6.7 m/s, 16 panels, body coefficient 1')
        ax.loglog([row['frequency_Hz'] for row in alternative],
                  [abs(value(row['yaw'])) * degrees if row['available'] else np.nan
                   for row in alternative],
                  color='#ff9f1a', marker='o', markerfacecolor='none',
                  markeredgewidth=1.6, markersize=7, linestyle='none',
                  label='Printed body coefficient 2 (seven samples)')
        ax.set(xlim=(.1, 10), xlabel='Frequency [Hz]',
               ylabel='Yaw magnitude [deg/s per native F3]',
               title='Published body-inertia convention check')
        valid = magnitude[np.isfinite(magnitude) & (magnitude > 0)]
        other = [abs(value(row['yaw'])) * degrees for row in alternative
                 if row['available'] and value(row['yaw']) != 0]
        all_positive = np.r_[valid, other,
                            [row['magnitude_deg_s_per_F3'] for row in reference]]
        ax.set_ylim(10 ** np.floor(np.log10(all_positive.min())),
                    10 ** np.ceil(np.log10(all_positive.max())))
        for axis in (ax.xaxis, ax.yaxis):
            log_axis(axis)
        ax.grid(which='major', color='#aeb4bd', linewidth=.7)
        ax.grid(which='minor', color='#dfe2e6', linewidth=.45)
        ax.legend(loc='upper left', fontsize=8, framealpha=.96)

        names = ['Fixed shape'] + [row['name'] for row in contribution['beams']] + ['Full elastic']
        values = np.array([value(contribution['fixed_yaw'])] +
                          [value(row['yaw']) for row in contribution['beams']] +
                          [value(contribution['full_yaw'])]) * degrees
        assert abs(sum(values[1:-1]) - (values[-1] - values[0])) < 1e-12
        positions = np.arange(len(names))
        signed.barh(positions - .16, values.real, height=.30,
                    color='#ff4a3d', label='Real part')
        signed.barh(positions + .16, values.imag, height=.30,
                    color='#ff9f1a', label='Imaginary part')
        signed.set_yticks(positions, names)
        signed.invert_yaxis()
        signed.axvline(0, color='#474b52', linewidth=.8)
        signed.axhline(.5, color='#b5bac2', linewidth=.7, linestyle=':')
        signed.axhline(5.5, color='#b5bac2', linewidth=.7, linestyle=':')
        signed.set(xlabel='Signed yaw contribution [deg/s per native F3]',
                   title='Elastic contributions at 1 Hz')
        signed.grid(axis='x', color='#e0e3e7', linewidth=.6)
        signed.set_axisbelow(True)
        signed.legend(loc='lower left', fontsize=8)
        fig.suptitle('Daedalus rudder → free-frame yaw: remaining discrepancy', fontsize=13)
        fig.text(.5, .025,
                 'Fixed shape + five complex beam contributions = full response. '
                 'This identity does not isolate causal effects of individual beams.',
                 ha='center', fontsize=8)
        fig.tight_layout(rect=(0, .07, 1, .92), w_pad=2)
        for suffix in ('svg', 'png', 'pdf'):
            fig.savefig(args.output_prefix.with_suffix('.' + suffix), dpi=160)
        plt.close(fig)


if __name__ == '__main__':
    main()
