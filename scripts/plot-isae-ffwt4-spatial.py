"""Plot authenticated FFWT-4 initial mesh comparisons without extrapolation."""
import argparse
from pathlib import Path
import re

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from isae_ffwt4_evidence import pin, read, require, write

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--assessment', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    report = read(args.assessment)
    require(report['status'] == 'INITIAL_SPATIAL_STUDY_ASSESSED', 'Audited spatial study required')
    palette = ROOT/'web/plot-colors.js'
    match = re.search(r'export const plotColors = Object.freeze\(\[(.*?)\]\);', palette.read_text(), re.S)
    colors = re.findall(r'#[0-9a-fA-F]{6}', match[1])
    rows, pairs = report['samples'], report['comparisons']
    xs = [r['nominal'] for r in rows]
    require(all(r['native'] == rows[0]['native'] for r in rows), 'Native reference changed between meshes')
    fig, axes = plt.subplots(3, 1, figsize=(9, 8), sharex=True)
    axes[0].axhline(rows[0]['native'], color=colors[0], label='Archived ASWING at t=0')
    axes[0].plot(xs, [r['root_moment'] for r in rows], 'o-', color=colors[1], label='OpenSwing equilibrium')
    axes[0].set_ylabel('Root Mc′ (N m)')
    axes[0].legend(frameon=False, fontsize=9)
    axes[1].plot(xs, [r['native_error_percent'] for r in rows], 'o-', color=colors[1])
    axes[1].set_ylabel('Native error (%)')
    axes[1].set_ylim(bottom=0)
    for name, label, color, style in zip(('root_moment','displacement','rotation_vector'),
            ('Root moment','Nodal displacement','Rotation vector'), colors[1:4], ('o-','s--','^-.')):
        changes = [p['gates'][name]['maximum_percent'] for p in pairs]
        require(all(v > 0 for v in changes), 'Log plot requires positive measured changes')
        axes[2].plot([p['nominal'][1] for p in pairs], changes, style, color=color, lw=2, label=label)
    axes[2].axhline(.1, color='#666666', linestyle=':', label='0.1% numerical gate')
    axes[2].set_yscale('log')
    axes[2].set_ylabel('Adjacent-mesh change (%)')
    axes[2].set_xlabel('Nominal cosine intervals (actual beam nodes)')
    axes[2].legend(frameon=False, fontsize=8)
    for axis in axes:
        axis.set_xscale('log', base=2)
        axis.grid(alpha=.2)
        axis.spines[['top','right']].set_visible(False)
    axes[2].set_xticks(xs, [f'{r["nominal"]}\n({r["nodes"]} nodes)' for r in rows])
    fig.suptitle('ISAE FFWT-4 · Fixed-1: initial spatial refinement')
    fig.text(.5,.012,'Same literal inputs and archived kernel. No fitted parameters. Full gust-history mesh accuracy remains open.',
             ha='center', fontsize=8)
    fig.tight_layout(rect=(0,.035,1,.96))
    args.output_dir.mkdir(parents=True, exist_ok=False)
    for suffix in ('png','svg'):
        fig.savefig(args.output_dir/('comparison.'+suffix), dpi=150, bbox_inches='tight')
    plt.close(fig)
    write(args.output_dir/'inputs.json', dict(inputs=[pin(args.assessment),pin(palette),pin(__file__)]))


if __name__ == '__main__':
    main()
