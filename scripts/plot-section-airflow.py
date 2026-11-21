"""Plot the recorded prescribed-circulation field, not a converged wing solution."""
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
path = ROOT/'docs/validation/section-airflow.json'
data = json.loads(path.read_text())
plt.rcParams.update({'font.size':10,'svg.fonttype':'none','svg.hashsalt':'openswing-section-airflow'})
fig, axes = plt.subplots(1, 2, figsize=(11, 5.2), layout='constrained')
for sweep, color in [(-35., '#7753aa'), (0., '#555555'), (35., '#167a88')]:
    cases = [c for c in data['cases'] if c['specification']['sweep']==sweep and 'units' not in c['specification']]
    n = [c['specification']['panels'] for c in cases]
    w = [c['result']['samples'][-1]['velocity'][2] for c in cases]
    axes[0].plot(n,w,'.-',color=color,label=f'Sweep {sweep:g}°')
    axes[1].plot(n,[v/i for v,i in zip(w,n)],'.-',color=color,label=f'Sweep {sweep:g}°')
for ax in axes:
    ax.grid(alpha=.2);ax.set_xlabel('Cosine-spaced intervals');ax.legend(fontsize=9)
    ax.axhline(0,color='#aaaaaa',linewidth=.7)
axes[0].set_title('Velocity at the last force point')
axes[0].set_ylabel('Induced velocity z [m/s]')
axes[1].set_title('Growth relative to interval count')
axes[1].set_ylabel('Tip induced velocity / intervals [m/s]')
fig.suptitle('Swept wind-aligned horseshoes · closed-form field verification',fontsize=14)
fig.supxlabel('Prescribed elliptic circulation Γ = sin θ m²/s · projected semispan 1 m · straight bound line\n'
              'This field does not satisfy a wing operating solution. The growing swept term is retained; no core or wake law is changed.',fontsize=9)
sha=hashlib.sha256(path.read_bytes()).hexdigest()
for ext in ['svg','pdf']:
    metadata=({'Date':None,'Creator':'OpenSwing','Description':f'section-airflow.json SHA-256 {sha}'} if ext=='svg' else
              {'CreationDate':None,'ModDate':None,'Creator':'OpenSwing','Subject':f'section-airflow.json SHA-256 {sha}'})
    fig.savefig(ROOT/f'docs/validation/section-airflow.{ext}',metadata=metadata)
if args.preview:fig.savefig(args.preview,dpi=150)
plt.close(fig)
