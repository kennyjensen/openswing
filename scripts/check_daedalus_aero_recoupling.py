"""Fully recouple 164 aerodynamic panels on the fixed original structure.

Solve the complete modified harmonic equations by residual corrections using
the original descriptor as preconditioner. A constant residual offset holds
the original equilibrium; this is not a retrimmed physical aircraft case.
Each circulation/load direction is a separate bounded, serial job.
"""
import argparse
from check_daedalus_load_sensitivity import ROOT, SOURCE, read
from check_daedalus_roll_aero import Trial, STUDY as PRIOR, SAMPLES, FREQUENCY
from daedalus_bounded_job import run

STUDY = ROOT/'artifacts/daedalus-aero-recoupling-20261114'


def accepted(folder):
    terminal=read(folder/'terminal.json')
    assert terminal['returncode']==0 and terminal['process_reaped'] and terminal['inputs_unchanged'],folder
    return read(folder/'result.json')


def arrays(folder):
    import numpy as np
    accepted(folder)
    with np.load(folder/'arrays.npz') as packet: return dict(packet)


def label(args): return 'fine' if args['width']==5e-4 else 'wide'


def update_folder(index):
    return STUDY/('update-0-fine-v2' if index==0 else f'update-{index}-fine')


def candidate(args):
    if args['iteration']==0: return arrays(STUDY/'base')['state']
    return arrays(update_folder(args['iteration']-1))['next_state']


def trial_at(state):
    import numpy as np
    trial=Trial(2)
    np.testing.assert_array_equal(trial.z,arrays(STUDY/'base')['state'])
    trial.z=state.copy(); trial.zdot=1j*trial.omega*trial.z
    return trial


def base(folder,args):
    import numpy as np
    trial=Trial(2); saved=arrays(PRIOR/'shape-2'); previous=arrays(PRIOR/'project')
    np.testing.assert_array_equal(trial.z,saved['full_state'])
    result=trial.evaluate(saved['gamma'])[0]
    error=float(max(abs(result['circulation_residual']))); assert error<1e-10
    with np.load(SOURCE/'assembled-6.7/maps.npz') as maps:
        C=maps['C']; B=maps['B'][:,0]
    np.savez_compressed(folder/'arrays.npz',state=trial.z,coarse_gamma=trial.initial_gamma,
        fine_gamma=saved['gamma'],jacobian=saved['jacobian'],lag_diagonal=saved['lag_diagonal'],
        baseline_fine_response=saved['gamma_response'],C=C,B=B,
        expected_load_difference=previous['load_differences'][:,:6].sum(axis=1),
        expected_first_state=trial.z+previous['total_correction_states'][:,0])
    return dict(frequency_hz=FREQUENCY,physical_panels=164,auxiliary_coarse_panels=82,
        structural_coordinates=2044,steady_fine_circulation_residual=error,
        full_original_residual=trial.full_residual,
        qualification='Fixed original geometry, controls and equilibrium. Fine mean-load differences are held by a constant residual offset, not a physical retrim.')


def shape(folder,args):
    import numpy as np
    state=candidate(args); trial=trial_at(state); saved=arrays(STUDY/'base')
    value=np.zeros(164); width=args['width']; part=args['part']; assert part in (0,1)
    for offset,weight in [(-2,1),(-1,-8),(1,8),(2,-1)]:
        value+=weight*trial.evaluate(saved['fine_gamma'],part=part,amplitude=offset*width)[0]['circulation_residual']/(12*width)
    np.savez_compressed(folder/'arrays.npz',state=state,shape=value)
    return dict(iteration=args['iteration'],part=part,width=width,aerodynamic_evaluations=trial.calls)


def circulation(folder,args):
    import numpy as np
    import scipy.sparse as sp
    state=candidate(args); saved=arrays(STUDY/'base'); omega=2*np.pi*FREQUENCY
    operator=saved['jacobian']+1j*omega*np.diag(saved['lag_diagonal'])
    if args['iteration']==0 and label(args)=='fine':
        response=saved['baseline_fine_response']
        rhs=arrays(PRIOR/'shape-2')['shape_rhs']; reused=True
    else:
        rhs=np.zeros(164,complex)
        for part in (0,1):
            packet=arrays(STUDY/f"shape-{args['iteration']}-{part}-{label(args)}")
            np.testing.assert_array_equal(packet['state'],state)
            rhs+=(1 if part==0 else 1j)*packet['shape']
        response=np.linalg.solve(operator,-rhs); reused=False
    residual=float(max(abs(operator@response+rhs))); assert residual<1e-10
    a,m=(sp.load_npz(SOURCE/'assembled-6.7'/p) for p in ('A.npz','M.npz'))
    coarse_error=float(max(abs(((1j*omega*m-a)@state-saved['B'])[1296:1378])))
    assert coarse_error<2e-10
    # Literal source layout: physical circulation = scaled state * gamma_scale.
    layout=read(SOURCE/'mass-6.7/layout.json')['circulation']
    assert layout['start']==1296 and layout['width']==82
    if args['iteration']>0:
        first=arrays(STUDY/'circulation-0-fine')
        np.testing.assert_allclose(first['coarse_response'],first['state'][1296:1378]*layout['scale'],atol=1e-14,rtol=1e-14)
    np.savez_compressed(folder/'arrays.npz',state=state,fine_response=response,
        coarse_response=state[1296:1378]*layout['scale'])
    return dict(iteration=args['iteration'],width=args['width'],fine_circulation_residual=residual,
        coarse_auxiliary_circulation_residual=coarse_error,reused_first_direction=reused)


def transferred(trial,gamma,response,part,amplitude):
    """Complete external loads with conservative moving-arm transfer."""
    import numpy as np
    from check_daedalus_load_sensitivity import groups
    n=trial.n; component=(np.real,np.imag)[part]
    value=gamma+amplitude*component(response)
    rate=amplitude*component(1j*trial.omega*response)
    aero,_,fine,state,options,points=trial.evaluate(value,rate,part=part,amplitude=amplitude)
    coarse=n.deformed_meshes(state.r,state.Q,n.geometry(state.r,state.Q))
    force=np.zeros_like(state.r); moment=np.zeros_like(force); closure=0.
    for parent,child in zip(coarse,fine):
        strips=[s for s in aero['strips'] if s['beam']==parent.beam.index]
        f=np.array([s['force'] for s in strips]); c=np.array([s['moment'] for s in strips])
        count=len(parent.tm); q=trial.factor if parent.beam.lifting else 1
        assert len(f)==count*q
        arm=child.rm.reshape(count,q,3)-parent.rm[:,None,:]
        ff=f.reshape(count,q,3).sum(axis=1)
        cc=(c.reshape(count,q,3)+np.cross(arm,f.reshape(count,q,3))).sum(axis=1)
        nf=np.zeros_like(force); nm=np.zeros_like(moment)
        for ids,v,w in n.steady_lifting_wrenches(parent,ff,cc):
            np.add.at(nf,ids,v); np.add.at(nm,ids,w)
        expected=np.r_[f.sum(axis=0),(c+np.cross(child.rm-n.model.reference[1],f)).sum(axis=0)]
        actual=np.r_[nf.sum(axis=0),(nm+np.cross(state.r-n.model.reference[1],nf)).sum(axis=0)]
        np.testing.assert_allclose(actual,expected,atol=2e-10,rtol=2e-11)
        closure=max(closure,float(max(abs(actual-expected)))); force+=nf; moment+=nm
    def point(node,position,f,c):
        force[node]+=f; moment[node]+=c+np.cross(np.asarray(position)-state.r[node],f)
    for row,position,f in zip(n.weights,points,aero['point_forces']):
        point(n.node(*row[:2]),position,np.asarray(f),np.zeros(3))
    for entry in aero['body_shoulders']:
        point(n.node(entry['beam'],entry['t']),entry['position'],np.asarray(entry['force']),np.zeros(3))
    for entry in aero['engines']:
        point(n.node(entry['beam'],entry['t']),entry['position'],np.asarray(entry['force']),np.asarray(entry['moment']))
    wrench=np.r_[force.sum(axis=0),(moment+np.cross(state.r-n.model.reference[1],force)).sum(axis=0)]
    expected=np.r_[aero['force'],aero['moment']]
    np.testing.assert_allclose(wrench,expected,atol=2e-10,rtol=2e-11)
    closure=max(closure,float(max(abs(wrench-expected))))
    out=np.zeros(trial.system.size)
    out[6*n.ne:6*n.ne+3*n.nn]=force.ravel()/n.F
    out[6*n.ne+3*n.nn:6*(n.ne+n.nn)]=moment.ravel()/(n.F*n.L)
    out[n.operating_start:n.size]=wrench/np.r_[np.full(3,n.F),np.full(3,n.F*n.L)]
    native_error=None
    if trial.factor==1:
        x=state.x.copy(); x[n.gamma_start:n.operating_start]=value/n.gamma_scale
        _,data=n.residual(x,detail=True,**dict(options,circulation_rate=rate))
        native,_,_=groups(trial.system,data)
        expected=sum(v for k,v in native.items() if k!='real_mass_gravity_applied' and not k.endswith(':stall'))
        native_error=float(max(abs(out-expected))); assert native_error<2e-10
    return out,np.asarray(aero['circulation_residual']),wrench,closure,native_error


def loads(folder,args):
    import numpy as np
    packet=arrays(STUDY/f"circulation-{args['iteration']}-{label(args)}")
    state=candidate(args); np.testing.assert_array_equal(packet['state'],state)
    trial=trial_at(state); saved=arrays(STUDY/'base'); derivatives=[]; closures=[]; native=[]; gamma_errors=[]
    width=args['width']; part=args['part']; assert part in (0,1)
    for factor,name in ((1,'coarse'),(2,'fine')):
        trial.factor=factor; gamma=saved[f'{name}_gamma']; response=packet[f'{name}_response']
        value=np.zeros(2044); circ=np.zeros(len(gamma)); wrench=np.zeros(6)
        for offset,weight in [(-2,1),(-1,-8),(1,8),(2,-1)]:
            out,g,w,c,e=transferred(trial,gamma,response,part,offset*width)
            value+=weight*out/(12*width); circ+=weight*g/(12*width); wrench+=weight*w/(12*width)
            closures.append(c)
            if e is not None: native.append(e)
        gamma_errors.append(float(max(abs(circ)))); derivatives.append((value,wrench))
    assert max(gamma_errors)<2e-8,gamma_errors
    multiplier=1 if part==0 else 1j
    difference=multiplier*(derivatives[1][0]-derivatives[0][0])
    assert np.all(difference[1296:1378]==0)
    np.savez_compressed(folder/'arrays.npz',state=state,difference=difference,
        coarse_loads=multiplier*derivatives[0][0],fine_loads=multiplier*derivatives[1][0],
        wrench_difference=multiplier*(derivatives[1][1]-derivatives[0][1]))
    return dict(iteration=args['iteration'],part=part,width=width,aerodynamic_evaluations=trial.calls,
        native_network_comparisons=len(native),native_transfer_error=max(native),
        transfer_wrench_closure=max(closures),coarse_and_fine_circulation_directional_errors=gamma_errors)


def update(folder,args):
    import numpy as np
    import scipy.sparse as sp
    from openswing.frequency_response import harmonic_solve
    from openswing.harmonic_structure import ReusableBeamStructure
    state=candidate(args); saved=arrays(STUDY/'base'); delta=np.zeros(2044,complex)
    for part in (0,1):
        packet=arrays(STUDY/f"loads-{args['iteration']}-{part}-{label(args)}")
        np.testing.assert_array_equal(packet['state'],state); delta+=packet['difference']
    a,m=(sp.load_npz(SOURCE/'assembled-6.7'/p) for p in ('A.npz','M.npz'))
    for matrix in (a,m):
        for data in (matrix.data,matrix.indices,matrix.indptr): data.flags.writeable=False
    structure=ReusableBeamStructure(a,m,np.r_[np.arange(618),np.arange(1266,1296)],
        np.arange(1266),np.arange(1384,2032),np.arange(1384,2032))
    omega=2*np.pi*FREQUENCY; K=1j*omega*m-a; residual=K@state-saved['B']-delta
    correction,checks=harmonic_solve(a,m,-residual,omega,_structure=structure)
    next_state=state+correction; output=saved['C']@state; next_output=saved['C']@next_state
    absolute=float(max(abs(residual))); relative=absolute/max(float(max(abs(saved['B']))),float(max(abs(K@state))))
    output_change=float(max(abs(next_output-output)/abs(output)))
    original_rows=np.r_[np.arange(0,618),np.arange(1266,1378),np.arange(1384,2044)]
    assert max(abs(delta[original_rows]))==0
    assert max(abs((K@next_state-saved['B']-delta)))<2e-10
    first_replay=None
    if args['iteration']==0:
        first_replay=dict(load=float(max(abs(delta-saved['expected_load_difference']))),state=float(max(abs(next_state-saved['expected_first_state']))))
        assert first_replay['load']<2e-10 and first_replay['state']<2e-8,first_replay
    np.savez_compressed(folder/'arrays.npz',state=state,next_state=next_state,residual=residual,
        load_difference=delta,correction=correction,output=output,next_output=next_output)
    result=dict(iteration=args['iteration'],width=args['width'],frequency_hz=FREQUENCY,
        modified_full_residual=absolute,modified_relative_residual=relative,
        next_output_relative_correction=output_change,output_magnitude=abs(output).tolist(),
        next_output_magnitude=abs(next_output).tolist(),linear_solve_checks=checks,
        first_variation_replay=first_replay,
        converged=bool(absolute<2e-11 and relative<2e-8 and output_change<2e-7))
    print(result,flush=True); return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage',choices=['base','shape','circulation','loads','update'])
    parser.add_argument('--tag',required=True); parser.add_argument('--iteration',type=int,default=0)
    parser.add_argument('--part',type=int,choices=[0,1]); parser.add_argument('--width',type=float,choices=[1e-3,5e-4],default=5e-4)
    args=vars(parser.parse_args()); assert args['iteration']>=0
    inputs=[ROOT/'scripts'/p for p in ('check_daedalus_roll_aero.py','check_daedalus_aero_resolution.py',
        'check_daedalus_wing_paper.py','check_daedalus_source_operator.py')]
    inputs+=[ROOT/'examples/dae.asw',ROOT/'examples/dae-cruise-physical-mesh-project.json',SOURCE/'trim-6.7-1/state.json',SOURCE/'mass-6.7/layout.json',
        ROOT/'docs/validation/ISAE_STATUS.md',ROOT/'docs/validation/aswing-authoritative-sources.json',
        ROOT/'reference/aswing-authoritative-20261108/drela-aswing-steady.pdf',ROOT/'reference/aswing-authoritative-20261108/drela-aswing-unsteady.pdf',
        SAMPLES/'coarse-samples/arrays.npz',SAMPLES/'fine-samples/arrays.npz']
    inputs+=[SOURCE/'assembled-6.7'/p for p in ('A.npz','M.npz','maps.npz')]+list((ROOT/'openswing').glob('*.py'))
    inputs+=[PRIOR/name/p for name in ('shape-2','project') for p in ('arrays.npz','result.json','terminal.json')]
    dependencies=[]
    if args['stage']!='base': dependencies.append('base')
    if args['iteration']>0:
        dependencies.append(update_folder(args['iteration']-1).name)
        if args['stage']=='circulation': dependencies.append('circulation-0-fine')
    if args['stage']=='circulation' and not (args['iteration']==0 and label(args)=='fine'):
        dependencies += [f"shape-{args['iteration']}-{part}-{label(args)}" for part in (0,1)]
    if args['stage']=='loads': dependencies.append(f"circulation-{args['iteration']}-{label(args)}")
    if args['stage']=='update': dependencies += [f"loads-{args['iteration']}-{part}-{label(args)}" for part in (0,1)]
    inputs += [STUDY/name/p for name in dependencies for p in ('arrays.npz','result.json','terminal.json')]
    run(STUDY,args['tag'],inputs,globals()[args['stage']],args,__file__)


if __name__=='__main__': main()
