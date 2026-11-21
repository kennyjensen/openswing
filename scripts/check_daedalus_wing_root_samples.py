"""Continuum root-motion maps sampled on the complete nested 56-interval grid."""
import argparse
from check_daedalus_load_sensitivity import ROOT,read
from daedalus_bounded_job import run
STUDY=ROOT/'artifacts/daedalus-wing-root-20261114'


def work(folder,args):
    import numpy as np
    from scipy.integrate import solve_ivp
    from scipy.linalg import lu_factor,lu_solve,get_lapack_funcs
    from daedalus_wing_root_reference import Rod,hat
    fixture=read(STUDY/'prepare/fixture.json');rod=Rod(fixture,args['rtol'])
    old=np.array(fixture['stations']);stations=np.r_[np.concatenate([np.linspace(a,b,5)[:-1] for a,b in zip(old[:-1],old[1:])]),old[-1]]
    wrench=np.load(STUDY/args['parent']/'arrays.npz')['root_wrench'];base=rod.base(wrench)
    base_error=float(max(abs(base['end'][12:18]/np.r_[[100.]*3,[5600.]*3])));assert base_error<1e-9
    omega=2*np.pi*args['frequency'];y=np.eye(12).ravel();samples={float(stations[0]):y.copy()};base_samples={float(stations[0]):base['after'][0,:18]}
    for segment in base['segments']:
        p=segment['polynomials']
        def ode(s,values):
            state=segment['dense'](s);a,_,_=rod.operator(state,s,p);q=state[3:12].reshape(3,3)
            mass=float(p['mg'](s))/fixture['gravity_constant'];arm=hat(q@np.array([float(p['Ccg'](s)),0.,0.]))
            b=np.zeros((12,12));b[6:9,:3]=mass*np.eye(3);b[6:9,3:6]=-mass*arm
            b[9:12,:3]=mass*arm;b[9:12,3:6]=-mass*arm@arm
            return ((a-omega**2*b)@values.reshape(12,12)).ravel()
        sol=solve_ivp(ode,(segment['lo'],segment['hi']),y,method='DOP853',rtol=args['rtol'],atol=.01*args['rtol'],dense_output=True)
        rod.ops['dynamic_rhs']+=sol.nfev;rod.ops['dynamic_integrations']+=1
        assert sol.success,sol.message
        y=sol.y[:,-1].copy()
        for s in stations[(stations>segment['lo'])&(stations<segment['hi'])]:
            samples[float(s)]=sol.sol(s);base_samples[float(s)]=segment['dense'](s)[:18]
        node=segment['node']
        if node==fixture['brace']['node']:
            derivative=y.reshape(12,12);derivative[6:]-=base['brace']['tangent']@derivative[:6]
        if segment['hi'] in stations:
            samples[float(segment['hi'])]=y.copy()
            base_samples[float(segment['hi'])]=(base['after'][node,:18] if node is not None else segment['dense'](segment['hi'])[:18])
    assert len(samples)==len(stations),(len(samples),len(stations))
    fundamental=np.array([samples[float(s)] for s in stations]).reshape(-1,12,12)
    end=y.reshape(12,12);a=end[6:,6:];b=-end[6:,:6]
    row=np.max(abs(a),axis=1);scaled=a/row[:,None];col=np.max(abs(scaled),axis=0);scaled/=col
    lu,piv=lu_factor(scaled);rcond,info=get_lapack_funcs('gecon',(scaled,))(lu,np.linalg.norm(scaled,1));assert info==0 and rcond>1e-12
    root=lu_solve((lu,piv),b/row[:,None])/col[:,None]
    error=float(np.max(abs((a@root-b)/row[:,None])));assert error<2e-8,error
    response=fundamental@np.r_[np.eye(6),root]
    np.savez_compressed(folder/'arrays.npz',stations=stations,motion=response[:,:6],internal=response[:,6:],
        reaction=-root,boundary_matrix=a,boundary_rhs=b,boundary_root=root,fundamental=fundamental,
        base_state=np.array([base_samples[float(s)] for s in stations]))
    result=dict(frequency_hz=args['frequency'],rtol=args['rtol'],base_scaled_residual=base_error,
        sampled_nodes=len(stations),boundary_rcond=float(rcond),boundary_residual=error,operations=rod.ops)
    print(result,flush=True);return result


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--tag',required=True);p.add_argument('--parent',required=True)
    p.add_argument('--frequency',type=float,required=True);p.add_argument('--rtol',type=float,required=True);args=vars(p.parse_args())
    inputs=[ROOT/'scripts/daedalus_wing_root_reference.py',STUDY/'prepare/fixture.json',ROOT/'docs/validation/ISAE_STATUS.md',
        ROOT/'docs/validation/daedalus-wing-root-20261114-plan.json']+[STUDY/args['parent']/name for name in ('arrays.npz','result.json','terminal.json')]
    run(STUDY,args['tag'],inputs,work,args,__file__)


if __name__=='__main__':main()
