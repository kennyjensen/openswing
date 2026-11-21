"""Publication/export figure for the recorded SA-1 comparison, without fitting."""
import argparse
import hashlib
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--preview')
args = parser.parse_args()
path = ROOT/'docs/validation/sa1.json'
data = json.loads(path.read_text())
plt.rcParams.update({'font.size': 10, 'svg.fonttype': 'none', 'svg.hashsalt': 'openswing-sa1'})
fig, axes = plt.subplots(2, 2, figsize=(11.6, 8.3), layout='constrained')
for ax in axes.flat:
    ax.grid(alpha=.2)
    ax.set_xlabel('Incidence [degrees]')
for column, coefficient in enumerate(['CL', 'CD']):
    ax = axes[0, column]
    ex = data['reference']['experiment'][coefficient]
    ref = data['reference']['aswing_5_96']
    ax.plot([p['alpha_deg'] for p in ex], [p['value'] for p in ex], 's', color='#303030',
            markersize=4.5, fillstyle='none', label='Experiment · ISAE digitization')
    ax.plot([p['alpha_deg'] for p in ref], [p[coefficient] for p in ref], 'x--', color='#bc6035',
            markersize=5, linewidth=1, label='Archived ASWING 5.96')
    for mode, color, label in [('fixed_zero', '#167a88', 'OpenSwing · fixed PG Mach 0'),
                               ('speed_derived', '#7753aa', 'OpenSwing · PG Mach V/a')]:
        indices = data['comparisons'][mode]['aswing_case_indices']
        cases = [data['cases'][i] for i in indices]
        ax.plot([c['specification']['alpha_deg'] for c in cases],
                [c['result'][coefficient] for c in cases], '.-', color=color, linewidth=1.3, label=label)
        matching = [data['cases'][i] for i in data['comparisons'][mode]['experiment_case_indices'][coefficient]]
        axes[1, column].plot([p['alpha_deg'] for p in ex],
            [c['result'][coefficient]-p['value'] for c, p in zip(matching, ex)], '.-', color=color,
            label=label)
    ax.set_ylabel(f'${coefficient[0]}_{coefficient[1:]}$')
    ax.set_title('Lift coefficient' if coefficient == 'CL' else 'Drag coefficient')
    ax.legend(fontsize=8, loc='upper left')
    axes[1, column].axhline(0, color='#888', linewidth=.8)
    axes[1, column].set_ylabel(f'Computed {coefficient} − experimental {coefficient}')
    axes[1, column].set_title('Difference at each measured incidence')
fig.suptitle('Straight rigid wing · archived SA-1 case', fontsize=15)
fig.supxlabel('Unchanged archived input · 400 intervals · no parameter fitting\n'
              'Experimental series: ISAE reduction of Applin, NASA TM-110148 (1995). Original PG/stall settings uncertain.\n'
              'Report prose and archived input differ. Numerical convergence does not remove the drag discrepancy.', fontsize=9)
digest = hashlib.sha256(path.read_bytes()).hexdigest()
for extension in ['svg', 'pdf']:
    metadata = ({'Date': None, 'Creator': 'OpenSwing', 'Description': f'sa1.json SHA-256 {digest}'}
                if extension == 'svg' else
                {'CreationDate': None, 'ModDate': None, 'Creator': 'OpenSwing', 'Subject': f'sa1.json SHA-256 {digest}'})
    fig.savefig(ROOT/f'docs/validation/sa1.{extension}', metadata=metadata)
if args.preview:
    fig.savefig(args.preview, dpi=150)
plt.close(fig)
