"""Bounded transmission-zero diagnostics of the complete Daedalus descriptor.

The augmented pencil follows directly from (s M - A) z = B u and C z = 0.
Only the previously verified cyclic-coordinate elimination is used. No mode
truncation, aircraft-property change or reference-curve fit is performed.
"""
import argparse
from check_daedalus_load_sensitivity import ROOT,SOURCE,read
from daedalus_bounded_job import run

STUDY=ROOT/'artifacts/daedalus-transmission-zeros-20261114'
CHANNELS=['yaw_rate','roll_rate','sideslip','bank']


def query(folder,args):
    import numpy as np
    import scipy.sparse as sp
    from scipy.sparse.linalg import LinearOperator,eigs,onenormest
    from check_daedalus_source_modes import matrices
    from openswing.harmonic_structure import ReusableBeamStructure
    a,m,b,c,keep=matrices();output=c[CHANNELS.index(args['channel'])]
    output_scale=np.linalg.norm(output);assert output_scale>0
    az=sp.bmat([[a,sp.csc_matrix(b[:,None])],
               [sp.csc_matrix(-output[None,:]/output_scale),sp.csc_matrix((1,1))]],format='csc')
    mz=sp.block_diag((m,sp.csc_matrix((1,1))),format='csc')
    shift=complex(args['real_shift'],2*np.pi*args['frequency'])
    # A direct augmented factor fills too much under the host's memory cap.
    # Use exact existing beam elimination and a scalar Schur complement for
    # the output constraint. This changes no matrix entry or selected state.
    for matrix in (a,m):
        for array in (matrix.data,matrix.indices,matrix.indptr):array.flags.writeable=False
    structure=ReusableBeamStructure(a,m,np.r_[np.arange(618),np.arange(1266,1296)],
        np.arange(1266),np.arange(1384,2032),np.arange(1384,2032))
    k=(shift*m-a).tocsc();rows=np.maximum(abs(k).max(axis=1).toarray().ravel(),1e-30)
    rowed=sp.diags(1/rows)@k;columns=np.maximum(abs(rowed).max(axis=0).toarray().ravel(),1e-30)
    norm=float(abs(rowed@sp.diags(1/columns)).sum(axis=0).max());del rowed
    factor=structure.factor(a,m,shift,rows,columns)
    inverse=LinearOperator(k.shape,matvec=factor.solve,matmat=factor.solve,
        rmatvec=lambda x:factor.solve(x,trans='H'),rmatmat=lambda x:factor.solve(x,trans='H'),dtype=complex)
    reciprocal=1/(norm*onenormest(inverse,t=1));assert reciprocal>1e-12,reciprocal
    solve=lambda rhs:factor.solve(rhs/rows)/columns
    zb=solve(b);h=output@zb;assert abs(h)>1e-10,h
    assert max(abs(k@zb-b)/rows)<1e-8
    calls=[0]
    def action(v):
        calls[0]+=1
        g=solve(m@v[:-1]);forcing=(output@g)/h
        result=np.r_[-g+zb*forcing,forcing]
        # Re[(Aaug-shift*Maug)^-1 Maug] is a real rational operator.
        return result.real
    op=LinearOperator(az.shape,matvec=action,dtype=float)
    seed=np.random.default_rng(49153).standard_normal(az.shape[0])
    print('real Arnoldi',args['count'],flush=True)
    mu,v=eigs(op,k=args['count'],which='LM',v0=seed,ncv=max(32,2*args['count']+8),tol=2e-12,maxiter=500)
    av=az@v;mv=mz@v
    values=np.sum(mv.conj()*av,axis=0)/np.sum(abs(mv)**2,axis=0)
    order=np.argsort(abs(values-shift));values=values[order];v=v[:,order];mu=mu[order]
    av=az@v;mv=mz@v
    residual=np.linalg.norm(av-mv*values,axis=0)/(np.linalg.norm(av,axis=0)+abs(values)*np.linalg.norm(mv,axis=0))
    rows=[]
    for i,value in enumerate(values):
        state=v[:-1,i];forcing=v[-1,i]
        rows.append(dict(index=i,zero=[float(value.real),float(value.imag)],
            imaginary_frequency_hz=float(value.imag/(2*np.pi)),distance_to_query_shift=float(abs(value-shift)),
            augmented_residual=float(residual[i]),input_magnitude=float(abs(forcing)),
            state_norm_per_input=float(np.linalg.norm(state)/abs(forcing)),
            output_per_input=[float((output@state/forcing).real),float((output@state/forcing).imag)]))
    np.savez_compressed(folder/'arrays.npz',values=values,vectors=v,keep=keep,residual=residual,rational_eigenvalues=mu)
    assert max(residual)<1e-7,residual
    print('shift-invert actions',calls[0],flush=True);print(rows,flush=True)
    return dict(channel=args['channel'],shift=[shift.real,shift.imag],dimension=az.shape[0],
        eigenvalues=rows,shift_invert_actions=calls[0],maximum_augmented_residual=float(max(residual)),
        output_constraint_scale=float(output_scale),
        query_pencil_reciprocal_condition=float(reciprocal),
        query_transfer=[float(h.real),float(h.imag)],
        beam_equations_eliminated=len(structure.rows),
        rational_operator='Re[(Aaug-shift*Maug)^-1 Maug], real Arnoldi; eigenvalues recovered from the original generalized pencil',
        qualification='Zeros of the augmented full descriptor after exact cyclic elimination. Candidates near unobservable poles must be distinguished by direct transfer-function checks; this query alone does not identify a Bode notch or native ASWING zero.')


def verify(folder,args):
    import numpy as np
    import scipy.sparse as sp
    from openswing.frequency_response import harmonic_solve,HarmonicInput
    from openswing.harmonic_structure import ReusableBeamStructure
    from check_daedalus_wing_paper import dynamic
    from check_daedalus_load_sensitivity import groups
    source=STUDY/args['query'];metadata=read(source/'result.json')
    channel=metadata['channel'];selected=CHANNELS.index(channel)
    with np.load(source/'arrays.npz') as archive:
        s=complex(archive['values'][args['index']]);keep=archive['keep']
        vector=archive['vectors'][:,args['index']]
    assert s.imag>0 and abs(vector[-1])>1e-8
    a,m=(sp.load_npz(SOURCE/'assembled-6.7'/name).tocsc() for name in ('A.npz','M.npz'))
    with np.load(SOURCE/'assembled-6.7/maps.npz') as archive:b=archive['B'][:,0];c=archive['C']
    for values in (m.data,m.indices,m.indptr):values.flags.writeable=False
    def direct(value,rhs):
        # Analytical continuation into either half-plane. Move the real part
        # into a real A matrix so every public harmonic-solve gate is retained.
        changed=(a-value.real*m).tocsc()
        for array in (changed.data,changed.indices,changed.indptr):array.flags.writeable=False
        structure=ReusableBeamStructure(changed,m,np.r_[np.arange(618),np.arange(1266,1296)],
            np.arange(1266),np.arange(1384,2032),np.arange(1384,2032))
        result,checks=harmonic_solve(changed,m,rhs,value.imag,_structure=structure)
        return result,checks,changed,structure
    z,checks,changed,structure=direct(s,b);output=c@z
    removed=np.setdiff1d(np.arange(len(b)),keep);reconstructed=np.empty(len(b),complex)
    reconstructed[keep]=vector[:-1]/vector[-1];k=(s*m-a).tocsc()
    reconstructed[removed]=np.linalg.solve(k[removed,:][:,removed].toarray(),
        b[removed]-k[removed,:][:,keep]@reconstructed[keep])
    state_error=float(max(abs(reconstructed-z)));assert state_error<2e-8,state_error
    assert abs(output[selected])<2e-8,output
    # Transpose adjoint: K.T l = c. The zero derivative is
    # ds/d(epsilon) = l.T delta_R(z,s*z,unit input)/(l.T M z).
    rows=np.maximum(abs(k).max(axis=1).toarray().ravel(),1e-30)
    rowed=sp.diags(1/rows)@k;columns=np.maximum(abs(rowed).max(axis=0).toarray().ravel(),1e-30)
    factor=structure.factor(changed,m,1j*s.imag,rows,columns)
    left=factor.solve(c[selected]/columns,trans='T')/rows
    left_residual=float(np.linalg.norm(k.T@left-c[selected])/(np.linalg.norm(k.T@left)+np.linalg.norm(c[selected])))
    assert left_residual<1e-8,left_residual
    overlap=left@(m@z);hprime=-overlap;assert abs(overlap)>1e-10
    del factor,structure,changed,rowed
    derivative_checks=[]
    for h in (1e-4*max(1.,abs(s)),5e-5*max(1.,abs(s))):
        samples=[]
        for sign in (-1,1):
            state,diagnostics,_,_=direct(s+sign*h,b)
            samples.append(c[selected]@state)
        estimate=(samples[1]-samples[0])/(2*h)
        error=float(abs(estimate-hprime)/abs(hprime));assert error<2e-6,error
        derivative_checks.append(dict(step=h,relative_derivative_error=error))
    system=dynamic();n=system.network;zero=np.zeros(system.size)
    assert system.size==len(b)==2044
    forcing,_=HarmonicInput(system,'control.3',0).at_frequency(s.imag)
    def sample(q,dq,drive):
        state,_,options=system.physical_state(q,dq,drive)
        residual,data=n.residual(state.x,detail=True,**options)
        loads,wrenches,diagnostics=groups(system,data)
        return loads,wrenches,data,residual
    base=sample(zero,zero,None);assert max(abs(base[3]))<1e-9
    keys=list(base[0]);stencils=[];wrench_stencils=[];full_stencils=[]
    for h in (1e-3,5e-4):
        loads=np.zeros((len(b),len(keys)),complex);wrenches=np.zeros((6,len(keys)),complex)
        complete=np.zeros(len(b),complex)
        for part,component in enumerate((np.real,np.imag)):
            for offset,weight in [(-2,1),(-1,-8),(1,8),(2,-1)]:
                scale=h*offset;values,moments,_,residual=sample(
                    scale*component(z),scale*component(s*z),forcing(part,scale))
                multiplier=weight/(12*h)*(1 if part==0 else 1j)
                loads+=multiplier*np.column_stack([values[key] for key in keys])
                wrenches+=multiplier*np.column_stack([moments[key] for key in keys])
                complete[:n.size]+=multiplier*residual
        stencils.append(loads);wrench_stencils.append(wrenches);full_stencils.append(complete)
    loads=stencils[-1];wrenches=wrench_stencils[-1]
    step_error=float(np.max(abs(loads-stencils[0])));assert step_error<2e-8,step_error
    net_wrench=float(max(abs(wrenches.sum(axis=1))));assert net_wrench<2e-6,net_wrench
    # n.residual covers the structural/circulation/global rows. Full frame and
    # local-velocity kinematics are covered by the direct descriptor solve.
    nonlinear_closure=float(max(abs(full_stencils[-1][:n.size])));assert nonlinear_closure<2e-8
    cursor=n.gamma_start;all_lag=np.zeros(len(b),complex)
    for mesh in base[2]['meshes']:
        if not mesh.beam.lifting:continue
        strips=base[2]['aero']['strips'][n.beam_elements[mesh.beam.index]]
        speed=np.array([strip['normal_speed'] for strip in strips]);stop=cursor+len(strips)
        action=np.zeros(len(b),complex)
        action[cursor:stop]=-2/np.pi*n.gamma_scale*s*z[cursor:stop]/speed/base[2]['condition'].speed
        all_lag+=action;keys.append(f'beam{mesh.beam.index}:circulation_lag')
        loads=np.column_stack([loads,action]);wrenches=np.column_stack([wrenches,np.zeros(6)])
        cursor=stop
    expected=np.zeros(len(b),complex);expected[n.gamma_start:cursor]=-s*(m[n.gamma_start:cursor,:]@z)
    lag_error=float(max(abs(all_lag-expected)));assert lag_error<2e-10
    derivatives=left@loads/overlap
    pose=z[:6*n.nn].reshape(n.nn,6);dr=n.L*pose[:,:3]
    node_summary={}
    for name,beam,t in [('wing_root',1,0),('wing_tip',1,56),('boom_mount',4,2.5),('boom_tip',4,20),('fin_root',3,0)]:
        node=n.node(beam,t);node_summary[name]=dict(node=int(node),
            position_real_ft=dr[node].real.tolist(),position_imag_ft=dr[node].imag.tolist(),
            rotation_real_deg=np.rad2deg(pose[node,3:].real).tolist(),rotation_imag_deg=np.rad2deg(pose[node,3:].imag).tolist())
    component_rows=[]
    for i,(key,d) in enumerate(zip(keys,derivatives)):
        component_rows.append(dict(component=key,zero_derivative=[float(d.real),float(d.imag)],
            real_part_change_per_1_percent=float(.01*d.real),
            frequency_hz_change_per_1_percent=float(.01*d.imag/(2*np.pi)),
            wrench_real=wrenches[:,i].real.tolist(),wrench_imag=wrenches[:,i].imag.tolist()))
    np.savez_compressed(folder/'arrays.npz',state=z,left=left,component_residuals=loads,
        wrenches=wrenches,zero_derivatives=derivatives,positions=system.r0,ends=n.ends,
        beam=np.concatenate([np.full(len(mesh.tm),mesh.beam.index) for mesh in n.meshes]),displacement=dr)
    result=dict(channel=channel,zero=[s.real,s.imag],imaginary_frequency_hz=s.imag/(2*np.pi),
        zero_distance_from_imaginary_axis=abs(s.real),output_real=output.real.tolist(),output_imag=output.imag.tolist(),
        output_magnitude=abs(output).tolist(),full_solve_checks=checks,query_state_difference=state_error,
        transpose_adjoint_residual=left_residual,transfer_derivative=[float(hprime.real),float(hprime.imag)],
        transfer_derivative_checks=derivative_checks,load_stencil_change=step_error,
        nonlinear_residual_directional_closure=nonlinear_closure,net_wrench_error=net_wrench,
        lag_action_error=lag_error,components=component_rows,node_motion=node_summary,
        nonlinear_evaluations=17,full_resolvent_solves=5,
        qualification='Unit F3 exponential input exp(s*t) at a transmission zero, not a sinusoidal Bode response or a natural eigenmode. Component multipliers are fixed-equilibrium affine sensitivities, including input derivatives. No native ASWING zero or fitted physics is inferred.')
    print('verified',channel,s,'outputs',abs(output),flush=True)
    print('largest real-part sensitivities',sorted(component_rows,key=lambda r:abs(r['real_part_change_per_1_percent']),reverse=True)[:8],flush=True)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('stage',choices=['query','verify'])
    parser.add_argument('--tag',required=True);parser.add_argument('--channel',choices=CHANNELS,default='yaw_rate')
    parser.add_argument('--frequency',type=float,default=1.15737773741517)
    parser.add_argument('--real-shift',type=float,default=-.1);parser.add_argument('--count',type=int,default=8)
    parser.add_argument('--query',default='yaw-query-structured');parser.add_argument('--index',type=int,default=0)
    args=vars(parser.parse_args());assert 1<=args['count']<=40
    inputs=[ROOT/'scripts/check_daedalus_source_modes.py',ROOT/'docs/validation/aswing-authoritative-sources.json',
        ROOT/'reference/aswing-authoritative-20261108/drela-aswing-unsteady.pdf',SOURCE/'mass-6.7/layout.json']
    inputs += [SOURCE/'assembled-6.7'/name for name in ('A.npz','M.npz','maps.npz')]
    if args['stage']=='verify':
        inputs += [STUDY/args['query']/name for name in ('arrays.npz','result.json','terminal.json')]
        inputs += [ROOT/'scripts/check_daedalus_wing_paper.py',ROOT/'scripts/check_daedalus_source_operator.py',
            ROOT/'examples/dae.asw',ROOT/'examples/dae-cruise-physical-mesh-project.json',SOURCE/'trim-6.7-1/state.json']
        inputs += list((ROOT/'openswing').glob('*.py'))
    run(STUDY,args['tag'],inputs,globals()[args['stage']],args,__file__)


if __name__=='__main__':main()
