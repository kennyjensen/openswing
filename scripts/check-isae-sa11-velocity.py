"""Independent line quadrature at rejected SA-11 force points; validity guard is retained."""
from pathlib import Path
import importlib.util, json, sys
import numpy as np
from scipy.integrate import quad, quad_vec

ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT/'scripts'))
from openswing.asw import parse_asw
from openswing.aero import FlightCondition, solve_rigid, AnalysisError
from isae_sa11_reference import sha
spec = importlib.util.spec_from_file_location('sa11', ROOT/'scripts/verify-isae-sa11.py')
study = importlib.util.module_from_spec(spec); spec.loader.exec_module(study)


def probe(case, panels):
    model = parse_asw(case['source']); speed = 240.; alpha = 0.
    condition = FlightCondition(speed=speed, alpha=alpha)
    try:
        result = solve_rigid(model, condition, panels)
    except AnalysisError as exc:
        assert exc.details['kind'] == 'section_normal_mach', str(exc)
        frame = exc.__traceback__
        while frame is not None and frame.tb_frame.f_code.co_name != 'evaluate_aerodynamics': frame = frame.tb_next
        assert frame is not None
        local = frame.tb_frame.f_locals
        # Observe the completed circulation solution from the exception frame;
        # neither solver control flow nor the physical-validity check is changed.
        gamma = local['gamma'].copy(); geometry = local['p']; index = int(local['worst'])
        assert local['error'] <= 1e-8 and len(set(geometry['physical'])) == 1
        assert not condition.ground_effect and all(b.lifting for b in model.beams)
        point = geometry['hv'][index].copy(); direction = np.array([1., 0., 0.])
        mach = speed/model.constants[2]
        pg = np.eye(3)+(1/np.sqrt(1-mach**2)-1)*np.outer(direction, direction)
        a = geometry['a']@pg.T; b = geometry['b']@pg.T; target = point@pg.T
        wake_direction = pg@direction; wake_direction /= np.linalg.norm(wake_direction)
        delta = b-a; selected = np.arange(len(gamma)) != index

        def integrand(fraction):
            r = target-a[selected]-fraction*delta[selected]
            return gamma[selected, None]*np.cross(delta[selected], r)/np.linalg.norm(r, axis=1)[:, None]**3/(4*np.pi)

        bound, bound_error = quad_vec(integrand, 0., 1., epsabs=1e-8, epsrel=1e-11, limit=10000)
        per_source = np.zeros((len(gamma), 3)); per_source[selected] = bound
        wake = np.zeros_like(per_source); wake_error = 0.
        for k in range(len(gamma)):
            for node, sign in [(b[k], 1.), (a[k], -1.)]:
                r = target-node; along = r@wake_direction
                h = np.linalg.norm(r-along*wake_direction); assert h > 0
                # w=tan(theta) makes the infinite ray integral smooth on a
                # bounded interval even for a very close wake encounter.
                # Direct quadrature from a huge negative w to infinity can
                # miss the narrow central contribution entirely.
                value, error = quad(np.cos, np.arctan2(-along, h), np.pi/2,
                                    epsabs=1e-12, epsrel=1e-12)
                coefficient = sign*gamma[k]*np.cross(wake_direction, r)/(4*np.pi*h*h)
                wake[k] += coefficient*value; wake_error += np.linalg.norm(coefficient)*error
        bound_physical = per_source@pg; wake_physical = wake@pg
        independent = speed*direction+bound_physical.sum(axis=0)+wake_physical.sum(axis=0)
        production = np.array(exc.details['maximum']['relative_velocity'])
        difference = float(np.max(abs(independent-production)))
        normal = independent-(independent@geometry['s'][index])*geometry['s'][index]
        normal_speed = float(np.linalg.norm(normal)); independent_mach = normal_speed/model.constants[2]
        tolerance = 2e-6+2e-9*np.linalg.norm(production)
        assert difference < tolerance, (case['case_id'], panels, difference, tolerance)
        contributors = []
        for beam in sorted(set(geometry['beam'])):
            mask = geometry['beam'] == beam
            contributors.append(dict(beam=int(beam), bound_velocity=bound_physical[mask].sum(axis=0).tolist(),
                                     wake_velocity=wake_physical[mask].sum(axis=0).tolist()))
        return dict(case=case['case_id'], panels=panels, speed=speed, alpha=alpha,
            status='REJECTION_VELOCITY_INDEPENDENTLY_REPRODUCED', error=str(exc), details=exc.details,
            normalized_circulation_residual=float(local['error']), actual_strips=len(gamma),
            independent_velocity=independent.tolist(), independent_normal_speed=normal_speed,
            independent_normal_mach=float(independent_mach), maximum_component_difference=difference,
            absolute_tolerance=float(tolerance), quadrature_bound_error=float(bound_error),
            quadrature_wake_error=float(wake_error), contributors=contributors,
            prescribed_circulation=gamma.tolist(), source_beams=geometry['beam'].tolist(),
            source_a=geometry['a'].tolist(), source_b=geometry['b'].tolist(),
            receiver=point.tolist(), receiver_source_index=index, receiver_span_axis=geometry['s'][index].tolist())
    else:
        return dict(case=case['case_id'], panels=panels, speed=speed, alpha=alpha,
            status='COMPUTED_NO_REJECTION_TO_REPLAY', CL=result['CL'], CD=result['CD'], residual=result['residual'])


def main():
    sources = json.loads((ROOT/'docs/validation/isae-sa11-sources.json').read_text())
    modules = {p.name: sha(p) for p in (ROOT/'openswing').glob('*.py')}
    rows = []
    for case in study.case_entries(sources):
        if case['name'] not in ['wingtip_up', 'wingtip_up_and_down']: continue
        for panels in [25, 50]:
            row = probe(case, panels); rows.append(row)
            print(case['case_id'], panels, row['status'], row.get('maximum_component_difference'), flush=True)
    assert len(rows) == 4 and modules == {p.name: sha(p) for p in (ROOT/'openswing').glob('*.py')}
    out = dict(status='INDEPENDENT_VELOCITY_DIAGNOSTIC_NOT_PHYSICAL_VALIDATION', rows=rows, modules=modules,
        source_report_sha256=sha(ROOT/'docs/validation/isae-sa11-sources.json'), script_sha256=sha(Path(__file__)),
        compute_script_sha256=sha(ROOT/'scripts/verify-isae-sa11.py'),
        method='Numerical finite-segment and semi-infinite-ray Biot-Savart quadrature in PG coordinates, transformed back to physical velocity. Same-physical-beam zero core; only the receiver own bound segment is omitted, matching the documented principal value.',
        limitations=['This verifies velocity for the production geometry and converged circulation; neither is an independent reconstruction or circulation solution.',
                     'Original requests remain rejected. No Mach guard, force law, circulation tolerance, local velocity or core radius is altered.',
                     'Large local velocities do not establish physical transonic flow or experimental agreement; geometry, wake encounters and discretization validity require further investigation.'])
    (ROOT/'docs/validation/isae-sa11-velocity.json').write_text(json.dumps(out, indent=2)+'\n')


if __name__ == '__main__': main()
