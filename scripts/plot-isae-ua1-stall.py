"""Plot retained full histories; no recomputation or resampling of production."""
import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads(path.read_text())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', type=Path, required=True)
    args = parser.parse_args()
    base = args.base.resolve()
    plan = read(base/'plan.json')
    reference = read(base/'reference.json')['references']['DOP853']['rows']
    period = reference[-1]['time']
    x = np.array([r['time'] for r in reference])/period
    fig, axes = plt.subplots(3, 1, figsize=(8, 8), sharex=True, constrained_layout=True)
    for ax, key in zip(axes, ('CL', 'CDp_fixed', 'section_cl')):
        ax.plot(x, [r[key] for r in reference], color='#111827', lw=2, label='Independent equations')
    for steps, color in [(160, '#d97706'), (640, '#2563eb')]:
        rows = []
        for part in range(steps//plan['segment_steps']):
            rows.extend(read(base/f'audit-n{steps}-part{part:03d}.json')['rows'])
        assert len(rows) == steps+1
        x = np.array([r['time'] for r in rows])/period
        for ax, key in zip(axes[:2], ('CL', 'CDp_fixed')):
            ax.plot(x, [r[key] for r in rows], color=color, lw=1.1, ls='--', label=f'OpenSwing, {steps} steps')
        cl = np.array([r['section_cl'] for r in rows])
        axes[2].plot(x, np.min(cl, axis=1), color=color, lw=1.1, ls='--')
        axes[2].fill_between(x, np.min(cl, axis=1), np.max(cl, axis=1), color=color, alpha=.3)
    axes[2].axhline(plan['section']['clmax'], color='#6b7280', ls=':', label='Declared upper stall limit')
    for ax, label in zip(axes, ('Fixed-axis lift coefficient', 'Pressure drag / fixed qS', 'Bound-vortex section cl')):
        ax.set_ylabel(label)
        ax.grid(alpha=.25)
        ax.set_xlim(0, 1)
    axes[0].legend(fontsize=9, loc='best')
    axes[2].legend(fontsize=9, loc='best')
    axes[2].set_xlabel('Time / heave period')
    axes[0].set_title('UA-1 stall supplement: 9°, k = 0.94, peak-to-peak A/c = 0.5\nFirst cycle from steady equilibrium; no native ASWING comparison')
    destination = ROOT/'docs/validation/isae-ua1-stall-20261102'
    for extension in ('svg', 'png'):
        fig.savefig(destination.with_suffix('.'+extension), dpi=150)
    plt.close(fig)


if __name__ == '__main__':
    main()
