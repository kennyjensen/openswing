"""Original, independently derived modal checks with source provenance."""
import hashlib
import json
from pathlib import Path
import platform
import runpy
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
import scipy
from scipy.optimize import brentq
from openswing.aero import FlightCondition
from openswing.linear_dynamics import make_system, linearize, eigensystem

benchmark = runpy.run_path(str(Path(__file__).with_name('modal-benchmark.py')))
configuration, exact = benchmark['configuration'], benchmark['typical_section']
files = [Path(__file__).resolve(), Path(__file__).with_name('modal-benchmark.py').resolve(),
         *sorted(Path('openswing').resolve().glob('*.py'))]
provenance = dict(versions=dict(python=platform.python_version(), numpy=np.__version__, scipy=scipy.__version__),
                  source_sha256={str(p.relative_to(Path.cwd())):hashlib.sha256(p.read_bytes()).hexdigest() for p in files})
checkpoint = Path('.reference/modal-verification-checkpoint.json')
saved = json.loads(checkpoint.read_text()) if checkpoint.exists() else {}
cache = saved.get('cases', {}) if saved.get('provenance') == provenance else {}


def case(span, speed, step=1e-5, tolerance=1e-9, panels=4):
    key = json.dumps([span, speed, step, tolerance, panels])
    if key in cache:
        result = cache[key]
        print(f'Resumed verified case: {key}', flush=True)
        return result, np.array([complex(*v) for v in result['eigenvalues']])
    model = configuration(span)
    system, _ = make_system(model, FlightCondition(speed=speed, alpha=0, mach=0, stall=False), panels,
                            gravity=[0, 0, 0])
    a, m = linearize(system, step)
    requested_tolerance = tolerance
    attempts = []
    while True:
        try:
            modes, metadata = eigensystem(a, m, time_scale=system.W, count=panels+4, rank_tolerance=tolerance)
            break
        except ValueError as exc:
            if 'rank is ambiguous' not in str(exc) or tolerance <= 1e-12:
                raise
            attempts.append(dict(rank_tolerance=tolerance, error=str(exc)))
            tolerance = max(1e-12, tolerance/3)
    values = np.array([complex(*mode['eigenvalue']) for mode in modes])
    assert metadata['finite_dimension'] == panels+4
    expected = exact(speed)
    # Each 2D root is paired with the nearest full finite-span root; extra
    # spanwise lag poles are retained in the exported spectrum.
    nearest = np.array([values[np.argmin(abs(values-v))] for v in expected])
    errors = abs(nearest-expected)
    result = dict(span=span, speed=speed, panels=panels, difference_step=step, rank_tolerance=tolerance,
                  requested_rank_tolerance=requested_tolerance, rank_refinement_attempts=attempts,
                  source=model.dumps(), eigenvalues=[[float(v.real), float(v.imag)] for v in values],
                  two_dimensional_roots=[[float(v.real), float(v.imag)] for v in expected],
                  root_absolute_errors=errors.tolist(), maximum_2d_root_error=float(max(errors)),
                  maximum_right_backward_error=max(v['right_backward_error'] for v in modes),
                  maximum_left_backward_error=max(v['left_backward_error'] for v in modes),
                  diagnostics=metadata)
    print(f'span={span}, V={speed}, h={step:g}, rank={tolerance:g}, finite={len(values)}, '
          f'max 2D root error={max(errors):.8g}', flush=True)
    cache[key] = result
    checkpoint.parent.mkdir(exist_ok=True)
    temporary = checkpoint.with_suffix('.tmp')
    temporary.write_text(json.dumps(dict(provenance=provenance, cases=cache), allow_nan=False))
    temporary.replace(checkpoint)
    return result, values


if __name__ == '__main__':
    cases = []
    stable, values = case(40, 40, step=1e-6)
    assert max(values.real) < 0
    cases.append(stable)
    for span, tol in ((40, 1e-9), (80, 1e-10), (160, 1e-11)):
        result, values = case(span, 50, step=1e-6, tolerance=tol)
        assert sum(values.real > 0) == 2
        cases.append(result)
    errors = [c['maximum_2d_root_error'] for c in cases[1:]]
    assert errors[1] < .6*errors[0] and errors[2] < .6*errors[1]
    assert errors[-1] < .5  # <0.5 / s, including the lag-dominated real pole.
    reference = values
    result, values = case(160, 50, step=2e-6, tolerance=3e-12)
    error = max(min(abs(values-v)) for v in reference)
    assert error < 1e-5
    result['maximum_step_rank_refinement_difference'] = float(error)
    cases.append(result)
    # Spatial refinement at fixed aspect ratio is distinct from the 2D limit.
    result, _ = case(40, 50, step=1e-6, tolerance=1e-10, panels=8)
    cases.append(result)
    flutter = brentq(lambda v: max(x.real for x in exact(v) if x.imag > 1), 40, 60, xtol=1e-10)
    report = dict(description='Independent heave/pitch plus empirical circulation-lag benchmark; not ASWING executable or experimental parity.',
                  references=['https://web.mit.edu/drela/Public/web/aswing/asw_uns_theory.pdf'],
                  **provenance,
                  independent_two_dimensional_flutter_speed=float(flutter), cases=cases,
                  limitations=['The 2D reference uses the published empirical lag, not Theodorsen aerodynamics or measured flutter.',
                               'Finite-span lag poles remain; only four structural and the collective lag pole have 2D counterparts.',
                               'Narrow supports with large span create weak inertias. Rank and tangent refinement are essential.',
                               'Automated full-model root tracking/flutter onset, sensors, closed-loop modes and ROMs remain pending.'])
    Path('docs/validation/coupled-modes.json').write_text(json.dumps(report, indent=2, allow_nan=False)+'\n')
