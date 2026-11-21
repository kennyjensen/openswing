"""Plot audited loaded structural response and real-inertia comparisons."""
import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import NullLocator
import numpy as np


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    audit = json.loads((args.root/'audit-final.json').read_text())
    assert audit['status'] == 'PASS'
    plt.rcParams.update({'font.size': 10, 'axes.spines.top': False, 'axes.spines.right': False,
                         'svg.fonttype': 'none', 'pdf.fonttype': 42})
    fig, axes = plt.subplots(1, 2, figsize=(10.8, 4.5))
    for wing, color, marker in [('25', '#127f78', 'o'), ('75', '#bf603f', 's')]:
        rows = [c for c in audit['cases'] if c['wing'] == wing]
        n = [r['panels'] for r in rows]
        axes[0].loglog(n, [r['tip_compliance_column_relative'] for r in rows], marker=marker,
                       color=color, label=wing+'% spar', linewidth=1.8)
        axes[1].semilogy(n, [r['projected_mass_relative'] for r in rows], marker=marker,
                         color=color, linestyle=':', label=wing+'% spar', linewidth=1.3)
    n = np.array([8, 16, 32])
    anchor = next(c['tip_compliance_column_relative'] for c in audit['cases'] if c['wing'] == '25' and c['panels'] == 8)
    axes[0].loglog(n, anchor*(8/n)**2, '--', color='#777777', linewidth=1, label='N⁻² guide')
    axes[0].set_title('Six tip-load responses\nIndependent continuum vs mixed beam')
    axes[0].set_ylabel('Worst relative difference per input column')
    axes[1].set_title('Real inertia at the same saved geometry\nIndependent kinetic energy vs load transfer')
    axes[1].set_ylabel('Relative projected mass-matrix difference')
    for ax in axes:
        ax.set_xticks(n, labels=n)
        ax.xaxis.set_minor_locator(NullLocator())
        ax.set_xlabel('Requested intervals (actual: 10, 18, 34)')
        ax.grid(True, which='major', alpha=.2)
        ax.legend(frameon=False, fontsize=9)
    fig.suptitle('Loaded-wing mechanics with frozen nodal loads', fontsize=14)
    fig.text(.5, .025, 'Frozen load sets differ by mesh. Aerodynamic feedback and flutter/experimental agreement are outside this check.',
             ha='center', fontsize=9)
    fig.tight_layout(rect=(0, .07, 1, .94))
    for suffix in ['svg', 'png', 'pdf']:
        fig.savefig(args.output.with_suffix('.'+suffix), dpi=180)
    plt.close(fig)


if __name__ == '__main__':
    main()
