"""Direct derivatives of the existing regularized Biot--Savart integrals.

The physical core, principal-value mask, PG map and image signs are unchanged.
These partials hold the PG tensor and ground plane fixed. Their variation with
flight state belongs to a separate chain rule. No geometry is frozen here.
"""
import numpy as np
from .aero import AnalysisError, _relative_pg
from .factored_influence import FactoredInfluence
from .geometry import normalize
from .vector_ops import cross3, dot3


class VortexDerivativeUnavailable(ValueError):
    pass


class VortexSourceTangent:
    """One owned endpoint/core baseline for the geometry assembly's queries."""
    def __init__(self, a, b, core, physical, *, limit=128*1024**2):
        arrays = [np.asarray(v, dtype=float) for v in (a, b, core)]
        arrays.append(np.asarray(physical))
        a, b, core, physical = arrays
        if a.ndim != 2 or a.shape[1] != 3 or b.shape != a.shape or core.shape != (len(a),) or physical.shape != core.shape:
            raise VortexDerivativeUnavailable('Invalid shared vortex-source layout.')
        self.bytes = sum(value.nbytes for value in arrays)
        if self.bytes > limit:
            raise VortexDerivativeUnavailable('Shared vortex sources exceed their storage budget.')
        for name, value in zip(('a', 'b', 'core', 'physical'), arrays):
            if not np.all(np.isfinite(value)):
                raise VortexDerivativeUnavailable('Nonfinite shared vortex sources.')
            owned = value.copy(); owned.flags.writeable = False
            setattr(self, name, owned)

    def difference(self, a, b, core, physical):
        """An owned source-change snapshot, used only for this field evaluation."""
        a, b, core = [np.asarray(v, dtype=float) for v in (a, b, core)]
        if a.shape != self.a.shape or b.shape != self.b.shape or core.shape != self.core.shape or not np.array_equal(physical, self.physical):
            raise VortexDerivativeUnavailable('Changed shared vortex-source layout.')
        return _VortexSourceChange(self, a-self.a, b-self.b, core-self.core)


class _VortexSourceChange:
    def __init__(self, source, a, b, core):
        self.source, self.a, self.b, self.core = source, a, b, core
        self.motion = np.any(a != 0., axis=1) | np.any(b != 0., axis=1)
        self.core_changed = core != 0.
        self.motion_indices = np.flatnonzero(self.motion).copy()
        self.indices = np.flatnonzero(self.motion | self.core_changed).copy()
        for value in vars(self).values():
            if isinstance(value, np.ndarray):value.flags.writeable = False


def cross_matrix(v):
    """Matrix mapping a vector w to v cross w."""
    v = np.asarray(v)
    out = np.zeros(v.shape[:-1]+(3, 3), dtype=v.dtype)
    out[..., 0, 1], out[..., 0, 2] = -v[..., 2], v[..., 1]
    out[..., 1, 0], out[..., 1, 2] = v[..., 2], -v[..., 0]
    out[..., 2, 0], out[..., 2, 1] = -v[..., 1], v[..., 0]
    return out


def outer(a, b):
    return a[..., :, None]*b[..., None, :]


def geometry(points, origin, u, core):
    r = np.asarray(points, dtype=float)-origin
    z = dot3(r, u)
    h = r-z[..., None]*u
    den = dot3(h, h)+np.asarray(core, dtype=float)**2
    return r, z, h, den, np.maximum(den, 1e-30)


def checked(partials, active):
    result = {}
    for name, value in partials.items():
        mask = active[..., None] if name == 'core' else active[..., None, None]
        result[name] = np.where(mask, value/(4*np.pi), 0.)
        if not np.all(np.isfinite(result[name])):
            raise VortexDerivativeUnavailable('Nonfinite direct vortex derivative.')
    return result


def finite_partials(points, a, b, core=0.):
    """Velocity Jacobians for receiver, both endpoints and core radius.

    Each vector Jacobian has (..., output_xyz, input_xyz) axes; the core
    derivative has (..., output_xyz). All leading axes broadcast as in aero.
    """
    d = np.asarray(b, dtype=float)-a
    length = np.linalg.norm(d, axis=-1)
    if np.any(length <= 0):
        raise AnalysisError('Zero-length vortex segment.')
    u = d/length[..., None]
    r, z, h, den, q = geometry(points, a, u, core)
    outside = (z < 0) | (z > length)
    if np.any((den == 1e-26) & ~outside):
        raise VortexDerivativeUnavailable('Vortex derivative is undefined at the self-influence switch.')
    # Outside the segment the integral is regular even on its axis. Use its
    # actual radial distance and rationalized limit, with no artificial core.
    q = np.where(outside, den, q)
    first = np.sqrt(z*z+q)
    second = np.sqrt((z-length)**2+q)
    f = np.divide(z/first-(z-length)/second, q, out=np.zeros_like(q), where=~outside)
    product = (z*second+(z-length)*first)
    stable = np.divide(length*(2*z-length), product*first*second,
                       out=np.zeros_like(q), where=outside)
    f = np.where(outside, stable, f)
    # Rationalize R1-R0 before differencing inverse cubes, including far field.
    difference = length*(length-2*z)/(second+first)
    fz = difference*(second*second+second*first+first*first)/(first**3*second**3)
    fl = 1/second**3
    fq = np.divide(-(z/first**3-(z-length)/second**3)/2-f, q,
                   out=np.zeros_like(q), where=~outside)
    ratio = np.divide((z/second+(z-length)/first)/2, product,
                      out=np.zeros_like(q), where=outside)
    fq = np.where(outside, -f*(ratio+.5/first**2+.5/second**2), fq)
    w = cross3(u, r)
    projection = np.eye(3)-outer(u, u)
    point = f[..., None, None]*cross_matrix(u)+outer(w, fz[..., None]*u+2*fq[..., None]*h)
    end = -f[..., None, None]*(cross_matrix(r)@projection)/length[..., None, None]
    end += outer(w, fl[..., None]*u+((fz-2*z*fq)/length)[..., None]*h)
    radius = w*(2*np.asarray(core)*fq)[..., None]
    return checked(dict(point=point, a=-point-end, b=end, core=radius), (den > 1e-26) | outside)


def semi_infinite_partials(points, origin, direction, core=0.):
    """Velocity Jacobians including normalization of the supplied direction."""
    direction = np.asarray(direction, dtype=float)
    u = normalize(direction)
    length = np.linalg.norm(direction, axis=-1)
    r, z, h, den, q = geometry(points, origin, u, core)
    upstream = z < 0
    if np.any((den == 1e-26) & ~upstream):
        raise VortexDerivativeUnavailable('Vortex derivative is undefined at the self-influence switch.')
    q = np.where(upstream, den, q)
    distance = np.sqrt(z*z+q)
    f = np.divide(1+z/distance, q, out=np.zeros_like(q), where=~upstream)
    stable = np.divide(1., distance*(distance-z), out=np.zeros_like(q), where=upstream)
    f = np.where(upstream, stable, f)
    fz = 1/distance**3
    fq = np.divide(-z/(2*distance**3)-f, q, out=np.zeros_like(q), where=~upstream)
    fq = np.where(upstream, -.5*f*(1/distance**2+f), fq)
    w = cross3(u, r)
    projection = np.eye(3)-outer(u, u)
    point = f[..., None, None]*cross_matrix(u)+outer(w, fz[..., None]*u+2*fq[..., None]*h)
    wind = -f[..., None, None]*(cross_matrix(r)@projection)/length[..., None, None]
    wind += outer(w, ((fz-2*z*fq)/length)[..., None]*h)
    radius = w*(2*np.asarray(core)*fq)[..., None]
    return checked(dict(point=point, origin=-point, direction=wind, core=radius), (den > 1e-26) | upstream)


def horseshoe_partials(points, a, b, direction, core=0., *, exclude_bound=None):
    bound = finite_partials(points, a, b, core)
    if exclude_bound is not None:
        mask = np.asarray(exclude_bound)
        bound = {name:np.where(mask[..., None] if name == 'core' else mask[..., None, None], 0., value)
                 for name, value in bound.items()}
    first = semi_infinite_partials(points, a, direction, core)
    second = semi_infinite_partials(points, b, direction, core)
    return dict(point=bound['point']+second['point']-first['point'],
                a=bound['a']-first['origin'], b=bound['b']+second['origin'],
                direction=second['direction']-first['direction'],
                core=bound['core']+second['core']-first['core'])


def horseshoe_velocity_partials(points, a, b, direction, pg, core=0., ground=None, *, exclude_bound=None):
    """Physical-coordinate partials, with fixed PG and image-plane parameters."""
    points, a, b, direction, pg = map(np.asarray, (points, a, b, direction, pg))
    def relative(first, second, segment, wind, excluded=None):
        bound = finite_partials(first, 0., segment, core)
        if excluded is not None:
            mask = np.asarray(excluded)
            bound = {name:np.where(mask[..., None] if name == 'core' else mask[..., None, None], 0., value)
                     for name, value in bound.items()}
        start = semi_infinite_partials(first, 0., wind, core)
        end = semi_infinite_partials(second, 0., wind, core)
        # Relative operands retain the same physical endpoint chain rule:
        # r1=p-a, r2=p-b, d=b-a.
        return dict(point=bound['point']+end['point']-start['point'],
                    a=bound['a']-start['origin'], b=bound['b']+end['origin'],
                    direction=end['direction']-start['direction'],
                    core=bound['core']+end['core']-start['core'])
    result = relative(*_relative_pg(points, a, b, pg), direction@pg.T, exclude_bound)
    result = {name:(value@pg if name == 'core' else pg.T@value@pg)
              for name, value in result.items()}
    if ground is not None and ground.flag:
        image = relative(*_relative_pg(points, ground.reflect_points(a), ground.reflect_points(b), pg),
                         ground.reflect_vectors(direction)@pg.T)
        for name in result:
            value = image[name]
            if name == 'core':
                value = value@pg
            else:
                input_map = pg@ground.reflection if name in ('a', 'b', 'direction') else pg
                value = pg.T@value@input_map
            result[name] = result[name]-ground.flag*value
    return result


class VortexFieldTangent:
    """Owned, circulation-contracted derivative for one fixed query layout.

    ``value`` evaluates the first-order field about the captured geometry. It
    belongs ONLY in derivative assembly; it is not a nonlinear flow evaluator.
    Changed receiver rows and source columns are applied without reevaluating
    every source/receiver interaction for every structural coordinate.
    """
    def __init__(self, points, a, b, direction, pg, core, gamma, ground=None,
                 *, exclude_bound=None, single_dot=False, limit=128*1024**2,
                 _source=None, _physical=None):
        points, a, b = [np.asarray(v, dtype=float) for v in (points, a, b)]
        gamma = np.asarray(gamma, dtype=float)
        if points.ndim != 2 or points.shape[1] != 3 or a.shape != b.shape or a.shape != (len(gamma), 3):
            raise VortexDerivativeUnavailable('Invalid retained vortex-field layout.')
        count, sources = len(points), len(gamma)
        # Conservative retained-storage bound before allocating the partials.
        required = 8*(count*sources*22+count*15+sources*6)
        if required > limit:
            raise VortexDerivativeUnavailable('Retained vortex-field derivatives exceed their storage budget.')
        self.points, self.a, self.b = [v.copy() for v in (points, a, b)]
        self.core = np.broadcast_to(np.asarray(core, dtype=float), (count, sources)).copy()
        self._source = _source
        self._physical = None if _physical is None else np.asarray(_physical).copy()
        shared_arrays = []
        if _source is not None:
            if not np.array_equal(a, _source.a) or not np.array_equal(b, _source.b):
                raise VortexDerivativeUnavailable('Mismatched shared vortex-source baseline.')
            if self._physical is not None and self._physical.shape != (count,):
                raise VortexDerivativeUnavailable('Invalid shared vortex receiver layout.')
            self.core_active = (np.ones(self.core.shape, dtype=bool) if self._physical is None else
                                self._physical[:, None] != _source.physical[None, :])
            if not np.array_equal(self.core, np.where(self.core_active, _source.core[None, :], 0.)):
                raise VortexDerivativeUnavailable('Mismatched shared vortex core exclusions.')
            self.active_columns = np.any(self.core_active, axis=0)
            self.all_core_active = bool(np.all(self.active_columns))
            self.any_core_active = bool(np.any(self.active_columns))
            shared_arrays.extend((self.core_active, self.active_columns))
        if self._physical is not None:shared_arrays.append(self._physical)
        arguments = (points[:, None, :], a[None, :, :], b[None, :, :], direction, pg, self.core, ground)
        # A stencil can leave the principal-value mask even when the base
        # point is inside it. The derivative of that constant masked branch
        # cannot replace the physical stencil. Exterior segment axes and
        # upstream ray axes are regular and use their exact derivatives.
        # Bound exclusions are permanent; their masked derivatives are safe.
        def check_mask(origins, ends, wind, excluded):
            first, second, segment = _relative_pg(points[:, None, :], origins[None, :, :], ends[None, :, :], pg)
            length = np.linalg.norm(segment, axis=-1)
            if np.any(length <= 0):
                raise VortexDerivativeUnavailable('Zero-length retained vortex segment.')
            _, axial, _, radial, _ = geometry(first, 0., segment/length[..., None], self.core)
            bound_mask = (radial <= 1e-26) & (axial >= 0) & (axial <= length)
            if excluded is not None:bound_mask &= ~np.asarray(excluded, dtype=bool)
            direction_pg = normalize(wind@pg.T)
            masked = np.any(bound_mask)
            for receiver in (first, second):
                _, axial, _, radial, _ = geometry(receiver, 0., direction_pg, self.core)
                masked |= np.any((radial <= 1e-26) & (axial >= 0))
            if masked:
                raise VortexDerivativeUnavailable('A retained vortex stencil can leave the principal-value mask; use full physical differences.')
        check_mask(a, b, np.asarray(direction), exclude_bound)
        if ground is not None and ground.flag:
            check_mask(ground.reflect_points(a), ground.reflect_points(b),
                       ground.reflect_vectors(direction), None)
        # Value grouping must not merge the independently moving endpoints or
        # cores in the partials below. The base uses the same stable arithmetic
        # as nonlinear evaluation, including one-receiver point/shoulder calls.
        # single_dot remains an accepted legacy keyword; it no longer selects
        # a different value contraction.
        operator = FactoredInfluence(points, a, b, direction, pg, self.core,
            ground, exclude_bound=exclude_bound)
        self.base = operator.apply(gamma)
        self.grouping = operator.endpoint_grouping()
        self.gamma = gamma.copy()
        source_ids, signs = self.grouping.representative_endpoints()
        nodes = np.where((signs > 0)[:, None], b[source_ids], a[source_ids])
        ray_core = self.core[:, source_ids]
        needed = 8*(count*sources*22+count*len(nodes)*12+count*15+sources*9)+self.grouping.nbytes
        if needed > limit:
            raise VortexDerivativeUnavailable('Grouped vortex derivatives exceed their storage budget.')

        # Bound derivatives retain source ownership. Coincident ray values
        # share derivatives only after summing their individually weighted
        # circulation/motion, never by imposing shared endpoint motion.
        def bound_partials(first, second, excluded):
            relative, _, segment = _relative_pg(points[:, None, :], first[None, :, :], second[None, :, :], pg)
            result = finite_partials(relative, 0., segment, self.core)
            if excluded is not None:
                mask = np.asarray(excluded)
                result = {k:np.where(mask[..., None] if k == 'core' else mask[..., None, None], 0., v)
                          for k,v in result.items()}
            return result

        def ray_partials(origins, wind):
            return semi_infinite_partials((points[:, None, :]-origins[None, :, :])@pg.T,
                                          0., np.asarray(wind)@pg.T, ray_core)

        bound = bound_partials(a, b, exclude_bound)
        rays = ray_partials(nodes, direction)
        bound = {k:(v@pg if k == 'core' else pg.T@v@pg) for k,v in bound.items()}
        rays = {k:(v@pg if k == 'core' else pg.T@v@pg) for k,v in rays.items()}
        if ground is not None and ground.flag:
            image_bound = bound_partials(ground.reflect_points(a), ground.reflect_points(b), None)
            image_rays = ray_partials(ground.reflect_points(nodes), ground.reflect_vectors(direction))
            for target,image in ((bound,image_bound),(rays,image_rays)):
                for k,v in image.items():
                    mapped = v@pg if k == 'core' else pg.T@v@(pg@ground.reflection if k in ('a','b','origin','direction') else pg)
                    target[k] -= ground.flag*mapped
        strengths = operator.wake_strengths(gamma)
        self.receiver = (np.einsum('ijab,j->iab', bound['point'], gamma)
                         + np.einsum('ijab,j->iab', rays['point'], strengths))
        self.source_a = bound['a']*gamma[None, :, None, None]
        self.source_b = bound['b']*gamma[None, :, None, None]
        self.radius = bound['core']*gamma[None, :, None]
        self.ray_origin, self.ray_radius = rays['origin'], rays['core']
        arrays = (self.points, self.a, self.b, self.core, self.base, self.receiver,
                  self.source_a, self.source_b, self.radius, self.ray_origin,
                  self.ray_radius, self.gamma, *shared_arrays)
        self.bytes = sum(value.nbytes for value in arrays)+self.grouping.nbytes
        if self.bytes > limit:
            raise VortexDerivativeUnavailable('Retained vortex-field derivatives exceed their storage budget.')
        for value in arrays:
            if not np.all(np.isfinite(value)):
                raise VortexDerivativeUnavailable('Nonfinite retained vortex-field derivative.')
            value.flags.writeable = False

    def value(self, points, a, b, core):
        points, a, b = [np.asarray(v, dtype=float) for v in (points, a, b)]
        if points.shape != self.points.shape or a.shape != self.a.shape or b.shape != self.b.shape:
            raise VortexDerivativeUnavailable('Changed retained vortex-field layout.')
        dc = np.broadcast_to(np.asarray(core, dtype=float), self.core.shape)-self.core
        da, db = a-self.a, b-self.b
        sources = np.flatnonzero(np.any(da != 0., axis=1) | np.any(db != 0., axis=1) | np.any(dc != 0., axis=0))
        return self._apply(points, sources, da[sources], db[sources], dc[:, sources])

    def value_shared(self, points, change, physical=None):
        """Apply an explicit snapshot; receiver/core exclusions remain per query."""
        points = np.asarray(points, dtype=float)
        if points.shape != self.points.shape:
            raise VortexDerivativeUnavailable('Changed retained vortex-field layout.')
        if self._source is None or change.source is not self._source:
            raise VortexDerivativeUnavailable('Mismatched shared vortex-source change.')
        if (physical is None) != (self._physical is None) or (physical is not None and not np.array_equal(physical, self._physical)):
            raise VortexDerivativeUnavailable('Changed shared vortex core exclusions.')
        if self.all_core_active:sources = change.indices
        elif not self.any_core_active:sources = change.motion_indices
        else:sources = np.flatnonzero(change.motion | (change.core_changed & self.active_columns))
        da = db = dc = None
        if len(sources):
            da, db = change.a[sources], change.b[sources]
            # Original dc[:, sources] has receiver-contiguous column storage.
            # Preserve that layout and contraction order for exact equality.
            dc = np.array(np.where(self.core_active[:, sources], change.core[None, sources], 0.), order='F')
        return self._apply(points, sources, da, db, dc)

    def _apply(self, points, sources, da, db, dc):
        dp = points-self.points
        receivers = np.flatnonzero(np.any(dp != 0., axis=1))
        result = self.base.copy()
        if len(receivers):
            result[receivers] += np.einsum('iab,ib->ia', self.receiver[receivers], dp[receivers])
        if len(sources):
            result += np.einsum('ijab,jb->ia', self.source_a[:, sources], da)
            result += np.einsum('ijab,jb->ia', self.source_b[:, sources], db)
            result += np.einsum('ija,ij->ia', self.radius[:, sources], dc)
            result += self._ray_change(sources, da, db, dc)
        return result

    def _ray_change(self, sources, da, db, dc):
        """Combine source-owned motion weights before large ray derivatives."""
        result = np.zeros((len(self.points), 3))
        if np.any(da) or np.any(db):
            starts = np.zeros_like(self.a); ends = np.zeros_like(self.b)
            starts[sources] = self.gamma[sources, None]*da
            ends[sources] = self.gamma[sources, None]*db
            motion = self.grouping.group_endpoint_weights(starts, ends)
            # Keep the original compensated incidence and source ownership.
            # Equal baseline endpoints may have different displacement weights.
            moved = np.flatnonzero(np.any(motion != 0., axis=1))
            if len(moved):
                result += np.einsum('ijab,jb->ia', self.ray_origin[:, moved], motion[moved])
        if np.any(dc):
            cores = np.zeros((len(self.gamma), len(self.points)))
            cores[sources] = self.gamma[sources, None]*dc.T
            radii = self.grouping.group_endpoint_weights(cores, cores).T
            # Core changes remain receiver dependent, including at zero base
            # core where distinct physical exclusion masks can share a group.
            changed = np.flatnonzero(np.any(radii != 0., axis=0))
            if len(changed):
                result += np.einsum('ija,ij->ia', self.ray_radius[:, changed], radii[:, changed])
        return result

    def source_columns(self, sources, da, db, dc, *, core_active):
        """Apply source-owned geometry columns, including grouped wake rays.

        Endpoint directions have shape (selected sources, 3, columns); core
        directions have shape (selected sources, columns). ``core_active``
        retains each receiver's physical-index exclusion. Columns share the
        bound contraction, while ray motion is grouped one column at a time:
        this avoids retaining a receiver × source × column core tensor.
        Receiver motion is separate and uses ``receiver``.
        """
        sources = np.asarray(sources)
        da, db, dc = [np.asarray(v, dtype=float) for v in (da, db, dc)]
        active = np.asarray(core_active, dtype=bool)
        if (sources.ndim != 1 or not np.issubdtype(sources.dtype, np.integer)
                or np.any((sources < 0) | (sources >= len(self.gamma)))
                or np.any(np.diff(sources) <= 0)
                or da.ndim != 3 or da.shape[:2] != (len(sources), 3)
                or db.shape != da.shape or not 0 < da.shape[-1] <= 32
                or dc.shape != (len(sources), da.shape[-1])
                or active.shape != (len(self.points), len(sources))):
            raise VortexDerivativeUnavailable('Invalid retained vortex source-column layout.')
        if not all(np.all(np.isfinite(v)) for v in (da, db, dc)):
            raise VortexDerivativeUnavailable('Nonfinite retained vortex source columns.')
        result = np.zeros((len(self.points), 3, da.shape[-1]))
        if not len(sources):return result
        result += np.einsum('ijab,jbk->iak', self.source_a[:, sources], da)
        result += np.einsum('ijab,jbk->iak', self.source_b[:, sources], db)
        if np.any(dc) and np.any(active):
            result += np.einsum('ija,jk->iak', self.radius[:, sources]*active[:, :, None], dc)
        for k in range(da.shape[-1]):
            result[:, :, k] += self._ray_change(sources, da[:, :, k], db[:, :, k],
                np.where(active, dc[None, :, k], 0.))
        return result

    def values_shared(self, points, changes, physical, *, _packed=False):
        """Apply matching source supports to several original stencil samples.

        The same receiver/a/b/core accumulation order is used. A change of
        support within the group keeps the individual application path.
        """
        if len(points)!=len(changes) or len(points)!=len(physical):
            raise VortexDerivativeUnavailable('Changed batched vortex-field layout.')
        if len(points)==0:return []
        arrays=[np.asarray(p,dtype=float) for p in points]
        if any(p.shape!=self.points.shape for p in arrays):
            raise VortexDerivativeUnavailable('Changed batched vortex-field layout.')
        selected=[];receivers=[];displacements=[]
        for p,change,owners in zip(arrays,changes,physical):
            if self._source is None or change.source is not self._source:
                raise VortexDerivativeUnavailable('Mismatched shared vortex-source change.')
            if (owners is None)!=(self._physical is None) or (owners is not None and not np.array_equal(owners,self._physical)):
                raise VortexDerivativeUnavailable('Changed shared vortex core exclusions.')
            if self.all_core_active:sources=change.indices
            elif not self.any_core_active:sources=change.motion_indices
            else:sources=np.flatnonzero(change.motion | (change.core_changed & self.active_columns))
            selected.append(sources);dp=p-self.points;displacements.append(dp)
            receivers.append(np.flatnonzero(np.any(dp!=0.,axis=1)))
        if any(not np.array_equal(selected[0],s) or not np.array_equal(receivers[0],q)
               for s,q in zip(selected[1:],receivers[1:])):
            return [self.value_shared(p,c,o) for p,c,o in zip(arrays,changes,physical)]
        sources=selected[0];moved=receivers[0]
        result=np.broadcast_to(self.base,(len(arrays),)+self.base.shape).copy()
        if len(moved):
            dp=np.array([p[moved] for p in displacements])
            result[:,moved]+=np.einsum('iab,sib->sia',self.receiver[moved],dp)
        if len(sources):
            da=np.array([c.a[sources] for c in changes]);db=np.array([c.b[sources] for c in changes])
            if _packed:
                dc=np.array([c.core[sources] for c in changes])
                from .field_products import source_product
                result+=source_product(self.source_a[:,sources],self.source_b[:,sources],
                    self.radius[:,sources]*self.core_active[:,sources,None],da,db,dc)
            else:
                dc=np.array([np.where(self.core_active[:,sources],c.core[None,sources],0.) for c in changes])
                result+=np.einsum('ijab,sjb->sia',self.source_a[:,sources],da)
                result+=np.einsum('ijab,sjb->sia',self.source_b[:,sources],db)
                result+=np.einsum('ija,sij->sia',self.radius[:,sources],dc)
            for i,change in enumerate(changes):
                core_change = np.where(self.core_active[:,sources], change.core[None,sources], 0.)
                result[i] += self._ray_change(sources, da[i], db[i], core_change)
        return list(result)
