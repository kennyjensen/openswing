"""Trace wing-root rotation through the literal fairing/forward-boom mounts."""
import argparse
import json
import os
from pathlib import Path
import resource
import signal
import sys
import time
import traceback

from check_daedalus_load_sensitivity import ROOT,SOURCE,LIMITS,read,write,pin,utc

STUDY=ROOT/'artifacts/daedalus-wing-mount-20261113'
SAVED=ROOT/'artifacts/daedalus-load-sensitivity-20261113'
TERMS=ROOT/'artifacts/daedalus-wing-lift-terms-20261113'
CASES={'slow':(.2,'slow-animation'),'dip':(1.15737773741517,'reference-dip')}


def inspect(folder,args):
    import numpy as np
    import scipy.sparse as sp
    from check_daedalus_wing_paper import dynamic
    from openswing.frequency_response import harmonic_solve
    from openswing.harmonic_structure import ReusableBeamStructure
    system=dynamic();n=system.network;frequency,tag=CASES[args.case];omega=2*np.pi*frequency
    z=np.load(SAVED/tag/'arrays.npz')['state'];pose=z[:6*n.nn].reshape(n.nn,6)
    velocity,rates=z[system.velocity_start:system.frame_start].reshape(2,n.nn,3)
    landmarks=[('frame_ground',5,-15.6),('pilot_attachment',5,-13.2),('fairing_top',5,-10.),
        ('boom_fairing',4,2.5),('boom_wing',4,0.),('wing_root',1,0.)]
    nodes=np.array([n.node(beam,t) for _,beam,t in landmarks]);root=nodes[-1]
    assert max(abs(pose[nodes[0]]))<2e-10
    joint_error=max(float(max(abs(pose[nodes[a],3:]-pose[nodes[b],3:]))) for a,b in [(2,3),(4,5)])
    assert joint_error<2e-10,joint_error
    kinematics=float(np.max(abs(system.W*rates[nodes]-1j*omega*pose[nodes,3:])))
    assert kinematics<2e-10,kinematics
    rotations=np.array([pose[nodes[2],3:]-pose[nodes[0],3:],pose[nodes[4],3:]-pose[nodes[3],3:]])
    labels=['fairing','forward_boom']
    closure=float(max(abs(rotations.sum(axis=0)-pose[root,3:])));assert closure<2e-10,closure
    zero=np.zeros(system.size);state,_,options=system.physical_state(zero,zero,None)
    residual,data=n.residual(state.x,detail=True,**options);assert max(abs(residual))<1e-9
    r,q,force0,moment0,_,_=n.unpack(state.x)
    # An independently assembled diagonal compliance uses the literal endpoint
    # material values. Compare both a straight-beam integral and the matrix
    # curvature identity (steady Eq.52), whose second-order discretization
    # differs from the production Euler Eq.53.
    _,_,ra,rb,*_=n.geometry(r,q)
    dtheta=pose[:,3:];internal=z[6*n.nn:6*(n.nn+n.ne)].reshape(n.ne,6)
    dm=internal[:,3:]*n.F*n.L
    def cross_matrix(v):
        x,y,z=v
        return np.array([[0,-z,y],[z,0,-x],[-y,x,0]],complex)
    compliance_rows=[];curvature_rows=[];straight=[]
    for label,beam,lower,upper,direction in [('fairing',5,-15.6,-10.,1),('forward_boom',4,0.,2.5,-1)]:
        mesh,=[m for m in n.meshes if m.beam.index==beam]
        local=np.flatnonzero((mesh.t0>=lower-1e-10)&(mesh.t1<=upper+1e-10))
        elements=n.beam_elements[beam].start+local
        coefficients=np.column_stack([(1/mesh.beam.value(name,mesh.t0[local],side='right')+
            1/mesh.beam.value(name,mesh.t1[local],side='left'))/2 for name in ('EIcc','GJ','EInn')])
        contribution=np.zeros(3,complex)
        for e,comp in zip(elements,coefficients):
            a,b=n.a[e],n.b[e];dRa=cross_matrix(dtheta[a])@ra[e];dRb=cross_matrix(dtheta[b])@rb[e]
            T=(ra[e].T+rb[e].T)/2;dT=(dRa.T+dRb.T)/2
            delta_material_moment=dT@moment0[e]+T@dm[e]
            expected=comp*delta_material_moment
            derivative=(dT@(rb[e]-ra[e])+T@(dRb-dRa))/n.ds[e]
            measured=np.array([derivative[2,1]-derivative[1,2],derivative[0,2]-derivative[2,0],derivative[1,0]-derivative[0,1]])/2
            curvature_rows.append(dict(path=label,element=int(e),expected_real=expected.real.tolist(),expected_imag=expected.imag.tolist(),
                matrix_curvature_real=measured.real.tolist(),matrix_curvature_imag=measured.imag.tolist(),
                absolute_difference=float(max(abs(measured-expected)))))
            # Spatial constant-axis approximation, with geometric preload
            # coupling intentionally excluded and disclosed in the result.
            compliance_spatial=(ra[e]*comp[None,:])@ra[e].T
            contribution+=direction*n.ds[e]*compliance_spatial@dm[e]
            compliance_rows.append(dict(path=label,element=int(e),ds=float(n.ds[e]),diagonal_stiffness=(1/comp).tolist()))
        straight.append(contribution)
    # Attribute the previously measured root-rotation velocity-load term to
    # these two actual physical paths and each body-axis rotation component.
    parent=np.load(TERMS/args.case/'arrays.npz');points=np.load(TERMS/(args.case+'-split')/'arrays.npz')['positions']
    rho=data['aero']['atmosphere']['density'];sl=n.beam_elements[1]
    terms=[f'{path}_{axis}' for path in labels for axis in 'xyz']
    rot=np.zeros((6,3),complex)
    for path in range(2):
        for axis in range(3):rot[3*path+axis,axis]=rotations[path,axis]
    flow=-np.cross((1j*omega*rot)[:,None,:],(points-system.r0[root])[None,:,:])
    f=rho*(parent['base_gamma']*parent['base_length'])[None,:,None]*np.cross(flow,parent['base_span'][None,:,:])
    m=np.cross(parent['base_arm'][None,:,:],f)
    nf=np.zeros((6,n.nn,3),complex);nm=np.zeros_like(nf)
    for ids in (n.a[sl],n.b[sl]):
        for j in range(6):np.add.at(nf[j],ids,f[j]/2);np.add.at(nm[j],ids,m[j]/2)
    wrench=np.concatenate([nf.sum(axis=1),(nm+np.cross((r-n.model.reference[1])[None,:,:],nf)).sum(axis=1)],axis=1).T
    loads=np.zeros((system.size,6),complex)
    loads[6*n.ne:6*n.ne+3*n.nn]=nf.reshape(6,-1).T/n.F
    loads[6*n.ne+3*n.nn:6*(n.ne+n.nn)]=nm.reshape(6,-1).T/(n.F*n.L)
    loads[n.operating_start:n.size]=wrench/np.array([n.F]*3+[n.F*n.L]*3)[:,None]
    original=np.load(TERMS/(args.case+'-elastic')/'arrays.npz')
    load_error=float(max(abs(loads.sum(axis=1)-original['residuals'][:,1])));assert load_error<2e-11,load_error
    a,m=(sp.load_npz(SOURCE/'assembled-6.7'/name) for name in ('A.npz','M.npz'))
    for pencil in (a,m):
        for v in (pencil.data,pencil.indices,pencil.indptr):v.flags.writeable=False
    maps=np.load(SOURCE/'assembled-6.7/maps.npz')
    structure=ReusableBeamStructure(a,m,np.r_[np.arange(618),np.arange(1266,1296)],np.arange(1266),np.arange(1384,2032),np.arange(1384,2032))
    dz,checks=harmonic_solve(a,m,loads,omega,_structure=structure);dy=maps['C']@dz;output=maps['C']@z
    output_error=float(max(abs(dy.sum(axis=1)-original['output_derivatives'][:,1])));assert output_error<2e-9,output_error
    def record(v):return dict(real=np.asarray(v).real.tolist(),imag=np.asarray(v).imag.tolist())
    expected=np.array([np.array(row['expected_real'])+1j*np.array(row['expected_imag']) for row in curvature_rows])
    measured=np.array([np.array(row['matrix_curvature_real'])+1j*np.array(row['matrix_curvature_imag']) for row in curvature_rows])
    relative=float(np.linalg.norm(measured-expected)/np.linalg.norm(expected))
    np.savez_compressed(folder/'arrays.npz',state=z,nodes=nodes,path_rotations=rotations,straight_integrals=np.array(straight),
        residuals=loads,output_derivatives=dy,output=output,wrenches=wrench,curvature_expected=expected,curvature_matrix=measured)
    result=dict(frequency_hz=frequency,landmarks=[dict(name=name,beam=beam,t=t,node=int(node),
        rotation_deg=record(pose[node,3:]*180/np.pi),rate_deg_s=record(system.W*rates[node]*180/np.pi)) for (name,beam,t),node in zip(landmarks,nodes)],
        paths=labels,path_rotation_deg=record(rotations*180/np.pi),straight_moment_integral_deg=record(np.array(straight)*180/np.pi),
        stiffness_samples=compliance_rows,curvature_comparison=curvature_rows,matrix_curvature_relative_difference=relative,
        joint_rotation_error=joint_error,rate_kinematic_error=kinematics,path_rotation_closure_error=closure,
        load_partition_error=load_error,output_partition_error=output_error,solve_checks=checks,
        terms=terms,log_magnitude_sensitivity=np.real(dy/output[:,None]).tolist(),
        qualification='Actual loaded-response path and differential-load accounting. The diagonal material compliance is independently assembled. Matrix Eq52 and straight-axis integrals are comparisons with different discretization/geometric approximations; neither is substituted for the full source Eq53 operator. No stiffness, joint or flight-frame setting is changed.')
    print(json.dumps(dict(frequency_hz=frequency,path_rotation_deg=result['path_rotation_deg'],straight_integral=result['straight_moment_integral_deg'],
        curvature_relative=relative,terms=terms,yaw_sensitivity=result['log_magnitude_sensitivity'][0])),flush=True)
    return result


def layout(system,path):
    import numpy as np
    n=system.network;beam=5 if path=='fairing' else 4;t,nodes=n.station_nodes[beam]
    cut=n.node(5,-15.6) if path=='fairing' else n.node(4,2.5)
    target=n.node(5,-10.) if path=='fairing' else n.node(4,0.)
    free=nodes[nodes!=cut] if path=='fairing' else nodes[t<2.5]
    eligible=np.r_[cut,free]
    elements=np.flatnonzero(np.isin(n.a,eligible)&np.isin(n.b,eligible))
    assert len(elements)==len(free)
    rows=np.r_[(6*elements[:,None]+np.arange(6)).ravel(),(6*n.ne+3*free[:,None]+np.arange(3)).ravel(),
        (6*n.ne+3*n.nn+3*free[:,None]+np.arange(3)).ravel()]
    columns=np.r_[(6*free[:,None]+np.arange(6)).ravel(),(6*n.nn+6*elements[:,None]+np.arange(6)).ravel()]
    return cut,target,free,elements,rows,columns,6*cut+np.arange(6)


def assemble(folder,args):
    import numpy as np
    import scipy.sparse as sp
    from check_daedalus_wing_paper import dynamic
    from check_daedalus_boom_drivers import mechanical_function
    system=dynamic();n=system.network
    cut,target,free,elements,rows,columns,root=layout(system,args.path)
    selected=np.r_[columns,root];function=mechanical_function(system,rows);zero=np.zeros(system.size)
    estimates=[]
    for step in (1e-5,5e-6):
        matrix=np.empty((len(rows),len(selected)))
        for index,column in enumerate(selected):
            d=zero.copy();d[column]=step
            matrix[:,index]=(8*(function(d)-function(-d))-(function(2*d)-function(-2*d)))/(12*step)
        estimates.append(matrix)
    error=float(np.max(abs(estimates[1]-estimates[0])));assert error<2e-8,error
    matrix=estimates[-1];saved=sp.load_npz(SOURCE/'assembled-6.7/A.npz')
    compatibility_error=float(np.max(abs(matrix[:6*len(elements)]-saved[rows[:6*len(elements)]][:,selected].toarray())))
    assert compatibility_error<2e-8,compatibility_error
    # Verify external and joint-load subtraction at perturbed poses as well
    # as at the base. This includes loaded geometric stiffness in the beam.
    direction=zero.copy();direction[selected]=np.random.default_rng(8967).normal(size=len(selected))
    probe_errors=[]
    for h in (0.,-1e-5,1e-5):
        state,_,options=system.physical_state(h*direction,zero,None)
        residual,data=n.residual(state.x,detail=True,**options)
        residual[6*n.ne:6*n.ne+3*n.nn]-=(data['force']/n.F).ravel()
        residual[6*n.ne+3*n.nn:6*(n.ne+n.nn)]-=(data['moment']/(n.F*n.L)).ravel()
        for reaction in data['reactions']:
            for node,force,moment in [(reaction['node'],reaction['force'],reaction['moment']),
                (reaction['other_node'],reaction['other_force'],reaction['other_moment'])]:
                if node is None:continue
                residual[6*n.ne+3*node:6*n.ne+3*node+3]-=np.array(force)/n.F
                residual[6*n.ne+3*n.nn+3*node:6*n.ne+3*n.nn+3*node+3]-=np.array(moment)/(n.F*n.L)
        assert not any(row['node'] in free for row in data['struts'])
        probe_errors.append(float(max(abs(function(h*direction)-residual[rows]))))
    assert max(probe_errors)<2e-10,probe_errors
    np.savez_compressed(folder/'arrays.npz',matrix=matrix,rows=rows,columns=columns,root=root,selected=selected,
        cut=cut,target=target,free=free,elements=elements)
    return dict(path=args.path,unknowns=len(columns),cut_node=int(cut),target_node=int(target),
        step_difference=error,compatibility_vs_full_matrix_error=compatibility_error,full_residual_subtraction_errors=probe_errors,
        qualification='Loaded beam-only mechanical tangent. All actual aerodynamic and real inertial/gravity forces and joint wrenches are prescribed separately. This reuses production constitutive/chart maps and is not an independent structural reference.')


def loads(folder,args):
    import numpy as np
    from scipy.linalg import lu_factor,lu_solve,get_lapack_funcs
    from check_daedalus_wing_paper import dynamic
    system=dynamic();n=system.network;frequency,tag=CASES[args.case]
    cut,target,free,elements,rows,columns,root=layout(system,args.path)
    matrix=np.load(STUDY/(args.path+'-mechanics')/'arrays.npz')['matrix']
    old=np.load(SAVED/tag/'arrays.npz');z=old['state'];external=old['component_residuals']
    keys=[row['component'] for row in read(SAVED/tag/'result.json')['components']]
    zero=np.zeros(system.size);state,_,options=system.physical_state(zero,zero,None)
    _,base=n.residual(state.x,detail=True,**options)
    pose=z[:6*n.nn].reshape(n.nn,6);dr=n.L*pose[:,:3]
    beam=5 if args.path=='fairing' else 4
    selected_keys=[key for key in keys if key.startswith(f'beam{beam}:') and not key.endswith(':stall')]
    selected_keys+=['points_shoulders_engines','real_mass_gravity_applied']
    pieces={key:external[rows,keys.index(key)].copy() for key in selected_keys}
    # Analytic derivative of T + (r_j-r_i) cross F, plus action/reaction on j.
    reaction_base=6*(n.nn+n.ne)
    joint_checks=[]
    for c in n.constraints:
        i,j,typ=c['a'],c['b'],c['type']
        if j is None or (i not in free and j not in free):continue
        assert typ==0
        start=reaction_base+c['sl'].start
        v0=system.base[start:start+6]*np.r_[[n.F]*3,[n.F*n.L]*3]
        dv=z[start:start+6]*np.r_[[n.F]*3,[n.F*n.L]*3]
        arm=system.r0[j]-system.r0[i];darm=dr[j]-dr[i]
        force=dv[:3];moment=dv[3:]+np.cross(arm,force)+np.cross(darm,v0[:3])
        value=np.zeros(system.size,complex)
        for node,f,m in [(i,force,moment),(j,-force,-dv[3:])]:
            value[6*n.ne+3*node:6*n.ne+3*node+3]+=f/n.F
            value[6*n.ne+3*n.nn+3*node:6*n.ne+3*n.nn+3*node+3]+=m/(n.F*n.L)
        name=f'joint_{i}_{j}';pieces[name]=value[rows]
        # Confirm the unperturbed convention against the actual reaction report.
        native,=[item for item in base['reactions'] if item['node']==i and item['other_node']==j]
        check=float(max(abs(np.r_[native['force'],native['moment']]-np.r_[v0[:3],v0[3:]+np.cross(arm,v0[:3])])));joint_checks.append(check)
        assert check<2e-10,check
    pieces['cut_motion']=matrix[:,-6:]@z[root]
    names=list(pieces);rhs=-np.column_stack(list(pieces.values()));operator=matrix[:,:len(columns)]
    row_scale=np.maximum(np.max(abs(operator),axis=1),1e-30)
    col_scale=np.maximum(np.max(abs(operator/row_scale[:,None]),axis=0),1e-30)
    scaled=operator/row_scale[:,None]/col_scale[None,:];factor=lu_factor(scaled)
    rcond,info=get_lapack_funcs('gecon',(scaled,))(factor[0],np.linalg.norm(scaled,1))
    assert info==0 and rcond>1e-12,(info,rcond)
    response=lu_solve(factor,rhs/row_scale[:,None])/col_scale[:,None]
    residual=float(np.max(abs(operator@response-rhs)));assert residual<2e-9,residual
    error=float(max(abs(response.sum(axis=1)-z[columns])));assert error<2e-8,error
    lookup={int(v):i for i,v in enumerate(columns)}
    rotations=response[[lookup[6*target+3+i] for i in range(3)]].copy()
    rotations[:,-1]-=z[6*cut+3:6*cut+6]
    expected=z[6*target+3:6*target+6]-z[6*cut+3:6*cut+6]
    root_error=float(max(abs(rotations.sum(axis=1)-expected)));assert root_error<2e-8,root_error
    np.savez_compressed(folder/'arrays.npz',rhs=rhs,contributions=response,path_rotations=rotations,expected_rotation=expected,
        operator=operator,actual_state=z[columns])
    def record(value):return dict(real=value.real.tolist(),imag=value.imag.tolist())
    result=dict(path=args.path,frequency_hz=frequency,names=names,path_rotation_deg=record(rotations*180/np.pi),
        expected_rotation_deg=record(expected*180/np.pi),reciprocal_condition=float(rcond),mechanical_residual=residual,
        complete_state_reconstruction_error=error,path_rotation_error=root_error,joint_base_convention_errors=joint_checks,
        qualification='Conditional mechanical reconstruction under actual full-aircraft load phasors. All real inertia/gravity, including point masses, is prescribed as D Alembert loading; mechanical matrix retains geometric preload. This is not a changed aircraft, a separate eigenfrequency calculation, or independent validation of the supplied joint loads.')
    print(json.dumps(result),flush=True);return result


def wing_wrench(folder,args):
    import numpy as np
    from check_daedalus_wing_paper import dynamic
    from check_daedalus_load_sensitivity import groups
    system=dynamic();n=system.network;frequency,tag=CASES[args.case]
    old=np.load(SAVED/tag/'arrays.npz');z=old['state'];load=old['component_residuals']
    keys=[row['component'] for row in read(SAVED/tag/'result.json')['components']]
    zero=np.zeros(system.size);state,_,options=system.physical_state(zero,zero,None)
    _,base=n.residual(state.x,detail=True,**options);base_loads,_,_=groups(system,base)
    boom=n.node(4,0.);wing=n.node(1,0.);_,nodes=n.station_nodes[1]
    dr=n.L*z[:6*n.nn].reshape(n.nn,6)[:,:3];theta=z[:6*n.nn].reshape(n.nn,6)[:,3:]
    arm=system.r0[nodes]-system.r0[boom];darm=dr[nodes]-dr[boom]
    fr=(6*n.ne+3*nodes[:,None]+np.arange(3)).ravel()
    mr=(6*n.ne+3*n.nn+3*nodes[:,None]+np.arange(3)).ravel()
    names=[key for key in keys if key.startswith('beam1:') and not key.endswith(':stall')]+['real_mass_gravity_applied']
    wrenches=[]
    for name in names:
        index=keys.index(name);force=n.F*load[fr,index].reshape(-1,3);moment=n.F*n.L*load[mr,index].reshape(-1,3)
        f0=n.F*base_loads[name][fr].reshape(-1,3)
        wrenches.append(np.r_[force.sum(axis=0),(moment+np.cross(arm,force)+np.cross(darm,f0)).sum(axis=0)])
    strut_checks=[]
    for index,row in enumerate(n.struts):
        assert int(row[0])==1
        node=n.node(*row[:2]);offset=system.Q0[node]@(row[2:5]-n.rj[node])
        point=system.r0[node]+offset;anchor=row[5:8];vector=anchor-point;length=np.linalg.norm(vector);e=vector/length
        rest=np.linalg.norm(anchor-row[2:5])+row[8];stiffness=row[9]/rest;tension=stiffness*(length-rest)
        assert tension>0
        f0=tension*e
        dp=dr[node]+np.cross(theta[node],offset)
        df=-(stiffness*np.outer(e,e)+tension/length*(np.eye(3)-np.outer(e,e)))@dp
        native=base['struts'][index]
        error=float(max(abs(np.array(native['force'])-f0)));assert error<2e-10,error;strut_checks.append(error)
        names.append(f'strut_{index+1}')
        wrenches.append(np.r_[df,np.cross(point-system.r0[boom],df)+np.cross(dp-dr[boom],f0)])
    wrenches=np.column_stack(wrenches)
    joint,=[c for c in n.constraints if c['a']==boom and c['b']==wing]
    start=6*(n.nn+n.ne)+joint['sl'].start
    v0=system.base[start:start+6]*np.r_[[n.F]*3,[n.F*n.L]*3]
    expected=z[start:start+6]*np.r_[[n.F]*3,[n.F*n.L]*3]
    expected[3:]+=np.cross(system.r0[wing]-system.r0[boom],expected[:3])+np.cross(dr[wing]-dr[boom],v0[:3])
    closure=float(max(abs(wrenches.sum(axis=1)-expected)));assert closure<2e-6,closure
    mechanics=np.load(STUDY/'forward_boom-mechanics/arrays.npz');rows=mechanics['rows'];columns=mechanics['columns']
    previous=np.load(STUDY/(args.case+'-forward_boom-loads')/'arrays.npz')
    row_lookup={int(row):i for i,row in enumerate(rows)};rhs=np.zeros((len(rows),len(names)),complex)
    for axis in range(3):
        rhs[row_lookup[6*n.ne+3*boom+axis]]=-wrenches[axis]/n.F
        rhs[row_lookup[6*n.ne+3*n.nn+3*boom+axis]]=-wrenches[3+axis]/(n.F*n.L)
    response=np.linalg.solve(previous['operator'],rhs)
    col_lookup={int(col):i for i,col in enumerate(columns)}
    rotation=response[[col_lookup[6*boom+3+axis] for axis in range(3)]]
    previous_names=read(STUDY/(args.case+'-forward_boom-loads')/'result.json')['names'];j=previous_names.index(f'joint_{boom}_{wing}')
    error=float(max(abs(rotation.sum(axis=1)-previous['path_rotations'][:,j])));assert error<2e-8,error
    residual=float(np.max(abs(previous['operator']@response-rhs)));assert residual<2e-9,residual
    np.savez_compressed(folder/'arrays.npz',wrenches=wrenches,expected_wrench=expected,rhs=rhs,rotations=rotation)
    def record(value):return dict(real=value.real.tolist(),imag=value.imag.tolist())
    result=dict(frequency_hz=frequency,names=names,wrenches=record(wrenches),expected_wrench=record(expected),
        forward_boom_rotation_deg=record(rotation*180/np.pi),wing_wrench_closure_error=closure,
        forward_boom_rotation_sum_error=error,mechanical_residual=residual,strut_base_force_errors=strut_checks,
        qualification='Wing external D Alembert loads and independently differentiated axial braces reconstruct the actual wing-to-boom wrench about the moving boom attachment. Conditional forward-boom responses retain supplied coupled load phases. These terms are not independent aircraft responses.')
    print(json.dumps(result),flush=True);return result


def report(folder,args):
    import csv
    import re
    import numpy as np
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    samples=[read(STUDY/case/'result.json') for case in ('slow','dip')]
    wing=read(STUDY/'dip-wing-wrench/result.json')
    wrench=np.array(wing['wrenches']['real'])+1j*np.array(wing['wrenches']['imag'])
    combined=np.column_stack([wrench[:,0],wrench[:,1],wrench[:,2:4].sum(axis=1),wrench[:,4],wrench[:,5],wrench[:,6:].sum(axis=1)])
    names=['Ordinary lift','Rate lift','Profile / pitch','Apparent inertia','Real inertia / gravity','Braces']
    palette=re.findall(r"'([^']+)'",(ROOT/'web/plot-colors.js').read_text().split('export const plotColors = Object.freeze([')[1].split(']);')[0])
    plt.rcParams.update({'figure.facecolor':'#111827','axes.facecolor':'#111827','text.color':'white',
        'axes.labelcolor':'white','xtick.color':'white','ytick.color':'white','axes.edgecolor':'#9ca3af','font.size':9})
    fig,axes=plt.subplots(1,3,figsize=(16,5.5),layout='constrained')
    y=np.arange(4)
    for j,sample in enumerate(samples):
        value=np.array(sample['path_rotation_deg']['real'])+1j*np.array(sample['path_rotation_deg']['imag'])
        axes[0].barh(y+(j-.5)*.36,abs(value[:,[0,2]]).ravel(),.36,color=palette[j],label=f"{sample['frequency_hz']:.3g} Hz")
    axes[0].set_yticks(y,['Fairing: body x','Fairing: body z','Forward boom: body x','Forward boom: body z'])
    axes[0].set_xlabel('Relative rotation magnitude [deg per native F3]');axes[0].set_title('Wing-root rotation through each path')
    for ax,component,title in [(axes[1],3,'Wing reaction: body-x moment'),(axes[2],5,'Wing reaction: body-z moment')]:
        value=combined[component];y=np.arange(len(names))
        ax.barh(y-.18,value.real,.36,color=palette[0],label='Real');ax.barh(y+.18,value.imag,.36,color=palette[1],label='Imaginary')
        ax.set_yticks(y,names);ax.set_xlabel('Moment at moving boom attachment [lb ft per F3]');ax.set_title(title)
    for ax in axes:
        ax.invert_yaxis();ax.axvline(0,color='white',alpha=.5,lw=.7);ax.grid(axis='x',alpha=.15);ax.set_axisbelow(True)
        ax.legend(facecolor='#111827',labelcolor='white')
    fig.suptitle('Daedalus wing mount: motion paths and cancelling reaction loads\nActual coupled state; prescribed-load reconstruction, no stiffness fitted')
    fig.savefig(folder/'wing-mount.png',dpi=150);fig.savefig(folder/'wing-mount.svg');plt.close(fig)
    with (folder/'wing-wrench.csv').open('x') as stream:
        writer=csv.writer(stream);writer.writerow(['source','component','real','imag','unit_per_F3'])
        for j,name in enumerate(wing['names']):
            for k,axis in enumerate(['Fx','Fy','Fz','Mx','My','Mz']):writer.writerow([name,axis,wrench[k,j].real,wrench[k,j].imag,'lb' if k<3 else 'lb ft'])
    comparisons=[]
    for sample in samples:
        actual=np.array(sample['path_rotation_deg']['real'])+1j*np.array(sample['path_rotation_deg']['imag'])
        straight=np.array(sample['straight_moment_integral_deg']['real'])+1j*np.array(sample['straight_moment_integral_deg']['imag'])
        comparisons.append(dict(frequency_hz=sample['frequency_hz'],path_complex_rotation_norm_relative_difference=(np.linalg.norm(straight-actual,axis=1)/np.linalg.norm(actual,axis=1)).tolist()))
    return dict(samples=samples,wing=wing,straight_integral_comparisons=comparisons,
        fairing_loads=read(STUDY/'dip-fairing-loads/result.json'),forward_boom_loads=read(STUDY/'dip-forward_boom-loads/result.json'),
        qualification='Display of the unchanged coupled response and conditional load reconstruction. Complex load terms cancel; magnitudes cannot be added. No new physical configuration or native Bode pass.')


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--case',choices=list(CASES))
    parser.add_argument('--stage',choices=['inspect','assemble','loads','wing_wrench','report'],default='inspect')
    parser.add_argument('--path',choices=['fairing','forward_boom'])
    parser.add_argument('--tag',required=True);args=parser.parse_args()
    if args.stage not in ('assemble','report') and args.case is None:parser.error('--case is required')
    if args.stage in ('assemble','loads') and args.path is None:parser.error('--path is required')
    STUDY.mkdir(exist_ok=True);folder=STUDY/args.tag;folder.mkdir(exist_ok=False)
    (folder/'runner.py').write_bytes(Path(__file__).read_bytes())
    inputs=[Path(__file__),ROOT/'scripts/check_daedalus_wing_paper.py',ROOT/'scripts/check_daedalus_source_operator.py',
        ROOT/'scripts/check_daedalus_load_sensitivity.py',ROOT/'scripts/check_daedalus_boom_drivers.py',ROOT/'examples/dae.asw',ROOT/'examples/dae-cruise-physical-mesh-project.json',
        SOURCE/'trim-6.7-1/state.json',ROOT/'docs/validation/aswing-authoritative-sources.json',
        ROOT/'reference/aswing-authoritative-20261108/drela-aswing-steady.pdf',ROOT/'reference/aswing-authoritative-20261108/drela-aswing-unsteady.pdf']
    if args.case is not None:
        inputs += [SAVED/CASES[args.case][1]/name for name in ('arrays.npz','result.json','terminal.json')]
        inputs += [TERMS/tag/name for tag in (args.case,args.case+'-split',args.case+'-elastic') for name in ('arrays.npz','result.json','terminal.json')]
    if args.stage=='loads':inputs += [STUDY/(args.path+'-mechanics')/name for name in ('arrays.npz','result.json','terminal.json')]
    if args.stage=='wing_wrench':inputs += [STUDY/tag/name for tag in ('forward_boom-mechanics',args.case+'-forward_boom-loads') for name in ('arrays.npz','result.json','terminal.json')]
    if args.stage=='report':inputs += [STUDY/tag/name for tag in ('slow','dip','fairing-mechanics','forward_boom-mechanics','dip-forward_boom-loads','dip-fairing-loads','dip-wing-wrench') for name in ('arrays.npz','result.json','terminal.json')]+[ROOT/'web/plot-colors.js']
    inputs += [SOURCE/'assembled-6.7'/name for name in ('A.npz','M.npz','maps.npz')]
    pins={str(p):pin(p) for p in inputs+list((ROOT/'openswing').glob('*.py'))}
    write(folder/'plan.json',dict(observed_utc=utc(),arguments=vars(args),limits=LIMITS,inputs_sha256=pins,
        allocator_environment={key:os.environ.get(key) for key in ('MALLOC_MMAP_THRESHOLD_','MALLOC_TRIM_THRESHOLD_')}))
    started=time.monotonic();sys.stdout.flush();pid=os.fork()
    if pid==0:
        code=0
        for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[key]='1'
        resource.setrlimit(resource.RLIMIT_AS,(LIMITS['address_space_bytes'],)*2);resource.setrlimit(resource.RLIMIT_CPU,(LIMITS['cpu_seconds'],)*2)
        sys.path.insert(0,str(ROOT))
        with (folder/'stdout.log').open('x') as out,(folder/'stderr.log').open('x') as err:
            os.dup2(out.fileno(),1);os.dup2(err.fileno(),2)
            try:write(folder/'result.json',globals()[args.stage](folder,args))
            except BaseException:traceback.print_exc();code=1
            sys.stdout.flush();sys.stderr.flush()
        os._exit(code)
    reaped=0;timed_out=False
    try:
        while not reaped:
            reaped,status,usage=os.wait4(pid,os.WNOHANG)
            if reaped:break
            if time.monotonic()-started>LIMITS['wall_seconds']:
                timed_out=True;os.kill(pid,signal.SIGKILL);reaped,status,usage=os.wait4(pid,0);break
            time.sleep(.05)
    finally:
        if not reaped:os.kill(pid,signal.SIGKILL);reaped,status,usage=os.wait4(pid,0)
    terminal=dict(observed_utc=utc(),returncode=os.waitstatus_to_exitcode(status),process_reaped=True,timed_out=timed_out,
        cpu_seconds=usage.ru_utime+usage.ru_stime,wall_seconds=time.monotonic()-started,peak_rss_kib=usage.ru_maxrss,
        limits=LIMITS,inputs_unchanged=all(pin(p)==h for p,h in pins.items()))
    write(folder/'terminal.json',terminal);print(json.dumps(terminal),flush=True)
    raise SystemExit(terminal['returncode'] or (0 if terminal['inputs_unchanged'] else 1))


if __name__=='__main__':main()
