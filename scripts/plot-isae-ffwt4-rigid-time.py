"""Plot synthetic rigid-tip temporal error against an independent exact solution."""
import argparse
from pathlib import Path
import re

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import ScalarFormatter
from isae_ffwt4_evidence import pin, read, require, write

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--assessment', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    data = read(args.assessment)
    require(data['status'] == 'INTEGRATED_RIGID_TIP_ASSESSED' and data['trajectories'] == 6,
            'Complete oscillator assessment required')
    palette = ROOT/'web/plot-colors.js'
    match = re.search(r'export const plotColors = Object.freeze\(\[(.*?)\]\);', palette.read_text(), re.S)
    colors = re.findall(r'#[0-9a-fA-F]{6}', match[1])
    quantities = dict(angle='Hinge angle', rate='Angular velocity',
        angular_acceleration='Angular acceleration', position='Point position',
        velocity='Point velocity', acceleration='Point acceleration')
    fig, axes = plt.subplots(1, 2, figsize=(10, 5), sharey=True)
    for ax, representation in zip(axes, ('pylon', 'extension')):
        rows = [r for r in data['studies'] if r['representation'] == representation]
        for color, (key, label) in zip(colors, quantities.items()):
            ax.loglog([r['dt'] for r in rows], [100*r['maximum_scaled_errors'][key] for r in rows],
                      color=color, marker='o', markersize=4, label=label)
        ax.axhline(.1, color='#777', linestyle=':', label='0.1% numerical gate')
        ax.set(title='Endpoint pylon' if representation == 'pylon' else 'Explicit rigid extension',
               xlabel='BDF2 maximum step (s)', xticks=[.005, .01, .02])
        ax.xaxis.set_major_formatter(ScalarFormatter())
        ax.grid(which='major', alpha=.35); ax.grid(which='minor', alpha=.12)
        ax.spines[['top', 'right']].set_visible(False)
    axes[0].set_ylabel('Maximum error / declared physical scale (%)')
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc='lower center', ncol=3, frameon=False, fontsize=8)
    fig.suptitle('Finite-rotation tip oscillator · independent exact solution\n'
                 'Two point masses · vacuum · 0.2 s histories · no rejected steps', fontsize=12)
    fig.tight_layout(rect=(0, .16, 1, .9))
    args.output_dir.mkdir(parents=True, exist_ok=False)
    for suffix in ('png', 'svg'):
        fig.savefig(args.output_dir/('convergence.'+suffix), dpi=150, bbox_inches='tight')
    plt.close(fig)
    write(args.output_dir/'inputs.json', dict(inputs=[pin(args.assessment), pin(palette), pin(__file__)]))


if __name__ == '__main__':
    main()
