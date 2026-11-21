"""Qualified UA-1 equation checks and a conservative UA-2 source ledger.

The UA-1 reference is the authors' MATLAB implementation of a published
ASWING equation, not executable output. The saved UA-2 curves reproduce a
scaled 2D equation; their labels do not establish native 3D solver provenance.
No upstream MATLAB is executed and no correction is applied to production.
"""
from __future__ import annotations

import cmath
import hashlib
import json
import math
from pathlib import Path
import sys


REVISION = 'f62943df20e9e4d7d9f50e070477b22426b5f865'
BASE = '1 - Aerodynamics/UA - Unsteady Aerodynamics Cases'
DIRECTORIES = {1: 'UA - 1 - Plunging Airfoil - 2D', 2: 'UA - 2 - Plunging Wing - 3D'}
MATLAB_SHA = {1: '47c8cce7595a0d350bb78d791722cb1b6f8d441d6a1ce11bafee526ee2aa4bce',
              2: 'c4d13973b1a0f996976478979f9c8805e2b8edc11a475732cf406d844df26733'}
AMPLITUDES = (.05, .1, .3, .5)
FREQUENCIES = tuple(.95 * i / 14 for i in range(15))
# These are equation verification tolerances, not the provisional SA 3% policy.
AMPLITUDE_RTOL = 1e-4
AMPLITUDE_ATOL = 1e-9
PHASE_ATOL_DEG = .01


def _require(ok, message):
    if not ok:
        raise ValueError(message)


def _pin(path):
    path = Path(path).resolve()
    raw = path.read_bytes()
    return dict(path=str(path), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def source_formula(k, correction=1.):
    """Literal UA sim_total.m bracket, before amplitude/phase presentation."""
    lag = (1 + 2j*k) / (1 + 4j*k)
    return correction * 2*math.pi*k*1j*lag - math.pi*k*k


def _observations(correction=1.):
    rows = []
    for amplitude in AMPLITUDES:
        for index, k in enumerate(FREQUENCIES):
            expected = amplitude*abs(source_formula(k, correction))
            rows.append(dict(name=f'amplitude:A{amplitude:g}:k{index:02}',
                output='amplitude', amplitude_over_chord=amplitude, k=k,
                expected=expected, tolerance=max(AMPLITUDE_ATOL, AMPLITUDE_RTOL*abs(expected))))
    # k=0 has zero lift oscillation and undefined phase: MATLAB excludes it.
    for index, k in enumerate(FREQUENCIES[1:], 1):
        rows.append(dict(name=f'phase:k{index:02}', output='phase_deg', k=k,
            expected=180 + math.degrees(cmath.phase(source_formula(k, correction))),
            tolerance=PHASE_ATOL_DEG))
    return rows


def audit_sources(root):
    """Verify pinned sources and test the provenance of all six UA-2 FIGs."""
    root = Path(root).resolve()
    cache = root/'.reference/isae-validation'
    manifest = json.loads((cache/'manifest.json').read_text())
    inventory = json.loads((root/'docs/validation/isae-figure-inventory.json').read_text())
    _require(manifest['revision'] == inventory['revision'] == REVISION, 'UA revision mismatch')
    pins = []

    def upstream(name):
        path = cache/REVISION/name
        pin = _pin(path)
        recorded = manifest['files'][name]
        _require(pin['sha256'] == recorded['sha256'] and pin['bytes'] == recorded['bytes'],
                 'Changed UA source: '+name)
        pins.append(pin)
        return path

    for number in (1, 2):
        path = upstream(f'{BASE}/{DIRECTORIES[number]}/sim_total.m')
        _require(_pin(path)['sha256'] == MATLAB_SHA[number], 'Unreviewed UA MATLAB source')
    primary = root/'docs/validation/isae-ua-primary-sources-20261101.json'
    conventions = json.loads(primary.read_text())
    _require({row['doi'] for row in conventions['sources']} ==
             {'10.2514/6.2017-0996', '10.2514/6.2017-3127'}, 'Unexpected UA primary sources')
    pins.append(_pin(primary))
    cases = []
    for alpha, correction in ((0, .85), (5, .90), (9, .90)):
        coordinates = []
        differences = {'amplitude': [], 'phase_deg': []}
        for kind in ('A1', 'phi'):
            name = f'{BASE}/{DIRECTORIES[2]}/CL_{kind}__alpha_{alpha}_W.fig'
            original = upstream(name)
            record = next(row for row in inventory['figures'] if row['path'] == name)
            _require(record['sha256'] == _pin(original)['sha256'], 'UA FIG inventory mismatch')
            extracted = cache/'figure-series'/(record['sha256']+'.json')
            pin = _pin(extracted)
            _require(pin['sha256'] == record['extracted_sha256'], 'Changed UA FIG extraction')
            pins.append(pin)
            series = json.loads(extracted.read_text())['series']
            labels = ([f'A/c = {a:g} (3D ASWING)' for a in AMPLITUDES] if kind == 'A1'
                      else ['3D ASWING'])
            native_labelled = [row for row in series if 'ASWING' in row['label']]
            _require(sorted(r['label'] for r in native_labelled) == sorted(labels),
                     'Unexpected UA-2 ASWING-labelled series')
            for label in labels:
                curve = next(row for row in native_labelled if row['label'] == label)
                amplitude = float(label.split()[2]) if kind == 'A1' else None
                expected_rows = [r for r in _observations(correction)
                    if (r['output'] == 'amplitude' and r['amplitude_over_chord'] == amplitude)
                    or (kind == 'phi' and r['output'] == 'phase_deg')]
                _require(len(curve['xy']) == len(expected_rows), 'UA-2 figure length changed')
                for xy, row in zip(curve['xy'], expected_rows):
                    _require(abs(xy[0]-row['k']) < 1e-14, 'UA-2 frequency coordinates changed')
                    error = abs(xy[1]-row['expected'])
                    differences[row['output']].append(error)
                    coordinates.append(dict(row, expected=xy[1], source=str(original), label=label))
        _require(len(coordinates) == 74, 'Incomplete UA-2 harmonic reference')
        maxima = {key: max(values) for key, values in differences.items()}
        _require(maxima['amplitude'] < 1e-12 and maxima['phase_deg'] < 1e-10,
                 'UA-2 saved curves no longer match the reviewed corrected 2D equation')
        cases.append(dict(alpha_label_deg=alpha, circulatory_scale_in_matlab=correction,
            observations=coordinates, formula_max_absolute_error=maxima,
            classification='saved_corrected_2D_formula_not_verified_native_3D_output'))
    names = [name for name in manifest['files'] if name.startswith(BASE+'/')]
    return dict(revision=REVISION, sources=pins, ua2=cases,
        literal_models=[name for name in names if name.endswith('.asw')],
        shell_drivers=[name for name in names if name.endswith('.sh')],
        ua1_duplicate_plot_labels_deg=[0, 5, 9],
        ua1_unique_harmonic_outputs=74, ua2_archived_harmonic_outputs=222,
        amplitude_convention='A is peak-to-peak displacement, A=2a; verified in both original papers.',
        ua2_reconstruction='Primary paper specifies semi-aspect ratio 5; symmetric full wing has AR10.',
        native_3D_run_provenance_verified=False)


def model_text(aspect_ratio=200000.):
    """Dimensionless rigid rectangular wing; reference area equals its geometry."""
    return f'''Name
UA equation verification wing (reconstructed, not an archived model)
End
Unit
L 1 m
T 1 s
F 1 N
End
Constant
9.80665 1.225 340.294
End
Reference
{aspect_ratio:.17g} 1 {aspect_ratio:.17g}
0 0 0
End
Ground
1 0 0
End
Beam 1
Rigid wing
t x y z chord Xax
0 0 0 0 1 .25
{aspect_ratio/2:.17g} 0 {aspect_ratio/2:.17g} 0 1 .25
t Cdf Cdp dCLda CLmax CLmin
0 0 0 6.283185307179586 10 -10
{aspect_ratio/2:.17g} 0 0 6.283185307179586 10 -10
End
'''


def plan(root):
    audit = audit_sources(root)
    jobs = []
    for panels in (4, 8):
        jobs.append(dict(id=f'UA-1-equation-N{panels}', case_id='UA-1', adapter='unsteady',
            target_kind='published_ASWING_equation', execution_route='production_harmonic_residual',
            expected_outputs=74, observations=_observations(), sources=audit['sources'],
            settings=dict(panels=panels, aspect_ratio=200000., speed=30., mach=0.,
                alpha_deg=0., stall=False, aero_lag=True, derivative_step=1e-4),
            scope='Unique first-harmonic amplitude/phase curves from UA-1 sim_total.m; two-dimensional linear limit.',
            normalization='For the source bracket use upward displacement phasor z/c=(A/c)/2. '
                'A is peak-to-peak displacement, A=2a, as defined in both original Chiereghin papers. '
                'k=omega*c/(2V); the input convention is verified, not fitted.',
            duplicate_plot_labels_deg=[0, 5, 9],
            limits=['The three incidence-labelled MATLAB plots use the same dynamic equation with alpha=0.',
                    'The four amplitudes scale a linear transfer; finite-amplitude nonlinear motion is not tested.',
                    'No native ASWING executable output, time marching, mean-lift or phase-average acceptance.',
                    'UA-2 3D corrected curves are not UA-1 targets.']))
    for case in audit['ua2']:
        jobs.append(dict(id=f"UA-2-native-alpha{case['alpha_label_deg']}", case_id='UA-2',
            adapter='unsteady', target_kind='unverified_native_3D', execution_route='unsupported',
            expected_outputs=74, observations=case['observations'], sources=audit['sources'],
            source_audit={key: value for key, value in case.items() if key != 'observations'},
            scope='Archived harmonic curves labelled 3D ASWING; native solver provenance unresolved.',
            blocker='Saved FIG coordinates reproduce the MATLAB scaled-2D formula to rounding. '
                'The report describes 3D runs, but no original model, modified motion driver or raw run is supplied. '
                'The .85/.90 factors must not be fitted into the production solver.'))
    return jobs


def harmonic_response(root, settings, frequencies=FREQUENCIES):
    """Linearize the real production residual and loads; solve its complex system.

    All matrices come from evaluate_aerodynamics at prescribed circulation,
    circulation rate and uniform nodal motion. The target formula is not used.
    Reuse the matrices at every frequency, including apparent mass and Γ-dot lift.
    """
    import numpy as np
    root = Path(root).resolve()
    sys.path.insert(0, str(root))
    from openswing.asw import parse_asw
    from openswing.aero import FlightCondition, evaluate_aerodynamics
    from openswing.network import StaticNetwork
    from openswing.local_motion import NetworkMotion

    _require(Path(sys.modules['openswing.aero'].__file__).resolve() == root/'openswing/aero.py',
             'Unexpected production checkout')
    condition = FlightCondition(speed=settings['speed'], alpha=settings['alpha_deg'],
        mach=settings['mach'], stall=settings['stall'], aero_lag=settings['aero_lag'])
    net = StaticNetwork(parse_asw(model_text(settings['aspect_ratio'])),
                        settings['panels'], condition, [0, 0, 0], [])
    positions = net.rj
    rotations = np.broadcast_to(np.eye(3), (net.nn, 3, 3))
    meshes = net.deformed_meshes(positions, rotations, net.geometry(positions, rotations))
    zeros = np.zeros_like(positions)
    ng = net.ng
    calls = 0

    def evaluate(gamma, gamma_dot, velocity=0., acceleration=0.):
        nonlocal calls
        v, a = zeros.copy(), zeros.copy()
        v[:, 2] = velocity
        a[:, 2] = acceleration
        motion = NetworkMotion(net, positions, rotations, v, zeros, a, zeros)
        result = evaluate_aerodynamics(net.model, condition, meshes,
            point_positions=net.point_positions(positions, rotations), local_motion=motion,
            circulation=gamma, circulation_rate=gamma_dot)
        calls += 1
        return np.r_[result['circulation_residual'], result['CL']]

    z = np.zeros(ng)
    base = evaluate(z, z)
    step = settings['derivative_step']
    columns = []
    for index in range(2*ng + 2):
        args = [z.copy(), z.copy(), 0., 0.]
        if index < 2*ng:
            args[index//ng][index % ng] = step
        else:
            args[index - 2*ng + 2] = step
        plus = evaluate(*args)
        minus = evaluate(*[-value for value in args])
        columns.append((plus-minus)/(2*step))
    matrix = np.column_stack(columns)
    stiffness = matrix[:ng, :ng]
    mass = matrix[:ng, ng:2*ng]
    rv, ra = matrix[:ng, -2], matrix[:ng, -1]
    fg, fd = matrix[-1, :ng], matrix[-1, ng:2*ng]
    fv, fa = matrix[-1, -2:]
    response = []
    max_residual = 0.
    for k in frequencies:
        omega = 2*condition.speed*k  # c=1; k=omega*c/(2V)
        velocity, acceleration = .5j*omega, -.5*omega**2
        lhs = stiffness + 1j*omega*mass
        rhs = -rv*velocity - ra*acceleration
        gamma = np.linalg.solve(lhs, rhs)
        cl = (fg + 1j*omega*fd)@gamma + fv*velocity + fa*acceleration
        residual = float(np.max(np.abs(lhs@gamma-rhs), initial=0.))
        max_residual = max(max_residual, residual)
        response.append(dict(k=k, CL_real=float(cl.real), CL_imag=float(cl.imag),
            amplitude=float(abs(cl)), phase_deg=float(np.angle(cl, deg=True) % 360) if k else None,
            harmonic_residual=residual))
    finite = np.all(np.isfinite(matrix)) and all(math.isfinite(r['amplitude']) for r in response)
    return dict(response=response, numerical_passed=bool(finite and max_residual < 1e-10
        and np.max(np.abs(base), initial=0.) < 1e-10),
        maximum_harmonic_residual=max_residual, zero_state_residual=float(np.max(np.abs(base), initial=0.)),
        production_evaluations=calls, circulation_unknowns=ng, matrix_assemblies=1,
        harmonic_solves=len(response), matrices_reused=True, nonlinear_time_steps=0,
        production_module=str(Path(sys.modules['openswing.aero'].__file__).resolve()))


def run(root, job):
    canonical = next(row for row in plan(root) if row['id'] == job.get('id'))
    for key, value in canonical.items():
        _require(job.get(key) == value, 'Prepared UA job changed: '+key)
    common = dict(id=job['id'], case_id=job['case_id'], adapter='unsteady',
        target_kind=job['target_kind'], scope=job['scope'])
    if job['execution_route'] == 'unsupported':
        checks = [dict(name=row['name'], predicted=None, expected=row['expected'],
            tolerance=row['tolerance'], relative_tolerance_allowed=False, passed=False)
            for row in job['observations']]
        return dict(common, status='unsupported', numerical_passed=False, reference_match=False,
            reference_checks=checks, blocker=job['blocker'], source_audit=job['source_audit'],
            production_evaluations=0, harmonic_solves=0, nonlinear_time_steps=0)
    result = harmonic_response(root, job['settings'])
    checks = []
    for row in job['observations']:
        computed = min(result['response'], key=lambda r: abs(r['k']-row['k']))
        predicted = (computed['amplitude']*row['amplitude_over_chord'] if row['output'] == 'amplitude'
                     else computed['phase_deg'])
        error = abs(predicted-row['expected'])
        checks.append(dict(name=row['name'], output=row['output'], predicted=predicted,
            expected=row['expected'], tolerance=row['tolerance'], abs_error=error,
            relative_tolerance_allowed=False, passed=bool(error <= row['tolerance'])))
    pins_held = all(_pin(p['path']) == p for p in job['sources'])
    numerical = result['numerical_passed'] and pins_held
    return dict(common, status='computed' if numerical else 'numerical_failure',
        numerical_passed=numerical, reference_match=numerical and all(c['passed'] for c in checks),
        reference_checks=checks, production=result, source_pins_unchanged=pins_held,
        settings=job['settings'], normalization=job['normalization'], limits=job['limits'])


def validate_result_contract(job, result):
    """Keep source qualifications and blocked 3D runs visible in saved evidence."""
    for key in ('id', 'case_id', 'adapter', 'target_kind', 'scope'):
        _require(result.get(key) == job[key], 'UA result identity changed: '+key)
    checks = result.get('reference_checks', [])
    _require(len(checks) == job['expected_outputs'], 'Incomplete UA reference outputs')
    for row, check in zip(job['observations'], checks):
        for key in ('name', 'expected', 'tolerance'):
            _require(row[key] == check.get(key), 'UA result reference changed: '+key)
        _require(check.get('relative_tolerance_allowed') is False,
                 'UA equation tolerance must not inherit the SA allowance')
    if job['execution_route'] == 'unsupported':
        _require(result.get('status') == 'unsupported' and result.get('numerical_passed') is False
                 and result.get('reference_match') is False, 'Unverified UA-2 native run cannot pass')
        _require(all(c.get('predicted') is None and c.get('passed') is False for c in checks),
                 'UA-2 source formula is not a native production prediction')
        _require(result.get('blocker') == job['blocker'] and result.get('source_audit') == job['source_audit'],
                 'UA-2 provenance qualification missing')
        _require(all(result.get(key) == 0 for key in
                     ('production_evaluations', 'harmonic_solves', 'nonlinear_time_steps')),
                 'Unsupported UA-2 job must not run a substitute model')
    else:
        for key in ('settings', 'normalization', 'limits'):
            _require(result.get(key) == job[key], 'UA-1 equation qualification missing: '+key)
        production = result.get('production', {})
        _require(production.get('numerical_passed') is True and result.get('source_pins_unchanged') is True,
                 'UA production/source verification failed')
        _require(production.get('matrix_assemblies') == 1 and production.get('harmonic_solves') == 15
                 and production.get('nonlinear_time_steps') == 0,
                 'UA-1 must report the actual harmonic component route')
    return True


def validate_blocked(root, job):
    """Suite inline path: verify the archived ledger without starting physics."""
    _require(job.get('execution_route') == 'unsupported', 'UA job is not blocked')
    result = run(root, job)
    validate_result_contract(job, result)
    return result
