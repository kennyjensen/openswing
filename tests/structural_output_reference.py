"""Independent 80-digit physical section values using quaternion interpolation.

No production Jacobian, rotation weights, or SO(3) differential is used.
Two central-difference widths resolve geometry, rotated resultants and shell laws.
"""
from decimal import Decimal,localcontext
import numpy as np
from scipy.spatial.transform import Rotation


def high_precision_sections(system,vector,width='1e-20'):
    n=system.network
    with localcontext() as ctx:
        ctx.prec=80
        D=lambda x:Decimal.from_float(float(x))
        dec=lambda v:[D(x) for x in v]
        dot=lambda a,b:sum((x*y for x,y in zip(a,b)),Decimal(0))
        add=lambda a,b:[x+y for x,y in zip(a,b)]
        sub=lambda a,b:[x-y for x,y in zip(a,b)]
        mul=lambda v,a:[a*x for x in v]
        norm=lambda v:dot(v,v).sqrt()
        unit=lambda v:mul(v,1/norm(v))
        cross=lambda a,b:[a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]]
        def quaternion(matrix):
            xyzw=Rotation.from_matrix(matrix).as_quat()
            return unit(dec([xyzw[3],*xyzw[:3]]))
        def product(a,b):
            return [a[0]*b[0]-dot(a[1:],b[1:]),*add(add(mul(b[1:],a[0]),mul(a[1:],b[0])),cross(a[1:],b[1:]))]
        conj=lambda q:[q[0],*mul(q[1:],-1)]
        def rotate(q,v):return product(product(q,[Decimal(0),*v]),conj(q))[1:]
        def incremental(theta):
            square=dot(theta,theta)/4;cos=Decimal(1);sinc=Decimal('.5');tc=cos;ts=sinc
            for k in range(1,90):
                tc*=-square/((2*k-1)*(2*k));ts*=-square/((2*k)*(2*k+1))
                cos+=tc;sinc+=ts
                if abs(tc)+abs(ts)<Decimal('1e-90'):break
            return [cos,*mul(theta,sinc)]
        def series(x):
            total=term=x;k=1
            while abs(term)>Decimal('1e-90'):
                term*=-x*x;total+=term/(2*k+1);k+=1
            return total
        pi=16*series(Decimal(1)/5)-4*series(Decimal(1)/239)
        def atan(x):
            if x>1:return pi/2-atan(1/x)
            times=0
            while x>Decimal('.2'):
                x=x/(1+(1+x*x).sqrt());times+=1
            return series(x)*2**times
        def log(q):
            if q[0]<0:q=mul(q,-1)
            length=norm(q[1:])
            if not length:return [Decimal(0)]*3
            return mul(q[1:],2*atan(length/q[0])/length)
        pa,pb,ra,rb,oa,ob=n.geometry(system.r0,system.Q0)
        frames=[(quaternion(a),quaternion(b)) for a,b in zip(ra,rb)]
        shell=np.zeros((n.ne,3));defined=np.zeros(n.ne,dtype=bool)
        for mesh in n.meshes:
            b=mesh.beam;sl=n.beam_elements[b.index]
            shell[sl]=np.array([b.value(key,mesh.ts) for key in ['Cshell','Nshell','Atshell']]).T
            defined[sl]='Cshell' in b.distributions or 'Nshell' in b.distributions
        F,L,position_scale=D(n.F),D(n.L),D(system.L);h=Decimal(width)
        loads=system.base[6*n.nn:6*(n.nn+n.ne)].reshape(n.ne,6)
        result=[]
        for part in (np.real(vector),np.imag(vector)):
            values=[]
            for e,(i,j) in enumerate(n.ends):
                qa,qb=frames[e]
                if dot(qa,qb)<0:qb=mul(qb,-1)
                section=n.sections[e];ds=D(n.ds[e]);r1=dec(system.r0[i]);r2=dec(system.r0[j]);o1=dec(oa[e]);o2=dec(ob[e])
                base=dec(loads[e]);v=dec(part[6*n.nn+6*e:6*n.nn+6*e+6])
                u1=dec(part[6*i:6*i+6]);u2=dec(part[6*j:6*j+6]);cs,ns,area=dec(shell[e])
                def physical(sign):
                    dh=sign*h;t1=incremental(mul(u1[3:],dh));t2=incremental(mul(u2[3:],dh))
                    a=product(t1,qa);b=product(t2,qb);mid=unit(add(a,b));relative=product(conj(a),b)
                    force=mul(add(base[:3],mul(v[:3],dh)),F)
                    moment=mul(add(base[3:],mul(v[3:],dh)),F*L)
                    local_force=rotate(conj(mid),force);local_moment=rotate(conj(mid),moment)
                    p1=add(add(r1,mul(u1[:3],position_scale*dh)),rotate(t1,o1))
                    p2=add(add(r2,mul(u2[:3],position_scale*dh)),rotate(t2,o2))
                    strain=mul(sub(rotate(conj(mid),sub(p2,p1)),dec(n.v0[e])),1/ds)
                    curvature=mul(sub(log(relative),dec(n.k0[e])),1/ds)
                    axial=strain[1]-D(section.Nta)*curvature[0]+D(section.Cta)*curvature[2]
                    shell_strain=axial+cs*curvature[2]-ns*curvature[0] if defined[e] else Decimal(0)
                    stress=(local_moment[1]-D(section.Nea)*local_force[0]+D(section.Cea)*local_force[2])/(2*area) if area>0 else Decimal(0)
                    return local_force+local_moment+strain+curvature+[axial,shell_strain,stress]
                plus,minus=physical(1),physical(-1)
                values.append([float((a-b)/(2*h)) for a,b in zip(plus,minus)])
            result.append(np.array(values))
        return result[0]+1j*result[1]
