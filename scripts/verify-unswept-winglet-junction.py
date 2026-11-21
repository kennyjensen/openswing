"""Small serial topology and sharp unswept-winglet diagnostics.

Uses the dimensions and incidence expression in Kleine et al. (2023), Table 1,
as a mechanism control, not a reproduction of their different LL formulation
or an ASWING reference comparison. No production geometry/default is changed.
"""
from dataclasses import asdict, replace
from datetime import datetime, timezone
import argparse
import gc
import hashlib
import json
from pathlib import Path
import shutil
import sys
import time

import numpy as np
from scipy.integrate import quad_vec

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from openswing.aero import FlightCondition, evaluate_aerodynamics
from openswing.asw import parse_asw
from openswing.factored_influence import FactoredInfluence
from openswing.frozen_influence import lifting_geometry
from openswing.geometry import model_meshes, surface_frame


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def utc():
    return datetime.now(timezone.utc).isoformat()


def write(path, data):
    path.write_text(json.dumps(data, indent=2, allow_nan=False) + '\n')


def source(kind):
    # The beam axis IS the bound quarter-chord line (Xax=.25), eliminating
    # chord/sweep-induced endpoint offsets. Circulation goes from left tip
    # down to the main wing and up to the right tip. All physical indices = 1.
    angle = np.rad2deg(1/(2*np.pi))
    header = '''Name
Unswept junction mechanism control
End
Unit
L 1 m
T 1 s
F 1 N
End
Constant
9.80665 1.225 340.294
End
Reference
0.1 0.1 1
0 0 0
End
'''
    if kind == 'straight-whole':
        parts = [(1, [(-.7, -.7, 0.), (.7, .7, 0.)])]
    elif kind == 'straight-split':
        parts = [(1, [(-.7, -.7, 0.), (-.5, -.5, 0.)]),
                 (2, [(-.5, -.5, 0.), (.5, .5, 0.)]),
                 (3, [(.5, .5, 0.), (.7, .7, 0.)])]
    elif kind == 'winglets':
        parts = [(1, [(-.7, -.5, .2), (-.5, -.5, 0.)]),
                 (2, [(-.5, -.5, 0.), (.5, .5, 0.)]),
                 (3, [(.5, .5, 0.), (.7, .5, .2)])]
    else:
        raise ValueError(kind)
    for i, knots in parts:
        header += f'Beam {i} 1\nPart {i}\nt x y z chord Xax twist dCLda Cdf Cdp Cm\n'
        for t, y, z in knots:
            header += f'{t:.17g} 0 {y:.17g} {z:.17g} .1 .25 {angle:.17g} {2*np.pi:.17g} 0 0 0\n'
        header += 'End\n'
    return header


def integral_field(points, a, b, gamma):
    """Independent direct Biot--Savart integration of ungrouped filaments."""
    def segment(t):
        r = points[:, None, :] - a[None] - t*(b-a)[None]
        return np.sum(gamma[None, :, None]*np.cross((b-a)[None], r)/
                      np.linalg.norm(r, axis=-1)[..., None]**3, axis=1)
    direction = np.array([1., 0., 0.])
    def wake(t):
        first = points[:, None, :] - a[None] - t*direction
        second = points[:, None, :] - b[None] - t*direction
        return np.sum(gamma[None, :, None]*(
            np.cross(direction, second)/np.linalg.norm(second, axis=-1)[..., None]**3 -
            np.cross(direction, first)/np.linalg.norm(first, axis=-1)[..., None]**3), axis=1)
    bound, eb = quad_vec(segment, 0., 1., epsabs=1e-12, epsrel=1e-12)
    trailing, ew = quad_vec(wake, 0., np.inf, epsabs=1e-12, epsrel=1e-12)
    assert max(eb, ew) < 2e-10
    return (bound+trailing)/(4*np.pi), (eb+ew)/(4*np.pi)


def fork_checks():
    points = np.array([[.4, .2, .3], [-.2, .7, .1], [1., -.3, -.4]])
    rows = []
    for shift in (0., .05):
        a = np.array([[0., -.5, 0.], [shift, .5, 0.], [0., .5, -.2]])
        b = np.array([[0., .5, 0.], [shift, .5, .2], [0., .5, 0.]])
        for upper in (.625, .5):
            gamma = np.array([1., upper, -.375])
            expected, estimate = integral_field(points, a, b, gamma)
            for reverse in (False, True):
                aa, bb, gg = a.copy(), b.copy(), gamma.copy()
                if reverse:
                    aa[2], bb[2], gg[2] = b[2], a[2], -gamma[2]
                operator = FactoredInfluence(points, aa, bb, [1., 0., 0.], np.eye(3))
                actual = operator.apply(gg)
                np.testing.assert_allclose(actual, expected, atol=2e-12, rtol=2e-11)
                ids, signs = operator.representative_endpoints()
                nodes = np.where(signs[:, None] > 0., bb[ids], aa[ids])
                strengths = operator.wake_strengths(gg)
                root = np.flatnonzero(np.all(nodes == [0., .5, 0.], axis=1))
                assert len(root) == 1
                target = .625 - (upper if shift == 0. else 0.)
                assert strengths[root[0]] == target
                assert sum(strengths) == 0.  # All horseshoes close downstream.
                rows.append(dict(offset=shift, upper_gamma=upper, reversed_lower=reverse,
                    common_root_ray_strength=float(strengths[root[0]]),
                    expected_common_root_ray_strength=target,
                    velocity_max_error=float(np.max(abs(actual-expected))),
                    independent_quadrature_error_bound=float(estimate),
                    grouped_endpoints=nodes.tolist(), wake_strengths=strengths.tolist()))
    return rows


def midpoint_meshes(meshes):
    # Deliberate diagnostic override, NOT the production ASWING midpoint.
    # Our fixture pieces are straight and t is arc length, so arithmetic
    # midpoints give exactly the uniform control-point spacing in the paper.
    result = []
    for mesh in meshes:
        tm = (mesh.t0+mesh.t1)/2
        result.append(replace(mesh, tm=tm, rm=(mesh.r0+mesh.r1)/2,
                              frames=surface_frame(mesh.beam, tm)))
    return result


def ray_report(geometry, gamma):
    # Use a harmless external receiver for incidence construction; all same
    # physical surface, hence zero core. Coordinates are never snapped.
    operator = FactoredInfluence(np.array([[-1., .1, .3]]), geometry['a'],
        geometry['b'], [1., 0., 0.], np.eye(3))
    ids, signs = operator.representative_endpoints()
    nodes = np.where(signs[:, None] > 0, geometry['b'][ids], geometry['a'][ids])
    strengths = operator.wake_strengths(gamma)
    rows = []
    for y in (-.5, .5):
        ids = np.flatnonzero(np.linalg.norm(nodes-[0., y, 0.], axis=1) < 1e-12)
        rows.append(dict(root=[0., y, 0.], distinct_origins=len(ids),
            origins=nodes[ids].tolist(), signed_wake_strengths=strengths[ids].tolist()))
    return rows


def decomposition(meshes, result):
    g = lifting_geometry(meshes, np.array([1., 0., 0.]))
    gamma = np.array([s['circulation'] for s in result['strips']])
    v = np.array([s['relative_velocity'] for s in result['strips']])
    i = int(np.argmax(np.linalg.norm(v, axis=1)))
    own = np.zeros((1, len(gamma)), dtype=bool)
    own[0, i] = True
    op = FactoredInfluence(g['hv'][i:i+1], g['a'], g['b'], [1., 0., 0.],
                          np.eye(3), exclude_bound=own)
    bound = np.einsum('ijk,j->ik', op.bound, gamma)[0]
    wake = np.einsum('ijk,j->ik', op.rays, op.wake_strengths(gamma))[0]
    np.testing.assert_allclose(bound+wake+[1., 0., 0.], v[i], atol=3e-12, rtol=3e-12)
    return dict(peak_index=i, peak_position=g['hv'][i].tolist(), peak_velocity=v[i].tolist(),
        bound_velocity=bound.tolist(), wake_velocity=wake.tolist(),
        maximum_speed=float(np.max(np.linalg.norm(v, axis=1))),
        roots=ray_report(g, gamma))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Use a fresh output directory; previous observations are preserved.')
    args.output.mkdir(parents=True)
    shutil.copyfile(__file__, args.output/'driver-used.py')
    paths = list((ROOT/'openswing').glob('*.py')) + [ROOT/'docs/validation/ISAE_STATUS.md',
        ROOT/'docs/validation/isae-progress-scopes.json']
    pins = {str(p.relative_to(ROOT)): sha(p) for p in paths}
    for kind in ('straight-whole', 'straight-split', 'winglets'):
        (args.output/(kind+'.asw')).write_text(source(kind))
    condition = FlightCondition(speed=1., alpha=0., beta=0., mach=0.,
        freeze_influences=False, stall=False)
    requests = [dict(main_intervals=n, sampling=s) for n in (50, 100, 200)
                for s in ('glauert', 'arithmetic-control')]
    plan = dict(utc=utc(), pins=pins, driver_sha256=sha(Path(__file__)),
        condition=asdict(condition), incidence_degrees=float(np.rad2deg(1/(2*np.pi))),
        requests=requests, reference='https://arxiv.org/abs/2209.00096',
        interpretation='Mechanism control, not a reference score. Dimensions and radian incidence '
            'from Table 1; .02 arithmetic control spacing on first grid. Paper degree value is '
            'inconsistent. Full ASWING tangency differs from the paper nonlinear sectional LL. '
            'All three surfaces have positive local incidence, generating inward winglet lift. '
            'No core on the common physical surface; no sweep, PG or stall. Normal section Mach '
            'is still evaluated with the actual atmospheric sound speed.')
    write(args.output/'plan.json', plan)
    fork = fork_checks()
    write(args.output/'fork-checks.json', fork)
    print('Independent fork field checks:', len(fork), 'max error',
          max(r['velocity_max_error'] for r in fork), flush=True)

    # Same physical intervals AND sample positions, changing logical ownership
    # only. Ordinary independent remeshing would change the Glauert midpoints.
    whole = parse_asw(source('straight-whole'))
    split = parse_asw(source('straight-split'))
    nodes = np.r_[np.linspace(-.7, -.5, 11), np.linspace(-.5, .5, 51)[1:],
                  np.linspace(.5, .7, 11)[1:]].tolist()
    master = model_meshes(whole, dict(default=70, beams={'1':dict(nodes=nodes)}))[0]
    partitioned = []
    for beam, lo, hi in zip(split.beams, (0, 10, 60), (10, 60, 70)):
        fields = {k: (v[lo:hi+1] if k == 'theta' else v[lo:hi])
                  for k, v in vars(master).items() if isinstance(v, np.ndarray)}
        partitioned.append(replace(master, beam=beam, **fields))
    runs = [evaluate_aerodynamics(whole, condition, [master]),
            evaluate_aerodynamics(split, condition, partitioned)]
    full, parts = runs
    differences = {}
    for key in ('CL', 'CD', 'CDi', 'CDi_near', 'Cm', 'force', 'moment'):
        aa, bb = np.asarray(full[key]), np.asarray(parts[key])
        differences[key] = float(np.max(abs(aa-bb)))
        np.testing.assert_allclose(aa, bb, atol=2e-12, rtol=2e-11)
    for key in ('circulation', 'relative_velocity', 'force'):
        aa, bb = [np.asarray([s[key] for s in r['strips']]) for r in runs]
        differences['strip_'+key] = float(np.max(abs(aa-bb)))
        np.testing.assert_allclose(aa, bb, atol=2e-12, rtol=2e-11)
    write(args.output/'partition-check.json', dict(utc=utc(), differences=differences,
        condition=asdict(condition), whole=full, partitioned=parts,
        roots=ray_report(lifting_geometry(partitioned, np.array([1., 0., 0.])),
            np.asarray([s['circulation'] for s in parts['strips']]))))
    print('Same-mesh logical partition:', differences, flush=True)
    del runs, full, parts
    rows = []
    model = parse_asw(source('winglets'))
    for request in requests:
        n = request['main_intervals']
        settings = dict(default=n, beams={str(i):dict(count=n if i == 2 else n//5,
            spacing='uniform') for i in (1, 2, 3)})
        meshes = model_meshes(model, settings)
        if request['sampling'] == 'arithmetic-control':
            meshes = midpoint_meshes(meshes)
        start = time.monotonic()
        result = evaluate_aerodynamics(model, condition, meshes)
        row = dict(request=request, utc=utc(), seconds=time.monotonic()-start,
            condition=asdict(condition), result=result, field=decomposition(meshes, result))
        rows.append(row)
        write(args.output/'results.json', rows)
        print(len(rows), '/6', request, 'CL', result['CL'], 'CD', result['CD'],
              'peak speed', row['field']['maximum_speed'], flush=True)
        gc.collect()
    assert pins == {str(p.relative_to(ROOT)): sha(p) for p in paths}
    assert sha(Path(__file__)) == plan['driver_sha256']
    write(args.output/'verification.json', dict(utc=utc(), source_and_scope_unchanged=True,
        calls=8, independent_fork_checks=len(fork),
        artifacts={p.name:sha(p) for p in args.output.iterdir() if p.is_file()}))


if __name__ == '__main__':
    main()
