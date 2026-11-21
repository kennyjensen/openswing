"""Publication artifacts from saved AE-1 sweeps; no numerical solves."""
from pathlib import Path
import json
import re
import math

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT/'docs/validation'
report = json.loads((DEST/'isae-ae1-sweep.json').read_text())
colors = re.findall(r"'(#\w{6})'", re.search(
    r'plotColors = Object.freeze\(\[(.*?)\]\)',
    (ROOT/'web/plot-colors.js').read_text(), re.S).group(1))


def qualify(axis, alpha):
    limit = 57 if alpha==5 else 42
    # Source controls extend beyond the measured speed window. Retain their
    # line interpolation at the edge without scaling y to invisible points.
    visible = []
    for line in axis.lines:
        points = [(float(x), float(y)) for x, y in zip(line.get_xdata(), line.get_ydata())
                  if y is not None and math.isfinite(float(y))]
        visible.extend(y for x, y in points if 0 <= x <= limit)
        for (x0, y0), (x1, y1) in zip(points, points[1:]):
            if x0 < limit < x1:
                visible.append(y0+(y1-y0)*(limit-x0)/(x1-x0))
    if visible:
        lower, upper = min(visible), max(visible)
        margin = .06*(upper-lower)
        axis.set_ylim(lower-margin, upper+margin)
    if alpha == 5:
        axis.axvline(48., color='#666666', linestyle=':', linewidth=.9)
        axis.axvspan(48., 57., color='#777777', alpha=.09)
    else:
        axis.axvline(40., color='#666666', linestyle=':', linewidth=.9)
        axis.axvspan(40., 42., color='#777777', alpha=.09)
    axis.grid(alpha=.2)
    axis.set_xlim(0, limit)


fig, axes = plt.subplots(2, 2, figsize=(11, 7), sharex='col')
for column, alpha in enumerate((5, 7)):
    axes[0, column].set_title(f'Root incidence {alpha}°')
    for row, (quantity, source_quantity) in enumerate((('displacement_percent_semispan', 'displacement'), ('twist_deg', 'twist'))):
        axis = axes[row, column]
        experiment = next(d['values'] for d in report['source_tables']
                          if d['reference']=='experiment' and d['alpha_deg']==alpha and d['quantity']==source_quantity)
        axis.plot([r[0] for r in experiment], [r[1] for r in experiment], color=colors[0],
                  linewidth=1.5, label='Published experiment')
        for i, refinement in enumerate((2, 4), 1):
            selected = [r for r in report['comparisons'] if r['refinement']==refinement and r['alpha_deg']==alpha]
            axis.plot([r['speed_m_s'] for r in selected],
                      [r.get('predicted',{}).get(quantity) for r in selected],
                      color=colors[i], linewidth=1.7, linestyle='--' if refinement==2 else '-',
                      label=f'OpenSwing {15*refinement}/half')
        control = next(d['values'] for d in report['source_tables']
                       if d['reference']=='UM/NAST-VLM' and d['alpha_deg']==alpha and d['quantity']==source_quantity)
        axis.plot([r[0] for r in control], [r[1] for r in control], color=colors[3],
                  linewidth=1.1, linestyle='-.', label='Primary UM/NAST-VLM')
        if source_quantity=='displacement':
            fine = [r for r in report['comparisons'] if r['refinement']==4 and r['alpha_deg']==alpha]
            axis.plot([r['speed_m_s'] for r in fine],
                      [r.get('predicted',{}).get('wind_normal_displacement_percent_semispan') for r in fine],
                      color=colors[4], linewidth=1., linestyle=':', label='60/half, wind-normal alternative')
        qualify(axis, alpha)
    axes[1, column].set_xlabel('Airspeed (m/s)')
axes[0, 0].set_ylabel('Tip midchord displacement\n(% nominal semispan)')
axes[1, 0].set_ylabel('Tip projected twist (degrees)')
handles, labels = axes[0, 0].get_legend_handles_labels()
fig.legend(handles, labels, loc='lower center', bbox_to_anchor=(.5, .045), ncol=3, fontsize=9)
fig.suptitle('ISAE AE-1 Pazy skin-on: full exported speed coordinates', fontsize=13)
fig.text(.5, .014, 'Gray: at/after reported dynamic indicators; exact stability boundaries are unresolved. Static roots do not establish stability.',
         ha='center', fontsize=8.5)
fig.tight_layout(rect=(0, .13, 1, .95))
for suffix in ('svg', 'png'):
    fig.savefig(DEST/f'isae-ae1-sweep.{suffix}', dpi=150)
plt.close(fig)

fig, axes = plt.subplots(1, 2, figsize=(10, 4.5))
for i, alpha in enumerate((5, 7)):
    rows = [r for r in report['mesh'] if r['alpha_deg']==alpha]
    for axis, key in zip(axes, ('displacement_percent_semispan', 'twist_deg')):
        axis.plot([r['speed_m_s'] for r in rows],
                  [None if r.get('relative_to_fine',{}).get(key) is None else
                   100*abs(r['relative_to_fine'][key]) for r in rows], color=colors[i],
                  linewidth=1.8, label=f'{alpha}°')
        axis.grid(alpha=.2)
        axis.set_xlabel('Airspeed (m/s)')
        axis.set_ylabel('|60 − 30| / |60| (%)')
axes[0].axhline(1., color='#666666', linewidth=1., linestyle=':', label='Displacement mesh gate: 1%')
axes[0].set_title('Root-normal displacement')
axes[1].set_title('Projected twist (no predeclared gate)')
axes[0].legend(fontsize=8)
axes[1].legend(fontsize=8)
fig.suptitle('Two-grid change at identical source speeds; not a continuum error bound', fontsize=11)
fig.tight_layout(rect=(0, 0, 1, .93))
for suffix in ('svg', 'png'):
    fig.savefig(DEST/f'isae-ae1-sweep-mesh.{suffix}', dpi=150)
plt.close(fig)
