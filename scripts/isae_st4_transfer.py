"""Continuous uniform Rayleigh beam with exact concentrated-mass jump matrices.

The state is [h,h',phi,B,N,T], with B=EI h'', N=EI h'''+omega² Icc h'
and T=GJ phi'. The clamped end sets the first three components to zero;
the free end sets the last three to zero. Point masses give the variational
jump in [-N,B,T] without altering displacement or slope. No mesh is used.
"""
import numpy as np
from scipy.linalg import expm
from scipy.optimize import brentq


def boundary(frequency,points,rotary,*,length=1.2192,t0=.0001,mass=1.2947,
             ei=41.1744*9.81,gj=20.2506*9.81,ea_x=.437*.2032,cg_x=.454*.2032):
    omega2=(2*np.pi*frequency)**2;d=cg_x-ea_x
    generator=np.zeros((6,6));generator[0,1]=1.;generator[1,3]=1/ei;generator[2,5]=1/gj
    generator[3,4]=1.;generator[3,1]=-omega2*rotary
    generator[4,0]=omega2*mass;generator[4,2]=omega2*mass*d
    generator[5,0]=-omega2*mass*d;generator[5,2]=-omega2*(rotary+mass*d*d)
    # Constant state scaling improves transfer products, without changing roots.
    scale=np.array([length,1.,1.,ei/length,ei/length**2,gj/length])
    scaled=generator*scale[None,:]/scale[:,None]
    transfer=np.eye(6);station=0.
    for weight,t,x,y,z in sorted(points,key=lambda p:p[1]):
        assert y==0;s=(t-t0)*length/(length-t0)
        transfer=expm(scaled*(s-station))@transfer;station=s
        v=np.array([1.,z-s,x-ea_x]);jump=np.eye(6)
        jump[3,:3]-=omega2*weight*v[1]*v
        jump[4,:3]+=omega2*weight*v[0]*v
        jump[5,:3]-=omega2*weight*v[2]*v
        transfer=(jump*scale[None,:]/scale[:,None])@transfer
    transfer=expm(scaled*(length-station))@transfer
    block=transfer[3:,3:]
    # Keep a fixed floor: an uncoupled torsion row vanishes at its pole.
    # Scaling that row to unit length would erase its small residual.
    return block/np.maximum(np.linalg.norm(block,axis=1),1.)[:,None]


def frequencies(points,rotary,estimates,**kwargs):
    roots=[];checks=[]
    centers=np.array(estimates)
    for i,center in enumerate(centers):
        determinant=lambda f:np.linalg.det(boundary(f,points,rotary,**kwargs))
        # Fine energy-beam frequencies locate the desired branch; broad
        # brackets can include an additional higher pole beyond this subset.
        for width in [1e-4,3e-4,1e-3,3e-3,.01]:
            low=max(center*(1-width),0 if i==0 else (centers[i-1]+center)/2)
            high=min(center*(1+width),np.inf if i==len(centers)-1 else (center+centers[i+1])/2)
            if determinant(low)*determinant(high)<0:break
        else:raise ValueError(f'No isolated transfer root around {center} Hz.')
        root,info=brentq(determinant,low,high,xtol=2e-12,rtol=2e-14,full_output=True)
        matrix=boundary(root,points,rotary,**kwargs);singular=np.linalg.svd(matrix,compute_uv=False)
        assert info.converged and singular[-1]/singular[0]<1e-8,(root,singular)
        roots.append(root);checks.append(dict(bracket_Hz=[float(low),float(high)],iterations=info.iterations,
                                            relative_boundary_singular_value=float(singular[-1]/singular[0])))
    return dict(frequencies_Hz=roots,boundary_checks=checks)
