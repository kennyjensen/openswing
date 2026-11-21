"""Original forced mechanical/coupled aeroelastic checks with source hashes."""
import hashlib
import json
from pathlib import Path
import platform
import runpy
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
import scipy
from openswing.aero import FlightCondition
from openswing.asw import parse_asw
from openswing.frequency_response import solve_frequency_response

benchmark = runpy.run_path(str(Path(__file__).with_name('modal-benchmark.py')))
files = [Path(__file__).resolve(), Path(__file__).with_name('modal-benchmark.py').resolve(),
         Path('examples/forced-oscillator.asw').resolve(), *sorted(Path('openswing').resolve().glob('*.py'))]
provenance = dict(versions=dict(python=platform.python_version(), numpy=np.__version__, scipy=scipy.__version__),
                  source_sha256={str(p.relative_to(Path.cwd())):hashlib.sha256(p.read_bytes()).hexdigest() for p in files})
checkpoint = Path('.reference/frequency-verification-checkpoint.json')
saved = json.loads(checkpoint.read_text()) if checkpoint.exists() else {}
cache = saved.get('cases', {}) if saved.get('provenance') == provenance else {}


def z(value):
    return np.array(value['real'])+1j*np.array(value['imag'])


def complex_rows(values):
    return dict(real=np.asarray(values).real.tolist(), imag=np.asarray(values).imag.tolist())


def forced_section(speed, omega):
    """Independent per-span force/moment balances, state [h,theta,v,q,Gamma].

    A unit upward force acts at the elastic axis; no applied pitch torque.
    A uniform vertical gust adds pi*w to the circulation equation only. The
    implemented ambient gust has no separate acceleration/pressure-gradient
    term; this reference deliberately matches that documented model scope.
    """
    rho = 1.225; ma = rho*np.pi/4; mass = 20*ma; inertia = .06*mass
    a, d, e = -.15, .1, .1; kh, kt = 400*mass, 2500*inertia
    A, M, B = np.zeros((5, 5)), np.zeros((5, 5)), np.zeros((5, 2))
    M[0, 0] = M[1, 1] = 1.; A[0, 2] = A[1, 3] = 1.
    M[2, 2:] = [mass+ma, -mass*e-ma*d, -rho]
    M[3, 2:] = [-mass*e-ma*d, inertia+ma*(d*d+1/32), a*rho]
    A[2, [0, 3, 4]] = [-kh, ma*speed, rho*speed]
    A[3, [1, 3, 4]] = [-kt, -ma*(d+.25)*speed, -a*rho*speed]
    M[4, 4] = 2/speed
    A[4, [1, 2, 3, 4]] = [np.pi*speed, -np.pi, np.pi*(a+.5), -1]
    B[2, 0] = 1.; B[4, 1] = np.pi
    return np.linalg.solve(1j*omega*M-A, B)


def record(key, compute):
    if key in cache:
        print('Resumed '+key, flush=True)
        return cache[key]
    result = compute(); cache[key] = result
    checkpoint.parent.mkdir(exist_ok=True)
    temporary = checkpoint.with_suffix('.tmp')
    temporary.write_text(json.dumps(dict(provenance=provenance, cases=cache), allow_nan=False))
    temporary.replace(checkpoint)
    print(key+': '+json.dumps(result['errors']), flush=True)
    return result


def oscillator(step, panels):
    source = Path('examples/forced-oscillator.asw').read_text()
    frequencies = np.r_[0., np.geomspace(.1, 100, 13), np.sqrt(250)]
    frequencies.sort()
    out = solve_frequency_response(parse_asw(source), FlightCondition(speed=10, alpha=0, mach=0), panels,
        frequencies=frequencies, inputs=['power.1'], gravity=[0, 0, 0], step=step)
    assert out['converged']
    actual = np.array([z(s['responses'][0]['output']['nodes'][-1]['displacement'])[1] for s in out['samples']])
    expected = 1/(500*(1+1j*.02*frequencies)-2*frequencies**2)
    error = float(max(abs(actual-expected)))
    assert error < 1e-10
    return dict(kind='axial spring-mass', source=source, panels=panels, step=step, omega=frequencies.tolist(),
                computed=complex_rows(actual), independent=complex_rows(expected), errors=dict(maximum_absolute=error),
                maximum_backward_error=max(max(s['diagnostics']['backward_errors']) for s in out['samples']))


def aeroelastic(span, step=1e-6, panels=4):
    configuration = benchmark['configuration'](span)
    # Gain=span gives one force unit per unit span per engine setting.
    source = configuration.dumps()+f'\nEngine\n1 0 2 0 0 0 1 0 0 1 {span} 0 -1 0 0\nEnd\n'
    frequencies = [1., 15., 25., 35., 50.]; speed=40.
    out = solve_frequency_response(parse_asw(source), FlightCondition(speed=speed, alpha=0, mach=0, stall=False),
        panels, frequencies=frequencies, inputs=['power.1', dict(kind='gust', wave='uniform', name='uniform vertical gust')],
        gravity=[0, 0, 0], step=step)
    assert out['converged']
    root = next(n['index'] for n in out['base']['nodes'] if n['beam'] == 2 and n['t'] == 0)
    actual = np.array([[[z(r['output']['nodes'][root]['displacement'])[2], z(r['output']['nodes'][root]['rotation'])[1]]
                        for r in s['responses']] for s in out['samples']]).transpose(0, 2, 1)
    expected = np.array([forced_section(speed, w)[:2] for w in frequencies])
    # Compare h and theta separately, each normalized by its own maximum
    # reference magnitude over frequency. Units and input channels stay separate.
    errors = np.max(abs(actual-expected), axis=0)/np.max(abs(expected), axis=0)
    return dict(kind='coupled heave/pitch/lag', source=source, span=span, speed=speed, panels=panels, step=step,
                omega=frequencies, output_order=['heave [L]', 'pitch [rad]'],
                input_order=['upward axis force per span [F/L]', 'uniform vertical gust [L/T]'],
                computed=complex_rows(actual), independent=complex_rows(expected),
                errors=dict(normalized_maximum=errors.tolist()),
                maximum_backward_error=max(max(s['diagnostics']['backward_errors']) for s in out['samples']))


if __name__ == '__main__':
    cases = [record(f'oscillator h={step} p={panels}', lambda:oscillator(step, panels))
             for step, panels in ((1e-5, 4), (2e-5, 4), (1e-5, 8))]
    aero = [record(f'coupled AR={span}', lambda:aeroelastic(span)) for span in (40, 80, 160)]
    errors = np.array([c['errors']['normalized_maximum'] for c in aero])
    assert np.all(errors[1:] < .7*errors[:-1]), errors
    assert np.max(errors[-1]) < .12, errors[-1]
    cases += aero
    report = dict(description='Independent forced oscillator and coupled heave/pitch/empirical-lag comparison; not ASWING executable or experimental parity.',
                  references=['https://web.mit.edu/drela/Public/web/aswing/asw_uns_theory.pdf'],
                  **provenance, cases=cases,
                  limitations=['The 2D model uses empirical circulation lag and the implemented ambient-gust convention, not exact Sears/Theodorsen theory.',
                               'Finite-span convergence toward an independent infinite-span reference is distinct from mesh convergence at fixed span.',
                               'The forced particular solution does not establish dynamic stability; no feedback sensors or controller states are present.'])
    Path('docs/validation/frequency-response.json').write_text(json.dumps(report, indent=2, allow_nan=False)+'\n')
