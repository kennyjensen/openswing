"""Independent energy beam for hanging ST-4 wings with eccentric point masses.

For the inextensible, shear-rigid, stiff-in-plane rod, R'=R hat([kappa,0,tau]).
At a straight base h'=-theta_x, phi'=tau, and the second variation of the chord
director elevation obeys (R e_x)_z'=-h' phi'. Gravity therefore contributes
1/2 integral T h'^2 + integral D h' phi' and 1/2 sum m g dz h'(s_p)^2.
T and D are the downstream weight and its chordwise first moment. This keeps
the reaction of the rigid in-plane curvature constraint. No OpenSwing imports.
"""
import numpy as np
from scipy.linalg import eigh
from isae_st4_reference import fields


def modes(points,*,length=1.2192,t0=.0001,mass=1.2947,icc=.0078,ip=.0078,
          ei=41.1744*9.81,gj=20.2506*9.81,ea_x=.437*.2032,cg_x=.454*.2032,
          gravity=0.,air_mass=0.,air_ip=0.,air_x=.1016,elements=128,count=6):
    stations=np.array([(p[1]-t0)*length/(length-t0) for p in points])
    uniform=np.linspace(0,length,elements+1)
    for station in stations:
        nearest=int(np.argmin(abs(uniform-station)))
        if 0<nearest<len(uniform)-1 and abs(uniform[nearest]-station)<.25*length/elements:
            uniform=np.delete(uniform,nearest)
    nodes=np.unique(np.r_[uniform,stations]);size=3*len(nodes)
    k,m,kb,kt,kg=[np.zeros((size,size)) for _ in range(5)]
    gx,gw=np.polynomial.legendre.leggauss(4)
    for j,(a,b) in enumerate(zip(nodes[:-1],nodes[1:])):
        ds=b-a;ix=np.ix_(np.arange(3*j,3*j+6),np.arange(3*j,3*j+6))
        for x,weight in zip((gx+1)/2,gw*ds/2):
            s=a+x*ds;h,dh,ddh,phi,dp=fields(x,ds)
            centroid=h+(cg_x-ea_x)*phi;air_center=h+(air_x-ea_x)*phi
            bend=ei*np.outer(ddh,ddh);torsion=gj*np.outer(dp,dp)
            downstream=[p for p,station in zip(points,stations) if station>s]
            tension=gravity*(mass*(length-s)+sum(p[0] for p in downstream))
            first_moment=gravity*(mass*(cg_x-ea_x)*(length-s)+sum(p[0]*(p[2]-ea_x) for p in downstream))
            geometric=tension*np.outer(dh,dh)+first_moment*(np.outer(dh,dp)+np.outer(dp,dh))
            k[ix]+=weight*(bend+torsion+geometric);kb[ix]+=weight*bend;kt[ix]+=weight*torsion;kg[ix]+=weight*geometric
            m[ix]+=weight*(mass*np.outer(centroid,centroid)+icc*np.outer(dh,dh)+ip*np.outer(phi,phi)
                           +air_mass*np.outer(air_center,air_center)+air_ip*np.outer(phi,phi))
    for point,station in zip(points,stations):
        point_mass,t,x,y,z=point;assert y==0 and 0<=station<=length
        j=int(np.argmin(abs(nodes-station)));assert abs(nodes[j]-station)<1e-14
        v=np.array([1.,z-station,x-ea_x]);ix=np.ix_(np.arange(3*j,3*j+3),np.arange(3*j,3*j+3))
        m[ix]+=point_mass*np.outer(v,v)
        k[3*j+1,3*j+1]+=point_mass*gravity*(z-station)
        kg[3*j+1,3*j+1]+=point_mass*gravity*(z-station)
    # Reciprocal symmetric pencil extracts the largest inverse squared frequencies.
    # eigh(M,K) returns K-normalized vectors; divide by sqrt(mu) for M normalization.
    nfree=size-3
    inverse,vectors=eigh(m[3:,3:],k[3:,3:],subset_by_index=[nfree-count,nfree-1])
    inverse=inverse[::-1];assert np.all(inverse>0)
    values=1/inverse;vectors=vectors[:,::-1]/np.sqrt(inverse)[None,:]
    shape=np.vstack([np.zeros((3,count)),vectors]).T
    energies=np.array([[v@kb@v,v@kt@v,v@kg@v] for v in shape])
    return dict(elements=len(nodes)-1,gravity=gravity,icc=icc,ip=ip,nodes=nodes.tolist(),
                frequencies_Hz=(np.sqrt(values)/(2*np.pi)).tolist(),shapes=shape.reshape(count,len(nodes),3).tolist(),
                elastic_bending_fraction=(energies[:,0]/energies[:,:2].sum(axis=1)).tolist(),
                elastic_torsion_fraction=(energies[:,1]/energies[:,:2].sum(axis=1)).tolist(),
                geometric_energy_fraction=(energies[:,2]/energies.sum(axis=1)).tolist())
