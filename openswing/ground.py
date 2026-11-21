"""Earth pose and ground images (steady equations 165–175, 205–206)."""
import numpy as np
from .geometry import surface_frame


def vector3(value, name):
    result = np.asarray(value, dtype=float)
    if result.shape != (3,) or not np.all(np.isfinite(result)):
        raise ValueError(f"{name} must contain three finite values.")
    return result


def body_to_earth(attitude):
    """ASWING bank/elevation/heading in degrees, in that order (eq. 205)."""
    phi, theta, psi = np.deg2rad(vector3(attitude, "Attitude"))
    c, s = np.cos([phi, theta, psi]), np.sin([phi, theta, psi])
    roll = np.array([[1,0,0],[0,c[0],s[0]],[0,-s[0],c[0]]])
    pitch = np.array([[c[1],0,s[1]],[0,1,0],[-s[1],0,c[1]]])
    heading = np.array([[c[2],s[2],0],[-s[2],c[2],0],[0,0,1]])
    return heading@pitch@roll


class GroundIntersectionError(ValueError):
    pass


class GroundPlane:
    def __init__(self, flag=0, position=(0,0,0), attitude=(0,0,0), normal=(0,0,1)):
        if flag not in (-1,0,1):
            raise ValueError("Ground-effect flag must be 0 (off), 1 (solid), or -1 (free surface).")
        self.flag = int(flag)
        self.position = vector3(position, "Earth position")
        self.attitude = vector3(attitude, "Attitude")
        self.rotation = body_to_earth(self.attitude)
        normal = vector3(normal, "Ground normal")
        if np.linalg.norm(normal) < 1e-12:
            raise ValueError("Ground normal must be nonzero.")
        self.normal_earth = normal/np.linalg.norm(normal)
        self.normal = self.rotation.T@self.normal_earth
        self.offset = float(self.position@self.normal_earth)
        self.reflection = np.eye(3)-2*np.outer(self.normal,self.normal)

    @classmethod
    def from_condition(cls, condition):
        return cls(condition.ground_effect,condition.position_earth,condition.attitude,condition.ground_normal)

    def distance(self, points):
        return np.asarray(points)@self.normal+self.offset

    def reflect_points(self, points):
        return np.asarray(points)@self.reflection.T-2*self.offset*self.normal

    def reflect_vectors(self, vectors):
        return np.asarray(vectors)@self.reflection.T

    def transformed_vectors(self, vectors, pg):
        """Reflect physical vectors while retaining their PG representation."""
        return np.asarray(vectors)@np.linalg.inv(pg).T@self.reflection.T@pg.T

    def clearance(self, meshes, points=(), engine_points=(), engine_rows=(), engine_rotations=None, *, model=None):
        """Minimum sampled actual-aircraft clearance; images are not geometry."""
        from .wall_root import WallRootBoundary
        boundary = WallRootBoundary(self, meshes, model)
        distances = []
        exempt = []
        for mesh in meshes:
            for t, r, frame, side in ((mesh.t0,mesh.r0,mesh.frame0,"right"),
                                      (mesh.t1,mesh.r1,mesh.frame1,"left")):
                frame = surface_frame(mesh.beam,t,side) if frame is None else frame
                if mesh.beam.lifting:
                    chord = mesh.beam.value('chord',t,side=side)
                    axis = mesh.beam.value('Xax',t,side=side)
                    distances.extend(self.distance(r-(chord*axis)[:,None]*frame[...,0]))
                    distances.extend(self.distance(r+(chord*(1-axis))[:,None]*frame[...,0]))
                    contact = boundary.surface(mesh, t, r, frame, side)
                    exempt.extend(contact); exempt.extend(contact)
                else:
                    radius = mesh.beam.value('radius',t,side=side)
                    radial = np.sqrt(np.maximum(0.,1-(frame[...,1]@self.normal)**2))
                    distances.extend(self.distance(r)-radius*radial)
                    exempt.extend(np.zeros(len(r), dtype=bool))
            if not mesh.beam.lifting:
                from .volume import body_quadrature
                _,r,radius,_ = body_quadrature(mesh)
                radial=np.sqrt(np.maximum(0.,1-(mesh.frames[...,1]@self.normal)**2))
                distances.extend((self.distance(r)-radius*radial[:,None]).ravel())
                exempt.extend(np.zeros(radius.size, dtype=bool))
        points = np.asarray(points).reshape(-1,3)
        distances.extend(self.distance(points))
        exempt.extend(boundary.point_mask(points))
        if len(engine_rows):
            from .propulsion import engine_axes
            for i,(p,row) in enumerate(zip(engine_points,engine_rows)):
                q=None if engine_rotations is None else engine_rotations[i]
                axis=engine_axes(row[7:10],q)[:,0]
                distances.append(self.distance(p)-abs(row[12])*np.sqrt(max(0.,1-(axis@self.normal)**2)))
                exempt.append(False)
        distances = np.asarray(distances)
        exempt = np.asarray(exempt, dtype=bool)
        if not np.all(np.isfinite(distances)):
            raise GroundIntersectionError('Aircraft clearance from the image plane is nonfinite.')
        minimum = float(np.min(distances)) if len(distances) else None
        if np.any((distances <= 0) & ~exempt):
            raise GroundIntersectionError("Aircraft geometry touches or crosses the ground image plane; increase clearance or change its attitude.")
        self._wall_boundary = boundary
        self._wall_positive_distances = distances[(distances > 0) & ~exempt]
        return minimum

    def report(self, minimum=None):
        report = dict(flag=self.flag,kind={0:'off',1:'solid',-1:'free_surface'}[self.flag],
                    normal_body=self.normal.tolist(),normal_earth=self.normal_earth.tolist(),
                    offset=self.offset,position_earth=self.position.tolist(),attitude=self.attitude.tolist(),
                    minimum_clearance=minimum)
        boundary = getattr(self, '_wall_boundary', None)
        if boundary is not None and boundary.roots:
            report.update(wall_roots=[dict(beam=beam, t=t) for beam, t in boundary.roots],
                          wall_root_roundoff_tolerance=boundary.roundoff,
                          wall_root_derivative_probe=boundary.probe is not None)
        return report
