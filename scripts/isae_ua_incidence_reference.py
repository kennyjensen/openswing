"""Independent finite-incidence section reference for freestream-normal heave.

Flat chord/span/normal body axes are x/y/z. The mean incident flow direction
is e=(cos(alpha),0,sin(alpha)); plunge is along H=(-sin(alpha),0,cos(alpha)).
This implements steady Eqs.155-157 and unsteady Eqs.34-35,43,49, with no
production imports, no stall, no empirical mean offsets and no frozen wind.
"""
import math

import numpy as np
from scipy.integrate import quad, solve_ivp


def kinematics(time, *, amplitude_ratio, k, speed=10., chord=1.):
    omega = 2*speed*k/chord
    height = amplitude_ratio*chord/2
    return height*math.cos(omega*time), -height*omega*math.sin(omega*time), -height*omega**2*math.cos(omega*time)


def fields(gamma, velocity, acceleration, *, alpha_deg, speed=10., chord=1., rate=None):
    """Forces normalized with fixed mean dynamic pressure, per unit span."""
    alpha = math.radians(alpha_deg)
    ca, sa = math.cos(alpha), math.sin(alpha)
    vx, vz = speed*ca + velocity*sa, speed*sa - velocity*ca
    local_speed = math.hypot(speed, velocity)
    required_rate = math.pi/2*local_speed*vz - vx*gamma/(2*chord)
    actual_rate = required_rate if rate is None else rate
    tangency = vz - gamma*vx/(math.pi*chord*local_speed) - 2*actual_rate/(math.pi*local_speed)
    cross = np.array([-vz, 0., vx])
    scale = 2/(speed**2*chord)
    circulation = scale*gamma*cross
    unsteady = scale*chord*actual_rate/local_speed*cross
    apparent = np.array([0., 0., -math.pi*chord*acceleration*ca/(2*speed**2)])
    # Steady Eq.73: zero on the differential circulation solution, retained
    # here so an arbitrary supplied rate has the documented off-solution load.
    profile = 4*tangency**2/(speed**2*local_speed)*np.array([vx, 0., vz])
    total = circulation + unsteady + apparent + profile
    heave = np.array([-sa, 0., ca])
    mean_wind = np.array([ca, 0., sa])
    instantaneous_normal = cross/local_speed
    return dict(circulation=float(gamma), circulation_rate=float(required_rate),
        relative_velocity=[vx, 0., vz], local_speed=local_speed,
        effective_alpha_deg=math.degrees(math.atan2(vz, vx)), residual=tangency/local_speed,
        CF_circulation=circulation.tolist(), CF_rate=unsteady.tolist(), CF_apparent=apparent.tolist(),
        CF_profile=profile.tolist(), CF=total.tolist(),
        CL=float(total@heave), CD=float(total@mean_wind),
        CL_instantaneous=float(total@instantaneous_normal*speed**2/local_speed**2),
        CL_circulation=float(circulation@heave), CL_rate=float(unsteady@heave),
        CL_apparent=float(apparent@heave))


def steady_circulation(*, alpha_deg, speed=10., chord=1.):
    return math.pi*chord*speed*math.tan(math.radians(alpha_deg))


def trajectory(times, *, alpha_deg, amplitude_ratio=.5, k=.94, speed=10., chord=1.,
               boundary='periodic', method='quadrature'):
    """Integrating-factor quadrature or an independent adaptive ODE solution.

    boundary='steady' starts from the attached steady circulation at t=0;
    boundary='periodic' solves the scalar one-period fixed-point condition.
    Both numerical methods calculate that boundary from their own integral.
    """
    times = np.asarray(times, dtype=float)
    if (times.ndim != 1 or not len(times) or not np.isfinite(times).all()
            or times[0] < 0 or np.any(np.diff(times) <= 0)
            or not (0 <= amplitude_ratio and k > 0 and speed > 0 and chord > 0)
            or not abs(alpha_deg) < 80):
        raise ValueError('Finite increasing times and valid forward-flow section settings required')
    if boundary not in ('steady', 'periodic') or method not in ('quadrature', 'DOP853', 'Radau'):
        raise ValueError('Use a declared boundary and integration method')
    alpha = math.radians(alpha_deg)
    ca, sa = math.cos(alpha), math.sin(alpha)
    omega = 2*speed*k/chord
    height = amplitude_ratio*chord/2
    if speed*ca <= height*omega*abs(sa):
        raise ValueError('This reference requires positive chordwise incident velocity throughout')
    period = 2*math.pi/omega

    def primitive(t):
        return (speed*ca*t + sa*height*(math.cos(omega*t)-1))/(2*chord)

    def forcing(t):
        w = -height*omega*math.sin(omega*t)
        return math.pi/2*math.hypot(speed, w)*(speed*sa-w*ca)

    maximum_quad_error = 0.

    def convolution(t):
        nonlocal maximum_quad_error
        if t == 0:
            return 0.
        value, error = quad(lambda s: math.exp(primitive(s)-primitive(t))*forcing(s),
                            0., t, epsabs=1e-12, epsrel=2e-12, limit=200)
        maximum_quad_error = max(maximum_quad_error, error)
        return value

    def rhs(t, gamma):
        w = -height*omega*math.sin(omega*t)
        # Explicit variable-coefficient ODE, independent of the quadrature
        # integrating factor and of fields' force evaluation.
        return math.pi/2*math.hypot(speed, w)*(speed*sa-w*ca)-(speed*ca+w*sa)*gamma/(2*chord)

    evaluations = 0

    def integrate(end, initial, output_times=None):
        nonlocal evaluations
        result = solve_ivp(rhs, (0., end), [initial], method=method,
                           t_eval=output_times, rtol=2e-12, atol=1e-13)
        if not result.success:
            raise RuntimeError(result.message)
        evaluations += result.nfev
        return result.y[0]

    if boundary == 'steady':
        initial = steady_circulation(alpha_deg=alpha_deg, speed=speed, chord=chord)
    else:
        inhomogeneous = convolution(period) if method == 'quadrature' else integrate(period, 0.)[-1]
        initial = inhomogeneous/(-math.expm1(-speed*ca*period/(2*chord)))
    if method == 'quadrature':
        gamma = [initial*math.exp(-primitive(t))+convolution(t) for t in times]
    elif times[-1] == 0:
        gamma = [initial]
    else:
        gamma = integrate(float(times[-1]), initial, times)
    rows = []
    for t, g in zip(times, gamma):
        z, w, a = kinematics(float(t), amplitude_ratio=amplitude_ratio, k=k, speed=speed, chord=chord)
        rows.append(dict(time=float(t), displacement=z, velocity=w, acceleration=a,
                         **fields(float(g), w, a, alpha_deg=alpha_deg, speed=speed, chord=chord)))
    return dict(period=period, initial_circulation=float(initial), rows=rows,
        maximum_quadrature_error_estimate=maximum_quad_error, method=method, boundary=boundary,
        ode_evaluations=evaluations, native_ASWING_comparison=False,
        qualifications='Attached-flow section limit; freestream-normal plunge and fixed freestream-normal lift; no fitted offsets.')
