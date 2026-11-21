"""Tabulated swept-wing aerodynamic coordinates and an independent vortex check.

The quarter-chord axis follows streamwise quarter-chord points from the primary
planform table. Normal chord is streamwise chord times dy/ds on each straight
axis segment. This preserves zero-wind quarter/three-quarter stations and strip
area; it does not reconstruct the manufactured RAE 101 sections or normal-strip
outline at root/tip. Stall and profile drag are disabled for this inviscid study.
"""
from pathlib import Path
import hashlib
import json
import platform
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import numpy as np
import scipy
from scipy.integrate import quad_vec
from openswing.asw import parse_asw
from openswing.aero import FlightCondition, solve_rigid, AnalysisError
from openswing.geometry import model_meshes
from openswing.frozen_influence import lifting_geometry

MODEL_PATH = ROOT/'examples/weber-tabulated.asw'
STUDY_PATH = ROOT/'docs/validation/weber-lifting-line.json'
PANELS = [24, 48, 96, 192, 384, 512]
ANGLES = [2.1, 4.2, 6.3, 8.4, 10.5]
MODES = {f'{name}_{pg}': dict(freeze_influences=frozen, mach=mach)
         for name, frozen in [('current', False), ('frozen', True)]
         for pg, mach in [('zero_pg', 0.), ('speed_pg', None)]}


def planform():
    record = json.loads((ROOT/'docs/validation/weber-planform.json').read_text())
    # The last two printed entries extend the constant-span edge. They do not
    # define new span stations or alter its limiting two-inch streamwise chord.
    tip = np.array(record['tip_coordinates_local_xy_in'])
    keep = np.r_[True, np.diff(tip[:, 1]) > 0]
    tip = tip[keep]
    assert tip.shape == (24, 2) and np.array_equal(tip[-1], [23, 5])
    y = np.r_[0., 44+tip[:, 1]]*.0254
    le = np.r_[0., 44+tip[:, 0]]*.0254
    chord = y+.508-le
    return record, y, le, chord, le+chord/4


def generate():
    record, y, le, chord, quarter = planform()
    lines = [
        '! Original OpenSwing study based on ARC R&M 2882 Part II Table 1.',
        '! Rigid inviscid aerodynamic-coordinate reconstruction; not a matched experiment.',
        '! Use rigid mode, speed 49.6824, beta 0, density 1.2256, and STALL DISABLED.',
        '! dCLda=2*pi and zero section/profile drag are idealizations, not RAE 101 data.',
        '! Quarter-chord/control stations and integrated strip area match the declared',
        '! piecewise-linear table reconstruction at zero wind angle. Normal-strip',
        '! display geometry near root/tip is an approximation. See the study record.',
        'Name', 'Tabulated swept-wing lifting-line study', 'End',
        'Unit', 'L 1 m', 'T 1 s', 'F 1 N', 'End',
        'Constant', '9.80665 1.2256 340.21', 'End', 'Reference',
        f"{record['cases'][0]['piecewise_linear']['area_m2']:.17g} .508 2.4892",
        f'{29.30*.0254:.17g} 0 0', 'End', 'Ground', '1 0 0', 'End',
        'Beam 1', 'Tabulated quarter-chord axis', 't x y z chord Xax']
    for i in range(len(y)-1):
        dy_ds = (y[i+1]-y[i])/np.hypot(quarter[i+1]-quarter[i], y[i+1]-y[i])
        # Doubled stations preserve each straight segment and its one-sided
        # normal chord, without depending on unspecified cubic end conditions.
        for j in [i, i+1]:
            lines.append(' '.join(f'{v:.17g}' for v in [y[j], quarter[j], y[j], 0., chord[j]*dy_ds, .25]))
    lines += ['t Cdf Cdp dCLda Cm alpha', f'0 0 0 {2*np.pi:.17g} 0 0',
              f'{y[-1]:.17g} 0 0 {2*np.pi:.17g} 0 0', 'End']
    return '\n'.join(lines)+'\n'


def reference_coordinates(t, direction):
    """Physical coordinates from the primary-table polyline, without ASW code."""
    _, y, le, chord, quarter = planform()
    t = np.asarray(t); q = abs(t)
    segment = np.clip(np.searchsorted(y, q, side='right')-1, 0, len(y)-2)
    slope = np.diff(quarter)/np.diff(y)
    dx_dy = np.sign(t)*slope[segment]
    tangent = np.column_stack([dx_dy, np.ones(len(t)), np.zeros(len(t))])
    tangent /= np.linalg.norm(tangent, axis=1)[:, None]
    chord_normal = np.interp(q, y, chord)*tangent[:, 1]
    axis = np.column_stack([np.interp(q, y, quarter), t, np.zeros(len(t))])
    across = np.linalg.norm(np.cross(direction, tangent), axis=1)
    control = axis+(chord_normal/(2*across))[:, None]*direction
    labels = np.sign(t)*(segment+1)
    return dict(axis=axis, control=control, tangent=tangent, chord=chord_normal, segment=labels)


def geometry_check(source, panels):
    model = parse_asw(source)
    assert not model.diagnostics and model.dumps() == source
    canonical = parse_asw(model.dumps(canonical=True))
    meshes = model_meshes(model, panels)
    mesh = meshes[0]; beam = mesh.beam
    wind = np.array([1., 0., 0.])
    ref = reference_coordinates(mesh.tm, wind)
    actual = lifting_geometry(meshes, wind)
    endpoint = max(np.max(abs(actual['a']-reference_coordinates(mesh.t0, wind)['axis'])),
                   np.max(abs(actual['b']-reference_coordinates(mesh.t1, wind)['axis'])))
    error = max(endpoint, np.max(abs(actual['hv']-ref['axis'])),
                np.max(abs(actual['cp']-ref['control'])),
                np.max(abs(mesh.frames[..., 1]-ref['tangent'])),
                np.max(abs(beam.value('chord', mesh.tm)-ref['chord'])))
    area = float(np.sum((beam.value('chord', mesh.t0, side='right')+
                         beam.value('chord', mesh.t1, side='left'))*.5*mesh.length))
    assert error < 1e-11 and abs(area-model.reference[0, 0]) < 1e-11
    for name in ['x', 'y', 'z', 'chord', 'Xax']:
        assert np.max(abs(beam.value(name, mesh.tm)-canonical.beams[0].value(name, mesh.tm))) < 1e-11
    return dict(requested_intervals=panels, actual_intervals=len(mesh.tm),
                maximum_coordinate_frame_error=error, integrated_normal_strip_area=area,
                reference_area=float(model.reference[0, 0]), area_error=abs(area-model.reference[0, 0]),
                lossless_and_canonical_roundtrip=True)


def independent_velocity(points, starts, ends, direction, collinear=None):
    """Biot–Savart bound-line quadrature plus analytically integrated wake rays.

    The finite segment uses adaptive numerical integration, not the production
    finite-vortex formula. Known straight-line principal values are zeroed by
    primary-polyline segment identity, not by a fitted distance threshold.
    """
    displacement = ends-starts
    r = points[:, None, :]-starts[None, :, :]
    numerator = np.cross(displacement[None, :, :], r)
    if collinear is not None:
        numerator = np.where(collinear[..., None], 0., numerator)
    def integrand(t):
        distance = np.linalg.norm(r-t*displacement[None, :, :], axis=2)
        if collinear is not None:
            distance = np.where(collinear, 1., distance)
        return numerator/distance[..., None]**3
    bound, error, info = quad_vec(integrand, 0., 1., norm='max', epsabs=1e-9,
                                  epsrel=2e-12, full_output=True)
    assert info.success, info.message
    def ray(origin):
        relative = points[:, None, :]-origin[None, :, :]
        along = relative@direction
        perpendicular = relative-along[..., None]*direction
        distance2 = np.sum(perpendicular**2, axis=-1)
        assert np.min(distance2) > 0
        factor = (1+along/np.linalg.norm(relative, axis=-1))/distance2
        return np.cross(direction, relative)*factor[..., None]
    return (bound+ray(ends)-ray(starts))/(4*np.pi), float(error/(4*np.pi)), int(info.neval)


def independent_case(source, panels, frozen):
    model = parse_asw(source); mesh = model_meshes(model, panels)[0]
    alpha = np.deg2rad(2.1); wind = np.array([np.cos(alpha), 0., np.sin(alpha)])
    influence_wind = np.array([1., 0., 0.]) if frozen else wind
    ref = reference_coordinates(mesh.tm, influence_wind)
    starts = reference_coordinates(mesh.t0, influence_wind)['axis']
    ends = reference_coordinates(mesh.t1, influence_wind)['axis']
    matrix, cp_error, cp_evals = independent_velocity(ref['control'], starts, ends, influence_wind)
    speed, density = 49.6824, 1.2256
    gamma = np.linalg.solve(matrix[..., 2], np.full(len(starts), -speed*wind[2]))
    collinear = ref['segment'][:, None] == ref['segment'][None, :]
    influence, hv_error, hv_evals = independent_velocity(ref['axis'], starts, ends, influence_wind, collinear)
    velocity = speed*wind+np.einsum('ijk,j->ik', influence, gamma)
    length = np.linalg.norm(ends-starts, axis=1)
    force = density*gamma[:, None]*np.cross(velocity, ref['tangent'])*length[:, None]
    moment = np.cross(ref['axis']-model.reference[1], force)
    condition = FlightCondition(speed=speed, alpha=2.1, mach=0., density=density, stall=False, freeze_influences=frozen)
    actual = solve_rigid(model, condition, panels=panels)
    actual_gamma = np.array([s['circulation'] for s in actual['strips']])
    actual_velocity = np.array([s['relative_velocity'] for s in actual['strips']])
    qS = .5*density*speed**2*model.reference[0, 0]
    errors = dict(circulation=float(np.max(abs(actual_gamma-gamma))/(speed*.508)),
                  velocity=float(np.max(abs(actual_velocity-velocity))/speed),
                  force=float(np.max(abs(np.sum(force, axis=0)-actual['force']))/qS),
                  moment=float(np.max(abs(np.sum(moment, axis=0)-actual['moment']))/(qS*.508)))
    assert max(errors.values()) < 2e-9, errors
    return dict(requested_intervals=panels, actual_intervals=len(starts), frozen=frozen,
                maximum_scaled_errors=errors, bound_quadrature_error_estimates=[cp_error, hv_error],
                bound_quadrature_evaluations=[cp_evals, hv_evals],
                circulation_matrix_condition=float(np.linalg.cond(matrix[..., 2])),
                physical_values_compared=int(4*len(starts)+6))


def compute(source, spec):
    condition = FlightCondition(speed=49.6824, alpha=spec['alpha_deg'], density=1.2256,
                                mach=spec['mach'], freeze_influences=spec['freeze_influences'], stall=False)
    try:
        result = solve_rigid(parse_asw(source), condition, panels=spec['panels'])
    except AnalysisError as exc:
        return dict(status='rejected', error=str(exc), details=exc.details)
    assert result['converged'] and result['residual'] < 1e-8
    assert abs(result['CDp']) < 1e-20
    assert max(abs(result[k]) for k in ['CY', 'Cl', 'Cn']) < 2e-9
    if spec['alpha_deg'] == 0:
        assert max(abs(result[k]) for k in ['CL', 'CD', 'Cm', 'CDi']) < 1e-13
    strips = result['strips']
    selected = [strips[i] for i in np.linspace(0, len(strips)-1, 9).astype(int)]
    return dict(status='computed', result={
        **{k: result[k] for k in ['CL', 'CD', 'CDi', 'CDp', 'Cm', 'CY', 'Cl', 'Cn', 'force', 'moment', 'mach', 'panels', 'residual', 'lifting_airflow']},
        'samples': [[s['t'], s['circulation'], s['cl'], *s['relative_velocity']] for s in selected]})


def physical(result):
    return np.r_[*[result[k] for k in ['CL', 'CD', 'CDi', 'CDp', 'Cm', 'CY', 'Cl', 'Cn']],
                 result['force'], result['moment'], np.ravel(result['samples'])]


def main():
    source = generate(); MODEL_PATH.write_text(source)
    geometry = [geometry_check(source, n) for n in PANELS]
    print('All six geometry/serialization checks passed.', flush=True)
    references = []
    for n in [24, 48]:
        for frozen in [False, True]:
            r = independent_case(source, n, frozen); references.append(r)
            print('Independent quadrature:', n, frozen, r['maximum_scaled_errors'], flush=True)
    cases = []
    for name, mode in MODES.items():
        for n in PANELS:
            for alpha in ANGLES:
                spec = dict(mode=name, panels=n, alpha_deg=alpha, **mode)
                started = time.monotonic(); out = compute(source, spec)
                cases.append(dict(specification=spec, **out))
                print(name, n, alpha, out['status'],
                      {k: out['result'][k] for k in ['CL', 'CD']} if out['status']=='computed' else out['error'],
                      f'{time.monotonic()-started:.2f}s', flush=True)
    for n in PANELS:
        spec = dict(mode='current_zero_pg', panels=n, alpha_deg=0., **MODES['current_zero_pg'])
        cases.append(dict(specification=spec, **compute(source, spec)))
    comparison = []
    for name in MODES:
        for alpha in ANGLES:
            rows = [c for c in cases if c['specification']['mode']==name and c['specification']['alpha_deg']==alpha]
            for lo, hi in zip(rows, rows[1:]):
                comparison.append(dict(mode=name, alpha_deg=alpha,
                    coarse=lo['specification']['panels'], fine=hi['specification']['panels'],
                    both_computed=lo['status']==hi['status']=='computed',
                    absolute_change={k:abs(lo['result'][k]-hi['result'][k]) for k in ['CL','CD','Cm','CDi']}
                    if lo['status']==hi['status']=='computed' else None))
    sources = [Path(__file__), MODEL_PATH, ROOT/'docs/validation/weber-planform.json',
               *sorted((ROOT/'openswing').glob('*.py'))]
    output = dict(description=__doc__, source_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},
        versions=dict(python=platform.python_version(), numpy=np.__version__, scipy=scipy.__version__),
        settings=dict(panels=PANELS, angles_deg=ANGLES, modes=MODES, speed=49.6824, density=1.2256,
                      stall=False, section_lift_slope=2*np.pi, section_moment=0., section_profile_drag=0.,
                      reference_area=planform()[0]['cases'][0]['piecewise_linear']['area_m2']),
        geometry=geometry, independent_references=references, cases=cases, mesh_changes=comparison,
        scope='Inviscid aerodynamic-coordinate reconstruction and independent implementation verification. No measured polar fitting, matched experimental validation, original-ASWING parity or full-range mesh convergence is claimed.',
        limitations=[
            'Normal-strip drawing geometry at root/tip differs from the streamwise planform. Zero-wind aerodynamic stations and integrated strip area are the verified invariants.',
            'RAE 101 thickness, viscous section data, experimental incidence corrections, pressure-tube fairings and the published moment-reference discrepancy remain unresolved.',
            'Piecewise-linear primary-table geometry retains small tangent jumps. Smooth manufactured geometry and its sensitivity are separate work.',
            'Subsonic rejection remains active; computed cases are not automatically converged or physically valid under spatial refinement.',
            'Near-field force drag and far-wake induced drag retain separate definitions; neither is substituted for measured pressure drag.'
        ])
    STUDY_PATH.write_text(json.dumps(output, indent=2)+'\n')
    print('Recorded',len(cases),'cases:',sum(c['status']=='computed' for c in cases),'computed,',sum(c['status']=='rejected' for c in cases),'rejected.',flush=True)


if __name__ == '__main__':
    main()
