"""Check and plot the retained central-section mechanism control."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import NullFormatter

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Use a fresh output directory.')
    manifest = json.loads((args.source/'verification.json').read_text())
    for name, digest in manifest['artifacts'].items():
        assert sha(args.source/name) == digest, name
    plan = json.loads((args.source/'plan.json').read_text())
    for name, digest in plan['unchanged_pins'].items():
        assert sha(ROOT/name) == digest, name
    results = json.loads((args.source/'results.json').read_text())
    # Linear section-law identity, not a claim that these prescribed Gamma
    # fields solve either circulation equation. Central section n=+z, h=c/2.
    identity_errors = []
    for row in results['rows']:
        section_residual = plan['constant_circulation'] - np.pi*plan['chord']*row['inner_control_point_velocity'][2]
        tangency_residual = -np.pi*plan['chord']*row['control_point_velocity'][2]
        identity_errors.append(abs(section_residual-tangency_residual))
    assert max(identity_errors) < 1e-14
    args.output.mkdir(parents=True)
    shutil.copyfile(__file__, args.output/'analysis-driver-used.py')
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.6), constrained_layout=True)
    colors = {'sweep': '#0072B2', 'dihedral': '#D55E00'}
    raw = [r for r in results['rows'] if r['kind']=='sweep']
    counts = [r['panels'] for r in raw]
    axes[0].plot(counts, [-r['bound_at_force_point'][2] for r in raw], 'o-',
                 color='#333333', label='On-line field (both curves)')
    for kind in colors:
        rows = [r for r in results['rows'] if r['kind']==kind]
        component, sign = (2, -1) if kind=='sweep' else (0, 1)
        values = [sign*r['corrected_bound'][component] for r in rows]
        axes[0].plot(counts, values, 'o-', color=colors[kind], label=f'Corrected field: {kind}')
        steps = [r for r in results['mesh_increments'] if r['kind']==kind]
        axes[1].loglog([r['second'] for r in steps],
                      [np.linalg.norm(r['corrected_increment']) for r in steps],
                      'o-', color=colors[kind], label=f'Corrected change: {kind}')
    steps = [r for r in results['mesh_increments'] if r['kind']=='sweep']
    axes[1].loglog([r['second'] for r in steps],
                  [np.linalg.norm(r['raw_increment']) for r in steps], 'o-',
                  color='#333333', label='On-line change (both curves)')
    axes[1].loglog([r['second'] for r in steps],
                  [np.linalg.norm(r['predicted_increment']) for r in steps], ':',
                  color='#999999', linewidth=3, label='Analytic logarithmic increment')
    axes[0].set_xscale('log', base=2)
    axes[0].set_ylabel('Bound velocity along local binormal (m/s)')
    axes[1].set_ylabel('Velocity change from previous mesh (m/s)')
    axes[0].set_title('Central section: smooth sweep and dihedral')
    axes[1].set_title('Refinement separates growth from convergence')
    for ax in axes:
        ax.set_xticks(counts if ax is axes[0] else counts[1:])
        ax.set_xticklabels([str(n) for n in (counts if ax is axes[0] else counts[1:])])
        ax.xaxis.set_minor_formatter(NullFormatter())
        ax.set_xlabel('Straight bound segments')
        ax.grid(True, which='both', alpha=.25)
        ax.legend(fontsize=8)
    fig.suptitle('Fixed circulation; zero core; no circulation solve or ISAE comparison', fontsize=12)
    fig.savefig(args.output/'curved-section-velocity.png', dpi=160)
    fig.savefig(args.output/'curved-section-velocity.svg')
    plt.close(fig)
    for name, digest in plan['unchanged_pins'].items():
        assert sha(ROOT/name) == digest, name
    review = dict(observed_utc=datetime.now(timezone.utc).isoformat(),
                  source=str(args.source), source_manifest_sha256=sha(args.source/'verification.json'),
                  source_results_sha256=sha(args.source/'results.json'),
                  unchanged_pin_count=len(plan['unchanged_pins']),
                  maximum_linear_section_tangency_identity_error=max(identity_errors),
                  identity_scope='Equality of two residual definitions; the prescribed fields do not satisfy zero tangency.',
                  final_increments=[r for r in results['mesh_increments'] if r['second']==511],
                  artifacts={p.name: sha(p) for p in sorted(args.output.iterdir()) if p.is_file()})
    (args.output/'review.json').write_text(json.dumps(review, indent=2, allow_nan=False)+'\n')
    print(json.dumps(dict(status='verified', identity_error=max(identity_errors),
                         unchanged_pins=len(plan['unchanged_pins']))))


if __name__ == '__main__':
    main()
