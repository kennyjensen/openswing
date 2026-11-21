"""Standalone scientific comparison figure; install the optional plots extra."""
import argparse
import hashlib
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--preview', help='Optional PNG path for visual review.')
args = parser.parse_args()
source = ROOT/'docs/validation/flying-wing.json'
data = json.loads(source.read_text())
plt.rcParams.update({'font.size': 10, 'svg.fonttype': 'none', 'svg.hashsalt': 'openswing-fw'})
fig, axes = plt.subplots(1, 3, figsize=(12.6, 5.0), layout='constrained')
points = data['reference']['points']
v = [p['speed_ft_s'] for p in points]
roots = [p['bff_root_per_s'] for p in points]
for ax in axes:
    ax.grid(True, alpha=.2)
axes[0].axhline(0, color='#84909c', linewidth=.8)
axes[2].axvline(0, color='#84909c', linewidth=.8)
axes[0].plot(v, [r[0] for r in roots], 'o--', color='#374151', markersize=4, label='MIT figure (digitized)')
axes[1].plot(v, [r[1] for r in roots], 'o--', color='#374151', markersize=4)
axes[2].plot([r[0] for r in roots], [r[1] for r in roots], 'o--', color='#374151', markersize=4)
for n, color, marker in [(8, '#be721d', 'x'), (16, '#3278b5', 's'), (32, '#159582', '^')]:
    cases = sorted((c for c in data['cases'] if c['requested_panels'] == n and c['difference_step'] == 1e-5), key=lambda c: c['speed_ft_s'])
    speeds = [c['speed_ft_s'] for c in cases]
    sigma = [c['bff_root_per_s'][0] for c in cases]
    omega = [c['bff_root_per_s'][1] for c in cases]
    # Do not draw a fictitious straight branch across unsampled speed gaps.
    for i in range(len(speeds)-1, 0, -1):
        if speeds[i]-speeds[i-1] > 4:
            for values in (speeds, sigma, omega):
                values.insert(i, float('nan'))
    label = f"OpenSwing: {cases[0]['actual_lifting_panels']} panels"
    axes[0].plot(speeds, sigma, marker=marker, color=color, label=label, linewidth=1.1, markersize=5)
    axes[1].plot(speeds, omega, marker=marker, color=color, linewidth=1.1, markersize=5)
    axes[2].plot(sigma, omega, marker=marker, color=color, linewidth=1.1, markersize=5)
axes[0].set(xlabel='Speed [ft/s]', ylabel='Growth rate σ [1/s]', title='Flutter-branch growth')
axes[1].set(xlabel='Speed [ft/s]', ylabel='Angular frequency ω [rad/s]', title='Flutter-branch frequency')
axes[2].set(xlabel='Growth rate σ [1/s]', ylabel='Angular frequency ω [rad/s]', title='Local root comparison')
axes[0].legend(loc='upper left', fontsize=8)
fig.suptitle('Swept flying wing · comparison with published ASWING figure', fontsize=14)
fig.supxlabel('OpenSwing markers are computed points; lines join samples at most 4 ft/s apart.\nInferred steady glide. Original mesh/settings unknown. Selected branch only; full parity remains unverified.', fontsize=9)
digest = hashlib.sha256(source.read_bytes()).hexdigest()
fig.savefig(ROOT/'docs/validation/flying-wing.svg', metadata={'Date': None, 'Creator': 'OpenSwing', 'Description': f'Input flying-wing.json SHA-256 {digest}'})
fig.savefig(ROOT/'docs/validation/flying-wing.pdf', metadata={'CreationDate': None, 'ModDate': None, 'Creator': 'OpenSwing', 'Subject': f'Input flying-wing.json SHA-256 {digest}'})
if args.preview:
    fig.savefig(args.preview, dpi=150)
plt.close(fig)
