"""Reproduce independent mode/panel refinement for Fourier circulation.

Fetch the pinned MIT flying-wing input first. Previous pointwise states are
checked warm starts only; Fourier states start from a new equilibrium solve.
"""
import hashlib
import json
import platform
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import numpy as np
import scipy
from openswing.asw import parse_asw
from openswing.aero import FlightCondition, solve_rigid
from openswing.linear_dynamics import make_system, linearize, eigensystem
from openswing.operating import OperatingConstraint


def elliptic_source():
    span = 80.; ts = np.linspace(-span/2, span/2, 201)
    chords = np.maximum(np.sqrt(1-(2*ts/span)**2), 1e-5)
    text = f'Name\nElliptic Fourier verification\nEnd\nUnit\nL 1 m\nT 1 s\nF 1 N\nEnd\nConstant\n9.80665 1.225 340.294\nEnd\nReference\n{np.pi*span/4} 1 {span}\nEnd\nBeam 1\nWing\nt y chord Xax\n'
    return text+'\n'.join(f'{t} {t} {c} .25' for t,c in zip(ts,chords))+'\nEnd\n'


def rigid_case(source, panels, count, *, alpha=5.):
    condition = FlightCondition(alpha=alpha, mach=0., stall=False, circulation_modes={1: count})
    result = solve_rigid(parse_asw(source), condition, panels)
    assert result['residual'] < 1e-9
    return dict(panels=panels, modes=count, alpha=alpha, result={k: result[k] for k in
        ('CL', 'CD', 'CDi', 'CDi_near', 'efficiency', 'residual', 'circulation_local_residual', 'circulation_discretization')})


def modal_case(source, count):
    condition = FlightCondition(speed=50., alpha=0., mach=0., stall=False, circulation_modes={2: count})
    system, _ = make_system(parse_asw(source), condition, 4, gravity=[0, 0, 0])
    a, m = linearize(system)
    modes, meta = eigensystem(a, m, time_scale=system.W, count=30)
    errors = []
    for mode in modes:
        lam = complex(*mode['eigenvalue']); v, w = mode['right'], mode['left']
        norm = np.linalg.norm(a)+abs(lam)*np.linalg.norm(m)
        errors.extend([float(np.linalg.norm(a@v-lam*m@v)/(norm*np.linalg.norm(v))),
                       float(np.linalg.norm(w.conj()@a-lam*(w.conj()@m))/(norm*np.linalg.norm(w)))])
    assert max(errors) < 1e-9
    return dict(panels=4, modes=count, condition=dict(speed=50., alpha=0., mach=0., stall=False, circulation_modes={2: count}),
                finite_dimension=meta['finite_dimension'], roots=[mode['eigenvalue'] for mode in modes],
                maximum_original_pencil_backward_error=max(errors), base=system.base_report())


def aircraft_case(source, previous, point, panels, count):
    started = time.monotonic()
    old = next(c for c in previous['flying_wing'] if c['requested_panels'] == panels)
    v = old['base']['operating_values']
    condition = FlightCondition(speed=64., alpha=v['alpha'], controls={2: v['control.2']},
        attitude=[0., v['attitude.elevation'], 0.], circulation_modes={1: count})
    constraints = [OperatingConstraint('alpha', 'force.z'), OperatingConstraint('attitude.elevation', 'force.x'),
                   OperatingConstraint('control.2', 'moment.y')]
    system, _ = make_system(parse_asw(source), condition, panels, frame='free', operating_constraints=constraints,
        initial_state=old['base']['equilibrium_state'] if count == 0 else None)
    base = system.base_report()
    assert base['modal_base']['continuous_residual'] < 1e-8
    if count == 0:
        for k in ('CL', 'CD', 'efficiency'):assert abs(base[k]-old['base'][k]) < 1e-8
    result = dict(panels=panels, modes=count, actual_lifting_panels=base['lifting_panels'],
        published_efficiency=point['efficiency'], efficiency_difference=base['efficiency']-point['efficiency'],
        base=base, elapsed_seconds=time.monotonic()-started)
    print(f"Flying wing: {base['lifting_panels']} intervals, {base['circulation_discretization']['independent_unknowns']} unknowns, e={base['efficiency']:.8f}; {result['elapsed_seconds']:.1f}s", flush=True)
    return result


def main():
    reference_path = ROOT/'docs/validation/fw-reference.json'
    prior_path = ROOT/'docs/validation/trefftz.json'
    reference = json.loads(reference_path.read_text()); previous = json.loads(prior_path.read_text())
    official = (ROOT/'.reference/fw.asw').read_bytes()
    assert hashlib.sha256(official).hexdigest() == reference['aircraft']['sha256']
    files = [Path(__file__), reference_path, prior_path, ROOT/'examples/rectangular.asw', ROOT/'examples/heave-pitch.asw', *sorted((ROOT/'openswing').glob('*.py'))]
    hashes = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    versions = dict(python=platform.python_version(), numpy=np.__version__, scipy=scipy.__version__)
    key = hashlib.sha256(json.dumps(dict(hashes=hashes, versions=versions), sort_keys=True).encode()).hexdigest()
    cache = ROOT/'.reference/circulation'/key; cache.mkdir(parents=True, exist_ok=True)
    def cached(name, function):
        path = cache/f'{name}.json'
        if not path.exists():path.write_text(json.dumps(function(), allow_nan=False)+'\n')
        return json.loads(path.read_text())
    ellipse = elliptic_source()
    analytical = [cached(f'ellipse-{n}', lambda n=n: rigid_case(ellipse, n, 1, alpha=.1)) for n in (32, 64, 96)]
    expected_slope = 2*np.pi/(1+np.pi/(2*80))
    for case in analytical:
        assert abs(case['result']['CL']/np.deg2rad(.1)/expected_slope-1) < .01
        assert abs(case['result']['efficiency']-1) < 1e-10
    rectangle = (ROOT/'examples/rectangular.asw').read_text()
    rectangular = [cached(f'rectangle-{k}', lambda k=k: rigid_case(rectangle, 16, k)) for k in (0, 1, 3, 7, 15)]
    heave = (ROOT/'examples/heave-pitch.asw').read_text()
    dynamics = [cached(f'modal-{k}', lambda k=k: modal_case(heave, k)) for k in (0, 1, 3)]
    point = next(p for p in reference['points'] if p['speed_ft_s'] == 64)
    aircraft = [cached(f'fw-{n}-{k}', lambda n=n, k=k: aircraft_case(official.decode(), previous, point, n, k))
                for n in (16, 32) for k in (0, 7, 15)]
    output = dict(description='Independent panel/mode refinement of the documented Fourier circulation representation.',
        source_sha256=hashes, versions=versions, reference=reference,
        analytical=dict(source=ellipse, expected_lift_slope_per_rad=expected_slope, cases=analytical),
        rectangular=rectangular, coupled_modes=dynamics, flying_wing=aircraft,
        interpretation='Original ASWING panel and circulation-mode settings are unknown. Both discretizations must be refined; weighted residual convergence does not imply small local flow defect. No constants are fitted.',
        convention='Gamma=sum A_k sin(k theta), theta=acos(2 arc/L-1) on each logical lifting beam; theta and delta-theta remain material coordinates under deformation. Pointwise horseshoe influence and physical forces retain all structural intervals.')
    target = ROOT/'docs/validation/circulation.json'
    target.write_text(json.dumps(output, indent=2, allow_nan=False)+'\n')
    print(f'Wrote {target.relative_to(ROOT)}', flush=True)


if __name__ == '__main__':main()
