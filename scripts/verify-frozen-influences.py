"""Independent K/F study: integrate vortex lines, then solve physical tangency.

The reference does not call the production mesher, vortex kernel, circulation
solver or frozen-coefficient cache. Surface rotations/stretch and the actual
wind enter the physical equations while both ends of influence coefficients
stay on the undeformed material geometry.
"""
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import runpy
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import numpy as np
from scipy.integrate import quad_vec
from scipy.spatial.transform import Rotation
from openswing.aero import FlightCondition, evaluate_aerodynamics
from openswing.asw import parse_asw
from openswing.geometry import model_meshes

WAKE = runpy.run_path(str(ROOT/'scripts/verify-wake-core.py'))
POINTS = WAKE['POINTS']
WINGS = WAKE['WINGS']
source = WAKE['source']


def rotations(spec):
    return [Rotation.from_rotvec(v).as_matrix() for v in spec.get('rotations', [[0., 0., 0.]]*2)]


def reference(spec, details=False):
    a, b, h, normal, chord, owner = WAKE['geometry'](spec['panels'])
    ds = b[:, 1]-a[:, 1]
    core = np.maximum(spec.get('ratio', .25)*chord, ds)
    pg = np.diag([1/np.sqrt(1-spec.get('mach', 0.)**2), 1., 1.])
    cp = h+np.column_stack([chord/2, np.zeros((len(chord), 2))])
    def field(points, physical=None, force=False):
        radii = np.broadcast_to(core, (len(points), len(core))).copy()
        if physical is not None:
            radii[physical[:, None] == owner[None, :]] = 0
        points = points@pg.T
        def line(start, direction, upper, omit=False):
            start, direction = start@pg.T, direction@pg.T
            def integrand(t):
                delta = points[:, None, :]-start[None, :, :]-t*direction[None, :, :]
                den = (np.sum(delta*delta, axis=-1)+radii*radii)**1.5
                value = np.divide(np.cross(direction[None, :, :], delta), den[..., None],
                                  out=np.zeros_like(delta), where=den[..., None]>0)/(4*np.pi)
                if omit:
                    value[np.eye(len(a), dtype=bool)] = 0
                return value
            return quad_vec(integrand, 0, upper, epsabs=2e-12, epsrel=2e-12)[0]@pg
        wake = np.tile([1., 0., 0.], (len(a), 1))
        value = line(a, b-a, 1, force)+line(b, wake, np.inf)-line(a, wake, np.inf)
        flag = spec.get('ground', 0)
        if flag:
            ia, ib = a.copy(), b.copy()
            ia[:, 2] *= -1; ib[:, 2] *= -1
            value -= flag*(line(ia, ib-ia, 1)+line(ib, wake, np.inf)-line(ia, wake, np.inf))
        return value
    q = rotations(spec)
    spans = np.array([[0., 1., 0.]@r.T for r in q])[owner]
    normal = np.einsum('nij,nj->ni', np.array(q)[owner], normal)
    stretches = np.array(spec.get('stretches', [1., 1.]))[owner]
    alpha, beta = np.deg2rad([spec.get('alpha', 8.), spec.get('beta', 4.)])
    wind = np.array([np.cos(alpha)*np.cos(beta), -np.sin(beta), np.sin(alpha)*np.cos(beta)])
    cp_matrix, hv_matrix = field(cp, owner), field(h, owner, True)
    matrix = np.einsum('ijk,ik->ij', cp_matrix, normal)
    gamma = np.linalg.solve(matrix, -spec.get('speed', 30.)*(normal@wind))
    velocity = spec.get('speed', 30.)*wind+np.einsum('ijk,j->ik', hv_matrix, gamma)
    forces = 1.225*gamma[:, None]*np.cross(velocity, spans)*(ds*stretches)[:, None]
    result = dict(gamma=gamma.tolist(), force=forces.sum(axis=0).tolist(),
                  field=np.einsum('ijk,j->ik', field(POINTS), gamma).tolist(), core=core.tolist())
    if details:
        return result, dict(matrix=matrix, hv_matrix=hv_matrix, velocity=velocity,
                            normal=normal, spans=spans, chord=chord, length=ds*stretches)
    return result


def setup(spec):
    L, T, F = spec.get('units', [1., 1., 1.])
    model = parse_asw(source(spec))
    condition = FlightCondition(speed=spec.get('speed', 30.)*T/L, alpha=spec.get('alpha', 8.), beta=spec.get('beta', 4.),
        mach=spec.get('mach', 0.), stall=False, freeze_influences=True,
        wake_core_ratio=spec.get('ratio', .25), ground_effect=spec.get('ground', 0))
    meshes = model_meshes(model, spec['panels'])
    deformed = []
    for i, (mesh, rotation) in enumerate(zip(meshes, rotations(spec))):
        pivot = np.array([WINGS[i][2], 0., WINGS[i][3]])/L
        shift = np.asarray(spec.get('shifts', [[0., 0., 0.]]*2)[i])/L
        stretch = spec.get('stretches', [1., 1.])[i]
        transform = lambda r: (r-pivot)*stretch@rotation.T+pivot+shift
        deformed.append(replace(mesh, r0=transform(mesh.r0), r1=transform(mesh.r1), rm=transform(mesh.rm),
                                frames=rotation@mesh.frames, length=stretch*mesh.length,
                                frame0=np.broadcast_to(rotation, (len(mesh.tm), 3, 3)),
                                frame1=np.broadcast_to(rotation, (len(mesh.tm), 3, 3))))
    return model, condition, deformed


def compute(spec):
    L, T, F = spec.get('units', [1., 1., 1.])
    model, condition, meshes = setup(spec)
    out = evaluate_aerodynamics(model, condition, meshes, survey_positions=POINTS/L)
    assert out['converged'] and out['residual'] < 1e-10
    return dict(gamma=(np.array([s['circulation'] for s in out['strips']])*L*L/T).tolist(),
                force=(np.array(out['force'])*F).tolist(),
                field=(np.array(out['flow_survey']['velocity_body']['lifting'])*L/T).tolist(),
                core=(np.array([s['wake_core_radius'] for s in out['strips']])*L).tolist(),
                metadata=out['aerodynamic_influences'])


def physical(result):
    return np.concatenate([np.asarray(result[k]).ravel() for k in ('gamma', 'force', 'field', 'core')])


def main():
    files = sorted((ROOT/'openswing').glob('*.py'))+[Path(__file__), ROOT/'scripts/verify-wake-core.py']
    hashes = lambda: {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    before = hashes()
    deformation = dict(rotations=[[.12, -.18, .06], [-.15, .11, -.04]], stretches=[1.2, .9], shifts=[[.1, 0, .2], [-.1, .1, .1]])
    specs = [dict(panels=n, **d) for n in [4, 8, 16] for d in [{}, deformation]]
    specs += [dict(panels=8, mach=.6, ground=g, **deformation) for g in [-1, 1]]
    specs += [dict(panels=8, alpha=-12., beta=-9., ratio=1., **deformation)]
    specs += [dict(panels=8, mach=.6, ground=1, units=u, **deformation) for u in [[.01, .2, 7.], [100., 3., .02]]]
    cases = []
    for i, spec in enumerate(specs):
        expected, actual = reference(spec), compute(spec)
        error = float(np.max(abs(physical(actual)-physical(expected))/np.maximum(1., abs(physical(expected)))))
        assert error < 3e-10, (spec, error)
        cases.append(dict(name=f'case_{i}', specification=spec, reference=expected, result=actual, maximum_scaled_reference_error=error))
        print(spec, error, flush=True)
    assert hashes() == before, 'Sources changed during verification.'
    (ROOT/'docs/validation/frozen-influences.json').write_text(json.dumps(dict(description=__doc__, source_sha256=before, cases=cases), indent=2)+'\n')


if __name__ == '__main__':
    main()
