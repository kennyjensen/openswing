"""Independent sampled slender-body/point volume flow and body loads.

SOURCE ONLY until an enclosing frozen audit authorizes execution. This module
imports no production physics and performs no model construction or evaluation
at import. Geometry, material sampling and kinematics are explicit inputs.

Primary sources, cached in .reference/asw_theory.txt and asw_uns_theory.txt:
https://web.mit.edu/drela/Public/web/aswing/asw_theory.pdf
  68--69: body lift and transverse velocity; 71: body profile drag;
  162--164: PG-space line/point source and doublet fields, including core sizes.
https://web.mit.edu/drela/Public/web/aswing/asw_uns_theory.pdf
  22--27: absolute acceleration supplied by the enclosing motion reference;
  45: body apparent force. The printed coefficient is 2*pi*rho*R**2.
  Here added_mass_factor is explicit; factor 1 retains the current aircraft's
  selected cylinder convention. It is not claimed to reproduce printed 45.

Distributed sources are integrated only over the supplied material intervals.
No terminal area closure is inferred. A finite nonzero end radius alone does
not specify a blunt-end source model. Explicit jump records may describe
interior shoulders or end closures, with left/right radii in increasing beam
coordinate order. Their source is the smooth-transition weak limit of 162--163,
numerically integrated over area with the varying R/2 core. Their concentrated
lift is the corresponding weak limit of 68. This is a declared extension, not
a claim of historical ASWING blunt-end or separated-flow treatment.

body_samples keys: t0,t1,physical (one value per panel), and radius,
dradius_dt,Cdf,Cdp (panel x quadrature arrays). Optional supplied quadrature
nodes/weights must match independently generated Gauss--Legendre quadrature on
[0,1], with weights summing to 1. Interpolation of material input is excluded.

All positions, tangents, velocities and accelerations use the same physical
axes. wind is a unit vector; pg maps physical coordinates into PG space.
evaluate returns velocity PER UNIT freestream speed. body_loads accepts the
complete local relative fluid velocity and absolute material acceleration;
it computes no motion, induction, self-field subtraction or freestream itself.
Complex perturbations of geometric/kinematic arrays are retained. Material
samples, ownership, quadrature and exclusions are frozen real inputs.
"""

import numpy as np


def norm(value):
    """Bilinear analytic continuation, without a complex conjugate."""
    value = np.asarray(value)
    return np.sqrt(np.sum(value*value, axis=-1))


def _array(value, shape, name):
    value = np.asarray(value)
    if value.shape != shape or not np.all(np.isfinite(value)):
        raise ValueError(name+' has the wrong shape or nonfinite entries')
    return value


def _real(value, shape, name):
    value = _array(value, shape, name)
    if np.iscomplexobj(value) and np.any(value.imag != 0):
        raise ValueError(name+' is a frozen real material input')
    return np.asarray(value.real, dtype=float).copy()


def _kernel(delta, source, doublet, core):
    """Eq.163 concentrated kernel, still in transformed coordinates."""
    radius2 = np.sum(delta*delta, axis=-1)
    denominator = radius2+np.asarray(core)**2
    active = denominator.real > 0
    nonzero = (np.abs(source) != 0) | np.any(np.abs(doublet) != 0, axis=-1)
    if np.any(~active & nonzero):
        raise ValueError('A nonzero unregularized singularity meets a receiver')
    safe = np.where(active, denominator, 1.)
    projection = np.sum(doublet*delta, axis=-1)
    monopole = np.asarray(source)[..., None]*delta/safe[..., None]**1.5
    dipole = (radius2[..., None]*doublet-3*projection[..., None]*delta)
    dipole = dipole/safe[..., None]**2.5
    return np.where(active[..., None], (monopole+dipole)/(4*np.pi), 0.)


def _excluded(value, shape, name):
    if value is None:
        return None
    value = np.asarray(value)
    if not np.issubdtype(value.dtype, np.integer):
        raise ValueError(name+' must contain integer object identifiers')
    try:
        return np.broadcast_to(value, shape).ravel()
    except ValueError as error:
        raise ValueError(name+' does not match the receiver shape') from error


def _jump(record):
    position = _array(record['position'], (3,), 'jump position')
    tangent = _array(record['tangent'], (3,), 'jump tangent')
    if abs(np.sum(tangent*tangent)-1) > 2e-10:
        raise ValueError('Jump tangent must be a unit physical vector')
    radii = _real([record['radius_left'], record['radius_right']], (2,), 'jump radii')
    if np.any(radii < 0):
        raise ValueError('Jump radii must be nonnegative')
    owner = record.get('physical_id', record.get('physical_index'))
    if owner is None or int(owner) != owner or owner <= 0:
        raise ValueError('Each declared jump requires a positive physical ID')
    return position, tangent, radii[0], radii[1], int(owner)


class VolumeReference:
    def __init__(self, body_samples, *, point_cda, point_volume,
                 quadrature_nodes=None, quadrature_weights=None,
                 jump_quadrature=32):
        radius = np.asarray(body_samples['radius'])
        if radius.ndim != 2 or radius.shape[1] < 1:
            raise ValueError('Body samples must have shape (panels,quadrature)')
        self.np, self.nq = radius.shape
        self.material = {key: _real(body_samples[key], radius.shape, key)
                         for key in ('radius', 'dradius_dt', 'Cdf', 'Cdp')}
        if any(np.any(self.material[key] < 0) for key in ('radius', 'Cdf', 'Cdp')):
            raise ValueError('Radius and body drag coefficients must be nonnegative')
        self.t0 = _real(body_samples['t0'], (self.np,), 't0')
        self.t1 = _real(body_samples['t1'], (self.np,), 't1')
        if np.any(self.t1 <= self.t0):
            raise ValueError('Body material coordinates must increase')
        physical = _array(body_samples['physical'], (self.np,), 'physical IDs')
        if np.any(physical <= 0) or np.any(physical != np.asarray(physical, dtype=int)):
            raise ValueError('Positive integer physical IDs are required')
        self.physical = np.asarray(physical, dtype=int).copy()
        nodes, weights = np.polynomial.legendre.leggauss(self.nq)
        self.u, self.weights = (nodes+1)/2, weights/2
        for value, expected, name in ((quadrature_nodes, self.u, 'quadrature nodes'),
                                     (quadrature_weights, self.weights, 'quadrature weights')):
            if value is not None:
                actual = _real(value, (self.nq,), name)
                if np.max(abs(actual-expected)) > 2e-14:
                    raise ValueError(name+' must match Gauss quadrature on [0,1]')
        self.npoints = np.size(point_cda)
        self.point_cda = _real(point_cda, (self.npoints,), 'point CdA')
        self.point_volume = _real(point_volume, (self.npoints,), 'point volume')
        if np.any(self.point_cda < 0) or np.any(self.point_volume < 0):
            raise ValueError('Point CdA and volume must be nonnegative')
        self.point_core = np.maximum(np.sqrt(self.point_cda/np.pi),
                                     np.cbrt(self.point_volume/np.pi))
        if int(jump_quadrature) != jump_quadrature or jump_quadrature < 1:
            raise ValueError('Jump quadrature degree must be a positive integer')
        nodes, weights = np.polynomial.legendre.leggauss(int(jump_quadrature))
        self.jump_u, self.jump_weights = (nodes+1)/2, weights/2

    def sample_geometry(self, r0, r1, length=None):
        r0 = _array(r0, (self.np, 3), 'body first endpoints')
        r1 = _array(r1, (self.np, 3), 'body second endpoints')
        if np.any(norm(r1-r0).real <= 0):
            raise ValueError('Positive current body endpoint lengths are required')
        position = r0[:, None, :]+self.u[None, :, None]*(r1-r0)[:, None, :]
        result = dict(position=position,
                      t=self.t0[:, None]+(self.t1-self.t0)[:, None]*self.u)
        if length is not None:
            length = _array(length, (self.np,), 'current physical material length')
            if np.any(length.real <= 0):
                raise ValueError('Positive current material lengths are required')
            result['weights'] = length[:, None]*self.weights
        return result

    def evaluate(self, r0, r1, point_positions, wind, pg, locations, *,
                 exclude_body=None, exclude_point=None, jumps=()):
        """Unit-speed body, point and declared-jump velocities at any receivers.

        Exclusions are scalar IDs or arrays broadcastable to locations.shape[:-1].
        Body exclusions use positive physical IDs; point exclusions use the
        original zero-based point index. Own body fields are not excluded unless
        explicitly requested. No finite-radius end sources are inferred.
        """
        geometry = self.sample_geometry(r0, r1)
        r0, r1 = np.asarray(r0), np.asarray(r1)
        point_positions = _array(point_positions, (self.npoints, 3), 'point positions')
        wind = _array(wind, (3,), 'wind')
        pg = _array(pg, (3, 3), 'PG transform')
        if abs(np.sum(wind*wind)-1) > 2e-10:
            raise ValueError('Influence wind must be a unit vector')
        locations = np.asarray(locations)
        if locations.ndim < 1 or locations.shape[-1] != 3 or not np.all(np.isfinite(locations)):
            raise ValueError('Receiver locations require finite xyz vectors')
        shape = locations.shape[:-1]
        targets = locations.reshape(-1, 3)@pg.T
        excluded_body = _excluded(exclude_body, shape, 'body exclusion')
        excluded_point = _excluded(exclude_point, shape, 'point exclusion')
        xi = pg@wind
        interval = (r1-r0)@pg.T
        ell = norm(interval)
        if np.any(ell.real <= 0):
            raise ValueError('Positive PG body interval lengths are required')
        tangent = interval/ell[:, None]
        along = tangent@xi
        radius = self.material['radius']
        area_dt = 2*np.pi*radius*self.material['dradius_dt']
        # sigma*dell = dA/dt * dt * (xi dot ell_hat) * Gauss weight.
        sources = area_dt*(self.t1-self.t0)[:, None]*along[:, None]*self.weights
        transverse = xi-along[:, None]*tangent
        doublets = (2*np.pi*radius**2*ell[:, None]*self.weights)[..., None]*transverse[:, None, :]
        source_positions = (geometry['position']@pg.T).reshape(-1, 3)
        source_values = sources.ravel()
        doublet_values = doublets.reshape(-1, 3)
        source_cores = (radius/2).ravel()
        owners = np.repeat(self.physical, self.nq)
        body_pairs = _kernel(targets[:, None, :]-source_positions[None, :, :],
                             source_values[None, :], doublet_values[None, :, :],
                             source_cores[None, :])
        if excluded_body is not None:
            body_pairs = np.where((excluded_body[:, None] != owners)[..., None], body_pairs, 0.)
        body_velocity = body_pairs.sum(axis=1)@pg
        point_pairs = _kernel(targets[:, None, :]-point_positions[None, :, :]@pg.T,
                              self.point_cda[None, :],
                              (self.point_volume[:, None]*xi)[None, :, :],
                              self.point_core[None, :])
        if excluded_point is not None:
            point_pairs = np.where((excluded_point[:, None] != np.arange(self.npoints))[..., None], point_pairs, 0.)
        point_velocity = point_pairs.sum(axis=1)@pg
        jump_velocity = np.zeros_like(body_velocity, dtype=np.result_type(
            body_velocity, point_velocity, pg, wind))
        for record in jumps:
            position, axis, left, right, owner = _jump(record)
            if left == right:
                continue
            transformed_axis = pg@axis
            transformed_axis = transformed_axis/norm(transformed_axis)
            coefficient = np.sum(xi*transformed_axis)
            areas = np.pi*((1-self.jump_u)*left**2+self.jump_u*right**2)
            delta_area = np.pi*(right**2-left**2)
            delta = targets-position@pg.T
            # Endpoint closure with zero radius is singular at its own center.
            # The actual declared-jumps-only Daedalus map has no such records.
            if min(left, right) == 0 and np.any(np.sum(delta.real**2, axis=1) == 0):
                raise ValueError('Zero-radius closure at its own center has no smooth directional map')
            cores = np.sqrt(areas/np.pi)/2
            values = _kernel(delta[:, None, :],
                             coefficient*delta_area*self.jump_weights,
                             np.zeros((len(self.jump_u), 3)), cores)
            value = values.sum(axis=1)@pg
            if excluded_body is not None:
                value = np.where((excluded_body != owner)[:, None], value, 0.)
            # A probe may move only a declared jump while all line/point inputs
            # stay real. Let the result dtype promote for that independent seam.
            jump_velocity = jump_velocity+value
        reshape = lambda value: value.reshape(locations.shape)
        return dict(velocity=reshape(body_velocity+point_velocity+jump_velocity),
                    body_velocity=reshape(body_velocity), point_velocity=reshape(point_velocity),
                    jump_velocity=reshape(jump_velocity),
                    source_positions_pg=source_positions, source_strengths=source_values,
                    source_doublets=doublet_values, source_cores=source_cores,
                    source_physical=owners)

    def body_loads(self, r0, r1, rm, length, span, velocity,
                   absolute_acceleration, density, *, added_mass_factor=1.):
        """Weighted sample forces/couples and element totals in physical axes.

        span may be one current unit vector per panel (the current discrete
        body convention) or one per quadrature sample. No vector is normalized
        or projected onto the endpoint chord here. Forces include Gauss weights;
        sample couples and element moments are about the supplied panel rm.
        """
        geometry = self.sample_geometry(r0, r1, length)
        rm = _array(rm, (self.np, 3), 'body moment reference points')
        shape = (self.np, self.nq, 3)
        span = np.asarray(span)
        if span.shape == (self.np, 3):
            span = np.broadcast_to(span[:, None, :], shape)
        span = _array(span, shape, 'body physical span')
        if np.any(abs(np.sum(span*span, axis=-1)-1) > 2e-10):
            raise ValueError('Body span must contain unit physical vectors')
        velocity = _array(velocity, shape, 'relative body velocity')
        acceleration = _array(absolute_acceleration, shape, 'absolute body acceleration')
        if not np.isfinite(density) or np.real(density) <= 0:
            raise ValueError('Density must be finite and positive')
        if not np.isfinite(added_mass_factor) or np.real(added_mass_factor) < 0:
            raise ValueError('Body apparent-mass factor must be finite and nonnegative')
        along = np.sum(velocity*span, axis=-1)
        transverse = velocity-along[..., None]*span
        transverse_acceleration = acceleration-np.sum(acceleration*span, axis=-1)[..., None]*span
        radius, derivative = self.material['radius'], self.material['dradius_dt']
        weights = geometry['weights']
        # Eq.68: dA/ds * ds cancels the current material-length factor.
        darea_weight = 2*np.pi*radius*derivative*(self.t1-self.t0)[:, None]*self.weights
        lift = (density*along*darea_weight)[..., None]*transverse
        profile = (density*radius*weights)[..., None]*(
            (self.material['Cdf']*norm(velocity))[..., None]*velocity
            +(self.material['Cdp']*norm(transverse))[..., None]*transverse)
        apparent = (-added_mass_factor*density*np.pi*radius**2*weights)[..., None]*transverse_acceleration
        force = lift+profile+apparent
        arm = geometry['position']-rm[:, None, :]
        result = dict(positions=geometry['position'], weights=weights,
                      force_samples=force, moment_samples=np.cross(arm, force),
                      force=force.sum(axis=1), moment=np.cross(arm, force).sum(axis=1))
        for name, value in (('lift', lift), ('profile', profile), ('apparent', apparent)):
            result[name+'_samples'] = value
            result[name+'_moment_samples'] = np.cross(arm, value)
            result[name] = value.sum(axis=1)
            result[name+'_moment'] = np.cross(arm, value).sum(axis=1)
        return result


def jump_loads(jumps, velocity, density):
    """Declared smooth-transition weak-limit lift, Eq.68 integrated over area.

    Includes explicitly declared end transitions if supplied. It adds no blunt
    face drag, separated-flow law, apparent point mass, or intrinsic couple.
    Returned force acts at each supplied position; caller transfers that force.
    """
    velocity = _array(velocity, (len(jumps), 3), 'jump relative velocities')
    if not np.isfinite(density) or np.real(density) <= 0:
        raise ValueError('Density must be finite and positive')
    forces, positions = [], []
    for record, value in zip(jumps, velocity):
        position, tangent, left, right, _ = _jump(record)
        along = np.sum(value*tangent)
        normal = value-along*tangent
        forces.append(density*normal*along*np.pi*(right**2-left**2))
        positions.append(position)
    dtype = np.result_type(velocity, density,
                           *(np.asarray(value) for value in positions))
    force = np.asarray(forces, dtype=dtype).reshape(-1, 3)
    return dict(position=np.asarray(positions, dtype=dtype).reshape(-1, 3),
                force=force, moment=np.zeros_like(force))
