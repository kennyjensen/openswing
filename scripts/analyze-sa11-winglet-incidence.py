"""Audit the two saved SA-11 twist-sign cases without running another solve."""
from datetime import datetime, timezone
import ast
import hashlib
import importlib.util
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'artifacts/isae/sa11-winglet-incidence-20261108'
SPEC = importlib.util.spec_from_file_location(
    'incidence', ROOT / 'scripts/verify-sa11-winglet-incidence.py')
INCIDENCE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(INCIDENCE)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
read = lambda path: json.loads(path.read_text())


def main():
    plan = read(BASE / 'plan.json')
    assert sha(BASE / 'driver-used.py') == plan['driver_sha256']
    assert sha(ROOT / 'scripts/verify-sa11-winglet-incidence.py') == plan['driver_sha256']
    assert sha(INCIDENCE.BINARY) == plan['binary_sha256']
    for name, pin in plan['unchanged_pins'].items():
        assert sha(ROOT / name) == pin, name

    rows, fields, pins = [], [], {}
    for case in plan['cases']:
        directory = BASE / case['id']
        report = read(directory / 'report.json')
        pins[str((directory / 'report.json').relative_to(ROOT))] = sha(directory / 'report.json')
        for name, pin in report['artifact_sha256'].items():
            assert sha(directory / name) == pin, name
        assert read(directory / 'process.json')['returncode'] == 0
        status = report['production']
        assert status['status'] == 'rejected'
        assert status['details']['kind'] == 'section_normal_mach'
        assert status['residual'] < 1e-8
        assert not (directory / 'openswing.json').exists()
        model = INCIDENCE.model_at(case['twist'])
        _, segments = INCIDENCE.CONVERT.conversion(model, 1)
        with np.load(directory / 'native-fields.npz') as archive:
            f = {name: archive[name].copy() for name in archive.files}
        fields.append(f)
        meshes, _, errors, _ = INCIDENCE.CONVERT.mapped_meshes(model, f, segments)
        assert max(errors.values()) < 2e-11
        assert len(f['GAM']) == 64
        tangent = np.concatenate([mesh.frames[..., 1] for mesh in meshes])
        native_velocity = 240 * (f['VV'] + f['VINF'])
        native_normal = native_velocity - np.sum(native_velocity * tangent, axis=1)[:, None] * tangent
        native_mach = np.linalg.norm(native_normal, axis=1) / 340.21
        with np.load(directory / 'diagnostic-state.npz') as state:
            gamma = state['gamma']
            velocity = state['velocity']
            normal = velocity - np.sum(velocity * tangent, axis=1)[:, None] * tangent
            production_mach = np.linalg.norm(normal, axis=1) / 340.21
            gamma_error = np.max(abs(gamma / 240 - f['GAM'].ravel())) / np.max(abs(f['GAM']))
            margin = float(np.min(state['stall_margin']) / .05)
            assert np.all(state['stall_margin'] > 0)
        assert abs(float(production_mach.max()) - status['maximum_section_normal_mach']) < 1e-12
        assert abs(gamma_error - report['native_production_gamma_relative_linf']) < 1e-14
        assert abs(margin - report['minimum_stall_margin_widths']) < 1e-12
        assert native_mach.max() > 1

        # Recover native vortex force directly from the retained element fields.
        force = np.sum(2 * f['GAM'] * np.cross(f['VINF'] + f['VV'], f['RV2'] - f['RV1']), axis=0) / model.reference[0, 0]
        angle = np.deg2rad(1.)
        lift_axis = np.array([-np.sin(angle), 0., np.cos(angle)])
        reconstructed = {'CL': float(force @ lift_axis), 'CD_near': float(force @ f['VINF'][0])}
        force_error = max(abs(reconstructed[k] - report['native'][k]) for k in reconstructed)
        assert force_error < 1e-12, force_error
        labels = INCIDENCE.CONVERT.MATCHED.NATIVE.labeled(directory / 'total.txt')
        assert abs(labels["Mach, rb/2V, r'b/2V"][0] - 240 / 340.21) < 1e-14
        assert labels['CLtot'][0] == report['native']['CL']
        assert labels['Trefftz Plane: CLff, CDff, CYff, e'][1] == report['native']['CDi']
        rows.append(dict(
            case=case, native=report['native'], reference=report['reference'],
            native_error_percent=report['native_error_percent'],
            production_status=status['status'], production_residual=status['residual'],
            production_maximum_section_normal_mach=float(production_mach.max()),
            native_maximum_section_normal_mach_using_asw_axis=float(native_mach.max()),
            native_production_gamma_relative_linf_percent=float(100 * gamma_error),
            minimum_stall_margin_widths=margin, geometry_maximum_error=max(errors.values()),
            native_force_reconstruction_maximum_error=force_error,
            native_seconds=read(directory / 'process.json')['seconds'],
            production_seconds=report['openswing_seconds']))

    texts = [(BASE / case['id'] / 'model.avl').read_text().splitlines() for case in plan['cases']]
    assert len(texts[0]) == len(texts[1])
    changes = []
    for index, (left, right) in enumerate(zip(*texts)):
        if left == right:
            continue
        assert texts[0][index - 1] == texts[1][index - 1] == 'SECTION'
        a, b = left.split(), right.split()
        assert len(a) == len(b) == 7
        changed = [i for i, (x, y) in enumerate(zip(a, b)) if x != y]
        assert changed == [4], changed
        changes.append(dict(line=index + 1, original_incidence=float(a[4]), alternative_incidence=float(b[4])))
    assert len(changes) == 4
    geometry_change = {name: float(np.max(abs(fields[0][name] - fields[1][name])))
                       for name in ('RV1', 'RV2', 'RV', 'RC')}
    assert max(geometry_change.values()) < 1e-14
    for name in ('verify-sa11-winglet-incidence.py', 'analyze-sa11-winglet-incidence.py'):
        ast.parse((ROOT / 'scripts' / name).read_text())
    output = BASE / 'analysis.json'
    assert not output.exists(), output
    output.write_text(json.dumps(dict(
        observed_utc=datetime.now(timezone.utc).isoformat(), cases=rows,
        report_sha256=pins, unchanged_pins=plan['unchanged_pins'],
        native_input_changes=changes, maximum_native_geometry_change=geometry_change,
        geometry_audit=plan['geometry_audit'],
        interpretation='The report-derived sign change improves native AVL lift/CDi agreement at this one archived operating point. Native and production fields still exceed the ASW section-normal Mach limit. This supports an input-conflict investigation, not a validated production result or proof of the archived generating input.',
        primary_status='SA-11 remains 163/4592 at 5%; no production or registered input/scope change.'
    ), indent=2, allow_nan=False) + '\n')
    print(json.dumps(dict(cases=rows, unchanged_pins=len(plan['unchanged_pins']),
                         native_input_changes=changes, maximum_native_geometry_change=geometry_change)))


if __name__ == '__main__':
    main()
