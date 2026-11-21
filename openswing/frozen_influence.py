"""Jig-geometry velocity coefficients for ASWING's K/F approximation.

Steady theory section 4.6 freezes both vortex and volume influence functions at
zero wind angles. Circulation, freestream speed, local frames, kinematics and
loads remain live. Mach and the physical image plane still parameterize the
coefficients (user guide K/M and steady equation 177).
"""
from collections import OrderedDict
import numpy as np
from .geometry import surface_frame, undeformed_mesh
from .volume import VolumeField, body_quadrature


def lifting_geometry(meshes, direction, *, _material=None):
    """Bound endpoints and force/control points, steady equations 155–157."""
    arrays = {key: [] for key in ('a', 'b', 'hv', 'cp', 'rm', 'chord', 'ds', 'physical')}
    for mesh in meshes:
        beam = mesh.beam
        if not beam.lifting:
            continue
        value = beam.value if _material is None else lambda name, t, **kw: _material.value(beam, name, t, **kw)
        t = mesh.tm
        chord = value('chord', t)
        def compute():
            across = np.linalg.norm(np.cross(direction, mesh.frames[..., 1]), axis=-1)
            if np.min(across) < 1e-6:
                raise ValueError('Lifting-line geometry is singular for a beam aligned with the influence wind.')
            hv = mesh.rm+((.25-value('Xax', t))*chord/across)[:, None]*direction
            cp = hv+(value('dCLda', t)/(4*np.pi)*chord/across)[:, None]*direction
            ends = []
            for tn, rn, side, frame in ((mesh.t0, mesh.r0, 'right', mesh.frame0), (mesh.t1, mesh.r1, 'left', mesh.frame1)):
                sn = (surface_frame(beam, tn, side) if frame is None else frame)[..., 1]
                cross = np.linalg.norm(np.cross(direction, sn), axis=-1)
                if np.min(cross) < 1e-6:
                    raise ValueError('A beam endpoint aligns with the influence wind.')
                ends.append(rn+((.25-value('Xax', tn, side=side))*value('chord', tn, side=side)/cross)[:, None]*direction)
            return ends[0], ends[1], hv, cp
        # Material distributions are fixed for the enclosing tangent; include
        # all sample coordinates and every current geometric/wind input.
        inputs = (mesh.t0, mesh.t1, mesh.tm, chord, mesh.r0, mesh.r1, mesh.rm,
                  mesh.frames[..., 1],
                  None if mesh.frame0 is None else mesh.frame0[..., 1],
                  None if mesh.frame1 is None else mesh.frame1[..., 1], np.asarray(direction))
        a, b, hv, cp = (compute() if _material is None else
            _material.array_map(('lifting_geometry', id(beam)), inputs, compute))
        ends = (a, b)
        values = dict(a=ends[0], b=ends[1], hv=hv, cp=cp, rm=mesh.rm, chord=chord,
                      ds=mesh.length, physical=np.full(len(t), beam.physical_index))
        for key, value in values.items():
            arrays[key].append(value)
    return {key: (np.concatenate(value) if value else np.empty((0, 3)) if key in ('a', 'b', 'hv', 'cp', 'rm') else np.empty(0))
            for key, value in arrays.items()}


class FrozenInfluences:
    """A bounded cache owned by one immutable model/material discretization.

    It is deliberately not global and is not serialized in physical states.
    Checkpoint restoration rebuilds it from the original ASW geometry. External
    survey points use their requested spatial positions; attached receivers use
    the corresponding jig positions supplied by the caller.
    """
    def __init__(self, model, meshes):
        self.model = model
        self.material = self.signature(meshes)
        self.meshes = [undeformed_mesh(m) for m in meshes]
        self.by_beam = {m.beam.index: m for m in self.meshes}
        self.direction = np.array([1., 0., 0.])
        self.geometry = lifting_geometry(self.meshes, self.direction)
        self.body_points = {m.beam.index: body_quadrature(m)[1].reshape(-1, 3)
                            for m in self.meshes if not m.beam.lifting}
        self.key = None
        self.cache = OrderedDict()
        self.cache_bytes = 0

    @staticmethod
    def signature(meshes):
        return tuple((id(m.beam), m.t0.tobytes(), m.t1.tobytes(), m.tm.tobytes()) for m in meshes)

    def configure(self, model, meshes, mach, ratio, ground):
        if model is not self.model or self.material != self.signature(meshes):
            raise ValueError('Frozen influences belong to a different model or material mesh.')
        key = (float(mach), float(ratio), ground.flag,
               ground.normal.tobytes() if ground.flag else None, ground.offset if ground.flag else None)
        if key != self.key:
            self.cache.clear()
            self.cache_bytes = 0
            self.pg = np.diag([1/np.sqrt(1-mach*mach), 1., 1.])
            self.ground = ground
            with np.errstate(over='ignore'):
                self.core = np.maximum(ratio*self.geometry['chord'], self.geometry['ds'])
            if np.any(~np.isfinite(self.core)) or np.any(self.core > np.sqrt(np.finfo(float).max)):
                raise ValueError('Wake core radius is too large for the vortex calculation in these input units.')
            self.volume_field = VolumeField(model, self.meshes, self.direction, self.pg, ground=ground)
            self.key = key
        return self

    @staticmethod
    def array_key(value):
        if value is None:
            return None
        a = np.asarray(value)
        return a.shape, a.dtype.str, a.tobytes()

    def cached(self, key, compute):
        if key in self.cache:
            self.cache.move_to_end(key)
            return self.cache[key]
        value = compute()
        value.setflags(write=False)
        # Bound large external surveys without limiting the physical model.
        while self.cache and (len(self.cache) >= 256 or self.cache_bytes+value.nbytes > 64*1024**2):
            self.cache_bytes -= self.cache.popitem(last=False)[1].nbytes
        if value.nbytes <= 64*1024**2:
            self.cache[key] = value
            self.cache_bytes += value.nbytes
        return value

    def vortex(self, points, physical=None, *, exclude_bound=None):
        from .aero import horseshoe_velocity
        points = np.asarray(points)
        key = ('vortex', self.array_key(points), self.array_key(physical), self.array_key(exclude_bound))
        def compute():
            g = self.geometry
            cores = self.core[None, :] if physical is None else np.where(
                np.asarray(physical)[:, None] == g['physical'][None, :], 0., self.core[None, :])
            return horseshoe_velocity(points[:, None, :], g['a'][None, :, :], g['b'][None, :, :],
                                      self.direction, self.pg, cores, self.ground, exclude_bound=exclude_bound)
        return self.cached(key, compute)

    def factored_vortex(self, points, physical=None, *, exclude_bound=None):
        from .factored_influence import FactoredInfluence
        points = np.asarray(points)
        key = ('factored_vortex', self.array_key(points), self.array_key(physical), self.array_key(exclude_bound))
        def compute():
            g = self.geometry
            cores = self.core[None, :] if physical is None else np.where(
                np.asarray(physical)[:, None] == g['physical'][None, :], 0., self.core[None, :])
            return FactoredInfluence(points, g['a'], g['b'], self.direction, self.pg,
                                     cores, self.ground, exclude_bound=exclude_bound)
        return self.cached(key, compute)

    def volume(self, points, *, exclude_body=None, exclude_point=None):
        key = ('volume', self.array_key(points), self.array_key(exclude_body), self.array_key(exclude_point))
        return self.cached(key, lambda: self.volume_field.velocity(points, exclude_body=exclude_body, exclude_point=exclude_point))
