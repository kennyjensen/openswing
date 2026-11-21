"""Expose the finite-BDF limit of continuous rigid-pylon equivalence.

Use rigid nodal pose histories, source-compatible constant Euler yaw rate,
BDF nodal velocity/acceleration, and the production LocalMotion pylon rule.
The independent reference is the complex BDF symbol of a rotating vector.
This is a prescribed-history consistency probe, not an integrated solution.
"""
import cmath
import numpy as np

from openswing.local_motion import LocalMotion


def bdf_difference(values, h, order):
    if order == 1:
        return (values[0]-values[1])/h
    if order == 2:
        return (1.5*(values[0]-values[1])+.5*(values[2]-values[1]))/h
    raise ValueError('Only BDF1 and BDF2 are covered')


def probe(order, h, omega=.7):
    if order not in (1, 2) or not np.isfinite(h) or h <= 0:
        raise ValueError('Finite positive time step and BDF1/2 required')
    theta = .37
    anchors = [np.array([0., .3521, 0.]), np.array([0., .364, 0.])]
    point = np.array([.03, .4, .02])
    rate = np.array([0., 0., omega])
    def rotate(p, angle):
        c, s = np.cos(angle), np.sin(angle)
        return np.array([c*p[0]-s*p[1], s*p[0]+c*p[1], p[2]])
    p = rotate(point, theta)
    motions = []
    for anchor in anchors:
        positions = np.array([rotate(anchor, theta-i*omega*h) for i in range(2*order+1)])
        velocities = np.array([bdf_difference(positions[i:i+order+1], h, order) for i in range(order+1)])
        acceleration = bdf_difference(velocities, h, order)
        local = LocalMotion(positions[0], velocities[0], rate, acceleration, np.zeros(3))
        motions.append((local.velocity_at(p), local.acceleration_at(p)))
    actual_v = motions[0][0]-motions[1][0]
    actual_a = motions[0][1]-motions[1][1]
    z = cmath.exp(-1j*omega*h)
    symbol = (1-z)/h if order == 1 else (3-4*z+z*z)/(2*h)
    delta = rotate(anchors[0]-anchors[1], theta)
    value = complex(delta[0], delta[1])
    cv, ca = (symbol-1j*omega)*value, (symbol**2+omega**2)*value
    expected_v = np.array([cv.real, cv.imag, 0.])
    expected_a = np.array([ca.real, ca.imag, 0.])
    error_v = float(np.max(abs(actual_v-expected_v)))
    error_a = float(np.max(abs(actual_a-expected_a)))
    if error_v > 2e-13 or error_a > 2e-11:
        raise ValueError('Production pylon difference disagrees with the independent BDF symbol')
    return dict(order=order, h=h, omega=omega, anchor_distance=float(np.linalg.norm(anchors[0]-anchors[1])),
                velocity_difference=float(np.linalg.norm(actual_v)), acceleration_difference=float(np.linalg.norm(actual_a)),
                velocity_oracle_error=error_v, acceleration_oracle_error=error_a,
                integrated_physical_solution=False)


def refinement(order):
    rows = [probe(order, h) for h in (.04, .02, .01)]
    ratios = {key: [rows[i][key]/rows[i+1][key] for i in (0, 1)]
              for key in ('velocity_difference', 'acceleration_difference')}
    if any(not (2**order*.99 < ratio < 2**order*1.01) for values in ratios.values() for ratio in values):
        raise ValueError('Rigid-anchor BDF discrepancy does not decrease at the expected order')
    return dict(order=order, rows=rows, halving_ratios=ratios,
                exact_finite_step_equivalence=False, continuous_limit_equivalence=True)
