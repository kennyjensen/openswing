"""UA-1 phase curves from production linear derivatives and pinned MATLAB targets.

The source superposes a linear mean-incidence response and a harmonic response
about zero incidence. No nonlinear finite-incidence or native-output claim is
made. The source formula participates only in the comparison, never prediction.
"""
from hashlib import sha256
import json
import math
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
FREQUENCIES = (.47, .94)
INCIDENCES = (0., 5., 9.)
GATES = dict(waveform_fraction=1e-4, amplitude_fraction=1e-4,
             phase_deg=.01, mean_relative=1e-4, mean_absolute=1e-9,
             equation_residual=1e-10, derivative_stability_fraction=1e-7)


def source_binding():
    manifest_path = ROOT / 'docs/validation/isae-ua1-phase-sources-20261101.json'
    manifest = json.loads(manifest_path.read_text())
    for name, expected in manifest['source_sha256'].items():
        if sha256((ROOT / name).read_bytes()).hexdigest() != expected:
            raise ValueError('Changed phase source: ' + name)
    source = manifest['phase_average']
    if (source['reduced_frequencies'] != list(FREQUENCIES)
            or source['mean_incidence_deg'] != list(INCIDENCES)
            or source['amplitude_peak_to_peak_over_chord'] != .5
            or source['phase_samples'] != 100 or source['native_solver_outputs']):
        raise ValueError('Unreviewed phase source settings')
    return manifest


def source_curve(k, alpha_deg, phase):
    """Literal Post_Traitement.m uncorrected ASWING curve."""
    bracket = 2 * np.pi * 1j * k * (1 + 2j*k) / (1 + 4j*k) - np.pi*k*k
    phasor = -.5 * bracket
    mean = 2 * np.pi * math.radians(alpha_deg)
    values = np.real(phasor * np.exp(2j*np.pi*np.asarray(phase))) + mean
    return dict(CL=values, mean=mean, phasor=phasor)


def production_matrix(panels, derivative_scale=1.):
    """Assemble residual/load derivatives once, including mean incidence.

    Columns: Gamma, Gamma_dot, nodal heave velocity, nodal heave acceleration,
    and FlightCondition incidence in radians. All are derivatives at zero.
    """
    from dataclasses import replace
    sys.path.insert(0, str(ROOT))
    from openswing.asw import parse_asw
    from openswing.aero import FlightCondition, evaluate_aerodynamics
    from openswing.network import StaticNetwork
    from openswing.local_motion import NetworkMotion
    from isae_suite_unsteady import model_text
    if panels not in (4, 8) or derivative_scale not in (.5, 1.):
        raise ValueError('Use the declared meshes and derivative scales')
    assert Path(sys.modules['openswing.aero'].__file__).resolve() == ROOT / 'openswing/aero.py'
    condition = FlightCondition(speed=30., alpha=0., mach=0., stall=False, aero_lag=True)
    net = StaticNetwork(parse_asw(model_text()), panels, condition, [0, 0, 0], [])
    rotation = np.broadcast_to(np.eye(3), (net.nn, 3, 3))
    meshes = net.deformed_meshes(net.rj, rotation, net.geometry(net.rj, rotation))
    zeros = np.zeros_like(net.rj)
    ng = net.ng
    calls = 0

    def evaluate(values):
        nonlocal calls
        velocity, acceleration = zeros.copy(), zeros.copy()
        velocity[:, 2], acceleration[:, 2] = values[2*ng:2*ng+2]
        motion = NetworkMotion(net, net.rj, rotation, velocity, zeros, acceleration, zeros)
        current = replace(condition, alpha=math.degrees(values[-1]))
        output = evaluate_aerodynamics(net.model, current, meshes,
            point_positions=net.point_positions(net.rj, rotation), local_motion=motion,
            circulation=values[:ng], circulation_rate=values[ng:2*ng])
        calls += 1
        return np.r_[output['circulation_residual'], output['CL']]

    base = evaluate(np.zeros(2*ng+3))
    steps = np.full(2*ng+3, 1e-4*derivative_scale)
    steps[-1] = 1e-5*derivative_scale
    columns = []
    for index, step in enumerate(steps):
        perturbation = np.zeros(len(steps))
        perturbation[index] = step
        columns.append((evaluate(perturbation)-evaluate(-perturbation))/(2*step))
    return dict(matrix=np.column_stack(columns), base=base, production_evaluations=calls,
                unknowns=ng, speed=condition.speed, derivative_steps=steps)


def predict(matrix, *, speed=30.):
    """Solve production linear systems; no use of source_curve or 2*pi lift slope."""
    matrix = np.asarray(matrix)
    ng = matrix.shape[0]-1
    if matrix.shape != (ng+1, 2*ng+3):
        raise ValueError('Unexpected derivative matrix shape')
    stiffness, mass = matrix[:ng, :ng], matrix[:ng, ng:2*ng]
    gamma_alpha = np.linalg.solve(stiffness, -matrix[:ng, -1])
    mean_slope = matrix[-1, :ng] @ gamma_alpha + matrix[-1, -1]
    static_residual = np.max(abs(stiffness @ gamma_alpha + matrix[:ng, -1]))
    phase = np.linspace(0., 1., 100)
    responses = []
    for k in FREQUENCIES:
        omega = 2*speed*k
        velocity, acceleration = .25j*omega, -.25*omega**2
        lhs = stiffness + 1j*omega*mass
        rhs = -matrix[:ng, -3]*velocity - matrix[:ng, -2]*acceleration
        gamma = np.linalg.solve(lhs, rhs)
        cl = (matrix[-1, :ng]+1j*omega*matrix[-1, ng:2*ng]) @ gamma
        cl += matrix[-1, -3]*velocity + matrix[-1, -2]*acceleration
        residual = float(np.max(abs(lhs @ gamma-rhs)))
        for alpha in INCIDENCES:
            mean = float(mean_slope*math.radians(alpha))
            responses.append(dict(k=k, alpha_deg=alpha, phase=phase.tolist(),
                # This is the prescribed linear incidence coordinate of the
                # source plot, not an independent nonlinear incidence check.
                incidence_axis_deg=(alpha + np.degrees(.5*k*np.sin(2*np.pi*phase))).tolist(),
                CL=(mean + np.real(cl*np.exp(2j*np.pi*phase))).tolist(), mean=mean,
                CL_real=float(cl.real), CL_imag=float(cl.imag),
                harmonic_residual=residual))
    return dict(responses=responses, mean_incidence_slope_per_rad=float(mean_slope),
                static_residual=float(static_residual), static_solves=1, harmonic_solves=2,
                matrix_assemblies=1, nonlinear_time_steps=0)


def assess(predicted):
    checks = []
    for row in predicted['responses']:
        expected = source_curve(row['k'], row['alpha_deg'], row['phase'])
        actual = complex(row['CL_real'], row['CL_imag'])
        scale = abs(expected['phasor'])
        point_errors = np.asarray(row['CL'])-expected['CL']
        mean_error = row['mean']-expected['mean']
        amplitude_error = abs(actual)/scale-1
        phase_error = math.degrees(np.angle(actual/expected['phasor']))
        points_passed = int(np.sum(abs(point_errors) <= GATES['waveform_fraction']*scale))
        passed = (points_passed == 100
            and abs(mean_error) <= max(GATES['mean_absolute'], GATES['mean_relative']*abs(expected['mean']))
            and abs(amplitude_error) <= GATES['amplitude_fraction']
            and abs(phase_error) <= GATES['phase_deg']
            and row['harmonic_residual'] < GATES['equation_residual'])
        checks.append(dict(k=row['k'], alpha_deg=row['alpha_deg'], passed=bool(passed),
            points_passed=points_passed, points_checked=100,
            reference_CL=expected['CL'].tolist(), reference_mean=expected['mean'],
            reference_dynamic_amplitude=scale,
            maximum_waveform_error_fraction=float(np.max(abs(point_errors))/scale),
            mean_error=float(mean_error), amplitude_error_fraction=float(amplitude_error),
            phase_error_deg=phase_error))
    return checks
