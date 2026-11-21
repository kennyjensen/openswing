"""Declared clamped thin-wing boundaries on an ideal solid image plane.

Physical evaluations admit only roundoff at a complete endpoint chord already
mounted in the wall.  Jacobians use a separate, bounded smooth continuation of
that endpoint's geometry.  It is never a clearance waiver for Newton trials.
The six clamp equations remain in the mixed system: admissible increments have
zero root pose, so the off-constraint extension cannot change their solution.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from functools import wraps

import numpy as np

from .geometry import surface_frame
from .ground import GroundIntersectionError, GroundPlane
from .point_objects import analysis_weight_station
from .point_objects import active_weights


_PROBE = ContextVar('openswing_wall_root_probe', default=None)


def _plane_key(plane):
    return plane.flag, plane.normal.tobytes(), plane.offset


def _clamps(model):
    return {(int(row[0]), float(row[1])) for row in model.records.get('ground', [])
            if int(row[-1]) == 0} if model is not None else set()


def _edges(beam, t, position, chord_direction, side):
    chord = beam.value('chord', t, side=side)
    axis = beam.value('Xax', t, side=side)
    return np.stack((position - chord * axis * chord_direction,
                     position + chord * (1 - axis) * chord_direction))


@dataclass(frozen=True)
class _Probe:
    model: object
    plane: tuple
    roots: dict
    points: dict
    radius: float
    root_motion: bool = False


class WallRootBoundary:
    """Per-evaluation contact identities; no geometry or image field is moved."""

    def __init__(self, plane, meshes, model):
        self.plane, self.model = plane, model
        self.roots, self.points = {}, {}
        self.clamps = _clamps(model)
        candidate = _PROBE.get()
        self.probe = candidate if candidate is not None and candidate.model is model else None
        if self.probe is not None and _plane_key(plane) != self.probe.plane:
            raise GroundIntersectionError('Wall-root derivative probe changed the image plane.')
        scale = max([abs(plane.offset)] + [float(np.max(np.abs(p), initial=0.))
                    for mesh in meshes for p in (mesh.r0, mesh.r1)] +
                    [float(np.max(mesh.beam.value('chord', mesh.tm), initial=0.))
                     for mesh in meshes if mesh.beam.lifting], default=0.)
        self.roundoff = 32 * np.finfo(float).eps * scale

    def surface(self, mesh, t, position, frames, side):
        """Return one exemption per complete chord; interior stations get none."""
        mask = np.zeros(len(t), dtype=bool)
        beam = mesh.beam
        if self.plane.flag != 1 or not self.clamps:
            return mask
        for i, station in enumerate(t):
            key = (beam.index, float(station))
            if key not in self.clamps or station not in beam.domain:
                continue
            current = _edges(beam, station, position[i], frames[i, :, 0], side)
            if self.probe is not None:
                before = self.probe.roots.get(key)
                if before is None:
                    continue
                if np.max(np.linalg.norm(current - before, axis=1)) > self.probe.radius:
                    raise GroundIntersectionError('Wall-root derivative probe exceeds its regular geometry neighborhood.')
            else:
                # A clamp elsewhere that happens to reach the wall is not a
                # declared wall mount. Check the undeformed material root too.
                jig = _edges(beam, station, beam.position(station, side=side),
                             surface_frame(beam, station, side)[:, 0], side)
                if (np.max(abs(self.plane.distance(jig))) > self.roundoff or
                        np.max(abs(self.plane.distance(current))) > self.roundoff):
                    continue
            mask[i] = True
            self.roots[key] = current.copy()
        return mask

    def point_mask(self, points):
        mask = np.zeros(len(points), dtype=bool)
        if self.model is None:
            return mask
        rows = active_weights(self.model)
        if len(rows) != len(points):
            raise GroundIntersectionError('Point geometry does not match the wall-root model.')
        for i, (row, point) in enumerate(zip(rows, points)):
            key = (int(row[0]), analysis_weight_station(self.model, row))
            if key not in self.roots or row[6] != 0 or row[7] != 0:
                continue
            if self.probe is not None:
                before = self.probe.points.get(i)
                if before is None:
                    continue
                if np.linalg.norm(point - before) > self.probe.radius:
                    raise GroundIntersectionError('Wall-root point derivative exceeds its regular geometry neighborhood.')
            elif (abs(self.plane.distance(row[2:5])) > self.roundoff or
                  abs(self.plane.distance(point)) > self.roundoff):
                continue
            mask[i] = True
            self.points[i] = np.array(point, copy=True)
        return mask


def validate_wall_flow(plane, condition, model, gust, *, local_motion=None, circulation_rate=None):
    """A stationary solid-wall mount needs compatible imposed flow.

    Existing image algebra handles vortex/source fields. It does not reflect
    a prescribed gust or propulsive jet, or repair normal freestream onset.
    """
    boundary = getattr(plane, '_wall_boundary', None)
    if boundary is None or not boundary.roots:
        return
    direction = condition.vectors()[0]
    if abs(direction @ plane.normal) > 64 * np.finfo(float).eps:
        raise GroundIntersectionError('A wall-mounted root requires wind parallel to the solid image plane.')
    if condition.freeze_influences and abs(plane.normal[0]) > 64 * np.finfo(float).eps:
        raise GroundIntersectionError('Frozen-jig influence wind must be parallel to the wall-mounted root plane.')
    if gust.kind != 'none' or any(np.any(getattr(condition, key)) for key in
                                 ('rates', 'acceleration', 'angular_acceleration')):
        raise GroundIntersectionError('Wall-root support currently requires steady imposed flow without gust or frame motion.')
    if model.records.get('engine'):
        raise GroundIntersectionError('Wall-root support requires an unpowered configuration; jets are not reflected.')
    if local_motion is None:
        return
    values = getattr(local_motion, 'values', None)
    if values is None or not callable(getattr(local_motion, 'station', None)):
        raise GroundIntersectionError('Wall-root support requires explicit elastic motion at its mounted stations.')
    # Unsteady Eqs.28--35 retain instantaneous influence functions, including
    # steady Eqs.169--175 images. Eqs.43--44 retain the local strip apparent
    # mass. Interior elastic motion and Gamma-dot need no extra image state.
    # Only the declared clamp must remain stationary. Owned modal derivatives
    # extend its rates off the constraint manifold, like its pose; the full
    # clamp and kinematic rows enforce zero root rates in admissible modes.
    if boundary.probe is not None and boundary.probe.root_motion:
        return
    for beam, station in boundary.roots:
        motion = local_motion.station(beam, station)
        for name, field in zip(('velocity', 'rates', 'acceleration', 'rate_derivative'), values):
            tolerance = 64*np.finfo(float).eps*float(np.max(abs(field), initial=0.))
            if np.any(abs(getattr(motion, name)) > tolerance):
                raise GroundIntersectionError('A clamped wall root requires zero elastic motion at its mounted station.')


@contextmanager
def wall_root_derivatives(network, x, *, condition_override=None, motion_override=None, root_motion=False):
    """Continue only validated root coordinates while an owned Jacobian runs.

    The neighborhood is one eighth of the nearest positive physical sample or
    lifting receiver clearance. A narrower geometry requires a smaller probe;
    it is never made admissible by enlarging this neighborhood automatically.
    All other physical samples and a changed plane retain strict rejection.
    """
    condition = network.operating.apply(x[network.operating_start:],
        condition_override=condition_override, motion_override=motion_override)[0]
    if condition is None or not condition.ground_effect:
        yield
        return
    # A nested context must also validate its own actual base, not inherit an
    # exemption from the caller's mathematical continuation.
    token = _PROBE.set(None)
    try:
        r, q, *_ = network.unpack(x)
        meshes = network.deformed_meshes(r, q, network.geometry(r, q))
        points = network.point_positions(r, q)
        engines = np.array([r[network.node(*row[2:4])] +
                           q[network.node(*row[2:4])] @ (row[4:7] - network.rj[network.node(*row[2:4])])
                           for row in network.engines]).reshape(-1, 3)
        rotations = [q[network.node(*row[2:4])] for row in network.engines]
        plane = GroundPlane.from_condition(condition)
        plane.clearance(meshes, points, engines, network.engines, rotations, model=network.model)
        boundary = plane._wall_boundary
        if boundary.roots:
            from .gust import gust_field
            from .frozen_influence import lifting_geometry
            validate_wall_flow(plane, condition, network.model, gust_field(condition.gust))
            wind = np.array([1., 0., 0.]) if condition.freeze_influences else condition.vectors()[0]
            geometry = lifting_geometry(meshes, wind)
            receivers = np.concatenate([geometry[key] for key in ('cp', 'hv', 'rm')])
            clearance = plane.distance(receivers)
            if np.any(clearance <= 0):
                raise GroundIntersectionError('Wall-root aerodynamic receivers must remain strictly on the fluid side.')
            positive = np.r_[plane._wall_positive_distances, clearance]
            radius = float(np.min(positive)) / 8
            if not np.isfinite(radius) or radius <= boundary.roundoff:
                raise GroundIntersectionError('Wall-root geometry has no resolved derivative neighborhood.')
            _PROBE.set(_Probe(network.model, _plane_key(plane), boundary.roots, boundary.points, radius, root_motion))
        yield
    finally:
        _PROBE.reset(token)
        # A mathematical probe must never be returned as a cached accepted
        # physical evaluation after leaving its derivative context.
        network.aero_key = None


def wall_root_linearization(function):
    """Own the off-constraint extension for continuous matrices and outputs.

    Root-rate polynomial probes can have finite amplitude; root geometry still
    obeys the bounded neighborhood. Neither extension applies to physical
    snapshots or nonlinear time steps outside this derivative-only context.
    """
    @wraps(function)
    def evaluate(system, *args, **kwargs):
        with wall_root_derivatives(system.network, system.base,
                condition_override=system.condition, motion_override=system.motion,
                root_motion=True):
            return function(system, *args, **kwargs)
    return evaluate


def wall_root_coordinate_scales(system, scales, step):
    """Bound independent spatial-coordinate stencils by the owned neighborhood.

    The fourth-order stencil reaches twice its nominal increment. A translation
    moves every attached point by L*d; a spatial rotation moves an attachment
    at radius a by at most a*abs(d). Keep that displacement below half the
    already validated radius. Matrix coloring shares no coordinates at a node,
    so its grouped local-load probes have the same per-root bound.
    """
    probe = _PROBE.get()
    report = dict(columns=[], requested_step=float(step),
                  scope='Only independent wall-root coordinate probes; physical clearance is unchanged.')
    if probe is None or probe.model is not system.network.model:
        return scales, report
    n = system.network
    bounded = np.array(scales, copy=True)
    weights = active_weights(n.model)
    for (beam, station), edges in probe.roots.items():
        node = n.node(beam, station)
        positions = [edges]
        for index, position in probe.points.items():
            row = weights[index]
            if (int(row[0]), analysis_weight_station(n.model, row)) == (beam, station):
                positions.append(np.asarray(position)[None, :])
        arm = float(np.max(np.linalg.norm(np.concatenate(positions)-system.r0[node], axis=1)))
        for component in range(6):
            distance_scale = n.L if component < 3 else arm
            if distance_scale == 0:
                continue
            column = 6*node+component
            allowed = probe.radius/(4*distance_scale)
            actual = min(step*scales[column], allowed)
            if actual < 1e-7:
                raise GroundIntersectionError('Wall-root geometry needs a coordinate difference step below the supported modal minimum 1e-7.')
            if actual < step*scales[column]:
                bounded[column] = actual/step
                report['columns'].append(dict(column=column, requested=step*float(scales[column]),
                    actual=float(actual), neighborhood_radius=probe.radius,
                    maximum_stencil_displacement=2*float(actual)*distance_scale))
    return bounded, report
