"""Fixed-circulation horseshoe columns including the complete PG chain rule.

The ground plane and physical core are fixed. Coincident baseline wake rays
share partials only after signed circulation and source-owned motion weights
are combined; independent endpoint displacements are never identified.
"""
import numpy as np
from .aero import finite_vortex, semi_infinite_vortex
from .factored_influence import FactoredInfluence
from .vortex_tangent import finite_partials, semi_infinite_partials, VortexDerivativeUnavailable


_STORAGE_LIMIT = 128*1024**2
_PAIR_BLOCK = 4096
_RECEIVER_BLOCK = 64


def vortex_state_columns(points, a, b, direction, pg, core, gamma,
                         point_columns, a_columns, b_columns, direction_columns,
                         pg_columns, ground=None, *, exclude_bound=None, baseline=None):
    """Return ``(receiver, xyz, column)`` physical velocity derivatives.

    Geometry columns have shape ``(point/source, 3, k)``, wake-direction
    columns ``(3, k)``, and PG columns ``(3, 3, k)``. Gamma and each effective
    receiver/source core are held fixed. The supplied direction need not be
    normalized: the ray partial differentiates its normalization as well.

    ``baseline`` may supply a compatible FactoredInfluence endpoint grouping.
    Its cached velocity coefficients are not used. Otherwise the physical
    baseline is constructed once. Real own-bound exclusions never remove the
    image bound leg. Existing physical principal-value branches are retained.
    """
    points, a, b, direction, pg, gamma = [np.asarray(v, dtype=float) for v in
                                        (points, a, b, direction, pg, gamma)]
    pc, ac, bc, dc, gc = [np.asarray(v, dtype=float) for v in
                        (point_columns, a_columns, b_columns, direction_columns, pg_columns)]
    if (points.ndim != 2 or points.shape[1:] != (3,) or a.ndim != 2 or a.shape[1:] != (3,)
            or b.shape != a.shape or direction.shape != (3,) or pg.shape != (3, 3)
            or gamma.shape != (len(a),) or pc.ndim != 3 or pc.shape[:2] != points.shape):
        raise VortexDerivativeUnavailable('Invalid vortex state-column layout.')
    nr, ns, nk = len(points), len(a), pc.shape[-1]
    if (ac.shape != (ns, 3, nk) or bc.shape != ac.shape or dc.shape != (3, nk)
            or gc.shape != (3, 3, nk)):
        raise VortexDerivativeUnavailable('Invalid vortex state-column layout.')
    if not all(np.isfinite(v).all() for v in (points, a, b, direction, pg, gamma, pc, ac, bc, dc, gc)):
        raise VortexDerivativeUnavailable('Nonfinite vortex state input or columns.')
    try:
        cores = np.broadcast_to(np.asarray(core, dtype=float), (nr, ns))
        excluded = None if exclude_bound is None else np.broadcast_to(
            np.asarray(exclude_bound, dtype=bool), (nr, ns))
    except ValueError as error:
        raise VortexDerivativeUnavailable('Invalid vortex core or exclusion layout.') from error
    if not np.isfinite(cores).all() or np.any(cores < 0):
        raise VortexDerivativeUnavailable('Vortex cores must be finite and nonnegative.')
    # Include grouped/source-owned weights and their reflected copies, not
    # just the returned columns. Pair partials are blocked separately below.
    if 8*(3*nr*nk+24*ns*nk+100*ns) > _STORAGE_LIMIT:
        raise VortexDerivativeUnavailable('Vortex state columns exceed their storage budget.')
    result = np.zeros((nr, 3, nk))
    if not nr or not ns or not nk:
        return result
    if baseline is None:
        if 8*nr*ns*32 > _STORAGE_LIMIT:
            raise VortexDerivativeUnavailable('Vortex state baseline exceeds its storage budget.')
        baseline = FactoredInfluence(points, a, b, direction, pg, cores, ground,
                                     exclude_bound=excluded)
    if not isinstance(baseline, FactoredInfluence) or baseline.shape != (nr, ns, 3):
        raise VortexDerivativeUnavailable('Incompatible vortex state baseline layout.')
    grouping = baseline.endpoint_grouping()
    ids, signs = grouping.representative_endpoints()
    nodes = np.where((signs > 0)[:, None], b[ids], a[ids])
    if not np.array_equal(nodes[grouping.starts], a) or not np.array_equal(nodes[grouping.ends], b):
        raise VortexDerivativeUnavailable('Incompatible vortex state endpoint grouping.')
    strengths = grouping.wake_strengths(gamma)
    motions = grouping.group_endpoint_weights(gamma[:, None, None]*ac, gamma[:, None, None]*bc)
    block = max(1, min(_RECEIVER_BLOCK, _PAIR_BLOCK//max(ns, len(nodes))))
    images = ground is not None and ground.flag

    def accumulate(rows, first, second, origins, wind, da, db, origin_motion, dw, factor, mask):
        # Relative coordinates preserve the physical operator's subtraction
        # order, including translated ground images and the inner PG map.
        physical = points[rows, None, :]-first[None, :, :]
        segment = second-first
        relative, transformed_segment = physical@pg.T, segment@pg.T
        bound = finite_partials(relative, 0., transformed_segment[None, :, :], cores[rows])
        value = finite_vortex(relative, 0., transformed_segment[None, :, :], cores[rows])
        if mask is not None:
            bound['point'] = np.where(mask[..., None, None], 0., bound['point'])
            bound['b'] = np.where(mask[..., None, None], 0., bound['b'])
            value = np.where(mask[..., None], 0., value)
        ray_physical = points[rows, None, :]-origins[None, :, :]
        ray_relative, ray_direction = ray_physical@pg.T, wind@pg.T
        ray_core = cores[rows][:, ids]
        ray = semi_infinite_partials(ray_relative, 0., ray_direction, ray_core)
        ray_value = semi_infinite_vortex(ray_relative, 0., ray_direction, ray_core)
        raw_base = np.einsum('rsi,s->ri', value, gamma)+np.einsum('rgi,g->ri', ray_value, strengths)
        for k in range(nk):
            dpg = gc[:, :, k]
            dr = (pc[rows, None, :, k]-da[None, :, :, k])@pg.T+physical@dpg.T
            ds = (db[:, :, k]-da[:, :, k])@pg.T+segment@dpg.T
            raw = (np.einsum('rsij,rsj,s->ri', bound['point'], dr, gamma)
                   +np.einsum('rsij,sj,s->ri', bound['b'], ds, gamma))
            # Incidence is applied to Gamma*motion before multiplying the
            # possibly near-singular shared ray partial. This also retains
            # different motions at exactly coincident baseline endpoints.
            ray_dr = ((pc[rows, None, :, k]*strengths[None, :, None]
                       -origin_motion[None, :, :, k])@pg.T
                      +(ray_physical@dpg.T)*strengths[None, :, None])
            ray_dw = dw[:, k]@pg.T+wind@dpg.T
            raw += (np.einsum('rgij,rgj->ri', ray['point'], ray_dr)
                    +np.einsum('rgij,j,g->ri', ray['direction'], ray_dw, strengths))
            # Physical velocity is raw_velocity @ PG, so the outer map has
            # its own state derivative in addition to the inner coordinates.
            result[rows, :, k] += factor*(raw@pg+raw_base@dpg)

    for start in range(0, nr, block):
        rows = slice(start, min(nr, start+block))
        if (not np.array_equal(cores[rows][:, ids[grouping.starts]], cores[rows])
                or not np.array_equal(cores[rows][:, ids[grouping.ends]], cores[rows])):
            raise VortexDerivativeUnavailable('Incompatible vortex state core grouping.')
        accumulate(rows, a, b, nodes, direction, ac, bc, motions, dc, 1.,
                   None if excluded is None else excluded[rows])
        if images:
            reflection = ground.reflection
            transform = lambda columns: np.einsum('ij,...jk->...ik', reflection, columns)
            accumulate(rows, ground.reflect_points(a), ground.reflect_points(b),
                       ground.reflect_points(nodes), ground.reflect_vectors(direction),
                       transform(ac), transform(bc), transform(motions), reflection@dc,
                       -ground.flag, None)
    if not np.isfinite(result).all():
        raise VortexDerivativeUnavailable('Nonfinite vortex state derivative.')
    return result
