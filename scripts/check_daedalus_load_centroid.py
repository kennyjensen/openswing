"""Test a structural-midpoint load-centroid interpretation at the yaw dip.

Only spanwise application of lift, circulation-rate and apparent forces changes.
Their aerodynamic sampling and section couples remain unchanged. Constant offsets
hold the original equilibrium. This is a quadrature diagnostic, not a claimed
native ASWING convention or an independently retrimmed physical aircraft.
"""
import argparse
from types import SimpleNamespace
from check_daedalus_load_sensitivity import ROOT, read
from check_daedalus_mesh_zeros import paths, load, factor_at, STUDY as SAMPLES, CHANNELS
from check_daedalus_mesh_residual import accepted, packet
from daedalus_bounded_job import run

STUDY = ROOT/'artifacts/daedalus-load-centroid-20261114'
FREQUENCY = 1.15737773741517
TERMS = [f'beam{beam}:{term}' for beam in (1,2,3,5) for term in ('lift','rate','apparent')]


def candidate(iteration):
    return packet(STUDY/('base' if iteration==0 else f'update-{iteration-1}'))['state']


class Probe:
    def __init__(self):
        import numpy as np
        from check_daedalus_structural_resolution import dynamic
        from openswing.frequency_response import HarmonicInput
        self.system = dynamic(SimpleNamespace(seed=paths('coarse')[2]))
        self.n = self.system.network
        assert self.system.size==2044 and not self.n.loads
        assert [c.quantity for c in self.n.operating.constraints]==['force.'+a for a in 'xyz']+['moment.'+a for a in 'xyz']
        self.zero = np.zeros(self.system.size); self.omega = 2*np.pi*FREQUENCY
        self.forcing,_ = HarmonicInput(self.system,'control.3',0).at_frequency(self.omega)
        self.calls = 0

    def sample(self, z=None, part=0, amplitude=0.):
        import numpy as np
        system,n = self.system,self.n
        if z is None: state,_,options=system.physical_state(self.zero,self.zero,None)
        else:
            component=(np.real,np.imag)[part]
            state,_,options=system.physical_state(amplitude*component(z),amplitude*component(1j*self.omega*z),self.forcing(part,amplitude))
        residual,data=n.residual(state.x,detail=True,**options); self.calls+=1
        rho=data['aero']['atmosphere']['density']; delta=np.zeros((system.size,len(TERMS)))
        moments=np.zeros((len(TERMS),3)); details=[]; transfer_error=0.; component_error=0.
        for mesh in data['meshes']:
            if not mesh.beam.lifting:continue
            sl=n.beam_elements[mesh.beam.index];strips=data['aero']['strips'][sl]
            get=lambda key:np.array([s[key] for s in strips])
            forces=[rho*get('circulation')[:,None]*np.cross(get('relative_velocity'),mesh.frames[:,:,1])*get('length')[:,None],
                get('circulation_rate_force'),get('apparent_force')]
            span_arm=(mesh.r0+mesh.r1)/2-mesh.rm
            # Profile drag already uses the arithmetic centroid. It is excluded.
            profile=get('force')-sum(forces)
            quarter=((.25-mesh.beam.value('Xax',mesh.tm))*mesh.beam.value('chord',mesh.tm))[:,None]*mesh.frames[:,:,0]
            intrinsic=(get('moment')-np.cross(quarter,forces[0]+forces[1])-get('apparent_moment')-np.cross(span_arm,profile))
            reconstructed=np.cross(quarter,forces[0]+forces[1])+get('apparent_moment')+np.cross(span_arm,profile)+intrinsic
            component_error=max(component_error,float(np.max(abs(reconstructed-get('moment')))))
            for term,force in zip(('lift','rate','apparent'),forces):
                column=TERMS.index(f'beam{mesh.beam.index}:{term}')
                change=np.cross(span_arm,force)
                nodal=np.zeros_like(state.r)
                for ids in (n.a[sl],n.b[sl]):np.add.at(nodal,ids,change/2)
                total=change.sum(axis=0)
                transfer_error=max(transfer_error,float(np.max(abs(nodal.sum(axis=0)-total))))
                delta[6*n.ne+3*n.nn:6*n.ne+6*n.nn,column]=nodal.ravel()/(n.F*n.L)
                delta[n.operating_start+3:n.size,column]=total/(n.F*n.L)
                moments[column]=total
            details.append(dict(beam=mesh.beam.index,maximum_spanwise_shift_ft=float(np.max(np.linalg.norm(span_arm,axis=1))),
                total_nonprofile_force=sum(forces).sum(axis=0).tolist(),total_couple_change=np.cross(span_arm,sum(forces)).sum(axis=0).tolist()))
        assert transfer_error<2e-10 and component_error<2e-10
        return delta,moments,dict(details=details,transfer_error=transfer_error,component_error=component_error,
            unmodified_residual=float(max(abs(residual))))


def base(folder,args):
    import numpy as np
    probe=Probe();values,moments,diagnostics=probe.sample()
    assert diagnostics['unmodified_residual']<1e-9
    with np.load(SAMPLES/'coarse-samples/arrays.npz') as saved:
        idx=int(np.argmin(abs(saved['frequencies']-FREQUENCY)))
        assert abs(saved['frequencies'][idx]-FREQUENCY)<1e-13
        z,y=saved['states'][idx],saved['outputs'][idx]
    # Independent constant distributed-force control: the exact spanwise moment
    # uses the arithmetic centroid; Glauert points are still valid field samples.
    nodes=np.array([0.,2.,10.]);theta=np.arccos(1-2*nodes/10)
    receiver=5*(1-np.cos((theta[:-1]+theta[1:])/2))
    center=(nodes[:-1]+nodes[1:])/2;length=np.diff(nodes)
    gauss=np.polynomial.legendre.leggauss(8)
    integrated=sum(np.sum((.5*(b-a)*gauss[0]+.5*(a+b))*.5*(b-a)*gauss[1]) for a,b in zip(nodes[:-1],nodes[1:]))
    midpoint=float(center@length);sample=float(receiver@length)
    assert abs(integrated-50.)<2e-13 and abs(midpoint-integrated)<2e-13
    np.savez_compressed(folder/'arrays.npz',state=z,original_output=y,base_corrections=values,base_moment_changes=moments)
    return dict(frequency_hz=FREQUENCY,terms=TERMS,diagnostics=diagnostics,native_evaluations=probe.calls,
        constant_force_control=dict(nodes=nodes.tolist(),glauert_receivers=receiver.tolist(),exact_moment=integrated,
            arithmetic_midpoint_moment=midpoint,glauert_point_moment=sample,
            qualification='Unit uniform force per span on a straight interval. An independent quadrature control, not an ASWING reference run.'),
        qualification='The midpoint variant is a diagnostic of a force-centroid convention. Source Eq.155 explicitly locates a lifting sample at the Glauert quarter-chord point; Eq.55 uses structural interval averages. Their finite-grid reconciliation is not established here.')


def loads(folder,args):
    import numpy as np
    probe=Probe();z=candidate(args['iteration']);width=args['width']
    baseline,moments,diagnostics=probe.sample();saved=packet(STUDY/'base')
    replay=float(np.max(abs(baseline-saved['base_corrections'])));assert replay<2e-12
    tangent=np.zeros_like(baseline,dtype=complex);wrench=np.zeros_like(moments,dtype=complex)
    captures=[]
    for part in (0,1):
        for offset,weight in ((-2,1),(-1,-8),(1,8),(2,-1)):
            value,moment,details=probe.sample(z,part,offset*width)
            multiplier=weight/(12*width)*(1 if part==0 else 1j)
            tangent+=multiplier*value;wrench+=multiplier*moment
            captures.append(dict(part=part,offset=offset,transfer_error=details['transfer_error'],component_error=details['component_error']))
    a,m,b,c,layout,_,_=load('coarse');K=2j*np.pi*FREQUENCY*m-a
    correction=tangent.sum(axis=1);residual=K@z-b-correction
    norm=float(np.max(abs(residual)));relative=float(np.linalg.norm(residual)/max(np.linalg.norm(b)+np.linalg.norm(correction),1e-30))
    # Only nodal and global moment rows may change.
    allowed=np.r_[np.arange(6*probe.n.ne+3*probe.n.nn,6*(probe.n.ne+probe.n.nn)),np.arange(probe.n.operating_start+3,probe.n.size)]
    outside=np.setdiff1d(np.arange(len(b)),allowed);assert np.max(abs(tangent[outside]))==0
    np.savez_compressed(folder/'arrays.npz',state=z,correction=correction,component_corrections=tangent,moment_changes=wrench,
        full_modified_residual=residual,output=c@z)
    return dict(iteration=args['iteration'],width=width,native_evaluations=probe.calls,base_replay_error=replay,
        full_modified_residual=norm,relative_modified_residual=relative,captures=captures,
        qualification='Complete modified harmonic residual evaluated by a fourth-order directional stencil. A response is accepted only after both this residual and its next-output correction pass.')


def update(folder,args):
    import numpy as np
    data=packet(STUDY/args['load_tag']);a,m,b,c,layout,_,structure=load('coarse')
    solve=factor_at(a,m,2j*np.pi*FREQUENCY,structure)
    correction,checks=solve(-data['full_modified_residual'])
    z=data['state']+correction;y=c@z;old=c@data['state'];dy=c@correction
    size=float(max(abs(dy)/np.maximum(abs(y),1e-30)))
    residual=accepted(STUDY/args['load_tag'])
    accepted_state=(residual['full_modified_residual']<2e-11 and residual['relative_modified_residual']<2e-8 and size<2e-7)
    components=[]
    if args['iteration']==0:
        for column in data['component_corrections'].T:
            state,_=solve(column);components.append(c@state)
        np.testing.assert_allclose(sum(components),dy,rtol=2e-7,atol=2e-11)
    np.savez_compressed(folder/'arrays.npz',state=z,output=y,previous_state=data['state'],previous_output=old,
        state_correction=correction,output_correction=dy,initial_component_outputs=np.array(components))
    initial=packet(STUDY/'base')['original_output']
    return dict(iteration=args['iteration'],load_tag=args['load_tag'],next_output_relative_change=size,
        previous_state_accepted=accepted_state,solve_checks=checks,
        previous_amplitude_change_percent=(100*(abs(old)/abs(initial)-1)).tolist(),
        next_amplitude_change_percent=(100*(abs(y)/abs(initial)-1)).tolist(),
        qualification='Acceptance refers to the evaluated previous state. The computed correction measures its remaining defect; it is not silently accepted without a fresh modified-residual evaluation.')


def report(folder,args):
    import csv
    import numpy as np
    base=packet(STUDY/'base');fine=packet(STUDY/'loads-3');wide=packet(STUDY/'loads-3-wide')
    update_fine=packet(STUDY/'update-3');update_wide=packet(STUDY/'update-3-wide')
    assert accepted(STUDY/'update-3')['previous_state_accepted']
    assert accepted(STUDY/'update-3-wide')['previous_state_accepted']
    np.testing.assert_array_equal(fine['state'],wide['state'])
    np.testing.assert_array_equal(fine['state'],update_fine['previous_state'])
    load_width=float(np.max(abs(fine['correction']-wide['correction'])))
    output_width=float(max(abs(update_fine['output_correction']-update_wide['output_correction'])/abs(fine['output'])))
    assert load_width<2e-11 and output_width<2e-7
    matrix,_,_=paths('coarse')
    with np.load(matrix/'maps.npz') as maps:C=maps['C']
    np.testing.assert_allclose(C@fine['state'],fine['output'],atol=2e-13,rtol=2e-13)
    from check_daedalus_load_sensitivity import SOURCE
    with (SOURCE/'report/comparison.csv').open() as f:reference=list(csv.DictReader(f))
    entries=[]
    for i,channel in enumerate(CHANNELS):
        row=next(r for r in reference if r['channel']==channel and abs(float(r['frequency_hz'])-FREQUENCY)<1e-13)
        target=float(row['reference_magnitude']);old=base['original_output'][i];new=fine['output'][i]
        entries.append(dict(channel=channel,original_magnitude=float(abs(old)),alternative_magnitude=float(abs(new)),reference_magnitude=target,
            amplitude_change_percent=float(100*(abs(new)/abs(old)-1)),complex_change_percent=float(100*abs(new-old)/abs(old)),
            original_reference_error_percent=float(100*(abs(old)/target-1)),alternative_reference_error_percent=float(100*(abs(new)/target-1))))
    components=packet(STUDY/'update-0')['initial_component_outputs']
    component_rows=[]
    for j,term in enumerate(TERMS):
        for i,channel in enumerate(CHANNELS):
            value=components[j,i]
            component_rows.append(dict(term=term,channel=channel,real=float(value.real),imag=float(value.imag),
                first_variation_amplitude_percent=float(100*np.real(value/base['original_output'][i]))))
    iterations=[]
    for i in range(4):
        l=accepted(STUDY/f'loads-{i}');u=accepted(STUDY/f'update-{i}')
        iterations.append(dict(iteration=i,full_residual=l['full_modified_residual'],relative_residual=l['relative_modified_residual'],
            next_output_relative_change=u['next_output_relative_change'],accepted=u['previous_state_accepted']))
    assert [r['iteration'] for r in iterations if r['accepted']]==[3]
    for name,rows in [('response-comparison.csv',entries),('initial-component-variations.csv',component_rows),('iterations.csv',iterations)]:
        with (folder/name).open('x',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,2,figsize=(12,4.8),layout='constrained');x=np.arange(4)
    axes[0].bar(x-.18,[100*r['original_magnitude']/r['reference_magnitude'] for r in entries],.36,color='#ff4a3d',label='Original')
    axes[0].bar(x+.18,[100*r['alternative_magnitude']/r['reference_magnitude'] for r in entries],.36,color='#ff9f1a',label='Midpoint diagnostic')
    axes[0].axhline(100,color='#6dd36f',linestyle='--',label='Published reference')
    axes[0].set(xticks=x,xticklabels=['Yaw rate','Roll rate','Sideslip','Bank'],ylabel='Magnitude / published reference (%)',title='The coupled result remains far from the drawing')
    for j,(term,color) in enumerate(zip(('lift','rate','apparent'),('#ff4a3d','#ff9f1a','#ffd166'))):
        values=[next(r['first_variation_amplitude_percent'] for r in component_rows if r['channel']=='yaw_rate' and r['term']==f'beam{beam}:{term}') for beam in (1,2,3,5)]
        axes[1].bar(x+(j-1)*.23,values,.23,color=color,edgecolor='#666',linewidth=.4,label=term)
    axes[1].axhline(0,color='#555',linewidth=.7)
    axes[1].set(xticks=x,xticklabels=['Wing','Stabilizer','Fin','Fairing'],ylabel='Initial yaw-amplitude first variation (%)',title='Component account for the first correction only')
    for ax in axes:ax.set_axisbelow(True);ax.grid(axis='y',alpha=.2);ax.legend(fontsize=8)
    fig.suptitle('Spanwise force-centroid diagnostic at 1.157378 Hz; original equilibrium held',fontsize=12)
    fig.savefig(folder/'load-centroid.png',dpi=150);fig.savefig(folder/'load-centroid.svg');plt.close(fig)
    return dict(frequency_hz=FREQUENCY,entries=entries,initial_component_variations=component_rows,iterations=iterations,
        accepted_candidate='update-2/arrays.npz',accepted_residual='loads-3/result.json',
        independent_width_residual='loads-3-wide/result.json',width_load_difference=load_width,width_output_correction_difference_relative=output_width,
        first_to_final_complex_change_percent=(100*abs(fine['output']-packet(STUDY/'update-0')['output'])/abs(base['original_output'])).tolist(),
        qualification='One frequency, one original structural/aerodynamic mesh, and a constant residual offset. Complete linear feedback converged; not a physical retrim or authentication of the historical ASWING sampling convention.')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('stage',choices=['base','loads','update','report'])
    p.add_argument('--tag',required=True);p.add_argument('--iteration',type=int,default=0)
    p.add_argument('--width',type=float,default=5e-4);p.add_argument('--load-tag',default='loads-0')
    args=vars(p.parse_args())
    inputs=[ROOT/'scripts'/s for s in ('check_daedalus_structural_resolution.py','check_daedalus_source_operator.py',
        'check_daedalus_mesh_zeros.py','check_daedalus_mesh_residual.py')]
    inputs += [ROOT/'examples/dae.asw',ROOT/'examples/dae-cruise-physical-mesh-project.json',ROOT/'docs/validation/ISAE_STATUS.md',ROOT/'docs/validation/aswing-authoritative-sources.json',
        ROOT/'reference/aswing-authoritative-20261108/drela-aswing-steady.pdf',ROOT/'reference/aswing-authoritative-20261108/drela-aswing-unsteady.pdf']
    inputs+=list((ROOT/'openswing').glob('*.py'))
    matrix,layout,seed=paths('coarse');inputs += [layout,seed]+[matrix/s for s in ('A.npz','M.npz','maps.npz')]
    inputs += [SAMPLES/'coarse-samples'/s for s in ('arrays.npz','result.json','terminal.json')]
    if args['stage']!='base':inputs += [STUDY/'base'/s for s in ('arrays.npz','result.json','terminal.json')]
    if args['stage']=='loads' and args['iteration']>0:inputs += [STUDY/f"update-{args['iteration']-1}"/s for s in ('arrays.npz','result.json','terminal.json')]
    if args['stage']=='update':inputs += [STUDY/args['load_tag']/s for s in ('arrays.npz','result.json','terminal.json')]
    if args['stage']=='report':
        from check_daedalus_load_sensitivity import SOURCE
        inputs += [SOURCE/'report/comparison.csv']
        inputs += [STUDY/f'{stage}-{i}'/s for stage in ('loads','update') for i in range(4) for s in ('arrays.npz','result.json','terminal.json')]
        inputs += [STUDY/tag/s for tag in ('loads-3-wide','update-3-wide') for s in ('arrays.npz','result.json','terminal.json')]
    run(STUDY,args['tag'],inputs,globals()[args['stage']],args,__file__)


if __name__=='__main__':main()
