"""Independent coupled Rayleigh-beam reference for the literal ST-4 model.

No OpenSwing imports. Cubic Hermite bending and linear torsion follow direct
strain and kinetic energy. Coordinates are physical vertical span s, normal
translation h along global y at the elastic axis, and twist phi about global z.
Distributed centroid offsets and actual point-mass pylon offsets remain live.
Constants below are literal ISAE input values, not experimental calibration.
"""
import numpy as np
from scipy.linalg import eigh

LENGTH=1.2192
T0=.0001
MASS=1.2947
EA_X=.437*.2032
CG_X=.454*.2032
EI=41.1744*9.81
GJ=20.2506*9.81


def fields(x,length):
    a=np.zeros((5,6));ids=[0,1,3,4]
    a[0,ids]=[1-3*x*x+2*x**3,length*(x-2*x*x+x**3),3*x*x-2*x**3,length*(-x*x+x**3)]
    a[1,ids]=[(-6*x+6*x*x)/length,1-4*x+3*x*x,(6*x-6*x*x)/length,-2*x+3*x*x]
    a[2,ids]=[(-6+12*x)/length**2,(-4+6*x)/length, (6-12*x)/length**2,(-2+6*x)/length]
    a[3,[2,5]]=[1-x,x];a[4,[2,5]]=[-1/length,1/length]
    return a


def modes(points,rotary=.0078,elements=128,count=6):
    # Points are independent physical inputs [mass, parameter t, x, y, z].
    stations=[(p[1]-T0)*LENGTH/(LENGTH-T0) for p in points]
    # Place every attachment exactly on a node, but replace a nearby interior
    # uniform node instead of creating a tiny element. Tiny intervals make
    # the energy stiffness ill-conditioned and corrupt low eigenvalues.
    uniform=np.linspace(0,LENGTH,elements+1)
    for station in stations:
        nearest=int(np.argmin(abs(uniform-station)))
        if 0<nearest<len(uniform)-1 and abs(uniform[nearest]-station)<.25*LENGTH/elements:
            uniform=np.delete(uniform,nearest)
    nodes=np.unique(np.r_[uniform,stations]);size=3*len(nodes)
    k,m,kb,kt=[np.zeros((size,size)) for _ in range(4)]
    gx,gw=np.polynomial.legendre.leggauss(4)
    for j,(a,b) in enumerate(zip(nodes[:-1],nodes[1:])):
        length=b-a;ix=np.ix_(np.arange(3*j,3*j+6),np.arange(3*j,3*j+6))
        for x,weight in zip((gx+1)/2,gw*length/2):
            h,dh,ddh,phi,dp=fields(x,length);centroid=h+(CG_X-EA_X)*phi
            bend=EI*np.outer(ddh,ddh);torsion=GJ*np.outer(dp,dp)
            k[ix]+=weight*(bend+torsion);kb[ix]+=weight*bend;kt[ix]+=weight*torsion
            m[ix]+=weight*(MASS*np.outer(centroid,centroid)+rotary*np.outer(dh,dh)+rotary*np.outer(phi,phi))
    for point,station in zip(points,stations):
        mass,t,x,y,z=point;assert y==0 and 0<=station<=LENGTH
        j=int(np.argmin(abs(nodes-station)));assert abs(nodes[j]-station)<1e-14
        # theta_x=-h'. The small axial pylon offset z-station is retained.
        v=np.array([1.,z-station,x-EA_X]);ix=np.ix_(np.arange(3*j,3*j+3),np.arange(3*j,3*j+3))
        m[ix]+=mass*np.outer(v,v)
    values,vectors=eigh(k[3:,3:],m[3:,3:],subset_by_index=[0,count-1]);assert np.all(values>0)
    shape=np.vstack([np.zeros((3,count)),vectors]).T
    energies=np.array([[v@kb@v,v@kt@v] for v in shape])
    return dict(elements=len(nodes)-1,rotary=rotary,nodes=nodes.tolist(),frequencies_Hz=(np.sqrt(values)/(2*np.pi)).tolist(),
                shapes=shape.reshape(count,len(nodes),3).tolist(),energy_fractions=(energies/energies.sum(axis=1)[:,None]).tolist(),
                bending_fraction_convention='Elastic strain energy only; mixed modes are not relabelled by experimental frequencies.')
