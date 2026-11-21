"""Plot saved Daedalus motion-arm sensitivity; no model evaluation or solving."""
import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter, LogLocator, NullFormatter
import numpy as np


def logarithmic_grid(ax):
    for axis in (ax.xaxis, ax.yaxis):
        axis.set_major_locator(LogLocator(base=10))
        axis.set_major_formatter(FuncFormatter(lambda value, _: f'{value:g}'))
        axis.set_minor_locator(LogLocator(base=10, subs=np.arange(2, 10)))
        axis.set_minor_formatter(NullFormatter())
    ax.grid(which='major', color='#aeb4bd', linewidth=.7)
    ax.grid(which='minor', color='#dfe2e6', linewidth=.45)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--output-prefix', type=Path, required=True)
    args = parser.parse_args()
    report = json.loads(args.report.read_text())
    baseline = report['baseline_samples']
    reference = report['reference_samples']
    assert len(baseline) == 203
    frequencies = np.array([row['frequency_Hz'] for row in baseline])
    assert np.all(np.diff(frequencies) > 0)
    magnitude = [abs(complex(row['yaw']['real'], row['yaw']['imag'])) * 180 / np.pi
                 if row['available'] else np.nan for row in baseline]
    with plt.rc_context({'font.size': 10, 'axes.titlesize': 11, 'svg.fonttype': 'none'}):
        fig, (response, changes) = plt.subplots(1, 2, figsize=(12, 4.8))
        response.loglog([row['frequency_Hz'] for row in reference],
                        [row['magnitude_deg_s_per_F3'] for row in reference],
                        color='#62666d', linestyle='--', linewidth=1.3,
                        label='Drela drawing (operating point unknown)')
        response.loglog(frequencies, magnitude, color='#ff4a3d', linewidth=1.5,
                        label='Current convention, 6.7 m/s, 16 panels')
        for variant, color, marker, label in [
                ('physical_force', '#ff9f1a', 'o', 'Material force-point velocity'),
                ('physical_both', '#8acf41', 'x', 'Material force/control-point velocity')]:
            rows = report['motion_arm_variants'][variant]['samples']
            assert len(rows) == 7
            assert all(row['frequency_Hz'] in frequencies for row in rows)
            available = [row for row in rows if row['available']]
            f = [row['frequency_Hz'] for row in available]
            response.loglog(f, [row['magnitude_deg_s_per_F3'] for row in available],
                            color=color, marker=marker, markerfacecolor='none',
                            markersize=7, markeredgewidth=1.5, linestyle='none', label=label)
            # Samples are intentionally unconnected; no sweep between them was made.
            changes.loglog(f, [100 * row['relative_complex_change']
                               if row['relative_complex_change'] else np.nan
                               for row in available], color=color, marker=marker,
                           markerfacecolor='none', markersize=7, markeredgewidth=1.5,
                           linestyle='none', label=label)
        response.set(xlim=(.1, 10), ylim=(.01, 1), xlabel='Frequency [Hz]',
                     ylabel='Yaw magnitude [deg/s per native F3]',
                     title='Rotational-velocity convention sensitivity')
        changes.set(xlim=(.1, 10), xlabel='Frequency [Hz]',
                    ylabel='Complex change from current convention [%]',
                    title='Seven selected samples; same physical trim')
        for ax in (response, changes):
            logarithmic_grid(ax)
            ax.legend(fontsize=8, framealpha=.96)
        fig.text(.5, .015, 'Diagnostic conventions only; no production change or matched-reference validation.',
                 ha='center', fontsize=9)
        fig.tight_layout(rect=(0, .04, 1, 1))
        for suffix in ('.svg', '.png', '.pdf'):
            fig.savefig(args.output_prefix.with_suffix(suffix), dpi=180)
        plt.close(fig)


if __name__ == '__main__':
    main()
