"""Wind-normal straight-wake forces and induced drag.

ASWING steady formulation §8.1 defines the reported coefficients. The signed
kinetic-energy integral is explicit in Drela's JVL formulation (2024), eqs.
124–127: D = -rho/2 sum(Gamma * v_wake dot (wind cross delta_r)).
The pointwise circulation is sampled at each element's Glauert-angle midpoint.
"""
import numpy as np


class WakeIntersection(ValueError):
    pass


def wake_velocity(points, start, end, circulation, wind):
    """Velocity of infinite trailing vortex pairs; no bound or core terms.

    A sampling point on a nonzero net filament is unresolved, not a zero
    principal-value velocity. Coincident equal/opposite filaments cancel.
    """
    points, start, end = (np.asarray(a, dtype=float).reshape(-1, 3) for a in (points, start, end))
    circulation, wind = np.asarray(circulation, dtype=float), np.asarray(wind, dtype=float)
    if start.shape != end.shape or circulation.shape != (len(start),):
        raise ValueError('Wake circulation must match the endpoint pairs.')
    if wind.shape != (3,) or not np.isclose(np.linalg.norm(wind), 1., rtol=0, atol=1e-12):
        raise ValueError('Wake direction must be a unit xyz vector.')
    if not all(np.all(np.isfinite(a)) for a in (points, start, end, circulation, wind)):
        raise ValueError('Wake geometry and circulation must be finite.')
    if not len(start):
        return np.zeros_like(points)
    endpoints = np.concatenate((start, end))
    strength = np.r_[-circulation, circulation]
    delta = points[:, None, :]-endpoints[None, :, :]
    delta -= (delta@wind)[..., None]*wind
    distance2 = np.sum(delta*delta, axis=-1)
    # Relative geometry tolerance, independent of global coordinate translation.
    scale = max(np.max(np.linalg.norm(end-start, axis=-1)),
                np.max(np.linalg.norm(delta, axis=-1)), np.finfo(float).tiny)
    coincident = distance2 <= (64*np.finfo(float).eps*scale)**2
    net = coincident@strength
    cancellation_scale = coincident@abs(strength)
    if np.any(abs(net) > 64*np.finfo(float).eps*cancellation_scale):
        raise WakeIntersection('A wake sampling point lies on a nonzero trailing filament; refine or change the wake discretization.')
    inverse = np.divide(1., distance2, out=np.zeros_like(distance2), where=~coincident)
    return np.einsum('ijk,ij,j->ik', np.cross(wind, delta), inverse, strength)/(2*np.pi)


def wake_forces(start, end, points, circulation, wind, side, lift, speed, density,
                reference, ground=None):
    """Frozen-wake diagnostic in file units, with explicit unavailable drag."""
    start, end, points = (np.asarray(a, dtype=float).reshape(-1, 3) for a in (start, end, points))
    gamma, wind, side, lift, reference = map(np.asarray, (circulation, wind, side, lift, reference))
    area, _, span = reference[0]
    if speed <= 0 or density <= 0 or area < 0 or span <= 0:
        raise ValueError('Trefftz speed, density and span must be positive; reference area must be nonnegative.')
    if start.shape != end.shape or points.shape != start.shape or gamma.shape != (len(start),):
        raise ValueError('Trefftz endpoints, sampling points and circulation must match.')
    qs = .5*density*speed**2*area
    trace_normal = np.cross(wind, end-start)
    force = density*speed*gamma[:, None]*trace_normal
    total = force.sum(axis=0)
    # The impulse moment of piecewise-constant circulation uses the physical
    # segment centroid, distinct from the theta drag-collocation point.
    roll = float(np.sum(np.cross(.5*(start+end)-reference[1], force)@wind))
    cli, cyi = (float(total@lift/qs), float(total@side/qs)) if area > 0 else (None, None)
    projected = points-reference[1]
    projected -= (projected@wind)[:, None]*wind
    result = dict(available=False, reason=None, CLi=cli, CYi=cyi, CDi=None, efficiency=None,
        coefficients_available=bool(area > 0),
        rolling_moment_wind=roll, Cl=-roll/(qs*span) if area > 0 else None, force_transverse_body=total.tolist(),
        induced_drag=None, velocity_body=None, strip_induced_drag=None,
        trace_points_body=projected.tolist(),
        convention='Frozen straight wake, infinite trailing filaments, theta-midpoint quadrature; D=-rho/2 sum(Gamma v_wake dot (wind cross delta_r)).',
        scope='Lifting-surface circulation only; no body/profile/engine/apparent-mass drag or shed-wake history.',
        efficiency_definition='(CLi^2+CYi^2)/(pi*(Bref^2/Sref)*CDi); zero by reporting convention for an exactly unloaded, nonempty lifting wake.')
    if np.any(gamma) and ground is not None and ground.flag and abs(ground.normal@wind) > 1e-10:
        result['reason'] = 'Trefftz drag requires wind parallel to the image plane; an oblique straight image wake has no common stationary trace.'
        return result
    try:
        if ground is not None and ground.flag:
            # Combine before evaluating to retain cancellation of coincident
            # physical/image filaments. Images supply flow, not extra aircraft.
            velocity = wake_velocity(points, np.concatenate((start, ground.reflect_points(start))),
                np.concatenate((end, ground.reflect_points(end))), np.r_[gamma, -ground.flag*gamma], wind)
        else:
            velocity = wake_velocity(points, start, end, gamma, wind)
    except WakeIntersection as exc:
        result['reason'] = str(exc)
        return result
    strip_drag = -.5*density*gamma*np.sum(velocity*trace_normal, axis=-1)
    drag = float(np.sum(strip_drag))
    result.update(velocity_body=velocity.tolist(), strip_induced_drag=strip_drag.tolist(), induced_drag=drag)
    if drag < -100*np.finfo(float).eps*np.sum(abs(strip_drag)):
        result['reason'] = 'Discrete wake quadrature gives negative total induced drag; refine the intersecting or poorly resolved wake traces.'
        return result
    cdi = drag/qs if area > 0 else None
    if area > 0:
        efficiency = (cli*cli+cyi*cyi)/(np.pi*(span*span/area)*cdi) if cdi > 0 else None
    else:
        # Sref cancels from span efficiency. Keep this defined diagnostic even
        # when the individual area-normalized coefficients are unavailable.
        efficiency = float((total@lift)**2+(total@side)**2)/(np.pi*span**2*(.5*density*speed**2)*drag) if drag > 0 else None
    # The ratio is 0/0 for an unloaded wake. Native ASWING's SA-5 output
    # reports zero there, as does Drela's JVL JTPFORC zero-drag branch.
    # Keep this convention narrower than zero drag: nonzero circulation can
    # cancel against another sheet or an image, and is still undefined here.
    # wake_velocity has already validated finite geometry and circulation.
    if (len(gamma) and not np.any(gamma) and np.all(total == 0) and drag == 0
            and np.all(np.any(trace_normal != 0, axis=1))
            and np.all(np.isfinite(reference))
            and np.all(np.isfinite([speed, density, qs]))):
        efficiency = 0.
    result.update(available=True, CDi=cdi, efficiency=efficiency)
    return result


def trefftz_for_meshes(model, condition, meshes, circulation, density, ground):
    lifting = [m for m in meshes if m.beam.lifting]
    def collect(name):
        return np.concatenate([getattr(m, name) for m in lifting]) if lifting else np.empty((0, 3))
    # Quarter-chord shifts are wind-parallel, so their Trefftz projection equals
    # that of these beam-axis points. PG also leaves transverse distances intact.
    return wake_forces(collect('r0'), collect('r1'), collect('rm'), circulation,
                       *condition.vectors(), condition.speed, density, model.reference, ground)
