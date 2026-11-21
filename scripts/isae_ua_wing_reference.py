"""Linearized 3D heave reference for UA-2 integration verification.

Spatial matrices come from production aerodynamics. Matrix-exponential time
propagation is independent of production BDF stepping. This establishes
integration parity, not independent 3D physics or native ASWING agreement.
"""
import argparse
from hashlib import sha256
import json
import math
from pathlib import Path
import sys
import time

import numpy as np
from scipy.linalg import expm

from isae_suite_unsteady import FREQUENCIES, model_text

ROOT = Path(__file__).resolve().parents[1]


def assemble(panels, *, aspect_ratio=10., speed=10., step=1e-4):
    sys.path.insert(0, str(ROOT))
    from openswing.asw import parse_asw
    from openswing.aero import FlightCondition, evaluate_aerodynamics
    from openswing.network import StaticNetwork

    base_condition = FlightCondition(speed=speed, alpha=0., mach=0., stall=False, aero_lag=True)
    net = StaticNetwork(parse_asw(model_text(aspect_ratio)), panels, base_condition, [0, 0, 0], [])
    rotations = np.broadcast_to(np.eye(3), (net.nn, 3, 3))
    meshes = net.deformed_meshes(net.rj, rotations, net.geometry(net.rj, rotations))
    qs = .5*net.model.constants[1]*speed**2*aspect_ratio
    points = net.point_positions(net.rj, rotations)
    def evaluate(gamma, rate, velocity=0., acceleration=0.):
        condition = FlightCondition(speed=math.hypot(speed, velocity),
            alpha=math.degrees(math.atan2(-velocity, speed)), mach=0.,
            acceleration=(0., 0., acceleration), stall=False, aero_lag=True)
        r = evaluate_aerodynamics(net.model, condition, meshes, point_positions=points,
            circulation=gamma, circulation_rate=rate)
        return np.r_[r['circulation_residual'], r['force'][2]/qs]
    z = np.zeros(net.ng)
    base = evaluate(z, z)
    columns = []
    for index in range(2*net.ng+2):
        args = [z.copy(), z.copy(), 0., 0.]
        if index < 2*net.ng:
            args[index//net.ng][index % net.ng] = step
        else:
            args[index-2*net.ng+2] = step
        columns.append((evaluate(*args)-evaluate(*[-v for v in args]))/(2*step))
    derivative = np.column_stack(columns)
    n = net.ng
    K, M = derivative[:n,:n], derivative[:n,n:2*n]
    rv, ra = derivative[:n,-2], derivative[:n,-1]
    operator = -np.linalg.solve(M, K)
    eigenvalues = np.linalg.eigvals(operator)
    return dict(settings=dict(panels=panels, aspect_ratio=aspect_ratio, speed=speed,
            alpha_deg=0., mach=0., stall=False, aero_lag=True, derivative_step=step),
        matrices=dict(K=K.tolist(), M=M.tolist(), rv=rv.tolist(), ra=ra.tolist(),
            fg=derivative[-1,:n].tolist(), fd=derivative[-1,n:2*n].tolist(),
            fv=float(derivative[-1,-2]), fa=float(derivative[-1,-1])),
        circulation_unknowns=n, production_evaluations=4*n+5, matrix_assemblies=1,
        zero_state_residual=float(np.max(np.abs(base))),
        maximum_eigenvalue_real=float(np.max(eigenvalues.real)),
        mass_condition_number=float(np.linalg.cond(M)),
        numerical_passed=bool(np.all(np.isfinite(derivative)) and np.max(np.abs(base)) < 1e-10
            and np.max(eigenvalues.real) < 0 and np.linalg.cond(M) < 1e10))


def arrays(reference):
    m = reference['matrices']
    return [np.asarray(m[k]) for k in ('K','M','rv','ra','fg','fd','fv','fa')]


def response(reference, times, *, amplitude_ratio, k):
    """Exact constant-matrix propagation of Gamma, sin(omega*t), cos(omega*t)."""
    K, M, rv, ra, fg, fd, fv, fa = arrays(reference)
    n = len(K)
    speed = reference['settings']['speed']
    omega, h = 2*speed*k, amplitude_ratio/2  # unit chord, A is peak-to-peak
    A = -np.linalg.solve(M, K)
    bv, ba = -np.linalg.solve(M, np.column_stack((rv,ra))).T
    augmented = np.zeros((n+2,n+2))
    augmented[:n,:n] = A
    augmented[:n,n] = -h*omega*bv
    augmented[:n,n+1] = -h*omega**2*ba
    augmented[n,n+1], augmented[n+1,n] = omega, -omega
    initial = np.zeros(n+2); initial[-1] = 1.
    rows = []
    for t in times:
        state = expm(augmented*float(t))@initial
        gamma = state[:n]
        w, acceleration = -h*omega*math.sin(omega*t), -h*omega**2*math.cos(omega*t)
        rate = A@gamma+bv*w+ba*acceleration
        cl = fg@gamma+fd@rate+fv*w+fa*acceleration
        residual = K@gamma+M@rate+rv*w+ra*acceleration
        rows.append(dict(time=float(t), circulation=gamma.tolist(), circulation_rate=rate.tolist(),
            velocity=w, acceleration=acceleration, CL=float(cl),
            residual=float(np.max(np.abs(residual)))))
    return rows


def harmonic(reference, frequencies=FREQUENCIES):
    K, M, rv, ra, fg, fd, fv, fa = arrays(reference)
    speed = reference['settings']['speed']
    rows = []
    for k in frequencies:
        omega = 2*speed*k
        velocity, acceleration = .5j*omega, -.5*omega**2
        gamma = np.linalg.solve(K+1j*omega*M, -rv*velocity-ra*acceleration)
        cl = (fg+1j*omega*fd)@gamma+fv*velocity+fa*acceleration
        rows.append(dict(k=float(k), CL_real=float(cl.real), CL_imag=float(cl.imag),
            amplitude=float(abs(cl)), phase_deg=float(np.angle(cl,deg=True)%360) if k else None))
    return rows


def compare(reference, samples, *, amplitude_ratio, k):
    expected = response(reference, [s['time'] for s in samples], amplitude_ratio=amplitude_ratio, k=k)
    rows = [dict(time=s['time'], expected=e, CL_error=s['CL_vertical']-e['CL'])
        for s,e in zip(samples,expected)]
    cl_scale = max(abs(e['CL']) for e in expected)
    gamma = np.array([s['circulation'] for s in samples])
    rate = np.array([s['circulation_rate'] for s in samples])
    expected_gamma = np.array([e['circulation'] for e in expected])
    expected_rate = np.array([e['circulation_rate'] for e in expected])
    return dict(scope='Linearized production 3D spatial equations, independent exact-matrix time propagation.',
        native_ASWING_comparison=False, independent_spatial_physics_reference=False, rows=rows,
        maximum_waveform_error_fraction=max(abs(r['CL_error']) for r in rows)/cl_scale,
        maximum_circulation_error_fraction=float(np.max(np.abs(gamma-expected_gamma))/np.max(np.abs(expected_gamma))),
        maximum_circulation_rate_error_fraction=float(np.max(np.abs(rate-expected_rate))/np.max(np.abs(expected_rate))),
        maximum_reference_residual=max(e['residual'] for e in expected))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--panels',type=int,choices=(20,40),required=True)
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Preserve completed references; choose a new path')
    paths = [*sorted((ROOT/'openswing').glob('*.py')), Path(__file__).resolve(),
        ROOT/'scripts/isae_suite_unsteady.py', ROOT/'.reference/asw_theory.txt',
        ROOT/'.reference/asw_uns_theory.txt']
    pins = {str(p.relative_to(ROOT)):sha256(p.read_bytes()).hexdigest() for p in paths}
    start = time.monotonic()
    reference = assemble(args.panels)
    reference.update(harmonic_response=harmonic(reference), seconds=time.monotonic()-start,
        source_sha256=pins, unchanged_code=all(sha256((ROOT/n).read_bytes()).hexdigest()==h for n,h in pins.items()),
        native_ASWING_comparison=False, independent_spatial_physics_reference=False,
        scope='UA-2 mirrored AR10 small-amplitude integration verification, zero mean incidence.',
        reconstruction='Full AR10 follows the primary paper semi-AR5; native deck/root-wall treatment unverified.')
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(reference,indent=2,allow_nan=False)+'\n')
    print(json.dumps({k:reference[k] for k in ('seconds','circulation_unknowns','maximum_eigenvalue_real','mass_condition_number','numerical_passed','unchanged_code')}))
    if not reference['numerical_passed'] or not reference['unchanged_code']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
