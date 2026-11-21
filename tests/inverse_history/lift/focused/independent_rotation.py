"""Independent noncommuting rigid-body trajectory and reference-airdata oracle.

Only Python stdlib and NumPy are used. No production OpenSwing helpers.
Angles are prescribed in degrees with physical time in seconds. Units converts
those physical inputs into consistent model length/time/force units.
"""
from dataclasses import dataclass
import numpy as np


@dataclass(frozen=True)
class Units:
    """Physical SI amount of one model length, time, and force unit."""
    length_m: float = 1.
    time_s: float = 1.
    force_N: float = 1.

    def __post_init__(self):
        if any(isinstance(x, bool) or not np.isfinite(x) or x <= 0
               for x in (self.length_m, self.time_s, self.force_N)):
            raise ValueError('Unit scales must be finite positive numbers.')


MASS_KG = 3.7
INERTIA_CG = np.array([[2.2,.18,-.11],[.18,3.1,.24],[-.11,.24,4.]])
CG = np.array([.24,-.17,.11])
RM = np.array([-.35,.28,.09])
RA = np.array([.41,.12,-.23])
RV = np.array([-.18,.36,.27])
P0 = np.array([2.,-1.,4.])
VE = np.array([-24.,3.,1.8])
RHO0 = 1.225
DENSITY_RATIO = .64
GUST_G = np.array([[.010,-.020,.015],[.025,.005,-.010],[-.012,.018,.008]])


def skew(v):
    x,y,z = v
    return np.array([[0.,-z,y],[z,0.,-x],[-y,x,0.]])


def vee(a):
    return np.array([a[2,1],a[0,2],a[1,0]])


def angles(t_seconds):
    """Return bank/elevation/heading and their first two SI-time derivatives.

    All three arrays are in degrees (degrees/s, degrees/s^2 for derivatives).
    Validated fixture interval is [0,1.6] s; formulas remain analytic outside it.
    """
    t = float(t_seconds)
    a = np.array([14+9*np.sin(.9*t)+2*t*t,
                  -8+5*np.sin(.6*t+.4)+1.5*t,
                  23+11*t+4*np.sin(1.1*t-.2)])
    d = np.array([8.1*np.cos(.9*t)+4*t,
                  3*np.cos(.6*t+.4)+1.5,
                  11+4.4*np.cos(1.1*t-.2)])
    dd = np.array([-7.29*np.sin(.9*t)+4,
                   -1.8*np.sin(.6*t+.4),
                   -4.84*np.sin(1.1*t-.2)])
    return a,d,dd


def axial_rotation(axis, q, qd, qdd):
    """A fixed-axis elementary rotation and its exact time derivatives."""
    c,s = np.cos(q),np.sin(q)
    if axis == 0:
        r = np.array([[1.,0.,0.],[0.,c,-s],[0.,s,c]])
    elif axis == 1:
        r = np.array([[c,0.,s],[0.,1.,0.],[-s,0.,c]])
    elif axis == 2:
        r = np.array([[c,-s,0.],[s,c,0.],[0.,0.,1.]])
    else:
        raise ValueError('Axis must be 0, 1 or 2.')
    generator = skew(np.eye(3)[axis])
    return r, qd*(generator@r), qdd*(generator@r)+qd*qd*(generator@generator@r)


def rotation_jet(t, units=Units()):
    """Exact R, dR/d(input time), d2R/d(input time)^2 by product differentiation."""
    a,d,dd = angles(float(t)*units.time_s)
    signs = np.array([-1.,1.,-1.])
    q = np.deg2rad(a)*signs
    qd = np.deg2rad(d)*signs*units.time_s
    qdd = np.deg2rad(dd)*signs*units.time_s**2
    x,xd,xdd = axial_rotation(0,q[0],qd[0],qdd[0])
    y,yd,ydd = axial_rotation(1,q[1],qd[1],qdd[1])
    z,zd,zdd = axial_rotation(2,q[2],qd[2],qdd[2])
    r = z@y@x
    rd = zd@y@x+z@yd@x+z@y@xd
    rdd = zdd@y@x+z@ydd@x+z@y@xdd+2*(zd@yd@x+zd@y@xd+z@yd@xd)
    return r,rd,rdd


def euler_body_rates(t, units=Units()):
    """Independent closed Euler-coordinate expressions for Omega and alpha."""
    a,d,dd = angles(float(t)*units.time_s)
    phi,theta,psi = np.deg2rad(a)*[-1,1,-1]
    pd,td,sd = np.deg2rad(d)*[-1,1,-1]*units.time_s
    pdd,tdd,sdd = np.deg2rad(dd)*[-1,1,-1]*units.time_s**2
    cp,sp,ct,st = np.cos(phi),np.sin(phi),np.cos(theta),np.sin(theta)
    omega = np.array([pd-sd*st, td*cp+sd*sp*ct, -td*sp+sd*cp*ct])
    alpha = np.array([pdd-sdd*st-sd*td*ct,
                      tdd*cp-td*pd*sp+sdd*sp*ct+sd*pd*cp*ct-sd*td*sp*st,
                      -tdd*sp-td*pd*cp+sdd*cp*ct-sd*pd*sp*ct-sd*td*cp*st])
    return omega,alpha


def gust_earth(position, t, units=Units()):
    """Spatial/time-dependent gust in Earth components, in model L/T."""
    ts = float(t)*units.time_s
    x = np.asarray(position)*units.length_m
    v = (np.array([1.2,-.5,.3])+GUST_G@(x-P0)
         +np.array([.7,-.3,.2])*np.sin(.7*ts)
         +np.array([-.2,.15,.1])*np.cos(.4*ts))
    return v*units.time_s/units.length_m


def sample(t, units=Units()):
    """Return required applied loads, trajectory, reference transport and airdata.

    Applied force is the positive external force required by Newton's equation.
    Applied moment at the selected reference is the positive external moment.
    A solver's reported inertial/support reactions may have opposite signs.
    """
    if isinstance(t,(bool,np.bool_)) or not np.isscalar(t) or not np.isfinite(t):
        raise ValueError('Time must be a finite real scalar.')
    t = float(t)
    L,T,F = units.length_m,units.time_s,units.force_N
    r,rd,rdd = rotation_jet(t,units)
    omega = vee(r.T@rd)
    alpha = vee(r.T@rdd-(r.T@rd)@(r.T@rd))
    mass = MASS_KG*L/(F*T*T)
    inertia = INERTIA_CG/(F*L*T*T)
    cg,rm,ra,rv = CG/L,RM/L,RA/L,RV/L
    v_origin = VE*T/L
    p = P0/L+v_origin*t
    u = r.T@v_origin
    udot = rd.T@v_origin
    a_cg = np.cross(alpha,cg)+np.cross(omega,np.cross(omega,cg))
    force = mass*a_cg
    torque_cg = inertia@alpha+np.cross(omega,inertia@omega)
    torque_m = torque_cg+np.cross(cg-rm,force)
    a_ref = np.cross(alpha,ra)+np.cross(omega,np.cross(omega,ra))
    v_ref_body = u+np.cross(omega,rv)
    v_ref_earth = v_origin+rd@rv
    p_ref = p+r@rv
    gust = gust_earth(p_ref,t,units)
    airflow = r.T@(gust-v_ref_earth)
    speed = np.linalg.norm(airflow)
    rho0 = RHO0*L**4/(F*T*T)
    rho = DENSITY_RATIO*rho0
    bank_elevation_heading,angles_d,angles_dd = angles(t*T)
    return dict(time=t,position_earth=p,velocity_origin_earth=v_origin,
                velocity_origin_body=u,velocity_origin_body_derivative=udot,
                origin_acceleration_body=np.zeros(3),R=r,Rdot=rd,Rddot=rdd,
                angles_deg=bank_elevation_heading,
                angles_derivative_deg=angles_d*T,angles_second_derivative_deg=angles_dd*T*T,
                omega_body=omega,alpha_body=alpha,mass=mass,inertia_cg_body=inertia,
                cg_body=cg,moment_reference_body=rm,acceleration_reference_body=ra,
                velocity_reference_body=rv,
                cg_position_earth=p+r@cg,cg_velocity_earth=v_origin+rd@cg,
                cg_acceleration_body=a_cg,
                force_body=force,torque_cg_body=torque_cg,torque_moment_reference_body=torque_m,
                acceleration_reference_body_value=a_ref,
                acceleration_reference_earth=rdd@ra,
                velocity_reference_body_value=v_ref_body,velocity_reference_earth=v_ref_earth,
                velocity_reference_position_earth=p_ref,
                gust_reference_earth=gust,airflow_reference_body=airflow,
                rho=rho,rho0=rho0,
                airdata=dict(V_IAS=float(speed*np.sqrt(rho/rho0)),V_true=float(speed),
                             A_deg=float(np.rad2deg(np.arctan2(airflow[2],airflow[0]))),
                             B_deg=float(np.rad2deg(np.arctan2(-airflow[1],np.hypot(airflow[0],airflow[2]))))))


def jsonable(value):
    if isinstance(value,np.ndarray):return value.tolist()
    if isinstance(value,dict):return {k:jsonable(v) for k,v in value.items()}
    if isinstance(value,list):return [jsonable(v) for v in value]
    if isinstance(value,np.generic):return value.item()
    return value
