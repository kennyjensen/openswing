"""Local motion derivatives: exact polynomial coefficients plus flow chain rule.

The incident-velocity partial holds geometry, circulation and frame motion
fixed. Its complementary partial retains ALL explicit elastic kinematics,
including gyroscopic, Coriolis, apparent-mass and material damping terms.
Neither partial alone is a physical tangent.
"""
import numpy as np
from scipy.sparse import csc_matrix, hstack
from .structured_static import (IterationFields, structural_column_rows, coloring,
    StructuredTangentUnavailable, acceleration_load_constraints, frame_load_pattern)
from .local_motion import NetworkMotion
from .circulation_tangent import flow_load_columns, CirculationDerivativeUnavailable
from .vector_ops import cross3


class LocalRateUnavailable(ValueError):
    pass


class RateFields(IterationFields):
    def __init__(self):
        super().__init__()
        self.capture_circulation = self.capture_rate_fields = True
        self.incident = {}
        self.incident_bytes = 0

    def incident_velocity(self, name, velocity):
        if self.phase == 'capture':
            previous = self.incident.get(name)
            storage = velocity.nbytes-(0 if previous is None else previous.nbytes)
            if self.bytes+self.incident_bytes+storage > 64*1024**2:
                raise LocalRateUnavailable('Local-motion field storage exceeds its budget.')
            self.incident[name] = velocity.copy()
            self.incident_bytes += storage
            return velocity
        if name not in self.incident:
            raise LocalRateUnavailable('Uncaptured local-motion incident velocity.')
        return self.incident[name].copy()


class RateFlow:
    def __init__(self, net, data, motion):
        self.sample = np.zeros((len(data['gamma']), 1))
        self.motion = motion
        self.engines = []
        self.meshes = {mesh.beam.index: mesh for mesh in net.meshes}

    def velocity(self, name, points):
        motion = self.motion
        if name in ('cp', 'hv', 'axis'):
            value = motion.surface().velocity_at(points)
        elif name[0] == 'body':
            value = motion.body(self.meshes[name[1]]).velocity.reshape(-1, 3)
        elif name[0] == 'point':
            value = motion.point('weight', name[1]).velocity_at(points)
        elif name[0] == 'shoulder':
            value = motion.station(*name[1:]).velocity_at(points)
        else:
            raise LocalRateUnavailable('Unsupported local-motion flow receiver.')
        return -value[..., None]


def local_rate_columns(system, *, amplitude=1.):
    """Return eligible local velocity/rate columns and their state indices.

    Symmetric finite amplitudes extract a polynomial coefficient, rather than
    approximate the derivative of the nonlinear incident-flow loads. Nonlinear
    load-dependent constraints and controllers keep full stencils. Canonical
    acceleration/net-load rows use each column's external nodal wrenches;
    these shared rows do not enter the local coloring. Engine-mount columns
    keep full stencils, including their nonlocal jet response.
    """
    n = system.network
    if (n.condition is None or n.hinges or not acceleration_load_constraints(n)
            or system.feedback is not None or n.iteration_fields is not None):
        raise LocalRateUnavailable('This context requires full local-motion stencils.')
    if not np.isfinite(amplitude) or amplitude <= 0:
        raise LocalRateUnavailable('Invalid local-motion coefficient amplitude.')
    zero = np.zeros(system.size)
    fields = RateFields()
    fields.capture_frame_loads = bool(n.operating.count)
    n.iteration_fields = fields; n.aero_key = None
    try:
        system.residual(zero, zero)
        data, mechanics = fields.circulation_aero, fields.circulation_mechanics
        if data is None or mechanics is None:
            raise LocalRateUnavailable('Missing local-motion load capture.')
        fields.phase = 'local_rates'; fields.capture_circulation = False
        engine_nodes = {n.node(*row[2:4]) for row in n.engines}
        layout = [(part, node, axis) for part in range(2)
            for node in range(n.nn) if node not in engine_nodes for axis in range(3)]
        columns = np.array([system.velocity_start+3*n.nn*part+3*node+axis
            for part, node, axis in layout], dtype=int)
        if not len(columns):
            raise LocalRateUnavailable('All local-motion columns touch an engine mount.')
        structural = structural_column_rows(n)
        load_nodes, load_components, load_scales = frame_load_pattern(n, structural)
        supports = [np.unique(np.r_[structural[6*node+3*part+axis],
            system.velocity_start+3*n.nn*part+3*node+axis])
            for part, node, axis in layout]
        groups = coloring(supports)
        result = [None]*len(columns)
        for group in groups:
            delta = zero.copy(); delta[columns[group]] = amplitude
            # At fixed incident velocity the remaining residual is at most
            # quadratic in these rates; symmetric extraction is exact.
            plus = system.residual(delta, zero)
            plus_loads = fields.frame_loads.copy() if fields.capture_frame_loads else None
            minus = system.residual(-delta, zero)
            load_coefficient = None if plus_loads is None else (plus_loads-fields.frame_loads)/(2*amplitude)
            coefficient = (plus-minus)/(2*amplitude)
            direction = zero.copy(); direction[columns[group]] = 1.
            state, _, _ = system.unpack(direction, zero)
            motion = NetworkMotion(n, mechanics['r'], mechanics['Q'], state.u,
                state.w, np.zeros_like(state.u), np.zeros_like(state.w))
            flow = RateFlow(n, data, motion)
            flow_coefficient = flow_load_columns(n, fields, flow, 1.)[:, 0]
            coefficient[:n.size] += flow_coefficient
            if load_coefficient is not None:
                # These rows contain only external flow-load derivatives, not
                # internal beam forces or joint reactions. Shift their nodal
                # couples to the same reference used by captured frame loads.
                start = 6*n.ne
                force = n.F*flow_coefficient[start:start+3*n.nn].reshape(n.nn, 3)
                moment = n.F*n.L*flow_coefficient[start+3*n.nn:start+6*n.nn].reshape(n.nn, 3)
                load_coefficient += np.c_[force, moment+cross3(mechanics['r']-n.model.reference[1], force)]
            for k in group:
                value = np.zeros(system.size)
                value[supports[k]] = coefficient[supports[k]]
                if load_coefficient is not None:
                    part, node, axis = layout[k]
                    wrench = load_coefficient[load_nodes[6*node+3*part+axis]].sum(axis=0)
                    value[n.operating_start:n.size] = wrench[load_components]/load_scales
                result[k] = csc_matrix(value[:, None])
        matrix = hstack(result, format='csc')
        if not np.all(np.isfinite(matrix.data)):
            raise LocalRateUnavailable('Nonfinite local-motion derivative.')
        return matrix, columns, dict(columns=len(columns), groups=len(groups),
            engine_mount_columns=6*len(engine_nodes),
            operating_load_rows=n.operating.count,
            load_evaluations=1+2*len(groups), coefficient_amplitude=amplitude,
            method='quadratic local-motion coefficient and analytic incident-flow chain rule')
    except (StructuredTangentUnavailable, CirculationDerivativeUnavailable) as exc:
        raise LocalRateUnavailable(str(exc)) from exc
    finally:
        n.iteration_fields = None; n.aero_key = None
