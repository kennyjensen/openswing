"""Independent real-mass scalar potential, gradient and Hessian.

No OpenSwing/Scipy imports or production geometry/load helpers. The explicit
fixture supplies material endpoints, masses, offsets and endpoint twist.
Second-order forward differentiation applies the chain rule to the scalar
potential; it does not reproduce the production nodal transfer matrices.
"""
import math
import numpy as np

DIM=36


class Jet:
    def __init__(self,value,gradient=None,hessian=None):
        self.v=float(value)
        self.g=np.zeros(DIM) if gradient is None else gradient
        self.h=hessian

    @classmethod
    def variable(cls,value,index,second):
        g=np.zeros(DIM);g[index]=1.
        return cls(value,g,np.zeros((DIM,DIM)) if second else None)

    def coerce(self,x):
        return x if isinstance(x,Jet) else Jet(x,hessian=np.zeros((DIM,DIM)) if self.h is not None else None)

    def __add__(self,other):
        b=self.coerce(other)
        return Jet(self.v+b.v,self.g+b.g,None if self.h is None else self.h+b.h)
    __radd__=__add__

    def __neg__(self):
        return Jet(-self.v,-self.g,None if self.h is None else -self.h)

    def __sub__(self,other):return self+-self.coerce(other)
    def __rsub__(self,other):return self.coerce(other)+-self

    def __mul__(self,other):
        b=self.coerce(other)
        h=None if self.h is None else (self.h*b.v+b.h*self.v+np.outer(self.g,b.g)+np.outer(b.g,self.g))
        return Jet(self.v*b.v,self.g*b.v+b.g*self.v,h)
    __rmul__=__mul__

    def unary(self,value,first,second):
        return Jet(value,first*self.g,None if self.h is None else first*self.h+second*np.outer(self.g,self.g))

    def __pow__(self,p):
        return self.unary(self.v**p,p*self.v**(p-1),p*(p-1)*self.v**(p-2))

    def __truediv__(self,other):return self*self.coerce(other)**-1
    def __rtruediv__(self,other):return self.coerce(other)*self**-1


def sine(x):
    return x.unary(math.sin(x.v),math.cos(x.v),-math.sin(x.v)) if isinstance(x,Jet) else math.sin(x)


def cosine(x):
    return x.unary(math.cos(x.v),-math.sin(x.v),-math.cos(x.v)) if isinstance(x,Jet) else math.cos(x)


def acos(x):
    if not isinstance(x,Jet):return math.acos(x)
    d=1-x.v*x.v
    if d<=0:raise ValueError('Independent rotation arc left the declared interior domain.')
    return x.unary(math.acos(x.v),-1/math.sqrt(d),-x.v/d**1.5)


def val(x):return x.v if isinstance(x,Jet) else float(x)
def eye():return [[1.,0.,0.],[0.,1.,0.],[0.,0.,1.]]
def transpose(a):return [list(row) for row in zip(*a)]
def dot(a,b):return sum(x*y for x,y in zip(a,b))
def matmul(a,b):return [[dot(row,col) for col in transpose(b)] for row in a]
def matvec(a,b):return [dot(row,b) for row in a]
def skew(v):
    x,y,z=v
    return [[0.,-z,y],[z,0.,-x],[-y,x,0.]]


def rotation(v):
    t=dot(v,v)
    if val(t)<1e-8:
        a=1-t/6+t*t/120-t*t*t/5040
        b=.5-t/24+t*t/720-t*t*t/40320
    else:
        theta=t**.5
        a=sine(theta)/theta;b=(1-cosine(theta))/t
    k=skew(v);kk=matmul(k,k)
    return [[float(i==j)+a*k[i][j]+b*kk[i][j] for j in range(3)] for i in range(3)]


def left_jacobian(v):
    t=dot(v,v)
    if val(t)<1e-8:
        a=.5-t/24+t*t/720-t*t*t/40320
        b=1/6-t/120+t*t/5040-t*t*t/362880
    else:
        theta=t**.5
        a=(1-cosine(theta))/t;b=(theta-sine(theta))/(t*theta)
    k=skew(v);kk=matmul(k,k)
    return [[float(i==j)+a*k[i][j]+b*kk[i][j] for j in range(3)] for i in range(3)]


def log_rotation(a):
    c=(sum(a[i][i] for i in range(3))-1)/2
    theta=acos(c)
    scale=theta/(2*sine(theta))
    return [scale*(a[2][1]-a[1][2]),scale*(a[0][2]-a[2][0]),scale*(a[1][0]-a[0][1])]


def earth_rotation(angles):
    phi,theta,psi=angles
    cp,sp=cosine(phi),sine(phi)
    ct,st=cosine(theta),sine(theta)
    ch,sh=cosine(psi),sine(psi)
    rx=[[1.,0.,0.],[0.,cp,sp],[0.,-sp,cp]]
    ry=[[ct,0.,st],[0.,1.,0.],[-st,0.,ct]]
    rz=[[ch,sh,0.],[-sh,ch,0.],[0.,0.,1.]]
    return matmul(matmul(rz,ry),rx)


def euler_rate_matrix(angles):
    phi,theta,_=angles
    return [[-1.,0.,sine(theta)],[0.,cosine(phi),sine(phi)*cosine(theta)],
            [0.,sine(phi),-cosine(phi)*cosine(theta)]]


def jig_frame(degrees):
    # Straight +y material tangent; c=[cos(twist),0,-sin(twist)].
    return rotation([0.,math.radians(degrees),0.])


def geometry(q,fixture):
    r=[[fixture['deformed_nodes'][i][j]+q[6+3*i+j] for j in range(3)] for i in range(5)]
    Q=[matmul(rotation(q[21+3*i:24+3*i]),rotation(fixture['base_rotation_vectors'][i])) for i in range(5)]
    segments=[]
    for element in fixture['elements']:
        a,b=element['nodes']
        pa=[r[a][j]+x for j,x in enumerate(matvec(Q[a],element['offset_a']))]
        pb=[r[b][j]+x for j,x in enumerate(matvec(Q[b],element['offset_b']))]
        ra=matmul(Q[a],jig_frame(element['twist_a_deg']))
        rb=matmul(Q[b],jig_frame(element['twist_b_deg']))
        arc=log_rotation(matmul(transpose(ra),rb))
        segments.append((pa,pb,ra,arc))
    return r,Q,segments


def potential(coordinates,fixture,quadrature,*,second=False):
    q=[Jet.variable(v,i,second) for i,v in enumerate(coordinates)]
    r,Q,segments=geometry(q,fixture)
    re=earth_rotation(q[3:6])
    g=fixture['gravity']
    potential=Jet(0.,hessian=np.zeros((DIM,DIM)) if second else None)
    masses=[];centroids=[]
    for e,(pa,pb,ra,arc) in zip(fixture['elements'],segments):
        for t,w in zip(*quadrature):
            rotation_at=matmul(ra,rotation([t*x for x in arc]))
            axis=[(1-t)*a+t*b for a,b in zip(pa,pb)]
            for entry in e['mass_distributions']:
                mass=entry['mass_per_material_length']*e['material_length']*w
                point=[axis[j]+entry['Ccg']*rotation_at[j][0]+entry['Ncg']*rotation_at[j][2] for j in range(3)]
                earth_z=q[2]+dot(re[2],point)
                potential=potential+mass*g*earth_z
                masses.append(mass);centroids.append([val(v) for v in point])
    for entry in fixture['point_masses']:
        i=entry['node'];offset=matvec(Q[i],entry['pylon_offset'])
        point=[r[i][j]+offset[j] for j in range(3)]
        mass=entry['mass']
        potential=potential+mass*g*(q[2]+dot(re[2],point))
        masses.append(mass);centroids.append([val(v) for v in point])
    return dict(value=potential.v,gradient=potential.g,hessian=potential.h,
                masses=np.asarray(masses),centroids=np.asarray(centroids))


def generalized_load(q,nodal_force,nodal_moment,global_force,global_moment_reference,fixture):
    """Spatial load → exact coordinate covector; no production helper."""
    R=np.asarray(earth_rotation(q[3:6]),dtype=float)
    E=np.asarray(euler_rate_matrix(q[3:6]),dtype=float)
    moment_origin=np.asarray(global_moment_reference)+np.cross(fixture['moment_reference'],global_force)
    out=np.zeros(DIM)
    out[:3]=R@global_force
    out[3:6]=E.T@moment_origin
    out[6:21]=np.asarray(nodal_force).ravel()
    for i in range(5):
        J=np.asarray(left_jacobian(q[21+3*i:24+3*i]),dtype=float)
        out[21+3*i:24+3*i]=J.T@nodal_moment[i]
    return out


def self_checks():
    """Explicit elementary value/gradient/Hessian formulas, before physics."""
    x,y=.2,.3
    a,b=Jet.variable(x,0,True),Jet.variable(y,1,True)
    f=sine(a*b)+a*a/b+(2+a)**.5+acos(b/2)
    s,c=math.sin(x*y),math.cos(x*y)
    expected=math.sin(x*y)+x*x/y+math.sqrt(2+x)+math.acos(y/2)
    gradient=np.zeros(DIM)
    gradient[:2]=[y*c+2*x/y+.5/math.sqrt(2+x),x*c-x*x/(y*y)-.5/math.sqrt(1-y*y/4)]
    hessian=np.zeros((DIM,DIM))
    hessian[0,0]=-y*y*s+2/y-.25/(2+x)**1.5
    hessian[0,1]=hessian[1,0]=c-x*y*s-2*x/y**2
    hessian[1,1]=-x*x*s+2*x*x/y**3-y/(8*(1-y*y/4)**1.5)
    return dict(value_error=abs(f.v-expected),gradient_error=float(np.max(abs(f.g-gradient))),
                hessian_error=float(np.max(abs(f.h-hessian))))
