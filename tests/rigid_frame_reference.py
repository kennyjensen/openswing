"""Independent twelve-state Newton-Euler model, without OpenSwing imports.

One unit mass at the body origin, principal inertia (2,3,4). Constant body
loads and separate moment/acceleration references. Complex-step derivatives
retain all transport and Euler-chart terms about a possibly accelerating base.
"""
import numpy as np


def rotation(q):
    p,t,h=q;c=np.cos(q);s=np.sin(q)
    return (np.array([[c[2],s[2],0],[-s[2],c[2],0],[0,0,1]])@
            np.array([[c[1],0,s[1]],[0,1,0],[-s[1],0,c[1]]])@
            np.array([[1,0,0],[0,c[0],s[0]],[0,-s[0],c[0]]]))


def acceleration(omega,inputs):
    rm=np.array([.7,.1,-.2]);ra=np.array([.3,-.2,.4]);I=np.diag([2.,3.,4.])
    # Inputs: Fx, Ay, Fz, Gx, My, Gz. Selected net targets determine ax, az, gy.
    prescribed=np.array([0,.7,0,.1,0,-.2],dtype=np.result_type(omega,inputs))
    prescribed[[1,3,5]]+=inputs[[1,3,5]]
    desired=np.array([.4,-.7,.2])+inputs[[0,2,4]]
    def wrench(a):
        acg=a[:3]+np.cross(a[3:],-ra)+np.cross(omega,np.cross(omega,-ra))
        force=np.array([1,2,3])-acg
        moment=np.array([.2,-.1,.3])-I@a[3:]-np.cross(omega,I@omega)+np.cross(-rm,force)
        return np.r_[force,moment]
    base=wrench(prescribed);indices=[0,2,4]
    matrix=np.column_stack([wrench(prescribed+np.eye(6)[i])-base for i in indices])[indices]
    prescribed[indices]=np.linalg.solve(matrix,desired-base[indices])
    return prescribed,wrench(prescribed)


def rhs(state,inputs):
    U,omega,position,angles=state.reshape(4,3)
    a,_=acceleration(omega,inputs);ra=np.array([.3,-.2,.4])
    phi,theta,_=angles
    E=np.array([[-1,0,np.sin(theta)],[0,np.cos(phi),np.sin(phi)*np.cos(theta)],
                [0,np.sin(phi),-np.cos(phi)*np.cos(theta)]])
    acg=a[:3]+np.cross(a[3:],-ra)+np.cross(omega,np.cross(omega,-ra))
    return np.r_[acg-np.cross(omega,U),a[3:],rotation(angles)@U,np.linalg.solve(E,omega)]


def jacobian(function,x):
    h=1e-25
    return np.column_stack([np.imag(function(x.astype(complex)+1j*h*e))/h for e in np.eye(len(x))])


def harmonic(state,frequencies):
    zero=np.zeros(6);A=jacobian(lambda q:rhs(q,zero),state);B=jacobian(lambda u:rhs(state,u),zero)
    ax=jacobian(lambda q:acceleration(q[3:6],zero)[0],state)
    au=jacobian(lambda u:acceleration(state[3:6],u)[0],zero)
    fx=jacobian(lambda q:acceleration(q[3:6],zero)[1],state)
    fu=jacobian(lambda u:acceleration(state[3:6],u)[1],zero)
    values=[]
    for w in frequencies:
        q=np.linalg.solve(1j*w*np.eye(12)-A,B)
        values.append(dict(state=q,acceleration=ax@q+au,wrench=fx@q+fu))
    return values
