"""One bounded continuum Newton step or one root-motion frequency per job."""
import argparse
from check_daedalus_load_sensitivity import ROOT,read
from daedalus_bounded_job import run

STUDY=ROOT/'artifacts/daedalus-wing-root-20261114'


def work(folder,args):
    import numpy as np
    from scipy.linalg import lu_factor,lu_solve,get_lapack_funcs
    from daedalus_wing_root_reference import Rod
    fixture=read(STUDY/'prepare/fixture.json');rod=Rod(fixture,args['rtol'])
    probes=read(STUDY/'prepare/property-probes.json');property_error=0.
    for name,p in probes.items():
        for t,expected in zip(p['t'],p['values']):
            candidates=[p for lo,hi,p in rod.table.parts[name] if lo<t<hi]
            assert len(candidates)==1,(name,t)
            actual=float(candidates[0](t));error=abs(actual-expected)/max(1.,abs(expected));property_error=max(property_error,error)
    assert property_error<2e-12,property_error
    if args['parent'] is None:wrench=np.array(fixture['root_wrench_guess'])
    else:
        parent=np.load(STUDY/args['parent']/'arrays.npz')
        wrench=parent['next_wrench'] if args['stage']=='base' else parent['root_wrench']
    base=rod.base(wrench);tip=base['end'][12:18]
    q=base['after'][:,3:12].reshape(-1,3,3)
    orthogonality=float(np.max(abs(q.transpose(0,2,1)@q-np.eye(3))))
    assert orthogonality<2e-7,orthogonality
    scale=np.array([100.]*3+[5600.]*3);residual=float(max(abs(tip/scale)))
    saved=dict(root_wrench=wrench,base_before=base['before'],base_after=base['after'])
    result=dict(stage=args['stage'],rtol=args['rtol'],property_probe_error=property_error,
        scaled_tip_residual=residual,tip_force_max=float(max(abs(tip[:3]))),tip_moment_max=float(max(abs(tip[3:]))),
        rotation_orthogonality=orthogonality,brace_tension_lb=float(base['brace']['tension']))
    if args['stage']=='base':
        jac=base['end'][18:].reshape(12,6)[6:];scaled=jac*scale[None,:]/scale[:,None]
        singular=np.linalg.svd(scaled,compute_uv=False);rcond=singular[-1]/singular[0];assert rcond>1e-10
        delta=np.linalg.solve(scaled,-tip/scale)*scale;saved['next_wrench']=wrench+delta
        result.update(boundary_rcond=float(rcond),accepted=bool(residual<1e-9),operations=rod.ops)
    else:
        assert residual<1e-9,('Base not accepted',residual)
        harmonic=rod.harmonic(base,args['frequency']);matrix=harmonic['end'][6:,6:];rhs=-harmonic['end'][6:,:6]
        row=np.max(abs(matrix),axis=1);scaled=matrix/row[:,None];col=np.max(abs(scaled),axis=0);scaled/=col
        lu,piv=lu_factor(scaled);rcond,info=get_lapack_funcs('gecon',(scaled,))(lu,np.linalg.norm(scaled,1));assert info==0 and rcond>1e-12
        root=lu_solve((lu,piv),rhs/row[:,None])/col[:,None]
        defect=float(np.max(abs((matrix@root-rhs)/row[:,None])));assert defect<2e-8,defect
        solution=harmonic['after']@np.r_[np.eye(6),root]
        saved.update(motion=solution[:,:6],internal=solution[:,6:],reaction=-root,
            boundary_matrix=matrix,boundary_rhs=rhs,boundary_root=root,
            fundamental_before=harmonic['before'],fundamental_after=harmonic['after'])
        result.update(frequency_hz=args['frequency'],boundary_rcond=float(rcond),boundary_residual=defect,operations=rod.ops)
    np.savez_compressed(folder/'arrays.npz',**saved)
    print(result,flush=True);return result


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('stage',choices=['base','harmonic'])
    parser.add_argument('--tag',required=True);parser.add_argument('--parent');parser.add_argument('--rtol',type=float,default=1e-9)
    parser.add_argument('--frequency',type=float,default=1.15737773741517);args=vars(parser.parse_args())
    inputs=[ROOT/'scripts/daedalus_wing_root_reference.py',STUDY/'prepare/fixture.json',STUDY/'prepare/property-probes.json',
        ROOT/'docs/validation/ISAE_STATUS.md',ROOT/'reference/aswing-authoritative-20261108/drela-aswing-steady.pdf',
        ROOT/'reference/aswing-authoritative-20261108/drela-aswing-unsteady.pdf']
    if args['parent']:inputs += [STUDY/args['parent']/name for name in ('arrays.npz','result.json','terminal.json')]
    run(STUDY,args['tag'],inputs,work,args,__file__)


if __name__=='__main__':main()
