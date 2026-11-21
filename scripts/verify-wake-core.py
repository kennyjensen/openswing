"""K/W validation using independent regularized vortex-line quadrature.

The reference constructs the two rectangular surfaces analytically and does not
use the production mesh, influence kernels or circulation solver.
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
from scipy.integrate import quad_vec
from openswing.aero import FlightCondition, solve_rigid, evaluate_aerodynamics
from openswing.asw import parse_asw
from openswing.geometry import model_meshes

# span, chord, x, z, section incidence [degrees]; all dimensions below are SI.
WINGS = [(2., 2., 0., 1., 3.), (1.5, .6, 3., 1.05, 1.)]
POINTS = np.array([[3., 0., 1.08], [3., .3, 1.05], [7., .2, 1.02]])


def source(spec):
    L, T, F = spec.get('units', [1., 1., 1.])
    s = ('! Original OpenSwing interacting-surface verification model.\n'
         'Name\nClose wake encounter\nEnd\nUnit\n'
         f'L {L:.17g} m\nT {T:.17g} s\nF {F:.17g} N\nEnd\nConstant\n'
         f'{9.80665*T*T/L:.17g} {1.225*L**4/(F*T*T):.17g} {340.294*T/L:.17g}\nEnd\n'
         f'Reference\n{4.9/L**2:.17g} {2/L:.17g} {2/L:.17g}\n0 0 0\nEnd\n'
         'Ground\n1 0 0\n2 0 0\nEnd\n'
         f'Sensor\n1 1 0 {3/L:.17g} 0 {1.08/L:.17g}\nEnd\n')
    for i, (span, chord, x, z, incidence) in enumerate(WINGS, 1):
        s += f'Beam {i} {i}\nSurface {i}\nt x y z chord Xax alpha\n'
        for y in [0, span/2]:
            s += f'{y/L:.17g} {x/L:.17g} {y/L:.17g} {z/L:.17g} {chord/L:.17g} .25 {incidence}\n'
        s += 't Cdf dCLda CLmax CLmin\n'
        for y in [0, span/2]:
            s += f'{y/L:.17g} 0 {2*np.pi:.17g} 100 -100\n'
        s += 'End\n'
    return s


def geometry(panels):
    a, b, h, n, chord, physical = [], [], [], [], [], []
    for i, (span, c, x, z, incidence) in enumerate(WINGS):
        edges = -span/2*np.cos(np.arange(panels+1)*np.pi/panels)
        centers = -span/2*np.cos((np.arange(panels)+.5)*np.pi/panels)
        a.extend([[x, y, z] for y in edges[:-1]])
        b.extend([[x, y, z] for y in edges[1:]])
        h.extend([[x, y, z] for y in centers])
        n.extend([[np.sin(np.deg2rad(incidence)), 0, np.cos(np.deg2rad(incidence))]]*panels)
        chord.extend([c]*panels); physical.extend([i]*panels)
    a, b, h, n, chord, physical = map(np.asarray, (a, b, h, n, chord, physical))
    return a, b, h, n, chord, physical


def independent(spec):
    a, b, h, normal, chord, physical = geometry(spec['panels'])
    ds = b[:, 1]-a[:, 1]
    core = np.maximum(spec['ratio']*chord, ds)
    pg = np.diag([1/np.sqrt(1-spec.get('mach', 0.)**2), 1., 1.])
    cp = h + np.column_stack([chord/2, np.zeros((len(chord), 2))])

    def field(points, target=None, force=False):
        radii = np.broadcast_to(core, (len(points), len(core))).copy()
        same = None if target is None else target[:, None] == physical[None, :]
        if same is not None: radii[same] = 0
        pts = points@pg.T

        def line(start, direction, upper, omit=None):
            start = start@pg.T; direction = direction@pg.T
            def integrand(t):
                r = pts[:, None, :] - start[None, :, :] - t*direction[None, :, :]
                den = (np.sum(r*r, axis=-1)+radii*radii)**1.5
                numer = np.cross(direction[None, :, :], r)
                value = np.divide(numer, den[..., None], out=np.zeros_like(numer), where=den[..., None]>0)/(4*np.pi)
                if omit is not None: value[omit] = 0
                return value
            return quad_vec(integrand, 0, upper, epsabs=2e-12, epsrel=2e-12)[0]@pg

        wake = np.tile([1., 0, 0], (len(a), 1))
        value = line(a, b-a, 1, same if force else None)+line(b, wake, np.inf)-line(a, wake, np.inf)
        flag = spec.get('ground', 0)
        if flag:
            ia = a.copy(); ib = b.copy(); ia[:, 2] *= -1; ib[:, 2] *= -1
            value -= flag*(line(ia, ib-ia, 1)+line(ib, wake, np.inf)-line(ia, wake, np.inf))
        return value

    matrix = np.einsum('ijk,ik->ij', field(cp, physical), normal)
    gamma = np.linalg.solve(matrix, -30*normal[:, 0])
    velocity = [30., 0, 0]+np.einsum('ijk,j->ik', field(h, physical, force=True), gamma)
    forces = 1.225*gamma[:, None]*np.cross(velocity, [0, 1, 0])*ds[:, None]
    return dict(gamma=gamma.tolist(), force=forces.sum(axis=0).tolist(),
        field=np.einsum('ijk,j->ik', field(POINTS), gamma).tolist(), core=core.tolist())


def compute(spec):
    L, T, F = spec.get('units', [1., 1., 1.])
    model = parse_asw(source(spec))
    c = FlightCondition(speed=30*T/L, alpha=0, mach=spec.get('mach', 0.), stall=False,
        wake_core_ratio=spec['ratio'], ground_effect=spec.get('ground', 0))
    out = solve_rigid(model, c, spec['panels'])
    assert out['converged'] and out['residual'] < 1e-10
    meshes = model_meshes(model, spec['panels'])
    probed = evaluate_aerodynamics(model, c, meshes,
        circulation=[s['circulation'] for s in out['strips']], survey_positions=POINTS/L)
    sensor = np.array(probed['sensor_airflow'][0]['induced_velocity'])*L/T
    velocity = np.array(probed['flow_survey']['velocity_body']['lifting'])*L/T
    np.testing.assert_allclose(sensor, velocity[0], atol=2e-12)
    return dict(gamma=(np.array([s['circulation'] for s in out['strips']])*L*L/T).tolist(),
        force=(np.array(out['force'])*F).tolist(), field=velocity.tolist(),
        core=(np.array([s['wake_core_radius'] for s in out['strips']])*L).tolist(),
        metadata=out['wake_core'])


def physical(result):
    return np.concatenate([np.asarray(result[k]).ravel() for k in ('gamma', 'force', 'field', 'core')])


def main():
    files = sorted((ROOT/'openswing').glob('*.py'))+[Path(__file__), ROOT/'examples/wake-interaction.asw']
    hashes = lambda: {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    before = hashes()
    specs = [dict(panels=n, ratio=r) for n in [4, 8, 16] for r in [0., .25, 1.]]
    specs += [dict(panels=8, ratio=r, mach=.6, ground=g) for r in [.25, 1.] for g in [-1, 1]]
    specs += [dict(panels=8, ratio=.25, mach=.6, ground=1, units=u) for u in [[.01, .2, 7.], [100, 3, .02]]]
    cases = []
    for i, spec in enumerate(specs):
        reference = independent(spec); actual = compute(spec)
        error = float(np.max(abs(physical(actual)-physical(reference))/np.maximum(1., abs(physical(reference)))))
        assert error < 3e-10, (spec, error)
        cases.append(dict(name=f'case_{i}', specification=spec, reference=reference, result=actual, maximum_scaled_reference_error=error))
        print(spec, error, flush=True)
    assert before == hashes(), 'Study sources changed during verification.'
    out = dict(description=__doc__, python=platform.python_version(), numpy=np.__version__, scipy=scipy.__version__, source_sha256=before, cases=cases)
    (ROOT/'docs/validation/wake-core.json').write_text(json.dumps(out, indent=2)+'\n')
    print('All independent wake-core cases passed.', flush=True)


if __name__ == '__main__': main()
