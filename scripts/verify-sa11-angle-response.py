"""One bounded SA-11 incidence diagnostic on the retained 64-interval grid.

Keeps rejected forces explicitly diagnostic. No production equations, validity
checks, source models or primary ISAE completion fractions are changed.
"""
import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import resource
import shutil
import signal
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT/'artifacts/isae/sa11-angle-conventions-20261108'
CONTROL = ROOT/'artifacts/isae/sa11-winglet-receivers-20261108/whole-beam-a1'
NAMES = ('report_minus4', 'horizontal_toe_minus4', 'unswept_incidence_minus4')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def write(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case', choices=NAMES, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    assert not args.output.exists(), 'Use a fresh output path; preserve prior evidence.'
    for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
        assert os.environ.get(name) == '1', name
    # Apply to this process before importing numerical libraries; no child jobs.
    limits = dict(address_space_mib=512, cpu_seconds=15, wall_seconds=25)
    resource.setrlimit(resource.RLIMIT_AS, (512*1024**2, 512*1024**2))
    resource.setrlimit(resource.RLIMIT_CPU, (15, 15))
    def timeout(*_):
        raise TimeoutError('SA11 incidence diagnostic exceeded its 25-second limit')
    signal.signal(signal.SIGALRM, timeout)
    signal.alarm(limits['wall_seconds'])
    start = time.monotonic()
    print('Checking retained inputs and importing the single-process solver.', flush=True)
    audit = read(INPUT/'geometry-audit.json')
    for name, digest in audit['source_pins'].items():
        assert sha(ROOT/name) == digest, name
    for name, digest in audit['file_sha256'].items():
        assert sha(INPUT/name) == digest, name
    prior = read(CONTROL/'report.json')
    for name, digest in prior['artifact_sha256'].items():
        assert sha(CONTROL/name) == digest, name
    pins = {str(p.relative_to(ROOT)): sha(p) for p in [
        *sorted((ROOT/'openswing').glob('*.py')), Path(__file__),
        INPUT/'geometry-audit.json', INPUT/f'{args.case}.asw',
        INPUT/'report_minus4.asw', CONTROL/'report.json',
        CONTROL/'mesh-settings.json', CONTROL/'condition.json', CONTROL/'state.npz',
        CONTROL/'geometry.npz', CONTROL/'whole-new.npz']}
    import numpy as np
    sys.path.insert(0, str(ROOT))
    from openswing.asw import parse_asw
    from openswing.aero import AnalysisError, FlightCondition, evaluate_aerodynamics
    from openswing.geometry import model_meshes
    from openswing.frozen_influence import lifting_geometry

    model = parse_asw((INPUT/f'{args.case}.asw').read_text())
    control = parse_asw((INPUT/'report_minus4.asw').read_text())
    np.testing.assert_array_equal(model.constants, control.constants)
    np.testing.assert_array_equal(model.reference, control.reference)
    assert model.records.keys() == control.records.keys()
    for key in model.records:
        assert len(model.records[key]) == len(control.records[key])
        for actual, expected in zip(model.records[key], control.records[key]):
            np.testing.assert_array_equal(actual, expected)
    for beam, original in zip(model.beams, control.beams, strict=True):
        assert beam.index == original.index and beam.physical_index == 1
        assert beam.distributions.keys() == original.distributions.keys()
        for name, distribution in beam.distributions.items():
            np.testing.assert_array_equal(distribution.t, original.distributions[name].t)
            if name != 'twist' or beam.index == 1:
                np.testing.assert_array_equal(distribution.values, original.distributions[name].values)
    settings = read(CONTROL/'mesh-settings.json')
    meshes = model_meshes(model, dict(default=16, beams=settings))
    geometry = lifting_geometry(meshes, np.array([1., 0., 0.]))
    assert len(geometry['hv']) == 64
    with np.load(CONTROL/'geometry.npz') as old:
        geometry_errors = {k:float(np.max(abs(geometry[k]-old[k]))) for k in old.files}
    assert max(geometry_errors.values()) < 2e-14, geometry_errors
    variant = next(v for v in audit['variants'] if v['name'] == args.case)
    frame_error = max(float(np.max(abs(mesh.frames[..., 2]-row['section_normal'])))
        for mesh, row in zip(meshes[1:], variant['beams'], strict=True))
    assert frame_error < 2e-14, frame_error
    condition = FlightCondition(**read(CONTROL/'condition.json'))
    out = args.output
    out.mkdir(parents=True)
    shutil.copyfile(__file__, out/'driver-used.py')
    shutil.copyfile(INPUT/f'{args.case}.asw', out/'model.asw')
    write(out/'inputs.json', dict(pins=pins, limits=limits, mesh=settings,
                                 condition=asdict(condition)))
    np.savez(out/'geometry.npz', **geometry)
    print(f'Solving {args.case}: 64 intervals, alpha=1, speed=240, frozen influences.', flush=True)
    solve_start = time.monotonic()
    try:
        result = evaluate_aerodynamics(model, condition, meshes)
    except AnalysisError as exc:
        assert exc.details and exc.details['kind'] == 'section_normal_mach', str(exc)
        tb = exc.__traceback__
        while tb and tb.tb_frame.f_code.co_name != 'evaluate_aerodynamics':
            tb = tb.tb_next
        assert tb is not None
        local = tb.tb_frame.f_locals
        arrays = {k:local[k].copy() for k in ('gamma', 'v', 'cl', 'local_mach', 'flift', 'frate', 'fprofile')}
        arrays.update(span=local['p']['s'].copy(),
                      clmax=local['p']['clmax'].copy(), clmin=local['p']['clmin'].copy())
        details = exc.details
        write(out/'rejected.json', dict(message=str(exc), details=details))
        forces = details['surface_force_diagnostic']
        assert forces['available']
        formal = {k:forces['terms']['sum'][k] for k in ('CL', 'CD')}
        residual = details['circulation_residual']
        status = 'REJECTED_STATE_SURFACE_FORCE_DIAGNOSTIC'
    else:
        # Retain unexpected accepted output for review, never assume rejection.
        write(out/'accepted.json', result)
        raise RuntimeError('Unexpected valid state; inspect retained result before extending this diagnostic.')
    solve_seconds = time.monotonic()-solve_start
    assert residual < 1e-8
    np.savez(out/'state.npz', **arrays)
    normal = arrays['v']-np.sum(arrays['v']*arrays['span'], axis=1)[:, None]*arrays['span']
    mach_error = float(np.max(abs(np.linalg.norm(normal, axis=1)/details['sound_speed']-arrays['local_mach'])))
    assert mach_error < 2e-14
    margin = np.minimum(arrays['clmax']-arrays['cl'], arrays['cl']-arrays['clmin'])
    assert margin.min() > 0
    scalar_force = [sum(float(arrays[k][i,j]) for k in ('flift','frate','fprofile') for i in range(64)) for j in range(3)]
    qs = forces['normalization']['dynamic_pressure']*forces['normalization']['reference_area']
    scalar = {k:sum(x*y for x,y in zip(scalar_force, forces['axes'][axis]))/qs
              for k,axis in [('CL','lift'),('CD','drag')]}
    force_error = max(abs(scalar[k]-formal[k]) for k in scalar)
    assert force_error < 2e-14
    control_errors = None
    if args.case == 'report_minus4':
        with np.load(CONTROL/'state.npz') as old:
            control_errors = {k:float(np.max(abs(arrays[k]-old[v]))) for k,v in
                              [('gamma','gamma'),('v','velocity'),('cl','cl')]}
        assert max(control_errors.values()) < 2e-9, control_errors
        for key in formal:
            assert abs(formal[key]-prior['replays']['whole-new'][f'formal_{key}']) < 2e-12
    report = dict(observed_utc=datetime.now(timezone.utc).isoformat(), case=args.case,
        status=status, primary_passes_added=0, reference=prior['reference'], formal=formal,
        error_percent={k:100*(v/prior['reference'][k]-1) for k,v in formal.items()},
        maximum_normal_mach=float(arrays['local_mach'].max()),
        rejected_sections=forces['rejected_strips'], circulation_residual=float(residual),
        minimum_stall_margin_widths=float(margin.min()/condition.stall_width),
        geometry_errors=geometry_errors, frame_error=frame_error,
        independent_mach_error=mach_error, scalar_force_coefficient_error=force_error,
        saved_control_errors=control_errors, solve_seconds=solve_seconds,
        total_seconds=time.monotonic()-start,
        process_maxrss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        limits=limits, artifacts={p.name:sha(p) for p in out.iterdir()},
        warning='Alternative geometry; rejected forces do not supply section moments or a valid equilibrium. No primary pass.')
    write(out/'report.json', report)
    signal.alarm(0)
    print(json.dumps({k:report[k] for k in ['case','formal','error_percent','maximum_normal_mach',
        'rejected_sections','solve_seconds','total_seconds','process_maxrss_kib']}), flush=True)


if __name__ == '__main__':
    main()
