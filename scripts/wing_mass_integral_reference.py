"""Continuous interval mass-wrench diagnostic, independent of OpenSwing.

Linear endpoint material/centerline interpolation, geodesic section frames and
their exact rotation tangent. Gauss integration includes the line's rotary
inertia geometrically; it must NOT also add steady Eq.80's ds^2/12 correction.
This is a declared quadrature diagnostic, not a replacement ASWING method.
"""
import numpy as np
from scipy.spatial.transform import Rotation
from fin_apparent_reference import jacobian
from wing_inertia_reference import PARTS


def integrate(data, motion, omega, order):
    nodes,weights=np.polynomial.legendre.leggauss(order)
    r=data['node_positions'];dr=motion['displacement'];theta=motion['rotation']
    u=motion['velocity'];w=motion['rates'];U=motion['frame_velocity'];W=motion['frame_rates']
    g=data['gravity'];gconst=float(data['g_constant']);alpha=1j*omega*W
    dg=-np.cross(W/(1j*omega),g)
    # Fixture sample order: main (left,right), additional (left,right).
    ne=len(data['a'])//4;assert 4*ne==len(data['a'])
    wrench=np.zeros((len(PARTS),6),complex);total_mass=0.
    for prefix in range(2):
        for element in range(ne):
            ia=(2*prefix)*ne+element;ib=ia+ne
            a=int(data['a'][ia]);b=int(data['b'][ia])
            assert data['node'][ia]==a and data['node'][ib]==b
            qa,qb=data['frames'][ia],data['frames'][ib]
            arc=Rotation.from_matrix(qa.T@qb).as_rotvec()
            for xi,weight in zip(nodes,weights):
                f=(xi+1)/2;length=data['ds'][ia]*weight/2
                interp=lambda key:(1-f)*data[key][ia]+f*data[key][ib]
                q=qa@Rotation.from_rotvec(f*arc).as_matrix()
                wb=qa@(f*jacobian(f*arc))@np.linalg.solve(jacobian(arc),qa.T)
                t=theta[a]+wb@(theta[b]-theta[a]);rate=w[a]+wb@(w[b]-w[a])
                axis=(1-f)*r[a]+f*r[b];daxis=(1-f)*dr[a]+f*dr[b]
                velocity=(1-f)*u[a]+f*u[b];offset=q@interp('cg_local')
                mass=interp('weight_density')*length/gconst;total_mass+=mass
                icc=interp('icc_weight_density')*length/gconst
                inn=interp('inn_weight_density')*length/gconst
                tensor=(q*np.array([icc,icc+inn,inn]))@q.T
                forces=np.zeros((len(PARTS),3),complex);couples=np.zeros_like(forces)
                accelerations=[1j*omega*U,np.cross(W,data['base_velocity']),
                    np.cross(alpha,axis+offset),1j*omega*velocity,np.cross(1j*omega*rate,offset)]
                for j,value in enumerate(accelerations):forces[j]=-mass*value
                forces[7]=mass*dg
                couples[5]=-tensor@(alpha+1j*omega*rate)
                # CG arm and axis arm are separate so each term can be compared
                # with the endpoint replay's decomposition.
                couples+=np.cross(offset,forces)
                couples[8]=np.cross(np.cross(t,offset),mass*g)
                couples+=np.cross(axis-data['moment_reference'],forces)
                couples[9]=np.cross(daxis-motion['reference_displacement'],mass*g)
                wrench+=np.c_[forces,couples]
    return wrench,total_mass
