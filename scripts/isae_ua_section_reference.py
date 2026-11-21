"""Independent nonlinear 2D heave limit of Drela's live-influence equations.

Steady eqs. 155-157 place the control point c/2 downstream along instantaneous
wind. Unsteady eqs. 34-35, 43 and 49 supply circulation/rate/apparent loads.
No production geometry, vortex kernel, residual or integrator is imported.
This is an attached-flow equation check, not an archived native ASWING run.
"""
import math
from scipy.integrate import quad


def heave_kinematics(t, *, amplitude_ratio, k, speed, chord=1.):
    omega, height = 2*speed*k/chord, .5*amplitude_ratio*chord
    return (height*math.cos(omega*t), -height*omega*math.sin(omega*t),
            -height*omega**2*math.cos(omega*t))


def section_load(gamma, velocity, acceleration, *, speed, chord=1.):
    # At cp=(c/2)*(V,0,-w)/U the infinite bound line gives
    # V_ind,z=-Gamma*V/(pi*c*U). Eq49 therefore gives
    # Gamma_dot+V/(2c)*Gamma=-(pi/2)*U*w, U=hypot(V,w).
    crossflow = math.hypot(speed, velocity)
    rate = -.5*(speed*gamma/chord+math.pi*crossflow*velocity)
    circulatory = 2*gamma/(speed*chord)
    rate_lift = 2*rate/(speed*crossflow)
    added = -math.pi*chord*acceleration/(2*speed**2)
    return dict(circulation=gamma, circulation_rate=rate, crossflow_speed=crossflow,
        CL_circulation=circulatory, CL_rate=rate_lift, CL_added=added,
        CL=circulatory+rate_lift+added)


def cold_heave(t, *, amplitude_ratio, k, speed, chord=1.):
    """Convolve the documented ODE with prescribed motion, Gamma(0)=0."""
    for name, value in (('time',t),('amplitude',amplitude_ratio),('k',k),('speed',speed),('chord',chord)):
        if not math.isfinite(value) or (value < 0 if name == 'time' else value <= 0):
            raise ValueError('Invalid nonlinear section '+name)
    def integrand(s):
        _, velocity, _ = heave_kinematics(s, amplitude_ratio=amplitude_ratio, k=k, speed=speed, chord=chord)
        return -.5*math.pi*math.hypot(speed,velocity)*velocity*math.exp(-(t-s)*speed/(2*chord))
    gamma, error = quad(integrand, 0., t, epsabs=1e-13, epsrel=2e-12, limit=200)
    z, velocity, acceleration = heave_kinematics(t, amplitude_ratio=amplitude_ratio,k=k,speed=speed,chord=chord)
    return dict(section_load(gamma,velocity,acceleration,speed=speed,chord=chord),
        z=z, velocity=velocity, acceleration=acceleration, quadrature_error_estimate=error)


def compare(samples, *, amplitude_ratio, k, speed):
    rows=[]
    for s in samples:
        expected=cold_heave(s['time'],amplitude_ratio=amplitude_ratio,k=k,speed=speed)
        rows.append(dict(time=s['time'],expected=expected,
            CL_error=s['CL_vertical']-expected['CL'],
            nonlinear_minus_linear_CL=expected['CL']-s['expected']['CL']))
    scale=max(abs(r['expected']['CL']) for r in rows)
    return dict(scope='Independent attached-flow 2D nonlinear equations; live wind, no stall, unit chord.',
        native_ASWING_comparison=False, rows=rows,
        maximum_waveform_error_fraction=max(abs(r['CL_error']) for r in rows)/scale,
        maximum_nonlinear_linear_difference_fraction=max(abs(r['nonlinear_minus_linear_CL']) for r in rows)/scale,
        maximum_quadrature_error_estimate=max(r['expected']['quadrature_error_estimate'] for r in rows))
