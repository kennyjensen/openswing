"""Bounded audit of Glauert sampling and an alternative nodal-rate interpolation.

The alternative is conditional: the references define nodal body-axis rates
and the Glauert location, but do not explicitly specify this interior angular
interpolant. No claim of native ASWING equivalence or production change.
"""
import argparse
from pathlib import Path
from types import SimpleNamespace
from check_daedalus_load_sensitivity import ROOT,SOURCE,read
from daedalus_bounded_job import run

STUDY=ROOT/'artifacts/daedalus-rate-interpolation-20261114'
SEED=SOURCE/'trim-6.7-1/state.json'
DIP=1.15737773741517


def system(seed=SEED):
    from check_daedalus_structural_resolution import dynamic
    return dynamic(SimpleNamespace(seed=seed))


class LinearRates:
    """Child-local component interpolation of interior spatial omega/omega-dot.

    Nodal kinematics and completed endpoint inertia are untouched. Material
    strain sampling is untouched; the aircraft has zero material damping.
    This is not the exact derivative of the unchanged geodesic orientation.
    """
    def __enter__(self):
        import numpy as np
        from openswing.local_motion import NetworkMotion
        self.original=NetworkMotion.sample;original=self.original
        def sample(motion,beam,fraction,*,material=False):
            field,rotation,kd=original(motion,beam,fraction,material=material)
            if material:return field,rotation,kd
            n=motion.network;sl=n.beam_elements[beam]
            f=np.broadcast_to(fraction,(len(motion.pa[sl]),)+np.shape(fraction)[1:])
            a,b=n.a[sl],n.b[sl]
            def interpolate(v):
                left,right=v[a],v[b]
                if f.ndim==2:left,right=left[:,None],right[:,None]
                return left+(right-left)*f[...,None]
            field.rates=interpolate(motion.rates)
            field.rate_derivative=interpolate(motion.rate_derivative)
            return field,rotation,kd
        NetworkMotion.sample=sample
        return self
    def __exit__(self,*exc):
        from openswing.local_motion import NetworkMotion
        NetworkMotion.sample=self.original


def euler_frame(angles,body):
    """Direct composition of the published surface/body Euler sequences."""
    import numpy as np
    from scipy.spatial.transform import Rotation
    p,t,s=angles.T
    rx=Rotation.from_rotvec(np.c_[p,np.zeros((len(p),2))]).as_matrix()
    ry=Rotation.from_rotvec(np.c_[np.zeros(len(t)),t,np.zeros(len(t))]).as_matrix()
    rz=Rotation.from_rotvec(np.c_[np.zeros((len(s),2)),s]).as_matrix()
    return (rz@rx if body else rx@rz)@ry


def inspect(folder,args):
    import numpy as np
    from scipy.spatial.transform import Rotation
    from openswing.local_motion import NetworkMotion
    from openswing.source_discrete import angles_from_frame,_increments
    s=system();n=s.network;zero=np.zeros(s.size)
    assert s.size==2044 and not np.any(n.damping_times)
    base,_,_=s.physical_state(zero,zero);r,Q,*_=n.unpack(base.x)
    geometry=n.geometry(r,Q);meshes=n.deformed_meshes(r,Q,geometry)
    original=s.residual(zero,zero)
    with LinearRates():changed=s.residual(zero,zero)
    np.testing.assert_array_equal(original,changed)
    assert max(abs(original))<1e-9
    positions=[];orientations=[]
    for mesh,loaded in zip(n.meshes,meshes):
        sl=n.beam_elements[mesh.beam.index];f=n.fractions[mesh.beam.index]
        # theta runs pi -> zero in the saved mesh. s = L(1+cos(theta))/2.
        a,b=mesh.theta[:-1],mesh.theta[1:]
        from_theta=(np.cos((a+b)/2)-np.cos(a))/(np.cos(b)-np.cos(a))
        np.testing.assert_allclose(f,from_theta,atol=4e-12,rtol=0)
        expected=geometry[0][sl]+from_theta[:,None]*(geometry[1][sl]-geometry[0][sl])
        position_error=float(max(abs(loaded.rm-expected).ravel()));assert position_error<2e-11
        qa=angles_from_frame(geometry[2][sl],not mesh.beam.lifting)
        qb=angles_from_frame(geometry[3][sl],not mesh.beam.lifting)
        frame=euler_frame(qa+f[:,None]*_increments(qa,qb),not mesh.beam.lifting)
        difference=Rotation.from_matrix(frame.transpose(0,2,1)@loaded.frames).magnitude()*180/np.pi
        orientations.append(dict(beam=mesh.beam.index,maximum_euler_vs_geodesic_degrees=float(max(difference)),
            rms_euler_vs_geodesic_degrees=float(np.sqrt(np.mean(difference**2))),
            station_at_maximum=float(mesh.tm[int(np.argmax(difference))])))
        positions.append(dict(beam=mesh.beam.index,maximum_fraction_error=float(max(abs(f-from_theta))),
            maximum_position_error_ft=position_error))
    with np.load(ROOT/'artifacts/daedalus-wing-peak-mass-20261114/dip/arrays.npz') as data:z=data['original_state']
    old=[];new=[]
    for component in (np.real,np.imag):
        _,_,options=s.physical_state(component(z),component(2j*np.pi*DIP*z))
        local=NetworkMotion(n,r,Q,*options['elastic_motion'])
        old_part=[];new_part=[]
        for mesh in n.meshes:
            f=n.fractions[mesh.beam.index]
            field,_,_=local.sample(mesh.beam.index,f)
            old_part.append(np.stack([field.rates,field.rate_derivative]))
            with LinearRates():field,_,_=local.sample(mesh.beam.index,f)
            new_part.append(np.stack([field.rates,field.rate_derivative]))
        old.append(np.concatenate(old_part,axis=1));new.append(np.concatenate(new_part,axis=1))
    old=old[0]+1j*old[1];new=new[0]+1j*new[1]
    rates=[]
    for mesh in n.meshes:
        sl=n.beam_elements[mesh.beam.index];difference=new[0,sl]-old[0,sl]
        magnitude=np.linalg.norm(difference,axis=1)
        rates.append(dict(beam=mesh.beam.index,maximum_angular_rate_difference_rad_s=float(max(magnitude)),
            rate_difference_relative_norm=float(np.linalg.norm(difference)/np.linalg.norm(old[0,sl])),
            maximum_angular_acceleration_difference_rad_s2=float(max(np.linalg.norm(new[1,sl]-old[1,sl],axis=1)))))
    np.savez_compressed(folder/'arrays.npz',original_rates=old,linear_rates=new,base_residual=original,
        alternative_base_residual=changed,original_harmonic_state=z)
    return dict(position_checks=positions,orientation_comparison=orientations,rate_comparison=rates,
        base_residual=float(max(abs(original))),base_residual_bitwise_unchanged=True,
        full_dimension=s.size,complete_residual_evaluations=2,
        qualification='Euler orientations are compared only, not applied. Conditional linear spatial-rate interpolation leaves the exact physical mean unchanged; it is not the derivative of the current orientation interpolant or a proven native-ASWING rule.')


def response(folder,args):
    import numpy as np
    import check_daedalus_wing_peak_mass as driver
    driver.STUDY=STUDY
    def make(seed):
        s=system(seed);assert not np.any(s.network.damping_times)
        return s
    driver.retrim_system=make
    with LinearRates():result=driver.retrim_step(folder,args)
    result['qualification']='Conditional componentwise interpolation of interior body-axis angular rates and their derivatives; baseline physical trim unchanged. All 2044 harmonic equations are evaluated. The original descriptor is only a preconditioner, not a rank certificate for this alternative.'
    return result


def euler_rate_probe(folder,args):
    """Exact time derivative of a conditional linearly interpolated Euler chart.

    This is a local comparison on the retained harmonic direction, not a new
    aircraft response and not a bound on its possible coupled output change.
    """
    import numpy as np
    from openswing.source_discrete import angles_from_frame,angle_matrix,_increments
    s=system();n=s.network;zero=np.zeros(s.size)
    base,_,_=s.physical_state(zero,zero);r,Q,*_=n.unpack(base.x);geometry=n.geometry(r,Q)
    with np.load(STUDY/'inspect/arrays.npz') as data:z=data['original_harmonic_state'];original=data['original_rates'][0]
    components=[]
    for component in (np.real,np.imag):
        _,_,options=s.physical_state(component(z),component(2j*np.pi*DIP*z))
        components.append(options['elastic_motion'][1])
    omega=components[0]+1j*components[1];rows=[];values=[]
    for mesh in n.meshes:
        key=mesh.beam.index;sl=n.beam_elements[key];body=not mesh.beam.lifting;f=n.fractions[key]
        Ra,Rb=geometry[2][sl],geometry[3][sl]
        qa,qb=angles_from_frame(Ra,body),angles_from_frame(Rb,body)
        qa_dot=np.linalg.solve(Ra@angle_matrix(qa,body),omega[n.a[sl],:,None])[...,0]
        qb_dot=np.linalg.solve(Rb@angle_matrix(qb,body),omega[n.b[sl],:,None])[...,0]
        mid=qa+f[:,None]*_increments(qa,qb);rate=qa_dot+f[:,None]*(qb_dot-qa_dot)
        R=euler_frame(mid,body);interior=np.einsum('nij,nj->ni',R@angle_matrix(mid,body),rate)
        values.append(interior);difference=interior-original[sl]
        rows.append(dict(beam=key,maximum_angular_rate_difference_rad_s=float(max(np.linalg.norm(difference,axis=1))),
            rate_difference_relative_norm=float(np.linalg.norm(difference)/np.linalg.norm(original[sl]))))
    np.savez_compressed(folder/'arrays.npz',euler_rates=np.concatenate(values),current_rates=original)
    return dict(frequency_hz=DIP,rows=rows,
        qualification='Tangent of linearly interpolated absolute Euler angles, using published nodal rate transformations. Current harmonic direction held for comparison; no alternative equilibrium or coupled Bode response has been solved.')


def report(folder,args):
    import csv
    import numpy as np
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.ticker import LogLocator,FuncFormatter,NullFormatter
    from check_daedalus_mesh_zeros import CHANNELS
    from check_daedalus_mesh_residual import accepted
    with (ROOT/'docs/validation/daedalus-rudder-four-outputs.csv').open() as stream:raw=list(csv.DictReader(stream))
    reference={ch:np.array(sorted((float(r['frequency_Hz']),float(r['reference_drawing_magnitude']))
        for r in raw if r['channel']==ch)) for ch in CHANNELS}
    rows=[];checks=[]
    for tag in ('low','dip','roll'):
        first,second=f'{tag}-1',f'{tag}-check'
        p,q=accepted(STUDY/first),accepted(STUDY/second)
        assert p['evaluated_state_accepted'] and q['evaluated_state_accepted']
        assert p['width']==.002 and q['width']==.004 and p['frequency_hz']==q['frequency_hz']
        assert p['physical_seed']==q['physical_seed']==str(SEED.resolve())
        with np.load(STUDY/first/'arrays.npz') as data:left=dict(data)
        with np.load(STUDY/second/'arrays.npz') as data:right=dict(data)
        np.testing.assert_array_equal(left['state'],right['state'])
        difference=float(max(abs(left['output_correction']-right['output_correction'])/abs(left['output'])))
        assert difference<2e-7
        f=p['frequency_hz'];checks.append(dict(frequency_hz=f,first=first,second=second,
            first_residual=p['history'][-1]['complete_harmonic_residual'],
            second_residual=q['history'][-1]['complete_harmonic_residual'],
            width_output_correction_difference_relative=difference))
        for j,ch in enumerate(CHANNELS):
            target=float(np.exp(np.interp(np.log(f),np.log(reference[ch][:,0]),np.log(reference[ch][:,1]))))
            value=p['output_magnitude'][j];original=p['original_output_magnitude'][j]
            rows.append(dict(frequency_hz=f,channel=ch,original_magnitude=original,magnitude=value,
                reference_magnitude=target,change_from_original_percent=100*(value/original-1),
                reference_error_percent=100*(value/target-1)))
    with (folder/'comparison.csv').open('x',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    with (SOURCE/'report/comparison.csv').open() as stream:baseline=[r for r in csv.DictReader(stream) if float(r['speed_m_s'])==6.7]
    fig,axes=plt.subplots(2,2,figsize=(12,8),layout='constrained')
    for j,(ax,ch) in enumerate(zip(axes.flat,CHANNELS)):
        original=sorted((float(r['frequency_hz']),float(r['magnitude_display'])) for r in baseline if r['channel']==ch)
        ax.loglog(reference[ch][:,0],reference[ch][:,1],color='#333333',label='Drela published magnitude')
        ax.loglog([v[0] for v in original],[v[1] for v in original],color='#ff4a3d',label='Current interpolant (retained sweep)')
        selected=[r for r in rows if r['channel']==ch]
        ax.loglog([r['frequency_hz'] for r in selected],[r['magnitude'] for r in selected],
            color='#ff9f1a',marker='o',linestyle='none',markersize=6,markeredgecolor='#333333',markeredgewidth=.6,
            label='Conditional linear angular rates')
        ax.set_title(ch.replace('_',' ').title());ax.set_xlabel('Frequency (cycles/s)')
        ax.set_ylabel(('deg/s' if j<2 else 'deg')+' per F3 unit');ax.set_xlim(.1,10)
        for axis in (ax.xaxis,ax.yaxis):
            axis.set_major_locator(LogLocator(base=10));axis.set_minor_locator(LogLocator(base=10,subs=np.arange(2,10)))
            axis.set_major_formatter(FuncFormatter(lambda v,pos:f'{v:g}'));axis.set_minor_formatter(NullFormatter())
        ax.grid(which='major',color='#aaaaaa',alpha=.6);ax.grid(which='minor',color='#dddddd',alpha=.65)
        if j==0:ax.legend(fontsize=8)
    fig.suptitle('Daedalus: interior angular-rate interpolation diagnostic\nSame exact mean state; only three alternative frequency samples; no native interpolation claim')
    fig.savefig(folder/'comparison.png',dpi=150);fig.savefig(folder/'comparison.svg');plt.close(fig)
    return dict(paired_stencil_checks=checks,rows=rows,frequencies=3,
        qualification='Conditional rate interpolation; no affine mean offset, new frequency sweep, reconstructed historical input, or native-reference pass count. Euler orientation comparison was not applied to these responses.')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage',choices=['inspect','response','report','euler_rate_probe']);parser.add_argument('--tag',required=True)
    parser.add_argument('--seed',default=str(SEED));parser.add_argument('--source')
    parser.add_argument('--frequency',type=float,default=DIP);parser.add_argument('--width',type=float,default=.002)
    parser.add_argument('--state',choices=['state','next_state'],default='next_state')
    parser.add_argument('--iterations',type=int,choices=[1,2],default=2)
    args=vars(parser.parse_args())
    inputs=[ROOT/name for name in ('examples/dae.asw','examples/dae-cruise-physical-mesh-project.json','docs/validation/ISAE_STATUS.md',
        'docs/validation/aswing-authoritative-sources.json','reference/aswing-authoritative-20261108/drela-aswing-steady.pdf',
        'reference/aswing-authoritative-20261108/drela-aswing-unsteady.pdf',
        'artifacts/daedalus-wing-peak-mass-20261114/dip/arrays.npz')]
    inputs+=list((ROOT/'openswing').glob('*.py'))
    inputs += [ROOT/'scripts'/name for name in ('check_daedalus_wing_peak_mass.py','check_daedalus_measured_mass.py',
        'check_daedalus_mesh_zeros.py','check_daedalus_mesh_residual.py','check_daedalus_structural_resolution.py',
        'check_daedalus_source_operator.py')]
    inputs += [Path(args['seed']).resolve(),SOURCE/'mass-6.7/layout.json']
    folders=[SOURCE/'assembled-6.7']
    if args['source']:folders += [STUDY/args['source']]
    if args['stage']=='report':
        folders += [STUDY/'inspect',*[STUDY/f'{tag}-{suffix}' for tag in ('low','dip','roll') for suffix in ('1','check')]]
        inputs += [ROOT/'docs/validation/daedalus-rudder-four-outputs.csv',SOURCE/'report/comparison.csv']
    if args['stage']=='euler_rate_probe':folders += [STUDY/'inspect']
    for folder in folders:inputs += [p for p in folder.iterdir() if p.suffix in ('.json','.npz')]
    run(STUDY,args['tag'],inputs,globals()[args['stage']],args,__file__)


if __name__=='__main__':main()
