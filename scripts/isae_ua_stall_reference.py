"""Independent 2D heave reference with smooth stall leakage and circulation lag.

Drela steady theory (2015), Eqs. 202--204, and unsteady Eqs. 34--35, 43,
48--49. No production imports. This is the documented instantaneous leakage
model plus circulation lag, not a separate dynamic separation-state model.
"""
from dataclasses import dataclass
import math

import numpy as np
from scipy.integrate import solve_ivp
from scipy.optimize import brentq


@dataclass(frozen=True)
class Section:
    alpha_deg: float = 9.
    k: float = .94
    amplitude_ratio: float = .5  # Peak-to-peak A/c.
    speed: float = 10.
    chord: float = 1.
    clmax: float = 1.5
    clmin: float = -1.5
    stall_factor: float = 40.
    stall_width: float = .05

    def __post_init__(self):
        if not all(math.isfinite(v) for v in vars(self).values()):
            raise ValueError('Finite section settings required')
        if not (self.k > 0 and self.speed > 0 and self.chord > 0 and
                self.amplitude_ratio >= 0 and self.stall_factor >= 0 and
                self.stall_width > 0 and self.clmin < self.clmax and abs(self.alpha_deg) < 80):
            raise ValueError('Invalid section settings')
        if math.cos(self.alpha) <= self.amplitude_ratio*self.k*abs(math.sin(self.alpha)):
            raise ValueError('Forward chordwise flow required throughout')

    @property
    def alpha(self):
        return math.radians(self.alpha_deg)

    @property
    def period(self):
        return math.pi*self.chord/(self.speed*self.k)

    @property
    def heave(self):
        return np.array([-math.sin(self.alpha), 0., math.cos(self.alpha)])

    @property
    def wind(self):
        return np.array([math.cos(self.alpha), 0., math.sin(self.alpha)])

    def motion(self, time):
        omega = 2*self.speed*self.k/self.chord
        height = self.amplitude_ratio*self.chord/2
        return (height*math.cos(omega*time), -height*omega*math.sin(omega*time),
                -height*omega**2*math.cos(omega*time))

    def flow(self, velocity):
        ca, sa = math.cos(self.alpha), math.sin(self.alpha)
        return self.speed*ca+velocity*sa, self.speed*sa-velocity*ca, math.hypot(self.speed, velocity)

    def leakage_function(self, cl):
        def softplus(x):
            return max(x, 0.)+math.log1p(math.exp(-abs(x)))
        return self.stall_width*(softplus((cl-self.clmax)/self.stall_width)-
                                 softplus((self.clmin-cl)/self.stall_width))

    def leakage_derivative(self, cl):
        def sigmoid(x):
            e = math.exp(-abs(x))
            return 1/(1+e) if x >= 0 else e/(1+e)
        return sigmoid((cl-self.clmax)/self.stall_width)+sigmoid((self.clmin-cl)/self.stall_width)

    def rate(self, gamma, velocity):
        vx, vz, v = self.flow(velocity)
        cl = 2*gamma/(self.chord*v)
        return math.pi*v*vz/2-vx*gamma/(2*self.chord)-self.stall_factor*v*v*self.leakage_function(cl)/4

    def rate_derivative(self, gamma, velocity):
        vx, _, v = self.flow(velocity)
        return -(vx+self.stall_factor*v*self.leakage_derivative(2*gamma/(self.chord*v)))/(2*self.chord)

    def steady_circulation(self):
        # Forward flow makes the residual strictly decreasing in Gamma.
        extent = self.speed*self.chord*max(1., abs(self.clmin), abs(self.clmax))
        while self.rate(-extent, 0.) <= 0 or self.rate(extent, 0.) >= 0:
            extent *= 2
        return brentq(lambda g: self.rate(g, 0.), -extent, extent, xtol=1e-13, rtol=1e-14)

    def fields(self, gamma, velocity, acceleration, rate=None):
        vx, vz, v = self.flow(velocity)
        required_rate = self.rate(gamma, velocity)
        actual_rate = required_rate if rate is None else rate
        cl = 2*gamma/(self.chord*v)
        leak = v*self.stall_factor*self.leakage_function(cl)/(2*math.pi)
        tangency = vz-gamma*vx/(math.pi*self.chord*v)-2*actual_rate/(math.pi*v)
        cross = np.array([-vz, 0., vx])
        scale = 2/(self.speed**2*self.chord)
        circulation = scale*gamma*cross
        unsteady = scale*self.chord*actual_rate/v*cross
        apparent = np.array([0., 0., -math.pi*self.chord*acceleration*math.cos(self.alpha)/(2*self.speed**2)])
        profile = 4*tangency**2/(self.speed**2*v)*np.array([vx, 0., vz])
        total = circulation+unsteady+apparent+profile
        return dict(circulation=float(gamma), circulation_rate=float(actual_rate),
            required_rate=float(required_rate), section_cl=float(cl),
            leakage_velocity=float(leak), lag_corrected_tangency=float(tangency),
            residual=float((tangency-leak)/self.speed),
            CF=total.tolist(), CF_circulation=circulation.tolist(), CF_rate=unsteady.tolist(),
            CF_apparent=apparent.tolist(), CF_profile=profile.tolist(),
            CDp_fixed=float(4*tangency**2/self.speed**2),
            CL=float(total@self.heave), CD=float(total@self.wind),
            CL_instantaneous=float(total@(cross/v)*self.speed**2/v**2))


def trajectory(section, times, method='DOP853'):
    """Start from independently solved steady equilibrium; integrate cold history."""
    times = np.asarray(times, dtype=float)
    if (times.ndim != 1 or not len(times) or not np.isfinite(times).all() or
            times[0] != 0 or np.any(np.diff(times) <= 0) or method not in ('DOP853', 'Radau')):
        raise ValueError('Increasing times from zero and DOP853/Radau required')
    initial = section.steady_circulation()
    if times[-1] == 0:
        gamma, evaluations = [initial], 0
    else:
        result = solve_ivp(lambda t, y: [section.rate(float(y[0]), section.motion(t)[1])],
            (0., float(times[-1])), [initial], method=method, t_eval=times, rtol=2e-12, atol=1e-13)
        if not result.success:
            raise RuntimeError(result.message)
        gamma, evaluations = result.y[0], result.nfev
    rows = []
    for t, g in zip(times, gamma):
        z, w, a = section.motion(float(t))
        rows.append(dict(time=float(t), displacement=z, velocity=w, acceleration=a,
                         **section.fields(float(g), w, a)))
    return dict(rows=rows, method=method, ode_evaluations=evaluations,
                initial_circulation=initial, native_ASWING_comparison=False)
