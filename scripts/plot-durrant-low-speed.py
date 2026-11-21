"""Plot the finite-frequency positive-airspeed limit and mesh convergence."""
import json
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import NullLocator

ROOT = Path(__file__).resolve().parents[1]
study = json.loads((ROOT/'docs/validation/durrant-low-speed.json').read_text())
if len(study['cases']) != 20:
    raise ValueError('Complete the planned native study first')
plt.rcParams.update({'font.size': 10, 'axes.spines.top': False, 'axes.spines.right': False,
                     'svg.fonttype': 'none'})
fig, axes = plt.subplots(1, 3, figsize=(13, 4.6), layout='constrained')
for wing, color in [('25', '#196f79'), ('75', '#915bb1')]:
    check = study['checks'][wing]
    label = f'{wing}% spar wing'
    error = np.max(check['mesh_relative_frequency_errors'], axis=1)*100
    speed = check['speed_m_s']
    decay = np.max(np.abs(check['growth_per_s']), axis=1)
    circulation = np.max(check['circulation_per_mechanical_amplitude'], axis=1)
    axes[0].loglog([8, 16, 32], error, 'o-', color=color, label=label)
    axes[1].loglog(speed, decay, 'o-', color=color, label=label)
    axes[2].loglog(speed, circulation, 'o-', color=color, label=label)
axes[0].set(xlabel='Requested structural intervals', ylabel='Maximum frequency error (%)',
            title='Nine modes vs independent still air\nMean airspeed = 0.01 m/s',
            xticks=[8, 16, 32], xticklabels=['8', '16', '32'])
axes[0].xaxis.set_minor_locator(NullLocator())
axes[1].set(xlabel='Mean airspeed (m/s)', ylabel='Maximum |growth rate| (1/s)',
            title='Aerodynamic damping tends to zero\nN = 16, circulation lag enabled')
axes[2].set(xlabel='Mean airspeed (m/s)', ylabel='Maximum circulation / amplitude (m/s)',
            title='Circulation tends to zero\nFixed mechanical mode amplitude')
for ax in axes:
    ax.grid(which='both', alpha=.2)
fig.legend(*axes[0].get_legend_handles_labels(), loc='outside lower center', ncol=2, frameon=False)
fig.suptitle('Durrant wing reconstruction: positive-airspeed modal limit\nAir inertia remains; exact stagnation and experimental flutter are unverified', fontsize=12)
for suffix in ['svg', 'pdf', 'png']:
    target = ROOT/f'docs/validation/durrant-low-speed.{suffix}'
    fig.savefig(target, dpi=170)
    print(target.relative_to(ROOT))
