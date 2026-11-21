"""Check finite-frequency wing modes as positive airspeed tends to zero.

No exact-stagnation regularization or change to production equations is made.
The independent still-air energy model is shared with the structural study.
"""
import argparse
import hashlib
import json
import platform
import runpy
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import numpy as np
import scipy
from openswing.asw import parse_asw, Distribution
from openswing.aero import FlightCondition
from openswing.linear_dynamics import make_system, linearize, eigensystem

STRUCTURE = runpy.run_path(str(ROOT/'scripts/verify-durrant-structure.py'))
REFERENCE = ROOT/'docs/validation/durrant-low-speed-reference.json'


def configuration(spec):
    source = STRUCTURE['configuration'](spec)
    source = source.replace('Vacuum structural study only; aerodynamic coefficients are not reconstructed.',
                            'Aerodynamic extension uses Durrant Table 3.11, Case 4.')
    source = source.replace('structural reconstruction', 'aerodynamic reconstruction')
    data = json.loads(REFERENCE.read_text())['aerodynamics']
    names = ['dCLda', 'CLmax', 'CLmin', 'alpha', 'Cm', 'Cdf', 'Cdp']
    values = [2*np.pi if name == 'dCLda' else data[name] for name in names]
    source = source.rsplit('End', 1)[0]+'t '+' '.join(names)+'\n'
    for station in (1, 2):
        source += str(station)+' '+' '.join(map(str, values))+'\n'
    source += 'End\n'
    scale = spec.get('time_unit_s', 1.)
    if scale != 1.:
        # L and M stay SI; one input T is scale seconds. Force values and g
        # scale by scale^2, velocities by scale, density and mass stay fixed.
        model = parse_asw(source)
        model.units.declarations['T'] = (scale, 's')
        model.constants *= np.array([scale**2, 1., scale])
        for beam in model.beams:
            for name in ('EIcc', 'EInn', 'EIcn', 'GJ', 'mg', 'mgcc', 'mgnn'):
                d = beam.distributions[name]
                beam.distributions[name] = Distribution(name, d.t.copy(), d.values*scale**2, d.line)
        source = model.dumps()
    return source


def specifications():
    cases = []
    for wing in ['25', '75']:
        for n in [8, 16, 32]:
            cases.append(dict(wing=wing, panels=n, speed_m_s=.01))
        for extra in [dict(speed_m_s=1.), dict(speed_m_s=.1), dict(speed_m_s=.001, step=1e-6),
                      dict(step=1e-6), dict(shift=[-.3, 1400.]), dict(aero_lag=False), dict(time_unit_s=.1)]:
            cases.append(dict(wing=wing, panels=16, **dict(dict(speed_m_s=.01), **extra)))
    return cases


def compute(spec):
    start = time.monotonic()
    source = configuration(spec)
    scale = spec.get('time_unit_s', 1.)
    condition = FlightCondition(speed=spec['speed_m_s']*scale, alpha=0., beta=0.,
                                mach=0., density=1.225, aero_lag=spec.get('aero_lag', True))
    n = spec['panels']
    panels = dict(default=n, beams={'1': dict(count=n, spacing='uniform')})
    system, _ = make_system(parse_asw(source), condition, panels=panels, gravity=[0., 0., 0.])
    a, m = linearize(system, step=spec.get('step', 1e-5))
    shift = np.asarray(spec.get('shift', [-.01, 1200.]))*scale
    modes, meta = eigensystem(a, m, time_scale=system.W, count=24,
                              method='full_shift_invert', shift=shift)
    # The independent still-air structural modes start above 8 Hz. This
    # explicit window excludes slow circulation roots; shape matching below
    # checks that the selected roots are the intended nine structural modes.
    selected = sorted((d for d in modes if d['eigenvalue'][1]/scale > 20.),
                      key=lambda d: d['eigenvalue'][1])[:9]
    if len(selected) != 9:
        raise ValueError('Nine oscillatory structural roots were not found in the search')
    roots = np.array([d['eigenvalue'] for d in selected])/scale
    residual = max(max(d['right_backward_error'], d['left_backward_error']) for d in selected)
    if residual > 1e-9:
        raise ValueError('Original pencil residual exceeds tolerance')
    network = system.network
    shapes, circulation = [], []
    for mode in selected:
        shape = mode['right'][:6*network.nn].reshape(network.nn, 6).copy()
        shape[:, :3] *= system.L
        shapes.append(dict(real=shape.real.tolist(), imag=shape.imag.tolist()))
        gamma = network.circulation_basis.decode(mode['right'][network.gamma_start:network.operating_start]*network.gamma_scale)/scale
        # Circulation divided by mechanical amplitude, so an arbitrary mode
        # normalization cannot manufacture a low-speed amplitude limit.
        amplitude = np.sqrt(np.sum(abs(shape[:, :3])**2)+.09446**2*np.sum(abs(shape[:, 3:])**2))
        circulation.append(float(np.linalg.norm(gamma)/amplitude))
    base = system.base_report()
    return dict(spec=spec, source=source, condition=vars(condition), actual_elements=network.ne,
                roots_per_s=roots.tolist(), frequencies_Hz=(roots[:, 1]/(2*np.pi)).tolist(),
                growth_per_s=roots[:, 0].tolist(), circulation_per_mechanical_amplitude=circulation,
                shapes=shapes, jig_span_m=network.rj[:, 2].tolist(), max_pencil_backward_error=residual,
                base_residual=base['modal_base']['continuous_residual'],
                base_max_displacement_m=base['max_displacement'], base_CL=base['CL'],
                finite_dimension=meta['finite_dimension'], elapsed_seconds=time.monotonic()-start)


def verify(cases, structural):
    checks = {}
    for wing in ['25', '75']:
        wing_cases = [c for c in cases if c['spec']['wing'] == wing]
        def get(**extra):
            spec = dict(dict(wing=wing, panels=16, speed_m_s=.01), **extra)
            return next(c for c in wing_cases if c['spec'] == spec)
        ref = structural['still_air_continuum'][wing]
        mesh = [get(panels=n) for n in [8, 16, 32]]
        for c in mesh:
            c['still_air_comparison'] = STRUCTURE['compare_shapes'](c, ref)
        errors = np.array([abs(np.array(c['still_air_comparison']['relative_frequency_error'])) for c in mesh])
        if not np.all(errors[1:] < .45*errors[:-1]):
            raise ValueError(f'{wing}: low-speed frequencies do not converge toward still-air mechanics')
        if min(mesh[-1]['still_air_comparison']['modal_assurance']) < .99:
            raise ValueError(f'{wing}: refined low-speed shapes disagree with still-air mechanics')
        base = get()
        invariance = {}
        for extra in [dict(step=1e-6), dict(shift=[-.3, 1400.]), dict(time_unit_s=.1)]:
            c = get(**extra)
            delta = abs(np.array(c['roots_per_s'])-base['roots_per_s'])/np.maximum(1., abs(np.array(base['roots_per_s'])))
            if max(delta.ravel()) > 2e-7:
                raise ValueError(f'{wing}: tangent/search/unit change alters physical roots')
            invariance[next(iter(extra))] = float(max(delta.ravel()))
        speed_cases = [get(speed_m_s=u, **(dict(step=1e-6) if u == .001 else {})) for u in [1., .1, .01, .001]]
        frequencies = np.array([c['frequencies_Hz'] for c in speed_cases])
        growth = np.array([c['growth_per_s'] for c in speed_cases])
        gamma = np.array([c['circulation_per_mechanical_amplitude'] for c in speed_cases])
        if not np.all(abs(growth[1:]) < .15*abs(growth[:-1])):
            raise ValueError(f'{wing}: aerodynamic growth/decay does not tend to zero with speed')
        if not np.all(gamma[1:] < .15*gamma[:-1]):
            raise ValueError(f'{wing}: normalized circulation amplitude does not tend to zero with speed')
        last_change = abs(frequencies[-1]/frequencies[-2]-1)
        if max(last_change) > 2e-6:
            raise ValueError(f'{wing}: finite-frequency low-speed limit is not resolved')
        lag_off = get(aero_lag=False)
        lag_off['still_air_comparison'] = STRUCTURE['compare_shapes'](lag_off, ref)
        if min(lag_off['still_air_comparison']['modal_assurance']) < .99:
            raise ValueError(f'{wing}: algebraic-circulation structural shapes differ from still-air reference')
        checks[wing] = dict(mesh_relative_frequency_errors=errors.tolist(), invariance=invariance,
                            speed_m_s=[1., .1, .01, .001], frequencies_Hz=frequencies.tolist(),
                            growth_per_s=growth.tolist(), circulation_per_mechanical_amplitude=gamma.tolist(),
                            last_speed_relative_frequency_change=last_change.tolist())
    return checks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--limit', type=int, help='Populate only the first N cases; leaves the complete report untouched.')
    args = parser.parse_args()
    files = [Path(__file__), ROOT/'scripts/verify-durrant-structure.py', REFERENCE,
             ROOT/'docs/validation/durrant-reference.json', ROOT/'docs/validation/durrant-structure.json',
             *sorted((ROOT/'openswing').glob('*.py'))]
    hashes = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    provenance = dict(source_sha256=hashes, versions=dict(python=platform.python_version(), numpy=np.__version__, scipy=scipy.__version__))
    key = hashlib.sha256(json.dumps(provenance, sort_keys=True).encode()).hexdigest()
    cache = ROOT/'.reference/durrant-low-speed'/key
    cache.mkdir(parents=True, exist_ok=True)
    specs = specifications()
    for spec in specs[:args.limit]:
        name = hashlib.sha256(json.dumps(spec, sort_keys=True).encode()).hexdigest()
        path = cache/f'{name}.json'
        if not path.exists():
            result = compute(spec)
            path.write_text(json.dumps(result, allow_nan=False)+'\n')
        result = json.loads(path.read_text())
        print(spec, result['frequencies_Hz'], flush=True)
    paths = [cache/(hashlib.sha256(json.dumps(spec, sort_keys=True).encode()).hexdigest()+'.json') for spec in specs]
    if not all(p.exists() for p in paths):
        print('Partial cache retained; run without --limit to complete the study.', flush=True)
        return
    cases = [json.loads(p.read_text()) for p in paths]
    structural = json.loads((ROOT/'docs/validation/durrant-structure.json').read_text())
    checks = verify(cases, structural)
    out = dict(description='Finite-frequency modal limit from positive airspeed; exact stagnation and experimental parity remain unresolved.',
               **provenance, reference=json.loads(REFERENCE.read_text()), cases=cases, checks=checks,
               still_air_reference=structural['still_air_continuum'])
    target = ROOT/'docs/validation/durrant-low-speed.json'
    target.write_text(json.dumps(out, indent=2, allow_nan=False)+'\n')
    print('Wrote', target.relative_to(ROOT), flush=True)


if __name__ == '__main__':
    main()
