"""Isolate direct wing/fin aerodynamic feedback at a fixed trim.

Diagnostic affine block removal retains the mean wake and every other motion
and structural pathway. It is not a physically altered aircraft prediction.
"""
import argparse
from check_daedalus_load_sensitivity import ROOT,SOURCE,read
from daedalus_bounded_job import run

STUDY=ROOT/'artifacts/daedalus-coupled-avl-20261114'
SAVED=ROOT/'artifacts/daedalus-load-sensitivity-20261113/reference-dip'


def build(folder,args):
    import numpy as np
    import scipy.sparse as sp
    from check_daedalus_wing_paper import dynamic
    from check_daedalus_load_sensitivity import groups
    system=dynamic();n=system.network;zero=np.zeros(system.size)
    a=sp.load_npz(SOURCE/'assembled-6.7/A.npz').tocsc()
    with np.load(SAVED/'arrays.npz') as archive:z=archive['state']
    gamma={};cursor=n.gamma_start
    for mesh in n.meshes:
        if not mesh.beam.lifting:continue
        gamma[mesh.beam.index]=np.arange(cursor,cursor+len(mesh.tm));cursor+=len(mesh.tm)
    assert cursor==n.gamma_start+n.ng
    rows=[]
    for source,target in [(1,3),(3,1)]:
        nodes=n.beam_nodes[target]
        pose_columns=(6*n.beam_nodes[source][:,None]+np.arange(6)).ravel()
        columns={'circulation':gamma[source],'pose':pose_columns,
                 'both':np.r_[pose_columns,gamma[source]]}[args['coupling']]
        force_rows=(6*n.ne+3*nodes[:,None]+np.arange(3)).ravel()
        moment_rows=(6*n.ne+3*n.nn+3*nodes[:,None]+np.arange(3)).ravel()
        force=a[force_rows,:][:,columns].toarray().reshape(len(nodes),3,len(columns))*n.F
        moment=a[moment_rows,:][:,columns].toarray().reshape(len(nodes),3,len(columns))*n.F*n.L
        net_force=force.sum(axis=0)
        net_moment=moment.sum(axis=0)+np.cross((system.r0[nodes]-n.model.reference[1])[None,:,:],force.transpose(2,0,1)).sum(axis=1).T
        block=np.zeros((system.size,len(columns)))
        selected=np.r_[force_rows,moment_rows,gamma[target]]
        block[selected]=a[selected,:][:,columns].toarray()
        block[n.operating_start:n.size]=np.vstack([net_force/n.F,net_moment/(n.F*n.L)])
        coo=sp.coo_matrix(block);increment=sp.csc_matrix((coo.data,(coo.row,columns[coo.col])),shape=a.shape)
        direction=np.zeros(system.size,complex);direction[columns]=z[columns]
        def sample(q):
            state,_,options=system.physical_state(q,zero,None)
            residual,data=n.residual(state.x,detail=True,**options)
            loads,_,_=groups(system,data)
            output=sum(v for key,v in loads.items() if key.startswith(f'beam{target}:') and not key.endswith(':stall'))
            output[gamma[target]]=residual[gamma[target]]
            return output
        stencils=[]
        for step in (1e-3,5e-4):
            tangent=np.zeros(system.size,complex)
            for part,component in enumerate((np.real,np.imag)):
                for offset,weight in [(-2,1),(-1,-8),(1,8),(2,-1)]:
                    tangent+=weight/(12*step)*(1 if part==0 else 1j)*sample(step*offset*component(direction))
            stencils.append(tangent)
        error=float(max(abs(stencils[-1]-increment@direction)))
        step_error=float(max(abs(stencils[-1]-stencils[0])))
        assert error<2e-8 and step_error<2e-8,(error,step_error)
        label=f'{source}-to-{target}';sp.save_npz(folder/f'A-{label}.npz',increment)
        rows.append(dict(source_beam=source,target_beam=target,columns=len(columns),nonzeros=increment.nnz,
            complete_action_error=error,stencil_change=step_error))
    print(rows,flush=True)
    return dict(channels=rows,coupling=args['coupling'],nonlinear_evaluations=32,
        qualification='Only the selected source circulation/pose columns in target circulation equations and aerodynamic nodal/global loads. Mean wake, free-frame, local velocity, indirect surface/body/engine and structural pathways remain. Fixed equilibrium requires an affine offset; no aircraft parameter is fitted.')


def solve(folder,args):
    import numpy as np
    import scipy.sparse as sp
    from openswing.frequency_response import harmonic_solve
    from openswing.harmonic_structure import ReusableBeamStructure
    a,m=(sp.load_npz(SOURCE/'assembled-6.7'/name).tocsc() for name in ('A.npz','M.npz'))
    with np.load(SOURCE/'assembled-6.7/maps.npz') as archive:b=archive['B'][:,0];c=archive['C']
    first=sp.load_npz(STUDY/args['blocks']/'A-1-to-3.npz');second=sp.load_npz(STUDY/args['blocks']/'A-3-to-1.npz')
    omega=2*np.pi*args['frequency'];rows=[];arrays={}
    for label,increment in [('baseline',sp.csc_matrix(a.shape)),('wing_to_fin_removed',first),
                            ('fin_to_wing_removed',second),('both_removed',first+second)]:
        modified=a-increment
        for matrix in (modified,m):
            for values in (matrix.data,matrix.indices,matrix.indptr):values.flags.writeable=False
        structure=ReusableBeamStructure(modified,m,np.r_[np.arange(618),np.arange(1266,1296)],np.arange(1266),np.arange(1384,2032),np.arange(1384,2032))
        z,checks=harmonic_solve(modified,m,b,omega,_structure=structure)
        output=c@z;rows.append(dict(case=label,real=output.real.tolist(),imag=output.imag.tolist(),magnitude=abs(output).tolist(),checks=checks))
        arrays[label+'_state']=z;arrays[label+'_output']=output
    if abs(args['frequency']-1.15737773741517)<1e-12:
        with np.load(SAVED/'arrays.npz') as archive:expected=archive['output']
        assert max(abs(arrays['baseline_output']-expected))<2e-10
    np.savez_compressed(folder/'arrays.npz',**arrays)
    print('frequency',args['frequency'],rows,flush=True)
    return dict(frequency_hz=args['frequency'],outputs=rows,channels=['yaw_rate','roll_rate','sideslip','bank'],
        blocks=args['blocks'],coupling=read(STUDY/args['blocks']/'result.json').get('coupling','circulation'),
        qualification='Full 2044-coordinate harmonic solve with selected direct perturbation-circulation/pose feedback removed conditionally. Mean wake and other feedback are retained. These are diagnostics, not candidate ASWING settings or modified-aircraft predictions.')


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('stage',choices=['build','solve'])
    parser.add_argument('--tag',required=True);parser.add_argument('--frequency',type=float,default=1.15737773741517)
    parser.add_argument('--coupling',choices=['circulation','pose','both'],default='circulation')
    parser.add_argument('--blocks',default='feedback-blocks')
    args=vars(parser.parse_args())
    inputs=[ROOT/'scripts/check_daedalus_wing_paper.py',ROOT/'scripts/check_daedalus_source_operator.py',
        ROOT/'examples/dae.asw',ROOT/'examples/dae-cruise-physical-mesh-project.json',SOURCE/'trim-6.7-1/state.json',
        ROOT/'docs/validation/aswing-authoritative-sources.json',ROOT/'reference/aswing-authoritative-20261108/drela-aswing-steady.pdf',
        SAVED/'arrays.npz']
    inputs += [SOURCE/'assembled-6.7'/name for name in ('A.npz','M.npz','maps.npz')]+list((ROOT/'openswing').glob('*.py'))
    if args['stage']=='solve':inputs += [STUDY/args['blocks']/name for name in ('A-1-to-3.npz','A-3-to-1.npz','result.json','terminal.json')]
    run(STUDY,args['tag'],inputs,globals()[args['stage']],args,__file__)


if __name__=='__main__':main()
