"""Real/apparent inertia and steady accelerating-frame loads.

ASWING steady equations 75–96, 237–256 and CG_Calc.pdf equation 29.
All masses/inertias here are mass quantities, after division by input g.
"""
from dataclasses import dataclass
import numpy as np
from .vector_ops import cross3
from scipy.spatial.transform import Rotation
from .geometry import surface_frame
from .structure import skew
from .point_objects import active_weight_items, check_point_data
from .apparent_box import _section_wrench


def vector(value, name):
    a = np.asarray(value, dtype=float)
    if a.shape != (3,) or not np.all(np.isfinite(a)):
        raise ValueError(f"{name} must be a finite xyz vector.")
    return a


@dataclass
class Motion:
    rates: tuple = (0., 0., 0.)
    acceleration: tuple = (0., 0., 0.)  # absolute acceleration at Reference row 3
    angular_acceleration: tuple = (0., 0., 0.)

    def __post_init__(self):
        self.rates = vector(self.rates, "Rotation rates")
        self.acceleration = vector(self.acceleration, "Reference acceleration")
        self.angular_acceleration = vector(self.angular_acceleration, "Angular acceleration")

    def at(self, position, reference):
        d = np.asarray(position)-np.asarray(reference)
        return self.acceleration+cross3(self.angular_acceleration, d)+cross3(self.rates, cross3(self.rates, d))


def parallel_axis(mass, offset):
    offset = np.asarray(offset)
    return np.asarray(mass)[..., None, None]*(np.sum(offset**2, axis=-1)[..., None, None]*np.eye(3)-offset[..., :, None]*offset[..., None, :])


def point_tensor(row, gravity):
    """ASW products Ixy/Ixz/Iyz are NEGATIVE tensor off-diagonal entries."""
    xx, yy, zz, xy, xz, yz = row[11:17]/gravity
    inertia = np.array([[xx, -xy, -xz], [-xy, yy, -yz], [-xz, -yz, zz]])
    if np.min(np.linalg.eigvalsh(inertia)) < -1e-12*max(np.max(abs(inertia)), 1e-30):
        raise ValueError("Point-object inertia must be positive semidefinite; check moments and products of inertia.")
    return inertia


def inertial_wrench(mass, position, inertia, spin, motion, gravity, acceleration_reference, *, local_motion=None):
    """Force and centroid couple exerted on the support by moving masses."""
    acceleration = motion.at(position, acceleration_reference) if local_motion is None else local_motion.absolute_acceleration(position,motion,acceleration_reference)
    rates = motion.rates if local_motion is None else motion.rates+local_motion.rates
    angular_acceleration = motion.angular_acceleration if local_motion is None else local_motion.absolute_angular_acceleration(motion)
    force = np.asarray(mass)[..., None]*(np.asarray(gravity)-acceleration)
    angular_momentum = np.einsum("...ij,...j->...i", inertia, rates)+spin
    moment = -np.einsum("...ij,...j->...i", inertia, angular_acceleration)-cross3(rates, angular_momentum)
    return force, moment


def mass_summary(mass, position, inertia, spin, reference):
    """Integrate centroidal tensors; return a symmetric spatial mass matrix."""
    mass, position, inertia, spin = map(np.asarray, (mass, position, inertia, spin))
    total = float(mass.sum())
    center = np.sum(mass[:, None]*position, axis=0)/total if total > 0 else None
    offset = position-np.asarray(reference)
    first = np.sum(mass[:, None]*offset, axis=0)
    about_ref = np.sum(inertia+parallel_axis(mass, offset), axis=0)
    about_cg = None if center is None else np.sum(inertia+parallel_axis(mass, position-center), axis=0)
    matrix = np.block([[total*np.eye(3), -skew(first)], [skew(first), about_ref]])
    return dict(mass=total, cg=None if center is None else center.tolist(),
                reference=np.asarray(reference).tolist(), first_moment=first.tolist(),
                inertia_reference=about_ref.tolist(), inertia_cg=None if center is None else about_cg.tolist(),
                spin_angular_momentum=spin.sum(axis=0).tolist(), spatial_matrix=matrix.tolist())


class InertiaModel:
    """Precomputed material weights and centroidal section properties.

    Each element's distributed mass is represented by its midpoint and its
    finite segment inertia. For a straight uniform element this integrates the
    rigid-body inertia exactly, including the ds²/12 correction in equation 80.
    """
    def __init__(self, model, meshes, *, allow_signed_point_weights=False, allow_signed_distributed_weights=False):
        self.model, self.data = model, {}
        self.signed_distributed_weights = []
        for mesh in meshes:
            beam = mesh.beam
            t = mesh.ts if mesh.ts is not None else (mesh.t0+mesh.t1)/2
            entries = []
            for prefix in ("", "D"):
                field = prefix+"mg"
                weight = beam.value(field, t)*mesh.length
                icc = beam.value(prefix+"mgcc", t)*mesh.length/model.constants[0]
                inn = beam.value(prefix+"mgnn", t)*mesh.length/model.constants[0]
                distribution = beam.distributions.get(field)
                signed = np.any(weight < 0) or (distribution is not None and np.any(distribution.values < 0))
                if signed:
                    self.signed_distributed_weights.append(dict(beam=beam.index, field=field))
                if (signed and not allow_signed_distributed_weights) or np.any(icc < 0) or np.any(inn < 0):
                    raise ValueError("Distributed weights and centroidal inertias must be nonnegative.")
                entries.append((weight/model.constants[0], beam.value(prefix+"Ccg", t), beam.value(prefix+"Ncg", t), icc, inn))
            self.data[beam.index] = entries
        items = active_weight_items(model)
        self.rows = [row for _, row in items]
        self.source_point_indices = [i for i, _ in items]
        self.signed_point_weights = [i+1 for i, row in items if row[5] < 0]
        if self.signed_point_weights and not allow_signed_point_weights:
            raise ValueError("Point weights must be nonnegative.")
        self.point_inertias = [point_tensor(row, model.constants[0]) for row in self.rows]

    def elements(self, meshes, point_positions=None, point_rotations=None):
        """Return mass records tagged with their beam element or point object."""
        out = []
        for mesh in meshes:
            Ra = surface_frame(mesh.beam, mesh.t0, "right") if mesh.frame0 is None else mesh.frame0
            Rb = surface_frame(mesh.beam, mesh.t1, "left") if mesh.frame1 is None else mesh.frame1
            delta = Rotation.from_matrix(Ra.transpose(0, 2, 1)@Rb).as_rotvec()
            R = Ra@Rotation.from_rotvec(delta/2).as_matrix()
            midpoint = (mesh.r0+mesh.r1)/2
            for mass, c, n, icc, inn in self.data[mesh.beam.index]:
                position = midpoint+c[:, None]*R[..., 0]+n[:, None]*R[..., 2]
                diagonal = np.stack([icc, icc+inn, inn], axis=1)
                inertia = (R*diagonal[:, None, :])@R.transpose(0, 2, 1)
                inertia += parallel_axis(mass/12, mesh.r1-mesh.r0)
                out.append(dict(beam=mesh.beam.index, point=None, mass=mass, position=position,
                                inertia=inertia, spin=np.zeros_like(position)))
        out.extend(self.point_elements(point_positions,point_rotations))
        return out

    def point_elements(self, point_positions=None, point_rotations=None):
        check_point_data(self.rows, point_positions, 'Point positions')
        check_point_data(self.rows, point_rotations, 'Point rotations')
        out=[]
        for k, row in enumerate(self.rows):
            Q = np.eye(3) if point_rotations is None else point_rotations[k]
            position = row[2:5] if point_positions is None else point_positions[k]
            out.append(dict(beam=None, point=k, mass=np.array([row[5]/self.model.constants[0]]),
                            position=np.array([position]), inertia=np.array([Q@self.point_inertias[k]@Q.T]),
                            spin=np.array([Q@row[8:11]/self.model.constants[0]])))
        return out

    def summary(self, elements):
        result = mass_summary(*(np.concatenate([e[key] for e in elements]) for key in ("mass", "position", "inertia", "spin")), self.model.reference[1])
        if self.signed_point_weights or self.signed_distributed_weights:
            result.update(physical=False, cg=None, inertia_cg=None,
                          signed_point_weights=self.signed_point_weights,
                          scope="Algebraic signed-weight bookkeeping for static gravity loads. This is not a physical mass/inertia model; no physical CG is defined. Dynamic analyses require nonnegative masses.")
            if self.signed_distributed_weights:
                result['signed_distributed_weights'] = self.signed_distributed_weights
        return result


def apparent_properties(meshes, density, reference, body_added_mass_factor=1.):
    """Spatial added-mass matrix about one reference, without inventing a CG.

    Thin lifting surfaces have direction-dependent mass; their 3×3 mass block
    can be rank deficient. The complete 6×6 matrix preserves its moment coupling.
    """
    matrix = np.zeros((6, 6))
    for mesh in meshes:
        c, s, n = mesh.frames[..., 0], mesh.frames[..., 1], mesh.frames[..., 2]
        if mesh.beam.lifting:
            chord = mesh.beam.value("chord", mesh.tm)
            offset = ((.5-mesh.beam.value("Xax", mesh.tm))*chord)[:, None]*c
            arm = mesh.rm+offset-np.asarray(reference)
            mass = density*np.pi/4*chord**2*mesh.length
            normal_mass = mass[:, None, None]*n[..., :, None]*n[..., None, :]
            rotational = (mass*chord**2/32)[:, None, None]*s[..., :, None]*s[..., None, :]
        else:
            from .volume import body_quadrature
            _, positions, radius, weights = body_quadrature(mesh)
            arm = (positions-np.asarray(reference)).reshape(-1,3)
            mass = body_added_mass_factor*density*np.pi*radius**2*weights
            transverse = np.eye(3)-s[..., :,None]*s[...,None,:]
            normal_mass = (mass[...,None,None]*transverse[:,None,:,:]).reshape(-1,3,3)
            rotational = np.zeros_like(normal_mass)
        cross = skew(arm)
        matrix[:3, :3] += normal_mass.sum(axis=0)
        matrix[:3, 3:] -= (normal_mass@cross).sum(axis=0)
        matrix[3:, :3] += (cross@normal_mass).sum(axis=0)
        matrix[3:, 3:] += (rotational-cross@normal_mass@cross).sum(axis=0)
    return dict(reference=np.asarray(reference).tolist(), mass_tensor=matrix[:3, :3].tolist(),
                inertia_reference=matrix[3:, 3:].tolist(), spatial_matrix=matrix.tolist())


def surface_apparent_loads(position, frames, chord, xax, length, density, velocity, motion, acceleration_reference, *, local_motion=None):
    """Integrated noncirculatory loads with absolute section kinematics."""
    c, s, n = frames[..., 0], frames[..., 1], frames[..., 2]
    offset = ((.5-xax)*chord)[:, None]*c
    acceleration = motion.at(position+offset, acceleration_reference) if local_motion is None else local_motion.absolute_acceleration(position+offset,motion,acceleration_reference)
    rates = motion.rates if local_motion is None else motion.rates+local_motion.rates
    angular_acceleration = motion.angular_acceleration if local_motion is None else local_motion.absolute_angular_acceleration(motion)
    rate_term = np.sum(cross3(velocity, rates)*n, axis=1)
    return _section_wrench(frames, chord, xax, density, acceleration, rate_term,
                           angular_acceleration, length)
