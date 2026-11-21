"""Radau chart in Earth position and velocity defects from target histories.

E = P - G(t), W = R U - G'(t), with G zero outside the selected axes.
The physical state is reconstructed at every stage. The original force,
moment, structure, circulation, actuator and controller equations are retained.
The two origin kinematic rows are E' = W and W' = R a_origin - G''.
These are equivalent to the original continuous equations on the rotational
kinematic constraint, without projecting accepted position or velocity.
"""
from copy import copy
import numpy as np
from .nonlinear_initial import InitialSystem
from .forcing import RightLimitForcing
from .local_motion import left_jacobian
from .network import exp
from .vector_ops import cross3


POLICY = 'earth-origin-position-defect-radau-v1'


class PositionHistoryRadauChart(InitialSystem):
    def __init__(self, system, seed, frame):
        local = copy(system)
        if system.forcing is not None:
            local.forcing = RightLimitForcing(system.forcing, seed.time)
        super().__init__(local, seed, frame, apply_forcing=True)
        self.lift = system.position_lift
        self.lift.validate_sample(seed, local.forcing)
        self.E0, self.W0 = self.lift.coordinates(seed, seed.position_history)

    def residual(self, z, rate, time, *, detail=False, side='right'):
        n = self.network; j = self.frame_start
        sample = self.lift.sample(time, self.system.forcing, side)
        R = self.seed.orientation @ exp(z[j+9:j+12])
        W = self.W0 + self.V*z[j:j+3]
        U = R.T @ (W + np.asarray(sample.rate))
        physical = z.copy(); physical_rate = rate.copy()
        physical[j:j+3] = U/self.V - self.base[j:j+3]
        physical[j+6:j+9] = (self.E0 + self.L*z[j+6:j+9] + np.asarray(sample.value))/self.L - self.base[j+6:j+9]
        omega_chart = left_jacobian(-z[j+9:j+12]) @ rate[j+9:j+12]
        physical_rate[j:j+3] = (R.T @ (self.V*rate[j:j+3] + np.asarray(sample.acceleration)) - cross3(omega_chart, U))/self.V
        physical_rate[j+6:j+9] = rate[j+6:j+9] + np.asarray(sample.rate)/self.L
        result, state, options = super().residual(physical, physical_rate, time, side=side, detail=True)
        _, motion, _ = n.operating.apply(state.x[n.operating_start:],
            condition_override=options['condition_override'], motion_override=options['motion_override'])
        result[j:j+3] = (self.V*rate[j:j+3] - state.orientation @ motion.at(np.zeros(3), n.model.reference[2]) + np.asarray(sample.acceleration))/self.system.A
        result[j+6:j+9] = (self.L*rate[j+6:j+9] - W)/self.V
        state.position_history = sample
        return (result, state, options) if detail else result

    def rate_guess(self, z):
        rate = super().rate_guess(z)
        _, state, options = self.residual(z, np.zeros(self.size), self.seed.time, detail=True)
        n = self.network; j = self.frame_start
        _, motion, _ = n.operating.apply(state.x[n.operating_start:],
            condition_override=options['condition_override'], motion_override=options['motion_override'])
        rate[j:j+3] = (state.orientation @ motion.at(np.zeros(3), n.model.reference[2]) - np.asarray(state.position_history.acceleration))/self.V
        rate[j+6:j+9] = (self.W0 + self.V*z[j:j+3])/self.L
        return rate
