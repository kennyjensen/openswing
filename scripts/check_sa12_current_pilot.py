"""Replay one saved SA-12 pilot with an independent vortex/image calculation."""
import argparse
from decimal import Decimal
import math
from pathlib import Path
import sys

import verify_sa12_current_pilot as recorder

ROOT = Path(__file__).resolve().parents[1]


def check(out, index):
    recorder.bounded()
    plan = recorder.read(out / 'plan.json')
    recorder.authenticate(plan['pins'])
    case = plan['cases'][index]
    folder = out / case['id']
    report = recorder.read(folder / 'report.json')
    assert report['case'] == case
    assert report['plan_sha256'] == recorder.sha(out / 'plan.json')
    for name, digest in report['artifacts'].items():
        assert recorder.sha(folder / name) == digest
    row = recorder.read(folder / 'result.json')
    job, settings = case['job'], case['job']['settings']
    tokens = (ROOT / job['table_path']).read_text().splitlines()[job['reference_row']['line_number'] - 1].split()
    assert tokens == job['reference_row']['tokens']
    assert row['numerical_pass'] and row['physical_calls'] == 1
    assert all(c['passed'] for c in row['numerical_checks'])
    import numpy as np
    sys.path.insert(0, str(ROOT))
    from openswing.asw import parse_asw
    from openswing.geometry import model_meshes
    from avl_vorvelc_reference import matrix
    model = parse_asw((ROOT / job['model_path']).read_text(), beam_interpolation=settings['beam_interpolation'])
    meshes = model_meshes(model, settings['panels'])
    sample = lambda key: np.concatenate([m.beam.value(key, m.tm) for m in meshes])
    span = np.concatenate([m.frames[..., 1] for m in meshes])
    normal = np.concatenate([np.sin(np.deg2rad(m.beam.value('alpha', m.tm)))[:, None] * m.frames[..., 0]
        + np.cos(np.deg2rad(m.beam.value('alpha', m.tm)))[:, None] * m.frames[..., 2] for m in meshes])
    with np.load(folder / 'geometry.npz') as saved:
        g = {key: saved[key] for key in saved}
    np.testing.assert_array_equal(span, g['span'])
    raw = row['verification_payload']
    gamma = np.array([s['circulation'] for s in raw['strips']])
    saved_v = np.array([s['relative_velocity'] for s in raw['strips']])
    saved_force = np.array([s['force'] for s in raw['strips']])
    alpha = math.radians(settings['alpha'])
    wind = np.array([math.cos(alpha), 0., math.sin(alpha)])
    lift = np.array([-math.sin(alpha), 0., math.cos(alpha)])
    rotation = np.array([wind, [0., 1., 0.], lift])
    height = settings['position_earth'][2]
    assert settings['attitude'] == [0., settings['alpha'], 0.]
    assert settings['ground_effect'] == 1 and settings['mach'] == 0 and not settings['freeze_influences']
    # Drela Eqs.165--175: reflect every source, including each self image.
    # The prescribed pitch makes the wake parallel to the board.
    reflect = lambda p: p - 2 * (p @ lift + height)[:, None] * lift
    image_a, image_b = reflect(g['a']), reflect(g['b'])
    scale = np.longdouble(1) / (4 * np.arccos(np.longdouble(-1)) * np.longdouble('.079577472'))
    velocities = []
    for target, exclude in ((g['hv'], True), (g['cp'], False)):
        operator = matrix(target @ rotation.T, g['a'] @ rotation.T, g['b'] @ rotation.T,
            0., exclude_self=exclude, core_fraction=0., dtype=np.longdouble)
        operator -= matrix(target @ rotation.T, image_a @ rotation.T, image_b @ rotation.T,
            0., exclude_self=False, core_fraction=0., dtype=np.longdouble)
        velocities.append(np.asarray(np.einsum('ijq,j->iq', operator, gamma) * scale, dtype=float) @ rotation
                          + settings['speed'] * wind)
        del operator
    v, vcp = velocities
    speed, rho = settings['speed'], settings['density']
    perp = v - np.sum(v * span, axis=1)[:, None] * span
    vp = np.linalg.norm(perp, axis=1)
    cl = 2 * gamma / (vp * g['chord'])
    width = settings['stall_width']
    f = width * (np.logaddexp(0, (cl - sample('CLmax')) / width)
                 - np.logaddexp(0, (sample('CLmin') - cl) / width))
    tangency = np.sum(vcp * normal, axis=1)
    leakage = vp * settings['stall_factor'] * f / sample('dCLda')
    vortex = rho * gamma[:, None] * np.cross(v, span) * g['ds'][:, None]
    friction = .5 * rho * np.linalg.norm(v, axis=1)[:, None] * v * (g['chord'] * sample('Cdf') * g['ds'])[:, None]
    pressure = .5 * rho * vp[:, None] * perp * (g['chord'] * sample('Cdp') * g['ds'])[:, None]
    stall_drag = 2 * rho * perp / vp[:, None] * (tangency**2 * g['chord'] * g['ds'])[:, None]
    force = vortex + friction + pressure + stall_drag
    total = np.array([math.fsum(force[:, i]) for i in range(3)])
    qs = .5 * rho * speed**2 * model.reference[0, 0]
    # Separate infinite-line calculation, not a call to production Trefftz.
    wake = np.zeros_like(g['hv'])
    for endpoints, sign in ((g['b'], 1), (g['a'], -1), (image_b, -1), (image_a, 1)):
        r = g['hv'][:, None, :] - endpoints[None, :, :]
        r -= (r @ wind)[..., None] * wind
        r2 = np.sum(r * r, axis=2)
        assert np.min(r2) > 0
        wake += sign * np.einsum('ijq,j->iq', np.cross(wind, r) / r2[..., None], gamma) / (2 * math.pi)
    cdi = -.5 * rho * math.fsum(gamma * np.sum(wake * np.cross(wind, g['b'] - g['a']), axis=1)) / qs
    moment = math.fsum(s['moment'][1] + (s['position'][2] - model.reference[1, 2]) * s['force'][0]
                      - (s['position'][0] - model.reference[1, 0]) * s['force'][2] for s in raw['strips'])
    errors = dict(velocity_relative=float(np.max(abs(v - saved_v)) / speed),
        section_cl=float(max(abs(cl - np.array([s['cl'] for s in raw['strips']])))),
        tangency_relative=float(max(abs(tangency - leakage)) / speed),
        force_vector=float(np.max(abs(force - saved_force))),
        CL=abs(float(total @ lift / qs) - raw['CL']),
        CD=abs(float(total @ wind / qs) - raw['CD']),
        CDi=abs(float(cdi) - raw['CDi']),
        Cm=abs(moment / (qs * model.reference[0, 1]) - raw['Cm']))
    assert errors['velocity_relative'] < 2e-10 and errors['section_cl'] < 2e-12, errors
    assert errors['tangency_relative'] < 1e-8 and errors['force_vector'] < 1e-9, errors
    assert max(errors[k] for k in ('CL', 'CD', 'CDi', 'Cm')) < 2e-12, errors
    for comparison, column in zip(report['comparisons'], range(5, 9), strict=True):
        expected = Decimal(tokens[column])
        name = comparison['name']
        original = Decimal(str(job['reference_row']['fields'][name]['tolerance']))
        tolerance = original if abs(expected) <= Decimal('1e-8') else max(original, Decimal('.05') * abs(expected))
        actual = Decimal(str(row['result']['predicted'][name]))
        assert comparison['expected'] == float(expected) and comparison['actual'] == float(actual)
        # Float multiplication may round one ulp differently from Decimal;
        # the actual pass decision below uses the exact decimal gate.
        assert math.isclose(comparison['tolerance'], float(tolerance), rel_tol=5e-16, abs_tol=0.)
        assert comparison['passed'] == (abs(actual - expected) <= tolerance)
    result = dict(verified=True, observed_utc=recorder.utc(), case=case['id'], physical_calls=0,
        errors=errors, passed=report['passed'], required=4,
        drag_parts={key: float(math.fsum(value @ wind) / qs) for key, value in
                    [('vortex', vortex), ('friction', friction), ('pressure', pressure), ('stall_leakage', stall_drag)]},
        native_CD_minus_CDi=float(Decimal(tokens[6]) - Decimal(tokens[7])),
        plan_sha256=recorder.sha(out / 'plan.json'), report_sha256=recorder.sha(folder / 'report.json'),
        checker_sha256=recorder.sha(Path(__file__)), source_pins_verified=len(plan['pins']))
    recorder.write(folder / 'verification.json', result)
    recorder.signal.alarm(0)
    print(result)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--index', type=int, required=True)
    args = parser.parse_args()
    check(args.output.resolve(), args.index)
