"""Export the archived-input comparison without concealing geometry/convention gaps."""
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
path = ROOT/'docs/validation/sa2.json'
data = json.loads(path.read_text())
plt.rcParams.update({'font.size': 10, 'svg.fonttype': 'none', 'svg.hashsalt': 'openswing-sa2'})
fig, axes = plt.subplots(2, 2, figsize=(12, 9), layout='constrained')
styles = [('current_fixed_zero', '#167a88', '-', 'Current · PG 0'),
          ('current_speed_derived', '#167a88', '--', 'Current · PG V/a'),
          ('frozen_fixed_zero', '#7753aa', '-', 'Frozen · PG 0'),
          ('frozen_speed_derived', '#7753aa', '--', 'Frozen · PG V/a')]
for ax in axes.flat:
    ax.grid(alpha=.2)
    ax.set_xlabel('Incidence [degrees]')
for column, coefficient in enumerate(['CL', 'CD']):
    archived = data['reference']['aswing_5_96']
    measured = data['reference']['primary_table_4']
    primary_key = 'CL' if coefficient == 'CL' else 'CD_pressure'
    valid = [p for p in measured if p[primary_key] is not None]
    axes[0, column].plot([p['alpha_deg'] for p in archived], [p[coefficient] for p in archived],
                        'x:', color='#bc6035', label='Archived ASWING 5.96', linewidth=1.1)
    axes[1, column].plot([p['alpha_deg'] for p in valid], [p[primary_key] for p in valid],
                        's', color='#303030', fillstyle='none', label='Experiment · pressure integral', markersize=5)
    for mode, color, line, label in styles:
        cases = [data['cases'][i] for i in data['comparisons'][mode]['case_indices']]
        x = [c['specification']['alpha_deg'] for c in cases]
        for row, key in enumerate([coefficient, coefficient+'_pressure']):
            axes[row, column].plot(x, [c['result'][key] for c in cases], marker='.', linestyle=line,
                                   color=color, linewidth=1.2, label=label)
    axes[0, column].set_title('Archived input · total '+('lift' if column == 0 else 'drag'))
    axes[1, column].set_title('Geometry differs · pressure-only '+('lift' if column == 0 else 'drag'))
    for row in [0, 1]:
        axes[row, column].set_ylabel(coefficient+(' · friction removed' if row else ''))
        axes[row, column].legend(fontsize=8, loc='upper left')
axes[1, 1].annotate('No measured drag at 2.1°', xy=(2.1, 0), xytext=(6., .002), fontsize=8,
                    arrowprops={'arrowstyle': '->', 'color': '#555'}, color='#555')
fig.suptitle('Archived SA-2 swept-wing case · comparison and setup audit', fontsize=15)
meshes = sorted({c['panels'] for c in data['comparisons'].values()})
fig.supxlabel(f'Unchanged input · {"/".join(map(str, meshes))} intervals (finest complete polars) · no fitted parameters\n'
              'Archive: 35.265° sweep, 0.508 m normal chord. Experiment: 45° sweep, 0.508 m streamwise chord, curved tips.\n'
              'Table 4 has no drag at 2.1°. Some 400-interval cases fail the local-Mach guard; no full-range mesh convergence is claimed.', fontsize=9)
digest = hashlib.sha256(path.read_bytes()).hexdigest()
for extension in ['svg', 'pdf']:
    metadata = ({'Date': None, 'Creator': 'OpenSwing', 'Description': f'sa2.json SHA-256 {digest}'}
                if extension == 'svg' else
                {'CreationDate': None, 'ModDate': None, 'Creator': 'OpenSwing', 'Subject': f'sa2.json SHA-256 {digest}'})
    fig.savefig(ROOT/f'docs/validation/sa2.{extension}', metadata=metadata)
if args.preview:
    fig.savefig(args.preview, dpi=150)
plt.close(fig)
