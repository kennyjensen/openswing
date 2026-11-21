"""Exact residual accounting between the saved coarse and refined responses.

Prescribe mapped nodal motion and frame velocity, complete fine kinematics and
circulation, then use full-pencil adjoints to account for the output difference.
Mapping variants disclose attribution dependence; no aircraft parameter changes.
"""
import argparse
from types import SimpleNamespace
from check_daedalus_load_sensitivity import ROOT,SOURCE,read
from check_daedalus_mesh_zeros import STUDY as SAMPLES,FINE,paths,load,euler
from daedalus_bounded_job import run

STUDY=ROOT/'artifacts/daedalus-mesh-residual-20261114'
FREQUENCY=1.5
CHANNELS=['yaw_rate','roll_rate','sideslip','bank']
CASES=['objective-repeat','objective-reference','material-repeat']


def accepted(folder):
    t=read(folder/'terminal.json')
    assert t['returncode']==0 and t['process_reaped'] and t['inputs_unchanged'],folder
    return read(folder/'result.json')


def packet(folder):
    import numpy as np
    accepted(folder)
    with np.load(folder/'arrays.npz') as data:return dict(data)


def map_folder(case):
    return STUDY/('map-compatible-repeat-v2' if case=='compatible-repeat' else f'map-{case}')


def sample_state(mesh):
    import numpy as np
    with np.load(SAMPLES/f'{mesh}-samples/arrays.npz') as data:
        i=int(np.argmin(abs(data['frequencies']-FREQUENCY)))
        assert abs(data['frequencies'][i]-FREQUENCY)<1e-14
        return data['states'][i],data['outputs'][i]


def capture(folder,args):
    import numpy as np
    from check_daedalus_structural_resolution import dynamic
    from openswing.local_motion import NetworkMotion,rotation_weights
    coarse,fine=[dynamic(SimpleNamespace(seed=paths(mesh)[2])) for mesh in ('coarse','fine')]
    c,f=coarse.network,fine.network
    assert (c.nn,c.ne,f.nn,f.ne)==(108,103,211,206)
    np.testing.assert_allclose([c.L,c.F,coarse.V,coarse.W],[f.L,f.F,fine.V,fine.W],rtol=2e-13,atol=1e-12)
    assert c.nc==f.nc==30 and not c.hinges and not f.hinges
    for system in (coarse,fine):
        *_,oa,ob=system.network.geometry(system.r0,system.Q0)
        assert max(np.max(abs(oa)),np.max(abs(ob)))<1e-13,'Position transport assumes zero beam-axis offsets.'
    left=np.zeros(f.nn,int);right=left.copy();fraction=np.zeros(f.nn);node_beam=left.copy()
    element_beam=np.zeros(f.ne,int);parent=np.zeros(f.ne,int);common=np.zeros(c.nn,int)
    probe=np.zeros((f.nn,6),complex);zc,hc=sample_state('coarse');zf,hf=sample_state('fine')
    pose=zc[:6*c.nn].reshape(c.nn,6)
    for beam in c.station_nodes:
        tc,ic=c.station_nodes[beam];tf,jf=f.station_nodes[beam]
        np.testing.assert_array_equal(tc,tf[::2]);common[ic]=jf[::2]
        index=np.clip(np.searchsorted(tc,tf,side='right')-1,0,len(tc)-2)
        left[jf]=ic[index];right[jf]=ic[index+1];fraction[jf]=(tf-tc[index])/(tc[index+1]-tc[index]);node_beam[jf]=beam
        ce=c.beam_elements[beam];fe=f.beam_elements[beam]
        parent[fe]=np.repeat(np.arange(c.ne)[ce],2);element_beam[fe]=beam
        fractions=np.column_stack((np.zeros(len(tc)-1),(tf[1::2]-tc[:-1])/(tc[1:]-tc[:-1]),np.ones(len(tc)-1)))
        for part,component in enumerate((np.real,np.imag)):
            motion=NetworkMotion(c,coarse.r0,coarse.Q0,c.L*component(pose[:,:3]),component(pose[:,3:]),np.zeros_like(c.rj),np.zeros_like(c.rj))
            field,_,_=motion.sample(beam,fractions)
            v=np.vstack((field.velocity[:,:-1].reshape(-1,3),field.velocity[-1,-1]))
            w=np.vstack((field.rates[:,:-1].reshape(-1,3),field.rates[-1,-1]))
            probe[jf]+=(1 if part==0 else 1j)*np.c_[v,w]
    wa,wb=rotation_weights(coarse.Q0[left],coarse.Q0[right],fraction)
    apply=lambda a,v:np.einsum('nij,nj->ni',a,v)
    dr=c.L*((1-fraction[:,None])*pose[left,:3]+fraction[:,None]*pose[right,:3])
    theta=apply(wa,pose[left,3:])+apply(wb,pose[right,3:])
    native_error=float(np.max(abs(probe-np.c_[dr,theta])));assert native_error<2e-11
    np.testing.assert_allclose(dr[common],c.L*pose[:,:3],atol=1e-12,rtol=2e-12)
    np.testing.assert_allclose(theta[common],pose[:,3:],atol=1e-12,rtol=2e-12)
    r=(1-fraction[:,None])*coarse.r0[left]+fraction[:,None]*coarse.r0[right]
    transport_arm=fine.r0-r
    patch=[]
    for axis in np.eye(3):
        rotation=apply(wa,np.tile(axis,(f.nn,1)))+apply(wb,np.tile(axis,(f.nn,1)))
        motion=(1-fraction[:,None])*np.cross(axis,coarse.r0[left])+fraction[:,None]*np.cross(axis,coarse.r0[right])
        transported=motion+np.cross(rotation,transport_arm)
        error=float(np.max(abs(transported-np.cross(axis,fine.r0))));assert error<2e-12
        patch.append(error)
    np.savez_compressed(folder/'arrays.npz',coarse_state=zc,fine_state=zf,coarse_output=hc,fine_output=hf,
        coarse_r=coarse.r0,fine_r=fine.r0,coarse_Q=coarse.Q0,fine_Q=fine.Q0,
        dr_material=dr,theta=theta,transport_arm=transport_arm,left=left,right=right,fraction=fraction,
        node_beam=node_beam,element_beam=element_beam,element_parent=parent,common_fine_nodes=common)
    return dict(frequency_hz=FREQUENCY,nodes=[c.nn,f.nn],elements=[c.ne,f.ne],common_nodes=len(common),
        native_motion_interpolation_error=native_error,objective_rigid_rotation_patch_errors=patch,
        maximum_equilibrium_position_transport=float(np.max(np.linalg.norm(transport_arm,axis=1))),
        qualification='Objective transport adds theta cross (fine mean position minus sampled coarse mean position). Material interpolation is retained as an explicit alternate mapping.')


def grouping(layout,data):
    import numpy as np
    nn,ne=layout['nodes'],layout['elements'];gs=layout['circulation']['start'];op=layout['operating']['start']
    vs=layout['local_velocity']['start'];fs=layout['frame']['start']
    groups=[];names=[]
    def add(name,indices):names.append(name);groups.append(np.asarray(indices,int))
    for beam in (1,2,3,4,5):
        es=np.flatnonzero(data['element_beam']==beam);ns=np.flatnonzero(data['node_beam']==beam)
        add(f'beam{beam}:position', (6*es[:,None]+np.arange(3)).ravel())
        add(f'beam{beam}:rotation', (6*es[:,None]+np.arange(3,6)).ravel())
        add(f'beam{beam}:force',(6*ne+3*ns[:,None]+np.arange(3)).ravel())
        add(f'beam{beam}:moment',(6*ne+3*nn+3*ns[:,None]+np.arange(3)).ravel())
    add('joints_ground',np.arange(6*(nn+ne),gs));add('circulation',np.arange(gs,op))
    add('net_force',np.arange(op,op+3));add('net_moment',np.arange(op+3,op+6))
    add('local_velocity',np.arange(vs,vs+3*nn));add('local_rates',np.arange(vs+3*nn,fs))
    for j,name in enumerate(('frame_velocity','frame_rates','earth_position','euler_angles')):add(name,np.arange(fs+3*j,fs+3*j+3))
    np.testing.assert_array_equal(np.sort(np.concatenate(groups)),np.arange(fs+12))
    return names,groups


def rank_probe(folder,args):
    import numpy as np
    import scipy.sparse as sp
    data=packet(STUDY/'capture');a,m=(sp.load_npz(paths('fine')[0]/p) for p in ('A.npz','M.npz'));K=2j*np.pi*FREQUENCY*m-a
    result=[]
    for beam in (1,2,3,4,5):
        nodes=np.flatnonzero(data['node_beam']==beam)[1::2]
        parents=np.unique(data['element_parent'][data['element_beam']==beam])
        for node,parent in zip(nodes,parents):
            es=np.flatnonzero(data['element_parent']==parent);rr=(6*es[:,None]+np.arange(3)).ravel();cc=6*node+np.arange(6)
            block=K[rr][:,cc].toarray();u,s,vh=np.linalg.svd(block)
            result.append(dict(beam=beam,node=int(node),parent=int(parent),singular_values=s.tolist(),
                last_ratio=float(s[-1]/s[0]),fifth_ratio=float(s[-2]/s[0]),null_translation_fraction=float(np.linalg.norm(vh[-1,:3]))))
    print(sorted(result,key=lambda r:r['last_ratio'],reverse=True)[:3],flush=True)
    return dict(blocks=result,maximum_last_ratio=max(r['last_ratio'] for r in result),minimum_fifth_ratio=min(r['fifth_ratio'] for r in result))


def mapping(folder,args):
    import numpy as np
    import scipy.sparse as sp
    data=packet(STUDY/'capture');coarse=read(paths('coarse')[1]);fine=read(paths('fine')[1])
    nc,nf=coarse['nodes'],fine['nodes'];ec,ef=coarse['elements'],fine['elements']
    gs,op,vs,fs=(fine[k]['start'] for k in ('circulation','operating','local_velocity','frame'))
    cgs,cfs=coarse['circulation']['start'],coarse['frame']['start'];omega=2*np.pi*FREQUENCY
    a,m=(sp.load_npz(paths('fine')[0]/p) for p in ('A.npz','M.npz'));K=1j*omega*m-a
    with np.load(paths('fine')[0]/'maps.npz') as saved:B,C=saved['B'][:,0],saved['C']
    zc,zf=data['coarse_state'],data['fine_state']; assert max(abs(K@zf-B))<2e-9
    np.testing.assert_allclose(C@zf,data['fine_output'],atol=2e-12,rtol=2e-12)
    z=np.zeros(len(B),complex);pose=z[:6*nf].reshape(nf,6)
    dr=data['dr_material'].copy()
    if args['case']!='material-repeat':dr+=np.cross(data['theta'],data['transport_arm'])
    pose[:,:3]=dr/fine['node_coordinates']['translation_scale'];pose[:,3:]=data['theta']
    internal=zc[6*nc:6*(nc+ec)].reshape(ec,6)[data['element_parent']].copy()
    internal[:,:3]*=coarse['internal_loads']['force_scale']/fine['internal_loads']['force_scale']
    internal[:,3:]*=coarse['internal_loads']['moment_scale']/fine['internal_loads']['moment_scale']
    z[6*nf:6*(nf+ef)]=internal.ravel()
    np.testing.assert_allclose(coarse['internal_loads']['force_scale'],fine['internal_loads']['force_scale'],rtol=2e-13)
    np.testing.assert_allclose(coarse['internal_loads']['moment_scale'],fine['internal_loads']['moment_scale'],rtol=2e-13)
    z[6*(nf+ef):gs]=zc[6*(nc+ec):cgs]
    if args['case'].endswith('reference'):z[6*nf:gs]=zf[6*nf:gs]
    assert np.max(abs(C[:,6*nf:gs]))==0
    completion=[]
    if args['case']=='compatible-repeat':
        # Remove the attainable position defects at inserted nodes. Each pair
        # has rank five: its torsional null direction is left unchanged.
        # All original-node motion stays fixed. This changes only the trial
        # mapping, never the fine aircraft operator, input or saved solution.
        ranks=accepted(STUDY/'rank-probe')
        assert ranks['maximum_last_ratio']<1e-10 and ranks['minimum_fifth_ratio']>1e-6
        before=z[:6*nf].copy()
        for beam in (1,2,3,4,5):
            nodes=np.flatnonzero(data['node_beam']==beam)[1::2]
            parents=np.unique(data['element_parent'][data['element_beam']==beam])
            assert len(nodes)==len(parents)
            for node,parent in zip(nodes,parents):
                elements=np.flatnonzero(data['element_parent']==parent);assert len(elements)==2
                rr=(6*elements[:,None]+np.arange(3)).ravel();cc=6*node+np.arange(6)
                assert np.max(abs(K[rr][:,6*nf:].data),initial=0)<1e-13
                block=K[rr][:,cc].toarray();assert np.max(abs(block.imag))<1e-14
                u,s,vh=np.linalg.svd(block.real)
                assert s[4]/s[0]>1e-6 and s[5]/s[0]<1e-10
                assert np.linalg.norm(vh[-1,:3])<1e-8
                old=K[rr]@z-B[rr]
                change=-vh[:5].T@((u[:,:5].T@old)/s[:5])
                z[cc]+=change;new=K[rr]@z-B[rr]
                assert max(abs(block.conj().T@new))<2e-12
                completion.append(dict(beam=beam,node=int(node),parent=int(parent),
                    rank=5,condition=float(s[0]/s[4]),
                    residual_norm_before=float(np.linalg.norm(old)),residual_norm_after=float(np.linalg.norm(new)),
                    translation_change_ft=float(np.linalg.norm(change[:3])*fine['node_coordinates']['translation_scale']),
                    rotation_change_rad=float(np.linalg.norm(change[3:]))))
        np.testing.assert_array_equal(z[:6*nf].reshape(nf,6)[data['common_fine_nodes']],before.reshape(nf,6)[data['common_fine_nodes']])
        dr=fine['node_coordinates']['translation_scale']*z[:6*nf].reshape(nf,6)[:,:3]
    z[fs:fs+3]=zc[cfs:cfs+3]*coarse['local_velocity']['scale']/fine['local_velocity']['scale']
    z[fs+3:fs+6]=zc[cfs+3:cfs+6]*coarse['local_rates']['scale']/fine['local_rates']['scale']
    z[vs:vs+3*nf]=(1j*omega*dr/fine['local_velocity']['scale']).ravel()
    z[vs+3*nf:fs]=(1j*omega*z[:6*nf].reshape(nf,6)[:,3:]/fine['local_rates']['scale']).ravel()
    # Complete the frame acceleration, Earth position and Euler kinematics.
    rows=np.arange(fs,fs+12);columns=np.r_[np.arange(op,op+6),np.arange(fs+6,fs+12)]
    z[columns]=np.linalg.solve(K[rows][:,columns].toarray(),B[rows]-K[rows]@z)
    # Fine circulation is eliminated at the mapped physical motion and fine trim.
    gamma=np.arange(gs,op);z[gamma]=np.linalg.solve(K[gamma][:,gamma].toarray(),B[gamma]-K[gamma]@z)
    residual=K@z-B
    kinematic=float(max(abs(residual[vs:])));circ=float(max(abs(residual[gs:op])))
    assert max(kinematic,circ)<2e-10,(kinematic,circ)
    names,groups=grouping(fine,data)
    pos=np.concatenate([indices for name,indices in zip(names,groups) if name.endswith(':position')])
    dep=K[pos][:,6*nf:gs]
    dependency=float(np.max(abs(dep.data),initial=0))
    expected_bank=np.linalg.solve(euler(read(paths('fine')[2])),fine['local_rates']['scale']*z[fs+3:fs+6])[0]/(1j*omega)*180/np.pi
    assert abs((C@z)[3]-expected_bank)<2e-12
    np.savez_compressed(folder/'arrays.npz',state=z,residual=residual,
        output=C@z,readout_change=C@z-data['coarse_output'],actual_change=data['fine_output']-data['coarse_output'])
    return dict(case=args['case'],frequency_hz=FREQUENCY,kinematic_residual=kinematic,circulation_residual=circ,
        joint_residual=float(max(abs(residual[6*(nf+ef):gs]))),position_internal_dependency=dependency,
        groups=names,group_maximum_residuals=[float(max(abs(residual[ix]),default=0)) for ix in groups],
        inserted_node_completion=completion,
        readout_change_real=(C@z-data['coarse_output']).real.tolist(),readout_change_imag=(C@z-data['coarse_output']).imag.tolist(),
        qualification='A mapped trial motion, not a solved physical aircraft. Exact row accounting depends on the stated mapping; the fine operator includes both discretization and trim changes.')


def adjoint(folder,args):
    import numpy as np
    import scipy.sparse as sp
    from scipy.sparse.linalg import LinearOperator,onenormest
    data=packet(STUDY/'capture');a,m,b,c,layout,_,structure=load('fine')
    K=(2j*np.pi*FREQUENCY*m-a).tocsc();K.sum_duplicates();K.eliminate_zeros()
    rows=np.maximum(abs(K).max(axis=1).toarray().ravel(),1e-30)
    rowed=sp.diags(1/rows)@K;columns=np.maximum(abs(rowed).max(axis=0).toarray().ravel(),1e-30)
    norm=float(abs(rowed@sp.diags(1/columns)).sum(axis=0).max());del rowed
    factor=structure.factor(a,m,2j*np.pi*FREQUENCY,rows,columns)
    inverse=LinearOperator(K.shape,matvec=factor.solve,matmat=factor.solve,
        rmatvec=lambda x:factor.solve(x,trans='H'),rmatmat=lambda x:factor.solve(x,trans='H'),dtype=complex)
    rcond=float(1/(norm*onenormest(inverse,t=1)));assert rcond>=1e-10
    channel=CHANNELS.index(args['channel']);rhs=c[channel].conj()
    dual=factor.solve(rhs/columns,trans='H')/rows
    dual+=factor.solve((rhs-K.conj().T@dual)/columns,trans='H')/rows
    error=K.conj().T@dual-rhs
    backward=float(np.linalg.norm(error)/(np.linalg.norm(K.data)*np.linalg.norm(dual)+np.linalg.norm(rhs)))
    colmax=np.maximum(abs(K).max(axis=0).toarray().ravel(),1e-30)
    scaled=float(max(abs(error)/colmax)/max(1.,max(abs(rhs)/colmax)))
    assert backward<1e-9 and scaled<1e-7
    names,groups=grouping(layout,data);results=[];values=[]
    for case in CASES:
        mapped=packet(STUDY/f'map-{case}');r=mapped['residual']
        contributions=np.array([-np.vdot(dual[ix],r[ix]) for ix in groups])
        readout=mapped['readout_change'][channel];actual=mapped['actual_change'][channel]
        closure=abs(contributions.sum()+readout-actual);assert closure<2e-10,(case,closure)
        results.append(dict(case=case,contribution_real=contributions.real.tolist(),contribution_imag=contributions.imag.tolist(),
            projection_on_actual_change_percent=(100*np.real(contributions*np.conj(actual))/abs(actual)**2).tolist(),
            readout=[float(readout.real),float(readout.imag)],actual=[float(actual.real),float(actual.imag)],closure=float(closure)))
        values.append(contributions)
    np.savez_compressed(folder/'arrays.npz',adjoint=dual,contributions=values)
    return dict(channel=args['channel'],frequency_hz=FREQUENCY,groups=names,cases=results,
        reciprocal_condition=rcond,backward_error=backward,scaled_residual=scaled,
        absolute_adjoint_residual=float(max(abs(error))),factor_dimension=factor.dimension,
        qualification='Exact identity Hfine-Hcoarse = -lambda^H residual(mapped state) + readout change. Row contributions are mapping-dependent accounts, not uniquely isolated physical causes.')


def projection(folder,args):
    import numpy as np
    import scipy.sparse as sp
    data=packet(STUDY/'capture');layout=read(paths('fine')[1]);names,groups=grouping(layout,data)
    a,m=(sp.load_npz(paths('fine')[0]/p) for p in ('A.npz','M.npz'));K=2j*np.pi*FREQUENCY*m-a
    with np.load(paths('fine')[0]/'maps.npz') as saved:C=saved['C']
    cases=CASES+['compatible-repeat'];entries=[];replay=0.;adjoint_error=0.
    for i,channel in enumerate(CHANNELS):
        old=accepted(STUDY/f'adjoint-{channel}');dual=packet(STUDY/f'adjoint-{channel}')['adjoint']
        error=float(max(abs(K.conj().T@dual-C[i].conj())));adjoint_error=max(adjoint_error,error)
        assert error<2e-8
        for j,case in enumerate(cases):
            p=packet(map_folder(case));values=np.array([-np.vdot(dual[ix],p['residual'][ix]) for ix in groups])
            actual=p['actual_change'][i];readout=p['readout_change'][i]
            closure=float(abs(values.sum()+readout-actual));assert closure<2e-10
            if j<len(CASES):
                expected=np.array(old['cases'][j]['contribution_real'])+1j*np.array(old['cases'][j]['contribution_imag'])
                replay=max(replay,float(max(abs(values-expected))))
                np.testing.assert_array_equal(values,expected)
            entries.append(dict(channel=channel,case=case,contribution_real=values.real.tolist(),contribution_imag=values.imag.tolist(),
                projection_on_actual_change_percent=(100*np.real(values*np.conj(actual))/abs(actual)**2).tolist(),
                actual=[float(actual.real),float(actual.imag)],readout=[float(readout.real),float(readout.imag)],closure=closure))
    np.savez_compressed(folder/'arrays.npz',contributions=np.array([np.array(r['contribution_real'])+1j*np.array(r['contribution_imag']) for r in entries]),
        actual=np.array([complex(*r['actual']) for r in entries]),readout=np.array([complex(*r['readout']) for r in entries]))
    return dict(frequency_hz=FREQUENCY,channels=CHANNELS,cases=cases,groups=names,entries=entries,
        original_projection_replay_error=replay,maximum_adjoint_residual=adjoint_error,
        qualification='Reuses verified full-pencil adjoints. The fourth mapping removes attainable inserted-node position defects without changing original-node motion; no new aircraft solution is claimed.')


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('stage',choices=['capture','mapping','adjoint','projection','rank_probe'])
    parser.add_argument('--tag',required=True);parser.add_argument('--case',choices=CASES+['compatible-repeat'],default=CASES[0]);parser.add_argument('--channel',choices=CHANNELS,default='roll_rate')
    args=vars(parser.parse_args())
    inputs=[ROOT/'scripts'/p for p in ('check_daedalus_structural_resolution.py','check_daedalus_source_operator.py','check_daedalus_mesh_zeros.py')]
    inputs += [ROOT/'examples/dae.asw',ROOT/'examples/dae-cruise-physical-mesh-project.json',ROOT/'docs/validation/ISAE_STATUS.md',ROOT/'docs/validation/aswing-authoritative-sources.json',
        ROOT/'reference/aswing-authoritative-20261108/drela-aswing-steady.pdf',ROOT/'reference/aswing-authoritative-20261108/drela-aswing-unsteady.pdf']
    for mesh in ('coarse','fine'):
        matrix,layout,seed=paths(mesh)
        inputs += [layout,seed,SAMPLES/f'{mesh}-samples/arrays.npz']+[matrix/p for p in ('A.npz','M.npz','maps.npz')]
    inputs += list((ROOT/'openswing').glob('*.py'))
    if args['stage']!='capture':inputs += [STUDY/'capture'/p for p in ('arrays.npz','result.json','terminal.json')]
    if args['stage']=='adjoint':inputs += [STUDY/f'map-{case}'/p for case in CASES for p in ('arrays.npz','result.json','terminal.json')]
    if args['stage']=='mapping' and args['case']=='compatible-repeat':inputs += [STUDY/'rank-probe'/p for p in ('result.json','terminal.json')]
    if args['stage']=='projection':
        inputs += [folder/p for folder in [*[map_folder(case) for case in CASES+['compatible-repeat']],*[STUDY/f'adjoint-{channel}' for channel in CHANNELS]] for p in ('arrays.npz','result.json','terminal.json')]
    run(STUDY,args['tag'],inputs,globals()[args['stage']],args,__file__)


if __name__=='__main__':main()
