"""Plot retained sectional SA-6 fields; no aerodynamic evaluations."""
from pathlib import Path
import json
import re

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT/'docs/validation'
data = json.loads((DEST/'isae-sa6-local.json').read_text())
colors = re.findall(r"'(#\w{6})'", re.search(
    r'plotColors = Object.freeze\(\[(.*?)\]\)',
    (ROOT/'web/plot-colors.js').read_text(), re.S).group(1))
rows = {r['specification']['right_deflection_deg']:r for r in data['states']
        if r['specification']['body_pitch_deg'] == 12}
fig, axes = plt.subplots(2, 2, figsize=(11, 7), sharex=True)
for column, (direction, sign) in enumerate((('up', 1), ('down', -1))):
    for k, delta in enumerate((0, 4, 20, 44)):
        row = rows[sign*delta]
        raw = row['raw']
        strips = row['result']['strips']
        y = [s['position'][1] for s in strips]
        cl = [s['cl'] for s in strips]
        stall_drag = [4*(tau/s['normal_speed'])**2 for tau, s in zip(raw['tangency'], strips, strict=True)]
        for a, values in zip(axes[:, column], (cl, stall_drag), strict=True):
            a.plot(y, values, color=colors[k], label=f'{delta}°', linewidth=1.8)
    axes[0, column].set_title(f'Right aileron {direction}; left aileron neutral')
    for limit in (-.4, 1.4):
        axes[0, column].axhline(limit, color='#666666', linestyle=':', linewidth=.8)
    axes[1, column].axhline(.01364, color='#666666', linestyle=':', linewidth=.8)
    axes[0, column].set_ylim(-.45, 1.55)
    axes[1, column].set_ylim(-.03, 1.35)
    axes[1, column].set_xlabel('Span station y (m)')
    for a in axes[:, column]:
        a.axvline(.253746, color='#999999', linestyle='--', linewidth=.8)
        a.set_xlim(-.762, .762)
        a.grid(alpha=.2)
        a.set_xticks([-.75, -.5, -.25, 0, .25, .5, .75])
axes[0, 0].set_ylabel(r'Section $c_l = 2\Gamma/(c V_\perp)$')
axes[1, 0].set_ylabel(r'Stall-drag coefficient $4(T/V_\perp)^2$')
handles, labels = axes[0, 0].get_legend_handles_labels()
fig.legend(handles, labels, loc='lower center', bbox_to_anchor=(.5, .045),
           ncol=4, title='Right-aileron deflection magnitude')
fig.suptitle('SA-6 local model diagnostic — body pitch 12°, 35%-chord aileron\n'
             'Dotted lines: input lift limits (top), constant profile drag (bottom)', fontsize=12)
fig.text(.5, .01, 'Dashed vertical line: inner boundary of the controlled right aileron. '
         'These curves are predictions, not measured section data.', ha='center', fontsize=8)
fig.tight_layout(rect=(0, .16, 1, .91))
for extension in ('svg', 'png'):
    fig.savefig(DEST/f'isae-sa6-local.{extension}', dpi=150)
plt.close(fig)
