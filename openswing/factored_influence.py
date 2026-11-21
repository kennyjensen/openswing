"""Horseshoe fields with shared wake strengths combined before evaluation.

Only exactly coincident endpoints with identical effective receiver core
columns share a ray. This factorization changes no physical singularity or
bound exclusion. It is a value/circulation operator: geometric derivatives
must retain the original, individually moving source endpoints and cores.
"""
import math
import numpy as np


class EndpointGrouping:
    """Immutable signed endpoint incidence, independent of field coefficients.

    A derivative owns each original endpoint and effective core change. Only
    their weighted contributions are summed here, never their coordinates.
    """
    def _arrays(self):
        return (self.starts, self.ends, self._offsets, self._indices,
                self._signs, self._one, self._two, self._many)

    @property
    def nbytes(self):
        return sum(a.nbytes for a in self._arrays())

    def representative_endpoints(self):
        """Return source index and endpoint sign for each exactly equal group."""
        positions = self._offsets[:-1]
        return self._indices[positions].copy(), self._signs[positions].copy()

    def group_endpoint_weights(self, start_values, end_values):
        """Sum signed source-owned weights; source is the first array axis.

        Weights may contain Gamma times distinct displacement/core columns.
        Equal baseline endpoints do not imply equal weights or movements.
        """
        start_values, end_values = map(np.asarray, (start_values, end_values))
        if (start_values.ndim < 1 or start_values.shape != end_values.shape
                or start_values.shape[0] != self.sources
                or not np.isfinite(start_values).all() or not np.isfinite(end_values).all()):
            raise ValueError('Endpoint weights require equal finite arrays with one row per source.')
        shape = (len(self._offsets)-1,) + start_values.shape[1:]
        result = np.empty(shape, dtype=np.result_type(start_values, end_values, float))
        def terms(k):
            positive = self._signs[k] > 0
            mask = positive.reshape(positive.shape + (1,)*(start_values.ndim-1))
            return np.where(mask, end_values[self._indices[k]], -start_values[self._indices[k]])
        first = self._offsets[self._one]
        result[self._one] = terms(first)
        first = self._offsets[self._two]
        result[self._two] = terms(first) + terms(first+1)
        for group in self._many:
            values = terms(np.arange(self._offsets[group], self._offsets[group+1]))
            flat = values.reshape(len(values), -1)
            summed = [complex(math.fsum(v.real), math.fsum(v.imag))
                      if np.iscomplexobj(v) else math.fsum(v) for v in flat.T]
            result[group] = np.asarray(summed).reshape(start_values.shape[1:])
        return result


    def wake_strengths(self, gamma):
        gamma = np.asarray(gamma)
        if gamma.shape != (self.sources,) or not np.isfinite(gamma).all():
            raise ValueError('Circulation must be a finite vector with one entry per source.')
        return self._wake_values(gamma)

    def wake_columns(self, columns):
        """Apply the same compensated incidence to a batch of circulation directions."""
        columns = np.asarray(columns)
        if columns.ndim != 2 or columns.shape[0] != self.sources or not np.isfinite(columns).all():
            raise ValueError('Circulation columns must have one finite row per source.')
        return self._wake_values(columns)

    def _wake_values(self, gamma):
        trailing = gamma.shape[1:]
        result = np.empty((len(self._offsets)-1,) + trailing,
                          dtype=np.result_type(gamma, float))
        def terms(k):
            return self._signs[k].reshape(k.shape + (1,)*len(trailing)) * gamma[self._indices[k]]
        k = self._offsets[self._one]
        result[self._one] = terms(k)
        k = self._offsets[self._two]
        result[self._two] = terms(k) + terms(k+1)
        # Normal chains use the vectorized two-term sum. Branches need a
        # compensated sum before multiplication by possibly large ray values.
        for group in self._many:
            k = np.arange(self._offsets[group], self._offsets[group+1])
            values = terms(k).reshape(len(k), -1)
            summed = [complex(math.fsum(v.real), math.fsum(v.imag))
                      if np.iscomplexobj(v) else math.fsum(v) for v in values.T]
            result[group] = np.asarray(summed).reshape(trailing)
        return result

class FactoredInfluence(EndpointGrouping):
    """Immutable finite-bound and unique-ray coefficients, without dense incidence.

    ``matrix`` and ``project`` expose circulation Jacobians. Use ``apply`` for
    velocities: expanding the horseshoes first loses the cancellation benefit.
    Copies share read-only storage, including when retained by iteration caches.
    """
    def __init__(self, points, a, b, direction, pg, core=0., ground=None, *,
                 exclude_bound=None, _pairs=None, _name=None):
        from .aero import finite_vortex, semi_infinite_vortex
        points, a, b, direction, pg = [np.asarray(v, dtype=float)
                                     for v in (points, a, b, direction, pg)]
        if (any(v.ndim != 2 or v.shape[1] != 3 for v in (points, a, b))
                or a.shape != b.shape or direction.shape != (3,) or pg.shape != (3, 3)
                or not all(np.isfinite(v).all() for v in (points, a, b, direction, pg))):
            raise ValueError('Vortex geometry must contain finite three-component coordinates.')
        self.receivers, self.sources = len(points), len(a)
        self.shape = (self.receivers, self.sources, 3)
        cores = np.broadcast_to(np.asarray(core, dtype=float), self.shape[:2])
        if not np.isfinite(cores).all() or np.any(cores < 0):
            raise ValueError('Vortex cores must be finite and nonnegative.')
        excluded = None if exclude_bound is None else np.broadcast_to(
            np.asarray(exclude_bound, dtype=bool), cores.shape)
        groups, nodes, core_columns, terms = {}, [], [], []
        starts, ends = [], []
        for source in range(self.sources):
            key_core = np.ascontiguousarray(cores[:, source]).tobytes()
            for point, sign, ids in ((a[source], -1., starts), (b[source], 1., ends)):
                key = (tuple(point), key_core)
                if key not in groups:
                    groups[key] = len(nodes)
                    nodes.append(point)
                    core_columns.append(cores[:, source])
                    terms.append([])
                group = groups[key]
                ids.append(group)
                terms[group].append((source, sign))
        self.starts, self.ends = np.asarray(starts, dtype=int), np.asarray(ends, dtype=int)
        nodes = np.asarray(nodes, dtype=float).reshape(-1, 3)
        ray_core = np.asarray(core_columns, dtype=float).reshape(len(nodes), self.receivers).T
        self._offsets = np.r_[0, np.cumsum([len(t) for t in terms], dtype=int)]
        self._indices = np.array([j for entries in terms for j, _ in entries], dtype=int)
        self._signs = np.array([s for entries in terms for _, s in entries])
        sizes = np.diff(self._offsets)
        self._one = np.flatnonzero(sizes == 1)
        self._two = np.flatnonzero(sizes == 2)
        self._many = np.flatnonzero(sizes > 2)
        images = ground is not None and ground.flag
        # BLAS can round equal-valued strided and contiguous arguments
        # differently. A layout change must invalidate both pair fields as
        # well as the enclosing operator; numeric equality alone is not enough.
        layouts = tuple(None if value is None else (value.shape, value.dtype.str, value.strides)
                        for value in (points, a, b, direction, pg, cores, excluded))
        global_key = (direction.tobytes(), pg.tobytes(), layouts,
                      None if not images else (ground.flag, ground.reflection.tobytes(),
                                               ground.normal.tobytes(), ground.offset,
                                               ground.reflection.strides, ground.normal.strides))

        def component(kind, first, second, radii, mask):
            # Relative transforms are evaluated for the complete arrays before
            # selecting cached pairs. This avoids shape-dependent BLAS rounding.
            relative = segment = image_relative = image_segment = None

            def compute(rows=slice(None), columns=slice(None)):
                nonlocal relative, segment, image_relative, image_segment
                if relative is None:
                    relative = (points[:, None, :] - first[None, :, :]) @ pg.T
                    segment = None if second is None else (second - first)[None, :, :] @ pg.T
                    if images:
                        image_relative = (points[:, None, :] - ground.reflect_points(first)[None, :, :]) @ pg.T
                        image_segment = (None if second is None else
                            (ground.reflect_points(second) - ground.reflect_points(first))[None, :, :] @ pg.T)
                selected = radii[rows][:, columns]
                displacement = relative[rows][:, columns]
                if second is None:
                    value = semi_infinite_vortex(displacement, 0., direction @ pg.T, selected)
                else:
                    value = finite_vortex(displacement, 0., segment[:, columns], selected)
                    if mask is not None:
                        value = np.where(mask[rows][:, columns, None], 0., value)
                if images:
                    if second is None:
                        image = semi_infinite_vortex(image_relative[rows][:, columns], 0.,
                                                     ground.reflect_vectors(direction) @ pg.T, selected)
                    else:
                        image = finite_vortex(image_relative[rows][:, columns], 0.,
                                              image_segment[:, columns], selected)
                    value -= ground.flag * image
                # Cache the same source-contiguous allocation used by apply.
                # Returning its physical tensor view lets pair reuse and the
                # immutable operator share coefficients without a second copy.
                packed = np.ascontiguousarray(np.moveaxis(value @ pg, 1, 2))
                return np.moveaxis(packed, 2, 1)

            if not self.receivers or not len(first):
                return np.zeros((self.receivers, len(first), 3))
            if _pairs is None:
                return compute()
            return _pairs.factored_pairs((_name, kind), global_key, points,
                                         first, second, radii, mask, compute)

        # Keep source coordinates contiguous for repeated BLAS contractions.
        # The physical bound/ray tensors below are views, not duplicate fields.
        # Bound and wake sums remain separate: coincident wake strengths must
        # still cancel before they multiply a possibly large ray coefficient.
        bound = component('bound', a, b, cores, excluded)
        rays = component('rays', nodes, None, ray_core, None)
        self._bound_matrix = np.ascontiguousarray(np.moveaxis(bound, 1, 2)).reshape(
            3*self.receivers, self.sources)
        self._ray_matrix = np.ascontiguousarray(np.moveaxis(rays, 1, 2)).reshape(
            3*self.receivers, len(nodes))
        self.setflags(write=False)

    @property
    def bound(self):
        return self._bound_matrix.reshape(self.receivers, 3, self.sources).transpose(0, 2, 1)

    @property
    def rays(self):
        return self._ray_matrix.reshape(self.receivers, 3, len(self._offsets)-1).transpose(0, 2, 1)

    def _arrays(self):
        return (self._bound_matrix, self._ray_matrix, *super()._arrays())

    def endpoint_grouping(self):
        """Share only immutable incidence storage with a derivative owner."""
        result = EndpointGrouping()
        result.sources = self.sources
        for name in ('starts', 'ends', '_offsets', '_indices', '_signs', '_one', '_two', '_many'):
            setattr(result, name, getattr(self, name))
        return result

    @property
    def nbytes(self):
        """All retained numeric storage, including sparse endpoint incidence."""
        return sum(a.nbytes for a in self._arrays())

    def setflags(self, *, write=False):
        if write:
            raise ValueError('Factored influence coefficients are immutable.')
        for array in self._arrays():
            array.setflags(write=False)

    def copy(self):
        return self  # Immutable value; cache capture/replay needs no tensor copy.

    def assert_equal(self, other):
        if not isinstance(other, FactoredInfluence) or self.shape != other.shape:
            raise AssertionError('Changed captured influence representation.')
        for first, second in zip(self._arrays(), other._arrays()):
            np.testing.assert_array_equal(first, second)

    def apply(self, gamma):
        strengths = self.wake_strengths(gamma)
        return (self._bound_matrix @ gamma + self._ray_matrix @ strengths).reshape(
            self.receivers, 3)

    def apply_columns(self, columns):
        columns = np.asarray(columns)
        if columns.ndim != 2 or columns.shape[0] != self.sources or not np.isfinite(columns).all():
            raise ValueError('Circulation columns must have one finite row per source.')
        if columns.shape[1] == 0:
            return np.empty((self.receivers, 3, 0), dtype=np.result_type(columns, float))
        strengths = self.wake_columns(columns)
        return (self._bound_matrix @ columns + self._ray_matrix @ strengths).reshape(
            self.receivers, 3, columns.shape[1])

    def matrix(self):
        return self.bound + self.rays[:, self.ends] - self.rays[:, self.starts]

    def projected(self, normals):
        """Prepare fixed scalar coefficients for repeated nonlinear residuals."""
        return ProjectedInfluence(self, normals)

    def project(self, normals):
        normals = np.asarray(normals)
        if normals.shape != (self.receivers, 3) or not np.isfinite(normals).all():
            raise ValueError('Projection requires one finite normal per receiver.')
        result = np.einsum('ijk,ik->ij', self.bound, normals)
        rays = np.einsum('ijk,ik->ij', self.rays, normals)
        result += rays[:, self.ends] - rays[:, self.starts]
        return result


class ProjectedInfluence:
    """A fixed normal projection retaining factored wake-strength evaluation."""
    def __init__(self, operator, normals):
        normals = np.asarray(normals)
        if normals.shape != (operator.receivers, 3) or not np.isfinite(normals).all():
            raise ValueError('Projection requires one finite normal per receiver.')
        self.grouping = operator.endpoint_grouping()
        self.bound = np.einsum('ijk,ik->ij', operator.bound, normals)
        self.rays = np.einsum('ijk,ik->ij', operator.rays, normals)
        self.bound.setflags(write=False)
        self.rays.setflags(write=False)

    @property
    def nbytes(self):
        return self.bound.nbytes + self.rays.nbytes + self.grouping.nbytes

    def apply(self, gamma):
        strengths = self.grouping.wake_strengths(gamma)
        return self.bound @ gamma + self.rays @ strengths

    def matrix(self):
        return self.bound + self.rays[:, self.grouping.ends] - self.rays[:, self.grouping.starts]
