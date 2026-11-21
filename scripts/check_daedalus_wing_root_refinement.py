"""Bounded current-source component Newton steps and root-motion responses."""
import argparse
from check_daedalus_load_sensitivity import ROOT,read
from daedalus_bounded_job import run
STUDY=ROOT/'artifacts/daedalus-wing-root-20261114'


def work(folder,args):
    import numpy as np
    from scipy.linalg import lu_factor,lu_solve,get_lapack_funcs
    from daedalus_wing_root_discrete import Discrete,initial_state
    fixture=read(STUDY/'prepare/fixture.json');original=np.load(STUDY/'prepare/layout.npz')
    if args['parent']:
        parent=np.load(STUDY/args['parent']/'arrays.npz');prefix='next_' if args['stage']=='base' else ''
        state={key:parent[prefix+key] for key in ('stations','positions','frames','force','moment')}
    else:state=initial_state(fixture,original,args['factor'])
    problem=Discrete(fixture,state,(ROOT/'examples/dae.asw').read_text());zero=np.zeros(problem.size+6)
    residual=problem.evaluate(zero);maximum=float(max(abs(residual[:problem.size])))
    result=dict(stage=args['stage'],elements=problem.ne,base_residual=maximum)
    saved=dict(state)
    if args['stage']=='base':
        jac=problem.derivative()[:problem.size,:problem.size]
        rows=np.max(abs(jac),axis=1);scaled=jac/rows[:,None];cols=np.max(abs(scaled),axis=0);scaled/=cols
        lu,piv=lu_factor(scaled);rcond,info=get_lapack_funcs('gecon',(scaled,))(lu,np.linalg.norm(scaled,1));assert info==0 and rcond>1e-12
        correction=lu_solve((lu,piv),-residual[:problem.size]/rows)/cols
        r,q,N,M=problem.unpack(np.r_[correction,np.zeros(6)])
        saved.update(next_stations=state['stations'],next_positions=r,next_frames=q,next_force=N,next_moment=M)
        result.update(accepted=maximum<1e-9,rcond=float(rcond),correction_max=float(max(abs(correction))))
    else:
        assert maximum<1e-9,('Base residual',maximum)
        j1=problem.derivative(fourth=True);j2=problem.derivative(step=5e-6,fourth=True)
        derivative_error=float(np.max(abs(j1-j2)));assert derivative_error<2e-8,derivative_error
        mass=problem.mass();saved.update(matrix=j2,mass=mass);cases=[]
        for k,f in enumerate((.2,1.15737773741517)):
            operator=j2+(2*np.pi*f)**2*mass;root=np.diag(np.r_[[1/problem.L]*3,[1.]*3])
            a=operator[:problem.size,:problem.size];b=-operator[:problem.size,problem.size:]@root
            row=np.max(abs(a),axis=1);scaled=a/row[:,None];col=np.max(abs(scaled),axis=0);scaled/=col
            lu,piv=lu_factor(scaled);rcond,info=get_lapack_funcs('gecon',(scaled,))(lu,np.linalg.norm(scaled,1));assert info==0 and rcond>1e-12
            solution=lu_solve((lu,piv),b/row[:,None])/col[:,None]
            error=float(np.max(abs(a@solution-b)));assert error<2e-8,error
            total=np.r_[solution,root];motion=np.r_[root[None,:,:],solution[:6*problem.ne].reshape(problem.ne,6,6)]
            motion=motion*np.array([problem.L]*3+[1.]*3)[None,:,None]
            reaction=-(operator[-6:]@total)*np.array([problem.F]*3+[problem.F*problem.L]*3)[:,None]
            saved[f'motion_{k}']=motion;saved[f'reaction_{k}']=reaction;saved[f'state_{k}']=total
            item=dict(frequency_hz=f,rcond=float(rcond),residual=error)
            if problem.ne==14:
                native=np.load(STUDY/'native/arrays.npz')
                motion_error=float(np.max(abs(motion-native[f'motion_{k}'])))
                reaction_error=float(np.max(abs(reaction-native[f'reaction_{k}'])))
                assert motion_error<2e-6 and reaction_error<2e-5,(motion_error,reaction_error)
                item.update(extracted_motion_error=motion_error,extracted_reaction_error=reaction_error)
            cases.append(item)
        result.update(derivative_step_difference=derivative_error,cases=cases)
    np.savez_compressed(folder/'arrays.npz',**saved);print(result,flush=True);return result


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('stage',choices=['base','solve']);p.add_argument('--tag',required=True)
    p.add_argument('--factor',type=int,default=1);p.add_argument('--parent');args=vars(p.parse_args())
    inputs=[ROOT/'scripts/daedalus_wing_root_discrete.py',ROOT/'scripts/daedalus_wing_root_reference.py',ROOT/'examples/dae.asw',
        STUDY/'prepare/fixture.json',STUDY/'prepare/layout.npz',STUDY/'native/arrays.npz',ROOT/'docs/validation/ISAE_STATUS.md',
        ROOT/'docs/validation/daedalus-wing-root-20261114-plan.json']+list((ROOT/'openswing').glob('*.py'))
    if args['parent']:inputs += [STUDY/args['parent']/name for name in ('arrays.npz','result.json','terminal.json')]
    run(STUDY,args['tag'],inputs,work,args,__file__)


if __name__=='__main__':main()
