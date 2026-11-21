"""Verify retained native chord/span refinement; no new equilibrium solves."""
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import re

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'artifacts/isae/sa11-native-chord-refinement-20261108'


def module(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT/'scripts'/filename)
    result = importlib.util.module_from_spec(spec); spec.loader.exec_module(result)
    return result


DRIVER = module('chord_driver', 'verify-sa11-native-chord-refinement.py')
QUADRATURE = module('field_quadrature', 'analyze-sa11-winglet-current-wind.py')
read, sha = DRIVER.read, DRIVER.sha


def control_residual(f):
    """Independent zero-core closed-segment/ray expressions, in small blocks."""
    pg = np.diag([1/np.sqrt(1-(240/340.21)**2), 1., 1.])
    a, b, points = [f[key]@pg for key in ('RV1', 'RV2', 'RC')]
    dl = b-a; result = []
    for start in range(0, len(points), 32):
        r1 = points[start:start+32, None, :]-a
        r2 = points[start:start+32, None, :]-b
        d1, d2 = np.linalg.norm(r1, axis=2), np.linalg.norm(r2, axis=2)
        cross = np.cross(r1, r2); cross2 = np.sum(cross**2, axis=2)
        assert np.all(cross2 > 0)
        bound = cross/cross2[..., None]*np.sum(dl*(r1/d1[..., None]-r2/d2[..., None]), axis=2)[..., None]
        def ray(r, distance):
            radius2 = np.sum(r[..., 1:]**2, axis=2); assert np.all(radius2 > 0)
            return np.cross([1., 0., 0.], r)*((1+r[..., 0]/distance)/radius2)[..., None]
        # Native AVL's rounded 1/(4*pi), preserved separately from exact pi.
        induced = np.einsum('ijk,j->ik', bound+ray(r2, d2)-ray(r1, d1), f['GAM'].ravel())@pg*.079577472
        v = induced+f['VINF'][start:start+32]
        result.extend(np.sum(v*f['ENC'][start:start+32], axis=1))
    return float(np.max(abs(np.array(result))))


def main():
    plan = read(BASE/'plan.json'); DRIVER.check(plan)
    assert sha(BASE/'driver-used.py') == plan['driver_sha256']
    rows = []; pins = {}; field_error = 0.; quad_error = 0.; residual = 0.
    native_scale = 4*np.pi*.079577472
    for case in plan['cases']:
        directory = BASE/case['id']; report = read(directory/'report.json')
        for name, expected in report['artifact_sha256'].items():
            assert sha(directory/name) == expected, (case['id'], name)
        pins[str((directory/'report.json').relative_to(ROOT))] = sha(directory/'report.json')
        assert read(directory/'process.json')['returncode'] == 0
        with np.load(directory/'native-fields.npz') as archive:
            f = {key:archive[key].copy() for key in archive.files}
        index = report['native_force_points']['worst_index']
        geometry = dict(a=f['RV1'], b=f['RV2'], hv=f['RV'])
        gamma = f['GAM'].ravel()*240*native_scale
        bound, wake = QUADRATURE.independent_field(geometry, gamma, np.array([1.,0.,0.]), index, 96)
        fine, _ = QUADRATURE.independent_field(geometry, gamma, np.array([1.,0.,0.]), index, 192)
        qe = float(np.max(abs(bound-fine)))
        fe = float(np.max(abs(bound+wake-240*f['VV'][index])))
        cr = control_residual(f)
        assert qe < 1e-5, (case, qe)
        assert fe < 1e-3, (case, fe)
        assert cr < 1e-5, (case, cr)
        quad_error = max(quad_error, qe); field_error = max(field_error, fe); residual = max(residual, cr)
        row = {k:report[k] for k in ('case','native','native_error_percent','native_force_points','seconds','Cm_origin_vortex_only')}
        row.update(independent_bound_speed=float(np.linalg.norm(bound)), independent_wake_speed=float(np.linalg.norm(wake)),
                   independent_velocity_error_m_s=fe, quadrature_refinement_error_m_s=qe,
                   zero_core_control_residual_over_freestream=cr)
        rows.append(row)
    changes = []
    for c in (2,4,8):
        coarse, fine = [r for r in rows if r['case']['chord_rows'] == c]
        changes.append(dict(chord_rows=c, span_64_to_128_percent={k:100*(fine['native'][k]/coarse['native'][k]-1) for k in ('CL','CDi','CD_near')},
                            maximum_mach_ratio=fine['native_force_points']['maximum_normal_mach']/coarse['native_force_points']['maximum_normal_mach']))
    result = dict(observed_utc=datetime.now(timezone.utc).isoformat(), cases=rows,
        refinement_changes=changes, report_sha256=pins, source_pins=plan['pins'],
        maximum_independent_velocity_error_m_s=field_error, maximum_quadrature_refinement_error_m_s=quad_error,
        maximum_zero_core_control_residual_over_freestream=residual,
        native_seconds=sum(r['seconds'] for r in rows), production_calls=0, primary_comparison_changed=False,
        caveat='Independent checks use zero core and native rounded 1/(4*pi); native uses its tiny numerical core. Native force points differ from the ASWING bound receivers. This is a finite-chord linear reference, with no ASWING profile/stall/moment law.')
    DRIVER.write(BASE/'analysis.json', result)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    colors = re.findall(r"'(#\w+)'", (ROOT/'web/plot-colors.js').read_text().split('export const plotColors')[1].split(']);')[0])
    fig, axes = plt.subplots(1, 3, figsize=(11.4, 3.8))
    for color, span in zip(colors, (64,128)):
        selected = [r for r in rows if r['case']['span_strips'] == span]
        x = [r['case']['chord_rows'] for r in selected]
        for ax, key in zip(axes[:2], ('CL','CDi')):
            ax.plot(x, [r['native_error_percent'][key] for r in selected], 'o-', color=color, label=f'{span} span strips')
        axes[2].plot(x,[r['native_force_points']['maximum_normal_mach'] for r in selected], 'o-', color=color, label=f'{span} span strips')
    for ax, title in zip(axes, ('Lift error vs archive (%)','Trefftz drag error vs archive (%)','Peak normal Mach at AVL force points')):
        ax.set_title(title, fontsize=10); ax.set_xlabel('Chordwise rows'); ax.set_xticks([2,4,8]); ax.grid(alpha=.3)
    for ax in axes[:2]:ax.axhline(0,color='#555555',ls=':',lw=1)
    axes[2].axhline(1,color='#555555',ls=':',lw=1); axes[2].set_yscale('log'); axes[0].legend(fontsize=8)
    fig.suptitle('Native AVL: SA-11 upper winglet, report-derived −4° twist, α = 1°, PG = 240/340.21',fontsize=11)
    fig.text(.5,.015,'Six native linear diagnostics; no profile drag or stall law. No new OpenSwing validation passes.',ha='center',fontsize=9)
    fig.tight_layout(rect=(0,.055,1,.91))
    fig.savefig(BASE/'native-chord-refinement.png',dpi=160)
    fig.savefig(BASE/'native-chord-refinement.svg');plt.close(fig)
    print(json.dumps({k:v for k,v in result.items() if k not in ('source_pins','report_sha256','cases')}))


if __name__ == '__main__':main()
