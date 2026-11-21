"""Bounded quarter-chord interpretation diagnostics; no production changes.

kinematic: only use the physical quarter-chord arm for section/frame velocity.
receiver: sample all force-receiver fields at physical chord/4; retain the
steady wind-aligned bound vortices, CPs and own-bound exclusion. This hybrid
is conditional, not a claim about historical ASWING. Constant offsets retain
the original equilibrium when receiver sampling changes its loads.
"""
import argparse
from types import SimpleNamespace
from check_daedalus_load_sensitivity import ROOT, SOURCE, read
from check_daedalus_mesh_zeros import paths, load, factor_at, CHANNELS, STUDY as SAMPLES
from check_daedalus_mesh_residual import accepted, packet
from daedalus_bounded_job import run

STUDY = ROOT/'artifacts/daedalus-quarter-receiver-20261114'
FREQUENCY = 1.15737773741517
POLICIES = ('kinematic', 'receiver')


def physical_receiver(meshes):
    import numpy as np
    return np.concatenate([m.rm+((.25-m.beam.value('Xax',m.tm))*m.beam.value('chord',m.tm))[:,None]*m.frames[:,:,0]
        for m in meshes if m.beam.lifting])


class Incident:
    phase = 'diagnostic'
    capture_circulation = False
    def __init__(self, change): self.change = change
    def fixed_geometry(self, key, compute): return compute()
    def get(self, key, compute): return compute()
    def incident_velocity(self, key, value): return value+self.change if key=='hv' else value


class Probe:
    def __init__(self):
        import numpy as np
        from check_daedalus_structural_resolution import dynamic
        from openswing.frequency_response import HarmonicInput
        self.system=dynamic(SimpleNamespace(seed=paths('coarse')[2]));self.n=self.system.network
        self.zero=np.zeros(self.system.size);self.calls=0;self.omega=2*np.pi*FREQUENCY
        self.forcing,_=HarmonicInput(self.system,'control.3',0).at_frequency(self.omega)
        assert self.system.size==2044 and not self.n.condition.freeze_influences

    def sample(self, policy='original', z=None, part=0, amplitude=0.):
        import numpy as np
        import openswing.aero as aero
        import openswing.source_coupled as coupled
        old_evaluate=coupled.evaluate_aerodynamics;old_geometry=aero.lifting_geometry
        def geometry(meshes, direction, **kwargs):
            g=old_geometry(meshes,direction,**kwargs)
            if policy=='receiver':g['hv']=physical_receiver(meshes)
            return g
        def evaluate(model, condition, meshes, *args, **kwargs):
            if policy=='kinematic':
                assert kwargs.get('_iteration_fields') is None
                g=old_geometry(meshes,condition.vectors()[0])
                local=kwargs.get('local_motion');rates=np.zeros_like(g['hv'])
                if local is not None:rates=local.surface().rates
                change=-np.cross(np.asarray(condition.rates)+rates,physical_receiver(meshes)-g['hv'])
                kwargs['_iteration_fields']=Incident(change)
            return old_evaluate(model,condition,meshes,*args,**kwargs)
        if z is None:state,_,options=self.system.physical_state(self.zero,self.zero,None)
        else:
            component=(np.real,np.imag)[part]
            state,_,options=self.system.physical_state(amplitude*component(z),amplitude*component(1j*self.omega*z),self.forcing(part,amplitude))
        self.n.aero_key=None
        try:
            coupled.evaluate_aerodynamics=evaluate;aero.lifting_geometry=geometry
            r,data=self.n.residual(state.x,detail=True,**options)
        finally:coupled.evaluate_aerodynamics=old_evaluate;aero.lifting_geometry=old_geometry
        self.calls+=1
        out=np.zeros(self.system.size);out[:len(r)]=r
        return out,data


def base(folder,args):
    import numpy as np
    from openswing.frozen_influence import lifting_geometry
    p=Probe();r,data=p.sample();k,kdata=p.sample('kinematic');v,vdata=p.sample('receiver')
    assert max(abs(r))<1e-9
    np.testing.assert_array_equal(k,r)
    g=lifting_geometry(data['meshes'],data['condition'].vectors()[0])
    strips=[s for s in data['aero']['strips'] if s['beam'] in (1,2,3,5)]
    altered=[s for s in vdata['aero']['strips'] if s['beam'] in (1,2,3,5)]
    actual=physical_receiver(data['meshes']);ids=np.array([s['beam'] for s in strips])
    with np.load(SAMPLES/'coarse-samples/arrays.npz') as saved:
        index=np.argmin(abs(saved['frequencies']-FREQUENCY));assert abs(saved['frequencies'][index]-FREQUENCY)<1e-13
        z=saved['states'][index];y=saved['outputs'][index]
    rows=[]
    for beam in (1,2,3,5):
        mask=ids==beam;first=np.array([s['relative_velocity'] for s in strips])[mask]
        second=np.array([s['relative_velocity'] for s in altered])[mask]
        rows.append(dict(beam=beam,maximum_receiver_shift_ft=float(np.max(np.linalg.norm(actual[mask]-g['hv'][mask],axis=1))),
            maximum_velocity_change_ft_s=float(np.max(np.linalg.norm(second-first,axis=1)))))
    np.savez_compressed(folder/'arrays.npz',state=z,original_output=y,base_original=r,
        base_kinematic=k-r,base_receiver=v-r,wind_receiver=g['hv'],physical_receiver=actual,beam=ids)
    return dict(frequency_hz=FREQUENCY,rows=rows,native_evaluations=p.calls,
        original_residual=float(max(abs(r))),receiver_base_residual_change=float(max(abs(v-r))),
        kinematic_base_residual_change=float(max(abs(k-r))),
        qualification='Physical receiver diagnostic retains the virtual wind-aligned source segments and own-bound exclusion. It is not proof of a coherent native convention or a new trim.')


def loads(folder,args):
    import numpy as np
    policy=args['policy'];i=args['iteration'];h=args['width'];p=Probe()
    z=packet(STUDY/('base-v2' if i==0 else f'{policy}-update-{i-1}'))['state']
    baseline=packet(STUDY/'base-v2');original,_=p.sample();alternative,_=p.sample(policy)
    replay=float(max(abs(alternative-original-baseline['base_'+policy])));assert replay<2e-12
    pieces=[]
    for part in (0,1):
        value=np.zeros(p.system.size)
        for offset,weight in ((-2,1),(-1,-8),(1,8),(2,-1)):
            original,_=p.sample('original',z,part,offset*h);alternative,_=p.sample(policy,z,part,offset*h)
            value+=weight*(alternative-original)/(12*h)
        pieces.append(value)
    delta=pieces[0]+1j*pieces[1]
    a,m,b,c,*_=load('coarse');residual=(2j*np.pi*FREQUENCY*m-a)@z-b-delta
    ne,nn=p.n.ne,p.n.nn
    allowed=np.r_[np.arange(6*ne,6*(ne+nn)),np.arange(p.n.gamma_start,p.n.size)]
    outside=np.setdiff1d(np.arange(len(z)),allowed);assert max(abs(delta[outside]))==0
    np.savez_compressed(folder/'arrays.npz',state=z,correction=delta,full_modified_residual=residual,output=c@z)
    return dict(policy=policy,iteration=i,width=h,native_evaluations=p.calls,base_replay_error=replay,
        full_modified_residual=float(max(abs(residual))),relative_modified_residual=float(np.linalg.norm(residual)/max(np.linalg.norm(b)+np.linalg.norm(delta),1e-30)))


def update(folder,args):
    import numpy as np
    d=packet(STUDY/args['load_tag']);r=accepted(STUDY/args['load_tag'])
    a,m,b,c,layout,seed,structure=load('coarse');solve=factor_at(a,m,2j*np.pi*FREQUENCY,structure)
    dz,checks=solve(-d['full_modified_residual']);z=d['state']+dz;y=c@z;dy=c@dz
    change=float(max(abs(dy)/np.maximum(abs(y),1e-30)))
    ok=r['full_modified_residual']<2e-11 and r['relative_modified_residual']<2e-8 and change<2e-7
    old=packet(STUDY/'base-v2')['original_output']
    np.savez_compressed(folder/'arrays.npz',state=z,output=y,previous_state=d['state'],previous_output=c@d['state'],state_correction=dz,output_correction=dy)
    return dict(policy=args['policy'],iteration=args['iteration'],load_tag=args['load_tag'],previous_state_accepted=ok,
        next_output_relative_change=change,solve_checks=checks,
        previous_amplitude_change_percent=(100*(abs(c@d['state'])/abs(old)-1)).tolist(),
        next_amplitude_change_percent=(100*(abs(y)/abs(old)-1)).tolist())


def reference(folder,args):
    """Independent quadrature and load-transfer derivative of receiver change."""
    import numpy as np
    from check_daedalus_plume_receivers import setup,direction,residual_action
    ref,fixture=setup();original_geometry=ref.aero.geometry
    def evaluate(state,physical):
        def geometry(*a,**kw):
            g=original_geometry(*a,**kw)
            if physical:g['hv']=g['rm']+g['quarter_arm']
            return g
        ref.aero.geometry=geometry
        try:return ref.evaluate(state)
        finally:ref.aero.geometry=original_geometry
    original=evaluate(ref.base,False);alternative=evaluate(ref.base,True)
    base_delta={k:alternative[k]-original[k] for k in original}
    z=packet(STUDY/'base-v2')['state'];d,motion=direction(ref,fixture,z,FREQUENCY)
    part=args['part'];component=(np.real,np.imag)[part];h=args['width']
    state={k:np.asarray(v,complex)+1j*h*component(d[k]) for k,v in ref.base.items()}
    original=evaluate(state,False);alternative=evaluate(state,True)
    delta={k:(alternative[k].imag-original[k].imag)/h for k in original}
    # Transfer uses complex aircraft motion; reconstruct the matching real component.
    real_motion={k:component(v) for k,v in motion.items()}
    expected=residual_action(ref,fixture,real_motion,base_delta,delta,'all')
    actual=component(packet(STUDY/'receiver-loads-0')['correction'])
    error=float(max(abs(expected-actual)));assert error<2e-10,error
    assert max(abs(delta['engine_force']).ravel())==0 and max(abs(delta['body_force']).ravel())==0
    np.savez_compressed(folder/'arrays.npz',expected=expected,actual=actual)
    return dict(part=part,complex_step=h,maximum_scaled_residual_action_error=error,evaluations=ref.evaluations,
        qualification='Independent vortex/volume/jet quadrature and physical load transfer verify the explicitly declared hybrid receiver convention. They do not authenticate that convention as native ASWING.')


def report(folder,args):
    import csv
    import numpy as np
    with (SOURCE/'report/comparison.csv').open() as stream:reference=list(csv.DictReader(stream))
    original=packet(STUDY/'base-v2')['original_output'];rows=[];checks=[];iterations=[]
    for policy,index in [('kinematic',2),('receiver',4)]:
        tag=f'{policy}-loads-{index}';data=packet(STUDY/tag);wide=packet(STUDY/(tag+'-wide'))
        update=packet(STUDY/f'{policy}-update-{index}');update_wide=packet(STUDY/f'{policy}-update-{index}-wide')
        assert accepted(STUDY/f'{policy}-update-{index}')['previous_state_accepted']
        assert accepted(STUDY/f'{policy}-update-{index}-wide')['previous_state_accepted']
        np.testing.assert_array_equal(data['state'],wide['state'])
        np.testing.assert_array_equal(data['state'],packet(STUDY/f'{policy}-update-{index-1}')['state'])
        difference=float(max(abs(data['correction']-wide['correction'])))
        output_difference=float(max(abs(update['output_correction']-update_wide['output_correction'])/abs(data['output'])))
        assert difference<2e-11 and output_difference<2e-7
        checks.append(dict(policy=policy,accepted_candidate=f'{policy}-update-{index-1}/arrays.npz',
            accepted_residual=tag+'/result.json',independent_width_residual=tag+'-wide/result.json',
            width_load_difference=difference,width_output_correction_difference_relative=output_difference))
        for j,channel in enumerate(CHANNELS):
            target=float(next(r['reference_magnitude'] for r in reference if r['channel']==channel and abs(float(r['frequency_hz'])-FREQUENCY)<1e-13))
            y=data['output'][j];old=original[j]
            rows.append(dict(policy=policy,channel=channel,original_magnitude=float(abs(old)),alternative_magnitude=float(abs(y)),
                reference_magnitude=target,amplitude_change_percent=float(100*(abs(y)/abs(old)-1)),
                complex_change_percent=float(100*abs(y-old)/abs(old)),reference_error_percent=float(100*(abs(y)/target-1))))
        for i in range(index+1):
            l=accepted(STUDY/f'{policy}-loads-{i}');u=accepted(STUDY/f'{policy}-update-{i}')
            iterations.append(dict(policy=policy,iteration=i,full_residual=l['full_modified_residual'],relative_residual=l['relative_modified_residual'],
                next_output_relative_change=u['next_output_relative_change'],accepted=u['previous_state_accepted']))
    for name,values in [('comparison.csv',rows),('iterations.csv',iterations)]:
        with (folder/name).open('x',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=list(values[0]));writer.writeheader();writer.writerows(values)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,2,figsize=(11.5,4.6),layout='constrained');x=np.arange(4)
    targets=np.array([r['reference_magnitude'] for r in rows[:4]])
    axes[0].bar(x-.25,100*abs(original)/targets,.25,color='#ff4a3d',label='Original')
    for i,(policy,color,label) in enumerate(zip(POLICIES,['#ff9f1a','#ffd166'],['Physical kinematic arm','Physical field receiver'])):
        values=[r for r in rows if r['policy']==policy]
        axes[0].bar(x+i*.25,[100*r['alternative_magnitude']/r['reference_magnitude'] for r in values],.25,color=color,label=label)
        axes[1].bar(x+(i-.5)*.3,[r['amplitude_change_percent'] for r in values],.3,color=color,label=label)
    axes[0].axhline(100,color='#6dd36f',linestyle='--',label='Published reference')
    axes[1].axhline(0,color='#555',linewidth=.7)
    for ax in axes:
        ax.set(xticks=x,xticklabels=['Yaw rate','Roll rate','Sideslip','Bank']);ax.set_axisbelow(True);ax.grid(axis='y',alpha=.2);ax.legend(fontsize=8)
    axes[0].set(ylabel='Magnitude / published reference (%)',title='Reference mismatch persists')
    axes[1].set(ylabel='Amplitude change from original (%)',title='Complete coupled correction')
    fig.suptitle('Quarter-chord interpretation diagnostics at 1.157378 Hz; fixed original equilibrium',fontsize=11)
    fig.savefig(folder/'quarter-receiver.png',dpi=150);fig.savefig(folder/'quarter-receiver.svg');plt.close(fig)
    return dict(frequency_hz=FREQUENCY,entries=rows,checks=checks,iterations=iterations,
        geometry=accepted(STUDY/'base-v2'),independent_action_checks=[accepted(STUDY/f'reference-{i}') for i in (0,1)],
        qualification='One mesh and frequency. Exact full-state correction solves with converged linear feedback and independent width checks; field-receiver variant holds its changed mean loads by a constant offset. Neither variant establishes historical ASWING geometry or browser defaults.')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('stage',choices=['base','loads','update','reference','report'])
    p.add_argument('--tag',required=True);p.add_argument('--policy',choices=POLICIES,default='receiver')
    p.add_argument('--iteration',type=int,default=0);p.add_argument('--width',type=float,default=5e-4)
    p.add_argument('--part',type=int,choices=[0,1],default=0);p.add_argument('--load-tag',default='receiver-loads-0')
    args=vars(p.parse_args())
    helpers=['check_daedalus_structural_resolution.py','check_daedalus_source_operator.py','check_daedalus_mesh_zeros.py','check_daedalus_mesh_residual.py']
    if args['stage']=='reference':
        from check_daedalus_circulation_phase import REFERENCE
        helpers+=REFERENCE+['check_daedalus_circulation_phase.py','check_daedalus_plume_receivers.py','daedalus_source_balance_reference.py']
    inputs=[ROOT/'scripts'/s for s in helpers]+list((ROOT/'openswing').glob('*.py'))
    inputs += [ROOT/s for s in ['examples/dae.asw','examples/dae-cruise-physical-mesh-project.json','docs/validation/ISAE_STATUS.md','docs/validation/aswing-authoritative-sources.json',
        'reference/aswing-authoritative-20261108/drela-aswing-steady.pdf','reference/aswing-authoritative-20261108/drela-aswing-unsteady.pdf']]
    matrix,layout,seed=paths('coarse');inputs += [layout,seed]+[matrix/s for s in ('A.npz','M.npz','maps.npz')]
    inputs += [SAMPLES/'coarse-samples'/s for s in ('arrays.npz','result.json','terminal.json')]
    if args['stage']!='base':inputs += [STUDY/'base-v2'/s for s in ('arrays.npz','result.json','terminal.json')]
    if args['stage']=='loads' and args['iteration']>0:inputs += [STUDY/f"{args['policy']}-update-{args['iteration']-1}"/s for s in ('arrays.npz','result.json','terminal.json')]
    if args['stage']=='update':inputs += [STUDY/args['load_tag']/s for s in ('arrays.npz','result.json','terminal.json')]
    if args['stage']=='reference':
        inputs += [ROOT/'artifacts/daedalus-circulation-phase-20261114/capture-base/base.pkl',ROOT/'artifacts/daedalus-source-balance-20261114/capture-dip/fixture.pkl']
        inputs += [STUDY/'receiver-loads-0'/s for s in ('arrays.npz','result.json','terminal.json')]
    if args['stage']=='report':
        inputs += [SOURCE/'report/comparison.csv']
        for p in STUDY.iterdir():
            if p.is_dir() and p.name not in ('base',args['tag']):
                inputs += [q for q in p.iterdir() if q.name in ('arrays.npz','result.json','terminal.json')]
    run(STUDY,args['tag'],inputs,globals()[args['stage']],args,__file__)


if __name__=='__main__':main()
