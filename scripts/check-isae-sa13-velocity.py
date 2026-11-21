"""Independently integrate the declared SA-13 body source field.

This checks numerical implementation of the regularized source law, not its
physical accuracy or the fidelity of the outline reconstruction.
"""
from pathlib import Path
import hashlib
import json
import numpy as np
from scipy.integrate import quad_vec
from scipy.interpolate import CubicSpline

ROOT = Path(__file__).resolve().parents[1]
D = ROOT / 'docs/validation'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    native = json.loads((D / 'isae-sa13.json').read_text())
    sources = json.loads((D / 'isae-sa13-sources.json').read_text())
    provenance = native['provenance']
    assert provenance['modules'] == {p.name: sha(p) for p in (ROOT / 'openswing').glob('*.py')}
    assert provenance['source_report_sha256'] == sha(D / 'isae-sa13-sources.json')
    case = next(c for c in sources['cases'] if c['name'] == 'pressure')
    table = np.array(case['outline']['normalized_table'])
    radius = CubicSpline(table[:, 0], table[:, 1], bc_type='natural')
    rows = []
    for row in native['rows']:
        q = row['specification']
        if q['case'] != 'pressure':
            continue
        assert row['status'] == 'computed' and sha(ROOT / row['cache_path']) == row['cache_sha256']
        assert q['alpha'] == 0. and q['length'] == 1.
        result = row['result']
        stations = np.array([p['t'] for p in result['measured_points'] if p['status'] == 'computed'])
        assert len(stations) == 22
        targets = np.c_[stations, np.zeros(len(stations)), radius(stations) * (1 + q['surface_offset'])]

        def integrand(s):
            r = float(radius(s))
            sigma = 2 * np.pi * r * float(radius(s, 1))
            delta = targets - np.array([s, 0., 0.])
            # Independent expression; no production VolumeField, quadrature,
            # source_doublet, mesh, or induction helper is called here.
            den = np.sum(delta * delta, axis=1) + (r / 2) ** 2
            return 10. * sigma * delta / den[:, None] ** 1.5 / (4 * np.pi)

        induced, error, info = quad_vec(integrand, 0., 1., points=radius.x[1:-1],
                                       epsabs=1e-10, epsrel=1e-11, limit=5000, full_output=True)
        assert info.success and error < 1e-8
        velocity = induced + np.array([10., 0., 0.])
        cp = 100. * (1. - np.sum(velocity * velocity, axis=1) / 100.)
        checks = []
        for t, target, v, c in zip(stations, targets, velocity, cp):
            sample, = [p for p in result['pressure_profile'] if p['t'] == t]
            assert np.array_equal(target, sample['position'])
            checks.append(dict(t=float(t), position=target.tolist(), independent_velocity=v.tolist(),
                               native_velocity=sample['velocity'], independent_Cp_percent=float(c),
                               native_Cp_percent=sample['Cp_percent'],
                               maximum_velocity_difference=float(np.max(abs(v - sample['velocity']))),
                               Cp_percent_difference=float(abs(c - sample['Cp_percent']))))
        rows.append(dict(specification=q, cache_sha256=row['cache_sha256'], checks=checks,
                         adaptive_error_bound=float(error), evaluations=info.neval,
                         maximum_velocity_difference=max(p['maximum_velocity_difference'] for p in checks),
                         maximum_Cp_percent_difference=max(p['Cp_percent_difference'] for p in checks)))
        print(q, rows[-1]['maximum_velocity_difference'], rows[-1]['maximum_Cp_percent_difference'], flush=True)
    assert len(rows) == 6
    out = dict(status='INDEPENDENT_QUADRATURE_COMPLETE', rows=rows,
               native_sha256=sha(D / 'isae-sa13.json'), source_sha256=sha(D / 'isae-sa13-sources.json'),
               script_sha256=sha(Path(__file__)), modules=provenance['modules'],
               method='Adaptive Gauss-Kronrod integration split at every declared radius-spline knot; axial source density 2*pi*R*dR/dx, source core R/2, speed10, zero PG.',
               limitations=['The same explicitly reconstructed radius table and natural cubic interpolation are used.',
                            'This independently evaluates the implemented regularized source law; it does not establish surface impermeability or experimental accuracy.',
                            'All quadrature errors are retained by mesh and surface offset. No measurement or source-core parameter was fitted.'])
    (D / 'isae-sa13-velocity.json').write_text(json.dumps(out, indent=2) + '\n')


if __name__ == '__main__':
    main()
