"""Account for actual tailboom motion using its loaded beam equations.

The rear boom is cut at the literal fairing attachment, t=2.5 ft. Its local
real inertia remains in the mechanical operator; actual aircraft airloads,
attachment wrenches, frame inertia/gravity and cut motion are prescribed.
Their responses are an accounting of one coupled solution, not separate
free-aircraft responses or independent native validation cases.
"""
import argparse
import json
import os
from pathlib import Path
import resource
import signal
import sys
import time
import traceback

from check_daedalus_load_sensitivity import ROOT, SOURCE, LIMITS, read, write, pin, utc

STUDY = ROOT/'artifacts/daedalus-boom-drivers-20261113'
MATRIX = SOURCE/'assembled-6.7'
CASES = {'slow': (.2,'slow-animation'), 'dip': (1.15737773741517,'reference-dip')}


def layout(system):
    import numpy as np
    n=system.network; t,ids=n.station_nodes[4]; cut=n.node(4,2.5)
    free=ids[t>2.5]; elements=np.flatnonzero(np.isin(n.b,free))
    assert len(elements)==len(free) and np.all(np.isin(n.a[elements],np.r_[cut,free]))
    assert np.all(n.damping_times==0) and not np.any(n.offa) and not np.any(n.offb)
    poses=(6*free[:,None]+np.arange(6)).ravel()
    internals=(6*n.nn+6*elements[:,None]+np.arange(6)).ravel()
    rows=np.r_[(6*elements[:,None]+np.arange(6)).ravel(),
        (6*n.ne+3*free[:,None]+np.arange(3)).ravel(),
        (6*n.ne+3*n.nn+3*free[:,None]+np.arange(3)).ravel()]
    columns=np.r_[poses,internals]; root=6*cut+np.arange(6)
    assert len(rows)==len(columns)
    return cut,free,elements,rows,columns,root


def mechanical_function(system, rows):
    """Fast explicit loaded compatibility and internal wrench assembly.

    Uses the production section/chart maps, without any airflow, inertia or
    joint reaction. This is not claimed to be an independent beam oracle.
    The new assembly is cross-checked against the full residual below.
    """
    import numpy as np
    from openswing.local_motion import rotation_matrix
    from openswing.source_discrete import angles_from_frame,angle_matrix,_increments
    n=system.network
    def evaluate(z):
        pose=z[:6*n.nn].reshape(n.nn,6)
        r=system.r0+system.L*pose[:,:3]
        q=rotation_matrix(pose[:,3:])@system.Q0
        internal=(system.base+z[:n.size])[6*n.nn:6*(n.nn+n.ne)].reshape(n.ne,6)
        force=internal[:,:3]*n.F; moment=internal[:,3:]*n.F*n.L
        pa,pb,ra,rb,oa,ob=n.geometry(r,q); dr=pb-pa
        ta=(ra.transpose(0,2,1)+rb.transpose(0,2,1))/2
        strain,curvature=n.constitutive_response(np.einsum('nij,nj->ni',ta,force),np.einsum('nij,nj->ni',ta,moment))
        qa,qb=angles_from_frame(ra,n.source_fuselage),angles_from_frame(rb,n.source_fuselage)
        ka=(angle_matrix(qa,n.source_fuselage)+angle_matrix(qb,n.source_fuselage))/2
        translation=dr-np.einsum('nji,nj->ni',ta,strain+np.array([0.,1.,0.]))*n.ds[:,None]
        rotation=np.einsum('nij,nj->ni',ka,_increments(qa,qb))-n.source_jig_curvature-curvature*n.ds[:,None]
        f=np.zeros_like(r); m=np.zeros_like(r)
        np.add.at(f,n.a,force);np.add.at(f,n.b,-force)
        np.add.at(m,n.a,moment+np.cross(dr,force)/2+np.cross(oa,force))
        np.add.at(m,n.b,-moment+np.cross(dr,force)/2-np.cross(ob,force))
        return np.r_[np.c_[translation/n.L,rotation].ravel(),(f/n.F).ravel(),(m/(n.F*n.L)).ravel()][rows]
    return evaluate


def assemble(folder,args):
    import numpy as np
    import scipy.sparse as sp
    from check_daedalus_wing_paper import dynamic
    system=dynamic();n=system.network;cut,free,elements,rows,columns,root=layout(system)
    selected=np.r_[columns,root]; evaluate=mechanical_function(system,rows)
    matrices=[];zero=np.zeros(system.size)
    for step in (1e-5,5e-6):
        matrix=np.empty((len(rows),len(selected)))
        for k,j in enumerate(selected):
            d=zero.copy();d[j]=step
            matrix[:,k]=(8*(evaluate(d)-evaluate(-d))-(evaluate(2*d)-evaluate(-2*d)))/(12*step)
        matrices.append(matrix)
    error=float(np.max(abs(matrices[1]-matrices[0])));assert error<2e-8,error
    matrix=matrices[-1]
    saved=sp.load_npz(MATRIX/'A.npz')
    compatibility_error=float(np.max(abs(matrix[:6*len(elements)]-saved[rows[:6*len(elements)]][:,selected].toarray())))
    assert compatibility_error<2e-8,compatibility_error
    # Source endpoint real-mass law at the stationary loaded base. The literal
    # boom has no CG offset or intrinsic section tensor; retain its Eq.80
    # finite-interval rotary contribution. Completed endpoint loads are then
    # transferred with the same equal-endpoint rule as the source equations.
    _,_,ra,rb,*_=n.geometry(system.r0,system.Q0)
    mass=np.zeros_like(matrix); row_lookup={int(v):i for i,v in enumerate(rows)}
    col_lookup={int(v):i for i,v in enumerate(selected)}
    weight=0.
    for sample,section_inertia in zip(n.source_mass_samples,n.source_rotary_samples):
        beam,sl,end,masses,arms=sample
        if beam!=4:continue
        assert not np.any(arms)
        for e in elements:
            local=e-sl.start; source=(n.a if end==0 else n.b)[e]; rotation=(ra if end==0 else rb)[e]
            scalar=masses[local];weight+=scalar*n.model.constants[0]
            diagonal=section_inertia[local]+scalar*n.ds[e]**2/12*np.array([1.,0.,1.])
            inertia=(rotation*diagonal[None,:])@rotation.T
            for target in (n.a[e],n.b[e]):
                for i in range(3):
                    force_row=row_lookup.get(int(6*n.ne+3*target+i))
                    if force_row is not None:mass[force_row,col_lookup[int(6*source+i)]]+=scalar*n.L/(2*n.F)
                    moment_row=row_lookup.get(int(6*n.ne+3*n.nn+3*target+i))
                    if moment_row is not None:
                        for j in range(3):mass[moment_row,col_lookup[int(6*source+3+j)]]+=inertia[i,j]/(2*n.F*n.L)
    # Full nonlinear residual subtraction checks the fresh mechanical assembly,
    # including its loaded geometry and the moving attachment moment arms.
    def physical_mechanical(z):
        state,_,options=system.physical_state(z,zero,None)
        residual,data=n.residual(state.x,detail=True,**options)
        residual[6*n.ne:6*n.ne+3*n.nn]-=(data['force']/n.F).ravel()
        residual[6*n.ne+3*n.nn:6*(n.ne+n.nn)]-=(data['moment']/(n.F*n.L)).ravel()
        for reaction in data['reactions']:
            for node,f,m in [(reaction['node'],reaction['force'],reaction['moment']),
                (reaction['other_node'],reaction['other_force'],reaction['other_moment'])]:
                if node is None:continue
                residual[6*n.ne+3*node:6*n.ne+3*node+3]-=np.array(f)/n.F
                residual[6*n.ne+3*n.nn+3*node:6*n.ne+3*n.nn+3*node+3]-=np.array(m)/(n.F*n.L)
        assert not any(entry['node'] in free for entry in data['struts'])
        return residual[rows]
    direction=zero.copy();direction[selected]=np.random.default_rng(8913).normal(size=len(selected))
    probe_errors=[]
    for h in (0.,-2e-5,-1e-5,1e-5,2e-5):
        probe_errors.append(float(max(abs(evaluate(h*direction)-physical_mechanical(h*direction)))))
    assert max(probe_errors)<2e-10,probe_errors
    np.savez_compressed(folder/'arrays.npz',matrix=matrix,mass=mass,rows=rows,columns=columns,root=root,selected=selected,
        cut=cut,free=free,elements=elements)
    return dict(cut_material_t=2.5,cut_node=int(cut),free_nodes=free.tolist(),elements=elements.tolist(),
        mechanical_unknowns=len(columns),step_difference=error,compatibility_vs_full_matrix_error=compatibility_error,
        full_residual_subtraction_errors=probe_errors,real_boom_weight_lb=weight,
        qualification='Linearized loaded mechanical equations, exact retained source endpoint real inertia. Airloads and attachment wrenches are supplied separately from the actual coupled solution.')


def response(folder,args):
    import numpy as np
    from scipy.linalg import lu_factor,lu_solve,get_lapack_funcs
    from check_daedalus_wing_paper import dynamic
    from check_daedalus_load_sensitivity import groups
    from openswing.frequency_response import HarmonicInput
    system=dynamic();n=system.network;cut,free,elements,rows,columns,root=layout(system)
    matrix_data=np.load(STUDY/'mechanics'/'arrays.npz')
    for name,expected in [('rows',rows),('columns',columns),('root',root)]:np.testing.assert_array_equal(matrix_data[name],expected)
    jac,mass=matrix_data['matrix'],matrix_data['mass']; selected=np.r_[columns,root]
    frequency,saved_tag=CASES[args.case];omega=2*np.pi*frequency
    z=np.load(ROOT/'artifacts/daedalus-load-sensitivity-20261113'/saved_tag/'arrays.npz')['state'];rate=1j*omega*z
    forcing,_=HarmonicInput(system,'control.3',0).at_frequency(omega)
    names=['fin_attachment','stabilizer_attachment','body_airloads','frame_inertia_gravity','cut_motion']
    frame=np.zeros_like(z);frame[n.operating_start:n.size]=z[n.operating_start:n.size];frame[system.frame_start:]=z[system.frame_start:]
    def sample(v,dv,force):
        state,_,options=system.physical_state(v,dv,force)
        _,data=n.residual(state.x,detail=True,**options)
        values,_,_=groups(system,data)
        body=values['beam4:body']+values['points_shoulders_engines']
        result={'body_airloads':body[rows], 'total_real_mass_gravity':values['real_mass_gravity_applied'][rows]}
        for name,beam,t in [('fin_attachment',3,20.),('stabilizer_attachment',2,17.5)]:
            reaction,=[v for v in data['reactions'] if v['kind']=='joint' and v['node']==n.node(4,t) and v['other_node']==n.node(beam,0.)]
            value=np.zeros(system.size);node=reaction['node']
            value[6*n.ne+3*node:6*n.ne+3*node+3]=np.array(reaction['force'])/n.F
            value[6*n.ne+3*n.nn+3*node:6*n.ne+3*n.nn+3*node+3]=np.array(reaction['moment'])/(n.F*n.L)
            result[name]=value[rows]
        return result
    estimates=[]
    for step in (1e-3,5e-4):
        values={name:np.zeros(len(rows),complex) for name in names[:-1]+['total_real_mass_gravity']}
        for part,function in enumerate((np.real,np.imag)):
            for offset,weight in [(-2,1),(-1,-8),(1,8),(2,-1)]:
                h=step*offset;factor=weight/(12*step)*(1 if part==0 else 1j)
                full=sample(h*function(z),h*function(rate),forcing(part,h))
                framed=sample(h*function(frame),h*function(1j*omega*frame),None)
                for key in full:values[key]+=factor*full[key]
                values['frame_inertia_gravity']+=factor*framed['total_real_mass_gravity']
        estimates.append(values)
    load_error=max(float(max(abs(estimates[1][key]-estimates[0][key]))) for key in estimates[1]);assert load_error<2e-8,load_error
    values=estimates[-1]
    mass_error=float(max(abs(values['total_real_mass_gravity']-values['frame_inertia_gravity']-omega**2*mass@z[selected])))
    assert mass_error<2e-8,mass_error
    dynamic=jac+omega**2*mass
    values['cut_motion']=dynamic[:,-6:]@z[root]
    rhs=-np.column_stack([values[name] for name in names]);operator=dynamic[:,:len(columns)]
    row_scale=np.maximum(np.max(abs(operator),axis=1),1e-30)
    col_scale=np.maximum(np.max(abs(operator/row_scale[:,None]),axis=0),1e-30)
    scaled=operator/row_scale[:,None]/col_scale[None,:]
    factor=lu_factor(scaled);rcond,info=get_lapack_funcs('gecon',(scaled,))(factor[0],np.linalg.norm(scaled,1))
    assert info==0 and rcond>1e-12,(info,rcond)
    contributions=lu_solve(factor,rhs/row_scale[:,None])/col_scale[:,None]
    residual=float(np.max(abs(operator@contributions-rhs)));assert residual<2e-9,residual
    reconstruction=float(max(abs(contributions.sum(axis=1)-z[columns])));assert reconstruction<2e-8,reconstruction
    # Fin root follows the boom tip plus the literal loaded rigid offset.
    tip=n.node(4,20.);fin=n.node(3,0.);arm=system.r0[fin]-system.r0[tip]
    position={int(c):i for i,c in enumerate(columns)};p=np.zeros((6,len(columns)))
    for j in range(6):
        idx=position[6*tip+j]
        if j<3:p[j,idx]=n.L
        else:p[:3,idx]=np.cross(np.eye(3)[j-3],arm);p[j,idx]=1.
    output=p@contributions
    expected=z[6*fin:6*fin+6]*np.r_[[n.L]*3,[1.]*3]
    root_error=float(max(abs(output.sum(axis=1)-expected)));assert root_error<2e-7,root_error
    # Same prescribed attachment/body/frame loads and cut motion, removing
    # only local distributed REAL boom inertia. This is not a vacuum-tail
    # mode or a full-aircraft variant; apparent airloads remain prescribed.
    static_rhs=rhs.copy();static_rhs[:,-1]=-jac[:,-6:]@z[root]
    static=np.linalg.solve(jac[:,:len(columns)],static_rhs)
    static_error=float(np.max(abs(jac[:,:len(columns)]@static-static_rhs)));assert static_error<2e-9
    def record(value):return dict(real=value.real.tolist(),imag=value.imag.tolist())
    np.savez_compressed(folder/'arrays.npz',state=z,contributions=contributions,rhs=rhs,operator=operator,
        root_map=p,root_contributions=output,expected_root=expected,static_contributions=static,
        total_real_mass=values['total_real_mass_gravity'],frame_real_mass=values['frame_inertia_gravity'])
    result=dict(frequency_hz=frequency,names=names,root_contributions=record(output),actual_root=record(expected),
        root_units='Translations in ft/F3, spatial rotations in rad/F3, relative to aircraft frame.',
        root_without_local_boom_inertia=record(p@static.sum(axis=1)),scaled_reciprocal_condition=float(rcond),
        derivative_step_error=load_error,real_mass_split_error=mass_error,mechanical_residual=residual,
        full_tail_state_reconstruction_error=reconstruction,fin_root_reconstruction_error=root_error,
        no_local_inertia_residual=static_error,directional_nonlinear_evaluations=32,
        qualification='Conditional load accounting of the actual full-aircraft solution. Prescribed attachment wrenches already include tail aerodynamic and structural feedback. Removing local boom real inertia alone is not a physical tail-mass change or a Bode comparison.')
    print(json.dumps(result),flush=True);return result


def fin_loads(folder,args):
    """Recover fin attachment wrench from saved external nodal-load derivatives."""
    import numpy as np
    from check_daedalus_wing_paper import dynamic
    from check_daedalus_load_sensitivity import groups
    system=dynamic();n=system.network;_,_,_,rows,columns,_=layout(system)
    frequency,saved_tag=CASES[args.case]
    old=ROOT/'artifacts/daedalus-load-sensitivity-20261113'/saved_tag
    data0=np.load(old/'arrays.npz');z=data0['state'];derivatives=data0['component_residuals']
    keys=[item['component'] for item in read(old/'result.json')['components']]
    zero=np.zeros(system.size);state,_,options=system.physical_state(zero,zero,None)
    _,base=n.residual(state.x,detail=True,**options);base_values,_,_=groups(system,base)
    _,nodes=n.station_nodes[3];tip=n.node(4,20.);root=n.node(3,0.)
    offsets=system.r0[nodes]-system.r0[tip]
    motion=n.L*z[:6*n.nn].reshape(n.nn,6)[:,:3]
    arm_changes=motion[nodes]-motion[tip]
    fr=(6*n.ne+3*nodes[:,None]+np.arange(3)).ravel()
    mr=(6*n.ne+3*n.nn+3*nodes[:,None]+np.arange(3)).ravel()
    names=[key for key in keys if (key.startswith('beam3:') and key!='beam3:stall') or key=='real_mass_gravity_applied']
    wrenches=[]
    for name in names:
        index=keys.index(name)
        f=n.F*derivatives[fr,index].reshape(-1,3)
        m=n.F*n.L*derivatives[mr,index].reshape(-1,3)
        f0=n.F*base_values[name][fr].reshape(-1,3)
        moment=np.sum(m+np.cross(offsets,f)+np.cross(arm_changes,f0),axis=0)
        wrenches.append(np.r_[f.sum(axis=0),moment])
    wrenches=np.column_stack(wrenches)
    c,=[v for v in n.constraints if v['kind']=='joint' and v['a']==tip and v['b']==root]
    reaction_start=6*(n.nn+n.ne)+c['sl'].start
    reaction=z[reaction_start:reaction_start+6]*np.r_[[n.F]*3,[n.F*n.L]*3]
    force0=system.base[reaction_start:reaction_start+3]*n.F
    expected=reaction.copy()
    expected[3:]+=np.cross(system.r0[root]-system.r0[tip],reaction[:3])+np.cross(motion[root]-motion[tip],force0)
    wrench_error=float(max(abs(wrenches.sum(axis=1)-expected)));assert wrench_error<2e-6,wrench_error
    previous=np.load(STUDY/args.case/'arrays.npz');forcing=np.zeros((len(rows),len(names)))+0j
    lookup={int(row):i for i,row in enumerate(rows)}
    for j in range(3):
        forcing[lookup[6*n.ne+3*tip+j]]=-wrenches[j]/n.F
        forcing[lookup[6*n.ne+3*n.nn+3*tip+j]]=-wrenches[3+j]/(n.F*n.L)
    rhs_error=float(np.max(abs(forcing.sum(axis=1)-previous['rhs'][:,0])));assert rhs_error<2e-8,rhs_error
    response=np.linalg.solve(previous['operator'],forcing)
    residual=float(np.max(abs(previous['operator']@response-forcing)));assert residual<2e-9,residual
    root_response=previous['root_map']@response
    root_error=float(max(abs(root_response.sum(axis=1)-previous['root_contributions'][:,0])));assert root_error<2e-7,root_error
    np.savez_compressed(folder/'arrays.npz',wrenches=wrenches,expected_wrench=expected,
        rhs=forcing,contributions=response,root_contributions=root_response)
    def record(v):return dict(real=v.real.tolist(),imag=v.imag.tolist())
    result=dict(frequency_hz=frequency,names=names,wrenches=record(wrenches),expected_wrench=record(expected),
        root_contributions=record(root_response),attachment_wrench_closure_error=wrench_error,
        prescribed_force_replay_error=rhs_error,mechanical_residual=residual,fin_root_contribution_sum_error=root_error,
        qualification='D Alembert external loads of the complete fin: aerodynamic terms plus real inertia/gravity. Moments are about the moving boom tip and include derivative of every lever arm. Each response is conditional on the actual coupled load phasors; it is not a separately realizable aircraft response.')
    print(json.dumps(result),flush=True);return result


def report(folder,args):
    import csv
    import re
    import numpy as np
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.ticker import MaxNLocator
    samples={case:read(STUDY/case/'result.json') for case in CASES}
    fin={case:read(STUDY/f'fin-{case}'/'result.json') for case in CASES}
    def complex_array(value):return np.array(value['real'])+1j*np.array(value['imag'])
    palette=re.findall(r"'([^']+)'",(ROOT/'web/plot-colors.js').read_text().split('export const plotColors = Object.freeze([')[1].split(']);')[0])
    plt.rcParams.update({'figure.facecolor':'#111827','axes.facecolor':'#111827','text.color':'white',
        'axes.labelcolor':'white','xtick.color':'white','ytick.color':'white','axes.edgecolor':'#9ca3af','font.size':9})
    fig,axes=plt.subplots(1,2,figsize=(12,6.8),layout='constrained')
    left_labels=['Fin attachment','Stabilizer attachment','Boom airloads','Frame inertia/gravity','Forward attachment motion']
    right_labels=['Circulation lift','Circulation-rate lift','Profile force','Section pitch','Apparent loads','Fin real inertia/gravity']
    for ax,data,labels,title in [(axes[0],samples['dip'],left_labels,'Loads driving fin-root lateral displacement'),
        (axes[1],fin['dip'],right_labels,'Fin-reaction contribution split by physical load')]:
        values=complex_array(data['root_contributions'])[1]
        total=values.sum()
        for index,(value,label) in enumerate(zip(values,labels)):
            ax.quiver(0,0,value.real,value.imag,angles='xy',scale_units='xy',scale=1.,color=palette[index],label=label)
        ax.plot(total.real,total.imag,'*',color='white',markersize=12,label='Complex sum')
        x=np.r_[0.,values.real,total.real];y=np.r_[0.,values.imag,total.imag]
        margin=.12*max(np.ptp(x),np.ptp(y),.005)
        ax.set_xlim(x.min()-margin,x.max()+margin);ax.set_ylim(y.min()-margin,y.max()+margin)
        ax.xaxis.set_major_locator(MaxNLocator(4));ax.yaxis.set_major_locator(MaxNLocator(5))
        ax.axhline(0,color='white',alpha=.3);ax.axvline(0,color='white',alpha=.3);ax.grid(alpha=.15)
        ax.set_aspect('equal',adjustable='box');ax.set_title(title)
        ax.set_xlabel('Real displacement [ft / native F3]');ax.set_ylabel('Imaginary displacement [ft / native F3]')
        ax.legend(loc='upper center',bbox_to_anchor=(.5,-.18),ncol=2,fontsize=8,facecolor='#111827',labelcolor='white')
    fig.suptitle('Daedalus at 1.157378 Hz: motion reconstructed from actual loads\nConditional accounting of one coupled response; no parameter changes')
    fig.savefig(folder/'boom-drivers.png',dpi=160);fig.savefig(folder/'boom-drivers.svg');plt.close(fig)
    metrics=[]
    with (folder/'root-contributions.csv').open('x') as stream:
        writer=csv.writer(stream);writer.writerow(['frequency_hz','scope','driver','coordinate','real','imag','magnitude','phase_deg'])
        for case,s in samples.items():
            actual=complex_array(s['actual_root']);without=complex_array(s['root_without_local_boom_inertia'])
            selected=[1,5]
            for axis in selected:
                ratio=without[axis]/actual[axis]
                metrics.append(dict(frequency_hz=s['frequency_hz'],coordinate='lateral_translation' if axis==1 else 'yaw_rotation',
                    no_local_boom_inertia_magnitude_change_percent=float(100*(abs(ratio)-1)),
                    no_local_boom_inertia_phase_change_degrees=float(np.rad2deg(np.angle(ratio)))))
            for scope,data in [('all_drivers',s),('fin_physical_loads',fin[case])]:
                values=complex_array(data['root_contributions'])
                for axis in selected:
                    for index,name in enumerate(data['names']):
                        value=values[axis,index]*(1 if axis==1 else 180/np.pi)
                        writer.writerow([s['frequency_hz'],scope,name,'y_ft' if axis==1 else 'rotation_z_deg',
                            value.real,value.imag,abs(value),np.rad2deg(np.angle(value))])
    checks=0;terminals=[]
    for tag in ['mechanics','slow','dip','fin-slow','fin-dip']:
        job=STUDY/tag;terminal=read(job/'terminal.json');terminals.append(terminal)
        assert terminal['returncode']==0 and terminal['process_reaped'] and terminal['inputs_unchanged'] and not terminal['timed_out']
        assert terminal['cpu_seconds']<LIMITS['cpu_seconds'] and terminal['wall_seconds']<LIMITS['wall_seconds']
        for path,expected in read(job/'plan.json')['inputs_sha256'].items():
            target=job/'runner.py' if path==str(Path(__file__)) else Path(path)
            assert pin(target)==expected,(tag,path)
            checks+=1
    result=dict(samples=samples,fin_loads=fin,local_boom_inertia_comparison=metrics,input_hash_checks=checks,
        source_jobs_checked=len(terminals),max_source_cpu_seconds=max(t['cpu_seconds'] for t in terminals),
        max_source_wall_seconds=max(t['wall_seconds'] for t in terminals),max_source_rss_kib=max(t['peak_rss_kib'] for t in terminals),
        qualification='No isolated boom resonance frequency or native ASWING agreement is inferred. Fin aerodynamic/apparent/real-inertia effects already reside in the prescribed fin reaction.')
    print(json.dumps({k:v for k,v in result.items() if k not in ('samples','fin_loads')}),flush=True);return result


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('stage',choices=['assemble','response','fin_loads','report'])
    parser.add_argument('--tag',required=True);parser.add_argument('--case',choices=list(CASES));args=parser.parse_args()
    if args.stage in ('response','fin_loads') and args.case is None:parser.error('--case is required')
    STUDY.mkdir(exist_ok=True);folder=STUDY/args.tag;folder.mkdir(exist_ok=False)
    (folder/'runner.py').write_bytes(Path(__file__).read_bytes())
    inputs=[Path(__file__),ROOT/'scripts/check_daedalus_wing_paper.py',ROOT/'scripts/check_daedalus_load_sensitivity.py',
        ROOT/'scripts/check_daedalus_source_operator.py',ROOT/'examples/dae.asw',ROOT/'examples/dae-cruise-physical-mesh-project.json',
        SOURCE/'trim-6.7-1/state.json',ROOT/'docs/validation/aswing-authoritative-sources.json',MATRIX/'A.npz']
    inputs += [ROOT/'reference/aswing-authoritative-20261108'/f'drela-aswing-{kind}.pdf' for kind in ('steady','unsteady')]
    if args.stage in ('response','fin_loads'):
        inputs += [STUDY/'mechanics'/name for name in ('arrays.npz','result.json','terminal.json')]
        inputs += [ROOT/'artifacts/daedalus-load-sensitivity-20261113'/CASES[args.case][1]/'arrays.npz']
    if args.stage=='fin_loads':
        inputs += [ROOT/'artifacts/daedalus-load-sensitivity-20261113'/CASES[args.case][1]/'result.json']
        inputs += [STUDY/args.case/name for name in ('arrays.npz','result.json','terminal.json')]
    if args.stage=='report':
        inputs += [STUDY/tag/name for tag in ('mechanics','slow','dip','fin-slow','fin-dip') for name in ('result.json','plan.json','terminal.json','runner.py')]
        inputs.append(ROOT/'web/plot-colors.js')
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
