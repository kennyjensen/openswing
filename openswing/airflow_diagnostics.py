"""Explain a rejected local flow using one row of existing vortex coefficients.

This observer changes no flow, core, geometry, convergence or validity criterion.
Shared wake strengths are combined before ranking, just as in the evaluator.
Source attribution inspects only the worst receiver; the remaining rejected
locations come from already evaluated fields. No influence matrix is assembled.
"""
import numpy as np


def rejected_surface_forces(parameters, lift, rate, profile, axes, density, speed,
                            reference_area, normal_mach):
    """Retain finite surface-force sums from a rejected state, never its moments.

    These arrays already exist before the local section-moment correction.
    This observer evaluates no additional flow, apparent-mass, body or engine
    loads, and supplies no complete equilibrium or valid aerodynamic result.
    """
    forces = dict(circulatory=np.asarray(lift), circulation_rate=np.asarray(rate),
                  profile=np.asarray(profile))
    directions = np.asarray(axes)  # drag, side, lift unit vectors in body axes
    if not all(np.isfinite(v).all() for v in (*forces.values(), directions)) or not np.isfinite(reference_area):
        return dict(available=False, reason='Surface-force components are nonfinite.')
    with np.errstate(over='ignore', invalid='ignore', divide='ignore'):
        q = .5*density*np.float64(speed)**2
        qs = q*reference_area
        total = forces['circulatory']+forces['circulation_rate']+forces['profile']
        normalize = np.isfinite(qs) and qs > 0

        def record(value):
            drag, side, lifting = directions@value
            return dict(force_body=value.tolist(), lift=float(lifting), drag=float(drag),
                side=float(side), CL=float(lifting/qs) if normalize else None,
                CD=float(drag/qs) if normalize else None,
                CY=float(side/qs) if normalize else None)

        terms = {name:record(value.sum(axis=0)) for name,value in forces.items()}
        terms['sum'] = record(total.sum(axis=0))
        rejected = np.asarray(normal_mach) >= 1
        rejected_sum = record(total[rejected].sum(axis=0))
        beams = [dict(beam=int(beam), strips=int(np.count_nonzero(parameters['beam']==beam)),
            **record(total[parameters['beam']==beam].sum(axis=0)))
            for beam in np.unique(parameters['beam'])]
    records = [*terms.values(), rejected_sum, *beams]
    if not np.isfinite(q) or not all(
            np.isfinite(r['force_body']).all() and all(
                r[k] is None or np.isfinite(r[k]) for k in ('lift','drag','side','CL','CD','CY'))
            for r in records):
        return dict(available=False, reason='Surface-force summation or normalization overflowed.')
    return dict(available=True, validity='rejected-state diagnostic',
        scope='Lifting-surface circulatory, circulation-rate and profile forces only.',
        excluded=['section moments', 'apparent-mass loads', 'body loads',
                  'point-object drag', 'engine loads'],
        force_unit='input F', axes=dict(drag=directions[0].tolist(),
            side=directions[1].tolist(), lift=directions[2].tolist()),
        normalization=dict(dynamic_pressure=float(q), reference_area=float(reference_area),
            coefficients_available=bool(normalize),
            definition='Force / (0.5 * density * flight_speed^2 * Sref)'),
        terms=terms, beams=beams, rejected_strips=int(np.count_nonzero(rejected)),
        rejected_strip_sum=rejected_sum, pitching_moment_available=False)


def rejected_section_airflow(parameters, geometry, velocity, normal_speed, normal_mach):
    """List every rejected receiver using already evaluated fields, worst first.

    No vortex attribution is recomputed. Current force locations and frozen
    influence locations remain distinct, as they are for the worst-row report.
    """
    indices = np.flatnonzero(normal_mach >= 1)
    indices = sorted(indices, key=lambda i: (-normal_mach[i], i))
    return [dict(panel_index=int(i), beam=int(parameters['beam'][i]),
        t=float(parameters['t'][i]), position=parameters['hv'][i].tolist(),
        influence_position=geometry['hv'][i].tolist(),
        relative_velocity=velocity[i].tolist(), normal_speed=float(normal_speed[i]),
        normal_mach=float(normal_mach[i])) for i in indices]


def local_vortex_breakdown(operator, receiver, gamma, parameters, geometry,
                          direction, core, incident, jet, total, *, frozen=False):
    """JSON-ready attribution at one force receiver, in body axes/input units.

    Bound/ray coefficients include the configured PG map and ground images.
    Reported distances are to physical rays, not their optional images.
    Individual large terms may cancel; they are not standalone flow estimates.
    """
    gamma = np.asarray(gamma)
    strengths = operator.wake_strengths(gamma)
    with np.errstate(over='ignore', invalid='ignore'):
        bound = operator.bound[receiver] * gamma[:, None]
        rays = operator.rays[receiver] * strengths[:, None]
    if not all(np.isfinite(x).all() for x in (bound, rays, incident, jet, total)):
        return dict(available=False, reason='Nonfinite velocity components prevent source attribution.')
    bound_sum, wake_sum = bound.sum(axis=0), rays.sum(axis=0)
    reconstructed = np.asarray(incident) + bound_sum + wake_sum + np.asarray(jet)
    receiver_point = geometry['hv'][receiver]
    wind = np.asarray(direction)/np.linalg.norm(direction)
    effective_core = np.where(parameters['physical'][receiver] == geometry['physical'], 0., core)

    def source(index):
        return dict(panel_index=int(index), beam=int(parameters['beam'][index]),
                    strip_t=float(parameters['t'][index]))

    def strongest(terms):
        magnitudes = np.linalg.norm(terms, axis=1)
        nonzero = np.flatnonzero(magnitudes > 0)
        return sorted(nonzero, key=lambda index: (-magnitudes[index], index))[:3], magnitudes

    bound_indices, bound_norms = strongest(bound)
    ray_indices, ray_norms = strongest(rays)
    receiver_ends = np.asarray([geometry['a'][receiver], geometry['b'][receiver]])
    bound_records = []
    for i in bound_indices:
        ends = np.asarray([geometry['a'][i], geometry['b'][i]])
        delta = ends[1]-ends[0]
        length2 = float(delta@delta)
        fraction = float(np.clip((receiver_point-ends[0])@delta/length2, 0., 1.)) if length2 > 0 else 0.
        closest = ends[0]+fraction*delta
        # Report literal geometry, without a tolerance that merges near roots.
        # A geometric turn follows the source into the joint and the receiver
        # out of it, irrespective of either panel's circulation orientation.
        pairs = [(j,k) for j in (0,1) for k in (0,1)
                 if np.array_equal(ends[j], receiver_ends[k])]
        shared = None
        if i != receiver and len(pairs) == 1:
            j,k = pairs[0]
            incoming = ends[j]-ends[1-j]
            outgoing = receiver_ends[1-k]-receiver_ends[k]
            scale = np.linalg.norm(incoming)*np.linalg.norm(outgoing)
            if scale > 0:
                shared = dict(position=ends[j].tolist(),
                    turn_degrees=float(np.rad2deg(np.arccos(np.clip(incoming@outgoing/scale,-1.,1.)))))
        bound_records.append(dict(**source(i), velocity=bound[i].tolist(), speed=float(bound_norms[i]),
            circulation=float(gamma[i]), core_radius=float(effective_core[i]),
            start=ends[0].tolist(), end=ends[1].tolist(),
            physical_bound_distance=float(np.linalg.norm(receiver_point-closest)),
            physical_closest_point=closest.tolist(), shared_bound_endpoint=shared))
    representatives, signs = operator.representative_endpoints()
    ray_records = []
    for group in ray_indices:
        index = representatives[group]
        point = geometry['a' if signs[group] < 0 else 'b'][index]
        relative = receiver_point-point
        along = float(relative@wind)
        distance = float(np.linalg.norm(relative-max(along, 0.)*wind))
        members = [(i, 'a', -1.) for i in np.flatnonzero(operator.starts == group)]
        members += [(i, 'b', 1.) for i in np.flatnonzero(operator.ends == group)]
        members.sort(key=lambda entry: (-abs(gamma[entry[0]]), entry[0], entry[1]))
        ray_records.append(dict(group_index=int(group), origin=point.tolist(),
            velocity=rays[group].tolist(), speed=float(ray_norms[group]),
            net_circulation=float(strengths[group]), core_radius=float(effective_core[index]),
            physical_ray_distance=distance, physical_ray_axial_distance=along,
            source_count=len(members), sources=[dict(**source(i), endpoint=end,
                signed_circulation=float(sign*gamma[i])) for i, end, sign in members[:4]]))
    return dict(available=True, axes='body', speed_unit='input L/T', position_unit='input L',
        influence_geometry='frozen jig' if frozen else 'current',
        influence_receiver=receiver_point.tolist(), direction=wind.tolist(),
        incident_velocity=np.asarray(incident).tolist(), jet_velocity=np.asarray(jet).tolist(),
        bound_velocity=bound_sum.tolist(), wake_velocity=wake_sum.tolist(),
        vortex_velocity=(bound_sum+wake_sum).tolist(), reconstructed_velocity=reconstructed.tolist(),
        reconstruction_error=float(np.linalg.norm(reconstructed-total)),
        bound_sources=bound_records, wake_sources=ray_records,
        wake_groups=len(strengths), zero_strength_wake_groups=int(np.count_nonzero(strengths == 0)),
        scope='Cached coefficients include PG and configured ground images; distances identify physical bound segments and rays, not images. '
              'Shared bound endpoints require exact coordinate equality; their turns describe geometry, not a separate flow estimate. '
              'Largest three nonzero terms of each kind; up to four source endpoints per wake group. '
              'Large terms can cancel and do not independently equal the local flow.')


def breakdown_message(breakdown):
    """Short source context retained even when a client only shows exception text."""
    if not breakdown['available']:
        return ''
    bound, wake = breakdown['bound_sources'], breakdown['wake_sources']
    if not bound and not wake:
        return ' Vortex contribution is zero at this point; inspect the incident flow and jets.'
    if wake and (not bound or wake[0]['speed'] >= bound[0]['speed']):
        item = wake[0]; owner = item['sources'][0]
        return (f" Largest grouped wake contribution: {item['speed']:.7g} (input L/T), "
                f"source strip beam {owner['beam']}, t={owner['strip_t']:.7g}; "
                f"distance to its physical ray={item['physical_ray_distance']:.7g} (input L). "
                'Other vortex terms may partly cancel it.')
    item = bound[0]
    shared = item.get('shared_bound_endpoint')
    location = (f" Distance to its physical bound segment={item['physical_bound_distance']:.7g} (input L)."
                if 'physical_bound_distance' in item else '')
    corner = (f" Shared bound endpoint with a {shared['turn_degrees']:.7g}-degree geometric turn."
              if shared is not None else '')
    return (f" Largest bound-vortex contribution: {item['speed']:.7g} (input L/T), "
            f"source strip beam {item['beam']}, t={item['strip_t']:.7g}."
            + location + corner + ' Other vortex terms may partly cancel it.')
