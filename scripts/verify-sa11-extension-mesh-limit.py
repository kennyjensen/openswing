"""Fixed-minimum mesh stability: twelve predeclared, serial SA-11 solves."""
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
PARENT = ROOT / 'artifacts/isae/sa11-extension-drag-budget-r2-20261108'
MINIMUM = .0164659927127284
read = lambda p: json.loads(p.read_text())
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
utc = lambda: datetime.now(timezone.utc).isoformat()


def write(path, value):
    text = json.dumps(value, indent=2, allow_nan=False) + '\n'
    with path.open('x') as stream:
        stream.write(text)


def bounded():
    for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
        assert os.environ.get(name) == '1'
    resource.setrlimit(resource.RLIMIT_AS, (512*1024**2, 512*1024**2))
    resource.setrlimit(resource.RLIMIT_CPU, (15, 15))
    signal.alarm(25)


def check(pins):
    for name, digest in pins.items():
        assert sha(ROOT / name) == digest, name


def prepare(out):
    bounded()
    assert not out.exists()
    parent = read(PARENT / 'plan.json')
    check(parent['pins'])
    analysis = read(PARENT / 'analysis.json')
    assert analysis['verified'] and analysis['plan_sha256'] == sha(PARENT / 'plan.json')
    controls = [r for r in analysis['cases'] if r['settings']['alpha'] in (3, 5)
                and not r['settings']['freeze_influences']]
    assert len(controls) == 8
    pins = dict(parent['pins'])
    for row in controls:
        folder = PARENT / row['id']
        assert sha(folder / 'report.json') == row['report_sha256']
        pins[str((folder / 'report.json').relative_to(ROOT))] = row['report_sha256']
        for name, digest in row['artifacts'].items():
            assert sha(folder / name) == digest
            pins[str((folder / name).relative_to(ROOT))] = digest
    sys.path.insert(0, str(ROOT))
    from openswing.asw import parse_asw
    from openswing.geometry import model_meshes
    cases = []
    for control in controls:
        if control['intervals'] != 108:
            continue
        model = parse_asw((ROOT / control['case']['original_job']['model_path']).read_text(),
                          beam_interpolation='natural-v1')
        for n in (256, 512, 1024):
            mesh_spec = dict(default=n, beams={'1': dict(count=n, spacing='cosine', min_spacing=MINIMUM)})
            mesh, = model_meshes(model, mesh_spec)
            assert min(mesh.length) >= MINIMUM - 1e-12
            assert len(mesh.tm) <= 256, 'Stop at preflight; do not launch an oversized solve.'
            cases.append(dict(id=f"v{int(control['settings']['speed'])}-a{int(control['settings']['alpha'])}-n{n}",
                requested_intervals=n, mesh=mesh_spec, control=control,
                preflight=dict(actual_intervals=len(mesh.tm), minimum_interval=float(min(mesh.length)),
                               maximum_interval=float(max(mesh.length)), nodes=[float(mesh.t0[0]), *map(float, mesh.t1)])))
    assert len(cases) == 12
    for path in (Path(__file__), PARENT / 'plan.json', PARENT / 'analysis.json'):
        pins[str(path.relative_to(ROOT))] = sha(path)
    out.mkdir(parents=True)
    (out / 'driver-used.py').write_text(Path(__file__).read_text())
    write(out / 'plan.json', dict(observed_utc=utc(), cases=cases, controls=controls, pins=pins,
        minimum_spacing=MINIMUM, physical_calls=12, primary_passes_added=0,
        previous_goal_turn='No progress: saved primary results and current progress plot were rechecked, with no new state or scientific conclusion. Proceed to the documented fixed-minimum force-stability question.',
        source_basis='Drela steady Eqs150--157,200--204 and64--74; ISAE PartI section5 p21 warns about fine-mesh singularity. References/catalog and prior physical-mesh versus Fourier study inspected.',
        protocol='Original extension at alpha3/5 and240/272m/s; cosine requests256/512/1024 with unchanged16.466mm minimum. Reuse authenticated64/128 controls. All other original settings fixed. Retain all rejections. No best-count selection or primary-scope replacement.',
        stability=dict(metrics=['CL', 'CD', 'CDi', 'Cm'],
            definition='100*abs(new-old)/abs(new), separately at each operating point. Examine the final two successive refinements; both <=1% for all metrics is diagnostic stability over these sampled requests only, not proof of continuum convergence or an added validation gate.',
            percent=1., refinements=2),
        limits='One BLAS thread;512MiB address space;15CPU/25wall seconds;one solve per foreground invocation. Mesh-only preflight caps actual intervals at256.'))
    signal.alarm(0)
    print(json.dumps([dict(id=c['id'], **{k:v for k,v in c['preflight'].items() if k!='nodes'}) for c in cases]), flush=True)


def run(out, index):
    bounded()
    clock = time.monotonic()
    plan = read(out / 'plan.json')
    check(plan['pins'])
    case = plan['cases'][index]
    control = case['control']
    folder = out / case['id']
    assert not folder.exists()
    import numpy as np
    sys.path.insert(0, str(ROOT))
    from openswing.asw import parse_asw
    from openswing.geometry import model_meshes
    from openswing.aero import FlightCondition, evaluate_aerodynamics, AnalysisError
    from openswing.frozen_influence import lifting_geometry
    model = parse_asw((ROOT / control['case']['original_job']['model_path']).read_text(),
                      beam_interpolation='natural-v1')
    mesh, = model_meshes(model, case['mesh'])
    assert [float(mesh.t0[0]), *map(float, mesh.t1)] == case['preflight']['nodes']
    condition = FlightCondition(**control['settings'])
    e, _, ez = condition.vectors()
    geometry = lifting_geometry([mesh], e)
    folder.mkdir()
    write(folder / 'setup.json', dict(condition=control['settings'], mesh=case['mesh'], preflight=case['preflight']))
    np.savez(folder / 'geometry.npz', **geometry, span=mesh.frames[...,1], t=mesh.tm,
             cdf=mesh.beam.value('Cdf', mesh.tm), cdp=mesh.beam.value('Cdp', mesh.tm))
    start = time.monotonic()
    try:
        result = evaluate_aerodynamics(model, condition, [mesh])
    except AnalysisError as exc:
        assert exc.details and exc.details['kind'] == 'section_normal_mach', str(exc)
        write(folder / 'rejected.json', dict(error=str(exc), details=exc.details))
        report = dict(status='rejected', actual=None, passed=0, required=7)
    else:
        write(folder / 'accepted.json', result)
        assert result['converged'] and result['residual'] < 1e-8
        actual = {k: float(result['Cm_origin' if k=='Cm' else k]) for k in ('CL','CD','CDi','Cm','efficiency')}
        actual.update(lift=float(np.dot(result['force'], ez)), drag=float(np.dot(result['force'], e)))
        errors = {k: 100*(actual[k]-v)/abs(v) for k,v in control['reference'].items()}
        cl = np.array([s['cl'] for s in result['strips']])
        margin = np.minimum(mesh.beam.value('CLmax', mesh.tm)-cl, cl-mesh.beam.value('CLmin', mesh.tm))/.05
        report = dict(status='computed', actual=actual, relative_percent_errors=errors,
            passed=int(sum(abs(v)<=5 for v in errors.values())), required=7, residual=result['residual'],
            maximum_normal_mach=max(s['normal_mach'] for s in result['strips']),
            airflow_maximum=result['lifting_airflow']['maximum'],
            minimum_stall_margin_widths=float(min(margin)), CDi_near=result['CDi_near'], CDp=result['CDp'])
    report.update(id=case['id'], observed_utc=utc(), reference=control['reference'], settings=control['settings'],
        requested_intervals=case['requested_intervals'], actual_intervals=len(mesh.tm),
        minimum_interval=float(min(mesh.length)), maximum_interval=float(max(mesh.length)),
        physical_calls=1, solve_seconds=time.monotonic()-start, seconds=time.monotonic()-clock,
        peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        plan_sha256=sha(out/'plan.json'), artifacts={p.name:sha(p) for p in folder.iterdir()})
    write(folder / 'report.json', report)
    signal.alarm(0)
    print(json.dumps({k:v for k,v in report.items() if k not in ('artifacts','settings','reference','actual','airflow_maximum')}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('action', choices=('prepare','run'))
    parser.add_argument('--index', type=int)
    args = parser.parse_args()
    if args.action == 'prepare':
        prepare(args.output.resolve())
    else:
        run(args.output.resolve(), args.index)
