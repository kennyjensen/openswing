"""Independent line-integral diagnosis of the archived SA-2 tip-velocity limit.

Circulation is taken from a low-speed solve at fixed PG Mach 0. The velocity
integral uses literal geometry and independent quadrature, not production vortex
kernels. Speed scaling diagnoses the rejected 49.9 m/s cases; it does not accept
them or change the physical validity guard.
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
from scipy.integrate import quad, quad_vec
from openswing.asw import parse_asw
from openswing.aero import FlightCondition, solve_rigid


def probe(source, panels, frozen):
    model = parse_asw(source)
    alpha = np.deg2rad(10.5)
    wind = np.array([np.cos(alpha), 0., np.sin(alpha)])
    influence = np.array([1., 0., 0.]) if frozen else wind
    direction = np.array([.8801, 1.2446, 0.])/np.hypot(.8801, 1.2446)
    crosswind = np.linalg.norm(np.cross(influence, direction))
    edges = -1.2446*np.cos(np.arange(panels+1)*np.pi/panels)
    centers = -1.2446*np.cos((np.arange(panels)+.5)*np.pi/panels)
    offset = .25*.508/crosswind*influence
    nodes = np.column_stack([np.abs(edges)*.8801/1.2446, edges, np.zeros_like(edges)])+offset
    point = np.array([abs(centers[-1])*.8801/1.2446, centers[-1], 0.])+offset
    result = solve_rigid(model, FlightCondition(speed=.499, density=1.2256, alpha=10.5,
                                              mach=0., freeze_influences=frozen), panels)
    gamma = np.array([s['circulation'] for s in result['strips']])
    assert gamma.shape == (panels,)
    assert np.max(abs(np.array([s['t'] for s in result['strips']])-centers)) < 2e-13
    # Consecutive trailing legs combine into nodal strength jumps. Integrate
    # each ray after scaling its closest-approach distance to unity.
    jumps = np.r_[-gamma[0], gamma[:-1]-gamma[1:], gamma[-1]]
    wake = np.zeros(3)
    for node, strength in zip(nodes, jumps):
        r = point-node
        z = r@influence
        perpendicular = r-z*influence
        h = np.linalg.norm(perpendicular)
        integral, error = quad(lambda w: (1+w*w)**(-1.5), -z/h, np.inf, epsabs=1e-12, epsrel=1e-12)
        assert error < 1e-10
        wake += strength*np.cross(influence, r)/h**2*integral/(4*np.pi)
    # On this straight right half, every bound segment is collinear with the
    # receiver and has zero principal-value velocity. Only the left half enters.
    start, delta = nodes[:panels//2], np.diff(nodes, axis=0)[:panels//2]
    def integrand(fraction):
        r = point-start-fraction*delta
        return np.sum(gamma[:panels//2, None]*np.cross(delta, r)/np.linalg.norm(r, axis=1)[:, None]**3, axis=0)/(4*np.pi)
    bound, error = quad_vec(integrand, 0., 1., epsabs=1e-12, epsrel=1e-12)
    assert error < 1e-10
    velocity = .499*wind+wake+bound
    normal_velocity = velocity-(velocity@direction)*direction
    speed = np.linalg.norm(normal_velocity)
    strip = result['strips'][-1]
    production_speed = 2*strip['circulation']/(.508*strip['cl'])
    difference = abs(speed-production_speed)
    assert difference < 2e-8, (panels, frozen, speed, production_speed)
    return dict(panels=panels, frozen=frozen, alpha_deg=10.5, diagnostic_speed=.499,
                original_speed=49.9, fixed_pg_mach=0., tip_t=float(centers[-1]),
                tip_distance=float(1.2446-centers[-1]), gamma_tail=gamma[-5:].tolist(),
                independent_velocity=velocity.tolist(), independent_bound=bound.tolist(),
                independent_wake=wake.tolist(), independent_normal_speed=float(speed),
                production_normal_speed=float(production_speed), absolute_speed_error=float(difference),
                inferred_original_speed_tip_Mach=float(100*speed/340.21),
                coefficients_at_diagnostic_speed={k:float(result[k]) for k in ['CL', 'CD', 'CDi', 'Cm']})


def main():
    source_path = ROOT/'.reference/isae-sa2/SA_2.asw'
    source = source_path.read_text()
    manifest = json.loads((ROOT/'docs/validation/sa2-sources.json').read_text())
    assert hashlib.sha256(source_path.read_bytes()).hexdigest() == manifest['files']['SA_2.asw']['sha256']
    cases = []
    for frozen in [False, True]:
        for panels in [100, 200, 400, 512]:
            result = probe(source, panels, frozen)
            cases.append(result)
            print('tip', panels, frozen, result['inferred_original_speed_tip_Mach'], result['absolute_speed_error'], flush=True)
    hashes = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in [Path(__file__), ROOT/'docs/validation/sa2-sources.json', *sorted((ROOT/'openswing').glob('*.py'))]}
    out = dict(description=__doc__, source_sha256=hashes, cases=cases,
               versions=dict(python=platform.python_version(), numpy=np.__version__, scipy=scipy.__version__),
               limitations=['This checks induced velocity for computed circulation; it is not an independent circulation solution.',
                            'The original-speed Mach follows fixed-PG velocity scaling. No rejected original-speed result is relabelled valid.',
                            'The growing tip velocity is reproduced by independent line integration. A physically justified tip/discretization treatment and ASWING comparison remain open.'])
    (ROOT/'docs/validation/sa2-tip.json').write_text(json.dumps(out,indent=2,allow_nan=False)+'\n')


if __name__ == '__main__':
    main()
