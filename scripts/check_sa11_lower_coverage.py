"""Independently replay one saved SA-11 lower-winglet state; no physical solve."""
import argparse
import math
from pathlib import Path
import sys

import verify_sa11_paper_aligned as recorder

ROOT = Path(__file__).resolve().parents[1]


def check(out, index):
    recorder.bounded()
    plan = recorder.read(out / 'plan.json')
    recorder.check(plan['pins'])
    case = plan['cases'][index]
    folder = out / case['id']
    row = recorder.read(folder / 'report.json')
    assert row['case'] == case and row['plan_sha256'] == recorder.sha(out / 'plan.json')
    for name, digest in row['artifacts'].items():
        assert recorder.sha(folder / name) == digest
    tokens = [line.split() for line in (ROOT / case['table']).read_text().splitlines()
              if len(line.split()) == 82 and line.split()[0].isdigit()][case['row']]
    assert tokens == case['tokens']
    assert float(tokens[69]) == case['condition']['speed'] and float(tokens[71]) == case['alpha']
    assert row['physical_calls'] == 1
    import numpy as np
    sys.path.insert(0, str(ROOT))
    from openswing.asw import parse_asw
    from openswing.geometry import model_meshes
    from avl_vorvelc_reference import matrix
    model = parse_asw((ROOT / case['model_path']).read_text(), beam_interpolation='natural-v1')
    meshes = model_meshes(model, case['mesh'])
    sample = lambda key: np.concatenate([m.beam.value(key, m.tm) for m in meshes])
    span = np.concatenate([m.frames[..., 1] for m in meshes])
    normal = np.concatenate([np.sin(np.deg2rad(m.beam.value('alpha', m.tm)))[:, None] * m.frames[..., 0]
        + np.cos(np.deg2rad(m.beam.value('alpha', m.tm)))[:, None] * m.frames[..., 2] for m in meshes])
    with np.load(folder / 'geometry.npz') as saved:
        g = {key: saved[key] for key in saved}
    with np.load(ROOT / 'artifacts/isae/sa11-two-winglet-spacing-20261108/m0_70-a00/geometry.npz') as saved:
        for key in saved:
            np.testing.assert_array_equal(g[key], saved[key])
    np.testing.assert_array_equal(g['span'], span)
    assert np.all(sample('CLmax') == .8)
    errors = {}
    diagnostic = {}
    if row['status'] == 'rejected':
        details = recorder.read(folder / 'rejected.json')['details']
        assert details['kind'] == 'section_normal_mach'
        assert details['maximum']['normal_mach'] >= 1 and details['circulation_residual'] < 1e-8
        assert row['values'] is None and not (folder / 'accepted.json').exists()
        diagnostic['rejection'] = details
        diagnostic['qualification'] = 'Rejected-state accounting only; no full saved-field replay or accepted force comparison.'
    else:
        assert row['status'] == 'computed'
        raw = recorder.read(folder / 'accepted.json')
        assert raw['converged'] and raw['residual'] < 1e-8
        gamma = np.array([s['circulation'] for s in raw['strips']])
        saved_v = np.array([s['relative_velocity'] for s in raw['strips']])
        saved_force = np.array([s['force'] for s in raw['strips']])
        speed = case['condition']['speed']
        alpha = math.radians(case['alpha'])
        flight = speed * np.array([math.cos(alpha), 0., math.sin(alpha)])
        # Independent AVL segment/ray law, no quartic core. Convert its rounded
        # Fortran 1/(4pi) constant to the exact constant used in ASWING equations.
        scale = np.longdouble(1) / (4 * np.arccos(np.longdouble(-1)) * np.longdouble('.079577472'))
        velocities = []
        for target, exclude in ((g['hv'], True), (g['cp'], False)):
            operator = matrix(target, g['a'], g['b'], speed / 340.21,
                exclude_self=exclude, core_fraction=0., dtype=np.longdouble)
            velocities.append(np.asarray(np.einsum('ijq,j->iq', operator, gamma) * scale + flight, dtype=float))
            del operator
        v, vcp = velocities
        errors['velocity_relative'] = float(np.max(abs(v - saved_v)) / speed)
        perp = v - np.sum(v * span, axis=1)[:, None] * span
        vp = np.linalg.norm(perp, axis=1)
        mach = vp / 340.21
        errors['normal_mach'] = float(max(abs(mach - np.array([s['normal_mach'] for s in raw['strips']]))))
        assert max(mach) < 1
        cl = 2 * gamma / (vp * g['chord'])
        errors['section_cl'] = float(max(abs(cl - np.array([s['cl'] for s in raw['strips']]))))
        width = case['condition']['stall_width']
        strength = case['condition']['stall_factor']
        f = width * (np.logaddexp(0, (cl - sample('CLmax')) / width)
                     - np.logaddexp(0, (sample('CLmin') - cl) / width))
        tangency = np.sum(vcp * normal, axis=1)
        leakage = vp * strength * f / sample('dCLda')
        errors['tangency_relative'] = float(max(abs(tangency - leakage)) / speed)
        rho = 1.2256
        vortex = rho * gamma[:, None] * np.cross(v, span) * g['ds'][:, None]
        friction = .5 * rho * np.linalg.norm(v, axis=1)[:, None] * v * (g['chord'] * sample('Cdf') * g['ds'])[:, None]
        pressure = .5 * rho * vp[:, None] * perp * (g['chord'] * sample('Cdp') * g['ds'])[:, None]
        stall_drag = 2 * rho * perp / vp[:, None] * (tangency**2 * g['chord'] * g['ds'])[:, None]
        force = vortex + friction + pressure + stall_drag
        errors['force_vector'] = float(np.max(abs(force - saved_force)))
        total = [math.fsum(force[:, i]) for i in range(3)]
        qs = .5 * rho * speed**2 * .9329
        cl_total = (total[2] * math.cos(alpha) - total[0] * math.sin(alpha)) / qs
        cd_total = (total[0] * math.cos(alpha) + total[2] * math.sin(alpha)) / qs
        errors['force_coefficients'] = max(abs(cl_total - row['values']['CL']), abs(cd_total - row['values']['CD']))
        moment = math.fsum(s['moment'][1] + s['position'][2] * s['force'][0]
                          - s['position'][0] * s['force'][2] for s in raw['strips'])
        errors['moment_coefficient'] = abs(moment / (qs * .37874) - row['values']['Cm_origin'])
        for key, column in recorder.FIELDS.items():
            assert case['reference'][key] == float(tokens[column])
            assert abs(row['errors_percent'][key] - 100 * (row['values'][key] / float(tokens[column]) - 1)) < 2e-10
        assert errors['velocity_relative'] < 2e-10 and errors['normal_mach'] < 2e-12
        assert errors['section_cl'] < 2e-12 and errors['tangency_relative'] < 1e-8
        assert errors['force_vector'] < 1e-9 and errors['force_coefficients'] < 2e-12
        assert errors['moment_coefficient'] < 2e-12
        axis = np.array([math.cos(alpha), 0., math.sin(alpha)])
        diagnostic.update(maximum_normal_mach=float(max(mach)),
            maximum_leakage_angle_degrees=math.degrees(float(max(abs(strength * f / sample('dCLda'))))),
            drag_parts={key: float(np.sum(value @ axis) / qs) for key, value in
                        [('vortex', vortex), ('friction', friction), ('pressure', pressure), ('stall_leakage', stall_drag)]})
    result = dict(verified=True, observed_utc=recorder.utc(), case=case['id'], status=row['status'],
        errors=errors, diagnostic=diagnostic, physical_calls=0,
        plan_sha256=recorder.sha(out / 'plan.json'), report_sha256=recorder.sha(folder / 'report.json'),
        checker_sha256=recorder.sha(Path(__file__)), source_pins_verified=len(plan['pins']))
    recorder.write(folder / 'verification.json', result)
    recorder.signal.alarm(0)
    print({key: value for key, value in result.items() if key != 'diagnostic'})
    print({key: value for key, value in diagnostic.items() if key != 'rejection'})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--index', type=int, required=True)
    args = parser.parse_args()
    check(args.output.resolve(), args.index)
