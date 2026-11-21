"""Prescribed moving-engine/translated-fin production adapter; no autoexecution.

The caller supplies the frozen literal model, its production meshes, condition,
and fixture motion vectors. This module does not solve for circulation, choose a
fixture, or import the independent reference. All motion scalars are real
instantaneous probe values; complex harmonic directions must be split by caller.
"""
from dataclasses import dataclass, replace

import numpy as np
from scipy.spatial.transform import Rotation

from openswing.aero import evaluate_aerodynamics
from openswing.local_motion import LocalMotion


def _vector(value, name, *, unit=False):
    result = np.array(value, dtype=float, copy=True)
    if result.shape != (3,) or not np.all(np.isfinite(result)):
        raise ValueError(f"{name} must be a finite three-vector")
    if unit and abs(float(np.linalg.norm(result)) - 1.) > 1e-12:
        raise ValueError(f"{name} must already be normalized in the fixture")
    result.flags.writeable = False
    return result


@dataclass(frozen=True)
class MotionParameters:
    fin_beam: int
    engine_pivot: np.ndarray
    engine_rotation_axis: np.ndarray
    fin_translation_direction: np.ndarray

    @classmethod
    def from_values(cls, *, fin_beam, engine_pivot, engine_rotation_axis,
                    fin_translation_direction):
        return cls(int(fin_beam), _vector(engine_pivot, "engine_pivot"),
                   _vector(engine_rotation_axis, "engine_rotation_axis", unit=True),
                   _vector(fin_translation_direction, "fin_translation_direction", unit=True))

    @classmethod
    def from_fixture(cls, fixture):
        # The frozen JSON records direction ratios, with explicit normalization.
        k = _vector(fixture["engine_rotation"]["axis"], "engine_rotation_axis")
        d = _vector(fixture["fin_translation"]["direction"], "fin_translation_direction")
        if np.linalg.norm(k) == 0 or np.linalg.norm(d) == 0:
            raise ValueError("Fixture motion directions must be nonzero")
        return cls.from_values(fin_beam=fixture["engine"]["mount_beam"],
            engine_pivot=fixture["engine_rotation"]["pivot"],
            engine_rotation_axis=k/np.linalg.norm(k),
            fin_translation_direction=d/np.linalg.norm(d))


class PrescribedMotion:
    def __init__(self, surfaces, engine):
        self._surfaces = surfaces
        self._engine = engine

    def surface(self):
        return self._surfaces

    def point(self, kind, index):
        # Aero uses engine-record ordinal, not the declared power-control index.
        if kind != "engine" or index != 0:
            raise ValueError("This single-engine adapter has no other point motion")
        return self._engine


def prescribed_geometry(model, meshes, parameters, *, engine_angle=0.,
                        engine_rate=0., engine_acceleration=0.,
                        fin_displacement=0., fin_velocity=0., fin_acceleration=0.):
    """Return current meshes, engine position/relative rotation and local motion.

    The literal engine row fixes its baseline position and axes. Q is the
    relative body-space rotation: production forms E = Q @ engine_axes(row).
    Fin motion is pure translation; material frames and station labels stay as
    supplied by the independent production mesh constructor.
    """
    scalars = np.asarray([engine_angle, engine_rate, engine_acceleration,
                          fin_displacement, fin_velocity, fin_acceleration])
    if np.iscomplexobj(scalars) or not np.all(np.isfinite(scalars)):
        raise ValueError("Prescribed motion values must be finite and real")
    rows = model.records.get("engine", [])
    if len(rows) != 1 or int(rows[0][1]) != 0:
        raise ValueError("Adapter scope is exactly one type0 engine")
    if model.records.get("weight") or model.records.get("sensor"):
        raise ValueError("Adapter scope excludes additional point objects")
    if len(meshes) != 1 or not meshes[0].beam.lifting or meshes[0].beam.index != parameters.fin_beam:
        raise ValueError("Adapter scope is one lifting fin and no body meshes")
    mesh = meshes[0]
    d = parameters.fin_translation_direction
    shift = fin_displacement * d
    current = [replace(mesh, r0=mesh.r0+shift, r1=mesh.r1+shift, rm=mesh.rm+shift)]
    origin = current[0].rm
    zero = np.zeros_like(origin)
    surface = LocalMotion(origin, np.broadcast_to(fin_velocity*d, origin.shape),
                          zero.copy(), np.broadcast_to(fin_acceleration*d, origin.shape),
                          zero.copy())
    k = parameters.engine_rotation_axis
    Q = Rotation.from_rotvec(engine_angle*k).as_matrix()
    pivot = parameters.engine_pivot
    position = pivot + Q @ (np.asarray(rows[0][4:7], dtype=float)-pivot)
    arm = position-pivot
    omega = engine_rate*k
    omega_dot = engine_acceleration*k
    velocity = np.cross(omega, arm)
    acceleration = np.cross(omega_dot, arm)+np.cross(omega, np.cross(omega, arm))
    engine = LocalMotion(position, velocity, omega, acceleration, omega_dot)
    return current, position[None, :], Q[None, :, :], PrescribedMotion(surface, engine)


def evaluate(model, condition, meshes, parameters, gamma, gamma_rate, **motion):
    """One full production evaluation, with no inner circulation solve or cache."""
    if gamma is None or gamma_rate is None:
        raise ValueError("Both circulation and circulation rate must be prescribed")
    if condition.freeze_influences:
        raise ValueError("Moving-jet benchmark requires current influence geometry")
    current, positions, rotations, local = prescribed_geometry(model, meshes, parameters, **motion)
    result = evaluate_aerodynamics(model, condition, current,
        circulation=gamma, circulation_rate=gamma_rate,
        engine_positions=positions, engine_rotations=rotations, local_motion=local)
    return result, current


def residual(result):
    """Complete pointwise tangency residual, normalized by reference speed U."""
    return np.asarray(result["circulation_local_residual"], dtype=float)


def outputs(result, model, current_meshes):
    """Four wrench families x [fin, engine, net] x [Fx,Fy,Fz,Mx,My,Mz].

    Families are total, circulation-rate, apparent, and total-rate-apparent.
    All moments use the model's physical moment reference; engine rate/apparent
    components are zero in the type0 standalone aerodynamic model.
    """
    reference = np.asarray(model.reference[1], dtype=float)
    strips = result["strips"]
    r = np.asarray([s["position"] for s in strips])
    f = np.asarray([s["force"] for s in strips])
    m = np.asarray([s["moment"] for s in strips])+np.cross(r-reference, f)
    rate = np.asarray([s["circulation_rate_force"] for s in strips])
    apparent = np.asarray([s["apparent_force"] for s in strips])
    mesh = current_meshes[0]
    if len(strips) != len(mesh.rm) or any(s["beam"] != mesh.beam.index for s in strips):
        raise ValueError("Strip ordering differs from the declared single fin")
    chord = mesh.beam.value("chord", mesh.tm)
    xax = mesh.beam.value("Xax", mesh.tm)
    quarter = r+((.25-xax)*chord)[:, None]*mesh.frames[..., 0]
    rate_m = np.cross(quarter-reference, rate)
    apparent_m = np.asarray([s["apparent_moment"] for s in strips])+np.cross(r-reference, apparent)
    total_fin = np.r_[f.sum(axis=0), m.sum(axis=0)]
    total_engine = np.r_[result["engine_force"], result["engine_moment"]]
    total = np.stack([total_fin, total_engine, total_fin+total_engine])
    rate_fin = np.r_[rate.sum(axis=0), rate_m.sum(axis=0)]
    apparent_fin = np.r_[apparent.sum(axis=0), apparent_m.sum(axis=0)]
    rate_family = np.stack([rate_fin, np.zeros(6), rate_fin])
    apparent_family = np.stack([apparent_fin, np.zeros(6), apparent_fin])
    return np.stack([total, rate_family, apparent_family, total-rate_family-apparent_family])
