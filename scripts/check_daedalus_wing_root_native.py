"""Current positive-half-wing mechanics under prescribed root motion.

The current loaded equilibrium is retained. Its aerodynamic/gravity loads
become fixed body-axis nodal loads; the brace and real inertia stay live.
No full-aircraft solve or altered aerodynamic model is substituted.
"""
import argparse
from check_daedalus_load_sensitivity import ROOT,SOURCE,read,write
from daedalus_bounded_job import run

STUDY=ROOT/'artifacts/daedalus-wing-root-20261114'


def layout(system):
    import numpy as np
    n=system.network;t,ids=n.station_nodes[1];free=ids[t>0];cut=n.node(1,0.)
    elements=np.flatnonzero(np.isin(n.b,free));nodes=np.r_[cut,free]
    assert np.array_equal(n.a[elements],nodes[:-1]) and np.array_equal(n.b[elements],nodes[1:])
    rows=np.r_[(6*elements[:,None]+np.arange(6)).ravel(),
        (6*n.ne+3*free[:,None]+np.arange(3)).ravel(),
        (6*n.ne+3*n.nn+3*free[:,None]+np.arange(3)).ravel()]
    columns=np.r_[(6*free[:,None]+np.arange(6)).ravel(),
        (6*n.nn+6*elements[:,None]+np.arange(6)).ravel()]
    selected=np.r_[columns,6*cut+np.arange(6)]
    return cut,nodes,elements,rows,columns,selected


def prepare(folder,args):
    import numpy as np
    from check_daedalus_wing_paper import dynamic
    from openswing.geometry import surface_frame
    system=dynamic();n=system.network;cut,nodes,elements,rows,columns,selected=layout(system)
    beam=next(b for b in n.model.beams if b.index==1);t=n.station_nodes[1][0];stations=t[t>=0]
    zero=np.zeros(system.size);state,_,options=system.physical_state(zero,zero,None)
    residual,base=n.residual(state.x,detail=True,**options);assert max(abs(residual))<1e-9
    for name in ('EA','GKc','GKn'):assert np.all(np.isposinf(beam.value(name,stations))),name
    for name in ('EIcn','EIcs','EIsn','Cea','Nea','Cta','Nta','Dmg','mgcc','mgnn','Ncg','tdeps','tdgam'):
        assert not np.any(beam.value(name,stations)),name
    assert not np.any(n.offa) and not np.any(n.offb)
    jig=surface_frame(beam,stations);np.testing.assert_allclose(jig,np.broadcast_to(jig[0],jig.shape),atol=2e-14,rtol=0)
    row,=[r for r in n.struts if int(r[0])==1 and r[1]>0]
    brace_node=n.node(*row[:2]);brace_index=int(np.flatnonzero(nodes==brace_node)[0])
    brace=dict(station=float(row[1]),node=brace_index,anchor=row[5:8].tolist(),
        material_arm=(jig[brace_index].T@(row[2:5]-n.rj[brace_node])).tolist(),
        rest_length=float(np.linalg.norm(row[5:8]-row[2:5])+row[8]),EA=float(row[9]))
    properties={}
    for name in ('EIcc','GJ','EInn','mg','Ccg'):
        d=beam.distributions[name];properties[name]=dict(t=d.t.tolist(),values=d.values.tolist())
    dead_force=base['force'][nodes].copy();dead_moment=base['moment'][nodes].copy()
    # Root loads only change the support reaction, not the released half-wing.
    # Remove them in both component formulations, and retain their original
    # values separately to prevent confusing the component and aircraft cut.
    root_dead=np.r_[dead_force[0],dead_moment[0]];dead_force[0]=0;dead_moment[0]=0
    first=elements[0];N=base['N'][first];M=base['M'][first]
    initial=np.r_[N,M+np.cross(system.r0[nodes[1]]-system.r0[cut],N)/2]
    fixture=dict(stations=stations.tolist(),positions=system.r0[nodes].tolist(),
        material_frames=(system.Q0[nodes]@jig).tolist(),dead_force=dead_force.tolist(),dead_moment=dead_moment.tolist(),
        root_dead_wrench_removed=root_dead.tolist(),root_wrench_guess=initial.tolist(),properties=properties,
        brace=brace,gravity_constant=float(n.model.constants[0]),span=56.,
        qualification='Positive half of current loaded aircraft. Original steady aerodynamic/gravity nodal loads held fixed in body axes. Live brace and real inertia; no aerodynamic/apparent-inertia/gravity derivatives or free-flight frame.')
    write(folder/'fixture.json',fixture)
    np.savez_compressed(folder/'layout.npz',cut=cut,nodes=nodes,elements=elements,rows=rows,columns=columns,selected=selected,
        positions=system.r0[nodes],rotations=system.Q0[nodes]@jig,
        internal_force=base['N'][elements],internal_moment=base['M'][elements])
    # Probe literal tables for a separate reference interpolation identity check.
    probes={}
    for name,d in properties.items():
        knots=np.unique(d['t']);interior=(knots[:-1]+knots[1:])/2
        probes[name]=dict(t=interior.tolist(),values=beam.value(name,interior).tolist())
    write(folder/'property-probes.json',probes)
    return dict(base_residual=float(max(abs(residual))),nodes=len(nodes),elements=len(elements),
                unknowns=len(columns),selected_columns=len(selected),brace=brace,qualification=fixture['qualification'])


def block(folder,args):
    import numpy as np
    import scipy.sparse as sp
    from check_daedalus_wing_paper import dynamic
    from check_daedalus_boom_drivers import mechanical_function
    system=dynamic();n=system.network;cut,nodes,elements,rows,columns,selected=layout(system)
    indices=selected[args['start']:args['start']+args['count']];assert len(indices)>0
    evaluate=mechanical_function(system,rows);zero=np.zeros(system.size)
    def value(z):
        local=evaluate(z)
        # Positive-side root internal wrench; omit the other half-wing.
        pose=z[:6*n.nn].reshape(n.nn,6);r=system.r0+n.L*pose[:,:3]
        k=elements[0];v=(system.base+z[:n.size])[6*n.nn+6*k:6*n.nn+6*k+6]
        f=v[:3]*n.F;m=v[3:]*n.F*n.L+np.cross(r[nodes[1]]-r[cut],f)/2
        return np.r_[local,f/n.F,m/(n.F*n.L)]
    matrices=[]
    for step in (1e-5,5e-6):
        matrix=np.empty((len(rows)+6,len(indices)))
        for j,col in enumerate(indices):
            d=zero.copy();d[col]=step
            matrix[:,j]=(8*(value(d)-value(-d))-(value(2*d)-value(-2*d)))/(12*step)
        matrices.append(matrix)
    error=float(np.max(abs(matrices[0]-matrices[1])));assert error<2e-8,error
    saved=sp.load_npz(SOURCE/'assembled-6.7/A.npz')
    compatibility_error=float(np.max(abs(matrices[-1][:6*len(elements)]-saved[rows[:6*len(elements)]][:,indices].toarray())))
    assert compatibility_error<2e-8,compatibility_error
    np.savez_compressed(folder/'arrays.npz',matrix=matrices[-1],indices=indices)
    return dict(start=args['start'],count=len(indices),step_difference=error,compatibility_error=compatibility_error)


def solve(folder,args):
    import numpy as np
    from scipy.linalg import lu_factor,lu_solve,get_lapack_funcs
    from check_daedalus_wing_paper import dynamic
    from daedalus_wing_root_reference import brace_state,hat
    system=dynamic();n=system.network;cut,nodes,elements,rows,columns,selected=layout(system)
    fixture=read(STUDY/'prepare/fixture.json');parts=[np.load(STUDY/tag/'arrays.npz') for tag in args['blocks']]
    np.testing.assert_array_equal(np.concatenate([p['indices'] for p in parts]),selected)
    matrix=np.column_stack([p['matrix'] for p in parts]);mass=np.zeros_like(matrix)
    lookup={int(col):i for i,col in enumerate(selected)};rowlookup={int(row):i for i,row in enumerate(rows)}
    for j in range(3):
        rowlookup[6*n.ne+3*cut+j]=len(rows)+j
        rowlookup[6*n.ne+3*n.nn+3*cut+j]=len(rows)+3+j
    # Native source mass data, physical accelerations from harmonic nodal pose.
    _,_,ra,rb,*_=n.geometry(system.r0,system.Q0)
    for sample,section in zip(n.source_mass_samples,n.source_rotary_samples):
        beam,sl,end,masses,arms=sample
        if beam!=1:continue
        for e in elements:
            j=e-sl.start;src=(n.a if end==0 else n.b)[e];q=(ra if end==0 else rb)[e]
            arm=q@arms[j];h=hat(arm);m=masses[j]
            diag=section[j]+m*n.ds[e]**2/12*np.array([1.,0.,1.]);I=(q*diag)@q.T
            physical=np.block([[m*np.eye(3),-m*h],[m*h,I-m*h@h]])
            physical=physical*np.r_[[n.L]*3,[1.]*3][None,:]/np.r_[[n.F]*3,[n.F*n.L]*3][:,None]
            c=[lookup[6*src+k] for k in range(6)]
            for dst in (n.a[e],n.b[e]):
                rr=[rowlookup[6*n.ne+3*dst+k] for k in range(3)]+[rowlookup[6*n.ne+3*n.nn+3*dst+k] for k in range(3)]
                mass[np.ix_(rr,c)]+=physical/2
    brace=brace_state(np.array(fixture['positions'])[fixture['brace']['node']],
                      np.array(fixture['material_frames'])[fixture['brace']['node']],fixture['brace'])
    node=nodes[fixture['brace']['node']]
    rr=[rowlookup[6*n.ne+3*node+k] for k in range(3)]+[rowlookup[6*n.ne+3*n.nn+3*node+k] for k in range(3)]
    cc=[lookup[6*node+k] for k in range(6)]
    matrix[np.ix_(rr,cc)]+=brace['tangent']*np.r_[[n.L]*3,[1.]*3][None,:]/np.r_[[n.F]*3,[n.F*n.L]*3][:,None]
    results=[];saved=dict(matrix=matrix,mass=mass,rows=rows,columns=columns,selected=selected)
    for k,f in enumerate((.2,1.15737773741517)):
        omega=2*np.pi*f;operator=matrix+omega**2*mass
        root=np.diag(np.r_[[1/n.L]*3,[1.]*3]);a=operator[:len(rows),:len(columns)];b=-operator[:len(rows),len(columns):]@root
        row_scale=np.max(abs(a),axis=1);scaled=a/row_scale[:,None];col_scale=np.max(abs(scaled),axis=0);scaled/=col_scale
        lu,piv=lu_factor(scaled);rcond,info=get_lapack_funcs('gecon',(scaled,))(lu,np.linalg.norm(scaled,1));assert info==0 and rcond>1e-12
        answer=lu_solve((lu,piv),b/row_scale[:,None])/col_scale[:,None]
        error=float(np.max(abs(a@answer-b)));assert error<2e-8,error
        total=np.r_[answer,root];motion=np.empty((len(nodes),6,6))
        for j,node in enumerate(nodes):motion[j]=total[[lookup[6*node+i] for i in range(6)]]*np.r_[[n.L]*3,[1.]*3][:,None]
        reaction=-(operator[-6:]@total)*np.r_[[n.F]*3,[n.F*n.L]*3][:,None]
        saved[f'motion_{k}']=motion;saved[f'reaction_{k}']=reaction;saved[f'state_{k}']=total
        results.append(dict(frequency_hz=f,reciprocal_condition=float(rcond),residual=error))
    np.savez_compressed(folder/'arrays.npz',**saved)
    return dict(cases=results,brace_tension_lb=float(brace['tension']),qualification=fixture['qualification'])


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('stage',choices=['prepare','block','solve'])
    parser.add_argument('--tag',required=True);parser.add_argument('--start',type=int,default=0);parser.add_argument('--count',type=int,default=48)
    parser.add_argument('--blocks',nargs='*',default=[]);args=vars(parser.parse_args())
    inputs=[ROOT/'scripts/check_daedalus_wing_paper.py',ROOT/'scripts/check_daedalus_source_operator.py',
        ROOT/'scripts/check_daedalus_boom_drivers.py',ROOT/'scripts/daedalus_wing_root_reference.py',
        ROOT/'examples/dae.asw',ROOT/'examples/dae-cruise-physical-mesh-project.json',SOURCE/'trim-6.7-1/state.json',
        SOURCE/'assembled-6.7/A.npz',ROOT/'docs/validation/aswing-authoritative-sources.json',ROOT/'docs/validation/ISAE_STATUS.md']
    inputs += list((ROOT/'openswing').glob('*.py'))
    if args['stage']=='solve':inputs += [STUDY/'prepare/fixture.json']+[STUDY/tag/'arrays.npz' for tag in args['blocks']]
    run(STUDY,args['tag'],inputs,globals()[args['stage']],args,__file__)


if __name__=='__main__':main()
