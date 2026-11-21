"""Plot the structural reconstruction and retain the distinction from experiment."""
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import NullLocator

ROOT = Path(__file__).resolve().parents[1]
r = json.loads((ROOT/'docs/validation/durrant-structure.json').read_text())
if not r['complete_planned_grid']:
    raise ValueError('Complete the planned native study first')
plt.rcParams.update({'font.size': 10, 'axes.spines.top': False, 'axes.spines.right': False,
                     'svg.fonttype': 'none'})
fig, axes = plt.subplots(1, 3, figsize=(13, 4.8), layout='constrained')
colors = ['#196f79', '#6797a0', '#915bb1', '#cf793d']
labels = ['OpenSwing vacuum, N=32', 'Independent still-air sensitivity', 'Reported ASWING', 'Ground vibration test']
for ax, mode, title in zip(axes[:2], [0, 1], ['First flapwise mode', 'First torsional mode']):
    values = []
    for wing in ['25', '75']:
        c = next(c for c in r['cases'] if c['spec'] == dict(wing=wing, panels=32))
        ref = r['reference']['wings'][wing]['frequencies_Hz']
        values.append([c['frequencies_Hz'][mode], r['still_air_continuum'][wing]['frequencies_Hz'][mode],
                       ref['ASWING'][mode], ref['GVT'][mode]])
    for j, (label, color) in enumerate(zip(labels, colors)):
        ax.bar(np.arange(2)+(j-1.5)*.19, np.array(values)[:, j], width=.18, color=color, label=label)
    ax.set(xticks=[0, 1], xticklabels=['25% spar wing', '75% spar wing'], ylabel='Frequency (Hz)', title=title)
    ax.grid(axis='y', alpha=.2)
    ax.set_axisbelow(True)
for wing, color in zip(['25', '75'], [colors[0], colors[2]]):
    error = np.array(r['checks']['mesh'][wing]['relative_errors'])
    axes[2].loglog([8, 16, 32], 100*np.max(error, axis=1), 'o-', color=color, label=f'{wing}% spar wing')
axes[2].set(xlabel='Requested structural intervals', ylabel='Maximum frequency error (%)',
            title='First nine modes vs independent\nvacuum beam', xticks=[8, 16, 32], xticklabels=['8', '16', '32'])
axes[2].xaxis.set_minor_locator(NullLocator())
axes[2].grid(which='both', alpha=.2)
axes[2].legend(loc='lower left')
fig.legend(*axes[0].get_legend_handles_labels(), loc='outside lower center', ncol=2, frameon=False)
fig.suptitle('Durrant (2024): table-based structural reconstruction\nSetup conflicts prevent an exact ASWING or experimental validation claim', fontsize=12)
for suffix in ['svg', 'pdf', 'png']:
    target = ROOT/f'docs/validation/durrant-structure.{suffix}'
    fig.savefig(target, dpi=170)
    print(target.relative_to(ROOT))
