"""Independent infinite-wing checks of steady PG/stall closure.

Uses the analytic infinite-line integral, not production influence or stall
helpers. Finite proxies at two lengths must approach that limit. Prescribed
circulation states are deliberately not equilibrium solutions or ISAE targets.
"""
from pathlib import Path
import argparse
import hashlib
import json
import math
import sys
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from openswing.aero import FlightCondition, evaluate_aerodynamics
from openswing.asw import parse_asw
from openswing.geometry import model_meshes

CHORD, SPEED, SLOPE = .8, 30., 5.4
LOWER, UPPER, WIDTH, FACTOR = -.9, 1.2, .07, 40.
LENGTHS = (1e5, 1e6)
CONFIGURATIONS = [
    dict(name='unswept-offset', sweep=0., dihedral=0., alpha=5., offset=3., mach=.6, frozen=False),
    dict(name='swept-negative', sweep=40., dihedral=0., alpha=-4., offset=-2., mach=.6, frozen=False),
    dict(name='forward-sweep-dihedral', sweep=-35., dihedral=35., alpha=4., offset=-3., mach=.3, frozen=False),
    dict(name='swept-frozen', sweep=40., dihedral=0., alpha=6., offset=3., mach=.6, frozen=True),
]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def leakage(cl):
    def softplus(x):
        return max(x, 0.) + math.log1p(math.exp(-abs(x)))
    return WIDTH * (softplus((cl-UPPER)/WIDTH) - softplus((LOWER-cl)/WIDTH))


def geometry(config):
    sweep, dihedral, alpha, offset = map(math.radians,
        [config['sweep'], config['dihedral'], config['alpha'], config['offset']])
    s = np.array([math.sin(sweep), math.cos(sweep)*math.cos(dihedral), math.cos(sweep)*math.sin(dihedral)])
    c = np.array([math.cos(sweep), -math.sin(sweep)*math.cos(dihedral), -math.sin(sweep)*math.sin(dihedral)])
    n = np.array([0., -math.sin(dihedral), math.cos(dihedral)])
    e = np.array([math.cos(alpha), 0., math.sin(alpha)])
    w = np.array([1., 0., 0.]) if config['frozen'] else e
    return s, e, w, c*math.sin(offset)+n*math.cos(offset)


def oracle(config, cl):
    s, e, w, ncp = geometry(config)
    ke = np.linalg.norm(np.cross(e, s))
    kw = np.linalg.norm(np.cross(w, s))
    ell = np.cross(w, s)/kw
    beta_normal = math.sqrt(1-config['mach']**2*kw**2)
    gamma = cl*CHORD*SPEED*ke/2
    cp_velocity = SPEED*e - gamma*beta_normal/(2*math.pi*(SLOPE/(4*math.pi))*CHORD)*ell
    signed_residual = cp_velocity@ncp/SPEED - ke/SLOPE*FACTOR*leakage(cl)
    return dict(gamma=float(gamma), cl=cl, normal_speed=float(SPEED*ke),
                relative_velocity=(SPEED*e).tolist(), residual=float(signed_residual),
                normal_pg_factor=beta_normal, normal_cp_velocity=float(cp_velocity@ncp))


def source(config, length):
    s, _, _, _ = geometry(config)
    positions = [' '.join(f'{v:.17g}' for v in t*s) for t in (-length/2, length/2)]
    return f'''Name
Independent infinite swept-wing limit
End
Unit
L 1 m
T 1 s
F 1 N
End
Constant
9.81 1.2256 340.21
End
Reference
{length*CHORD:.17g} {CHORD} {length}
End
Ground
1 0 0
End
Beam 1
Constant straight lifting beam
t x y z chord Xax
{-length/2} {positions[0]} {CHORD} 0
{length/2} {positions[1]} {CHORD} 0
t alpha dCLda CLmin CLmax Cdf Cdp
{-length/2} {config['offset']} {SLOPE} {LOWER} {UPPER} .0035 .0077
{length/2} {config['offset']} {SLOPE} {LOWER} {UPPER} .0035 .0077
End
'''


def evaluate(config, cl, length):
    reference = oracle(config, cl)
    model = parse_asw(source(config, length))
    assert not model.diagnostics, model.diagnostics
    meshes = model_meshes(model, 16)
    assert len(meshes) == 1 and len(meshes[0].tm) == 16
    condition = FlightCondition(speed=SPEED, alpha=config['alpha'], mach=config['mach'],
        density=1.2256, freeze_influences=config['frozen'], stall_factor=FACTOR, stall_width=WIDTH)
    result = evaluate_aerodynamics(model, condition, meshes,
        circulation=np.full(16, reference['gamma']))
    center = np.flatnonzero(np.abs(meshes[0].tm) < .1*length)
    assert len(center) >= 2
    errors = {}
    samples = []
    for i in center:
        strip = result['strips'][i]
        actual = dict(cl=strip['cl'], normal_speed=strip['normal_speed'],
            relative_velocity=strip['relative_velocity'], residual=result['circulation_local_residual'][i])
        for name, value in actual.items():
            expected = np.asarray(reference[name])
            error = float(np.max(np.abs(np.asarray(value)-expected)/(1+np.abs(expected))))
            errors[name] = max(errors.get(name, 0.), error)
        samples.append(dict(index=int(i), t=strip['t'], actual=actual))
    return dict(length=length, intervals=16, center_samples=samples, scaled_errors=errors,
        maximum_scaled_error=max(errors.values()), equilibrium=result['converged'],
        maximum_physical_residual=result['residual'], solver=result['circulation_solver'],
        max_normal_mach=max(s['normal_mach'] for s in result['strips']))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    folder = args.output_dir
    folder.mkdir(parents=True, exist_ok=True)
    if (folder/'protocol.json').exists():
        raise SystemExit('Use a fresh output directory to preserve the original witness.')
    started = time.monotonic()
    pins = {str(p.relative_to(ROOT)):digest(p) for p in sorted((ROOT/'openswing').glob('*.py'))}
    pins[str(Path(__file__).relative_to(ROOT))] = digest(Path(__file__))
    for name in ('.reference/asw_theory.pdf', '.reference/asw_theory.txt'):
        if (ROOT/name).exists():
            pins[name] = digest(ROOT/name)
    protocol = dict(scope=__doc__, configurations=CONFIGURATIONS, section_cl=[-1.25,.35,1.45],
        lengths=LENGTHS, intervals=16, prescribed_evaluations=24, nonlinear_solves=0,
        properties=dict(chord=CHORD,speed=SPEED,slope=SLOPE,lower=LOWER,upper=UPPER,width=WIDTH,factor=FACTOR),
        gates=dict(fine_maximum_scaled_error=1e-4, fine_to_coarse_error_ratio=.2), source_sha256=pins,
        qualifications=['Synthetic constant-property states; parameters are not fitted to ISAE.',
            'Finite-tip effects are retained and checked by length refinement.',
            'Fixed PG Mach and actual speed are independent settings.',
            'These prescribed circulation states generally have nonzero residual and are not equilibria.'])
    save(folder/'protocol.json', protocol)
    rows = []
    for config in CONFIGURATIONS:
        for cl in protocol['section_cl']:
            pair = [evaluate(config, cl, length) for length in LENGTHS]
            ratio = pair[1]['maximum_scaled_error']/pair[0]['maximum_scaled_error']
            passed = pair[1]['maximum_scaled_error'] <= 1e-4 and ratio <= .2
            row = dict(configuration=config, prescribed_cl=cl, oracle=oracle(config,cl),
                       evaluations=pair, fine_to_coarse_ratio=ratio, passed=passed)
            rows.append(row)
            save(folder/f'state-{len(rows):02d}.json', row)
            print(f'{config["name"]}, cl={cl:g}: fine error {pair[1]["maximum_scaled_error"]:.6g}, ratio {ratio:.6g}, pass={passed}', flush=True)
    assert all(digest(ROOT/path) == sha for path, sha in pins.items())
    report = dict(status='complete', all_passed=all(row['passed'] for row in rows),
        states=rows, maximum_fine_error=max(r['evaluations'][1]['maximum_scaled_error'] for r in rows),
        maximum_refinement_ratio=max(r['fine_to_coarse_ratio'] for r in rows),
        prescribed_evaluations=24, nonlinear_solves=0, source_pins_unchanged=True,
        elapsed_seconds=time.monotonic()-started)
    save(folder/'report.json', report)
    if not report['all_passed']:
        raise SystemExit('At least one predeclared infinite-wing limit gate failed; see report.json.')


if __name__ == '__main__':
    main()
