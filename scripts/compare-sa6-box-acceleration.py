"""Compare the documented box acceleration response on SA-6's declared meshes.

The source-box Jacobian is generally nonsymmetric. These literal constant,
straight sections are the special case where it is a physical midpoint mass.
This is a separate diagnostic, not a replacement of the registered ledger or
proof of the historical tensor exporter's undisclosed mesh/quadrature.
"""
from pathlib import Path
import argparse
import csv
from decimal import Decimal
import hashlib
import json
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np
from openswing.asw import parse_asw
from openswing.geometry import model_meshes, surface_frame
from openswing.apparent_box import rigid_acceleration_response
from openswing.inertia import apparent_properties
from isae_suite_sa6_mass import decode, declared_nodes


def pin(path):
    path = Path(path)
    data = path.read_bytes()
    return dict(path=str(path.relative_to(ROOT)), bytes=len(data), sha256=hashlib.sha256(data).hexdigest())


def compute(job):
    settings = job['settings']
    model = parse_asw((ROOT/job['model_path']).read_text(), beam_interpolation=settings['beam_interpolation'])
    meshes = model_meshes(model, settings['panels'])
    rho = settings['density']
    box, independent = np.zeros((6, 6)), np.zeros((6, 6))
    samples = []
    for mesh in meshes:
        assert mesh.beam.lifting, 'This diagnostic requires the original lifting-only SA-6 models.'
        nodes = np.r_[mesh.r0[:, 1], mesh.r1[-1, 1]]
        np.testing.assert_allclose(nodes, declared_nodes(job), rtol=0, atol=2e-12)
        endpoints = []
        for t, side, position in ((mesh.t0, 'right', mesh.r0), (mesh.t1, 'left', mesh.r1)):
            frame = surface_frame(mesh.beam, t, side)
            chord = mesh.beam.value('chord', t, side=side)
            xax = mesh.beam.value('Xax', t, side=side)
            endpoints.append((frame, chord, xax, position))
        a, b = endpoints
        pieces = rigid_acceleration_response(mesh.r0, mesh.r1, a[0], b[0], a[1], b[1],
            a[2], b[2], mesh.length, rho, np.zeros(3))
        box += pieces.sum(axis=0)
        # Direct force/couple evaluation of all six impulses, independent of
        # the production matrix assembly and its local wrench helper.
        for col, impulse in enumerate(np.eye(6)):
            force, couple = np.zeros_like(mesh.r0), np.zeros_like(mesh.r0)
            for frame, chord, xax, position in endpoints:
                normal, span, chord_axis = frame[..., 2], frame[..., 1], frame[..., 0]
                offset = ((.5-xax)*chord)[:, None]*chord_axis
                acceleration = impulse[:3]+np.cross(impulse[3:], position+offset)
                mu = rho*np.pi*chord**2/4
                f = -(mu*np.sum(acceleration*normal, axis=1))[:, None]*normal
                m = np.cross(offset, f)-(mu*chord**2/32*(span@impulse[3:]))[:, None]*span
                force += mesh.length[:, None]*f/2
                couple += mesh.length[:, None]*m/2
            midpoint = (mesh.r0+mesh.r1)/2
            independent[:, col] -= np.r_[force.sum(axis=0),
                (couple+np.cross(midpoint, force)).sum(axis=0)]
        samples.append(dict(beam=mesh.beam.index, r0=mesh.r0.tolist(), r1=mesh.r1.tolist(),
            length=mesh.length.tolist(), frame0=a[0].tolist(), frame1=b[0].tolist(),
            chord0=a[1].tolist(), chord1=b[1].tolist(), xax0=a[2].tolist(), xax1=b[2].tolist()))
    np.testing.assert_allclose(box, independent, rtol=2e-12, atol=2e-14)
    # Symmetry is checked for this constant SA-6 geometry, not imposed on the
    # general endpoint operator. Keep every computed entry without snapping.
    np.testing.assert_allclose(box, box.T, rtol=0, atol=2e-14)
    legacy = np.asarray(apparent_properties(meshes, rho, np.zeros(3))['spatial_matrix'])
    return dict(model_path=job['model_path'], nominal_intervals=settings['panels'],
        actual_intervals=sum(len(m.tm) for m in meshes), density=rho,
        box_matrix=box.tolist(), impulse_matrix=independent.tolist(), legacy_matrix=legacy.tolist(),
        max_impulse_discrepancy=float(np.max(abs(box-independent))),
        max_antisymmetric_entry=float(np.max(abs(box-box.T))), samples=samples)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', required=True, type=Path)
    args = parser.parse_args()
    out = args.output_dir
    out.mkdir(parents=True, exist_ok=True)
    assert not (out/'comparison.json').exists(), 'Preserve existing evidence; choose a new output directory.'
    started = time.monotonic()
    plan_path = ROOT/'artifacts/isae/sa6-mass-tensors-20261028/batch/plan.json'
    plan_pin = pin(plan_path)
    code = [pin(path) for path in sorted((ROOT/'openswing').glob('*.py'))]
    code += [pin(ROOT/name) for name in ('scripts/compare-sa6-box-acceleration.py',
        'scripts/isae_suite_sa6_mass.py', 'scripts/isae_suite_sa6_mass_math.py',
        'scripts/isae_suite_sa6_controls.py')]
    plan = json.loads(plan_path.read_text())
    jobs = plan['jobs']
    assert len(jobs) == 88 and {j['settings']['panels'] for j in jobs} == {64, 128}
    source_pins = {}
    for job in jobs:
        for original in job['sources']:
            if original['path'].startswith('.reference/'):
                actual = pin(ROOT/original['path'])
                assert actual == original, 'Original input changed: '+original['path']
                source_pins[actual['path']] = actual
    calculations, comparisons = {}, []
    triangle = ((0, 0, 'xx'), (0, 1, 'xy'), (0, 2, 'xz'), (1, 1, 'yy'), (1, 2, 'yz'), (2, 2, 'zz'))
    for job in jobs:
        key = job['model_path']+':'+str(job['settings']['panels'])
        if key not in calculations:
            calculations[key] = compute(job)
        record = calculations[key]
        fields = decode((ROOT/job['table_path']).read_text())
        for block, offset in (('apparent_mass', 0), ('apparent_inertia_origin', 3), ('apparent_inertia_centroid', 3)):
            assert job['reported_centroid'] == [0., 0., 0.]
            for i, j, label in triangle:
                channel = block+'.'+label
                field = fields[channel]
                assert field == job['reference_row']['fields'][channel]
                target = Decimal(field['token'])
                tolerance = Decimal(field['exact_decimal_tolerance'])
                row = dict(job_id=job['id'], calculation=key, channel=channel,
                    nominal_intervals=job['settings']['panels'], source_path=job['table_path'],
                    source_token=field['token'], tolerance=str(tolerance))
                for method in ('box', 'legacy'):
                    prediction = record[method+'_matrix'][i+offset][j+offset]
                    error = abs(Decimal(str(prediction))-target)
                    row.update({method+'_prediction':prediction, method+'_absolute_error':float(error),
                        method+'_percent_error':float(100*error/abs(target)) if target else None,
                        method+'_passed':error <= tolerance})
                comparisons.append(row)
    assert len(calculations) == 8 and len(comparisons) == 1584
    statistics = {}
    for mesh in (64, 128):
        rows = [r for r in comparisons if r['nominal_intervals']==mesh]
        channels = {}
        for channel in sorted({r['channel'] for r in rows}):
            group = [r for r in rows if r['channel']==channel]
            channels[channel] = {method:dict(passes=sum(r[method+'_passed'] for r in group), count=len(group),
                failed_median_percent=float(np.median([r[method+'_percent_error'] for r in group
                    if not r[method+'_passed'] and r[method+'_percent_error'] is not None]))
                    if any(not r[method+'_passed'] and r[method+'_percent_error'] is not None for r in group) else None)
                for method in ('box', 'legacy')}
        statistics[str(mesh)] = dict(checks=len(rows), channels=channels,
            **{method+'_passes':sum(r[method+'_passed'] for r in rows) for method in ('box', 'legacy')})
    evidence = dict(status='COMPLETED', scope='Separate source-box rigid acceleration diagnostic; registered scores unchanged',
        qualifications=['Historical exporter and mesh are not recovered.',
            'Eight model/mesh operators are shared across 44 control states because these undeformed mass coefficients do not depend on controls.',
            'Only the 18 apparent entries per job are compared; no new real-mass result or whole-case pass is claimed.',
            'All reference values and half-printed-unit gates are unchanged; tiny nonzeros remain required.',
            'No symmetric projection, fitted mesh or parameter adjustment is used.'],
        plan=plan_pin, source_pins=list(source_pins.values()), code_pins=code,
        calculations=calculations, statistics=statistics, comparisons=comparisons,
        operations=dict(models_and_meshes=8, rigid_response_assemblies=8, independent_impulse_columns=48,
            legacy_matrix_assemblies=8, aerodynamic_solves=0, nonlinear_solves=0),
        elapsed_seconds=time.monotonic()-started)
    for source in evidence['source_pins']+code+[plan_pin]:
        assert pin(ROOT/source['path']) == source
    (out/'comparison.json').write_text(json.dumps(evidence, indent=2, allow_nan=False)+'\n')
    with (out/'comparisons.csv').open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(comparisons[0]))
        writer.writeheader(); writer.writerows(comparisons)
    print(json.dumps(dict(status=evidence['status'], elapsed_seconds=evidence['elapsed_seconds'],
        operations=evidence['operations'], statistics=statistics), indent=2), flush=True)


if __name__ == '__main__':
    main()
