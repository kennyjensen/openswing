"""Audit saved circulation/force ledgers and plot attached-wake controls."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import shutil

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]


def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists(): parser.error('Use a fresh output directory.')
    folders = [f'attached-wake-forces-20261108-n{n}' for n in (16, 32, 64, 128)]
    folders += ['attached-wake-forces-20261108-n128-alpha1-residual-check']
    rows = []; sources = {}; arrays = {}; pins = None; maxima = dict(residual=0., force=0., moment=0.)
    for folder in folders:
        path = ROOT/'artifacts/isae'/folder
        manifest = json.loads((path/'verification.json').read_text())
        for name, digest in manifest['artifacts'].items(): assert sha(path/name) == digest
        sources[str(path.relative_to(ROOT))] = sha(path/'verification.json')
        plan = json.loads((path/'plan.json').read_text())
        if pins is None: pins = plan['unchanged_pins']
        assert pins == plan['unchanged_pins']
        for name, digest in plan['source_pins'].items(): assert sha(ROOT/name) == digest
        for row in json.loads((path/'results.json').read_text())['records']:
            row = dict(row, incidence_degrees=plan['incidence_degrees'])
            with np.load(path/f"sweep-{row['sweep_degrees']:+03d}.npz") as archive:
                d = {k: archive[k] for k in archive.files}
            gamma = d['gamma']; n = len(gamma)
            # Compensated scalar sums, independent of the driver's tensor
            # contractions, reconstruct all three saved velocity locations.
            velocity = {}
            for key in ('cp_inner', 'quarter', 'attached'):
                tensor = d[key]
                velocity[key] = np.array([[float(k == 0)+math.fsum(float(tensor[i,j,k]*gamma[j])
                    for j in range(n)) for k in range(3)] for i in range(len(tensor))])
            x = velocity['cp_inner']@d['chord']; z = velocity['cp_inner']@d['normal']
            speed = np.hypot(x, z)
            residual = gamma-np.pi*speed*np.arctan2(z, x)
            maxima['residual'] = max(maxima['residual'], float(np.max(abs(residual))))
            assert np.max(abs(residual)) < 1e-10
            v = velocity['quarter']; vp = v-np.outer(v@d['span'], d['span'])
            section = (gamma*speed*d['ds'])[:, None]*np.cross(vp, d['span'])/np.linalg.norm(vp, axis=1)[:, None]
            attached = (d['jump']@gamma)[:, None]*np.cross(velocity['attached'], d['te']-d['q'])
            force = section.sum(axis=0)+attached.sum(axis=0)
            moment = np.cross(d['mid'], section).sum(axis=0)+np.cross(d['at_points'], attached).sum(axis=0)
            force_error = max(np.max(abs(section-d['force_section'])), np.max(abs(attached-d['force_at'])),
                              np.max(abs(force-row['total_force'])))
            moment_error = np.max(abs(moment-row['total_moment']))
            maxima['force'] = max(maxima['force'], float(force_error))
            maxima['moment'] = max(maxima['moment'], float(moment_error))
            assert force_error < 2e-11 and moment_error < 2e-11
            peak = int(np.argmax(np.linalg.norm(velocity['attached'], axis=1)))
            row['attached_peak'] = dict(index=peak, endpoint=peak in (0,n),
                velocity=velocity['attached'][peak].tolist(),
                span_velocity=float(velocity['attached'][peak]@d['span']),
                chord_velocity=float(velocity['attached'][peak]@d['chord']),
                normal_velocity=float(velocity['attached'][peak]@d['normal']),
                endpoint_force_sum=(attached[0]+attached[-1]).tolist())
            arrays[(row['incidence_degrees'],n,row['sweep_degrees'])] = d
            rows.append(row)
    for name, digest in pins.items(): assert sha(ROOT/name) == digest
    for alpha,n in sorted({(r['incidence_degrees'],r['panels']) for r in rows}):
        plus = next(r for r in rows if (r['incidence_degrees'],r['panels'],r['sweep_degrees']) == (alpha,n,30))
        minus = next(r for r in rows if (r['incidence_degrees'],r['panels'],r['sweep_degrees']) == (alpha,n,-30))
        np.testing.assert_allclose(arrays[(alpha,n,30)]['gamma'], arrays[(alpha,n,-30)]['gamma'][::-1], atol=2e-12, rtol=2e-12)
        np.testing.assert_allclose(np.array(plus['total_force'])*[1,-1,1], minus['total_force'], atol=2e-12, rtol=2e-12)
        np.testing.assert_allclose(np.array(plus['total_moment'])*[-1,1,-1], minus['total_moment'], atol=2e-12, rtol=2e-12)
    selected = [r for r in rows if r['incidence_degrees'] == 5 and r['sweep_degrees'] == 30]
    fine_change = 100*(np.array(selected[-1]['total_force'])/selected[-2]['total_force']-1)
    args.output.mkdir(parents=True)
    shutil.copyfile(__file__, args.output/'analysis-driver-used.py')
    fig, axes = plt.subplots(1,3,figsize=(14,4.5),constrained_layout=True)
    counts = [r['panels'] for r in selected]
    axes[0].plot(counts,[r['section_only_drag_difference_percent'] for r in selected],'o-',label='Section only')
    axes[0].plot(counts,[r['full_drag_difference_percent'] for r in selected],'o-',label='With attached legs')
    axes[0].axhline(0,color='gray',linestyle=':'); axes[0].set_ylabel('Difference from Trefftz drag (%)')
    axes[0].set_title('Force accounting at 30° sweep')
    axes[1].plot(counts,[r['total_force'][0] for r in selected],'o-',label='Complete force')
    axes[1].plot(counts,[r['trefftz_drag'] for r in selected],'o--',label='Trefftz reference')
    axes[1].set_title('Drag refinement'); axes[1].set_ylabel('Drag (N)')
    axes[2].plot(counts,[r['peak_quarter_speed'] for r in selected],'o-',label='Quarter chord')
    axes[2].plot(counts,[r['peak_attached_speed'] for r in selected],'o-',label='Attached legs')
    axes[2].set_title('Peak velocity: distinct receiver sets'); axes[2].set_ylabel('Speed / freestream')
    for ax in axes:
        ax.set_xscale('log',base=2); ax.set_xticks(counts,labels=[str(n) for n in counts])
        ax.set_xlabel('Span intervals'); ax.grid(True,alpha=.25); ax.legend(fontsize=8)
    fig.suptitle('Solved attached-leg control: 5° incidence, zero core; not native ASWING validation')
    fig.savefig(args.output/'attached-wake-forces.png',dpi=150)
    fig.savefig(args.output/'attached-wake-forces.svg'); plt.close(fig)
    failure=ROOT/'artifacts/isae/attached-wake-forces-20261108-n128-alpha1/failure.json'
    summary=dict(observed_utc=datetime.now(timezone.utc).isoformat(), unchanged_pins=pins,
        source_manifests=sources, verified_records=len(rows), scalar_reconstruction_maxima=maxima,
        mirror_symmetry_verified=True, final_force_change_percent=fine_change.tolist(),
        completed_stage_seconds=sum(r['seconds'] for r in rows), records=rows,
        prior_rejected_harness_attempt=dict(path=str(failure.relative_to(ROOT)),sha256=sha(failure)),
        production_and_primary_counts_unchanged=True,
        artifacts={p.name:sha(p) for p in sorted(args.output.iterdir()) if p.is_file()})
    (args.output/'analysis.json').write_text(json.dumps(summary,indent=2,allow_nan=False)+'\n')
    print(json.dumps({k:v for k,v in summary.items() if k not in ('unchanged_pins','source_manifests','records','artifacts')},indent=2))
    print(json.dumps([r for r in rows if r['panels']==128 and r['sweep_degrees']>=0],indent=2))


if __name__ == '__main__': main()
