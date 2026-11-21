"""Canonical inverse-history quantities; parsing is not initialization support.

Legacy labels name active inverse actuator targets. Explicit Earth-vector
quantity names are extensions in canonical units, not inferred Spec.Ax labels.
Controller measurement definitions are deliberately outside this catalog.
"""
from dataclasses import asdict, dataclass
from types import MappingProxyType
import math
import numpy as np


@dataclass(frozen=True)
class HistoryTarget:
    quantity: str
    label: str
    table_unit: str
    target_unit: str
    factor: float
    semantics: str
    derivative_order: int
    periodic: bool = False
    label_kind: str = 'documented global label'


_targets = [
    HistoryTarget('reference.equivalent_airspeed', 'V', 'input L/T', 'input L/T', 1.,
                  'Gust-relative airspeed at the body velocity reference times sqrt(rho/rho0); low-speed equivalent-airspeed convention, not proven executable IAS parity.', 1),
    HistoryTarget('reference.alpha', 'A', 'deg', 'deg', 1.,
                  'Gust-relative alpha at the body velocity reference; excludes induced and local elastic flow.', 1, True),
    HistoryTarget('reference.beta', 'B', 'deg', 'deg', 1.,
                  'Gust-relative beta at the body velocity reference; excludes induced and local elastic flow.', 1),
    HistoryTarget('flight_path', 'Ga', 'deg', 'deg', 1.,
                  'Climb angle of stationary-air Earth velocity at the velocity reference; original ASW reference-point parity is unresolved.', 1),
]
for _axis in 'xyz':
    _targets.append(HistoryTarget('rates.'+_axis, 'W'+_axis, 'deg/input T', 'rad/input T', math.pi/180,
                                 'Body angular-velocity vector component; not an Euler-angle rate.', 1))
    _targets.append(HistoryTarget('position_earth.'+_axis, 'R'+_axis.upper(), 'input L', 'input L', 1.,
                                 'Body-origin Earth position; not the velocity-reference position.', 2))
for _axis, _name in zip('xyz', ('bank', 'elevation', 'heading')):
    _targets.append(HistoryTarget('attitude.'+_name, 'E'+_axis, 'deg', 'deg', 1.,
                                 'ASW principal Euler chart R=Rz(-heading) Ry(elevation) Rx(-bank); nonsingular elevation required.', 2,
                                 _name != 'elevation'))
for _group, _unit, _order, _meaning in [
    ('velocity_earth', 'input L/T', 1, 'Stationary-air Earth velocity at the body velocity reference, R(U_origin + Omega cross r_v).'),
    ('rates_earth', 'rad/input T', 1, 'Earth angular-velocity vector R Omega, in radians per input time.'),
    ('acceleration_earth', 'input L/T^2', 0, 'Absolute acceleration at the acceleration reference, resolved in Earth axes; not body-origin acceleration or a body-velocity derivative.'),
    ('angular_acceleration_earth', 'rad/input T^2', 0, 'Absolute angular-acceleration vector in Earth axes, in radians per squared input time.'),
]:
    for _axis in 'xyz':
        _quantity = _group+'.'+_axis
        _targets.append(HistoryTarget(_quantity, _quantity, _unit, _unit, 1., _meaning, _order,
                                     label_kind='explicit canonical extension'))
TARGETS = MappingProxyType({item.quantity: item for item in _targets})
_LABELS = MappingProxyType({item.label.lower(): item for item in _targets})


def history_channel(name):
    """Resolve only documented global labels or declared canonical extensions."""
    return _LABELS.get(name.lower()) if isinstance(name, str) else None


def history_catalog():
    """Return JSON-safe metadata; no full-history solver capability is implied."""
    return [asdict(item) for item in TARGETS.values()]


def _finite(value):
    return (not isinstance(value, (bool, np.bool_))
            and isinstance(value, (int, float, np.integer, np.floating)) and np.isfinite(value))


def validate_history_target(quantity, target):
    if quantity not in TARGETS or not _finite(target):
        raise ValueError('Inverse history target requires a supported canonical quantity and finite numeric value.')
    if quantity == 'reference.equivalent_airspeed' and target <= 0:
        raise ValueError('Inverse reference equivalent-airspeed target must be positive.')
    if quantity in ('reference.alpha', 'attitude.bank', 'attitude.heading') and abs(target) > 180:
        raise ValueError('Inverse periodic angle targets use the principal range [-180, 180] degrees; multi-turn histories are not defined.')
    if quantity in ('reference.beta', 'attitude.elevation', 'flight_path') and abs(target) >= 90:
        raise ValueError('Inverse beta, elevation and flight-path targets require the open nonsingular range (-90, 90) degrees.')


def validate_history_actual(quantity, actual, condition, aero):
    """Reject undefined/nondifferentiable achieved charts only for time rows."""
    if not _finite(actual):
        raise ValueError(f'Inverse history {quantity} is undefined or nonfinite at the trial state.')
    if quantity.startswith('reference.'):
        flow = aero['reference_flow']
        velocity = np.asarray(flow['relative_velocity_body'], dtype=float)
        speed = float(np.linalg.norm(velocity))
        scale = max(np.linalg.norm(flow['still_air_velocity_body']), np.linalg.norm(flow['gust_velocity_body']))
        if not np.isfinite(speed) or speed <= 32*np.finfo(float).eps*scale:
            raise ValueError('Inverse reference-airflow chart is undefined at zero or cancelled airspeed.')
        if quantity in ('reference.alpha', 'reference.beta') and math.hypot(velocity[0], velocity[2]) <= 1e-10*speed:
            raise ValueError('Inverse flow-angle chart is singular at a lateral velocity direction.')
    if quantity.startswith('attitude.'):
        elevation = float(condition.attitude[1])
        if not np.isfinite(elevation) or abs(elevation) >= 90 or abs(math.cos(math.radians(elevation))) <= 1e-10:
            raise ValueError('Inverse Euler-angle chart is singular or outside principal elevation (-90, 90).')
    if quantity == 'flight_path':
        velocity = np.asarray(aero['earth_state']['velocity_earth'], dtype=float)
        speed = float(np.linalg.norm(velocity))
        if not np.isfinite(speed) or speed <= 0 or math.hypot(velocity[0], velocity[1]) <= 1e-10*speed:
            raise ValueError('Inverse flight-path chart requires nonzero, nonvertical Earth velocity at the velocity reference.')


def history_error(quantity, actual, target, *, anchor_error=None):
    """Local signed error; optional stencil anchor rejects a periodic cut jump.

    The caller owns the anchor's lifetime. This helper does not unwrap or alter
    table polynomials. Initial derivative stencils may own an explicit context.
    """
    if quantity not in TARGETS or not _finite(actual) or not _finite(target):
        raise ValueError('Inverse history error needs a supported quantity and finite values.')
    error = float(actual-target)
    if TARGETS[quantity].periodic:
        error = (error+180.) % 360.-180.
        if abs(abs(error)-180.) <= 1e-7:
            raise ValueError('Inverse periodic-angle residual is antipodal; select a continuous local branch.')
        if anchor_error is not None:
            if not _finite(anchor_error) or abs(error-anchor_error) >= 180.:
                raise ValueError('Inverse periodic-angle stencil crosses its anchored residual branch cut.')
    return error


@dataclass(frozen=True)
class PeriodicStencilAnchor:
    """One local lift, owned by a derivative stencil rather than a trajectory."""
    variable: str
    quantity: str
    actual: float
    target: float
    error: float


@dataclass(frozen=True)
class PeriodicStencilContext:
    """Immutable local angle charts for a frozen initial-time polynomial.

    Physical targets retain their principal-range validation. Only this explicit
    context permits a periodic Taylor target to leave that range. Achieved
    angles are lifted about the anchor, so their displayed +/-180 wrap is not a
    discontinuity. Each actual/target displacement must stay within a half-turn
    of its anchor, and the lifted error stays on the initial shortest-error
    branch. This is deliberately local, not a multi-turn table interpretation.
    """
    time: float
    side: str
    source: str
    anchors: tuple

    def __post_init__(self):
        if not _finite(self.time) or self.side not in ('left', 'right') or not isinstance(self.source, str):
            raise ValueError('Periodic stencil context needs a finite anchor, selected side and source.')
        object.__setattr__(self, 'anchors', tuple(self.anchors))
        for a in self.anchors:
            if not isinstance(a, PeriodicStencilAnchor) or not isinstance(a.variable, str):
                raise ValueError('Periodic stencil anchors need explicit actuator/quantity ownership.')
            if a.quantity not in TARGETS or not TARGETS[a.quantity].periodic:
                raise ValueError('Periodic stencil anchors require periodic inverse-history quantities.')
            validate_history_target(a.quantity, a.target)
            if a.error != history_error(a.quantity, a.actual, a.target):
                raise ValueError('Periodic stencil anchor error must match its physical actual/target pair.')
        if len({(a.variable, a.quantity) for a in self.anchors}) != len(self.anchors):
            raise ValueError('Periodic stencil anchors need unique actuator/quantity ownership.')

    @classmethod
    def from_report(cls, time, side, source, rows):
        if not _finite(time) or side not in ('left', 'right') or not isinstance(source, str):
            raise ValueError('Periodic stencil context needs a finite anchor, selected side and source.')
        anchors = []
        for row in rows:
            quantity, actual, target = row['quantity'], row['actual'], row['specified_target']
            if quantity not in TARGETS or not TARGETS[quantity].periodic:
                raise ValueError('Periodic stencil anchors require periodic inverse-history quantities.')
            validate_history_target(quantity, target)
            error = history_error(quantity, actual, target)
            anchors.append(PeriodicStencilAnchor(row['variable'], quantity, float(actual), float(target), error))
        keys = [(a.variable, a.quantity) for a in anchors]
        if len(set(keys)) != len(keys) or not all(isinstance(a.variable, str) for a in anchors):
            raise ValueError('Periodic stencil anchors need unique actuator/quantity ownership.')
        return cls(float(time), side, source, tuple(anchors))

    def validate_rows(self, rows):
        expected = {(row.variable, row.quantity) for row in rows if TARGETS[row.quantity].periodic}
        if expected != {(a.variable, a.quantity) for a in self.anchors}:
            raise ValueError('Periodic stencil context does not match active inverse-history ownership.')

    def error(self, variable, quantity, actual, target):
        anchor = next((a for a in self.anchors if (a.variable, a.quantity) == (variable, quantity)), None)
        if anchor is None or not _finite(actual) or not _finite(target):
            raise ValueError('Periodic stencil error needs its owned row and finite actual/target values.')
        # atan/Euler output may wrap, but this displacement follows the same
        # local orientation. Never wrap the polynomial target itself.
        actual_change = history_error(quantity, actual, anchor.actual)
        target_change = float(target-anchor.target)
        if abs(target_change) >= 180.-1e-7:
            raise ValueError('Periodic stencil target exits its anchored local half-turn chart.')
        error = anchor.error+actual_change-target_change
        if abs(error) >= 180.-1e-7:
            raise ValueError('Periodic stencil residual exits its anchored shortest-error branch.')
        return float(error)

    def report(self):
        return dict(kind='initialization stencil only', anchor=self.time, side=self.side,
                    source=self.source, physical_lookup=False,
                    anchors=[asdict(a) for a in self.anchors],
                    policy='Local achieved-angle lift and unwrapped frozen target polynomial; no physical sample unwrapping or multi-turn interpretation.')
