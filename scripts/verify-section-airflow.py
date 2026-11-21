"""Closed-form swept-line field and reported local airflow verification.

Prescribed elliptic circulation isolates the velocity integral; it is NOT a
converged operating solution. No production mesher or vortex kernel is used to
construct the analytical reference. The bound line is x=y*tan(sweep), z=0.
"""
import hashlib
import json
from pathlib import Path
import platform
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import numpy as np
import scipy
from openswing.asw import parse_asw
from openswing.aero import FlightCondition, evaluate_aerodynamics
from openswing.geometry import model_meshes


def source(spec):
    L, T, F = spec.get('units', [1., 1., 1.])
    slope = np.tan(np.deg2rad(spec['sweep']))
    return ('! Original prescribed-circulation field verification; not an operating solution.\n'
            'Name\nSwept straight lifting line\nEnd\nUnit\n'
            f'L {L:.17g} m\nT {T:.17g} s\nF {F:.17g} N\nEnd\nConstant\n'
            f'{9.80665*T*T/L:.17g} {1.225*L**4/(F*T*T):.17g} {340.294*T/L:.17g}\nEnd\n'
            f'Reference\n{1/L**2:.17g} {.5/L:.17g} {2/L:.17g}\nEnd\n'
            'Beam 1\nPrescribed field\nt x y z chord Xax Cdf Cdp\n'
            f'-1 {-slope/L:.17g} {-1/L:.17g} 0 {.5/L:.17g} .25 0 0\n'
            f'1 {slope/L:.17g} {1/L:.17g} 0 {.5/L:.17g} .25 0 0\nEnd\n')


def reference(spec):
    n = spec['panels']
    angle = np.deg2rad(spec['sweep'])
    node_angles = np.arange(n+1)*np.pi/n
    middle_angles = (np.arange(n)+.5)*np.pi/n
    centers = -np.cos(middle_angles)
    gamma = np.sin(middle_angles)
    # Stable trigonometric differences avoid subtracting almost equal cosines
    # near the tips. Endpoint rays carry half the interior jump weight.
    jumps = -2*np.sin(np.pi/(2*n))*np.cos(node_angles)
    jumps[[0, -1]] *= .5
    dy = 2*np.sin((middle_angles[:, None]+node_angles[None, :])/2)*np.sin((middle_angles[:, None]-node_angles[None, :])/2)
    # On the straight bound line all finite segments have zero principal-value
    # self velocity. A wind-aligned ray gives [1/dy+sin(sweep)/|dy|]/(4*pi).
    classical = (1/dy)@jumps/(4*np.pi)
    swept = np.sin(angle)*(1/abs(dy))@jumps/(4*np.pi)
    exact_classical = -n*np.sin(np.pi/(2*n))/(2*np.pi)
    assert np.max(abs(classical-exact_classical)) < 2e-10
    velocity = np.column_stack([np.full(n, 30.), np.zeros(n), classical+swept])
    span = np.array([np.sin(angle), np.cos(angle), 0.])
    normal_speed = np.linalg.norm(velocity-(velocity@span)[:, None]*span, axis=1)
    positions = np.column_stack([np.tan(angle)*centers, centers, np.zeros(n)])
    return dict(t=centers, gamma=gamma, velocity=velocity, positions=positions,
                normal_speed=normal_speed, normal_mach=normal_speed/340.294,
                classical=classical, swept=swept)


def compute(spec):
    ref = reference(spec)
    L, T, F = spec.get('units', [1., 1., 1.])
    model = parse_asw(source(spec))
    condition = FlightCondition(speed=30*T/L, alpha=0., mach=0., stall=False,
                               freeze_influences=spec.get('frozen', False))
    result = evaluate_aerodynamics(model, condition, model_meshes(model, spec['panels']),
                                  circulation=ref['gamma']*T/L**2)
    strips = result['strips']
    velocity = np.array([s['relative_velocity'] for s in strips])*L/T
    positions = np.array([s['velocity_position'] for s in strips])*L
    speed = np.array([s['normal_speed'] for s in strips])*L/T
    mach = np.array([s['normal_mach'] for s in strips])
    errors = dict(velocity=float(np.max(abs(velocity-ref['velocity']))),
                  position=float(np.max(abs(positions-ref['positions']))),
                  normal_speed=float(np.max(abs(speed-ref['normal_speed']))),
                  normal_mach=float(np.max(abs(mach-ref['normal_mach']))))
    assert errors['velocity'] < 2e-7 and errors['position'] < 2e-12
    assert errors['normal_speed'] < 2e-7 and errors['normal_mach'] < 1e-9
    assert result['lifting_airflow']['samples'] == spec['panels']
    maximum = result['lifting_airflow']['maximum']
    assert abs(maximum['normal_mach']-max(ref['normal_mach'])) < 1e-9
    assert abs(result['lifting_airflow']['sound_speed']*L/T-340.294) < 1e-10
    # Store selected positions and velocities, including both endpoints, rather
    # than the entire dense influence matrix or all of the intentionally nonzero
    # flow-tangency residual. This is a field check, not a physical trim.
    ids = np.unique(np.linspace(0, len(strips)-1, 9).astype(int))
    samples = [dict(t=float(ref['t'][i]), position=positions[i].tolist(),
                    velocity=velocity[i].tolist(), normal_speed=float(speed[i]), normal_mach=float(mach[i]),
                    reference_velocity=ref['velocity'][i].tolist()) for i in ids]
    return dict(errors=errors, samples=samples, maximum_normal_mach=maximum['normal_mach'],
                exact_unswept_downwash=float(ref['classical'][-1]), sweep_tip_velocity=float(ref['swept'][-1]),
                physical_values_compared=len(strips)*8+1,
                flow_residual=result['residual'], prescribed_circulation=True)


def physical(result):
    return np.r_[result['maximum_normal_mach'],
                 *[np.r_[s['position'], s['velocity'], s['normal_speed'], s['normal_mach']] for s in result['samples']]]


def main():
    cases = []
    for sweep in [-35., 0., 35.]:
        for panels in [32, 64, 128, 256, 512]:
            spec = dict(sweep=sweep, panels=panels)
            result = compute(spec)
            cases.append(dict(specification=spec, result=result))
            print(spec, result['errors'], flush=True)
    for units in [[.3048, 2., 4.4482216152605], [100., .25, .01]]:
        spec = dict(sweep=35., panels=128, units=units, frozen=True)
        result = compute(spec)
        cases.append(dict(specification=spec, result=result))
        print(spec, result['errors'], flush=True)
    hashes = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in [Path(__file__), *sorted((ROOT/'openswing').glob('*.py'))]}
    out = dict(description=__doc__, source_sha256=hashes, cases=cases,
               versions=dict(python=platform.python_version(), numpy=np.__version__, scipy=scipy.__version__),
               limitations=['Prescribed circulation need not satisfy flow tangency; these cases are not accepted aerodynamic operating points.',
                            'The growing swept term exists in the documented wind-aligned horseshoe integral. No smoothing or altered wake law is introduced.',
                            'A local Mach below one does not establish accuracy or mesh convergence. The finite-wing force prediction remains subject to the model limits.'])
    (ROOT/'docs/validation/section-airflow.json').write_text(json.dumps(out,indent=2,allow_nan=False)+'\n')


if __name__ == '__main__':
    main()
