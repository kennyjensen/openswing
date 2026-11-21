"""Plot the retained analytical and published-case Trefftz discrepancies."""
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
study = json.loads((ROOT/'docs/validation/trefftz.json').read_text())
fig, axes = plt.subplots(1, 2, figsize=(10, 4.4), constrained_layout=True)
elliptic = [c for c in study['analytical']['cases'] if c['fourier_amplitudes'] == [10.]]
n = [c['panels'] for c in elliptic]; error = [abs(c['errors']['relative_drag']) for c in elliptic]
axes[0].loglog(n, error, 'o-', color='#136e82', label='Wake quadrature')
axes[0].loglog(n, [error[0]*(n[0]/p)**2 for p in n], '--', color='#a06439', label='Second-order slope')
axes[0].set(xlabel='Lifting panels', ylabel='Absolute relative induced-drag error', title='Elliptical circulation: continuum check')
axes[0].set_xticks(n, labels=n); axes[0].legend(loc='upper right', fontsize=9)
axes[0].xaxis.set_minor_formatter(matplotlib.ticker.NullFormatter())
cases = study['flying_wing']; reference = cases[0]['published_efficiency']
axes[1].axhspan(reference-.0005, reference+.0005, color='#a06439', alpha=.15)
axes[1].axhline(reference, color='#a06439', linestyle='--', label=f'ASWING printed e = {reference:.3f}')
axes[1].plot([c['actual_lifting_panels'] for c in cases], [c['base']['efficiency'] for c in cases],
             'o-', color='#136e82', label='OpenSwing Trefftz wake')
axes[1].set(xlabel='Actual lifting panels (property breaks included)', ylabel='Span efficiency e',
            title='MIT flying wing: V = 64 ft/s', ylim=(.908, .946))
axes[1].set_xticks([c['actual_lifting_panels'] for c in cases]); axes[1].legend(loc='upper right', fontsize=9)
for ax in axes:ax.grid(True, alpha=.2)
fig.suptitle('Trefftz-plane verification and published-case comparison', fontsize=13)
fig.supxlabel('Right: original ASWING mesh/settings unknown; nonmonotonic OpenSwing refinement. Band: printed rounding only.', fontsize=8)
for extension in ('svg', 'pdf'):
    fig.savefig(ROOT/f'docs/validation/trefftz.{extension}', metadata={'Creator': 'OpenSwing'})
