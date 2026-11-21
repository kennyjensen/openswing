"""Plot independent Fourier/panel refinement without fitting published values."""
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
study = json.loads((ROOT/'docs/validation/circulation.json').read_text())
fig, axes = plt.subplots(1, 3, figsize=(12.5, 4.7), constrained_layout=True)
ellipse = study['analytical']; cases = ellipse['cases']
axes[0].plot([c['panels'] for c in cases],
    [100*(c['result']['CL']/np.deg2rad(c['alpha'])/ellipse['expected_lift_slope_per_rad']-1) for c in cases],
    'o-', color='#136e82')
axes[0].axhline(0, linestyle='--', color='#a06439')
axes[0].set(xlabel='Requested structural panels', ylabel='Lift-slope error (%)',
    title='Elliptic wing: one sine mode', xticks=[c['panels'] for c in cases])
rect = [c for c in study['rectangular'] if c['modes']]; labels = [str(c['modes']) for c in rect]
axes[1].semilogy(range(len(rect)), [max(abs(np.array(c['result']['circulation_local_residual']))) for c in rect],
    'o-', color='#136e82')
axes[1].set(xlabel='Fourier mode count', ylabel='Maximum local flow defect / airspeed',
    title='Rectangular wing: fixed panel mesh', xticks=range(len(rect)), xticklabels=labels)
cases = study['flying_wing']; reference = cases[0]['published_efficiency']
axes[2].axhspan(reference-.0005, reference+.0005, color='#a06439', alpha=.15)
axes[2].axhline(reference, color='#a06439', linestyle='--', label=f'ASWING printed e = {reference:.3f}')
for k,color,marker in [(0,'#136e82','o'),(7,'#924c7d','s'),(15,'#48634e','^')]:
    group = [c for c in cases if c['modes']==k]
    axes[2].plot([c['actual_lifting_panels'] for c in group], [c['base']['efficiency'] for c in group],
        marker+'-', color=color, label='Pointwise' if k==0 else f'{k} sine modes')
axes[2].set(xlabel='Actual lifting panels', ylabel='Span efficiency e',
    title='MIT flying wing: V = 64 ft/s', xticks=sorted({c['actual_lifting_panels'] for c in cases}))
axes[2].legend(fontsize=8)
for ax in axes:ax.grid(True, alpha=.2)
fig.suptitle('Fourier circulation: separate mode and panel refinement', fontsize=13)
fig.supxlabel('Right: original ASWING mesh/mode settings unknown. Shaded band is printed rounding; no constants are fitted.', fontsize=9)
for extension in ('svg', 'pdf'):
    fig.savefig(ROOT/f'docs/validation/circulation.{extension}', metadata={'Creator': 'OpenSwing'})
