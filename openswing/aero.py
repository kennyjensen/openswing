"""Extended lifting-line residual and instantaneous loads on supplied geometry.

Independent implementation of Drela, Steady Formulation (2015), equations
62–74, 146–161, 200–204. Pointwise/Fourier circulation; wind-aligned wakes
and control points; exact semi-infinite regularized Biot–Savart integrals.
The network solver couples this residual to elastic equilibrium and selected
operating constraints. Optional local motion and circulation-rate fields add the
unsteady terms used by the shared time and linear-dynamic equations.
"""
from dataclasses import dataclass, field, replace
from numbers import Real
import numpy as np
from .vector_ops import cross3, dot3
from scipy.optimize import root
from scipy.special import expit
from .asw import Model
from .point_objects import active_weights, check_point_data
from .geometry import mesh_beam, model_meshes, normalize, surface_frame
from .inertia import Motion, InertiaModel, inertial_wrench, surface_apparent_loads, apparent_properties
from .propulsion import validate_engines, engine_load, jet_velocity, engine_report
from .volume import VolumeField, body_quadrature, body_loads
from .ground import GroundPlane
from .atmosphere import operating_air
from .kinematics import flight_kinematics
from .reference_flow import reference_airflow
from .gust import gust_field, LIMITATIONS as GUST_LIMITATIONS
from .trefftz import trefftz_for_meshes
from .circulation import CirculationBasis
from .frozen_influence import FrozenInfluences, lifting_geometry
from .body_shoulders import body_shoulders
from .factored_influence import FactoredInfluence


class AnalysisError(ValueError):
    def __init__(self, message, *, details=None):
        super().__init__(message)
        self.details = details


def finite_vortex(points, a, b, core=0.):
    """Unit circulation on a→b; arrays broadcast, last axis is xyz."""
    d = np.asarray(b) - a
    length = np.linalg.norm(d, axis=-1)
    if np.any(length <= 0):
        raise AnalysisError("Zero-length vortex segment.")
    u = d / length[..., None]
    r = np.asarray(points) - a
    z = dot3(r, u)
    h = r - z[..., None] * u
    den = dot3(h, h) + np.asarray(core) ** 2
    safe = np.where(den > 0., den, 1.)
    first=np.sqrt(z*z+safe);second=np.sqrt((z-length)**2+safe)
    fac=(z/first-(z-length)/second)/safe
    # Outside the segment both endpoint cosines have the same sign and can
    # round to the same number. Rationalize their difference before dividing
    # by the squared radial distance; this is the identical Biot--Savart law.
    outside=(z<0)|(z>length)
    stable=np.divide(length*(2*z-length),
        (z*second+(z-length)*first)*first*second,
        out=np.zeros_like(safe),where=outside)
    fac=np.where(outside,stable,fac)
    # The existing near-filament self convention applies only over the segment.
    # Its exterior axis is nonsingular: retain the rationalized integral even
    # at tiny transverse distances, without an absolute length cutoff/floor.
    return cross3(u, h) * (np.where((den > 1e-26) | outside, fac, 0.) / (4 * np.pi))[..., None]


def semi_infinite_vortex(points, origin, direction, core=0.):
    u = normalize(direction)
    r = np.asarray(points) - origin
    z = dot3(r, u)
    h = r-z[..., None]*u
    den = dot3(h, h) + np.asarray(core) ** 2
    safe = np.where(den > 0., den, 1.)
    distance=np.sqrt(z*z+safe)
    fac=(1+z/distance)/safe
    # Upstream, 1+z/R loses the entire small wake influence near the axis.
    # (R+z)/safe = 1/(R-z), without changing the core or self-influence rule.
    stable=np.divide(1.,distance*(distance-z),out=np.zeros_like(safe),where=z<0)
    fac=np.where(z<0,stable,fac)
    # Upstream of the origin the ray has no singularity on its extended axis.
    return cross3(u, r) * (np.where((den > 1e-26) | (z < 0.), fac, 0.) / (4 * np.pi))[..., None]


def horseshoe(points, a, b, direction, core=0., *, exclude_bound=None):
    bound = finite_vortex(points, a, b, core)
    if exclude_bound is not None:
        bound = np.where(np.asarray(exclude_bound)[..., None], 0., bound)
    return (bound
            + semi_infinite_vortex(points, b, direction, core)
            - semi_infinite_vortex(points, a, direction, core))


def _relative_pg(points, a, b, pg):
    """Pair differences before PG avoids rounding separate absolute maps."""
    return (points-a)@pg.T, (points-b)@pg.T, (b-a)@pg.T


def _relative_horseshoe(first, second, segment, direction, core=0., *, exclude_bound=None):
    bound = finite_vortex(first, 0., segment, core)
    if exclude_bound is not None:
        bound = np.where(np.asarray(exclude_bound)[..., None], 0., bound)
    return (bound + semi_infinite_vortex(second, 0., direction, core)
            - semi_infinite_vortex(first, 0., direction, core))


def horseshoe_velocity(points, a, b, direction, pg, core=0., ground=None, *, exclude_bound=None):
    """Physical velocity, with paired ground images and PG transformation.

    exclude_bound removes only selected physical bound segments, before adding
    their wakes. Ground-image bound segments remain present.
    """
    points,a,b,direction = map(np.asarray,(points,a,b,direction))
    result=_relative_horseshoe(*_relative_pg(points,a,b,pg),direction@pg.T,core,exclude_bound=exclude_bound)
    if ground is not None and ground.flag:
        result-=ground.flag*_relative_horseshoe(*_relative_pg(points,ground.reflect_points(a),ground.reflect_points(b),pg),
                                               ground.reflect_vectors(direction)@pg.T,core)
    return result@pg


@dataclass
class FlightCondition:
    speed: float = 30.
    alpha: float = 5.  # degrees
    beta: float = 0.
    density: float | None = None
    mach: float | None = None
    rates: tuple[float, float, float] = (0., 0., 0.)  # rad/input T, body axes
    acceleration: tuple[float, float, float] = (0., 0., 0.)  # input L/T² at acceleration reference
    angular_acceleration: tuple[float, float, float] = (0., 0., 0.)  # rad/input T², body axes
    controls: dict[int, float] = field(default_factory=dict)
    powers: dict[int, float] = field(default_factory=dict)
    body_added_mass_factor: float = 1.  # cylinder potential flow; 2 reproduces printed ASW body coefficient
    position_earth: tuple[float,float,float] = (0.,0.,0.)  # body origin, input L
    attitude: tuple[float,float,float] = (0.,0.,0.)  # bank, elevation, heading, degrees
    ground_effect: int = 0  # 0 off, +1 solid, -1 constant-pressure free surface
    ground_normal: tuple[float,float,float] = (0.,0.,1.)  # Earth axes, normalized internally
    stall: bool = True
    stall_factor: float = 40.
    stall_width: float = .05
    altitude_m: float = 0.  # prescribed atmospheric geometric altitude, SI metres; independent of Earth Z
    gravity_magnitude: float | None = None  # input L/T²; never changes weight-to-mass conversion
    load_factor: float = 1.  # multiplies the specified lift target only (steady eq. 185)
    gust: dict | None = None  # prescribed Earth-coordinate velocity field
    sensor_flow: str = 'full'  # full local airflow or kinematic still-atmosphere measurement
    time: float = 0.  # field evaluation time, input T; time solver starts at zero
    circulation_modes: dict[int, int] = field(default_factory=dict)  # per logical beam; zero/omitted is pointwise
    aero_lag: bool = True  # ASWING K/L: shed-vorticity downwash and circulation-rate lift
    wake_core_ratio: float = .25  # ASWING K/W; interval width is a lower bound
    freeze_influences: bool = True  # ASWING K/F fast default: jig geometry and zero wind angles

    def motion(self):
        return Motion(self.rates, self.acceleration, self.angular_acceleration)

    def earth_state(self, model=None):
        return flight_kinematics(self, model)

    def vectors(self):
        a, b = np.deg2rad([self.alpha, self.beta])
        wind = np.array([np.cos(a) * np.cos(b), -np.sin(b), np.sin(a) * np.cos(b)])
        side = np.array([np.cos(a) * np.sin(b), np.cos(b), np.sin(a) * np.sin(b)])
        lift = np.array([-np.sin(a), 0., np.cos(a)])
        return wind, side, lift


def _wake_core_ratio(condition):
    value = condition.wake_core_ratio
    message = 'Wake core radius/chord must be a finite nonnegative number.'
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Real):
        raise AnalysisError(message)
    try:
        value = float(value)
    except (OverflowError, ValueError):
        raise AnalysisError(message) from None
    if not np.isfinite(value) or value < 0:
        raise AnalysisError(message)
    return value


def _stall_leakage(cl, lower, upper, width):
    """Equation 204 and its derivative, without subtracting nearly equal logs."""
    cl, lower, upper = np.broadcast_arrays(np.asarray(cl, dtype=float), lower, upper)
    x, y = cl-upper, lower-cl
    first, second = np.maximum(x, y), np.minimum(x, y)
    # For ordered section limits, second <= 0. With nearby arguments use
    # log((1+exp(a))/(1+exp(b))) = log1p(expit(b)*expm1(a-b)).
    # Far apart, separate the positive linear part before dividing by width.
    # The split at 32 selects an evaluation formula, not a different stall law.
    with np.errstate(over='ignore', under='ignore'):
        a, b = first/width, second/width
        distance = (first-second)/width
        close = distance <= 32
        value = np.empty_like(cl)
        value[close] = width*np.log1p(expit(b[close])*np.expm1(distance[close]))
        value[~close] = np.maximum(first[~close], 0) + width*(
            np.log1p(np.exp(-np.abs(a[~close]))) - np.log1p(np.exp(b[~close])))
        derivative = expit(a)+expit(b)
    return np.where(x >= y, value, -value), derivative


def _reference_area(model, *, required=False):
    """Sref normalizes reported coefficients; it is not a physical load area."""
    area = model.reference[0, 0]
    if not np.isfinite(area) or area < 0:
        raise AnalysisError('Reference area must be finite and nonnegative.')
    if required and area == 0:
        raise AnalysisError('Coefficient derivatives require a positive Reference area for coefficient normalization. Dimensional loads and modes remain available with zero area.')


def _validate(model, condition):
    _reference_area(model)
    from .sensors import validate_sensors
    validate_sensors(model)
    _wake_core_ratio(condition)
    if not isinstance(condition.freeze_influences, (bool, np.bool_)):
        raise AnalysisError('Freeze aerodynamic influences must be a boolean.')
    if not isinstance(condition.aero_lag, (bool, np.bool_)):
        raise AnalysisError('Aerodynamic lag must be a boolean.')
    if condition.sensor_flow not in ('full', 'kinematic'):
        raise AnalysisError('Sensor flow must be full or kinematic.')
    condition.motion()  # Validate all three-vector motion quantities, including sizes.
    GroundPlane.from_condition(condition)
    gust_field(condition.gust).velocity(np.asarray(condition.position_earth), condition.time)
    values = [condition.speed, condition.alpha, condition.beta, *condition.rates, *condition.controls.values()]
    if not np.all(np.isfinite(values)) or condition.speed <= 0:
        raise AnalysisError("Flight condition must be finite and speed must be positive.")
    for name, positive in [('stall_factor', False), ('stall_width', True)]:
        value = getattr(condition, name)
        message = ('Stall transition width must be a finite positive number.' if positive else
                   'Stall leakage factor must be a finite nonnegative number.')
        if isinstance(value, (bool, np.bool_)) or not isinstance(value, Real):
            raise AnalysisError(message)
        try:
            value = float(value)
        except (OverflowError, ValueError):
            raise AnalysisError(message) from None
        if not np.isfinite(value) or (value <= 0 if positive else value < 0):
            raise AnalysisError(message)
    if model.diagnostics:
        raise AnalysisError("Resolve unrecognized input before solving: " + "; ".join(model.diagnostics))
    validate_engines(model, condition.powers)
    if condition.body_added_mass_factor not in (1., 2.):
        raise AnalysisError("Body apparent-mass factor must be 1 (cylinder potential flow) or 2 (printed ASWING formula).")
    operating_air(model, condition)
    for row in model.records.get("weight", []):
        if row[6] < 0 or row[7] < 0:
            raise AnalysisError("Point-object drag area and aerodynamic volume must be nonnegative.")


def evaluate_aerodynamics(model: Model, condition: FlightCondition, meshes,
                          circulation=None, point_positions=None, engine_positions=None, engine_rotations=None,
                          *, local_motion=None, circulation_rate=None, sensor_positions=None, circulation_basis=None,
                          survey_positions=None, circulation_method='auto', initial_circulation=None,
                          frozen_influences=None, fourier_wake_diagnostic=False,
                          _loads_only=False, _tangent_influences=None, _iteration_fields=None,
                          _circulation_progress=None):
    """Evaluate the aerodynamic residual and loads on supplied geometry.

    If circulation is supplied, no inner aerodynamic solve is performed. This
    permits a simultaneous structural/circulation Newton solve. K/F optionally
    freezes velocity coefficients at jig geometry and zero wind angles; current
    normals, kinematics, circulation and physical load transfer are retained.
    Optional NetworkMotion and circulation-rate fields evaluate the documented
    unsteady loads and lag residual at an instant; they do not integrate time.
    Point positions and returned point forces use active_weights(model) order;
    completely null Weight records are retained only in the parsed input.
    initial_circulation is an optional physical per-panel Newton seed, not a
    prescribed solution. Auto tries it before the unchanged cold algorithm;
    direct retains the seeded attempt. It cannot accompany prescribed
    circulation or an explicit continuation request. No historical startup
    or branch identity is implied by supplying a seed.
    fourier_wake_diagnostic adds an independent continuous-wake reference for
    straight Fourier traces in free space. It does not replace CDi,
    efficiency, loads, residuals or derivatives; unsupported traces are explicit.
    """
    _reference_area(model)
    if not isinstance(fourier_wake_diagnostic, (bool, np.bool_)):
        raise AnalysisError('Fourier wake diagnostic must be true or false.')
    if circulation_method not in ('auto', 'direct', 'continuation'):
        raise AnalysisError('Circulation method must be auto, direct or continuation.')
    if initial_circulation is not None and circulation is not None:
        raise AnalysisError('Initial circulation cannot accompany prescribed circulation.')
    if initial_circulation is not None and circulation_method == 'continuation':
        raise AnalysisError('Initial circulation cannot accompany explicit continuation.')
    if not isinstance(condition.aero_lag, (bool, np.bool_)):
        raise AnalysisError('Aerodynamic lag must be a boolean.')
    if not isinstance(condition.freeze_influences, (bool, np.bool_)):
        raise AnalysisError('Freeze aerodynamic influences must be a boolean.')
    core_ratio = _wake_core_ratio(condition)
    air = operating_air(model, condition)
    rho = air["density"]
    motion_state = condition.motion()
    mach = air["ambient_mach"] if condition.mach is None else float(condition.mach)
    if not np.isfinite(rho) or rho <= 0 or not np.isfinite(mach) or not 0 <= mach < 1:
        raise AnalysisError("Density must be positive and Prandtl–Glauert Mach must be in [0, 1).")
    e, ey, ez = condition.vectors()
    wind = np.array([1., 0., 0.]) if condition.freeze_influences else e
    # User guide, Engine jet: its centerline follows the vortex wake, hence
    # the aircraft x-axis in K/F fast mode. Engine inflow still uses e.
    jet_direction = wind
    # Symmetric stretch Q = R^T D R, where the theory uses P = D R.
    # Rotational covariance of Biot–Savart removes the explicit rotation R.
    # Velocities transform with P^T (equivalently Q here), not P^-1.
    pg = np.eye(3) + (1 / np.sqrt(1 - mach ** 2) - 1) * np.outer(wind, wind)
    if not meshes:
        raise AnalysisError("No beam geometry in this configuration.")
    ground = GroundPlane.from_condition(condition)
    frozen = None
    if condition.freeze_influences:
        frozen = (FrozenInfluences(model, meshes) if frozen_influences is None else frozen_influences)
        frozen.configure(model, meshes, mach, core_ratio, ground)
    basis = circulation_basis if circulation_basis is not None else CirculationBasis(meshes, condition.circulation_modes)
    if circulation_basis is not None:basis.validate_settings(condition.circulation_modes)
    initial_coefficients = None
    if initial_circulation is not None:
        try:
            if np.iscomplexobj(initial_circulation):
                raise ValueError('Complex circulation is not a physical seed.')
            initial_circulation = np.array(initial_circulation, dtype=float, copy=True)
            initial_coefficients = basis.encode(initial_circulation)
        except (TypeError, ValueError, OverflowError) as exc:
            raise AnalysisError(f'Invalid initial circulation: {exc}') from exc
    gust = gust_field(condition.gust)
    gust_locations = []

    def gust_velocity(points):
        points = np.asarray(points)
        if gust.kind == 'none':
            return np.zeros_like(points, dtype=float)
        gust_locations.append(points.reshape(-1, 3))
        return gust.body_velocity(points, condition)
    engine_rows = model.records.get("engine", [])
    weight_rows = active_weights(model)
    check_point_data(weight_rows, point_positions, 'Point positions')
    capture_circulation = (_iteration_fields is not None and _iteration_fields.phase == 'capture'
                           and _iteration_fields.capture_circulation)
    derivative_bodies, derivative_points = [], []
    engine_points = np.array([row[4:7] for row in engine_rows] if engine_positions is None else engine_positions).reshape(-1,3)
    point_locations = [row[2:5] for row in weight_rows] if point_positions is None else point_positions
    clearance = ground.clearance(meshes,point_locations,engine_points,engine_rows,engine_rotations,model=model) if ground.flag else None
    if ground.flag:
        from .wall_root import validate_wall_flow
        validate_wall_flow(ground, condition, model, gust,
                           local_motion=local_motion, circulation_rate=circulation_rate)
    def fixed_geometry(key, compute):
        return compute() if _iteration_fields is None else _iteration_fields.fixed_geometry(key,compute)
    volume = None if frozen else fixed_geometry('volume_field',lambda:VolumeField(model, meshes, e, pg, point_positions, ground))
    def volume_velocity(points, reference=None, *, cache_name=None, **exclusions):
        compute = lambda: (frozen.volume(points if reference is None else reference, **exclusions) if frozen else
                volume.velocity(points, _tangent=_tangent_influences, _cache_name=cache_name, **exclusions))
        if _iteration_fields is None or (frozen and reference is not None
                and getattr(_iteration_fields, 'reuse_frozen_influences', False)):
            return compute()
        return _iteration_fields.get(("volume",cache_name),compute)
    arrays = {k: [] for k in ("normal", "section_normal", "jig_normal", "s", "c", "slope", "clmax", "clmin", "cdf", "cdp", "cm", "xax", "beam", "t", "profile_arm")}
    for mesh in meshes:
        beam = mesh.beam
        if not beam.lifting:
            continue
        section_value = beam.value if _tangent_influences is None else lambda name, t: _tangent_influences.value(beam, name, t)
        t = mesh.tm
        chord = section_value("chord", t)
        slope = section_value("dCLda", t)
        clmin, clmax = section_value("CLmin", t), section_value("CLmax", t)
        if np.any(chord <= 0) or np.any(slope <= 0) or np.any(clmin >= clmax):
            raise AnalysisError(f"Beam {beam.index}: chord and lift slope must be positive, and CLmin < CLmax.")
        c, s, n = mesh.frames[..., 0], mesh.frames[..., 1], mesh.frames[..., 2]
        xax = section_value("Xax", t)
        alpha = np.deg2rad(section_value("alpha", t))
        cm, cdp = section_value("Cm", t).copy(), section_value("Cdp", t).copy()
        for k, value in condition.controls.items():
            alpha += value * section_value(f"dCLdF{k}", t) / slope
            cm += value * section_value(f"dCMdF{k}", t)
            cdp += value * section_value(f"dCDdF{k}", t)
        cdf = section_value("Cdf", t)
        if np.any(cdf < 0) or np.any(cdp < 0):
            raise AnalysisError("Control settings or interpolation produced a negative profile drag coefficient.")
        values = dict(normal=np.sin(alpha)[:, None] * c + np.cos(alpha)[:, None] * n,
                      section_normal=n, jig_normal=(surface_frame(beam, t) if _tangent_influences is None else _tangent_influences.frame(beam, t))[..., 2],
                      s=s, c=c, slope=slope, clmax=clmax, clmin=clmin,
                      cdf=cdf, cdp=cdp, cm=cm, xax=xax, beam=np.full(len(t), beam.index), t=t,
                      profile_arm=.5*(mesh.r0-mesh.rm)+.5*(mesh.r1-mesh.rm))
        for key, val in values.items():
            arrays[key].extend(val)
    vector_keys = {"a", "b", "hv", "cp", "normal", "section_normal", "jig_normal", "s", "c", "rm", "profile_arm"}
    p = {k: np.asarray(v).reshape(-1,3) if k in vector_keys else np.asarray(v) for k, v in arrays.items()}
    p.update(fixed_geometry('lifting_geometry',lambda:lifting_geometry(meshes, wind, _material=_tangent_influences)))
    ig = frozen.geometry if frozen else p
    gamma_dot = np.zeros(len(p['t'])) if circulation_rate is None else np.asarray(circulation_rate,dtype=float)
    if gamma_dot.shape != (len(p['t']),) or not np.all(np.isfinite(gamma_dot)):
        raise AnalysisError('Circulation rates must be a finite vector with one entry per lifting panel.')
    if basis.modes:basis.encode(gamma_dot)
    # K/L disables both shed-vorticity downwash and rate lift. Keep the actual
    # circulation derivative in outputs; an algebraic circulation can still
    # change with motion or forcing. Apparent-mass terms are independent.
    lag_rate = gamma_dot if condition.aero_lag else np.zeros_like(gamma_dot)
    surface_motion = None if local_motion is None else local_motion.surface()
    with np.errstate(over='ignore'):
        source_core = np.maximum(core_ratio * ig["chord"], ig["ds"])
    if np.any(~np.isfinite(source_core)) or np.any(source_core > np.sqrt(np.finfo(float).max)):
        raise AnalysisError('Wake core radius is too large for the vortex calculation in these input units.')

    def original_influences(points, physical=None, *, reference=None, exclude_bound=None, cache_name=None):
        if frozen:
            return frozen.factored_vortex(points if reference is None else reference, physical, exclude_bound=exclude_bound)
        target_cores = source_core[None,:] if physical is None else np.where(
            np.asarray(physical)[:,None] == p["physical"][None,:],0.,source_core[None,:])
        if _tangent_influences is not None and cache_name is not None:
            return _tangent_influences.factored_vortex(cache_name, points, p['a'], p['b'], e, pg, target_cores, ground, exclude_bound)
        return FactoredInfluence(points, p['a'], p['b'], e, pg, target_cores,
                                 ground, exclude_bound=exclude_bound)

    def influences(points, physical=None, *, reference=None, exclude_bound=None, cache_name=None):
        compute = lambda: original_influences(points,physical,reference=reference,exclude_bound=exclude_bound,cache_name=cache_name)
        if _iteration_fields is None:
            return compute()
        if frozen and reference is not None and getattr(_iteration_fields, 'reuse_frozen_influences', False):
            return _iteration_fields.frozen_vortex(cache_name, len(points), compute)
        return _iteration_fields.get(('vortex',cache_name),compute)

    def induced_velocity(points, physical=None, *, reference=None, exclude_bound=None, cache_name=None):
        def compute():
            return influences(points, physical, reference=reference, exclude_bound=exclude_bound,
                              cache_name=cache_name).apply(gamma)
        if frozen and reference is not None and getattr(_iteration_fields, 'reuse_frozen_influences', False):
            # Geometry perturbations hold Gamma fixed, so these attached
            # receivers can reuse the velocity instead of the full map.
            if _iteration_fields.phase != 'circulation':
                return _iteration_fields.get(('fixed-vortex-velocity',cache_name),compute)
        return compute()

    from .propulsion import jet_velocity as original_jet_velocity
    def jet_velocity(points, engines, direction, density, *, cache_name=None):
        if hasattr(_iteration_fields,'observe_jet'):
            _iteration_fields.observe_jet(cache_name,points,engines,direction,density)
        compute = lambda: original_jet_velocity(points,engines,direction,density)
        return compute() if _iteration_fields is None else _iteration_fields.get(('jet',cache_name),compute)

    # The bound-segment midpoint may differ from the theta midpoint under curved
    # geometry. Omit the panel's own physical bound segment BEFORE summation:
    # subtracting two near-singular evaluations loses the finite wake velocity,
    # especially when PG transforms round differently in broadcast operations.
    vcp = influences(p["cp"], p["physical"], reference=ig['cp'], cache_name='cp')
    vhv = influences(p["hv"], p["physical"], reference=ig['hv'], cache_name='hv', exclude_bound=np.eye(len(p["t"]), dtype=bool))
    omega = np.asarray(condition.rates)
    # Speed/angles apply at the explicitly specified velocity-reference point.
    cp_free = condition.speed * e - cross3(omega, p["cp"] - model.reference[3])
    hv_free = condition.speed * e - cross3(omega, p["hv"] - model.reference[3])
    cp_free += gust_velocity(p['cp'])
    hv_free += gust_velocity(p['hv'])
    if surface_motion is not None:
        cp_free -= surface_motion.velocity_at(p['cp'])
        hv_free -= surface_motion.velocity_at(p['hv'])
    cp_free += condition.speed*volume_velocity(p["cp"], ig['cp'], cache_name='cp')
    hv_free += condition.speed*volume_velocity(p["hv"], ig['hv'], cache_name='hv')
    incident = getattr(_iteration_fields, 'incident_velocity', None)
    if incident is not None:
        cp_free = incident('cp', cp_free)
        hv_free = incident('hv', hv_free)
    engine_free = condition.speed*e-cross3(omega, engine_points-model.reference[3])
    engine_free += gust_velocity(engine_points)
    engine_reference = np.array([row[4:7] for row in engine_rows]).reshape(-1, 3)
    engine_free += condition.speed*volume_velocity(engine_points, engine_reference, cache_name='engine')
    engine_rates = np.broadcast_to(omega,engine_points.shape).copy()
    if local_motion is not None:
        for i,position in enumerate(engine_points):
            mount = local_motion.point('engine',i)
            engine_free[i] -= mount.velocity_at(position)
            engine_rates[i] += mount.rates
    engine_aic = influences(engine_points, reference=engine_reference, cache_name='engine')
    flow_key, flow_cache = None, None
    # A plume is identically zero on and upstream of its disk. Only jets
    # with a downstream circulation receiver can affect this Jacobian.
    receivers = np.concatenate((p["cp"], p["hv"])) if circulation is None else None
    jet_feedback = receivers is not None and any(
        row[12] > 0 and np.any((receivers-position)@jet_direction > 0.)
        for row, position in zip(engine_rows, engine_points))
    evaluate_trial_jets = circulation is not None or jet_feedback

    def engine_flow(gamma):
        nonlocal flow_key, flow_cache
        key = gamma.tobytes()
        if key != flow_key:
            inflows = engine_free+engine_aic.apply(gamma)
            engines = [engine_load(row, condition.powers.get(int(row[0]), 0.), rho, position, velocity,
                                   engine_rates[i], None if engine_rotations is None else engine_rotations[i])
                       for i, (row, position, velocity) in enumerate(zip(engine_rows, engine_points, inflows))]
            flow_cache = engines, jet_velocity(p["cp"], engines, jet_direction, rho, cache_name="cp"), jet_velocity(p["hv"], engines, jet_direction, rho, cache_name="hv")
            flow_key = key
        return flow_cache
    # An own solve repeatedly needs only the normal CP velocity. Keep that
    # scalar operator factored too, including prescribed-Gamma replay, so both
    # evaluate exactly the same residual. Only own solves need a dense matrix.
    normal_influence = vcp.projected(p["normal"])
    aic = normal_influence.matrix() if circulation is None else None
    rhs = -np.sum(cp_free * p["normal"], axis=-1)
    velocity_key, velocity_cache = None, None
    normal_key, normal_cache = None, None

    def normal_velocity(gamma):
        nonlocal normal_key, normal_cache
        key = gamma.tobytes()
        if key != normal_key:
            normal_cache = normal_influence.apply(gamma)
            normal_key = key
        return normal_cache

    def velocities(gamma):
        nonlocal velocity_key, velocity_cache
        key = gamma.tobytes()
        if key == velocity_key:
            return velocity_cache
        v = hv_free + vhv.apply(gamma)
        if evaluate_trial_jets:
            v += engine_flow(gamma)[2]
        vperp = v - np.sum(v * p["s"], axis=-1)[:, None] * p["s"]
        speed = np.linalg.norm(vperp, axis=-1)
        velocity_key = key
        velocity_cache = v, vperp, np.maximum(speed, condition.speed * 1e-12)
        return velocity_cache

    def local_residual(gamma):
        _, _, speed = velocities(gamma)
        cl = 2 * gamma / (p["chord"] * speed)
        fstall, _ = _stall_leakage(cl, p['clmin'], p['clmax'], condition.stall_width)
        leakage = speed / p["slope"] * condition.stall_factor * fstall if condition.stall else 0.
        jet_normal = np.sum(engine_flow(gamma)[1]*p["normal"], axis=-1) if evaluate_trial_jets else 0.
        return (normal_velocity(gamma) - rhs + jet_normal - leakage - 2/np.pi*lag_rate/speed) / condition.speed

    evaluations = 0
    tracing = False
    def residual(gamma):
        nonlocal evaluations
        if _circulation_progress is not None and circulation is None:
            evaluations += 1
            if not tracing and (evaluations == 1 or evaluations % 16 == 0):
                _circulation_progress('static_circulation_residual', evaluations, 0)
        value = local_residual(gamma)
        if getattr(_iteration_fields, 'capture_local_flow', False):
            _iteration_fields.local_flow_residual = value
        return basis.test@value if basis.modes else value

    def circulation_jacobian(gamma):
        # Exact fixed-geometry derivative when no circulation-dependent engine
        # jet is present. Local speed, stall leakage and prescribed lag-rate
        # terms all vary with circulation. Engine feedback uses centered
        # derivatives of the complete residual in the continuation helper.
        _, vp, speed = velocities(gamma)
        speed_jacobian = vhv.project(vp/speed[:, None])
        speed_jacobian[np.linalg.norm(vp, axis=1) <= condition.speed*1e-12] = 0.
        cl = 2*gamma/(p['chord']*speed)
        f, df = _stall_leakage(cl, p['clmin'], p['clmax'], condition.stall_width)
        strength = condition.stall_factor/p['slope'] if condition.stall else np.zeros_like(cl)
        leakage_jacobian = np.diag(strength*2/p['chord']*df)
        leakage_jacobian += (strength*(f-cl*df))[:, None]*speed_jacobian
        physical = (aic-leakage_jacobian+(2/np.pi*lag_rate/speed**2)[:, None]*speed_jacobian)/condition.speed
        return basis.test@physical@basis.sample if basis.modes else physical

    initialization = None
    seeded = False
    seed_evaluations = 0
    if initial_coefficients is not None:
        # MINPACK initializes its trust radius from ||diag*x0||. Solving for
        # absolute coefficients therefore stalls on small nonzero seeds (even
        # ordinary roundoff), while an exact zero seed gets a finite radius.
        # Use coefficients = seed + scale*increment, with increment initially
        # zero. This preserves the physical seed and uses the same dimensional
        # circulation scale as the continuation/polish paths, without clipping.
        coefficient_scale = float(np.max(.5*p['chord']*condition.speed)) if basis.size else 1.
        def seeded_gamma(increment):
            return basis.decode(initial_coefficients+coefficient_scale*increment)
        attempt = dict(method='direct', derivative='numerical engine feedback' if jet_feedback else 'analytic',
            evaluations=0, accepted=False)
        initialization = dict(kind='provided circulation', initial_circulation=initial_circulation.tolist(),
            initial_coefficients=initial_coefficients.tolist(), seed_attempt=attempt, cold_fallback=False,
            coordinates='dimensionless increment from supplied coefficients', coefficient_scale=coefficient_scale,
            scope='Initialization of the unchanged equations; historical startup, uniqueness and branch identity are not established.')
        def seeded_residual(x):
            attempt['evaluations'] += 1
            return residual(seeded_gamma(x))
        try:
            if basis.size:
                solution = root(seeded_residual, np.zeros(basis.size),
                    jac=None if jet_feedback else lambda x: circulation_jacobian(seeded_gamma(x))*coefficient_scale,
                    method='hybr', options={'xtol': 1e-10})
                gamma = seeded_gamma(solution.x)
                attempt.update(reported_success=bool(solution.success), message=str(solution.message),
                    solver_evaluations=int(solution.nfev), jacobian_evaluations=int(getattr(solution, 'njev', 0)))
            else:
                gamma = basis.decode(initial_coefficients)
                attempt.update(reported_success=True, message='No lifting circulation unknowns.',
                    solver_evaluations=0, jacobian_evaluations=0)
            seed_error = float('inf')
            if np.all(np.isfinite(gamma)):
                attempt['evaluations'] += 1
                seed_error = float(np.max(np.abs(residual(gamma)), initial=0.))
            if basis.size and 0 < seed_error <= 1e-8:
                # Recover relative accuracy when seed + increment cancels.
                # The incremental solve has already reached a physical root;
                # refine in absolute dimensionless coefficients, retaining the
                # root unless the new residual improves inside the same local
                # neighborhood used by terminal circulation polishing.
                coefficients = initial_coefficients+coefficient_scale*solution.x
                local_radius = 1e-8*max(coefficient_scale, float(np.max(abs(gamma))))
                refinement = dict(coordinates='absolute dimensionless coefficients', evaluations=0,
                    accepted=False, initial_physical_residual=seed_error,
                    maximum_gamma_change=local_radius)
                attempt['refinement'] = refinement
                def absolute_residual(z):
                    attempt['evaluations'] += 1
                    refinement['evaluations'] += 1
                    return residual(basis.decode(coefficient_scale*z))
                try:
                    refined = root(absolute_residual, coefficients/coefficient_scale,
                        jac=None if jet_feedback else lambda z:
                        circulation_jacobian(basis.decode(coefficient_scale*z))*coefficient_scale,
                        method='hybr', options={'xtol': 1e-10})
                    candidate_coefficients = coefficient_scale*refined.x
                    refinement.update(reported_success=bool(refined.success), message=str(refined.message),
                        solver_evaluations=int(refined.nfev), jacobian_evaluations=int(getattr(refined, 'njev', 0)))
                    if np.all(np.isfinite(candidate_coefficients)):
                        candidate = basis.decode(candidate_coefficients)
                        change = float(np.max(abs(candidate-gamma)))
                        refinement['gamma_change'] = change
                        if change <= local_radius:
                            candidate_error = float(np.max(abs(absolute_residual(refined.x)), initial=0.))
                            refinement['physical_residual'] = candidate_error if np.isfinite(candidate_error) else None
                            if np.isfinite(candidate_error) and candidate_error < seed_error:
                                gamma, seed_error = candidate, candidate_error
                                refinement['accepted'] = True
                except (ValueError, FloatingPointError, OverflowError, np.linalg.LinAlgError) as exc:
                    refinement.update(error_type=type(exc).__name__, error=str(exc))
            attempt['physical_residual'] = seed_error if np.isfinite(seed_error) else None
            attempt['accepted'] = bool(np.isfinite(seed_error) and seed_error <= 1e-8)
            seeded = attempt['accepted'] or circulation_method == 'direct'
        except (ValueError, FloatingPointError, OverflowError, np.linalg.LinAlgError) as exc:
            attempt.update(error_type=type(exc).__name__, error=str(exc), physical_residual=None)
            if circulation_method == 'direct':
                raise AnalysisError(f'Seeded circulation solve raised {type(exc).__name__}: {exc}',
                    details=dict(method='direct', evaluations=attempt['evaluations'], initialization=initialization)) from exc
        seed_evaluations = attempt['evaluations']
        initialization['cold_fallback'] = not seeded

    linear_error = None
    if circulation is None and not seeded:
        try:
            coefficients0 = np.linalg.solve(basis.test@aic@basis.sample, basis.test@rhs) if basis.modes else np.linalg.solve(aic, rhs)
            gamma0 = basis.decode(coefficients0) if basis.modes else coefficients0
        except np.linalg.LinAlgError as exc:
            linear_error = exc
            coefficients0 = np.zeros(basis.size)
            gamma0 = basis.decode(coefficients0)
            if circulation_method == 'direct' or not condition.stall:
                raise AnalysisError("Singular circulation matrix; check overlapping surfaces and mesh.",
                    details=None if initialization is None else dict(initialization=initialization,
                        evaluations=seed_evaluations)) from exc

    iterations = 0
    direct_attempted = False
    solver_report = dict(method='prescribed' if circulation is not None else 'linear', evaluations=0)
    try:
        if seeded:
            solver_report = dict(method='direct', evaluations=0)
        elif circulation is not None:
            gamma = np.asarray(circulation, dtype=float)
            if gamma.shape != gamma_dot.shape:
                raise AnalysisError('Circulation must have one entry per lifting panel.')
            if basis.modes:basis.encode(gamma)
        elif len(gamma0) and (condition.stall or engine_rows or np.any(lag_rate)):
            section_guess = 2*gamma0/(p['chord']*velocities(gamma0)[2])
            near_stall = condition.stall and condition.stall_factor > 0 and bool(np.any(
                (section_guess > p['clmax']-2*condition.stall_width) |
                (section_guess < p['clmin']+2*condition.stall_width)))
            continuation = circulation_method == 'continuation' or (
                circulation_method == 'auto' and (near_stall or linear_error is not None))
            if not continuation:
                direct_attempted = True
                solution = root(lambda x: residual(basis.decode(x)), coefficients0,
                    jac=None if jet_feedback else lambda x: circulation_jacobian(basis.decode(x)),
                    method="hybr", options={"xtol": 1e-10})
                gamma = basis.decode(solution.x)
                iterations = int(solution.nfev)
                solver_report = dict(method='direct', evaluations=iterations)
                continuation = circulation_method == 'auto' and (
                    not np.all(np.isfinite(gamma)) or np.max(abs(residual(gamma)), initial=0.) > 1e-8)
            if continuation:
                from .circulation_solve import continue_circulation, CirculationContinuationError
                # Gamma has units L^2/T. Local scales and the common coefficient
                # scale transform together under arbitrary consistent input units.
                local_scale = .5*p['chord']*condition.speed
                coefficient_scale = float(np.max(local_scale))
                regularizer = basis.test@((coefficient_scale/local_scale)[:, None]*basis.sample)
                continuation_evaluations = 0
                def continuation_residual(z):
                    nonlocal continuation_evaluations
                    continuation_evaluations += 1
                    return residual(basis.decode(z*coefficient_scale))
                try:
                    tracing = True
                    z, solver_report = continue_circulation(
                        continuation_residual, regularizer,
                        derivative=None if jet_feedback else lambda z:
                        circulation_jacobian(basis.decode(z*coefficient_scale))*coefficient_scale,
                        progress=_circulation_progress)
                except CirculationContinuationError as exc:
                    tracing = False
                    if (circulation_method != 'auto' or direct_attempted or linear_error is not None
                            or not np.all(np.isfinite(coefficients0))):
                        raise AnalysisError(str(exc)) from exc
                    # Failure of this auxiliary path does not prove R(Gamma)=0 has
                    # no root. Try the original linear seed once, with no changed
                    # equations or reference-data-dependent choice of branch.
                    direct_attempted = True
                    fallback = dict(seed='original linear circulation coefficients',
                        initial_coefficients=coefficients0.tolist(), evaluations=0,
                        derivative='numerical engine feedback' if jet_feedback else 'analytic',
                        scope='A root of the unchanged equations; uniqueness and stability are not established.')
                    solver_report = dict(method='direct', trigger='failed automatic continuation',
                        failed_continuation=dict(error=str(exc), evaluations=continuation_evaluations),
                        fallback=fallback)
                    def fallback_residual(x):
                        fallback['evaluations'] += 1
                        return residual(basis.decode(x))
                    try:
                        solution = root(fallback_residual, coefficients0.copy(),
                            jac=None if jet_feedback else lambda x: circulation_jacobian(basis.decode(x)),
                            method='hybr', options={'xtol': 1e-10})
                    except (ValueError, FloatingPointError, OverflowError, np.linalg.LinAlgError) as direct_error:
                        fallback.update(error_type=type(direct_error).__name__, error=str(direct_error))
                        raise AnalysisError(f'{exc} Direct fallback raised {type(direct_error).__name__}: '
                            f'{direct_error}', details=solver_report) from direct_error
                    gamma = basis.decode(solution.x)
                    fallback.update(reported_success=bool(solution.success), message=str(solution.message),
                        solver_evaluations=int(solution.nfev), jacobian_evaluations=int(getattr(solution, 'njev', 0)))
                    iterations += continuation_evaluations + fallback['evaluations']
                    solver_report['evaluations'] = iterations
                    if not np.all(np.isfinite(gamma)):
                        fallback['physical_residual'] = None
                        raise AnalysisError('Circulation solve failed: nonfinite circulation endpoint. '
                            f'Direct fallback after: {exc} '
                            f"Fallback evaluations={fallback['evaluations']}.", details=solver_report) from exc
                else:
                    tracing = False
                    gamma = basis.decode(z*coefficient_scale)
                    iterations += solver_report['evaluations']
                    solver_report['evaluations'] = iterations
                    solver_report['trigger'] = 'requested' if circulation_method == 'continuation' else 'stall or failed direct solve'
        else:
            gamma = gamma0
    except AnalysisError as exc:
        if initialization is not None:
            detail = dict(exc.details or solver_report)
            detail['initialization'] = initialization
            detail['evaluations'] = detail.get('evaluations', 0) + seed_evaluations
            exc.details = detail
        raise
    if initialization is not None:
        solver_report['initialization'] = initialization
        solver_report['evaluations'] += seed_evaluations
        iterations += seed_evaluations
        if seeded and not np.all(np.isfinite(gamma)):
            raise AnalysisError('Circulation solve failed: normalized residual nonfinite '
                '(nonfinite circulation endpoint).', details=solver_report)
    residual_value = residual(gamma)
    error = float(np.max(np.abs(residual_value), initial=0.))
    if (circulation is None and len(gamma) and not basis.modes and not engine_rows
            and np.all(np.isfinite(gamma)) and np.isfinite(error) and error > 1e-12):
        from .circulation_polish import polish_circulation
        gamma, residual_value, polish = polish_circulation(
            residual, circulation_jacobian, gamma, residual_value,
            scale=float(np.max(.5*p['chord']*condition.speed)))
        solver_report['terminal_polish'] = polish
        solver_report['evaluations'] += polish['evaluations']
        iterations += polish['evaluations']
        error = float(np.max(np.abs(residual_value), initial=0.))
    if 'fallback' in solver_report:
        solver_report['fallback']['physical_residual'] = error if np.isfinite(error) else None
    if initialization is not None and seeded:
        initialization['seed_attempt']['accepted'] = bool(np.all(np.isfinite(gamma)) and np.isfinite(error) and error <= 1e-8)
        initialization['seed_attempt']['final_physical_residual'] = error if np.isfinite(error) else None
    if not np.all(np.isfinite(gamma)) or not np.isfinite(error) or (circulation is None and error > 1e-8):
        message = f"Circulation solve failed: normalized residual {error:.3g}."
        if 'failed_continuation' in solver_report:
            message += (f" Direct fallback after: {solver_report['failed_continuation']['error']} "
                        f"Fallback evaluations={solver_report['fallback']['evaluations']}.")
        raise AnalysisError(message, details=solver_report if 'fallback' in solver_report or initialization is not None else None)
    if _circulation_progress is not None and circulation is None:
        _circulation_progress('static_circulation_loads', evaluations, 0)
    v, vp, vp_speed = velocities(gamma)
    v_speed = np.linalg.norm(v, axis=-1)
    cl = 2 * gamma / (p["chord"] * vp_speed)
    engines, cp_jet, _ = engine_flow(gamma)
    tangency = np.sum((cp_free + vcp.apply(gamma) + cp_jet) * p["normal"], axis=-1)
    tangency -= 2/np.pi*lag_rate/vp_speed
    flift = rho * gamma[:, None] * cross3(v, p["s"]) * p["ds"][:, None]
    frate = rho * (p['chord']*lag_rate/vp_speed)[:,None] * cross3(v,p['s']) * p['ds'][:,None]
    fprofile = (.5 * rho * v_speed[:, None] * v * (p["chord"] * p["cdf"])[:, None]
                + .5 * rho * vp_speed[:, None] * vp * (p["chord"] * p["cdp"])[:, None]
                + 2 * rho * vp / vp_speed[:, None] * (tangency ** 2 * p["chord"])[:, None]) * p["ds"][:, None]
    local_mach = vp_speed / air["sound_speed"]
    maximum_airflow = None
    if len(local_mach):
        worst = int(np.argmax(local_mach))
        maximum_airflow = dict(beam=int(p['beam'][worst]), t=float(p['t'][worst]),
            position=p['hv'][worst].tolist(), relative_velocity=v[worst].tolist(),
            normal_speed=float(vp_speed[worst]), normal_mach=float(local_mach[worst]))
    if np.any(local_mach >= 1):
        from .airflow_diagnostics import (local_vortex_breakdown, breakdown_message,
                                         rejected_section_airflow, rejected_surface_forces)
        rejected_sections = rejected_section_airflow(p, ig, v, vp_speed, local_mach)
        breakdown = local_vortex_breakdown(vhv, worst, gamma, p, ig, wind, source_core,
            hv_free[worst], engine_flow(gamma)[2][worst], v[worst], frozen=bool(frozen))
        point = ', '.join(f'{x:.7g}' for x in maximum_airflow['position'])
        force_diagnostic = rejected_surface_forces(p, flift, frate, fprofile,
            (e, ey, ez), rho, condition.speed, model.reference[0, 0], local_mach)
        raise AnalysisError("Local section-normal Mach reaches unity; the section pitching-moment correction is undefined. "
            f"Maximum M_perp={maximum_airflow['normal_mach']:.7g} at beam {maximum_airflow['beam']}, "
            f"t={maximum_airflow['t']:.7g}, body force point [{point}] (input L). "
            f"Normal relative speed={maximum_airflow['normal_speed']:.7g}; "
            f"sound speed={air['sound_speed']:.7g} (input L/T). "
            f"Circulation residual={error:.7g} (gate 1e-8). "
            f"Rejected sections={len(rejected_sections)}." + breakdown_message(breakdown),
            details=dict(kind='section_normal_mach', maximum=maximum_airflow,
                         rejected_sections=rejected_sections,
                         surface_force_diagnostic=force_diagnostic,
                         vortex_breakdown=breakdown, circulation_residual=float(error),
                         sound_speed=float(air['sound_speed']), speed_unit='input L/T', position_unit='input L',
                         **({'circulation_solver': solver_report} if initialization is not None else {})))
    cm = p["cm"] / np.sqrt(1 - local_mach ** 2)
    # Displayed Variables in the user guide: physical section normals, rather
    # than the zero-lift/control-modified normal used by flow tangency. da_eff
    # is a linearized normal change, not an arcsine or a difference of angles.
    da_eff = np.divide(np.sum((p['section_normal']-p['jig_normal'])*v, axis=1),
                       v_speed, out=np.full(len(v_speed), np.nan), where=v_speed > 0)
    f_aero = np.sum((flift+frate)*p['section_normal'], axis=1)/p['ds']
    # Section moment convention is about chord/4 in the local c,n plane (eq 72).
    quarter_arm = ((.25 - p['xax']) * p['chord'])[:,None] * p['c']
    section_moment = cross3(quarter_arm, flift+frate)
    section_moment += (.5 * rho * vp_speed ** 2 * p["chord"] ** 2 * cm * p["ds"])[:, None] * p["s"]
    # Profile drag has no intrinsic section couple (steady eq. 74). Integrate
    # the strip's constant distributed profile force at the straight interval's
    # physical centroid (eqs. 49–56), expressed about the existing section rm.
    # The Glauert sample for velocity/circulation and lift arm stay unchanged.
    section_moment += cross3(p['profile_arm'], fprofile)
    # The apparent-mass rate term uses velocity at the beam axis (eq. 84),
    # which is distinct from the bound-vortex force point.
    axis_velocity = condition.speed*e-cross3(omega, p["rm"]-model.reference[3])
    axis_velocity += gust_velocity(p['rm'])
    if surface_motion is not None:
        axis_velocity -= surface_motion.velocity_at(p['rm'])
    if (np.any(omega) or (surface_motion is not None and np.any(surface_motion.rates))
            or getattr(_iteration_fields,'capture_rate_fields',False)):
        axis_velocity += induced_velocity(p["rm"], p["physical"], reference=ig['rm'], cache_name='axis', exclude_bound=np.eye(len(p["t"]), dtype=bool))
        axis_velocity += condition.speed*volume_velocity(p["rm"], ig['rm'], cache_name='axis')
        axis_velocity += jet_velocity(p["rm"], engines, jet_direction, rho, cache_name="axis")
    if incident is not None:axis_velocity = incident('axis', axis_velocity)
    frames = np.stack([p["c"], p["s"], cross3(p["c"], p["s"])], axis=-1)
    fapparent, mapparent = surface_apparent_loads(p["rm"], frames, p["chord"], p["xax"], p["ds"], rho,
                                                axis_velocity, motion_state, model.reference[2],local_motion=surface_motion)
    strip_force = flift+frate+fprofile+fapparent
    section_moment += mapparent
    moment = cross3(p["rm"] - model.reference[1], strip_force) + section_moment
    force = strip_force.sum(axis=0)
    moment = moment.sum(axis=0)
    body_lift, body_profile, body_apparent, body_apparent_moment = [np.zeros(3) for _ in range(4)]
    body_strips = {}
    shoulder_loads=[]
    for mesh in meshes:
        if mesh.beam.lifting:
            continue
        tquad, positions, _, _ = body_quadrature(mesh)
        locations = positions.reshape(-1,3)
        velocity = condition.speed*e-cross3(omega, locations-model.reference[3])
        velocity += gust_velocity(locations)
        body_motion = None if local_motion is None else local_motion.body(mesh)
        if body_motion is not None:
            velocity -= body_motion.velocity.reshape(-1,3)
        body_reference = frozen.body_points[mesh.beam.index] if frozen else locations
        velocity += condition.speed*volume_velocity(locations,body_reference,exclude_body=mesh.beam.physical_index,cache_name=('body',mesh.beam.index))
        velocity += induced_velocity(locations,np.full(len(locations),mesh.beam.physical_index),reference=body_reference,cache_name=('body',mesh.beam.index))
        velocity += jet_velocity(locations,engines,jet_direction,rho,cache_name=("body",mesh.beam.index))
        if incident is not None:velocity = incident(('body', mesh.beam.index), velocity)
        loads = body_loads(mesh,rho,velocity.reshape(positions.shape),motion_state,model.reference[2],condition.body_added_mass_factor,local_motion=body_motion)
        if capture_circulation:
            derivative_bodies.append((mesh, velocity.reshape(positions.shape)))
        total = loads["lift"]+loads["profile"]+loads["apparent"]
        body_lift += loads["lift"].sum(axis=0);body_profile += loads["profile"].sum(axis=0)
        body_apparent += loads["apparent"].sum(axis=0)
        body_apparent_moment += (loads["apparent_moment"]+cross3(mesh.rm-model.reference[1],loads["apparent"])).sum(axis=0)
        force += total.sum(axis=0)
        moment += (loads["moment"]+cross3(mesh.rm-model.reference[1],total)).sum(axis=0)
        body_strips[mesh.beam.index] = [dict(beam=mesh.beam.index,lifting=False,t=float(t),length=float(mesh.length[i]),position=mesh.rm[i].tolist(),
            circulation=None,cl=None,force=total[i].tolist(),moment=loads["moment"][i].tolist(),
            apparent_force=loads["apparent"][i].tolist(),apparent_moment=loads["apparent_moment"][i].tolist(),stalled=False)
            for i,t in enumerate(mesh.tm)]
        if body_motion is not None:
            for i,strip in enumerate(body_strips[mesh.beam.index]):
                strip['force_samples']=loads['force_samples'][i].tolist()
                strip['force_fractions']=((tquad[i]-mesh.t0[i])/(mesh.t1[i]-mesh.t0[i])).tolist()
        for shoulder in (body_shoulders(mesh) if frozen else volume.body_shoulders[mesh.beam.index]):
            position=shoulder['position'];tangent=shoulder['tangent']
            velocity=condition.speed*e-cross3(omega,position-model.reference[3])+gust_velocity(position)
            if local_motion is not None:
                velocity-=local_motion.station(mesh.beam.index,shoulder['t']).velocity_at(position)
            reference = next(s['position'] for s in frozen.volume_field.body_shoulders[mesh.beam.index] if s['t']==shoulder['t']) if frozen else position
            velocity+=condition.speed*volume_velocity(position,reference,exclude_body=mesh.beam.physical_index,cache_name=("shoulder",mesh.beam.index,shoulder["t"]))
            velocity+=induced_velocity(position[None,:],np.array([mesh.beam.physical_index]),reference=reference[None,:],cache_name=("shoulder",mesh.beam.index,shoulder["t"]))[0]
            velocity+=jet_velocity(position[None,:],engines,jet_direction,rho,cache_name=("shoulder",mesh.beam.index,shoulder["t"]))[0]
            if incident is not None:velocity = incident(('shoulder', mesh.beam.index, shoulder['t']), velocity)
            along=velocity@tangent;normal=velocity-along*tangent
            load=rho*normal*along*shoulder['area_jump']
            body_lift+=load;force+=load;moment+=cross3(position-model.reference[1],load)
            shoulder_loads.append(dict(beam=mesh.beam.index,t=shoulder['t'],position=position.tolist(),tangent=tangent.tolist(),
                radius_left=shoulder['radius_left'],radius_right=shoulder['radius_right'],area_jump=shoulder['area_jump'],
                incident_velocity=velocity.tolist(),force=load.tolist(),moment=[0.,0.,0.]))
    # Steady eqs. 220–223 differentiate distributed lift/profile loads.
    # Keep these separate from engine, point-object and apparent-mass loads.
    distributed_aero_force = force-fapparent.sum(axis=0)-body_apparent
    distributed_aero_moment = moment-(mapparent+cross3(p["rm"]-model.reference[1],fapparent)).sum(axis=0)-body_apparent_moment
    point_drag = np.zeros(3)
    point_forces = []
    for point_index, row in enumerate(weight_rows):
        # Point-object CDA contribution at its current pylon position.
        r = row[2:5] if point_positions is None else point_positions[point_index]
        vel = condition.speed * e - cross3(omega, r - model.reference[3])
        vel += gust_velocity(r)
        if local_motion is not None:
            vel -= local_motion.point('weight',point_index).velocity_at(r)
        # Evaluate the induced field with inter-object finite cores.
        reference = np.asarray(row[2:5])[None,:]
        vel += induced_velocity(np.asarray(r)[None,:],reference=reference,cache_name=("point",point_index))[0]
        vel += condition.speed*volume_velocity(np.asarray(r)[None,:],reference,exclude_point=point_index,cache_name=("point",point_index))[0]
        vel += jet_velocity(np.asarray(r)[None, :], engines, jet_direction, rho,cache_name=("point",point_index))[0]
        if incident is not None:vel = incident(('point', point_index), vel)
        drag = .5 * rho * np.linalg.norm(vel) * vel * row[6]
        if capture_circulation:
            derivative_points.append((np.asarray(r), vel, row[6]))
        point_drag += drag
        moment += cross3(r - model.reference[1], drag)
        point_forces.append(drag.tolist())
    force += point_drag
    engine_force, engine_moment = np.zeros(3), np.zeros(3)
    for engine in engines:
        engine_force += engine["force"]
        engine_moment += engine["moment"]+cross3(engine["position"]-model.reference[1], engine["force"])
    force += engine_force
    moment += engine_moment
    if capture_circulation:
        _iteration_fields.circulation_aero = dict(
            p=p, gamma=gamma, lag_rate=lag_rate, basis=basis, condition=condition,
            rho=rho, sound_speed=air['sound_speed'], velocity=v, tangency=tangency,
            cp_velocity=cp_free+vcp.apply(gamma)+cp_jet,
            rates=omega if surface_motion is None else omega+surface_motion.rates,
            engine_rows=engine_rows, engines=engines, engine_points=engine_points,
            engine_velocity=engine_free+engine_aic.apply(gamma),
            engine_rates=engine_rates, engine_rotations=engine_rotations,
            bodies=derivative_bodies, points=derivative_points, shoulders=shoulder_loads,
            direction=e, jet_direction=jet_direction)
    if _loads_only:
        # Internal mounted-residual path: preserve the physical calculations
        # above, but defer wake diagnostics, sensors and export formatting to
        # a detailed evaluation. These fields are not equilibrium equations.
        surface_strips = [dict(beam=int(p["beam"][i]), force=strip_force[i].tolist(),
                               moment=section_moment[i].tolist()) for i in range(len(gamma))]
        result = dict(circulation_residual=residual(gamma).tolist(), point_forces=point_forces,
                    body_shoulders=shoulder_loads, engines=[engine_report(engine) for engine in engines],
                    strips=[strip for mesh in meshes for strip in
                            ([s for s in surface_strips if s["beam"] == mesh.beam.index]
                             if mesh.beam.lifting else body_strips[mesh.beam.index])])
        if gust.kind != 'none':
            # Time-step phase guards need receiver positions even when only
            # loads were requested. Match the full snapshot's sensor receivers
            # without recomputing their flow or recovering any display output.
            sensor_rows = model.records.get('sensor', [])
            receivers = list(gust_locations)
            if sensor_rows:
                receivers.append(np.array([row[3:6] for row in sensor_rows] if sensor_positions is None else sensor_positions).reshape(-1,3))
            from .ground import body_to_earth
            locations = np.concatenate(receivers)
            result['gust'] = dict(sample_positions_earth=(locations@body_to_earth(condition.attitude).T+condition.position_earth).tolist())
        return result
    q = .5 * rho * condition.speed ** 2
    area, chord_ref, span = model.reference[0]
    qs = q * area
    def coefficient(value, length=1.):
        return float(value / (qs * length)) if area > 0 else None
    # Eq. 221 integrates position cross force about the body origin. Keep
    # the reference-point wrench used by constraints, and expose the origin
    # wrench separately (eq. 187: M_ref = M_origin + F cross r_ref).
    moment_origin = moment + cross3(model.reference[1], force)
    distributed_aero_moment_origin = distributed_aero_moment + cross3(model.reference[1], distributed_aero_force)
    lift_coeff = coefficient(force @ ez)
    cdi = coefficient(flift.sum(axis=0) @ e)
    cdp = coefficient((fprofile.sum(axis=0) + body_profile + point_drag) @ e)
    if area > 0:
        efficiency_near = float(flift.sum(axis=0) @ ez / qs) ** 2 / (np.pi * (span ** 2 / area) * cdi) if cdi > 1e-12 else None
    else:
        near_lift, near_drag = float(flift.sum(axis=0) @ ez), float(flift.sum(axis=0) @ e)
        efficiency_near = near_lift**2 / (np.pi * span**2 * q * near_drag) if near_drag > 0 else None
    trefftz = trefftz_for_meshes(model, replace(condition, alpha=0., beta=0.) if frozen else condition,
                               frozen.meshes if frozen else meshes, gamma, rho, ground)
    trefftz['influence_geometry'] = 'undeformed; zero wind angles' if frozen else 'current; current wind angles'
    if fourier_wake_diagnostic:
        from .fourier_wake import fourier_wake_for_meshes
        trefftz['continuous_fourier'] = fourier_wake_for_meshes(
            model, replace(condition, alpha=0., beta=0.) if frozen else condition,
            frozen.meshes if frozen else meshes, gamma, basis, rho, ground)
    ground_report=ground.report(clearance)
    ground_report['oblique_compressible']=bool(ground.flag and mach>1e-12 and abs(ground.normal@wind)>1e-10)
    ground_report['limitations']=[]
    if ground.flag:
        ground_report['limitations'].append('Ground images act on instantaneous vortices, sources and doublets. Local section apparent mass follows unsteady Eqs.43–44, without a separate wall-dependent tensor.')
        if ground_report['oblique_compressible']:
            ground_report['limitations'].append('The wind has a component normal to the plane. Physical images followed by PG transformation are an approximation for oblique compressible ground flow; exact impermeability is verified for incompressible flow or wind parallel to the plane.')
        if ground.flag == -1:
            ground_report['limitations'].append('Free-surface images impose the linearized constant-pressure condition; interface deformation and waves are not modeled.')
            if abs(ground.normal@wind)>1e-10:
                ground_report['limitations'].append('The constant-pressure image condition assumes wind parallel to the free surface; this oblique-onset result is an approximation.')
        if any(engine['jet_enabled'] for engine in engines):
            ground_report['limitations'].append('Propulsive jets are not reflected or deflected by the ground plane.')
    from .vortex_display import vortex_geometry
    result = {
        "vortex_geometry": vortex_geometry(ig, wind, frozen=bool(frozen)),
        "analysis": "instantaneous_unsteady" if local_motion is not None or circulation_rate is not None else "rigid_steady", "converged": error <= 1e-8, "residual": error, "evaluations": iterations,
        "circulation_solver": solver_report,
        "circulation_residual": residual(gamma).tolist(), "point_forces": point_forces,
        "circulation_local_residual": local_residual(gamma).tolist(),
        "circulation_discretization": basis.report(gamma),
        "section_output_definitions": dict(
            cm='Local chord/4 pitching-moment coefficient, including flap mixing and the actual section-normal Mach correction; excludes moment arms and apparent-mass moments.',
            f_aero='Circulatory plus enabled circulation-rate force projected on the physical current section normal, per current length [input F/L]. Profile drag, apparent mass and point loads are excluded.',
            f_reac='Distributed real-mass gravity/inertia plus apparent-mass force projected on the physical current section normal, per current length [input F/L]. Excludes point masses, engines, struts, applied point loads and support reactions.',
            f_reac_sampling='Unavailable until distributed real-mass loads are evaluated by a rigid or network analysis.',
            da_eff='(n - n_jig) dot V_relative / |V_relative| [rad], using physical section normals and total relative velocity at the bound-vortex force point. This is the documented linearized incidence change, not an exact angle difference. Undefined at zero relative speed.',
            sampling='Aerodynamic quantities use material Glauert midpoint stations. Inertial forces are interval averages, reported at those stations. No half-interval shift to structural nodes is applied.'),
        "lifting_airflow": dict(samples=len(local_mach), maximum=maximum_airflow,
            sound_speed=float(air['sound_speed']), speed_unit='input L/T', position_unit='input L',
            axes='Body axes',
            scope='Relative fluid velocity at each lifting force point, including induced flow, gusts, jets and local section motion. Normal speed excludes the component along the current span axis. Local Mach uses atmospheric sound speed, independently of the selected PG Mach.',
            sampling=('Current force points for kinematics/gusts/jets; induced coefficients at jig force points under K/F.' if frozen else
                      'Current bound-vortex force points; these differ from the reported beam-axis strip positions.'),
            validity='Subsonic local Mach is necessary, not sufficient for physical validity or mesh convergence. Swept lifting lines can develop growing force-point velocities under refinement.'),
        "aerodynamic_influences": dict(frozen=bool(frozen), geometry='undeformed' if frozen else 'current',
            wind_angles=[0.,0.] if frozen else [float(condition.alpha),float(condition.beta)],
            pg_mach=mach, volume_geometry='undeformed' if frozen else 'current',
            ground='Current Earth pose and image plane; coefficients update when the plane changes.',
            scope='Vortex and volume velocity coefficients. Current circulation, section frames, lengths, motion, gusts, jets and loads remain active.',
            attached_receivers='Jig positions' if frozen else 'Current positions',
            external_receivers='Requested spatial positions'),
        "wake_core": dict(ratio=core_ratio, rule=f'max(ratio * local chord, {"undeformed" if frozen else "current"} interval length)',
            minimum_radius=float(np.min(source_core)) if len(source_core) else None,
            maximum_radius=float(np.max(source_core)) if len(source_core) else None,
            spacing_limited_panels=int(np.sum(ig['ds'] >= core_ratio*ig['chord'])),
            radius_unit='input L',
            scope='Lifting-surface interactions within one physical beam use zero core. Distinct physical beams and external probes/objects use the configured cores; images inherit the selected influence core.'),
        "aerodynamic_lag": dict(enabled=bool(condition.aero_lag),
            circulation='differential' if condition.aero_lag else 'algebraic',
            shed_downwash_coefficient=2/np.pi if condition.aero_lag else 0.,
            circulation_rate_lift=bool(condition.aero_lag),
            apparent_mass='Retained independently of the aerodynamic-lag setting.'),
        "coefficient_normalization": dict(available=bool(area > 0), reference_area=float(area),
            reason=None if area > 0 else 'Sref is zero; area-normalized coefficients are undefined. Dimensional loads and circulation are retained.'),
        "CL": lift_coeff, "CY": coefficient(force @ ey), "CD": coefficient(force @ e),
        "CDi": trefftz['CDi'], "CLi": trefftz['CLi'], "CYi": trefftz['CYi'], "CDi_near": cdi, "CDp": cdp,
        "CDam": coefficient((fapparent.sum(axis=0)+body_apparent) @ e),
        "CDrate": coefficient(frate.sum(axis=0) @ e),
        "CDbody": coefficient(body_lift @ e),
        "CDeng": coefficient(engine_force @ e),
        "Cl": coefficient(-moment[0], span), "Cm": coefficient(moment[1], chord_ref), "Cn": coefficient(-moment[2], span),
        "Cm_origin": coefficient(moment_origin[1], chord_ref),
        "efficiency": trefftz['efficiency'], "trefftz": trefftz,
        "efficiency_near": efficiency_near,
        "coefficient_definitions": dict(CDi='Trefftz-plane induced drag', CDi_near='Near-field circulation-force drag projection',
            CD='Total near-field force projection: CDi_near+CDp+CDbody+CDam+CDeng+CDrate',
            Cl='Negative body-x moment about Reference row 2, divided by q*Sref*Bref',
            Cm='Body-y moment about Reference row 2, divided by q*Sref*Cref',
            Cn='Negative body-z moment about Reference row 2, divided by q*Sref*Bref',
            Cm_origin='Body-y moment about the body origin, divided by q*Sref*Cref; same load scope as Cm',
            efficiency='Trefftz-plane (CLi^2+CYi^2)/(pi*(Bref^2/Sref)*CDi)'),
        "force": force.tolist(), "moment": moment.tolist(), "mach": mach, "panels": sum(len(m.tm) for m in meshes),
        "moment_origin": moment_origin.tolist(),
        "moment_definitions": dict(reference=model.reference[1].tolist(), axes='body',
            translation='moment_origin = moment + reference cross force',
            scope='Aerodynamic, apparent-mass, point-object drag and engine loads; excludes real-mass gravity/inertia and support reactions.',
            distributed_scope='Distributed lift/profile loads, including body shoulders; excludes apparent mass, point objects and engines.'),
        "body_shoulders": shoulder_loads,
        "lifting_panels": len(gamma), "body_added_mass_factor": condition.body_added_mass_factor,
        "ground_plane": ground_report,
        "earth_state": condition.earth_state(model),
        "reference_flow": reference_airflow(model, condition, air),
        "gust": gust.report(condition, model.reference[3]),
        "atmosphere": air,
        "surface_force": strip_force.sum(axis=0).tolist(),
        "circulation_rate_force": frate.sum(axis=0).tolist(),
        "circulation_rate_moment": cross3(p['rm']+quarter_arm-model.reference[1],frate).sum(axis=0).tolist(),
        "distributed_aero_force": distributed_aero_force.tolist(),
        "distributed_aero_moment": distributed_aero_moment.tolist(),
        "distributed_aero_moment_origin": distributed_aero_moment_origin.tolist(),
        "surface_apparent_force": fapparent.sum(axis=0).tolist(),
        "body_force": (body_lift+body_profile+body_apparent).tolist(),
        "engines": [engine_report(engine) for engine in engines],
        "engine_force": engine_force.tolist(), "engine_moment": engine_moment.tolist(),
        "apparent_force": (fapparent.sum(axis=0)+body_apparent).tolist(),
        "apparent_moment": ((mapparent+cross3(p["rm"]-model.reference[1], fapparent)).sum(axis=0)+body_apparent_moment).tolist(),
        "apparent_mass": apparent_properties(meshes, rho, model.reference[1], condition.body_added_mass_factor),
        "strips": [dict(beam=int(p["beam"][i]), lifting=True, t=float(p["t"][i]),length=float(p["ds"][i]), position=p["rm"][i].tolist(),
                         circulation=float(gamma[i]), cl=float(cl[i]), force=strip_force[i].tolist(),
                         velocity_position=p['hv'][i].tolist(), relative_velocity=v[i].tolist(),
                         normal_speed=float(vp_speed[i]), normal_mach=float(local_mach[i]),
                         cm=float(cm[i]), f_aero=float(f_aero[i]),
                         da_eff=float(da_eff[i]) if np.isfinite(da_eff[i]) else None,
                         wake_core_radius=float(source_core[i]),
                         circulation_rate=float(gamma_dot[i]), circulation_rate_force=frate[i].tolist(),
                         moment=section_moment[i].tolist(),
                         apparent_force=fapparent[i].tolist(), apparent_moment=mapparent[i].tolist(),
                         stalled=bool(cl[i] > p["clmax"][i] or cl[i] < p["clmin"][i])) for i in range(len(gamma))],
        "limitations": ["Prescribed rigid geometry; structural deflection and free-flight trim are not solved.",
                        "Steady accelerating-frame and instantaneous apparent-mass loads; unsteady circulation lag is not solved.",
                        "CDi and span efficiency use the frozen straight Trefftz wake; total CD and load balance use near-field forces, including CDi_near."]
    }
    sensor_rows = model.records.get('sensor', [])
    result['sensor_airflow'] = []
    if sensor_rows:
        locations = np.array([row[3:6] for row in sensor_rows] if sensor_positions is None else sensor_positions).reshape(-1,3)
        sensed = condition.speed*e-cross3(omega, locations-model.reference[3])
        if local_motion is not None:
            for i, point in enumerate(locations):
                sensed[i] -= local_motion.point('sensor', i).velocity_at(point)
        reference = np.array([row[3:6] for row in sensor_rows]).reshape(-1,3)
        induced = influences(locations,reference=reference).apply(gamma)+condition.speed*volume_velocity(locations,reference)
        induced += jet_velocity(locations, engines, jet_direction, rho)
        wind = gust_velocity(locations)
        result['sensor_airflow'] = [dict(index=int(row[0]), position=point.tolist(),
            kinematic_velocity=kin.tolist(), induced_velocity=ind.tolist(), gust_velocity=gus.tolist(),
            relative_velocity=(kin+ind+gus).tolist()) for row, point, kin, ind, gus in zip(sensor_rows, locations, sensed, induced, wind)]
    if survey_positions is not None:
        locations=np.asarray(survey_positions,dtype=float)
        if locations.ndim!=2 or locations.shape[1]!=3 or not 1<=len(locations)<=10000 or not np.all(np.isfinite(locations)):
            raise AnalysisError('A flow survey requires 1 to 10000 finite xyz sample positions.')
        # External probes use the same source cores and physical image/PG
        # transformations as sensors. Chunking bounds the influence array.
        components={key:[] for key in ('kinematic','gust','lifting','volume','jet')}
        for start in range(0,len(locations),128):
            points=locations[start:start+128]
            components['kinematic'].append(condition.speed*e-cross3(omega,points-model.reference[3]))
            components['gust'].append(gust_velocity(points))
            components['lifting'].append(influences(points).apply(gamma))
            components['volume'].append(condition.speed*volume_velocity(points))
            components['jet'].append(jet_velocity(points,engines,jet_direction,rho))
        components={key:np.concatenate(values) for key,values in components.items()}
        components['induced']=components['lifting']+components['volume']+components['jet']
        components['air']=components['gust']+components['induced']
        components['relative']=components['kinematic']+components['air']
        result['flow_survey']=dict(position_body=locations.tolist(),
            velocity_body={key:values.tolist() for key,values in components.items()},
            fluid_side=(np.ones(len(locations),dtype=bool) if not ground.flag else ground.distance(locations)>=0).tolist(),
            vortex_core=f'Vortex core: max({core_ratio:.17g} * local chord, {"undeformed" if frozen else "current"} interval length), as for external sensors.',
            reference='Relative velocity subtracts rigid flight-frame motion. Air velocity is relative to the still atmosphere. No elastic velocity field is extrapolated away from the aircraft.',
            wake=('Current circulation on undeformed horseshoes with x-directed wakes. Attached sensors use jig receiver positions; external surveys sample the frozen field at the requested spatial positions.' if frozen else
                  'Current circulation on straight wind-aligned horseshoes; no resolved shed-wake history.'))
    surface_strips = result["strips"]
    result["strips"] = [strip for mesh in meshes for strip in
                        ([s for s in surface_strips if s["beam"] == mesh.beam.index] if mesh.beam.lifting else body_strips[mesh.beam.index])]
    result['limitations']+=ground_report['limitations']
    if shoulder_loads:
        from .body_shoulders import LIMITATION
        result['limitations'].append(LIMITATION)
    if gust.kind != 'none':
        # Preserve the actual locations used by the load evaluation, for the
        # time-step phase guard and reproducible field sampling in exports.
        locations = np.concatenate(gust_locations)
        from .ground import body_to_earth
        result['gust']['sample_positions_earth'] = (locations@body_to_earth(condition.attitude).T+condition.position_earth).tolist()
        result['limitations'] += GUST_LIMITATIONS
    if result['analysis']=='instantaneous_unsteady':
        result['limitations'][:2]=[
            'Instantaneous loads and circulation-lag residual at prescribed geometry and motion; no time integration or flutter solution.',
            ('Empirical circulation lag approximates shed vorticity; volume and propulsion wakes remain quasi-steady.' if condition.aero_lag else
             'Circulation satisfies instantaneous flow tangency; shed-vorticity lag and circulation-rate lift are disabled.')]
    if not condition.aero_lag:
        result['limitations'].append('Aerodynamic lag is disabled: circulation satisfies instantaneous flow tangency, and circulation-rate lift is omitted. Apparent mass, elastic inertia and damping remain active.')
    if frozen:
        result['limitations'].append('K/F freezes vortex and volume influences at jig geometry and zero wind angles. This approximation loses influence changes from deformation and wind alignment; use current influences for large deformations, extreme angles or close wake interactions. Trefftz coefficients use the frozen wake axes; total near-field coefficients use actual flight axes.')
    return result


def _add_section_reactions(result, meshes, mass_forces, sampling):
    """Attach interval-average distributed inertia without modifying solver loads."""
    for mesh in meshes:
        if not mesh.beam.lifting:
            continue
        rows = [s for s in result['strips'] if s['beam'] == mesh.beam.index]
        real = mass_forces[mesh.beam.index]
        for i, row in enumerate(rows):
            row['f_reac'] = float((real[i]+row['apparent_force'])@mesh.frames[i, :, 2]/mesh.length[i])
    result['section_output_definitions']['f_reac_sampling'] = sampling


def solve_rigid(model: Model, condition: FlightCondition, panels=48, *, circulation_method='auto', initial_circulation=None,
                fourier_wake_diagnostic=False):
    """Solve on rigid geometry, optionally starting from physical panel Gamma."""
    _validate(model, condition)
    meshes = model_meshes(model, panels)
    result = evaluate_aerodynamics(model, condition, meshes, circulation_method=circulation_method,
                                  initial_circulation=initial_circulation, fourier_wake_diagnostic=fourier_wake_diagnostic)
    from .discretization import report as mesh_report
    result['mesh_discretization'] = mesh_report(model, meshes, panels)
    mass = InertiaModel(model, meshes)
    masses = mass.elements(meshes)
    result["mass_properties"] = mass.summary(masses)
    gravity = GroundPlane.from_condition(condition).rotation.T@np.array(
        [0., 0., -(model.constants[0] if condition.gravity_magnitude is None else condition.gravity_magnitude)])
    mass_forces = {mesh.beam.index:np.zeros_like(mesh.rm) for mesh in meshes}
    for element in masses:
        if element['point'] is None:
            force, _ = inertial_wrench(*(element[k] for k in ('mass', 'position', 'inertia', 'spin')),
                                      condition.motion(), gravity, model.reference[2])
            mass_forces[element['beam']] += force
    _add_section_reactions(result, meshes, mass_forces,
        'Rigid analysis: distributed material mass represented at each interval centroid, divided by current interval length. Point masses excluded.')
    from .sensors import rigid_sensors, UNITS, LIMITATIONS
    result['sensors'] = rigid_sensors(model, condition, result)
    result['sensor_metadata'] = dict(units=UNITS, limitations=LIMITATIONS)
    return result
