"""Plot complete adjacent FFWT-4 histories and their unscaled time-grid differences."""
import argparse
from pathlib import Path
import re

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from isae_ffwt4_evidence import pin, read, require, write

ROOT = Path(__file__).resolve().parents[1]


def checked(record):
    require(pin(record['path']) == record, 'Changed plot input: '+record['path'])
    return read(record['path'])


def values(data):
    divisor = data['divisor']
    require(data['complete'], 'Do not plot a partial history as a complete comparison')
    samples = [data['samples'][str(i)] for i in range(199*divisor+1)]
    t = np.array([s['time'] for s in samples])
    moment = np.array([s['moment'] for s in samples])
    require(np.isfinite(t).all() and np.isfinite(moment).all(), 'Nonfinite plot input')
    return t, moment


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--assessment', type=Path, required=True)
    parser.add_argument('--previous', type=Path)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    report = read(args.assessment)
    require(report['status'] == 'ADJACENT_GRIDS_ASSESSED', 'Audited adjacent grids required')
    coarse, fine = (checked(report[name]) for name in ('coarser_assessment', 'finer_assessment'))
    rows = [r for r in fine['checks'] if r['name'].startswith('FFWT_Fixed-1:')]
    require(len(rows) == 200, 'Native reference coverage changed')
    native = np.array([r['expected'] for r in rows])
    palette = ROOT/'web/plot-colors.js'
    match = re.search(r'export const plotColors = Object.freeze\(\[(.*?)\]\);', palette.read_text(), re.S)
    colors = re.findall(r'#[0-9a-fA-F]{6}', match[1])
    fig, axes = plt.subplots(3, 1, figsize=(9, 8), sharex=True)
    axes[0].plot([r['time'] for r in rows], native, color=colors[0], label='Archived ASWING')
    for data, color, style in [(coarse, colors[1], '--'), (fine, colors[2], ':')]:
        t, moment = values(data)
        axes[0].plot(t, moment, color=color, linestyle=style, label=f'OpenSwing · dt={data["dt"]} s')
        stride = data['divisor']
        axes[1].plot(t[::stride], 100*(moment[::stride]-native)/abs(native), color=color, linestyle=style)
    axes[0].set_ylabel('Root Mc′ (N m)')
    axes[0].legend(frameon=False, fontsize=8)
    axes[1].set_ylabel('Native error (%)')
    axes[1].axhline(0, color='#888', lw=.7)
    comparisons = [(report, coarse, fine, colors[2])]
    inputs = [pin(args.assessment), report['coarser_assessment'], report['finer_assessment'], pin(palette), pin(__file__)]
    if args.previous:
        previous = read(args.previous)
        require(previous['finer_assessment'] == report['coarser_assessment'], 'Previous refinement does not join this one')
        previous_coarse = checked(previous['coarser_assessment'])
        comparisons.insert(0, (previous, previous_coarse, coarse, colors[3]))
        inputs += [pin(args.previous), previous['coarser_assessment']]
    for comparison, low, high, color in comparisons:
        ct, cv = values(low)
        ft, fv = values(high)
        require(high['divisor'] == 2*low['divisor'], 'Non-adjacent plot grids')
        require(np.max(abs(ct-ft[::2])) <= 1e-10, 'Different physical clocks')
        common = fv[::2]
        scale = max(abs(common-common[0]))
        gate = comparison['all_shared_ticks']['gates']['gust_increment']
        require(abs(scale-gate['scale']) < 1e-12, 'Plot normalization differs from the audited gate')
        error = 100*((cv-cv[0])-(common-common[0]))/scale
        require(abs(max(abs(error))-gate['maximum_percent_of_scale']) < 1e-10, 'Plot disagrees with accuracy audit')
        axes[2].plot(ct, error, color=color, label=f'dt {low["dt"]} → {high["dt"]} s')
    axes[2].axhspan(-.1, .1, color=colors[2], alpha=.15, label='0.1% increment gate')
    axes[2].set(ylabel='Increment change (%)', xlabel='Time (s)')
    axes[2].legend(frameon=False, fontsize=8)
    for ax in axes:
        ax.grid(alpha=.2)
        ax.spines[['top', 'right']].set_visible(False)
    fig.suptitle('ISAE FFWT-4 · Fixed-1: adjacent time resolutions')
    fig.text(.5, .015, 'Exact common ticks; identical pinned physics and nominal32 mesh. Other histories and spatial accuracy remain open.',
             ha='center', fontsize=8)
    fig.tight_layout(rect=(0, .035, 1, .96))
    args.output_dir.mkdir(parents=True, exist_ok=False)
    for suffix in ('png', 'svg'):
        fig.savefig(args.output_dir/('comparison.'+suffix), dpi=150, bbox_inches='tight')
    plt.close(fig)
    write(args.output_dir/'inputs.json', dict(inputs=inputs))


if __name__ == '__main__':
    main()
