"""All current circulation-rate matrix columns from independent load equations.

Equation 49 sets the circulation-row coefficient. Equations 35--36 set
the rate lift and quarter-chord couple. The steady profile-drag term also
depends on the lagged tangency defect, so its derivative is retained. All
other matrix entries must be zero for these circulation-rate inputs.
"""
import argparse
from pathlib import Path
from check_daedalus_load_sensitivity import ROOT, SOURCE, read
from check_daedalus_circulation_phase import STUDY, restore, REFERENCE
from daedalus_bounded_job import run


def analyze(folder, args):
    import numpy as np
    import scipy.sparse as sp
    from daedalus_source_aero_reference import FullAeroReference, sample_beam, norm, softplus
    source = STUDY/'capture-base'
    packet = restore(source/'base.pkl'); fixture = packet['fixture']
    ref = FullAeroReference(fixture, packet['packet'], quadrature=32)
    values = ref.evaluate(ref.base)
    layout = read(SOURCE/'mass-6.7/layout.json')
    nn, ne = layout['nodes'], layout['elements']; ng = layout['circulation']['width']
    start = layout['circulation']['start']; operating = layout['operating']['start']
    indices = np.arange(start, start+ng)
    mass = sp.load_npz(SOURCE/'assembled-6.7/M.npz'); expected = np.zeros((mass.shape[0], ng))
    scale = layout['circulation']['scale']; force_scale = layout['internal_loads']['force_scale']
    moment_scale = layout['internal_loads']['moment_scale']
    assert scale == fixture['scales']['Gamma_scale'] and len(ref.base['gamma']) == ng
    assert ref.condition['aero_lag'] and not ref.condition['circulation_modes']
    sections = [sample_beam(b, ref.base, fixture['ends']) for b in ref.lifting]
    fields = {key:np.concatenate([s[key] for s in sections]) for key in ('rm','r0','r1','Rm','ds')}
    ends = np.concatenate([fixture['ends'][b['element_ids']] for b in ref.lifting])
    chord = ref.material['chord']; span = fields['Rm'][:,:,1]; caxis = fields['Rm'][:,:,0]
    velocity = values['lifting_velocity']; vp = velocity-(velocity*span).sum(axis=1)[:,None]*span
    speed = norm(vp); free = norm(-ref.base['U']-np.cross(ref.base['Omega'],ref.reference[3]))
    lag = 2/np.pi; rho = ref.rho; cl = values['lifting_cl']; width = ref.condition['stall_width']
    limits = {k:np.concatenate([b['material_receiver'][k] for b in ref.lifting]) for k in ('CLmin','CLmax')}
    leakage = width*(softplus((cl-limits['CLmax'])/width)-softplus((limits['CLmin']-cl)/width))
    leakage = speed/ref.material['CLa']*ref.condition['stall_factor']*leakage if ref.condition['stall'] else np.zeros(ng)
    tangency = free*values['circulation_local_residual']+leakage
    # A zero-rate base makes coefficient derivatives times Gamma_dot vanish.
    rate_force = (rho*chord*scale/speed*fields['ds'])[:,None]*np.cross(velocity,span)
    profile_force = (-4*rho*chord*lag*scale*tangency/speed**2*fields['ds'])[:,None]*vp
    forces = rate_force+profile_force
    midpoint = (fields['r0']+fields['r1'])/2
    quarter_arm = ((.25-ref.material['Xax'])*chord)[:,None]*caxis
    # Distributed profile force is at midpoint; rate lift is at rm+quarter_arm.
    nodal_couple = np.cross(fields['rm']+quarter_arm-midpoint, rate_force)
    nodes = ref.base['r']; origin = ref.reference[1]
    expected[indices,np.arange(ng)] = lag*scale/(speed*free)
    nodal_force = np.zeros((nn,3,ng)); nodal_moment = np.zeros_like(nodal_force)
    for j,(a,b) in enumerate(ends):
        for node in (a,b):
            nodal_force[node,:,j] += forces[j]/2
            nodal_moment[node,:,j] += nodal_couple[j]/2
    # M=-dR/dzdot in the saved descriptor convention.
    expected[6*ne:6*ne+3*nn] = -nodal_force.reshape(3*nn,ng)/force_scale
    expected[6*ne+3*nn:6*(ne+nn)] = -nodal_moment.reshape(3*nn,ng)/moment_scale
    total_force = nodal_force.sum(axis=0)
    total_moment = nodal_moment.sum(axis=0)+np.cross((nodes-origin)[None,:,:],nodal_force.transpose(2,0,1)).sum(axis=1).T
    expected[operating:operating+6] = -np.vstack([total_force/force_scale,total_moment/moment_scale])
    actual = mass[:,indices].toarray(); difference = abs(actual-expected)
    gate = 2e-8+2e-8*abs(expected)
    np.savez_compressed(folder/'arrays.npz', expected_mass=expected, actual_mass=actual,
        rate_force=rate_force, profile_force=profile_force, normal_speed=speed, chord=chord,
        circulation_indices=indices, tangency=tangency,
        beam=np.concatenate([np.full(len(b['element_ids']),b['index']) for b in ref.lifting]))
    assert np.all(difference <= gate), (float(difference.max()),np.unravel_index(difference.argmax(),difference.shape))
    blocks = {'circulation':indices,'node_force':np.arange(6*ne,6*ne+3*nn),
              'node_moment':np.arange(6*ne+3*nn,6*(ne+nn)),
              'global_force_moment':np.arange(operating,operating+6)}
    checked = np.concatenate(list(blocks.values())); unused = np.setdiff1d(np.arange(len(expected)),checked)
    blocks['all_other_rows'] = unused
    errors = {key:float(np.max(difference[rows],initial=0)) for key,rows in blocks.items()}
    # A useful physical scale, not the exact finite-wing transfer function.
    wing = slice(0,len(ref.lifting[0]['element_ids'])); reduced = {}
    for frequency in (.2,1.15737773741517):
        k = np.pi*frequency*chord[wing]/speed[wing]
        implied = (1+2j*k)/(1+4j*k)
        reduced[str(frequency)] = dict(k_range=[float(k.min()),float(k.max())],
            locally_2d_lag_magnitude_range=[float(abs(implied).min()),float(abs(implied).max())],
            locally_2d_lag_phase_degrees_range=[float(np.angle(implied,deg=True).min()),float(np.angle(implied,deg=True).max())])
    result = dict(columns=ng,entries=int(expected.size),max_absolute_error=float(difference.max()),
        max_gate_ratio=float(np.max(difference/gate)),block_errors=errors,
        maximum_profile_rate_force_column=float(abs(profile_force).max()),reduced_frequency= reduced,
        qualification='Independent Eq49 and Eq35-36 rate/load construction on supplied parsed material and loaded geometry. Every saved M column associated with circulation rates is checked. The displayed Eq56 local 2D approximation is not an exact finite-wing or coupled-aircraft transfer function.')
    print(result,flush=True)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--tag',required=True)
    args=vars(parser.parse_args())
    inputs=[ROOT/'scripts/check_daedalus_circulation_phase.py',SOURCE/'mass-6.7/layout.json',
            SOURCE/'assembled-6.7/M.npz',STUDY/'capture-base/base.pkl',
            STUDY/'capture-base/plan.json',STUDY/'capture-base/terminal.json',
            ROOT/'reference/aswing-authoritative-20261108/drela-aswing-unsteady.pdf',
            ROOT/'reference/aswing-authoritative-20261108/drela-aswing-steady.pdf']
    inputs += [ROOT/'scripts'/name for name in REFERENCE]
    run(STUDY,args['tag'],inputs,analyze,args,__file__)


if __name__=='__main__':main()
