"""Independent geometrically exact static rod with primary nodal gravity loads.

No OpenSwing imports, force assembly, section mapping or structural mesh.
Each massless material interval is integrated with DOP853. Forces are constant
inside it; point masses and rigid CG offsets produce exact node wrench jumps.
The original full4x4 law and its explicit K12 projection are separate cases.
"""
import numpy as np
from scipy.integrate import solve_ivp
from scipy.optimize import root
from scipy.spatial.transform import Rotation
from pazy_primary_conm2 import source
from pazy_loaded import payload


def solve(spec,projected=True,stations=None,rtol=2e-11,atol=2e-13):
    data=source(spec['skin']);s=data['coordinates'][:,1]
    rotation=np.eye(3) if spec['orientation']=='horizontal' else np.array([[1.,0,0],[0,0,-1.],[0,1.,0]])
    grav=np.array([0.,0.,-spec['gravity']]);forces=data['mass'][:,None]*grav
    mass=spec.get('mass_kg',0.);extra=mass*grav;offset=payload(spec['skin'],spec.get('kind','bending'))
    compliance=[]
    for original in data['stiffness']:
        matrix=original.copy()
        if projected:matrix[0,1]=matrix[1,0]=0.
        compliance.append(np.linalg.inv(matrix))
    interval_forces=np.array([forces[i+1:].sum(axis=0)+extra for i in range(len(s)-1)])

    def integrate(moment,factor,dense=False):
        initial=np.r_[np.zeros(3),Rotation.from_matrix(rotation).as_quat(),moment]
        pieces=[]
        for i,(a,b,sm) in enumerate(zip(s[:-1],s[1:],compliance)):
            force=factor*interval_forces[i]
            def rhs(t,state):
                quat=state[3:7];q=Rotation.from_quat(quat).as_matrix()
                f_local=q.T@force;m_local=q.T@state[7:]
                # Primary work conjugates [F_span,M_span,M_leading,M_up].
                strain=sm@np.array([f_local[1],m_local[1],-m_local[0],m_local[2]])
                dr=q@np.array([0.,1.+strain[0],0.]);k=np.array([-strain[2],strain[1],strain[3]])
                dq=.5*np.r_[quat[3]*k+np.cross(quat[:3],k),-quat[:3]@k]
                return np.r_[dr,dq,-np.cross(dr,force)]
            solution=solve_ivp(rhs,[a,b],initial,method='DOP853',rtol=rtol,atol=atol,dense_output=dense)
            assert solution.success,solution.message
            initial=solution.y[:,-1].copy();q=Rotation.from_quat(initial[3:7]).as_matrix()
            initial[7:]-=np.cross(q@data['offset'][i+1],factor*forces[i+1])
            if i==len(s)-2:initial[7:]-=np.cross(q@offset,factor*extra)
            pieces.append(solution)
        return initial,pieces

    undeformed=sum((np.cross(rotation@(p+cg),f) for p,cg,f in zip(data['coordinates'][1:],data['offset'][1:],forces[1:])),np.zeros(3))
    undeformed+=np.cross(rotation@(data['coordinates'][-1]+offset),extra)
    moment=np.zeros(3);history=[]
    for factor in np.linspace(.125,1.,8):
        guess=undeformed*factor if not history else moment*factor/history[-1]['factor']
        residual=lambda m:integrate(m,factor)[0][7:]
        answer=root(residual,guess,method='hybr',options={'xtol':1e-10})
        error=float(np.max(abs(residual(answer.x))));assert error<2e-8,(spec,projected,answer.message,error)
        moment=answer.x;history.append(dict(factor=float(factor),boundary_moment_error_Nm=error,evaluations=int(answer.nfev)))
    end,pieces=integrate(moment,1.,True)
    samples=np.unique(np.r_[s,np.linspace(0.,s[-1],121)]) if stations is None else np.asarray(stations)
    assert min(samples)>=0 and max(samples)<=s[-1]+1e-12
    states=np.array([pieces[min(np.searchsorted(s[1:],x,side='left'),len(pieces)-1)].sol(x) for x in samples])
    error=float(np.max(abs(np.linalg.norm(states[:,3:7],axis=1)-1.)));assert error<2e-9
    return dict(specification=spec,projected=projected,stations_m=samples.tolist(),positions=states[:,:3].tolist(),
        rotations=Rotation.from_quat(states[:,3:7]).as_matrix().tolist(),moments=states[:,7:].tolist(),
        root_internal_moment=moment.tolist(),tip_boundary_error_Nm=float(np.max(abs(end[7:]))),
        quaternion_norm_error=error,rtol=rtol,atol=atol,continuation=history)
