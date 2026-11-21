"""One bounded production-kernel replay of SA-13's identified nodal load law.

Use explicit piecewise-linear radii and stored stations, without fitting loads.
This is a force-density diagnostic, not an original ASWING model/full solve.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import resource
import signal
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case', choices=['r33', 'r101', 'rs1'], required=True)
    parser.add_argument('--analysis', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
        assert os.environ.get(name) == '1', name
    resource.setrlimit(resource.RLIMIT_AS, (512*1024**2, 512*1024**2))
    resource.setrlimit(resource.RLIMIT_CPU, (15, 15))
    signal.alarm(25)
    started = time.perf_counter()
    import numpy as np
    from openswing.asw import parse_asw
    from openswing.geometry import mesh_beam
    from openswing.inertia import Motion
    from openswing.volume import body_loads, body_quadrature
    analysis = json.loads(args.analysis.read_text())
    for name, expected in analysis['sources'].items():
        assert sha(ROOT/name) == expected, name
    source = json.loads((ROOT/'docs/validation/isae-sa13-sources.json').read_text())
    case = next(c for c in source['cases'] if c['name'] == args.case)
    identified = next(c for c in analysis['rows'] if c['case'] == args.case)
    upper, lower = case['series'][3]['xy'], case['series'][4]['xy']
    xy = [[a[0], (a[1]-b[1])/2] for a, b in zip(upper, lower) if None not in a+b]
    # R33 has a negative signed terminal outline radius. Stop before it;
    # neither clip it nor include its interval in this physical-kernel check.
    positive = [r for r in xy if r[1] >= 0]
    assert positive == xy[:len(positive)]
    x, radius = np.asarray(positive).T
    diameter = identified['diameter_in_figure_units']
    # Repeated, equal-valued knots specify separate two-point linear pieces
    # with continuous radius and explicit slope breaks in the existing parser.
    table = '\n'.join(f'{xx:.17g} {rr:.17g}' for i in range(len(x)-1)
                      for xx, rr in ((x[i], radius[i]), (x[i+1], radius[i+1])))
    text = f'''! SA-13 pointwise Eq.68 diagnostic; not the original ASWING input.
! Stored stations and positive radii only; no fitted values or cap closure.
Name
SA13 {args.case} linear radius segments
End
Unit
L 1 m
T 1 s
F 1 N
End
Constant
9.80665 1 340.21
End
Reference
{diameter*(x[-1]-x[0]):.17g} {x[-1]-x[0]:.17g} {diameter:.17g}
0 0 0
End
Beam 1
Open body segments for local force density
t x
{x[0]:.17g} {x[0]:.17g}
{x[-1]:.17g} {x[-1]:.17g}
t radius
{table}
End
'''
    model = parse_asw(text); beam = model.beams[0]
    mesh = mesh_beam(beam, {'default': 4, 'beams': {'1': {'nodes': x.tolist()}}})
    np.testing.assert_array_equal(mesh.t0, x[:-1])
    np.testing.assert_array_equal(mesh.t1, x[1:])
    t, points, _, weights = body_quadrature(mesh)
    alpha = np.deg2rad(identified['alpha_deg'])
    v = np.array([np.cos(alpha), 0., np.sin(alpha)])
    load = body_loads(mesh, 1., np.broadcast_to(v, points.shape), Motion(), np.zeros(3))
    density = load['force_samples'][:, :, 2]/weights/(.5*diameter)
    u = (t-mesh.t0[:, None])/(mesh.t1-mesh.t0)[:, None]
    # Independent affine recovery at the LEFT station from computed Gauss
    # force samples. No archived load appears in this calculation.
    slope = (density[:, 1]-density[:, 0])/(u[:, 1]-u[:, 0])
    node = density[:, 0]-u[:, 0]*slope
    np.testing.assert_allclose(density, node[:, None]+u*slope[:, None], rtol=0, atol=2e-12)
    average = load['lift'][:, 2]/mesh.length/(.5*diameter)
    endpoint_average = np.sin(2*alpha)*np.pi*np.diff(radius**2)/np.diff(x)/diameter
    np.testing.assert_allclose(average, endpoint_average, rtol=0, atol=2e-12)
    rows = []
    for i, (nodal, mean) in enumerate(zip(node, average)):
        target = identified['rows'][i]
        assert target['status'] == 'adjacent_station_rule' and not target['negative_radius_interval']
        assert abs(nodal-target['archived']) < 2e-12
        assert abs((mean-nodal)-target['expected_average_minus_node']) < 2e-12
        rows.append(dict(source_row_1based=i+1, x=float(x[i]), archived=target['archived'],
                         nodal_from_kernel=float(nodal), interval_average=float(mean),
                         nodal_error=float(abs(nodal-target['archived'])),
                         average_minus_archived=float(mean-target['archived'])))
    modules = {p.name: sha(p) for p in (ROOT/'openswing').glob('*.py')}
    previous = json.loads((ROOT/'artifacts/isae/sa13-quadrature-20261109/checks-v2.json').read_text())
    assert modules == previous['modules']
    model_path = args.output.with_suffix('.asw')
    with model_path.open('x') as handle:
        handle.write(text)
    result = dict(observed_utc=datetime.now(timezone.utc).isoformat(), case=args.case,
                  status='MATCHING_POINTWISE_KERNEL_DIAGNOSTIC_NOT_NATIVE_CASE_PASS',
                  rows=rows, intervals=len(rows), quadrature_points=int(t.size),
                  max_nodal_error=max(r['nodal_error'] for r in rows),
                  max_average_difference=max(abs(r['average_minus_archived']) for r in rows),
                  retained_unreplayed_rows=identified['retained']-len(rows),
                  finite_unreplayed_rows=identified['finite']-len(rows),
                  model_path=str(model_path), model_sha256=sha(model_path),
                  analysis_sha256=sha(args.analysis), script_sha256=sha(Path(__file__)), modules=modules,
                  seconds=time.perf_counter()-started, peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                  limits=dict(address_space_mib=512, cpu_seconds=15, wall_seconds=25, blas_threads=1),
                  full_physical_solves=0, native_passes_added=0,
                  qualifications=['Explicit piecewise-linear segment reconstruction; no original model or global operating state recovered.',
                                  'No end-cap/shoulder force or induced-field calculation is included in this local uniform-flow kernel check.',
                                  'Unreplayed original zeros, negative-radius interval and missing rows remain in the native scope.'])
    with args.output.open('x') as handle:
        json.dump(result, handle, indent=2); handle.write('\n')
    print(json.dumps({k:result[k] for k in ('case', 'intervals', 'max_nodal_error', 'max_average_difference',
                                          'finite_unreplayed_rows', 'seconds', 'peak_rss_kib')}))


if __name__ == '__main__':
    main()
