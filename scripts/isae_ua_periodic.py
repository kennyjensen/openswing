"""Independent attached-flow periodic section reference and Fourier measurements.

The reference uses the same published section equations as the first-cycle
study, with a periodic boundary condition derived from their decay kernel.
It imports no production solver. A/c is peak-to-peak displacement/chord.
"""
import math
import numpy as np

from isae_ua_section_reference import cold_heave, heave_kinematics, section_load


def periodic_reference(times, *, amplitude_ratio, k, speed=10.):
    """Return one phase-aligned cycle; no simulated startup is discarded here."""
    period = math.pi/(speed*k)
    times = np.asarray(times, dtype=float)
    if np.any(times < -1e-12) or np.any(times > period+1e-12):
        raise ValueError('Reference times must cover at most one cycle')
    settings = dict(amplitude_ratio=amplitude_ratio, k=k, speed=speed)
    decay = speed/2
    initial = cold_heave(period, **settings)['circulation']/(-math.expm1(-decay*period))
    rows = []
    for value in times:
        t = float(np.clip(value, 0., period))
        gamma = cold_heave(t, **settings)['circulation']+initial*math.exp(-decay*t)
        z, velocity, acceleration = heave_kinematics(t, **settings)
        rows.append(dict(time=t, z=z, velocity=velocity, acceleration=acceleration,
                         **section_load(gamma, velocity, acceleration, speed=speed)))
    return dict(period=period, initial_circulation=initial, rows=rows)


def fourier(times, values, period):
    """Trapezoidal Fourier integrals over a complete cycle, with both ends.

    The phasor convention is real(H exp(i omega t)). The returned wrapped
    phase therefore agrees with 180+arg(B) for the source's linear CL=-A*B.
    Unequal endpoint values are retained, rather than silently periodized.
    """
    times, values = np.asarray(times), np.asarray(values)
    if times.ndim != 1 or values.shape != times.shape or len(times) < 5:
        raise ValueError('One-dimensional cycle samples required')
    if not np.isfinite(times).all() or not np.isfinite(values).all():
        raise ValueError('Finite cycle samples required')
    if not period > 0 or abs(times[-1]-times[0]-period) > 1e-10*period:
        raise ValueError('A complete cycle with both endpoints is required')
    widths = np.diff(times)
    if np.any(widths <= 0):
        raise ValueError('Cycle times must increase strictly')
    def integral(v):
        return float(np.sum(widths*(v[:-1]+v[1:])*.5)/period)
    phases = 2*math.pi*(times-times[0])/period
    harmonics = []
    for number in (1, 2, 3):
        cosine = 2*integral(values*np.cos(number*phases))
        sine = 2*integral(values*np.sin(number*phases))
        harmonics.append(dict(order=number, cosine=cosine, sine=sine,
            amplitude=math.hypot(cosine, sine), phase_deg=math.degrees(math.atan2(-sine, cosine))%360))
    return dict(mean=integral(values), harmonics=harmonics,
                endpoint_difference=float(values[-1]-values[0]))


def phase_difference(a, b):
    return (a-b+180)%360-180
