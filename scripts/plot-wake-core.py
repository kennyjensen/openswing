"""Standalone figures for the independently integrated close-wake example."""
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT = Path(__file__).resolve().parents[1]
data = json.loads((ROOT/'docs/validation/wake-core.json').read_text())
fig, axes = plt.subplots(1, 3, figsize=(12, 3.8), layout='constrained')
for ratio, color in [(0., '#386cb0'), (.25, '#e08214'), (1., '#1b9e77')]:
    case = next(c for c in data['cases'] if c['specification'] == dict(panels=16, ratio=ratio))
    y = -np.cos((np.arange(16)+.5)*np.pi/16)
    label = f'r/c = {ratio:g}'+(' (spacing floor)' if ratio == 0 else '')
    for i in range(2):
        axes[i].plot(y, case['result']['gamma'][i*16:(i+1)*16], color=color, label=label)
        axes[i].plot(y, case['reference']['gamma'][i*16:(i+1)*16], '.', color=color, markersize=4)
    axes[2].plot(y, case['result']['core'][:16], color=color, label=label)
for ax in axes:
    ax.set_xlabel('Span coordinate / semispan'); ax.grid(alpha=.2)
axes[0].set(title='Upstream surface', ylabel='Circulation [m²/s]')
axes[1].set(title='Downstream surface', ylabel='Circulation [m²/s]')
axes[2].set(title='Upstream source core', ylabel='Radius [m]')
axes[0].legend(fontsize=8)
fig.suptitle('Close wake encounter · 16 intervals per surface · 30 m/s\nLines: OpenSwing; dots: independent vortex-line quadrature', fontsize=11)
for suffix in ['svg', 'pdf']:
    fig.savefig(ROOT/f'docs/validation/wake-core.{suffix}')
