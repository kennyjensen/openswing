"""Plot saved SA-6 comparisons; performs no aircraft evaluation."""
from pathlib import Path
import json
import re
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / 'docs/validation'
data = json.loads((DEST / 'isae-sa6-current.json').read_text())
rows = [r for r in data['cases'] if r['specification']['panels'] == 160
        and r['reference_kind'] == 'primary_tabulated']
names = list(dict.fromkeys(r['specification']['case'] for r in rows))
palette = (ROOT / 'web/plot-colors.js').read_text()
colors = re.findall(r"'(#\w{6})'", re.search(
    r'plotColors = Object.freeze\(\[(.*?)\]\)', palette, re.S).group(1))
assert len(colors) >= len(names)
fig, axes = plt.subplots(3, 2, figsize=(12, 12), sharex=True)
for i, pitch in enumerate([0, 8, 12]):
    for j, coefficient in enumerate(['Cl', 'Cn']):
        ax = axes[i, j]
        for k, name in enumerate(names):
            series = sorted([r for r in rows if r['specification']['case'] == name
                             and r['specification']['alpha'] == pitch],
                            key=lambda r: r['specification']['delta'])
            x = [r['specification']['delta'] for r in series]
            ax.scatter(x, [r['primary'][coefficient] for r in series],
                       color=colors[k], s=19, marker='o', facecolors='none')
            ax.plot(x, [r['result'][coefficient] if r['status'] == 'computed'
                        else float('nan') for r in series], color=colors[k], lw=1.3)
        ax.set_title(f'Body pitch {pitch}° — {"roll" if j == 0 else "yaw"}')
        ax.set_ylabel(f'{coefficient} (body axes, span normalization)')
        ax.grid(alpha=.22)
        if i == 2:
            ax.set_xlabel('Physical aileron deflection (degrees)')
        ax.set_xticks([4, 12, 20, 28, 36, 44])
legend = [Line2D([0], [0], color=colors[k], lw=2,
                label=n.replace('_literal', '').replace('_reconstructed', ' (reconstructed)'))
          for k, n in enumerate(names)]
legend += [Line2D([0], [0], color='black', lw=1.3, label='OpenSwing, 160 requested intervals'),
           Line2D([0], [0], color='black', marker='o', markerfacecolor='none',
                  linestyle='none', label='Primary tabulated values')]
fig.legend(handles=legend, loc='lower center', ncol=3, fontsize=9,
           bbox_to_anchor=(.5, .015))
fig.suptitle('ISAE SA-6: current solver versus primary roll/yaw tables\n'
             'Wing-only inputs; no parameter fitting; zero anchors excluded', fontsize=14)
fig.tight_layout(rect=(0, .10, 1, .94))
for extension in ['svg', 'png']:
    fig.savefig(DEST / f'isae-sa6-current.{extension}', dpi=150)
plt.close(fig)
