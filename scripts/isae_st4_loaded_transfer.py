"""Continuous hanging Rayleigh beam, independent of the energy mesh and kernel.

State [h,h',phi,B,N,P] uses B=EI*h'', P=GJ*phi'+D*h', and
N=B'-(T-omega²*Icc)*h'-D*phi'. T,D are downstream gravity force
and chordwise first moment. Concentrated masses retain exact pylon offsets.
"""
import numpy as np
from scipy.integrate import solve_ivp
from scipy.optimize import brentq


def boundary(frequency,points,*,length=1.2192,t0=.0001,mass=1.2947,icc=.0078,ip=.0078,
             ei=41.1744*9.81,gj=20.2506*9.81,ea_x=.437*.2032,cg_x=.454*.2032,
             gravity=0.,air_mass=0.,air_ip=0.,air_x=.1016,rtol=2e-11,atol=2e-13):
    omega2=(2*np.pi*frequency)**2;d=cg_x-ea_x;da=air_x-ea_x
    mm=mass+air_mass;md=mass*d+air_mass*da;ii=ip+mass*d*d+air_ip+air_mass*da*da
    scale=np.array([length,1.,1.,ei/length,ei/length**2,gj/length])
    sorted_points=sorted(points,key=lambda p:p[1]);stations=[(p[1]-t0)*length/(length-t0) for p in sorted_points]
    # Only the three unknown clamped-root reactions need propagation.
    transfer=np.eye(6)[:,3:];station=0.
    for j,end in enumerate(stations+[length]):
        downstream=sorted_points[j:]
        def derivative(s,values):
            tension=gravity*(mass*(length-s)+sum(p[0] for p in downstream))
            first=gravity*(mass*d*(length-s)+sum(p[0]*(p[2]-ea_x) for p in downstream))
            generator=np.zeros((6,6));generator[0,1]=1.;generator[1,3]=1/ei
            generator[2,1]=-first/gj;generator[2,5]=1/gj
            generator[3,4]=1.;generator[3,1]=tension-omega2*icc-first*first/gj;generator[3,5]=first/gj
            generator[4,0]=omega2*mm;generator[4,2]=omega2*md
            generator[5,0]=-omega2*md;generator[5,2]=-omega2*ii
            return ((generator*scale[None,:]/scale[:,None])@values.reshape(6,3)).ravel()
        if end!=station:
            result=solve_ivp(derivative,[station,end],transfer.ravel(),method='DOP853',rtol=rtol,atol=atol)
            assert result.success;transfer=result.y[:,-1].reshape(6,3);station=end
        if j<len(sorted_points):
            weight,t,x,y,z=sorted_points[j];assert y==0
            v=np.array([1.,z-station,x-ea_x]);jump=np.eye(6)
            jump[3,:3]-=omega2*weight*v[1]*v;jump[3,1]+=weight*gravity*v[1]
            jump[4,:3]+=omega2*weight*v[0]*v;jump[5,:3]-=omega2*weight*v[2]*v
            transfer=(jump*scale[None,:]/scale[:,None])@transfer
    block=transfer[3:]
    return block/np.maximum(np.linalg.norm(block,axis=1),1.)[:,None]


def frequencies(points,estimates,**kwargs):
    roots=[];checks=[];centers=np.asarray(estimates)
    for i,center in enumerate(centers):
        determinant=lambda f:np.linalg.det(boundary(f,points,**kwargs))
        for width in [1e-4,3e-4,1e-3,3e-3,.01]:
            low=max(center*(1-width),0 if i==0 else (centers[i-1]+center)/2)
            high=min(center*(1+width),np.inf if i==len(centers)-1 else (center+centers[i+1])/2)
            if determinant(low)*determinant(high)<0:break
        else:raise ValueError(f'No isolated loaded transfer root around {center} Hz.')
        root,info=brentq(determinant,low,high,xtol=2e-12,rtol=2e-14,full_output=True)
        singular=np.linalg.svd(boundary(root,points,**kwargs),compute_uv=False)
        assert info.converged and singular[-1]/singular[0]<1e-8,(root,singular)
        roots.append(root);checks.append(dict(bracket_Hz=[float(low),float(high)],iterations=info.iterations,
                                            relative_boundary_singular_value=float(singular[-1]/singular[0])))
    return dict(frequencies_Hz=roots,boundary_checks=checks)
