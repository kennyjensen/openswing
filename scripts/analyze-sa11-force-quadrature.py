"""Audit fixed-Gamma quadrature and derive its endpoint singular coefficients.

No circulation solve, model modification, fitted core or production import.
The singular coefficient is calculated from incident source geometry and
circulation, independently of the observed force changes.
"""
from datetime import datetime, timezone
import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import shutil

import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def portable(x):
    if isinstance(x, np.ndarray):
        return x.tolist()
    if isinstance(x, np.generic):
        return x.item()
    if isinstance(x, dict):
        return {k: portable(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [portable(v) for v in x]
    return x


def vector_sum(vectors):
    vectors = np.asarray(vectors).reshape(-1, 3)
    return np.array([math.fsum(vectors[:, k]) for k in range(3)])


def ray_residue(inside, source, strength, pg):
    """lim(s→0+) s V at node+s*inside, s measured in physical length.

    An incident finite segment has the same leading term as its outward ray.
    Vector cross products are taken in PG space and velocity mapped back.
    The positive-dot branch rationalizes |p|-u.p to avoid cancellation.
    """
    p, direction = inside @ pg, source @ pg
    cr = np.cross(direction, p)
    if np.all(cr == 0):
        if p @ direction > 0 and strength != 0:
            raise ValueError('Overlapping outgoing incident filaments are outside this audit.')
        return np.zeros(3)
    length = np.linalg.norm(direction)
    cr = cr / length
    dot = p @ direction / length
    norm = np.linalg.norm(p)
    multiplier = ((1 + dot / norm) / (cr @ cr) if dot > 0
                  else 1 / (norm * (norm - dot)))
    return (strength / (4 * np.pi) * cr * multiplier) @ pg


def endpoint_coefficients(data, physics):
    finite, wakes = {}, {}
    strengths = data['edge_strengths']
    ray_strengths = data['ray_coefficients'] @ data['gamma']
    for i, (a, b, g) in enumerate(zip(data['starts'], data['ends'], strengths)):
        finite.setdefault(tuple(a), []).append((i, b - a, g))
        finite.setdefault(tuple(b), []).append((i, a - b, -g))
    for i, (p, g) in enumerate(zip(data['ray_starts'], ray_strengths)):
        wakes.setdefault(tuple(p), []).append((i, data['wake_direction'], g))
    # K[e,end,kind] is the force coefficient multiplying ds/s at each endpoint.
    coefficients = np.zeros((len(strengths), 2, 2, 3))
    velocity_residues = np.zeros_like(coefficients)
    incident = {}
    scale = physics['density'] * physics['speed'] ** 2
    for edge, (a, b, g) in enumerate(zip(data['starts'], data['ends'], strengths)):
        tangent = (b - a) / np.linalg.norm(b - a)
        for end, (p, inward) in enumerate(((a, tangent), (b, -tangent))):
            for kind, mapping in enumerate((finite, wakes)):
                sources = [(i, v, gamma) for i, v, gamma in mapping.get(tuple(p), [])
                           if not (kind == 0 and i == edge) and gamma != 0.]
                residue = vector_sum([ray_residue(inward, v, gamma, data['pg'])
                                      for i, v, gamma in sources])
                velocity_residues[edge, end, kind] = residue
                coefficients[edge, end, kind] = scale * g * np.cross(residue, tangent)
                incident[(edge, end, kind)] = [i for i, v, gamma in sources]
    return coefficients, velocity_residues, incident


def coplanar_wake_crossings(data):
    """Exact coplanar subset: x-directed edges crossed by a downstream ray.

    Equal y coordinates and zero direction components are exact comparisons;
    no distance tolerance selects a crossing. Other 3D encounters are not
    classified here. The returned double-precision coordinate is a numerical
    representation of the intersection of those coplanar straight lines.
    """
    wake = data['wake_direction']
    assert wake[1] == 0. and wake[2] != 0.
    strength = data['ray_coefficients'] @ data['gamma']
    crossings = []
    for edge, (a, b, gamma) in enumerate(zip(data['starts'], data['ends'], data['edge_strengths'])):
        if not data['body_mask'][edge] or gamma == 0. or a[1] != b[1] or a[2] != b[2]:
            continue
        for ray in np.flatnonzero((data['ray_starts'][:, 1] == a[1]) & (strength != 0.)):
            origin = data['ray_starts'][ray]
            distance = (a[2] - origin[2]) / wake[2]
            if distance <= 0.:
                continue
            x = origin[0] + distance * wake[0]
            fraction = (x - a[0]) / (b[0] - a[0])
            if 0. < fraction < 1.:
                crossings.append(dict(edge=edge, ray=int(ray), body_start=a, body_end=b,
                    ray_origin=origin, intersection=np.array([x, a[1], a[2]]),
                    body_fraction=float(fraction), ray_distance=float(distance),
                    body_gamma=float(gamma), ray_gamma=float(strength[ray])))
    return crossings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Use a fresh output directory.')
    orders = (1, 2, 4, 8, 16, 32)
    audits, all_records = [], []
    sources = {}
    for case in ('up48', 'both48'):
        base = ROOT / ('artifacts/isae/sa11-wake-direction-20261107-' + case)
        plan = json.loads((base / 'plan.json').read_text())
        verification = json.loads((base / 'verification.json').read_text())
        assert all(sha(base / p) == h for p, h in verification['artifacts'].items())
        assert all(sha(ROOT / p) == h for p, h in plan['unchanged_pins'].items())
        with np.load(base / 'c2.npz') as z:
            d = {k: z[k] for k in z.files}
        coeff, residues, incident = endpoint_coefficients(d, plan['physics'])
        active = d['body_mask'] & (d['edge_strengths'] != 0.)
        total_coeff = vector_sum(coeff[active].reshape(-1, 3))
        by_kind = {kind: vector_sum(coeff[active, :, k].reshape(-1, 3))
                   for k, kind in enumerate(('finite', 'wake'))}
        qs = .5 * plan['physics']['density'] * plan['physics']['speed'] ** 2 * plan['physics']['reference_area']
        lift = np.array([-d['ambient'][2], 0., d['ambient'][0]])
        root_edges = (306, 415) if case == 'up48' else (498, 607)
        records, saved = [], {}
        for q in orders:
            folder = ROOT / f'artifacts/isae/sa11-force-quadrature-20261107-{case}-q{q}'
            verify = json.loads((folder / 'verification.json').read_text())
            assert all(sha(folder / p) == h for p, h in verify['artifacts'].items())
            jobplan = json.loads((folder / 'plan.json').read_text())
            assert jobplan['source_sha256'] == sha(base / 'c2.npz')
            row = json.loads((folder / 'result.json').read_text())
            with np.load(folder / 'quadrature.npz') as z:
                saved[q] = {k: z[k] for k in z.files}
            arrays = saved[q]
            np.testing.assert_array_equal(arrays['source_gamma'], d['gamma'])
            harmonic = math.fsum(1. / k for k in range(1, q + 1))
            # Independent exact quadrature identity for the singular 1/u term.
            weight_check = math.fsum(arrays['weights'] / arrays['fractions'])
            assert abs(weight_check - 2 * harmonic) < 2e-11
            force = vector_sum(arrays['forces'])
            moment = vector_sum(arrays['moments'])
            np.testing.assert_allclose(force, row['force'], atol=2e-10, rtol=2e-12)
            np.testing.assert_allclose(moment, row['moment'], atol=2e-9, rtol=2e-12)
            sources[str(folder.relative_to(ROOT))] = sha(folder / 'verification.json')
            records.append(dict(**row, twice_harmonic=2 * harmonic,
                singular_quadrature_identity_error=abs(weight_check - 2 * harmonic)))
        root_checks = []
        spec = importlib.util.spec_from_file_location('independent_vlm', base / 'reference/vlm.py')
        vlm = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(vlm)
        for edge in root_edges:
            i16 = int(np.flatnonzero(saved[16]['edges'] == edge)[0])
            i32 = int(np.flatnonzero(saved[32]['edges'] == edge)[0])
            end_coeff = coeff[edge].sum(axis=1)
            edge_coeff = end_coeff.sum(axis=0)
            dh = 2 * math.fsum(1. / k for k in range(17, 33))
            observed = saved[32]['forces'][i32] - saved[16]['forces'][i16]
            predicted = dh * edge_coeff
            error = float(np.max(abs(observed - predicted)))
            assert error < 2e-6, (case, edge, error)
            p = saved[32]['points'][i32]
            pg = d['pg']
            ray_ids = sorted(set(incident[(edge, 0, 1)] + incident[(edge, 1, 1)]))
            rs = d['ray_coefficients'] @ d['gamma']
            direct = np.einsum('qrk,r->qk', vlm.semi_infinite(p[:, None, :] @ pg,
                d['ray_starts'][ray_ids][None, :, :] @ pg, d['wake_direction'] @ pg), rs[ray_ids]) @ pg
            length = np.linalg.norm(d['ends'][edge] - d['starts'][edge])
            fraction = saved[32]['fractions']
            analytic = (residues[edge, 0, 1] / (length * fraction[:, None]) +
                        residues[edge, 1, 1] / (length * (1 - fraction[:, None])))
            np.testing.assert_allclose(direct, analytic, atol=2e-7, rtol=2e-10)
            root_checks.append(dict(edge=edge, start=d['starts'][edge], end=d['ends'][edge],
                force_log_coefficient=edge_coeff, finite_endpoint_coefficients=coeff[edge, :, 0],
                wake_endpoint_coefficients=coeff[edge, :, 1], incident_ray_ids=ray_ids,
                predicted_Q16_to_Q32_force_change=predicted, observed_Q16_to_Q32_force_change=observed,
                maximum_change_error_N=error, ray_field_maximum_error_unit_speed=float(np.max(abs(direct - analytic)))))
        prediction = dh * total_coeff
        actual = np.asarray(records[-1]['force']) - records[-2]['force']
        audits.append(dict(case=case, total_endpoint_force_coefficient=total_coeff,
            endpoint_coefficient_by_source_kind=by_kind,
            CL_coefficient=float(total_coeff @ lift / qs), CD_coefficient=float(total_coeff @ d['ambient'] / qs),
            predicted_total_Q16_to_Q32_force_change=prediction,
            observed_total_Q16_to_Q32_force_change=actual,
            remaining_force_change_after_endpoint_prediction=actual - prediction,
            coplanar_interior_wake_crossings=coplanar_wake_crossings(d),
            root_checks=root_checks, source_sha256=sha(base / 'c2.npz'), records=records))
        all_records.extend(records)
    args.output.mkdir(parents=True)
    shutil.copyfile(__file__, args.output / 'analysis-driver-used.py')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(2, 2, figsize=(10.5, 7), constrained_layout=True)
    for audit, color, label in zip(audits, ('#0072B2', '#D55E00'), ('Upper', 'Upper/lower')):
        rows = audit['records']
        x = [r['order'] for r in rows]
        anchor = next(r for r in rows if r['order'] == 16)
        for ax, name in ((axes[0, 0], 'CL'), (axes[0, 1], 'CD')):
            ax.plot(x, [r[name] for r in rows], 'o-', color=color, label=label)
            prediction = [anchor[name] + (r['twice_harmonic'] - anchor['twice_harmonic']) * audit[name + '_coefficient'] for r in rows]
            ax.plot(x, prediction, ':', color=color, label=label + ' endpoint term, anchored at Q16')
            ax.set_ylabel(name)
        axes[1, 0].plot(x, [r['peak_speed_ratio'] for r in rows], 'o-', color=color, label=label)
        axes[1, 1].plot(x, [r['sum_edge_force_norms'] for r in rows], 'o-', color=color, label=label)
    axes[1, 0].set_yscale('log')
    axes[1, 0].set_ylabel('Sampled peak velocity / freestream')
    axes[1, 1].set_ylabel('Sum of edge-force magnitudes (N)')
    for ax in axes.flat:
        ax.set_xscale('log', base=2)
        ax.set_xticks(orders, [str(q) for q in orders])
        ax.set_xlabel('Gauss points per edge (Q)')
        ax.grid(alpha=.25)
    axes[0, 0].legend(fontsize=6)
    fig.suptitle('SA-11 independent finite-chord force integration\nFixed Gamma, N48, two chord rows; endpoint terms are analytic, not fitted')
    for suffix in ('png', 'svg'):
        fig.savefig(args.output / ('force-quadrature.' + suffix), dpi=160)
    plt.close(fig)
    result = dict(observed_utc=datetime.now(timezone.utc).isoformat(),
        numerical_field_evaluations=len(all_records), circulation_solves=0,
        field_seconds=sum(r['seconds'] for r in all_records), source_verification_pins=sources,
        audits=audits, caution='Nonzero endpoint log terms diagnose this independent line-force closure. No subtraction is adopted as a force correction.',
        artifacts={p.name: sha(p) for p in args.output.iterdir() if p.is_file()})
    (args.output / 'analysis.json').write_text(json.dumps(portable(result), indent=2, allow_nan=False) + '\n')
    print(json.dumps(portable([{k: a[k] for k in ('case', 'total_endpoint_force_coefficient',
        'endpoint_coefficient_by_source_kind', 'predicted_total_Q16_to_Q32_force_change',
        'observed_total_Q16_to_Q32_force_change', 'remaining_force_change_after_endpoint_prediction',
        'coplanar_interior_wake_crossings', 'root_checks')}
        for a in audits]), indent=2), flush=True)


if __name__ == '__main__':
    main()
