"""Integrate saved finite-chord body-edge forces at fixed circulation.

One foreground invocation evaluates one Gauss-Legendre order on one saved
state. Geometry, Gamma, PG and wake remain unchanged. This tests the reference
line-force model, not native ASWING, and does not assert a finite sharp-corner
force integral. No core, geometric cutoff or neighboring-edge omission.
"""
from datetime import datetime, timezone
import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import shutil
import sys
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def portable(value):
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, dict):
        return {k: portable(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [portable(v) for v in value]
    return value


def write(path, value):
    path.write_text(json.dumps(portable(value), indent=2, allow_nan=False) + '\n')


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--chord-rows', type=int, default=2)
    parser.add_argument('--order', type=int, choices=(1, 2, 4, 8, 16, 32), required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Use a fresh output directory.')
    prior = json.loads((args.baseline / 'plan.json').read_text())
    verified = json.loads((args.baseline / 'verification.json').read_text())
    for name, expected in verified['artifacts'].items():
        assert sha(args.baseline / name) == expected, name
    for name, expected in prior['unchanged_pins'].items():
        assert sha(ROOT / name) == expected, name
    selected = next(r for r in json.loads((args.baseline / 'results.json').read_text())
                    if r['chord_rows'] == args.chord_rows)
    source = args.baseline / selected['artifact']['path']
    assert sha(source) == selected['artifact']['sha256']
    with np.load(source) as saved:
        data = {k: saved[k] for k in saved.files}
    assert len(data['gamma']) <= 600, 'This diagnostic is limited to the coarse saved grids.'
    assert np.array_equal(data['edge_coefficients'], data['body_edge_coefficients'])
    helper = load_module('saved_wake_direction', args.baseline / 'driver-used.py')
    vlm = load_module('saved_independent_vortex', args.baseline / 'reference/vlm.py')
    graph = {k: data[k] for k in ('starts', 'ends', 'edge_coefficients',
                                  'ray_starts', 'ray_coefficients')}
    strengths = data['body_edge_coefficients'] @ data['gamma']
    np.testing.assert_array_equal(strengths, data['edge_strengths'])
    # A zero-strength edge carries no load and need not be a force probe.
    edges = np.flatnonzero(data['body_mask'] & (strengths != 0.))
    assert len(edges) ** 2 * args.order <= 40_000_000
    nodes, weights = np.polynomial.legendre.leggauss(args.order)
    fraction, weights = (nodes + 1.) / 2., weights / 2.
    assert np.all((fraction > 0) & (fraction < 1))
    assert abs(math.fsum(weights) - 1) < 2e-15
    a, b = data['starts'][edges], data['ends'][edges]
    delta = b - a
    points = a[:, None, :] + fraction[None, :, None] * delta[:, None, :]
    if args.order == 1:
        points[:, 0] = data['edge_midpoints'][edges]
    own = np.repeat(edges, args.order)
    physics = prior['physics']
    scale = physics['density'] * physics['speed'] ** 2
    qs = .5 * scale * physics['reference_area']
    origin = np.asarray(physics['moment_origin'])
    args.output.mkdir(parents=True)
    shutil.copyfile(__file__, args.output / 'driver-used.py')
    plan = dict(observed_utc=datetime.now(timezone.utc).isoformat(),
                previous_turn='progress: expanded primary-source winglet literature and implementation leads',
                baseline=str(args.baseline), baseline_artifact=source.name,
                source_sha256=sha(source), baseline_plan_sha256=sha(args.baseline / 'plan.json'),
                helper_sha256=sha(args.baseline / 'driver-used.py'),
                kernel_sha256=sha(args.baseline / 'reference/vlm.py'),
                driver_sha256=sha(Path(__file__)), unchanged_pins=prior['unchanged_pins'],
                example=prior['example'], span=prior['span'], chord_rows=args.chord_rows,
                order=args.order, body_edges=len(edges), quadrature_points=len(own),
                physics=physics,
                changed_quantity='Force quadrature along fixed straight body edges only.',
                rule='Interior Gauss-Legendre nodes per full edge; moments integrated at each node.',
                self_field='Only the exact own straight edge is omitted. All other finite/ray sources retained.',
                caveat='No claim of convergence or finite integral at sharp endpoints; this is not an ASWING force rule.',
                new_circulation_solves=0)
    write(args.output / 'plan.json', plan)
    start = time.monotonic()
    try:
        flat = points.reshape(-1, 3)
        velocity = helper.field(flat, graph, data['gamma'], data['pg'],
                                data['wake_direction'], vlm, own) + data['ambient']
        velocity = velocity.reshape(points.shape)
        # Integrate rho Gamma V cross dr. Gamma and V in the source are for U=1.
        force_density = scale * strengths[edges, None, None] * np.cross(velocity, delta[:, None, :])
        moments_density = np.cross(points - origin, force_density)
        forces = np.einsum('eqk,q->ek', force_density, weights)
        moments = np.einsum('eqk,q->ek', moments_density, weights)
        total = np.array([math.fsum(forces[:, k]) for k in range(3)])
        moment = np.array([math.fsum(moments[:, k]) for k in range(3)])
        # A uniform field has known force and moment on any straight edge.
        uniform = scale * strengths[edges, None] * np.cross(data['ambient'], delta)
        exact_uniform_moment = np.cross((a + b) / 2. - origin, uniform)
        integrated_uniform_moment = np.einsum('eqk,q->ek',
            np.cross(points - origin, uniform[:, None, :]), weights)
        np.testing.assert_allclose(integrated_uniform_moment, exact_uniform_moment, atol=2e-11, rtol=1e-12)
        midpoint_delta = None
        if args.order == 1:
            np.testing.assert_allclose(velocity[:, 0], data['edge_velocity'][edges], atol=2e-10, rtol=3e-11)
            np.testing.assert_allclose(forces, data['edge_forces'][edges], atol=2e-9, rtol=3e-11)
            np.testing.assert_allclose(moments, data['edge_moments'][edges], atol=4e-8, rtol=3e-11)
            midpoint_delta = float(np.max(abs(forces - data['edge_forces'][edges])))
        speed = np.linalg.norm(velocity, axis=2)
        peak = np.unravel_index(np.argmax(speed), speed.shape)
        lift = np.array([-data['ambient'][2], 0., data['ambient'][0]])
        worst = np.argsort(np.linalg.norm(forces - data['edge_forces'][edges], axis=1))[-12:][::-1]
        output = args.output / 'quadrature.npz'
        np.savez_compressed(output, edges=edges, fractions=fraction, weights=weights,
            points=points, velocity=velocity, forces=forces, moments=moments,
            force_density=force_density, moment_density=moments_density,
            source_gamma=data['gamma'], body_strengths=strengths[edges])
        result = dict(observed_utc=datetime.now(timezone.utc).isoformat(),
            example=prior['example'], span=prior['span'], chord_rows=args.chord_rows, order=args.order,
            status='evaluated_not_validated', seconds=time.monotonic() - start,
            CL=float(total @ lift / qs), CD=float(total @ data['ambient'] / qs),
            CY=float(total[1] / qs), Cm=float(moment[1] / (qs * physics['reference_chord'])),
            force=total, moment=moment,
            sum_edge_force_norms=float(np.sum(np.linalg.norm(forces, axis=1))),
            peak_speed_ratio=float(speed[peak]), peak_edge=int(edges[peak[0]]),
            peak_fraction=float(fraction[peak[1]]), peak_point=points[peak],
            nearest_fraction_to_endpoint=float(fraction[0]),
            uniform_moment_check=float(np.max(abs(integrated_uniform_moment - exact_uniform_moment))),
            midpoint_force_reproduction_difference=midpoint_delta,
            largest_edge_force_changes=[dict(edge=int(edges[i]), start=a[i], end=b[i],
                gamma=float(strengths[edges[i]]), force=forces[i], midpoint_force=data['edge_forces'][edges[i]],
                difference=forces[i] - data['edge_forces'][edges[i]]) for i in worst],
            artifact=dict(path=output.name, sha256=sha(output)))
        write(args.output / 'result.json', result)
        assert sha(source) == plan['source_sha256']
        for name, expected in plan['unchanged_pins'].items():
            assert sha(ROOT / name) == expected, name
        assert not any(n == 'openswing' or n.startswith('openswing.') for n in sys.modules)
        write(args.output / 'verification.json', dict(observed_utc=datetime.now(timezone.utc).isoformat(),
            unchanged_source_and_status=True, new_solves=0,
            artifacts={p.name: sha(p) for p in args.output.iterdir() if p.is_file()}))
        print(json.dumps({k: result[k] for k in ('example', 'order', 'CL', 'CD', 'Cm',
                         'peak_speed_ratio', 'sum_edge_force_norms', 'seconds')}), flush=True)
    except Exception as error:
        write(args.output / 'failure.json', dict(observed_utc=datetime.now(timezone.utc).isoformat(),
            type=type(error).__name__, message=str(error), elapsed=time.monotonic() - start))
        raise


if __name__ == '__main__':
    main()
