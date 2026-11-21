"""Slender-body and point-object source/doublet flow (steady eqs. 162–164).

Strengths are per unit freestream speed, in Prandtl–Glauert space. The final
velocity uses the transpose coordinate transform. Bodies do not sample their
own volume field when computing slender-body loads.
"""
import numpy as np
from .vector_ops import dot3
from numpy.polynomial.legendre import leggauss
from .body_shoulders import body_shoulders,shoulder_source
from .point_objects import active_weights, check_point_data

_GAUSS = leggauss(8)


def source_doublet(displacement, source, doublet, core=0.):
    """Velocity of concentrated singularities, with the documented finite core."""
    delta = np.asarray(displacement, dtype=float)
    r2 = dot3(delta, delta)
    den = r2+np.asarray(core)**2
    active = den > 0
    den = np.where(active,den,1.)
    numerator = np.asarray(doublet)*r2[...,None]-3*dot3(doublet,delta)[...,None]*delta
    result = np.asarray(source)[...,None]*delta/den[...,None]**1.5+numerator/den[...,None]**2.5
    return np.where(active[...,None],result/(4*np.pi),0.)


def _body_quadrature_splits(mesh):
    """Material spline boundaries, independent of current elastic geometry."""
    tables = [d.t for name in ('radius', 'Cdf', 'Cdp')
              if (d := mesh.beam.distributions.get(name)) is not None]
    knots = np.unique(np.concatenate(tables)) if tables else np.empty(0)
    start = np.searchsorted(knots, mesh.t0, side='right')
    stop = np.searchsorted(knots, mesh.t1, side='left')
    return knots, start, stop


def body_quadrature_count(mesh):
    """Count the padded material rule before allocating derivative arrays."""
    _, start, stop = _body_quadrature_splits(mesh)
    return len(start)*len(_GAUSS[0])*int(np.max(stop-start, initial=0)+1)


def body_quadrature_rule(mesh):
    """Eight Gauss points per spline piece, in each element's [0,1] chart.

    Rows have a common width for body motion and force transfer. Unused slots
    sample the element midpoint with zero weight. Splitting at material knots
    makes polynomial load integrals exact without adding structural nodes.
    """
    knots, start, stop = _body_quadrature_splits(mesh)
    pieces = int(np.max(stop-start, initial=0)+1)
    q, w = (_GAUSS[0]+1)/2, _GAUSS[1]/2
    shape = (len(start), len(q)*pieces)
    if pieces == 1:
        return np.broadcast_to(q, shape), np.broadcast_to(w, shape)
    fractions, weights = np.full(shape, .5), np.zeros(shape)
    for i, (lo, hi, a, b) in enumerate(zip(mesh.t0, mesh.t1, start, stop)):
        cuts = np.r_[0., (knots[a:b]-lo)/(hi-lo), 1.]
        width = np.diff(cuts)
        size = len(width)*len(q)
        fractions[i, :size] = (cuts[:-1, None]+width[:, None]*q).ravel()
        weights[i, :size] = (width[:, None]*w).ravel()
    return fractions, weights


def body_quadrature(mesh):
    """Integrate each current straight element, split at material spline knots."""
    u, weights = body_quadrature_rule(mesh)
    t = mesh.t0[:,None]+(mesh.t1-mesh.t0)[:,None]*u
    position = mesh.r0[:,None,:]+(mesh.r1-mesh.r0)[:,None,:]*u[...,None]
    radius = mesh.beam.value("radius",t)
    if np.any(radius < 0):
        raise ValueError(f"Beam {mesh.beam.index}: interpolated body radius must be nonnegative.")
    return t, position, radius, mesh.length[:,None]*weights


class VolumeField:
    def __init__(self, model, meshes, direction, pg, point_positions=None, ground=None):
        self.pg = pg
        weight_rows = active_weights(model)
        check_point_data(weight_rows, point_positions, 'Point positions')
        xi = pg@direction
        positions, strengths, doublets, cores, owners, points = [], [], [], [], [], []
        self.body_shoulders={m.beam.index:body_shoulders(m) for m in meshes if not m.beam.lifting}
        for mesh in meshes:
            if mesh.beam.lifting:
                continue
            t, p, radius, weights = body_quadrature(mesh)
            if not np.any(radius):
                continue
            # Quadrature along each deformed straight interval in PG space.
            dr = (mesh.r1-mesh.r0)@pg.T
            length = np.linalg.norm(dr,axis=1)
            ell = dr/length[:,None]
            dt = mesh.t1-mesh.t0
            drdt = mesh.beam.value("radius",t,derivative=1)
            darea = 2*np.pi*radius*drdt*dt[:,None]/length[:,None]
            sigma = darea*(ell@xi)[:,None]
            nu = 2*np.pi*radius[...,None]**2*(xi-(ell@xi)[:,None]*ell)[:,None,:]
            w = weights*(length/mesh.length)[:,None]
            positions.extend((p@pg.T).reshape(-1,3))
            strengths.extend((sigma*w).ravel());doublets.extend((nu*w[...,None]).reshape(-1,3))
            cores.extend((radius/2).ravel())
            owners.extend([mesh.beam.physical_index]*radius.size);points.extend([-1]*radius.size)
        for i,row in enumerate(weight_rows):
            if row[6] < 0 or row[7] < 0:
                raise ValueError("Point-object drag area and aerodynamic volume must be nonnegative.")
            if row[6] == row[7] == 0:
                continue
            p = row[2:5] if point_positions is None else point_positions[i]
            positions.append(np.asarray(p)@pg.T)
            strengths.append(row[6]);doublets.append(row[7]*xi)
            cores.append(max(np.sqrt(row[6]/np.pi),np.cbrt(row[7]/np.pi)))
            owners.append(-1);points.append(i)
        self.positions = np.array(positions).reshape(-1,3)
        self.sources = np.asarray(strengths)
        self.doublets = np.array(doublets).reshape(-1,3)
        self.cores = np.asarray(cores)
        self.owners,self.points = np.array(owners),np.array(points)
        self.is_image = np.zeros(len(self.sources),dtype=bool)
        if ground is not None and ground.flag:
            physical=self.positions@np.linalg.inv(pg).T
            self.positions=np.concatenate([self.positions,ground.reflect_points(physical)@pg.T])
            self.sources=np.r_[self.sources,ground.flag*self.sources]
            self.doublets=np.concatenate([self.doublets,ground.flag*ground.transformed_vectors(self.doublets,pg)])
            self.cores=np.tile(self.cores,2)
            self.owners=np.tile(self.owners,2);self.points=np.tile(self.points,2)
            self.is_image=np.r_[self.is_image,np.ones_like(self.is_image)]

        self.shoulders=[]
        for entries in self.body_shoulders.values():
            for entry in entries:
                ell=pg@entry['tangent'];ell/=np.linalg.norm(ell)
                self.shoulders.append(dict(**entry,position_pg=pg@entry['position'],coefficient=float(xi@ell),image=False))
        if ground is not None and ground.flag:
            self.shoulders += [dict(entry,position_pg=pg@ground.reflect_points(entry['position']),
                coefficient=ground.flag*entry['coefficient'],image=True) for entry in self.shoulders]

    def shoulder_velocity(self, locations, exclude_body=None):
        result=np.zeros_like(locations)
        for entry in self.shoulders:
            value=shoulder_source(locations@self.pg.T-entry['position_pg'],entry['radius_left'],entry['radius_right'],entry['coefficient'])@self.pg
            if exclude_body is not None and not entry['image']:
                value=np.where((np.broadcast_to(exclude_body,(len(locations),))!=entry['physical_index'])[:,None],value,0.)
            result+=value
        return result

    def velocity(self, locations, *, exclude_body=None, exclude_point=None, _tangent=None, _cache_name=None):
        locations = np.asarray(locations,dtype=float)
        shape = locations.shape
        locations = locations.reshape(-1,3)
        shoulders=self.shoulder_velocity(locations,exclude_body)
        if not len(self.sources):
            return shoulders.reshape(shape)
        selected = np.ones(len(self.sources),dtype=bool)
        if exclude_body is not None and np.ndim(exclude_body)==0:
            selected &= (self.owners != exclude_body) | self.is_image
        if exclude_point is not None and np.ndim(exclude_point)==0:
            selected &= (self.points != exclude_point) | self.is_image
        if not np.any(selected):
            return shoulders.reshape(shape)
        transformed = locations@self.pg.T
        if _tangent is None or _cache_name is None:
            delta = transformed[:,None,:]-self.positions[None,selected,:]
            values = source_doublet(delta,self.sources[None,selected],self.doublets[None,selected,:],self.cores[None,selected])
        else:
            values = _tangent.volume_pairs(_cache_name, transformed, self.positions[selected],
                                          self.sources[selected], self.doublets[selected], self.cores[selected])
        if exclude_body is not None:
            excluded=(np.broadcast_to(exclude_body,(len(locations),))[:,None] == self.owners[None,selected]) & ~self.is_image[None,selected]
            values = np.where(excluded[...,None],0.,values)
        if exclude_point is not None:
            excluded=(np.broadcast_to(exclude_point,(len(locations),))[:,None] == self.points[None,selected]) & ~self.is_image[None,selected]
            values = np.where(excluded[...,None],0.,values)
        return (values.sum(axis=1)@self.pg+shoulders).reshape(shape)


def body_loads(mesh, density, velocity, motion, acceleration_reference, added_mass_factor=1., *, local_motion=None):
    """Integrated body lift, profile and acceleration loads at mesh.rm.

Cylinder potential flow gives rho*pi*R² transverse added mass. The optional
factor two reproduces the printed ASWING body formula; see numerical notes.
"""
    t, positions, radius, weights = body_quadrature(mesh)
    tangent = mesh.frames[...,1]
    v = np.asarray(velocity)
    along = np.sum(v*tangent[:,None,:],axis=-1)
    normal = v-along[...,None]*tangent[:,None,:]
    speed,normspeed = np.linalg.norm(v,axis=-1),np.linalg.norm(normal,axis=-1)
    cdf,cdp = mesh.beam.value("Cdf",t),mesh.beam.value("Cdp",t)
    if np.any(cdf < 0) or np.any(cdp < 0):
        raise ValueError(f"Beam {mesh.beam.index}: body drag coefficients must be nonnegative.")
    area_derivative = 2*np.pi*radius*mesh.beam.value("radius",t,derivative=1)*(mesh.t1-mesh.t0)[:,None]/mesh.length[:,None]
    lift = density*normal*(along*area_derivative*weights)[...,None]
    profile = density*radius[...,None]*(speed[...,None]*v*cdf[...,None]+normspeed[...,None]*normal*cdp[...,None])*weights[...,None]
    acc = motion.at(positions,acceleration_reference) if local_motion is None else local_motion.absolute_acceleration(positions,motion,acceleration_reference)
    normal_acc = acc-np.sum(acc*tangent[:,None,:],axis=-1)[...,None]*tangent[:,None,:]
    apparent = -added_mass_factor*density*np.pi*radius[...,None]**2*normal_acc*weights[...,None]
    arm = positions-mesh.rm[:,None,:]
    return dict(lift=lift.sum(axis=1), profile=profile.sum(axis=1), apparent=apparent.sum(axis=1),
                force_samples=lift+profile+apparent,
                moment=np.cross(arm,lift+profile+apparent).sum(axis=1),
                apparent_moment=np.cross(arm,apparent).sum(axis=1))
