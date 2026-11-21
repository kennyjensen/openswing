"""Reproducible independent forcing, time-order and discontinuity checks."""
import hashlib
import json
from pathlib import Path
import platform
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
import scipy
from openswing.asw import parse_asw
from openswing.aero import FlightCondition
from openswing.time_integration import solve_time

source = '''Name
Rigid forced trajectory verification
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
1 0 0 0 0 9.80665 0 0 0 0 0 19.6133 29.41995 39.2266
End
Beam 1
Rigid massless rod
t y
0 0
2 2
End
'''


def series(result):
    return [dict(time=s['time'], position=s['frame']['position_earth'],
                 velocity=s['frame']['velocity_origin_body'],
                 acceleration=s['frame']['acceleration_reference_body'],
                 forcing=s['forcing_values'], side=s['forcing_side'],
                 order=s['order'], step=s['step'], residual=s['residual']) for s in result['snapshots']]


if __name__ == '__main__':
    cases = []
    for kind in ['prescribed_acceleration_ramp', 'free_thrust_ramp']:
        previous_error = None
        for dt in [.04, .02, .01]:
            model = parse_asw(source)
            args = dict(gravity=[0,0,0], duration=.4, dt=dt, panels=4)
            if kind == 'prescribed_acceleration_ramp':
                args.update(forcing='time Ax\n0 0\n.4 1.2')
                condition = None
                exact_v, exact_x = lambda t: 1.5*t*t, lambda t: .5*t**3
            else:
                row = np.zeros(25)
                row[:15] = [1,0,1,0,0,0,0,-1,0,0,1,0,-1,150,0]
                model.records['engine'] = [row]
                condition = FlightCondition(speed=3, alpha=0, mach=0)
                args.update(frame='free', forcing='time E1\n0 0\n.4 .8')
                exact_v, exact_x = lambda t: -3-t*t, lambda t: -3*t-t**3/3
            result = solve_time(model, condition, **args)
            samples = series(result)
            ev = max(abs(s['velocity'][0]-exact_v(s['time'])) for s in samples)
            ex = max(abs(s['position'][0]-exact_x(s['time'])) for s in samples)
            error = max(ev, ex)
            ratio = None if previous_error is None else error/previous_error
            if ratio is not None:
                assert ratio < .29
            assert max(s['residual'] for s in samples) < 1e-8
            cases.append(dict(kind=kind, dt=dt, duration=.4, max_velocity_error=ev,
                              max_position_error=ex, error_ratio=ratio, samples=samples))
            previous_error = error
            print(f'{kind}: dt={dt}, velocity error={ev:.8g}, position error={ex:.8g}, ratio={ratio}', flush=True)
    forcing = 'time Ax\n0 0\n.113 0\n.113 2\n.27 2'
    result = solve_time(parse_asw(source), panels=4, duration=.27, dt=.04,
                        gravity=[0,0,0], forcing=forcing)
    samples = series(result)
    error = max(abs(s['velocity'][0]-2*max(s['time']-.113,0)) for s in samples)
    event = next(i for i,s in enumerate(samples) if s['time'] == .113)
    assert error < 1e-8 and samples[event]['side'] == 'left' and samples[event+1]['order'] == 1
    cases.append(dict(kind='discontinuous_acceleration', dt=.04, duration=.27,
                      forcing=forcing, maximum_velocity_error=error, samples=samples))
    wing = Path('examples/rectangular.asw').read_text()
    wing = wing[:wing.index('t dCLdF1')]+'t dCLdF1\n0 .1\n100000 .1\nEnd\n'
    wing = (wing.replace('6 0 6 0','100000 0 100000 0').replace('6 .008','100000 .008')
            .replace('.008','0').replace('12 1 12','200000 1 200000'))
    previous_error = None
    for dt in [.02,.01,.005]:
        result = solve_time(parse_asw(wing), FlightCondition(speed=10,alpha=0,mach=0,stall=False), 4,
                            duration=.2, dt=dt, tolerance=1e-10, gravity=[0,0,0], forcing='time F1\n0 0\n.2 .02')
        samples = [dict(time=s['time'],CL=s['CL'],residual=s['residual'],circulation_rate=s['circulation_rate']) for s in result['snapshots']]
        error = max(abs(s['CL']-.01*(s['time']-.1*(1-np.exp(-s['time']/.2)))) for s in samples)
        ratio = None if previous_error is None else error/previous_error
        if ratio is not None:
            assert ratio < .3
        previous_error = error
        cases.append(dict(kind='flap_ramp_empirical_lag', source=wing, dt=dt, duration=.2,
                          maximum_CL_error=error, error_ratio=ratio, samples=samples))
        print(f'flap_ramp_empirical_lag: dt={dt}, CL error={error:.8g}, ratio={ratio}', flush=True)
    paths = [Path(__file__), *sorted(Path('openswing').glob('*.py'))]
    report = dict(description='Independent time-forcing validation, not ASWING numerical parity.',
                  source=source, units='m, s, N, kg',
                  versions=dict(python=platform.python_version(), numpy=np.__version__, scipy=scipy.__version__),
                  source_sha256={str(p.relative_to(Path.cwd()) if p.is_absolute() else p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
                  exact_solutions=dict(prescribed='a=3t, v=1.5t^2, x=0.5t^3',
                                       thrust='m=1, thrust=-2t, v=-3-t^2, x=-3t-t^3/3',
                                       step='a=2 for t>0.113; v=2 max(t-0.113,0)',
                                       flap='High aspect ratio, c=1, V=10, CLcmd=.01t: CL=.01*(t-.1*(1-exp(-t/.2)))'),
                  cases=cases,
                  limitations=['Rigid axial trajectories and high-aspect-ratio small-disturbance lift only; flexible finite-rotation validation remains incomplete.',
                               'Natural cubic endpoint conditions and ASWING discrete time/forcing parity are unverified.',
                               'No gust, sensor/control-law, flutter or experimental comparison.'])
    Path('docs/validation/time-forcing.json').write_text(json.dumps(report, indent=2, allow_nan=False)+'\n')
