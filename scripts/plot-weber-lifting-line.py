"""Show both verified aerodynamic coordinates and unresolved refinement limits."""
from pathlib import Path
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection
from matplotlib.ticker import NullFormatter
from openswing.asw import parse_asw
from openswing.geometry import geometry_summary, model_meshes
from openswing.frozen_influence import lifting_geometry

study = json.loads((ROOT/'docs/validation/weber-lifting-line.json').read_text())
for name, wanted in study['source_sha256'].items():
    assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest() == wanted, name
planform = json.loads((ROOT/'docs/validation/weber-planform.json').read_text())
model = parse_asw((ROOT/'examples/weber-tabulated.asw').read_text())
meshes = model_meshes(model, 48)
geometry = lifting_geometry(meshes, np.array([1., 0., 0.]))
quads = np.array(geometry_summary(model, meshes=meshes)[0]['quads'])
outline = np.array(planform['cases'][0]['half_outline_xy_in'])*.0254
plt.rcParams.update({'font.size': 9, 'svg.hashsalt': 'openswing-weber-lifting-line'})
fig, axes = plt.subplots(2, 2, figsize=(11.4, 8.3), layout='constrained')
for ax in axes[0]:
    for sign in [-1, 1]:
        ax.plot(sign*outline[:, 1], outline[:, 0], color='#242d33', lw=1.1,
                label='Primary-table planform' if sign == 1 else None)
    polygons = quads[:, :, [1, 0]]
    ax.add_collection(PolyCollection(polygons, facecolors='#e2aa66', edgecolors='#bd863e',
                                     linewidths=.25, alpha=.3, label='Normal-strip drawing'))
    ax.scatter(geometry['hv'][:, 1], geometry['hv'][:, 0], s=7, color='#176985', label='Quarter-chord axis')
    ax.scatter(geometry['cp'][:, 1], geometry['cp'][:, 0], s=7, color='#a74456', marker='+', label='Zero-wind control points')
    ax.set(xlabel='Span coordinate y (m)', ylabel='Aft coordinate x (m)')
    ax.grid(alpha=.2)
axes[0, 0].set(xlim=(-1.35, 1.35), ylim=(1.83, -.03), title='Verified stations; approximate normal-strip outline')
axes[0, 0].set_aspect('equal')
axes[0, 1].set(xlim=(1.09, 1.29), ylim=(1.82, 1.10), title='Tip detail · distinct coordinate representations')
axes[0, 1].legend(fontsize=8, loc='upper left')

actual = {g['requested_intervals']: g['actual_intervals'] for g in study['geometry']}
styles = [('current_zero_pg', '#176985', '-', 'Current · PG 0'),
          ('current_speed_pg', '#176985', '--', 'Current · PG V/a'),
          ('frozen_zero_pg', '#a74456', '-', 'Frozen · PG 0'),
          ('frozen_speed_pg', '#a74456', '--', 'Frozen · PG V/a')]
for mode, color, style, label in styles:
    rows = [c for c in study['cases'] if c['specification']['mode']==mode and c['specification']['alpha_deg']==2.1]
    n = [actual[c['specification']['panels']] for c in rows]
    cl = [c['result']['CL'] if c['status']=='computed' else np.nan for c in rows]
    mach = [(c['result']['lifting_airflow'] if c['status']=='computed' else c['details'])['maximum']['normal_mach'] for c in rows]
    axes[1, 0].plot(n, cl, style, color=color, marker='o', ms=4, label=label)
    axes[1, 1].plot(n, mach, style, color=color, marker='o', ms=4, label=label)
    rejected = np.array([c['status']=='rejected' for c in rows])
    axes[1, 1].scatter(np.array(n)[rejected], np.array(mach)[rejected], marker='x', color=color, s=38, zorder=4)
axes[1, 0].set(ylabel='CL', title='α = 2.1° · rejected cases remain gaps')
axes[1, 0].legend(fontsize=8)
axes[1, 1].axhline(1, color='#202020', linestyle=':', label='Subsonic rejection threshold')
axes[1, 1].set(yscale='log', ylabel='Maximum section-normal Mach', title='α = 2.1° · × marks rejected calculations')
axes[1, 1].legend(fontsize=8)
for ax in axes[1]:
    ax.set(xscale='log', xlabel='Actual lifting intervals (includes mandatory table stations)', xlim=(64, 600))
    ax.set_xticks(list(actual.values()), labels=[str(v) for v in actual.values()])
    ax.xaxis.set_minor_formatter(NullFormatter())
    ax.grid(alpha=.2)
fig.suptitle('Tabulated swept-wing lifting-line study\nInviscid verification; no matched experimental or full-range convergence claim', fontsize=13)
for extension in ['svg', 'pdf', 'png']:
    path = ROOT/f'docs/validation/weber-lifting-line.{extension}'
    fig.savefig(path, dpi=160)
    print(path)
plt.close(fig)
