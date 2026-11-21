"""Air-data constraints at the body-fixed ASW velocity reference, eqs. 181–184.

FlightCondition stores still-atmosphere speed/angles at that reference. Thus
-U_origin - Omega x r_ref is already speed*wind; rotation must not be counted
twice. The reference air-data velocity adds the posed Earth gust, without
lifting/volume/jet induced flow or a beam's local elastic velocity.
"""
import math
import numpy as np
from .atmosphere import operating_air
from .ground import body_to_earth
from .gust import gust_field


QUANTITIES = ('speed', 'alpha', 'beta', 'equivalent_airspeed', 'dynamic_pressure')


def validate_reference_target(quantity, target):
    key = quantity.removeprefix('reference.')
    if key not in QUANTITIES or isinstance(target, (bool, np.bool_)) or not isinstance(target, (int, float, np.integer, np.floating)) or not np.isfinite(target):
        raise ValueError('Reference-airflow constraints require a supported quantity and finite numeric target.')
    if key in ('speed', 'equivalent_airspeed', 'dynamic_pressure') and target <= 0:
        raise ValueError('Reference airspeed and dynamic-pressure targets must be positive.')
    if key in ('alpha', 'beta') and abs(target) > (180 if key == 'alpha' else 90):
        raise ValueError('Reference alpha must lie within ±180 degrees and beta within ±90 degrees.')


def reference_airflow(model, condition, atmosphere=None):
    air = operating_air(model, condition) if atmosphere is None else atmosphere
    rotation = body_to_earth(condition.attitude)
    reference = np.asarray(model.reference[3], dtype=float)
    earth = np.asarray(condition.position_earth)+rotation@reference
    gust_earth = gust_field(condition.gust).velocity(earth, condition.time)
    gust_body = rotation.T@gust_earth
    still = condition.speed*condition.vectors()[0]
    relative = still+gust_body
    if not np.all(np.isfinite(relative)):
        raise ValueError('Airflow at the velocity reference is not finite.')
    u, v, w = relative
    longitudinal = math.hypot(u, w)
    speed = math.hypot(longitudinal, v)
    # Exact cancellation and cos(90 degrees) leave roundoff-sized components.
    # Such components cannot define a reliable flow direction. Retain the
    # computed vector/magnitude, but do not manufacture angles from roundoff.
    threshold = 32*np.finfo(float).eps*max(math.hypot(*still), math.hypot(*gust_body))
    alpha = math.degrees(math.atan2(w, u)) if longitudinal > threshold else None
    beta = math.degrees(math.atan2(-v, longitudinal)) if speed > threshold else None
    return dict(reference_body=reference.tolist(), reference_earth=earth.tolist(),
                still_air_velocity_body=still.tolist(), gust_velocity_body=gust_body.tolist(),
                gust_velocity_earth=gust_earth.tolist(), relative_velocity_body=relative.tolist(),
                relative_velocity_earth=(rotation@relative).tolist(), speed=speed, alpha=alpha, beta=beta,
                equivalent_airspeed=speed*math.sqrt(air['density']/model.constants[1]),
                dynamic_pressure=.5*air['density']*speed**2,
                definition='Relative air velocity at the fixed body velocity reference: -U_origin - Omega cross r_ref + posed Earth gust. Induced flow and local elastic velocity are excluded.',
                angle_convention='Degrees: alpha=atan2(w,u), beta=atan2(-v,hypot(u,w)); undefined or roundoff-sized directions are null.')


def reference_airflow_constraints(speed, alpha, beta):
    """Use the supplied values as true local airspeed and flow-angle targets."""
    from .operating import OperatingConstraint
    for name, value in zip(('speed', 'alpha', 'beta'), (speed, alpha, beta)):
        validate_reference_target('reference.'+name, value)
    return [OperatingConstraint(name, 'reference.'+name, value)
            for name, value in zip(('speed', 'alpha', 'beta'), (speed, alpha, beta))]
