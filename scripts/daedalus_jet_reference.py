"""Independent positive-thrust type-0 engine, jet, and point-drag equations.

Primary source: .reference/asw_theory.txt, equations 95--106, 108, 121--139.
No production modules are imported. All quantities use consistent ASW units.
The caller supplies loaded geometry and the complete local relative inlet
velocity, including vortex/volume flow and subtracting frame/local motion.
Engines do not ingest their own or other engines' jets. Receiver flow and
wrench transfer to attachment nodes are the caller's responsibility.

Complex arguments analytically continue the selected real branches; norms
use v.v, never conjugation. This supports small complex-step probes, not
arbitrary complex-valued physical flows. Branch diagnostics expose the
upstream, mixing-layer, core, outer-edge, and centerline decisions.
At the disk plane the finite convention is zero velocity; the positive-thrust
jet jumps immediately downstream, so a derivative crossing that plane is
unsupported. Other exact branch boundaries retain the selected finite value;
their branch-crossing derivatives are not certified by this source module.

Scope: type 0, positive thrust, enabled positive-radius jet, forward inlet.
Types 1/2, reverse flow, windmilling, disabled jets, and zero-thrust branch
changes are deliberately rejected. The actual Daedalus engine has radius
5.5, Omega 12.5, blade CdA .0125, dFdPe 1, and dMdPe 0. These literal input
values are not substituted here. Omega/CdA affect actuator-disk models, not
the type-0 proportional law, and are retained as metadata only.
"""

from functools import lru_cache

import numpy as np


def norm(value, axis=-1):
    """Euclidean norm continued without complex conjugation."""
    value = np.asarray(value)
    return np.sqrt(np.sum(value * value, axis=axis))


def _finite(value, name, shape=None):
    value = np.asarray(value)
    if shape is not None and value.shape != shape:
        raise ValueError(f"{name} must have shape {shape}.")
    if not np.all(np.isfinite(value)):
        raise ValueError(f"{name} must be finite.")
    return value


def _scalar(value, name):
    return _finite(value, name, ()).item()


def _positive(value, name, *, allow_zero=False):
    value = _scalar(value, name)
    if np.real(value) < 0 or (not allow_zero and np.real(value) == 0):
        raise ValueError(f"{name} is outside the supported positive real branch.")
    return value


def engine_axes(thrust, rotation=None):
    """Loaded body-axis engine triad; first column points downstream.

    ``thrust`` is the undeformed Tspec input, not the resulting thrust force.
    ``rotation`` is its loaded deformation rotation Q, not the full local
    beam material triad. Only the first column affects the type-0 equations.
    """
    thrust = _finite(thrust, "specified thrust direction", (3,))
    length = norm(thrust)
    _positive(length, "specified thrust direction magnitude")
    xe = -thrust / length
    # A transverse reference only completes the axisymmetric engine triad.
    reference = np.array([0., 0., 1.]) if abs(xe[2].real) < .9 else np.array([0., 1., 0.])
    ye = np.cross(reference, xe)
    ye = ye / norm(ye)
    axes = np.column_stack((xe, ye, np.cross(xe, ye)))
    if rotation is not None:
        rotation = _finite(rotation, "engine deformation rotation", (3, 3))
        if not np.allclose(rotation.T @ rotation, np.eye(3), atol=2e-10, rtol=2e-10):
            raise ValueError("Engine deformation rotation must be orthogonal.")
        if np.linalg.det(rotation).real <= 0:
            raise ValueError("Engine deformation rotation must be proper.")
        axes = rotation @ axes
    return axes


def engine_load(row, power, density, position, inlet_velocity,
                mount_rate=(0., 0., 0.), rotation=None):
    """Type-0 intrinsic force/moment and the state needed by ``jet_velocity``.

    ``row`` is the literal 15-field Engine record. ``position`` and all
    vectors are body coordinates. Returned moment is an intrinsic couple;
    add (position-reference) cross force for any requested wrench origin.
    Mount rates are accepted/reported but do not affect the type-0 law.
    """
    row = _finite(row, "Engine record", (15,))
    if np.iscomplexobj(row):
        raise ValueError("The literal Engine record must be real; perturb its physical arguments.")
    if row[1] != 0 or row[0] <= 0 or row[0] != int(row[0]):
        raise ValueError("Only a declared positive-index type-0 engine is supported.")
    radius = _positive(row[12], "enabled engine radius")
    if row[14] < 0:
        raise ValueError("Engine blade drag area must be nonnegative.")
    power = _scalar(power, "engine power parameter")
    density = _positive(density, "density")
    position = _finite(position, "loaded engine position", (3,))
    velocity = _finite(inlet_velocity, "relative engine inlet velocity", (3,))
    mount_rate = _finite(mount_rate, "engine mount rate", (3,))
    axes = engine_axes(row[7:10], rotation)
    axial = _positive(axes[:, 0] @ velocity, "engine axial inlet", allow_zero=True)
    thrust = _positive(row[10] * power, "type-0 thrust")
    torque = row[11] * power
    # Eq. 121, rationalized to preserve light-disk-loading accuracy.
    loading = 2 * thrust / (density * np.pi * radius**2)
    delta = loading / (np.sqrt(axial**2 + loading) + axial)
    return dict(index=int(row[0]), type=0, beam=int(row[2]), t=float(row[3]),
                position=position.copy(), axes=axes, force=-thrust * axes[:, 0],
                moment=-torque * axes[:, 0], thrust=thrust, torque=torque,
                axial_velocity=axial, delta_velocity=delta, radius=radius,
                jet_enabled=True, requested_power=power, power_clipped=False,
                viscous_power=None, inviscid_power=None, minimum_power=None,
                omega=float(row[13]), blade_drag_area=float(row[14]),
                inlet_velocity=velocity.copy(), mount_rate=mount_rate.copy())


@lru_cache(maxsize=None)
def _radial_rule(degree):
    # r=c+w*t^2 and q=(1-t^3)^2 make all four integrands polynomial.
    # Highest degree is 17 (r^2 dr q^2), so Gauss degree >=9 is sufficient.
    if isinstance(degree, bool) or int(degree) != degree or degree < 9:
        raise ValueError("Radial Gauss degree must be an integer at least 9.")
    nodes, weights = np.polynomial.legendre.leggauss(int(degree))
    return (nodes + 1) / 2, weights / 2


def jet_profile(engine, downstream, density, *, degree=16):
    """Momentum-conserving radial profile at arbitrary wake stations.

    Four numerical radial integrals enforce equations 134 and 137 directly.
    In particular they retain the full angular-momentum integral, rather than
    the deficient inner*width**2 coefficients printed in equation 138.
    """
    density = _positive(density, "density")
    v = _positive(engine["axial_velocity"], "engine axial inlet", allow_zero=True)
    dv = _positive(engine["delta_velocity"], "positive jet velocity increment")
    radius = _positive(engine["radius"], "enabled engine radius")
    thrust = _positive(engine["thrust"], "type-0 thrust")
    torque = _scalar(engine["torque"], "engine torque")
    downstream = _finite(downstream, "downstream coordinate")
    x = np.where(downstream.real > 0, downstream, 0.)
    contracted = radius * np.sqrt((v + dv / 2) / (v + dv))
    # Positive thrust fixes |dv|=dv without destroying its complex derivative.
    raw_inner = contracted - .11 * dv / (v + dv) * x
    inner = np.where(raw_inner.real > 0, raw_inner, 0.)
    outer = contracted + .11 * dv / (v + dv / 2) * x
    width = outer - inner
    t, weights = _radial_rule(degree)
    r = inner[..., None] + width[..., None] * t**2
    dr = 2 * width[..., None] * t
    q = (1 - t**3)**2
    k1 = inner**2 + 2 * np.sum(weights * r * dr * q, axis=-1)
    k2 = inner**2 + 2 * np.sum(weights * r * dr * q**2, axis=-1)
    k3 = 2 / 3 * inner**3 + 2 * np.sum(weights * r**2 * dr * q, axis=-1)
    k4 = 2 / 3 * inner**3 + 2 * np.sum(weights * r**2 * dr * q**2, axis=-1)
    momentum = thrust / (np.pi * density)
    center = 2 * momentum / (k1 * v + np.sqrt((k1 * v)**2 + 4 * k2 * momentum))
    transport = np.pi * density * (k3 * v + k4 * center)
    if np.any(transport.real <= 0):
        raise ValueError("Jet angular-momentum transport must be positive.")
    swirl = -torque / transport
    return dict(inner=inner, outer=outer, width=width, center=center, swirl=swirl,
                contracted=contracted, raw_inner=raw_inner,
                k1=k1, k2=k2, k3=k3, k4=k4)


def jet_velocity(points, engines, direction, density, *, degree=16, diagnostics=False):
    """Jet increments at CP, Hv, axis, body, or point receivers.

    ``direction`` is the live unit trailing-wind direction. It determines
    downstream/radial distances; each loaded engine shaft determines the
    velocity-increment direction. Input/output shape is (...,3), including a
    single point. With diagnostics=True, return (velocity, per-engine list).
    The centerline radial unit vector is zero, matching the finite convention
    for axisymmetric swirl; a nonzero-torque centerline has no unique lateral
    derivative. Actual Daedalus torque is identically zero.
    """
    points = _finite(points, "jet receiver positions")
    if points.ndim < 1 or points.shape[-1] != 3:
        raise ValueError("Jet receiver positions must have shape (...,3).")
    direction = _finite(direction, "live trailing-wind direction", (3,))
    if not np.allclose(direction @ direction, 1., atol=2e-10, rtol=2e-10):
        raise ValueError("Trailing-wind direction must be a unit vector.")
    density = _positive(density, "density")
    engines = tuple(engines)
    dtype = np.result_type(points, direction, density,
                           *(np.asarray(e[k]) for e in engines
                             for k in ("position", "axes", "thrust", "torque", "axial_velocity")))
    velocity = np.zeros(points.shape, dtype=dtype)
    reports = []
    for engine in engines:
        if engine.get("type") != 0 or not engine.get("jet_enabled", False):
            raise ValueError("Only enabled positive-thrust type-0 jets are supported.")
        relative = points - engine["position"]
        downstream = relative @ direction
        radial = relative - downstream[..., None] * direction
        distance = norm(radial)
        profile = jet_profile(engine, downstream, density, degree=degree)
        inner, outer, width = (profile[k] for k in ("inner", "outer", "width"))
        active = (downstream.real > 0) & (distance.real < outer.real)
        mixing = active & (distance.real > inner.real) & (width.real > 0)
        fraction = np.zeros(distance.shape, dtype=dtype)
        np.divide(distance - inner, width, out=fraction, where=mixing)
        shape = np.where(active, (1 - fraction**1.5)**2, 0.)
        radial_unit = np.zeros(radial.shape, dtype=dtype)
        np.divide(radial, distance[..., None], out=radial_unit,
                  where=distance.real[..., None] > 0)
        shaft = engine["axes"][:, 0]
        increment = shape[..., None] * (profile["center"][..., None] * shaft
                    + profile["swirl"][..., None] * np.cross(radial_unit, shaft))
        velocity += increment
        if diagnostics:
            reports.append(dict(index=engine["index"], downstream=downstream,
                radial=radial, distance=distance, shape=shape, velocity=increment,
                branch_names=("downstream", "unmerged_core", "inside_inner", "inside_outer", "off_centerline"),
                branches=np.stack((downstream.real > 0, profile["raw_inner"].real > 0,
                    distance.real < inner.real, distance.real < outer.real,
                    distance.real > 0), axis=-1),
                boundary_distances=np.stack((abs(downstream.real), abs(profile["raw_inner"].real),
                    abs(distance.real - inner.real), abs(distance.real - outer.real),
                    abs(distance.real)), axis=-1), **profile))
    return (velocity, reports) if diagnostics else velocity


def point_drag(relative_velocity, density, drag_area):
    """Aerodynamic part of equation 95: rho/2 * CDA * |V| V.

    Relative velocity must already contain the jet and all other incident
    flow. Return force only; gravity, inertia, and wrench arms are external.
    Supports a single vector or (...,3) arrays and broadcastable drag areas.
    """
    velocity = _finite(relative_velocity, "point relative velocity")
    if velocity.ndim < 1 or velocity.shape[-1] != 3:
        raise ValueError("Point relative velocity must have shape (...,3).")
    density = _positive(density, "density")
    area = _finite(drag_area, "point drag area")
    if np.any(area.real < 0):
        raise ValueError("Point drag area must be nonnegative.")
    return (.5 * density * area * norm(velocity))[..., None] * velocity


def engine_report(engine):
    """Return plain containers while retaining complex probe scalars."""
    return {key: value.tolist() if isinstance(value, np.ndarray) else value
            for key, value in engine.items()}
