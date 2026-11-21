"""Constitutive interval estimates and one-sided sections for the source law.

The arithmetic average of endpoint transforms is generally nonorthogonal.
Keep it distinct from the physical frame used to draw an interval. Endpoint
sections use their actual frames and sided input properties. With material
damping, only the interval strain rate is defined: endpoint mechanical strains
remain unavailable and sensors explicitly use the adjacent interval estimate.
"""
import numpy as np
from .asw import AswError
from .recovery import recover_section


def source_damping_elements(network):
    """A material property flag, independent of whether this snapshot has rates.

    A damped zero-rate base must expose the same output locations as its modal
    perturbations. Static policies and a dynamic policy with zero damping keep
    their existing endpoint recovery exactly.
    """
    if not getattr(network, 'source_dynamic', False):
        return np.zeros(network.ne, dtype=bool)
    return np.any(np.asarray(network.damping_times) != 0, axis=1)


def source_static_distributed_gravity(network, data):
    """Static part of f_reac: interval gravity force per material length.

    Static source policies put only distributed gravity in element_forces.
    Concentrated weights/support reactions are separate nodal loads. Other
    policies can mix aerodynamic and inertial loads into these arrays, so this
    recovery deliberately leaves those analyses unavailable rather than
    mislabeling their total distributed force as gravity.

    Steady Eq.78 supplies the force. Its projection uses the physical normal,
    not the nonorthogonal Eq.50 transform used by the constitutive equations.
    """
    if (network.structural_operator not in ('drela-steady-zero-offset-v1', 'drela-steady-section-v1')
            or getattr(network, 'source_dynamic', False) or data.get('condition') is not None):
        return None
    lengths = np.concatenate([mesh.length for mesh in network.meshes])
    forces = np.asarray(data['element_forces'])
    frames = np.asarray(data['section_frame'])
    if (forces.shape != (len(lengths), 2, 3) or frames.shape != (len(lengths), 3, 3)
            or not np.all(np.isfinite(lengths)) or np.any(lengths <= 0)
            or not np.all(np.isfinite(forces)) or not np.all(np.isfinite(frames))):
        raise ValueError('Static gravity recovery requires finite interval forces, frames and positive material lengths.')
    normals = frames[:, :, 2]
    if np.any(abs(np.sum(normals*normals, axis=1)-1) > 1e-10):
        raise ValueError('Static gravity recovery requires unit physical section normals.')
    density = np.sum(forces, axis=1)/lengths[:, None]
    normal = np.einsum('ij,ij->i', density, normals)
    return [dict(force_per_length=f.tolist(), normal=float(n),
                 sample_location='interval mean load; physical midpoint normal')
            for f, n in zip(density, normal)]


def recover_source_structure(network, data, *, sensor_traces_only=False):
    source = data['source_discrete']
    damping = source_damping_elements(network)
    gravity = source_static_distributed_gravity(network, data)
    pa, pb, ra, rb, *_ = network.geometry(data['r'], data['Q'])
    elements = []
    sensor_nodes = {(int(row[1]), network.node(*row[1:3]))
                    for row in network.model.records.get('sensor', [])} if sensor_traces_only else None
    for mesh in network.meshes:
        beam = mesh.beam
        endpoints = []
        for t, side in ((mesh.t0, 'right'), (mesh.t1, 'left')):
            endpoints.append({name: beam.value(name, t, side=side)
                              for name in ('Cshell', 'Nshell', 'Atshell')})
        for i, j in enumerate(range(network.beam_elements[beam.index].start, network.beam_elements[beam.index].stop)):
            shell = {arg: float((endpoints[0][name][i]+endpoints[1][name][i])/2)
                     if name in beam.distributions or name == 'Atshell' else None
                     for arg, name in (('cshell', 'Cshell'), ('nshell', 'Nshell'), ('atshell', 'Atshell'))}
            translation = (source['translation_strain'][j] if 'translation_strain' in source
                           else [0., source['axial_strain'][j], 0.])
            strain = np.r_[translation, source['curvature_change'][j]]
            state = recover_section(network.source_sections[j], source['force_local'][j],
                                    source['moment_local'][j], mechanical_strain=strain, **shell)
            if damping[j]:
                state['strain_source'] = 'source_discrete_damped_constitutive'
                state['shell']['stress_source'] = 'total_section_resultant'
            traces = []
            for end, side, t, sign, node, position, frame in (
                    (0, 'right', mesh.t0[i], 1, network.a[j], pa[j], ra[j]),
                    (1, 'left', mesh.t1[i], -1, network.b[j], pb[j], rb[j])):
                # Linear outputs differentiate interval values and sensor
                # measurements. Full snapshots still export every trace.
                if sensor_nodes is not None and (beam.index, node) not in sensor_nodes:
                    continue
                force = data['N'][j]+sign*data['element_forces'][j, end]
                moment = data['M'][j]+sign*np.cross(pb[j]-pa[j], data['N'][j])/2
                moment += np.cross(position-data['r'][node], data['N'][j])+sign*data['element_moments'][j, end]
                section = network.source_endpoint_sections[j][end]
                endpoint = recover_section(section, frame.T@force, frame.T@moment,
                    mechanical_strain=np.zeros(6) if damping[j] else None,
                    cshell=float(endpoints[end]['Cshell'][i]) if 'Cshell' in beam.distributions else None,
                    nshell=float(endpoints[end]['Nshell'][i]) if 'Nshell' in beam.distributions else None,
                    atshell=float(endpoints[end]['Atshell'][i]))
                if damping[j]:
                    # Do not turn total elastic-plus-viscous resultants into
                    # fictitious elastic strain by applying static compliance.
                    # The source operator supplies no unique nodal strain rate.
                    endpoint.update(strain=None, curvature_change=None, axial_strain_tension=None,
                        strain_source='unavailable_endpoint_material_rate',
                        strain_unavailable_reason='Only the source interval material rate is defined; no endpoint rate interpolation is prescribed.')
                    endpoint['shell'].update(strain_available=False, axial_strain=None,
                        axial_strain_bound=None, stress_source='total_section_resultant')
                traces.append(dict(side=side, node=int(node), t=float(t), position=position.tolist(),
                    frame=frame.tolist(), force=force.tolist(), moment=moment.tolist(), **endpoint))
            physical = data['section_frame'][j].tolist()
            elements.append(dict(beam=beam.index, t=float(mesh.ts[i]), t0=float(mesh.t0[i]), t1=float(mesh.t1[i]),
                length=float(mesh.length[i]), position=((pa[j]+pb[j])/2).tolist(),
                frame=physical, physical_midpoint_frame=physical,
                frame_role='geometric display only; use transform_average for constitutive components',
                transform_average=source['transform_average'][j].tolist(),
                sample_location='element constitutive average',
                force=data['N'][j].tolist(), moment=data['M'][j].tolist(), endpoint_traces=traces,
                **({'distributed_gravity': gravity[j]} if gravity is not None else {}), **state))

    def peak(key):
        candidates = [(e, e, 'element constitutive average') for e in elements]
        candidates += [(e, trace, 'endpoint '+trace['side']) for e in elements for trace in e['endpoint_traces']]
        candidates = [(e, s, location) for e, s, location in candidates if s['shell'][key] is not None]
        if not candidates:
            return None
        e, s, location = max(candidates, key=lambda v: abs(v[1]['shell'][key]))
        return dict(beam=e['beam'], t=s['t'], value=s['shell'][key], sample_location=location)

    try:
        scales = network.model.units.si_scales()
        stress_to_pa = scales['F']/scales['L']**2
    except AswError:
        stress_to_pa = None
    metadata = dict(sample_location='element constitutive average; t is its material-midpoint plot coordinate',
        local_axes=['c', 's', 'n'], strain_source='source_discrete_constitutive', shell_reference='tension axis',
        structural_operator=network.structural_operator,
        shell_sampling='Inward endpoint properties averaged before interval strain/stress recovery; endpoint_traces use exact sided properties.',
        peak_sampling='Interval estimates and both endpoint traces; no extrapolation through load or property jumps.',
        units=dict(force='input F', moment='input F L', strain='dimensionless', curvature_change='rad / input L',
                   shear_stress='input F / L^2', stress_to_pa=stress_to_pa),
        summary=dict(max_abs_shell_strain=peak('axial_strain'), max_shell_strain_bound=peak('axial_strain_bound'),
                     max_abs_shear_stress=peak('shear_stress'),
                     strain_sections=sum(e['shell']['strain_available'] for e in elements),
                     stress_sections=sum(e['shell']['shear_stress'] is not None for e in elements),
                     invalid_stress_sections=sum(e['shell']['area_thickness'] < 0 for e in elements)),
        limitations=[
            'Interval local components use the arithmetic endpoint transform average, not the orthonormal physical midpoint display frame.',
            'Interval strain follows the selected averaged stiffness/force law. Averaged shell properties give a constitutive interval estimate, not a point sample or an average of endpoint stress.',
            'Endpoint strains use one-sided section properties and conservative endpoint resultants. Both sides of load/property jumps remain distinct.',
            'Shell coordinates are measured from the tension axis per steady Eq.28. Exact historical ASWING output sampling remains unverified.',
            ('Closed-shell torsional shear uses translated Mprime_s/(2*Atshell). Missing shell arms or nonpositive area leave unavailable values null; strength, warping and transverse-shear stresses are not inferred.'
             if 'translation_strain' in source else
             'Closed-shell torsional shear uses Ms/(2*Atshell). Missing shell arms or nonpositive area leave unavailable values null; strength, warping and transverse-shear stresses are not inferred.')
        ])
    if gravity is not None:
        metadata['units']['distributed_load'] = 'input F / input L'
        metadata['distributed_gravity'] = dict(
            available=True, quantity='static distributed gravity contribution to f_reac',
            sample_location='interval mean force per undeformed material length, projected onto the physical midpoint n axis',
            includes='Distributed mg and Dmg at the actual applied gravity, including signed static bench loads.',
            excludes='Concentrated weights, support reactions, aerodynamic, acceleration and apparent-mass loads.',
            native_export='Physical intervals only; duplicate-station and terminal ASWING display rows are not reconstructed.')
    if np.any(damping):
        metadata.update(strain_source='source_discrete_damped_constitutive',
            shell_sampling='Damped interval mechanical strains use corrected source constitutive arrays and averaged shell properties. Endpoint resultants and total-torque shell stress retain exact sided properties; endpoint mechanical strains are unavailable on damped intervals.',
            peak_sampling='Mechanical strain peaks use interval estimates and any undamped endpoint traces. Total-torque shear stress retains all interval and endpoint samples; no extrapolation through jumps.')
        metadata['limitations'][1] = ('Damped interval mechanical strain is the selected source compliance response to total loads minus its material-rate contribution. It is a constitutive interval estimate, not a point sample or endpoint stress average.')
        metadata['limitations'][2] = ('A damped interval has no prescribed endpoint material-rate interpolation. Its endpoint mechanical strain and shell axial strain are null; total endpoint force/moment and translated-torque shell shear stress remain available. Undamped intervals retain one-sided compliance recovery.')
    return elements, metadata
