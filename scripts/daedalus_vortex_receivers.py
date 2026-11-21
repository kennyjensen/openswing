"""Independent live vortex flow at arbitrary actual-aircraft receivers.

Primary equations: .reference/asw_theory.txt 154--161. Source and receiver
geometry are caller-owned physical arrays. Only the independent quadrature
methods on free_elastic_aero.MultiSurfaceAero are reused; no production
modules, geometry construction, field cache, residual, or solve are called.

The PG coordinate map, wind, source endpoints and source cores must belong to
the current supplied geometry, including any complex perturbation. All cores
are active for external receivers by default. Explicit physical IDs select
zero core for matching physical surfaces. An optional per-receiver source
index excludes that bound segment only, retaining both trailing legs.

No ground images are represented: this helper is for the actual Daedalus
zero-ground-effect audit. The reused zero-core integral rejects receivers on
non-excluded bound segments or downstream wake filaments; it does not add a
core, singularity floor, or principal-value substitute. Small complex steps
retain real-geometry integration branches and bilinear Euclidean norms.
"""

import numpy as np


def _array(value, shape, name):
    value = np.asarray(value)
    if value.shape != shape or not np.all(np.isfinite(value)):
        raise ValueError(f"{name} must be a finite array with shape {shape}.")
    return value


def _indices(value, shape, name, lower, upper=None):
    value = np.asarray(value)
    if (np.iscomplexobj(value) or value.dtype.kind == 'b'
            or not np.all(np.isfinite(value))
            or np.any(value != np.floor(value))):
        raise ValueError(f"{name} must contain real integer indices.")
    if np.any(value < lower) or (upper is not None and np.any(value >= upper)):
        raise ValueError(f"{name} contains an out-of-range index.")
    try:
        return np.broadcast_to(value, shape).astype(int).reshape(-1)
    except ValueError as exc:
        raise ValueError(f"{name} must broadcast to the receiver shape {shape}.") from exc


def vortex_velocity(aero, geometry, gamma, points, receiver_physical=None,
                    own_bound_source=None):
    """Return (induced_velocity, diagnostics), preserving points shape (...,3).

    ``aero`` supplies n, physical and the independent _regularized_integral
    method. ``geometry`` supplies a/b[n,3], pg[3,3], wind[3], source_core[n].
    ``gamma`` contains physical circulation per source panel, not scaled
    descriptor unknowns. Receiver IDs may be scalar or broadcastable to the
    receiver shape. Positive IDs identify physical surfaces; own-bound indices
    are zero-based with -1 meaning no exclusion. Neither option is inferred
    from receiver coordinates, so CP/Hv/axis conventions remain explicit.

    The result contains only vortex velocity. The caller adds ambient, gust,
    volume, and jet flow and subtracts local/frame motion where appropriate.
    """
    points = np.asarray(points)
    if (points.ndim < 1 or points.shape[-1] != 3
            or not np.all(np.isfinite(points))):
        raise ValueError("Receiver positions must be finite with shape (...,3).")
    shape = points.shape[:-1]
    targets = points.reshape(-1, 3)
    count = len(targets)
    n = aero.n
    gamma = _array(gamma, (n,), "physical source circulation")
    first = _array(geometry['a'], (n, 3), "first source endpoint")
    second = _array(geometry['b'], (n, 3), "second source endpoint")
    pg = _array(geometry['pg'], (3, 3), "live PG map")
    wind = _array(geometry['wind'], (3,), "live wake direction")
    cores = _array(geometry['source_core'], (n,), "live source cores")
    if np.any(cores.real < 0):
        raise ValueError("Source cores must be nonnegative.")
    if not np.allclose(wind @ wind, 1., atol=2e-10, rtol=2e-10):
        raise ValueError("Live wake direction must be a unit vector.")
    source_physical = _indices(aero.physical, (n,), "source physical IDs", 1)
    receiver_ids = (None if receiver_physical is None else
                    _indices(receiver_physical, shape, "receiver physical IDs", 1))
    exclude = (np.full(count, -1, dtype=int) if own_bound_source is None else
               _indices(own_bound_source, shape, "own-bound source", -1, n))
    dtype = np.result_type(targets, gamma, first, second, pg, wind, cores)
    velocity = np.zeros((count, 3), dtype=dtype)
    diagnostic = dict(receiver_count=count, source_count=n,
        own_bound_excluded=0, direct_disjoint_finite=0,
        direct_upstream_wake=0, theta_integrals=0, regularized_integrals=0,
        minimum_direct_clearance=float('inf'), minimum_theta_radius=float('inf'),
        same_physical_surface_core=0., same_physical_receiver_source_pairs=0,
        source_core=cores.copy(),
        receiver_core_policy=('all source cores' if receiver_ids is None else
                              'zero core for equal physical IDs'),
        ground_images=False)
    wake = pg @ wind
    wake_norm = np.sqrt(wake @ wake)
    if not np.isfinite(wake_norm) or wake_norm.real <= 0:
        raise ValueError("Transformed wake direction must have positive magnitude.")
    wake = wake / wake_norm
    for j in range(n):
        segment = pg @ (second[j] - first[j])
        length = np.sqrt(segment @ segment)
        if not np.isfinite(length) or length.real <= 0:
            raise ValueError("Bound segments must have positive transformed length.")
        tangent = segment / length
        same = (np.zeros(count, dtype=bool) if receiver_ids is None else
                receiver_ids == source_physical[j])
        diagnostic['same_physical_receiver_source_pairs'] += int(np.sum(same))
        receiver_cores = np.where(same, 0., cores[j])
        for bound, origin, direction, extent, sign in (
                (True, first[j], tangent, length, 1.),
                (False, second[j], wake, None, 1.),
                (False, first[j], wake, None, -1.)):
            keep = exclude != j if bound else np.ones(count, dtype=bool)
            if bound:
                diagnostic['own_bound_excluded'] += int(np.sum(~keep))
            if not np.any(keep):
                continue
            # Subtract in physical axes first; transform the relative vector.
            relative = (targets[keep] - origin) @ pg.T
            value = aero._regularized_integral(relative, direction, extent,
                                                receiver_cores[keep], diagnostic)
            # Eq. 160 maps PG-space velocity back with P^T, not P^{-1}.
            velocity[keep] += sign * gamma[j] * (value @ pg)
    if not np.all(np.isfinite(velocity)):
        raise ValueError("Independent vortex quadrature produced nonfinite velocity.")
    for key in ('minimum_direct_clearance', 'minimum_theta_radius'):
        if not np.isfinite(diagnostic[key]):
            diagnostic[key] = None
    return velocity.reshape(points.shape), diagnostic
