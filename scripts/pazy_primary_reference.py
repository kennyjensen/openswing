"""Independent exact linear beam with nodal spatial inertia, no solver imports.

Each material interval is massless between the source's point inertias. Its
exact end flexibility is the unit-load work integral of the supplied full4x4
compliance. Two Gauss points integrate its quadratic integrand exactly.
"""
import numpy as np
from scipy.linalg import eigh


def skew(v):
    x,y,z=v
    return np.array([[0.,-z,y],[z,0.,-x],[-y,x,0.]])


def element(length,stiffness):
    compliance=np.linalg.inv(stiffness);tip=np.zeros((6,6))
    x,w=np.polynomial.legendre.leggauss(2)
    for s,weight in zip((x+1)*length/2,w*length/2):
        arm=length-s
        # Work conjugates of [eps_x,kappa_x,kappa_y,kappa_z] in primary w axes:
        # w_x=global+y; w_y=global-x (leading edge); w_z=global+z.
        b=np.array([[0,1,0,0,0,0],[0,0,0,0,1,0],[0,0,-arm,-1,0,0],[-arm,0,0,0,0,1]])
        tip+=weight*b.T@compliance@b
    transform=np.zeros((6,12));transform[:3,:3]=-np.eye(3);transform[:3,3:6]=skew([0,length,0])
    transform[:3,6:9]=np.eye(3);transform[3:,3:6]=-np.eye(3);transform[3:,9:]=np.eye(3)
    return transform.T@np.linalg.solve(tip,transform)


def matrices(data,projected=False):
    size=6*len(data['mass']);k=np.zeros((size,size));m=np.zeros_like(k)
    for i,(a,b,section) in enumerate(zip(data['coordinates'][:-1,1],data['coordinates'][1:,1],data['stiffness'])):
        section=section.copy()
        if projected:section[0,1]=section[1,0]=0
        ids=np.arange(6*i,6*i+12);k[np.ix_(ids,ids)]+=element(b-a,section)
    for i,(mass,offset,inertia) in enumerate(zip(data['mass'],data['offset'],data['inertia'])):
        motion=np.eye(6);motion[:3,3:]=-skew(offset)
        cg=np.zeros((6,6));cg[:3,:3]=mass*np.eye(3);cg[3:,3:]=inertia
        m[6*i:6*i+6,6*i:6*i+6]=motion.T@cg@motion
    return k,m


def modes(data,projected=False,count=8):
    k,m=matrices(data,projected)
    values,vectors=eigh(k[6:,6:],m[6:,6:],subset_by_index=[0,count-1])
    assert np.min(values)>0
    shapes=np.vstack([np.zeros((6,count)),vectors]).T.reshape(count,-1,6)
    rows=[]
    for value,v,shape in zip(values,vectors.T,shapes):
        residual=np.linalg.norm(k[6:,6:]@v-value*m[6:,6:]@v)/(np.linalg.norm(k[6:,6:])*np.linalg.norm(v)+abs(value)*np.linalg.norm(m[6:,6:])*np.linalg.norm(v))
        assert residual<1e-12
        rows.append(dict(frequency_Hz=float(np.sqrt(value)/(2*np.pi)),shape=shape.tolist(),backward_error=float(residual)))
    return dict(projected=projected,modes=rows,clamped_finite_dimension=2*(len(k)-6),
                description='Exact massless-interval flexibility; original16 nodal spatial inertias. Air-free and gravity-free.')
