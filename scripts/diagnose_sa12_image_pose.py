"""Bounded SA-12 pose/wake diagnostics; alternative operators are not production."""
import argparse
import math
from pathlib import Path
import resource
import sys
import time

import verify_sa12_current_pilot as io

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'artifacts/isae/sa12-current-pilot-20261108'
VARIANTS = [
    dict(id='parallel-reflected', pitch=8., frozen=False, reflect_wake=True),
    dict(id='zero-reflected', pitch=0., frozen=False, reflect_wake=True),
    dict(id='zero-shared-wake', pitch=0., frozen=False, reflect_wake=False),
    dict(id='zero-frozen', pitch=0., frozen=True, reflect_wake=True),
]


def prepare(out):
    io.bounded()
    baseline = io.read(BASE / 'plan.json')
    io.authenticate(baseline['pins'])
    pins = dict(baseline['pins'])
    for p in [Path(__file__), BASE / 'analysis.json', BASE / 'No_Flap-h05-a8/result.json',
              BASE / 'No_Flap-h05-a8/geometry.npz',
              ROOT / 'reference/aswing-authoritative-20261108/aswing-extended-user-manual.txt']:
        pins[str(p.relative_to(ROOT))] = io.sha(p)
    assert not out.exists()
    out.mkdir(parents=True)
    io.write(out / 'plan.json', dict(observed_utc=io.utc(), pins=pins, variants=VARIANTS,
        baseline_job=baseline['cases'][3]['job'],
        rationale='Separate the unarchived Euler pose and startup K/F state from image-wake direction. Shared-wake variant reflects endpoints but deliberately not the ray direction; it tests an interpretation, not an authorized physics change. All original reference values and production defaults retained.',
        reference_basis='Drela steady sections4.2,4.5,4.6; Eqs160,165--177. Jan PartI p38/Fig23. Ground images must reflect complete vortex paths to satisfy induced no-through-flow.',
        limits='One foreground diagnostic solve per invocation;512MiB,15CPU/25wall seconds,one BLAS thread.',
        prior_turn='Progress: six current production states and independent fields verified, SA12 focus recorded.'))
    (out / 'driver-used.py').write_text(Path(__file__).read_text())
    io.signal.alarm(0)
    print('Prepared four separate diagnostic solves; no primary scope changes.')


def run(out, index):
    io.bounded()
    start_time = time.monotonic()
    plan = io.read(out / 'plan.json')
    io.authenticate(plan['pins'])
    variant = plan['variants'][index]
    directory = out / variant['id']
    assert not directory.exists()
    import numpy as np
    sys.path.insert(0, str(ROOT))
    from openswing.asw import parse_asw
    from openswing.geometry import model_meshes
    from openswing.frozen_influence import lifting_geometry
    from avl_vorvelc_reference import matrix
    job = plan['baseline_job']
    s = job['settings']
    model = parse_asw((ROOT / job['model_path']).read_text(), beam_interpolation=s['beam_interpolation'])
    meshes = model_meshes(model, s['panels'])
    sample = lambda key: np.concatenate([m.beam.value(key, m.tm) for m in meshes])
    span = np.concatenate([m.frames[..., 1] for m in meshes])
    normal = np.concatenate([m.frames[..., 2] for m in meshes])
    assert np.all(sample('alpha') == 0) and np.all(sample('Cdp') == 0)
    alpha = math.radians(s['alpha'])
    wind = np.array([math.cos(alpha), 0., math.sin(alpha)])
    lift = np.array([-math.sin(alpha), 0., math.cos(alpha)])
    direction = np.array([1., 0., 0.]) if variant['frozen'] else wind
    pitch = math.radians(variant['pitch'])
    ground_normal = np.array([-math.sin(pitch), 0., math.cos(pitch)])
    height = s['position_earth'][2]
    reflection = np.eye(3) - 2 * np.outer(ground_normal, ground_normal)
    reflect = lambda p: p @ reflection.T - 2 * height * ground_normal
    image_direction = direction @ reflection.T if variant['reflect_wake'] else direction
    g = lifting_geometry(meshes, direction)

    def operator(points, a, b, axis, exclude=False):
        rotation = np.array([axis, [0., 1., 0.], np.cross(axis, [0., 1., 0.])])
        m = matrix(points @ rotation.T, a @ rotation.T, b @ rotation.T, 0.,
                   exclude_self=exclude, core_fraction=0.)
        return (m @ rotation) / (4 * math.pi * .079577472)

    def components(points, exclude=False):
        return (operator(points, g['a'], g['b'], direction, exclude),
                -operator(points, reflect(g['a']), reflect(g['b']), image_direction))

    hv_real, hv_image = components(g['hv'], True)
    hv = hv_real + hv_image
    cp = sum(components(g['cp']))
    cp_normal = np.einsum('ijq,iq->ij', cp, normal)
    speed, rho, width = s['speed'], s['density'], s['stall_width']
    chord, slope = g['chord'], sample('dCLda')
    strength = s['stall_factor'] / slope
    flight = speed * wind

    def equations(gamma):
        v = flight + np.einsum('ijq,j->iq', hv, gamma)
        vp_vector = v - np.sum(v * span, axis=1)[:, None] * span
        vp = np.linalg.norm(vp_vector, axis=1)
        cl = 2 * gamma / (chord * vp)
        upper, lower = (cl - sample('CLmax')) / width, (sample('CLmin') - cl) / width
        f = width * (np.logaddexp(0, upper) - np.logaddexp(0, lower))
        fp = np.exp(-np.logaddexp(0, -upper)) + np.exp(-np.logaddexp(0, -lower))
        residual = normal @ flight + cp_normal @ gamma - vp * strength * f
        dvp = np.einsum('iq,ijq->ij', vp_vector / vp[:, None], hv)
        jacobian = cp_normal - (strength * (f - fp * cl))[:, None] * dvp
        jacobian -= np.diag(strength * fp * 2 / chord)
        return residual, jacobian, v, vp_vector, vp, cl

    gamma = np.linalg.solve(cp_normal, -(normal @ flight))
    for iteration in range(20):
        residual, jacobian, *_ = equations(gamma)
        if max(abs(residual)) / speed < 1e-12:
            break
        step = np.linalg.solve(jacobian, -residual)
        for backtrack in range(20):
            trial = gamma + step * .5**backtrack
            if max(abs(equations(trial)[0])) < max(abs(residual)):
                gamma = trial
                break
        else:
            raise AssertionError('Diagnostic Newton line search failed')
    residual, jacobian, v, vp_vector, vp, cl = equations(gamma)
    assert max(abs(residual)) / speed < 1e-10
    probe = np.cos(np.arange(len(gamma)))
    numerical = (equations(gamma + 1e-5 * probe)[0] - equations(gamma - 1e-5 * probe)[0]) / 2e-5
    jacobian_error = float(max(abs(numerical - jacobian @ probe)) / max(abs(jacobian @ probe)))
    assert jacobian_error < 1e-7
    tangent = normal @ flight + cp_normal @ gamma
    ds = g['ds']
    vortex = rho * gamma[:, None] * np.cross(v, span) * ds[:, None]
    friction = .5 * rho * np.linalg.norm(v, axis=1)[:, None] * v * (chord * sample('Cdf') * ds)[:, None]
    stall_drag = 2 * rho * vp_vector / vp[:, None] * (tangent**2 * chord * ds)[:, None]
    force = vortex + friction + stall_drag
    qS = .5 * rho * speed**2 * model.reference[0, 0]
    total = np.array([math.fsum(force[:, i]) for i in range(3)])
    values = dict(CL=float(total @ lift / qS), CD=float(total @ wind / qS))
    # Use only a common parallel wake trace; no fabricated CDi for tilted images.
    values['CDi'] = None
    if max(abs(image_direction - direction)) < 1e-12:
        wake = np.zeros_like(g['hv'])
        for endpoints, sign in ((g['b'], 1), (g['a'], -1), (reflect(g['b']), -1), (reflect(g['a']), 1)):
            r = g['hv'][:, None, :] - endpoints[None, :, :]
            r -= (r @ direction)[..., None] * direction
            wake += sign * np.einsum('ijq,j->iq', np.cross(direction, r) / np.sum(r*r, axis=2)[..., None], gamma) / (2*math.pi)
        values['CDi'] = float(-.5 * rho * math.fsum(gamma * np.sum(wake * np.cross(direction, g['b']-g['a']), axis=1)) / qS)
    # Ground points span a two-dimensional patch; inspect induced flow alone.
    along = np.array([math.cos(pitch), 0., math.sin(pitch)])
    board = np.array([x * along + [0., y, 0.] - height * ground_normal
                      for x in (-.5, 0., .5) for y in (-.5, 0., .5)])
    board_velocity = np.einsum('ijq,j->iq', sum(components(board)), gamma)
    boundary_normal = float(max(abs(board_velocity @ ground_normal)))
    if variant['reflect_wake']:
        assert boundary_normal < 1e-10
    replay_error = None
    if index == 0:
        baseline = io.read(BASE / 'No_Flap-h05-a8/result.json')['verification_payload']
        replay_error = float(max(abs(gamma - [row['circulation'] for row in baseline['strips']])))
        assert replay_error < 2e-10
        for key in ('CL', 'CD', 'CDi'):
            assert abs(values[key] - baseline[key]) < 2e-12
    errors = {key: None if value is None else 100 * (value / job['reference_row']['fields'][key]['value'] - 1)
              for key, value in values.items()}
    result = dict(observed_utc=io.utc(), variant=variant, values=values, errors_percent=errors,
        diagnostic_equilibrium_calls=1, production_calls=0, primary_passes_added=0,
        equation_residual=float(max(abs(residual)) / speed), jacobian_error=jacobian_error,
        baseline_gamma_replay_error=replay_error,
        induced_ground_normal_speed=boundary_normal, freestream_ground_normal_speed=float(flight @ ground_normal),
        minimum_stall_margin_widths=float(min(np.minimum(sample('CLmax')-cl, cl-sample('CLmin'))/width)),
        drag_parts={key:float(math.fsum(value @ wind)/qS) for key,value in
                    [('circulation',vortex),('friction',friction),('stall',stall_drag)]},
        seconds=time.monotonic()-start_time, peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        plan_sha256=io.sha(out / 'plan.json'), driver_sha256=io.sha(Path(__file__)))
    directory.mkdir()
    np.savez(directory / 'state.npz', gamma=gamma, velocity=v, force=force, a=g['a'], b=g['b'], hv=g['hv'], cp=g['cp'])
    result['state_sha256'] = io.sha(directory / 'state.npz')
    io.write(directory / 'result.json', result)
    io.signal.alarm(0)
    print(result)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'run'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--index', type=int)
    args = parser.parse_args()
    if args.action == 'prepare':
        prepare(args.output.resolve())
    else:
        run(args.output.resolve(), args.index)
