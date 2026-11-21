"""One bounded SA-13 linear-radius replay through the browser JSON boundary.

Recover station density from public interval force and moment, without
calling the low-level body kernel or using reference values in the recovery.
This is a documented reconstruction, not a recovered original ASWING input.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import resource
import signal
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
EVIDENCE = ROOT/'artifacts/isae/sa13-discrete-loads-20261109'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case', choices=['r33', 'r101', 'rs1'], required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
        assert os.environ.get(name) == '1', name
    resource.setrlimit(resource.RLIMIT_AS, (512*1024**2, 512*1024**2))
    resource.setrlimit(resource.RLIMIT_CPU, (15, 15))
    signal.alarm(25)
    started = time.perf_counter()
    # The same serialized boundary is used by the browser worker. This call
    # is native Python only; it does not start a browser or load WebAssembly.
    from openswing.bridge import run_worker_json
    analysis = json.loads((EVIDENCE/'analysis.json').read_text())
    for name, expected in analysis['sources'].items():
        assert sha(ROOT/name) == expected, name
    prior = json.loads((EVIDENCE/f'kernel-{args.case}.json').read_text())
    assert prior['analysis_sha256'] == sha(EVIDENCE/'analysis.json')
    model_path = ROOT/prior['model_path']
    assert sha(model_path) == prior['model_sha256']
    source = json.loads((ROOT/'docs/validation/isae-sa13-sources.json').read_text())
    case = next(c for c in source['cases'] if c['name'] == args.case)
    identified = next(c for c in analysis['rows'] if c['case'] == args.case)
    outline = [(a[0], (a[1]-b[1])/2) for a, b in zip(case['series'][3]['xy'], case['series'][4]['xy'])
               if None not in a+b and (a[1]-b[1])/2 >= 0]
    assert len(outline)-1 == prior['intervals']
    nodes = [row[0] for row in outline]
    request = dict(action='solve', mode='rigid', source=model_path.read_text(),
                   panels=dict(default=4, beams={'1':dict(nodes=nodes)}),
                   condition=dict(speed=1., alpha=identified['alpha_deg'], mach=0., freeze_influences=True))
    solve_started = time.perf_counter()
    raw_response = run_worker_json(json.dumps(request, allow_nan=False))
    solve_seconds = time.perf_counter()-solve_started
    envelope = json.loads(raw_response)
    assert 'error' not in envelope, envelope.get('error')
    result = envelope['result']
    assert result['converged'] and result['residual'] <= 1e-8
    assert result['lifting_panels'] == 0 and result['body_shoulders'] == []
    assert result['aerodynamic_influences']['frozen'] is True
    assert len(result['strips']) == len(nodes)-1
    alpha = math.radians(identified['alpha_deg'])
    force_factor = math.sin(alpha)*math.cos(alpha)  # rho=1, U=1
    diameter = identified['diameter_in_figure_units']
    qd = .5*diameter
    records = []
    for i, strip in enumerate(result['strips']):
        (x0, r0), (x1, r1) = outline[i:i+2]
        length = x1-x0
        assert not strip['lifting']
        assert abs(strip['length']-length) < 2e-14
        assert abs(strip['position'][0]-strip['t']) < 2e-14
        assert strip['position'][1:] == [0., 0.]
        fz, my = strip['force'][2], strip['moment'][1]
        # Stored moment is about the Glauert force point, generally not the
        # arithmetic interval midpoint. Translate it before recovering slope.
        midpoint = (x0+x1)/2
        centered_moment = my+(midpoint-strip['position'][0])*fz
        node_density = (fz/length+6*centered_moment/length**2)/qd
        area0, area1 = math.pi*r0*r0, math.pi*r1*r1
        volume = math.pi*length*(r0*r0+r0*r1+r1*r1)/3
        expected_force = force_factor*(area1-area0)
        expected_moment = -force_factor*((x1-strip['position'][0])*area1
                                         -(x0-strip['position'][0])*area0-volume)
        assert abs(fz-expected_force) < 2e-14
        assert abs(my-expected_moment) < 2e-14
        target = identified['rows'][i]
        assert target['status'] == 'adjacent_station_rule' and not target['negative_radius_interval']
        error = abs(node_density-target['archived'])
        assert error < 2e-12
        records.append(dict(source_row_1based=i+1, x=x0, archived=target['archived'],
                            station_density_from_public_wrench=node_density, absolute_error=error,
                            interval_average=fz/length/qd,
                            reported_force_point=strip['position'][0],
                            force_integral_error=abs(fz-expected_force),
                            local_moment_error=abs(my-expected_moment)))
    # Independent integral over the complete (open-ended) reconstructed body.
    volume = math.fsum(math.pi*(b[0]-a[0])*(a[1]**2+a[1]*b[1]+b[1]**2)/3
                       for a, b in zip(outline, outline[1:]))
    x0, r0 = outline[0]; x1, r1 = outline[-1]
    exact_fz = force_factor*math.pi*(r1*r1-r0*r0)
    exact_my = -force_factor*(math.pi*(x1*r1*r1-x0*r0*r0)-volume)
    assert abs(result['force'][2]-exact_fz) < 2e-14
    assert abs(result['moment'][1]-exact_my) < 2e-14
    assert all(abs(result['force'][j]) < 2e-14 for j in (0, 1))
    assert all(abs(result['moment'][j]) < 2e-14 for j in (0, 2))
    area = diameter*(x1-x0)
    for name, expected in dict(CL=math.cos(alpha)*exact_fz/(.5*area),
                               CD=math.sin(alpha)*exact_fz/(.5*area),
                               Cm=exact_my/(.5*area*(x1-x0))).items():
        assert abs(result[name]-expected) < 2e-12, (name, result[name], expected)
    modules = {p.name:sha(p) for p in (ROOT/'openswing').glob('*.py')}
    assert modules == prior['modules']
    args.output.parent.mkdir(parents=True, exist_ok=True)
    response_path = args.output.with_suffix('.response.json')
    request_path = args.output.with_suffix('.request.json')
    with response_path.open('x') as handle:
        handle.write(raw_response+'\n')
    with request_path.open('x') as handle:
        json.dump(request, handle, indent=2, allow_nan=False); handle.write('\n')
    output = dict(observed_utc=datetime.now(timezone.utc).isoformat(),
                  status='MATCHING_FULL_JSON_SOLVE_ON_DISCLOSED_RECONSTRUCTION',
                  case=args.case, rows=records, compared_stations=len(records),
                  maximum_station_error=max(r['absolute_error'] for r in records),
                  maximum_force_error=max(r['force_integral_error'] for r in records),
                  maximum_local_moment_error=max(r['local_moment_error'] for r in records),
                  global_force_error=abs(result['force'][2]-exact_fz),
                  global_moment_error=abs(result['moment'][1]-exact_my),
                  unmatched_finite_stations=identified['finite']-len(records),
                  retained_reference_rows=identified['retained'],
                  finite_reference_rows=identified['finite'],
                  request_path=str(request_path.relative_to(ROOT)), request_sha256=sha(request_path),
                  response_path=str(response_path.relative_to(ROOT)), response_sha256=sha(response_path),
                  model_sha256=sha(model_path), source_analysis_sha256=sha(EVIDENCE/'analysis.json'),
                  script_sha256=sha(Path(__file__)), modules=modules,
                  solve_seconds=solve_seconds, seconds=time.perf_counter()-started,
                  peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                  limits=dict(address_space_mib=512, cpu_seconds=15, wall_seconds=25, blas_threads=1),
                  physical_solves=1, browser_or_wasm_runs=0, native_passes_added=0,
                  qualifications=['Same piecewise-linear radius reconstruction and positive intervals as the preceding kernel check; original ASWING inputs remain unavailable.',
                                  'Pointwise force is recovered from public force and moment only because density is affine on each of these uniform-flow intervals.',
                                  'This does not infer general nodal forces from arbitrary integrated loads.',
                                  'Terminal zeros, negative-radius interval and missing values remain unvalidated and retained.'])
    with args.output.open('x') as handle:
        json.dump(output, handle, indent=2, allow_nan=False); handle.write('\n')
    print(json.dumps({k:output[k] for k in ('case', 'compared_stations', 'maximum_station_error',
                                           'global_force_error', 'global_moment_error',
                                           'solve_seconds', 'seconds', 'peak_rss_kib')}))


if __name__ == '__main__':
    main()
