"""Independent gust-load formulas and temporal refinement, with provenance."""
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import platform
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
import scipy
from openswing.asw import parse_asw
from openswing.aero import FlightCondition, solve_rigid
from openswing.network import solve_static
from openswing.time_integration import solve_time


def base_source():
    return '''Name
Original gust verification rod
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
2 1 2
End
Ground
1 0 0
End
Weight
1 2 0 2 0 0 2 0
End
Beam 1
Massless axial rod
t y EA
0 0 1000
2 2 1000
End
'''


if __name__ == '__main__':
    cases = []
    source = base_source()
    c = FlightCondition(speed=10, alpha=0, mach=0,
                        gust=dict(type='expression', components=['-10', '5*y', '0']))
    result = solve_static(parse_asw(source), c, 4, gravity=[0, 0, 0], tolerance=1e-10)
    k = .5*1.225*2*25*2/1000
    exact_y = (1-np.sqrt(1-8*k))/(2*k)
    error = abs(result['nodes'][-1]['position'][1]-exact_y)
    assert error < 2e-9
    cases.append(dict(name='elastic_gust_feedback', source=source, condition=asdict(c),
                      exact_formula='y = 2 + (.5*rho*CDA*25)*(L/EA)*y^2; stable smaller root',
                      exact_tip_y=exact_y, actual_tip_y=result['nodes'][-1]['position'][1], error=error,
                      point_force=result['point_forces'][0], residual=result['residual']))
    print(f'Elastic gust feedback: tip position error {error:.8g}', flush=True)

    source = source.replace('1 2 0 2 0 0 2 0', '1 0 0 0 0 0 .2 0').replace('1000', '0')
    c = FlightCondition(speed=10, alpha=0, mach=0,
                        gust=dict(type='cosine', amplitude=[0, 0, 2], origin=[-.4, 0, 0], length=.1))
    out = solve_time(parse_asw(source), c, 4, duration=.08, dt=.08, gravity=[0, 0, 0])
    samples = []
    for s in out['snapshots']:
        w = 1-np.cos(np.pi*np.clip((10*s['time']-.4)/.1, 0, 2))
        exact = .5*1.225*.2*np.hypot(10, w)*np.array([10, 0, w])
        samples.append(dict(time=s['time'], force=s['point_forces'][0], exact_force=exact.tolist(),
                            maximum_force_error=float(np.max(abs(s['point_forces'][0]-exact))),
                            step=s['step'], residual=s['residual']))
    error = max(s['maximum_force_error'] for s in samples)
    assert error < 1e-9 and max(s['force'][2] for s in samples) > 2.4
    cases.append(dict(name='narrow_frozen_cosine', source=source, condition=asdict(c), duration=.08, requested_step=.08,
                      phase_limit_radians=float(np.pi/8), gust_resolution_retries=out['gust_resolution_retries'],
                      exact_formula='w(t)=1-cos(pi*clip((10t-.4)/.1,0,2)); F=.5*rho*CDA*sqrt(100+w^2)*[10,0,w]',
                      maximum_force_error=error, samples=samples))
    print(f'Narrow frozen cosine: force error {error:.8g}; {out["accepted_steps"]} steps', flush=True)

    source = Path('examples/rectangular.asw').read_text()
    source = source[:source.index('t dCLdF1')]+'End\n'
    source = (source.replace('6 0 6 0', '100000 0 100000 0').replace('6 .008', '100000 .008')
              .replace('.008', '0').replace('12 1 12', '200000 1 200000'))
    c = FlightCondition(speed=10, alpha=0, mach=0, stall=False,
                        gust=dict(type='expression', components=['0', '0', '.002*t']))
    previous = None
    for dt in [.02, .01, .005]:
        out = solve_time(parse_asw(source), c, 4, duration=.2, dt=dt, tolerance=1e-10, gravity=[0, 0, 0])
        samples = [dict(time=s['time'], CL=s['CL'],
                        exact_CL=float(2*np.pi*.002/10*(s['time']-.1*(1-np.exp(-s['time']/.2)))),
                        residual=s['residual']) for s in out['snapshots']]
        error = max(abs(s['CL']-s['exact_CL']) for s in samples)
        ratio = None if previous is None else error/previous
        assert ratio is None or ratio < .3
        cases.append(dict(name='temporal_gust_empirical_lag', source=source, condition=asdict(c), dt=dt, duration=.2,
                          exact_formula='Small-disturbance infinite-AR limit: tau=2c/V=.2; CL=2*pi*.002/10*(t-.1*(1-exp(-t/.2)))',
                          maximum_CL_error=error, refinement_ratio=ratio, samples=samples))
        print(f'Gust lag: dt {dt}; CL error {error:.8g}; ratio {ratio}', flush=True)
        previous = error
    assert previous < 6e-8
    files = [Path(__file__).resolve(), *sorted(Path('openswing').resolve().glob('*.py'))]
    report = dict(description='Independent prescribed-gust checks, not ASWING executable or experimental parity.',
                  versions=dict(python=platform.python_version(), numpy=np.__version__, scipy=scipy.__version__),
                  source_sha256={str(p.relative_to(Path.cwd())): hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
                  cases=cases,
                  limitations=['Circulation lag is empirical; the reference is not an exact Sears gust transfer function.',
                               'Temporal ramp is a small-disturbance infinite-aspect-ratio limit with finite-AR/nonlinear error.',
                               'No numeric .gust catalog compatibility or measured-aircraft comparison is established.'])
    Path('docs/validation/gust-response.json').write_text(json.dumps(report, indent=2, allow_nan=False)+'\n')
