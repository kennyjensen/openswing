"""Section loads, mechanical strains and closed-shell stress after equilibrium.

Steady theory (18–20), (28–29), and §8.2. Shell coordinates are measured from
the tension axis, as defined by the theory (the user-guide labels disagree).
No elastic modulus, section strength or complete shell shape is implied.
"""
import numpy as np
from .asw import AswError
from .structure import Section


def recover_section(section: Section, force, moment, *, cshell=None, nshell=None, atshell=0., mechanical_strain=None):
    """Inputs are resultants in the current local c,s,n frame, about the s axis.

    A missing shell coordinate defaults to zero if the other is supplied. If
    both are absent the material-point strain is unknown. A nonpositive area ×
    thickness leaves stress unknown, even at zero torque; negative is invalid.
    """
    force, moment = np.asarray(force, dtype=float), np.asarray(moment, dtype=float)
    if force.shape != (3,) or moment.shape != (3,) or not np.all(np.isfinite([force, moment])):
        raise ValueError('Section resultants must be finite local three-vectors.')
    if not all(np.isfinite(v) for v in (cshell, nshell, atshell) if v is not None):
        raise ValueError('Shell parameters must be finite.')
    response = section.compliance() @ np.r_[force, moment] if mechanical_strain is None else np.asarray(mechanical_strain,dtype=float)
    if response.shape!=(6,) or not np.all(np.isfinite(response)):
        raise ValueError('Mechanical strain must be a finite six-vector.')
    translated = moment + [section.Nta*force[1], -section.Nea*force[0]+section.Cea*force[2], -section.Cta*force[1]]
    axial = float(force[1]/section.EA) if mechanical_strain is None else float(response[1]-section.Nta*response[3]+section.Cta*response[5])
    c, n = 0. if cshell is None else cshell, 0. if nshell is None else nshell
    defined = cshell is not None or nshell is not None
    bending = np.array([c*response[5], -n*response[3]])
    strain = float(axial+bending.sum()) if defined else None
    bound = float(abs(axial)+abs(bending).sum()) if defined else None
    stress = float(translated[1]/(2*atshell)) if atshell > 0 else None
    return dict(force_local=force.tolist(), moment_local=moment.tolist(), moment_axes=translated.tolist(),
                strain=response[:3].tolist(), curvature_change=response[3:].tolist(),
                axial_strain_tension=axial,
                shell=dict(c=float(c), n=float(n), area_thickness=float(atshell),
                           strain_available=defined, axial_strain=strain, axial_strain_bound=bound,
                           shear_stress=stress, shear_stress_abs=None if stress is None else abs(stress),
                           shear_status='available' if atshell > 0 else 'missing' if atshell == 0 else 'invalid_negative_area_thickness'))


def recover_structure(network, data, *, sensor_traces_only=False):
    """Recover at each constitutive/material midpoint, using the residual's frame.

    Midpoint values do not resolve load jumps or endpoint extrema; report that
    explicitly instead of extrapolating across a concentrated load or joint.
    """
    if 'source_discrete' in data:
        from .source_recovery import recover_source_structure
        return recover_source_structure(network, data, sensor_traces_only=sensor_traces_only)
    frame = data['section_frame']
    force = np.einsum('nji,nj->ni', frame, data['N'])
    moment = np.einsum('nji,nj->ni', frame, data['M'])
    pa, pb = network.geometry(data['r'],data['Q'])[:2]
    elements = []
    for mesh in network.meshes:
        beam = mesh.beam
        values = {name:beam.value(name,mesh.ts) for name in ('Cshell','Nshell','Atshell')}
        for k,j in enumerate(range(network.beam_elements[beam.index].start,network.beam_elements[beam.index].stop)):
            state = recover_section(network.sections[j],force[j],moment[j],
                                    mechanical_strain=None if data.get('mechanical_strain') is None else data['mechanical_strain'][j],
                                    cshell=float(values['Cshell'][k]) if 'Cshell' in beam.distributions else None,
                                    nshell=float(values['Nshell'][k]) if 'Nshell' in beam.distributions else None,
                                    atshell=float(values['Atshell'][k]))
            elements.append(dict(beam=beam.index,t=float(mesh.ts[k]),t0=float(mesh.t0[k]),t1=float(mesh.t1[k]),
                                 length=float(mesh.length[k]),position=((pa[j]+pb[j])/2).tolist(),
                                 frame=frame[j].tolist(),force=data['N'][j].tolist(),moment=data['M'][j].tolist(),**state))
    def peak(key):
        valid = [e for e in elements if e['shell'][key] is not None]
        if not valid: return None
        e = max(valid,key=lambda e:abs(e['shell'][key]))
        return dict(beam=e['beam'],t=e['t'],value=e['shell'][key])
    try:
        scales = network.model.units.si_scales()
        stress_to_pa = scales['F']/scales['L']**2
    except AswError:
        stress_to_pa = None
    metadata = dict(sample_location='material midpoint',local_axes=['c','s','n'],
                    strain_source='elastic_load_compliance' if data.get('mechanical_strain') is None else 'current_geometry',
                    shell_reference='tension axis',
                    units=dict(force='input F',moment='input F L',strain='dimensionless',
                               curvature_change='rad / input L',shear_stress='input F / L^2',stress_to_pa=stress_to_pa),
                    summary=dict(max_abs_shell_strain=peak('axial_strain'),max_shell_strain_bound=peak('axial_strain_bound'),
                                 max_abs_shear_stress=peak('shear_stress'),
                                 strain_sections=sum(e['shell']['strain_available'] for e in elements),
                                 stress_sections=sum(e['shell']['shear_stress'] is not None for e in elements),
                                 invalid_stress_sections=sum(e['shell']['area_thickness'] < 0 for e in elements)),
                    limitations=[
                        'Strain uses load-induced curvature relative to the jig; positive axial strain is tension.',
                        'Cshell/Nshell are offsets from the tension axis per steady eq. 28; the user guide labels them relative to the elastic axis. Executable parity is unverified.',
                        'The strain bound sums absolute axial and bending contributions. It bounds the specified rectangular extents, not an unspecified complete cross section.',
                        'Torsional shear stress assumes a thin, closed, uniform shell: torque about the elastic axis divided by twice Atshell. Transverse-shear stress, warping, normal stress and strength margins are not inferred.',
                        'Missing shell arms or nonpositive Atshell produce null material results. Negative Atshell is invalid; shell parameters do not change equilibrium.',
                        'These are element midpoint samples. Peaks at endpoints, joints and concentrated loads require local refinement; no interpolation across jumps is implied.'])
    if data.get('mechanical_strain') is not None:
        metadata['limitations'][0]='Mechanical strain is recovered from current geometry; total section loads include material damping and do not alone determine strain.'
    return elements, metadata
