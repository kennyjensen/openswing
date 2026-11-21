"""ASW engine types 0/1/2 and momentum-conserving propulsive jets.

Steady eqs. 106–139 and unsteady eqs. 231, 234, 241, 244, 254–255.
All dimensional values are in the file's consistent input units. Engine Omega
is positive about the specified thrust direction; mount rates use body axes.
"""
import numpy as np
from scipy.optimize import brentq


def engine_axes(thrust, rotation=None):
    thrust = np.asarray(thrust, dtype=float)
    xe = -thrust/np.linalg.norm(thrust) if np.any(thrust) else np.array([1., 0., 0.])
    # The transverse orientation is arbitrary for the axisymmetric model.
    reference = np.array([0., 0., 1.]) if abs(xe[2]) < .9 else np.array([0., 1., 0.])
    ye = np.cross(reference, xe); ye /= np.linalg.norm(ye)
    axes = np.column_stack([xe, ye, np.cross(xe, ye)])
    return axes if rotation is None else rotation@axes


def validate_engines(model, powers):
    keys = {int(r[0]) for r in model.records.get("engine", [])}
    if any(k not in keys or not np.isfinite(v) for k, v in powers.items()):
        raise ValueError("Engine settings must have declared indices and finite values.")
    for row in model.records.get("engine", []):
        if int(row[0]) <= 0 or int(row[1]) not in (0, 1, 2):
            raise ValueError("Engine needs a positive control index and model type 0, 1 or 2.")
        if row[14] < 0:
            raise ValueError("Engine blade drag area must be nonnegative.")
        if int(row[1]) in (1, 2) and (row[12] == 0 or row[13] == 0):
            raise ValueError("Actuator-disk engines require nonzero Rdisk and Omega.")


def actuator_disk(power, density, velocity, radius, omega, drag_area):
    """Forward-flow physical branch, including hover and windmilling.

The swirl-loss cubic's actual minimum replaces the ideal Betz clipping value
when swirl is finite. Selecting its monotone branch avoids spurious cubic roots.
"""
    if velocity < 0:
        raise ValueError("Actuator-disk reverse flow is outside the documented forward-flow model.")
    radius = abs(radius)
    if radius <= 0 or omega == 0 or density <= 0 or drag_area < 0:
        raise ValueError("Invalid actuator-disk radius, rotation rate, density or blade drag area.")
    area = np.pi*radius**2
    tip = abs(omega)*radius
    viscous = density/8*np.sqrt(velocity**2+tip**2)*(velocity**2+3*tip**2)*drag_area
    swirl = 1+5*(velocity/tip)**2
    def inviscid(dv):
        return density*area*(velocity+swirl*dv/2)*(velocity+dv/2)*dv
    # Stable root of d(Pi)/d(dv)=0 nearest dv=0. For swirl=1: -2V/3.
    minimum_dv = -2*velocity/(1+swirl+np.sqrt((1+swirl)**2-3*swirl))
    minimum_power = inviscid(minimum_dv)
    requested = power-viscous
    used = max(requested, minimum_power)
    if used == minimum_power:
        dv = minimum_dv
    elif used == 0:
        dv = 0.
    else:
        upper = max(velocity, (4*abs(used)/(density*area*swirl))**(1/3), 1.)
        while inviscid(upper) < used:
            upper *= 2
        dv = brentq(lambda d: inviscid(d)-used, minimum_dv, upper, xtol=1e-12, rtol=1e-14)
    thrust = density*area*(velocity+dv/2)*dv
    return dict(thrust=float(thrust), torque=float(-power/omega), delta_velocity=float(dv),
                viscous_power=float(viscous), inviscid_power=float(used), requested_power=float(power),
                power_clipped=bool(requested < minimum_power), minimum_power=float(minimum_power))


def engine_load(row, power, density, position, velocity, mount_rate=(0., 0., 0.), rotation=None):
    typ = int(row[1])
    axes = engine_axes(row[7:10], rotation)
    local_v, local_w = axes.T@velocity, axes.T@np.asarray(mount_rate)
    radius, omega = abs(float(row[12])), float(row[13])
    axial = float(local_v[0])
    if typ == 0:
        thrust, torque = float(row[10]*power), float(row[11]*power)
        dv = 0.
        if row[12] > 0:
            if axial < 0 or axial**2+2*thrust/(density*np.pi*radius**2) < 0:
                raise ValueError("Proportional-engine jet has no forward-flow momentum solution; check thrust and Rdisk.")
            # Rationalized quadratic avoids cancellation at small thrust.
            denominator = np.sqrt(axial**2+2*thrust/(density*np.pi*radius**2))+axial
            dv = 2*thrust/(density*np.pi*radius**2)/denominator if denominator else 0.
        state = dict(thrust=thrust, torque=torque, delta_velocity=float(dv),
                     viscous_power=None, inviscid_power=None, requested_power=float(power),
                     power_clipped=False, minimum_power=None)
    else:
        state = actuator_disk(power, density, axial, radius, omega, float(row[14]))
    force = np.array([-state["thrust"], 0., 0.])
    moment = np.array([-state["torque"], 0., 0.])
    if typ == 2:
        cl, cla, s0, c0, s1, c1, s2, c2, s3, c3 = row[15:25]
        vd, tip = axial+state["delta_velocity"]/2, abs(omega)*radius
        fv = density*radius**2/4*((cla*s0-cl*c0)*vd+2*cl*s1*tip)
        mv = -density*radius**3/4*((cla*c1+cl*s1)*vd+2*cl*c2*tip)
        fw = density*radius**3/4*((cla*s2-cl*c2)*tip-2*cl*s1*vd)
        mw = -density*radius**4/4*((cla*c3+cl*s3)*tip-2*cl*c2*vd)
        spin_sign = -np.sign(omega)  # unsteady eq. 253 uses the opposite x_e axis
        force[1:] = fv*local_v[1:]+spin_sign*fw*local_w[1:]
        moment[1:] = spin_sign*mv*local_v[1:]+mw*local_w[1:]
    state.update(index=int(row[0]), type=typ, beam=int(row[2]), t=float(row[3]),
                 position=np.asarray(position), axes=axes, force=axes@force, moment=axes@moment,
                 axial_velocity=axial, radius=radius, jet_enabled=bool(row[12] > 0))
    return state


def jet_profile(engine, downstream, density):
    """Inner/outer radius and centerline axial/swirl velocities at a wake station."""
    v, dv, radius = engine["axial_velocity"], engine["delta_velocity"], engine["radius"]
    x = np.maximum(np.asarray(downstream, dtype=float), 0.)
    if v+dv <= 0:
        if v == dv == 0 and engine["thrust"] == engine["torque"] == 0:
            return np.full_like(x, radius), np.full_like(x, radius), np.zeros_like(x), np.zeros_like(x)
        raise ValueError("Engine jet requires positive downstream convection velocity.")
    contracted = radius*np.sqrt((v+dv/2)/(v+dv))
    inner = np.maximum(0., contracted-.11*abs(dv)/(v+dv)*x)
    outer = contracted+.11*abs(dv)/(v+dv/2)*x
    d = outer-inner
    k1 = inner**2+9/10*inner*d+9/35*d**2
    k2 = inner**2+243/385*inner*d+243/1820*d**2
    discriminant = (k1*v)**2+4*k2*engine["thrust"]/(np.pi*density)
    if np.any(discriminant < -1e-12*np.maximum((k1*v)**2, 1.)):
        raise ValueError("Engine wake has no real momentum-conserving velocity profile.")
    denominator = k1*v+np.sqrt(np.maximum(discriminant, 0.))
    center = np.divide(2*engine["thrust"]/(np.pi*density), denominator,
                       out=np.zeros_like(x), where=denominator != 0)
    # Exact integrals 2∫r² q(r)dr and 2∫r² q(r)²dr. Printed eq. 138 omits
    # a factor two in the inner*d² terms; verify these by independent quadrature.
    k3 = 2/3*inner**3+9/10*inner**2*d+18/35*inner*d**2+1/9*d**3
    k4 = 2/3*inner**3+243/385*inner**2*d+243/910*inner*d**2+2/45*d**3
    transport = np.pi*density*(k3*v+k4*center)
    swirl = np.divide(-engine["torque"], transport, out=np.zeros_like(x), where=transport != 0)
    if engine["torque"] != 0 and np.any(transport == 0):
        raise ValueError("Engine jet cannot carry nonzero torque with zero convection.")
    return inner, outer, center, swirl


def jet_velocity(points, engines, direction, density):
    points = np.asarray(points, dtype=float)
    velocity = np.zeros_like(points)
    for engine in engines:
        if not engine["jet_enabled"]:
            continue
        # An unloaded disk has an identically zero wake. This exact branch
        # avoids rebuilding its zero profile for each geometry derivative;
        # arbitrarily small nonzero thrust/torque still follows the full model.
        # Retain the original rejection of invalid reverse convection.
        if (engine["thrust"] == engine["torque"] == engine["delta_velocity"] == 0
                and engine["axial_velocity"] >= 0):
            continue
        relative = points-engine["position"]
        downstream = relative@direction
        radial = relative-downstream[..., None]*direction
        distance = np.linalg.norm(radial, axis=-1)
        inner, outer, axial, swirl = jet_profile(engine, downstream, density)
        width = outer-inner
        fraction = np.divide(distance-inner, width, out=np.zeros_like(distance), where=width > 0)
        shape = (1-np.clip(fraction, 0., 1.)**1.5)**2
        shape = np.where((downstream > 0) & (distance < outer), shape, 0.)
        radial_unit = np.divide(radial, distance[..., None], out=np.zeros_like(radial), where=distance[..., None] > 0)
        # The centerline follows the vortex-wake direction (x in fast mode),
        # but the velocity increment follows the thrust axis. Engines do not see jets.
        velocity += shape[..., None]*(axial[..., None]*engine["axes"][:, 0]
                                      + swirl[..., None]*np.cross(radial_unit, engine["axes"][:, 0]))
    return velocity


def engine_report(engine):
    return {k: v.tolist() if isinstance(v, np.ndarray) else v for k, v in engine.items()}
