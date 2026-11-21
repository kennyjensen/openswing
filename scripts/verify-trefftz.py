"""Analytical wake verification and the published flying-wing span efficiency.

Fetch official references first. The earlier flying-wing study supplies checked
warm starts only; each equilibrium is solved with the current kernel. No
circulation, drag or stiffness correction is fitted to the published result.
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
from openswing.aero import FlightCondition
from openswing.asw import parse_asw
from openswing.ground import GroundPlane
from openswing.linear_dynamics import make_system, linearize, eigensystem
from openswing.operating import OperatingConstraint
from openswing.trefftz import wake_forces, wake_velocity


def distribution(n, modes=(10.,)):
    theta = np.linspace(0, np.pi, n+1)
    mid = .5*(theta[:-1]+theta[1:])
    nodes = np.c_[np.zeros(n+1), -4*np.cos(theta), np.zeros(n+1)]
    points = np.c_[np.zeros(n), -4*np.cos(mid), np.zeros(n)]
    gamma = sum(amplitude*np.sin(k*mid) for k, amplitude in enumerate(modes, 1))
    return nodes[:-1], nodes[1:], points, gamma


def analytical():
    rows = []
    for n, modes in [(n, (10.,)) for n in (16, 32, 64, 128)]+[(192, (10., 0., 2.)), (192, (0., 10.)), (192, (8., -2., 1., .5))]:
        a, b, p, gamma = distribution(n, modes)
        result = wake_forces(a, b, p, gamma, [1., 0., 0.], [0., 1., 0.], [0., 0., 1.],
                             20., 1.2, [[8., 1., 8.], [0., 0., 0.]])
        exact = dict(lift=1.2*20*8*np.pi/4*modes[0],
                     drag=1.2*np.pi/8*sum(k*v*v for k, v in enumerate(modes, 1)),
                     roll=-1.2*20*8**2*np.pi/16*(modes[1] if len(modes)>1 else 0.),
                     efficiency=modes[0]**2/sum(k*v*v for k, v in enumerate(modes, 1)))
        errors = dict(lift=result['force_transverse_body'][2]-exact['lift'],
                      relative_drag=result['induced_drag']/exact['drag']-1,
                      roll=result['rolling_moment_wind']-exact['roll'],
                      efficiency=result['efficiency']-exact['efficiency'])
        assert result['available'] and abs(errors['relative_drag']) < .004
        rows.append(dict(panels=n, fourier_amplitudes=list(modes), exact=exact, errors=errors,
                         result={k: result[k] for k in ('CLi', 'CYi', 'CDi', 'efficiency', 'induced_drag', 'rolling_moment_wind')}))
    ground_rows = []
    a, b, _, gamma = distribution(511)
    for flag in (1, -1):
        for height in (.3, 1., 4.):
            plane = GroundPlane(flag, [0., 0., height])
            w = wake_velocity([[0., 0., 0.]], np.r_[a, plane.reflect_points(a)],
                np.r_[b, plane.reflect_points(b)], np.r_[gamma, -flag*gamma], [1., 0., 0.])[0, 2]
            k = height/2; solid = k/np.sqrt(1+k*k)
            exact = -10/8*(solid if flag == 1 else 2-solid)
            error = w/exact-1
            assert abs(error) < 3e-5
            ground_rows.append(dict(flag=flag, height=height, panels=511, center_downwash=float(w),
                                    exact_center_downwash=float(exact), relative_error=float(error)))
    return dict(span=8., area=8., speed=20., density=1.2,
                definition='Gamma(theta)=sum Gamma_n sin(n theta), y=-b cos(theta)/2; L=rho V pi b Gamma_1/4, D=rho pi sum(n Gamma_n^2)/8.',
                cases=rows, ground_center_cases=ground_rows)


def flying_wing(source, prior, point, panels):
    start = time.monotonic()
    old = next((c for c in prior['cases'] if c['requested_panels'] == panels and c['speed_ft_s'] == 64 and c['difference_step'] == 1e-5), None)
    trim = old['trim'] if old else point
    condition = FlightCondition(speed=64., alpha=trim['alpha_deg'], controls={2: trim['control_2_deg']},
                                attitude=[0., trim['elevation_deg'], 0.])
    constraints = [OperatingConstraint('alpha', 'force.z'), OperatingConstraint('attitude.elevation', 'force.x'),
                   OperatingConstraint('control.2', 'moment.y')]
    system, _ = make_system(parse_asw(source), condition, panels, frame='free', operating_constraints=constraints,
                            initial_state=old['base']['equilibrium_state'] if old else None)
    base = system.base_report()
    assert base['modal_base']['continuous_residual'] < 1e-8 and base['trefftz']['available']
    near_difference = None
    if old:
        near_difference = {k: base[k]-old['base'][k] for k in ('CL', 'CD', 'CY', 'Cl', 'Cm', 'Cn')}
        assert max(abs(v) for v in near_difference.values()) < 1e-8
        assert abs(base['efficiency_near']-old['base']['efficiency']) < 1e-8
    root = None
    if panels == 8:
        # One fresh original-pencil check confirms that adding reporting fields
        # has not changed the physical dynamic equations of the prior study.
        a, m = linearize(system, step=1e-5)
        modes, _ = eigensystem(a, m, time_scale=system.W, count=4, shift=(-.1, 18.), method='full_shift_invert')
        selected = [mode for mode in modes if mode['eigenvalue'][0] > -3 and 15 < mode['eigenvalue'][1] < 24]
        assert len(selected) == 1
        difference = float(np.linalg.norm(np.array(selected[0]['eigenvalue'])-old['bff_root_per_s']))
        backward = max(max(mode['right_backward_error'], mode['left_backward_error']) for mode in modes)
        assert difference < 1e-6 and backward < 1e-9
        root = dict(value_per_s=selected[0]['eigenvalue'], previous_difference_per_s=difference, maximum_backward_error=backward)
    result = dict(requested_panels=panels, actual_lifting_panels=base['lifting_panels'], speed_ft_s=64.,
                  initialized_from_previous_study=old is not None, base=base,
                  published_efficiency=point['efficiency'], efficiency_difference=base['efficiency']-point['efficiency'],
                  previous_near_field_coefficient_differences=near_difference, modal_regression=root,
                  elapsed_seconds=time.monotonic()-start)
    print(f"{base['lifting_panels']} panels: e={base['efficiency']:.9f}, CDi={base['CDi']:.9f}; {result['elapsed_seconds']:.1f}s", flush=True)
    return result


def main():
    reference_path = ROOT/'docs/validation/fw-reference.json'
    previous_path = ROOT/'docs/validation/flying-wing.json'
    reference = json.loads(reference_path.read_text()); previous = json.loads(previous_path.read_text())
    source = (ROOT/'.reference/fw.asw').read_bytes()
    assert hashlib.sha256(source).hexdigest() == reference['aircraft']['sha256']
    files = [Path(__file__), reference_path, previous_path, *sorted((ROOT/'openswing').glob('*.py'))]
    hashes = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    key = hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()
    cache = ROOT/'.reference/trefftz'/key; cache.mkdir(parents=True, exist_ok=True)
    point = next(p for p in reference['points'] if p['speed_ft_s'] == 64)
    analytic = analytical()
    cases = []
    for panels in (8, 16, 32, 64):
        path = cache/f'{panels}.json'
        if not path.exists():
            path.write_text(json.dumps(flying_wing(source.decode(), previous, point, panels), allow_nan=False)+'\n')
        cases.append(json.loads(path.read_text()))
    output = dict(description='Trefftz-plane analytical verification and published ASWING flying-wing efficiency comparison.',
                  source_sha256=hashes, versions=dict(python=platform.python_version(), numpy=np.__version__, scipy=scipy.__version__),
                  reference=reference, analytical=analytic, flying_wing=cases,
                  interpretation='No parameter fitting. Prior study packets are checked warm starts, not current validation. Original ASWING mesh/settings are unknown; the new spatial trend and raw differences are retained.',
                  scope='Piecewise constant current circulation, theta midpoint quadrature, wind-aligned straight wake, no shed-wake history, no body/jet wake. Images require wind parallel to the plane.',
                  coefficients='CDi and efficiency now use Trefftz lift/sideforce/drag. CDi_near and efficiency_near retain the former near-field quantities. Total CD and physical equations are unchanged.')
    target = ROOT/'docs/validation/trefftz.json'
    target.write_text(json.dumps(output, indent=2, allow_nan=False)+'\n')
    print(f'Wrote {target.relative_to(ROOT)}', flush=True)


if __name__ == '__main__':
    main()
