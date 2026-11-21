"""Mounted steady source sections coupled to the interval lifting-line model.

The aerodynamic Glauert-midpoint quadrature is retained explicitly. Its strip
wrench is re-expressed symmetrically at the structural endpoints so that the
mixed force/moment unknowns remain their physical endpoint averages (Eq. 51).
No aerodynamic force-point arm is added to the already translated Eq. 72
section couple. This policy does not initialize a different dynamic operator.
"""
import numpy as np

from .aero import AnalysisError, FlightCondition, evaluate_aerodynamics
from .equilibrium_state import warm_start_recipe
from .frozen_influence import FrozenInfluences
from .source_discrete import SourceSectionNetwork, COUPLED_POLICY, _solve_source_network
from .numerical_policy import validate_source_steady_constraints


def _cross(arm, value):
    """Cross product with either a force or a final axis of derivative columns."""
    if value.ndim == 2:
        return np.cross(arm, value)
    return np.moveaxis(np.cross(arm[:, None, :], np.moveaxis(value, 1, -1)), -1, 1)


class SourceCoupledNetwork(SourceSectionNetwork):
    structural_operator = COUPLED_POLICY
    compact_source_evaluation = True

    def __init__(self, model, panels, condition, gravity=None, loads=(), **kwargs):
        if condition is not None and not isinstance(condition, FlightCondition):
            raise AnalysisError('Source mounted analysis requires a FlightCondition.')
        super().__init__(model, panels, condition, gravity, loads, **kwargs)

    def _check_analysis_scope(self):
        if self.quiescent_density is not None:
            raise AnalysisError('Source mounted analysis does not support a separate quiescent fluid.')
        validate_source_steady_constraints(self.operating.constraints)
        if self.operating.count and self.condition is None:
            raise AnalysisError('Source mounted trim requires a FlightCondition.')
        if self.condition is not None and not isinstance(self.condition, FlightCondition):
            raise AnalysisError('Source mounted analysis requires a FlightCondition.')

    def steady_lifting_wrenches(self, mesh, force, moment):
        """Conservative primal/derivative transfer with actual N/M averages.

        Force and moment may have shape (interval,3) or (interval,3,column).
        The moment input is about mesh.rm, which is the aerodynamic section
        point, distinct from the arithmetic structural midpoint on coarse grids.
        Stepped reference axes are rejected by the source network constructor.
        """
        sl = self.beam_elements[mesh.beam.index]
        midpoint = (mesh.r0+mesh.r1)/2
        half_force = force/2
        half_couple = (moment+_cross(mesh.rm-midpoint, force))/2
        for ids in (self.a[sl], self.b[sl]):
            yield ids, half_force, half_couple

    def external(self, r, Q, meshes, gamma, condition, motion, operating_key, *,
                 local_motion=None, circulation_rate=None, gravity=None, _loads_only=False):
        self._check_motion(motion)
        if circulation_rate is not None:
            raise AnalysisError('Source mounted states do not support circulation rates or dynamic loads.')
        if local_motion is not None and any(np.any(value) for value in local_motion.values):
            raise AnalysisError('Source mounted analysis requires zero local elastic motion.')
        if condition is not None:
            self._check_motion(condition.motion())
        force, moment, _, masses, couples, ends = super().external(
            r, Q, meshes, np.empty(0), None, motion, operating_key,
            local_motion=None, gravity=gravity, _loads_only=_loads_only)
        return self.add_aerodynamic_loads(r, Q, meshes, gamma, condition, operating_key,
            force, moment, masses, couples, ends, _loads_only=_loads_only)

    def add_aerodynamic_loads(self, r, Q, meshes, gamma, condition, operating_key,
                              force, moment, masses, couples, ends, *,
                              local_motion=None, circulation_rate=None, _loads_only=False):
        """Add Glauert section loads to source box balances, once per state.

        Shared by the steady and dynamic source operators. Apparent-fluid and
        circulation-rate loads retain their aerodynamic section sampling;
        source real inertia remains in the caller's endpoint operator.
        """
        if condition is None:
            return force, moment, None, masses, couples, ends
        # Keep the source gravity cache independent of aerodynamic additions:
        # detailed f_reac reports must not count lift as a real-mass load.
        force, moment, couples, ends = [value.copy() for value in (force, moment, couples, ends)]
        key = (r.tobytes(), Q.tobytes(), gamma.tobytes(), operating_key,
               None if local_motion is None else local_motion.key(),
               None if circulation_rate is None else np.asarray(circulation_rate).tobytes(),
               _loads_only)
        if key != self.aero_key:
            if condition.freeze_influences and self.frozen_influences is None:
                self.frozen_influences = FrozenInfluences(self.model, self.meshes)
            engine_nodes = [self.node(*row[2:4]) for row in self.engines]
            engine_positions = [r[node]+Q[node]@(row[4:7]-self.rj[node])
                for row, node in zip(self.engines, engine_nodes)]
            self.aero_cached = evaluate_aerodynamics(self.model, condition, meshes, gamma,
                self.point_positions(r, Q), engine_positions, Q[engine_nodes],
                local_motion=local_motion, circulation_rate=circulation_rate,
                circulation_basis=self.circulation_basis,
                frozen_influences=self.frozen_influences, _loads_only=_loads_only,
                _tangent_influences=self.tangent_influences, _iteration_fields=self.iteration_fields,
                sensor_positions=[r[j]+Q[j]@(row[3:6]-self.rj[j])
                    for row in self.model.records.get('sensor', []) for j in [self.node(*row[1:3])]])
            self.aero_key = key
        aero = self.aero_cached
        for mesh in meshes:
            sl = self.beam_elements[mesh.beam.index]
            strips = aero['strips'][sl]
            f = np.array([strip['force'] for strip in strips])
            m = np.array([strip['moment'] for strip in strips])
            for end, (ids, nf, nm) in enumerate(self.steady_lifting_wrenches(mesh, f, m)):
                np.add.at(force, ids, nf)
                np.add.at(moment, ids, nm)
                ends[sl, end] += nf
                couples[sl, end] += nm
        for row, position, value in zip(self.weights, self.point_positions(r, Q), aero['point_forces']):
            node = self.node(*row[:2])
            value = np.asarray(value)
            force[node] += value
            moment[node] += np.cross(position-r[node], value)
        # Radius steps are concentrated body loads, separate from the
        # distributed slender-body wrench already included in the strip sum.
        for shoulder in aero['body_shoulders']:
            node = self.node(shoulder['beam'], shoulder['t'])
            value = np.asarray(shoulder['force'])
            force[node] += value
            moment[node] += np.cross(np.asarray(shoulder['position'])-r[node], value)
        # Engines are concentrated loads at their actual rotated pylons, not
        # distributed section loads. Transfer the complete engine force/couple
        # once to its attachment, preserving moment about every reference.
        for engine in aero['engines']:
            node = self.node(engine['beam'], engine['t'])
            force[node] += engine['force']
            moment[node] += engine['moment']+np.cross(
                np.asarray(engine['position'])-r[node], engine['force'])
        return force, moment, aero, masses, couples, ends


def solve_source_coupled(model, condition, panels=24, *, gravity=None, loads=(),
                         tolerance=1e-8, continuation_steps=4, initial_state=None, progress=None,
                         strut_mode='bilateral', operating_constraints=()):
    """Nonrotating mounted equilibrium/trim with the full source section laws."""
    net = SourceCoupledNetwork(model, panels, condition, gravity, loads, strut_mode=strut_mode,
        operating_constraints=operating_constraints,
        mesh_recipe=warm_start_recipe(model, panels, initial_state))
    return _solve_source_network(net, tolerance, continuation_steps, initial_state, progress)
