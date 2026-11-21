"""Verify the fixed-PG diagnostic, including its blocked geometry comparisons.

The native field reconstruction uses exported AVL endpoints and normals. It
does not turn a rejected production state or an alternative input into a pass.
"""
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import re

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'artifacts/isae/sa11-fixed-pg-candidate-20261108'
spec = importlib.util.spec_from_file_location('candidate', ROOT / 'scripts/verify-sa11-fixed-pg-candidate.py')
driver = importlib.util.module_from_spec(spec)
spec.loader.exec_module(driver)
from openswing.factored_influence import FactoredInfluence


def main():
    plan = driver.read(OUT / 'plan.json')
    driver.check(plan)
    assert driver.sha(OUT / 'driver-used.py') == plan['pins']['scripts/verify-sa11-fixed-pg-candidate.py']
    rows, pins = [], {}
    for case in plan['cases']:
        folder = OUT / case['id']
        process = driver.read(folder / 'process.json')
        assert process['returncode'] == 0
        model, choice = driver.model_for(case['choice'])
        assert choice == driver.read(folder / 'input-choice.json') == plan['models'][case['choice']]
        _, segments = driver.BASE.CONVERT.conversion(model, 1 if case['choice'].startswith('upper') else 2)
        with np.load(folder / 'native-fields.npz') as archive:
            fields = {key: archive[key].copy() for key in archive.files}
        assert len(fields['GAM']) == sum(s['count'] for s in segments) == 64
        labels = driver.BASE.CONVERT.MATCHED.NATIVE.labeled(folder / 'total.txt')
        mach = 0. if case['pg'] == 'zero' else 255 / model.constants[2]
        assert abs(labels["Mach, rb/2V, r'b/2V"][0] - mach) < 1e-14
        pg = np.diag([1 / np.sqrt(1 - mach**2), 1., 1.])
        cp = FactoredInfluence(fields['RC'], fields['RV1'], fields['RV2'], [1., 0., 0.], pg)
        hv = FactoredInfluence(fields['RV'], fields['RV1'], fields['RV2'], [1., 0., 0.], pg,
                               exclude_bound=np.eye(64, dtype=bool))
        ng = fields['GAM'].ravel()
        factor = 4 * np.pi * .079577472  # Literal native PI4INV; no fitted constant.
        gamma = np.linalg.solve(np.einsum('ijk,ik->ij', cp.matrix(), fields['ENC']),
                                -np.sum(fields['VINF'] * fields['ENC'], axis=1))
        gamma_error = float(np.max(abs(gamma / factor - ng)) / np.max(abs(ng)))
        field_error = float(np.max(abs(factor * hv.apply(ng) - fields['VV'])))
        field_relative_error = field_error / max(1., float(np.max(abs(fields['VV']))))
        assert gamma_error < 1e-6, (case['id'], gamma_error)
        force = np.sum(2 * ng[:, None] * np.cross(fields['VINF'] + fields['VV'],
                                                 fields['RV2'] - fields['RV1']), axis=0) / model.reference[0, 0]
        listed_force = np.array([labels['CXtot, Cltot, Cl\'tot'][0], labels['CYtot, Cmtot'][0],
                                 labels['CZtot, Cntot, Cn\'tot'][0]])
        force_error = float(np.max(abs(force - listed_force)))
        row = dict(case=case, native_returncode=0, native_seconds=process['seconds'],
                   native_gamma_reconstruction_relative_error=gamma_error,
                   native_velocity_reconstruction_error=field_error,
                   native_velocity_reconstruction_scaled_error=field_relative_error,
                   native_force_reconstruction_error=force_error,
                   production=[], primary_passes_added=0)
        try:
            meshes, geometry, errors, settings = driver.BASE.CONVERT.mapped_meshes(model, fields, segments)
        except AssertionError as exc:
            # Preserve both predeclared extension cases as blocked comparisons.
            assert case['choice'] == 'extension' and isinstance(exc.args[0], dict)
            assert not (folder / 'report.json').exists() and not list(folder.glob('u*'))
            row.update(status='conversion-blocked', geometry_errors=exc.args[0],
                       reason='The extension uses natural cubic ASW geometry/chord; the piecewise-linear AVL export does not share its endpoints and receivers.',
                       blocked_production_calls=2)
            blocked = folder / 'conversion-blocked.json'
            # These observations were first recorded before adding the scaled
            # field diagnostic; preserve their original bytes on verification.
            if blocked.exists():
                saved = driver.read(blocked)
                assert all(row[k] == v for k, v in saved.items())
            else:
                driver.write(blocked, row)
        else:
            # Native and Python finite-leg arithmetic differ near sharp roots.
            # Check the field at the same relative precision as circulation and
            # retain the absolute discrepancy; this is not a native-target gate.
            assert field_relative_error < 1e-6 and force_error < 2e-10, (case['id'], field_error, force_error)
            report = driver.read(folder / 'report.json')
            assert report['case'] == case and report['accepted_primary_checks'] == 0
            assert not report['original_setup_authenticated']
            assert errors == report['geometry_errors'] and max(errors.values()) < 2e-11
            for name, digest in report['artifact_sha256'].items():
                assert driver.sha(folder / name) == digest, (case['id'], name)
            row.update(status='matched-geometry', geometry_errors=errors, native=report['native'])
            ff = labels['Trefftz Plane: CLff, CDff, CYff, e']
            assert report['native'] == dict(CL=labels['CLtot'][0], CDi=ff[1], efficiency=ff[3],
                                             CD_near=labels['CDvis, CDind'][1])
            tangents = np.concatenate([m.frames[..., 1] for m in meshes])
            previous, previous_values, previous_speed = None, None, None
            expected_speeds = [255., 266.] if case['pg'] == 'zero' else [255.]
            assert [s['speed'] for s in report['production']] == expected_speeds
            for record in report['production']:
                speed = record['speed']
                sub = folder / f'u{int(speed)}'
                condition = driver.read(sub / 'condition.json')
                assert condition['speed'] == speed and condition['alpha'] == case['alpha']
                assert condition['stall'] and condition['freeze_influences']
                assert condition['mach'] == (0. if case['pg'] == 'zero' else None)
                with np.load(sub / 'state.npz') as archive:
                    state = {key: archive[key].copy() for key in archive.files}
                v, g = state['velocity'], state['gamma']
                normal = v - np.sum(v * tangents, axis=1)[:, None] * tangents
                local_mach = np.linalg.norm(normal, axis=1) / model.constants[2]
                velocity_error = float(np.max(abs(hv.apply(g) + speed * fields['VINF'] - v)))
                assert velocity_error < 1e-6, (case['id'], velocity_error)
                assert abs(float(local_mach.max()) - record['maximum']['normal_mach']) < 1e-12
                assert record['residual'] < 1e-8 and record['stalled_strips'] == 0
                assert np.all(state['stall_margin'] > 0)
                assert abs(float(state['stall_margin'].min() / .05) - record['minimum_stall_margin_widths']) < 1e-12
                assert record['cached_arrays_reused']
                if previous is not None:
                    assert record['retained_cached_arrays'] > 0
                    scaling = {k: float(np.max(abs(state[k] / speed - previous[k] / previous_speed)))
                               for k in ('gamma', 'velocity')}
                    assert scaling['gamma'] < 1e-13 and scaling['velocity'] < 1e-11
                else:
                    scaling = None
                raw_name = 'Wing_tip_up' if choice['variant'] == 'wingtip_up' else choice['variant']
                suffix = '0_75' if speed == 255 else '0_78'
                raw = np.loadtxt(driver.SOURCE / raw_name / f'{choice["variant"]}_Ma_{suffix}.txt')
                target = raw[raw[:, 71] == case['alpha']]
                assert target.shape == (1, 82)
                reference = {k: float(target[0, col]) for k, col in [('CL',77),('CD',78),('CDi',79),('Cm',80),('efficiency',81)]}
                assert reference == record['reference']
                assert record['native_error_percent'] == {
                    k: 100 * (report['native'][k] / reference[k] - 1) for k in ('CL','CDi','efficiency')}
                values, drag = None, None
                if record['status'] == 'computed':
                    result = driver.read(sub / 'openswing.json')
                    values = {k: result[k] for k in ('CL', 'CD', 'CDi', 'efficiency')}
                    values['Cm'] = result['Cm_origin']
                    assert values == record['values'] and local_mach.max() < 1
                    drag = {k: result[k] for k in ('CDi_near', 'CDp', 'CDi', 'CD')}
                    assert abs(drag['CD'] - drag['CDi_near'] - drag['CDp']) < 1e-12
                    if previous_values is not None:
                        for key in ('CL', 'CD', 'CDi', 'efficiency'):
                            assert abs(values[key] - previous_values[key]) < 1e-12
                    errors = {k: 100 * (v / reference[k] - 1) for k, v in values.items()}
                    assert errors == record['production_error_percent']
                else:
                    assert record['status'] == 'rejected' and local_mach.max() >= 1
                    assert record['values'] is None and not (sub / 'openswing.json').exists()
                    errors = None
                row['production'].append(dict(speed=speed, status=record['status'],
                    maximum_normal_mach=float(local_mach.max()), maximum=record['maximum'],
                    minimum_stall_margin_widths=record['minimum_stall_margin_widths'],
                    stalled_strips=record['stalled_strips'], residual=record['residual'],
                    production_native_gamma_relative_error=record['native_gamma_relative_linf'],
                    production_field_reconstruction_error=velocity_error, normalized_speed_scaling_error=scaling,
                    values=values, reference=reference, drag_components=drag,
                    native_error_percent=record['native_error_percent'], production_error_percent=errors,
                    seconds=record['seconds']))
                previous, previous_values, previous_speed = state, values, speed
        for path in folder.rglob('*'):
            if path.is_file():
                pins[str(path.relative_to(ROOT))] = driver.sha(path)
        rows.append(row)
    assert len(rows) == 12
    assert sum(r['status'] == 'conversion-blocked' for r in rows) == 2
    production = [s for r in rows for s in r['production']]
    assert len(production) == 18
    driver.check(plan)
    result = dict(observed_utc=datetime.now(timezone.utc).isoformat(), cases=rows,
        native_calls=12, planned_production_calls=22, production_calls=18, conversion_blocked_calls=4,
        production_computed=sum(s['status'] == 'computed' for s in production),
        production_rejected=sum(s['status'] == 'rejected' for s in production),
        production_seconds=sum(s['seconds'] for s in production),
        maximum_native_gamma_reconstruction_relative_error=max(r['native_gamma_reconstruction_relative_error'] for r in rows),
        maximum_native_velocity_reconstruction_error=max(r['native_velocity_reconstruction_error'] for r in rows),
        maximum_matched_native_velocity_reconstruction_error=max(r['native_velocity_reconstruction_error'] for r in rows if r['status'] == 'matched-geometry'),
        maximum_matched_native_force_reconstruction_error=max(r['native_force_reconstruction_error'] for r in rows if r['status'] == 'matched-geometry'),
        maximum_production_field_reconstruction_error=max(s['production_field_reconstruction_error'] for s in production),
        plan_sha256=driver.sha(OUT / 'plan.json'), source_pins=plan['pins'], artifact_pins=pins,
        analyzer_sha256=driver.sha(Path(__file__)), original_setup_authenticated=False,
        production_equations_changed=False, primary_fraction_or_scope_changed=False)
    driver.write(OUT / 'analysis.json', result)
    print(json.dumps({k:v for k,v in result.items() if k not in ('cases','source_pins','artifact_pins')}), flush=True)
    plot(rows)


def plot(rows):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    colors = re.findall(r"'(#\w+)'", (ROOT / 'web/plot-colors.js').read_text().split('export const plotColors')[1].split(']);')[0])
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.6))
    labels = {'baseline_original':'Baseline, slope 7', 'baseline_slope634':'Baseline, slope 6.34',
              'upper_plus4':'Upper winglet, +4°', 'upper_minus4':'Upper winglet, −4°'}
    for choice, color in zip(labels, colors):
        selected = [r for r in rows if r['case']['choice'] == choice and r['case']['pg'] == 'zero']
        for ax, key in zip(axes, ('CL','CDi')):
            ax.plot([r['case']['alpha'] for r in selected],
                    [r['production'][0]['native_error_percent'][key] for r in selected],
                    'o-', color=color, label=labels[choice])
    for ax, key in zip(axes, ('CL','CDi')):
        ax.axhspan(-5, 5, color='#888888', alpha=.12, label='±5% comparison band')
        ax.axhline(0, color='#666666', linewidth=.7)
        ax.set(xlabel='Angle of attack (degrees)', ylabel=f'Native AVL {key} error (%)', xticks=[0,1])
        ax.grid(alpha=.2)
    axes[0].legend(fontsize=8)
    fig.suptitle('SA-11 .75 archive: fixed-zero-PG / cant0 normalization candidates\nIndependent alternatives; no primary passes added')
    fig.tight_layout()
    fig.savefig(OUT / 'fixed-pg-candidate.png', dpi=150)
    fig.savefig(OUT / 'fixed-pg-candidate.svg')
    plt.close(fig)


if __name__ == '__main__':
    main()
