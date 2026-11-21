"""Audit the zero-core swept lifting-line limit without changing the solver.

Prescribed elliptic circulation removes the circulation solve from the test.
An independent nodal-jump formula and numerical line integration test the
documented horseshoe field. Cutoff integrals diagnose a singular limit; they
are not regularized production solutions or a proposed core-size choice.
"""
from pathlib import Path
import hashlib
import json
import platform
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import numpy as np
import scipy
from scipy.integrate import quad, quad_vec
from openswing.aero import horseshoe_velocity, solve_rigid, FlightCondition, AnalysisError
from openswing.asw import parse_asw
from openswing.geometry import model_meshes
from openswing.frozen_influence import lifting_geometry


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def exact_ray_integral(point, origin, direction):
    """Adaptive integration of an infinite ray after distance rescaling."""
    r = point-origin
    z = r@direction
    perpendicular = r-z*direction
    h = np.linalg.norm(perpendicular)
    assert h > 0
    integral, error = quad(lambda u: (1+u*u)**-1.5, -z/h, np.inf,
                           epsabs=2e-12, epsrel=2e-12)
    assert error < 1e-10
    return np.cross(direction, r)/h**2*integral/(4*np.pi)


def prescribed(sweep, n):
    nodes = -np.cos(np.arange(n+1)*np.pi/n)
    y = -np.cos((np.arange(n)+.5)*np.pi/n)
    gamma = np.sin((np.arange(n)+.5)*np.pi/n)
    slope = np.tan(np.deg2rad(sweep))
    endpoints = np.column_stack([slope*nodes, nodes, np.zeros(n+1)])
    points = np.column_stack([slope*y, y, np.zeros(n)])
    jumps = np.r_[-gamma[0], gamma[:-1]-gamma[1:], gamma[-1]]
    delta = y[:, None]-nodes
    # For x=y*tan(sweep), a wind-aligned ray's z velocity is
    # (1 + sin(sweep)*sign(delta_y))/(4*pi*delta_y).
    odd = (1/delta)@jumps/(4*np.pi)
    even = (np.sin(np.deg2rad(sweep))/abs(delta))@jumps/(4*np.pi)
    independent = odd+even
    production = np.einsum('ijk,j->ik', horseshoe_velocity(
        points[:, None, :], endpoints[None, :-1, :], endpoints[None, 1:, :],
        np.array([1., 0., 0.]), np.eye(3), 0.,
        exclude_bound=np.eye(n, dtype=bool)), gamma)
    error = float(np.max(abs(production[:, 2]-independent)))
    assert error < 2e-7, (sweep, n, error)
    assert np.max(abs(production[:, :2])) < 1e-12
    # The unswept discrete cosine-grid result has this exact finite-N factor.
    exact_discrete = -.25*np.sinc(1/(2*n))
    assert np.max(abs(odd-exact_discrete)) < 2e-8
    i = int(np.argmin(abs(y-.5)))
    indices = [i, n-1]
    quadrature = []
    if n == 50:
        for j in indices:
            wake = sum((strength*exact_ray_integral(points[j], origin, np.array([1., 0., 0.]))
                        for strength, origin in zip(jumps, endpoints)), start=np.zeros(3))
            diff = float(np.max(abs(wake-production[j])))
            assert diff < 2e-9
            quadrature.append(dict(index=j, velocity=wake.tolist(), maximum_component_error=diff))
    return dict(sweep_deg=sweep, panels=n, maximum_production_difference=error,
        analytic_unswept_limit=-.25, analytic_unswept_discrete=exact_discrete,
        maximum_unswept_limit_error=float(np.max(abs(odd+.25))),
        samples=[dict(index=j, y=float(y[j]), circulation=float(gamma[j]),
            span_distance_to_tip=float(1-y[j]), odd_kernel=float(odd[j]),
            sweep_even_kernel=float(even[j]), velocity=production[j].tolist()) for j in indices],
        ray_quadrature=quadrature)


def cutoff_integral(sweep, y, cutoff):
    """Symmetric spanwise exclusion around the field point, not a core."""
    s = np.sin(np.deg2rad(sweep))
    limits = [(-np.pi/2, np.arcsin(y-cutoff)), (np.arcsin(y+cutoff), np.pi/2)]
    # eta=sin(theta) removes the integrable endpoint singularities of Gamma'.
    def f(theta):
        eta = np.sin(theta)
        return np.array([eta/(y-eta), s*eta/abs(y-eta)])/(4*np.pi)
    value = np.zeros(2)
    for lower, upper in limits:
        part, err = quad_vec(f, lower, upper, epsabs=2e-10, epsrel=2e-10)
        assert err < 1e-7
        value += part
    return dict(sweep_deg=sweep, y=y, cutoff=cutoff,
        odd_kernel=float(value[0]), sweep_even_kernel=float(value[1]), total=float(sum(value)),
        expected_logarithmic_slope=float(s*y/(2*np.pi*np.sqrt(1-y*y))))


def sa14_check(row, source):
    q = row['specification']
    assert q['case'] == 'wing_only' and q['pg'] == 'zero' and q['alpha'] == 12.9
    model = parse_asw(source)
    meshes = model_meshes(model, q['panels'])
    a = np.deg2rad(q['alpha']); direction = np.array([np.cos(a), 0., np.sin(a)])
    geometry = lifting_geometry(meshes, direction)
    # Shared geometry is explicit: this independently checks the field, not
    # the geometry interpolation or the circulation solution.
    profiles = row['result']['profiles']
    gamma = np.array([p['circulation'] for p in profiles])
    assert np.allclose([p['t'] for p in profiles], np.concatenate([m.tm for m in meshes]))
    assert len(model.beams) == 1 and model.beams[0].lifting
    indices = sorted(set([0, len(profiles)-1, int(np.argmin(abs(np.array([p['normalized_y'] for p in profiles])-.5)))]))
    checks = []
    for i in indices:
        point = geometry['hv'][i]
        wake = np.zeros(3)
        for j, strength in enumerate(gamma):
            wake += strength*(exact_ray_integral(point, geometry['b'][j], direction)
                              -exact_ray_integral(point, geometry['a'][j], direction))
        delta = geometry['b']-geometry['a']
        cross = np.cross(delta, point-geometry['a'])*gamma[:, None]
        cross[i] = 0.  # documented bound-filament principal-value omission
        def integrand(fraction):
            r = point-geometry['a']-fraction*delta
            norm = np.linalg.norm(r, axis=1)
            norm[i] = 1.
            return np.sum(cross/norm[:, None]**3, axis=0)/(4*np.pi)
        bound, err = quad_vec(integrand, 0., 1., epsabs=2e-9, epsrel=2e-10)
        assert err < 1e-6, (q, i, err)
        velocity = 70*direction+wake+bound
        observed = np.array(profiles[i]['relative_velocity'])
        error = float(np.max(abs(velocity-observed)))
        assert error < 2e-6, (q, i, error)
        checks.append(dict(index=i, t=profiles[i]['t'], normalized_y=profiles[i]['normalized_y'],
            gamma=float(gamma[i]), force_point=point.tolist(),
            independent_wake=wake.tolist(), independent_bound=bound.tolist(),
            independent_velocity=velocity.tolist(), production_velocity=observed.tolist(),
            maximum_component_error=error, normal_mach=profiles[i]['normal_mach']))
    return dict(specification=q, source_cache=row['cache_path'], source_cache_sha256=row['cache_sha256'], samples=checks)


def main():
    inputs = [Path(__file__), ROOT/'.reference/asw_theory.pdf', ROOT/'.reference/aswing_doc.txt',
              ROOT/'docs/validation/isae-sa14-sources.json', ROOT/'docs/validation/isae-sa14-pilot.json']
    pins = {p.relative_to(ROOT).as_posix():sha(p) for p in inputs+sorted((ROOT/'openswing').glob('*.py'))}
    prescribed_cases = []
    for sweep in [0., 45.]:
        for n in [25, 50, 100, 200, 400]:
            case = prescribed(sweep, n); prescribed_cases.append(case)
            print('prescribed', sweep, n, case['samples'][-1]['velocity'], flush=True)
    integrals = [cutoff_integral(sweep, .5, cutoff)
                 for sweep in [0., 45.] for cutoff in [1e-2, 1e-3, 1e-4, 1e-5, 1e-6]]
    swept = [r for r in integrals if r['sweep_deg'] == 45.]
    slope = (swept[-1]['sweep_even_kernel']-swept[-2]['sweep_even_kernel'])/np.log(10)
    assert abs(slope-swept[-1]['expected_logarithmic_slope']) < 2e-8
    assert abs(integrals[-1]['odd_kernel']+.25) < 1e-6
    sources = json.loads((ROOT/'docs/validation/isae-sa14-sources.json').read_text())
    native = json.loads((ROOT/'docs/validation/isae-sa14-pilot.json').read_text())
    source = next(m['source'] for m in sources['models'] if m['name']=='wing_only')
    actual = []
    for row in native['rows']:
        q = row['specification']
        if q['case']=='wing_only' and q['alpha']==12.9 and q['pg']=='zero':
            assert sha(ROOT/row['cache_path'])==row['cache_sha256']
            case=sa14_check(row,source); actual.append(case)
            print('SA14',q['panels'],max(p['maximum_component_error'] for p in case['samples']),flush=True)
    assert len(actual)==3
    refinements=[]
    for n in [200,400]:
        try:
            result=solve_rigid(parse_asw(source),FlightCondition(speed=70.,alpha=12.9,mach=0.),n)
            entry=dict(panels=n,status='computed',residual=result['residual'],
                maximum_normal_mach=max(s['normal_mach'] for s in result['strips']))
        except AnalysisError as exc:
            entry=dict(panels=n,status='rejected',error=str(exc),details=exc.details)
        refinements.append(entry)
        print('SA14 refinement',n,entry['status'],flush=True)
    assert pins == {name:sha(ROOT/name) for name in pins}
    report = dict(status='PASS_FIELD_DIAGNOSIS_UNRESOLVED_SWEPT_FORCE_VELOCITY_LIMIT',
        source_sha256=pins, versions=dict(python=platform.python_version(),numpy=np.__version__,scipy=scipy.__version__),
        source=dict(url='https://web.mit.edu/drela/Public/web/aswing/asw_theory.pdf',
            sections=['3.1: eqs62-67, circulation and force velocity at bound vortex',
                      '4.2: eqs150-161, sampled horseshoes and same-surface zero core',
                      '5.6: eqs200-201, control-point tangency and Fourier test functions']),
        prescribed=dict(units='m and s; semispan1m, Gamma0=1m^2/s, PG Mach0, no ambient velocity',
            geometry='Straight bound line (y*tan(sweep),y,0), wind-aligned +x wakes, zero core.',
            circulation='Gamma(y)=sqrt(1-y^2), sampled at theta midpoints. No circulation equation is solved.',
            cases=prescribed_cases), cutoff_integrals=integrals, observed_logarithmic_slope=float(slope),
        sa14_independent_field=actual, sa14_original_speed_refinement=refinements,
        conclusions=[
            'The unswept prescribed elliptic case converges to exact uniform downwash -Gamma0/(4*semispan).',
            'For nonzero sweep, the same smooth prescribed circulation produces a logarithmically divergent same-line wake velocity at fixed interior y where Gamma derivative is nonzero. Tip-midpoint velocities also grow with refinement.',
            'The nodal-jump formula, adaptive ray integration and production horseshoe field agree. The SA14 sampled field agrees with independent bound/ray quadrature.',
            'This mechanism exists without a circulation solve or Fourier truncation. Changing circulation representation alone cannot generally remove it.',
            'Public equations reproduce the mechanism; they do not prove how a particular ASWING executable treats the force-point limit. No undocumented finite-part or core rule is inferred.'],
        limitations=[
            'No production model, core size, Mach guard, tolerances or release files changed.',
            'Cutoffs are diagnostic exclusions and are not valid accepted physical states or a proposed regularization.',
            'The SA14 check shares geometry and solved circulation with production; it independently verifies the field integration only.',
            'Drela parity and a physically justified treatment of the swept bound-line force velocity remain unresolved.'])
    output=ROOT/'docs/validation/swept-lifting-line-limit.json'
    output.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print('COMPLETE',output,flush=True)


if __name__=='__main__':
    main()
