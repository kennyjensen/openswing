"""Independent infinite-wing solution of steady Eqs. 155–159 and 202–204.

Only scalar standard-library arithmetic is used. alpha and theta are radians;
theta is the combined twist/zero-lift/control rotation of the section normal.
The vortex direction is fixed at zero incidence when frozen=True.
"""
import math


def section(alpha, theta, *, frozen, slope=5.77, lower=-.4, upper=1.4,
            factor=40., width=.05, profile=.01364, control_slope=.071, twist=0.):
    phi=theta if frozen else alpha+theta
    incidence=alpha+theta
    if slope<=0 or width<=0 or lower>=upper or factor<0 or math.cos(phi)<=0:
        raise ValueError('Reference requires a positive slope/width/cos(phi) and ordered limits.')
    def softplus(x):return max(x,0.)+math.log1p(math.exp(-abs(x)))
    def sigmoid(x):
        e=math.exp(-abs(x))
        return 1/(1+e) if x>=0 else e/(1+e)
    def leakage(cl):
        a,b=(cl-upper)/width,(lower-cl)/width
        return width*(softplus(a)-softplus(b)),sigmoid(a)+sigmoid(b)
    def residual(cl):return slope*math.sin(incidence)-cl*math.cos(phi)-factor*leakage(cl)[0]
    # Strictly negative residual derivative proves uniqueness on this domain.
    lo,hi=-64.,64.
    if not residual(lo)>0>residual(hi):raise ValueError('Root is outside the declared reference bracket.')
    for _ in range(100):
        mid=(lo+hi)/2
        if residual(mid)>0:lo=mid
        else:hi=mid
    cl=(lo+hi)/2;value,gradient=leakage(cl)
    den=math.cos(phi)+factor*gradient
    cl_alpha=(slope*math.cos(incidence)+(0 if frozen else cl*math.sin(phi)))/den
    cl_theta=(slope*math.cos(incidence)+cl*math.sin(phi))/den
    tau=math.sin(incidence)-cl*math.cos(phi)/slope
    tau_alpha=math.cos(incidence)-(cl_alpha*math.cos(phi)-(0 if frozen else cl*math.sin(phi)))/slope
    tau_theta=math.cos(incidence)-(cl_theta*math.cos(phi)-cl*math.sin(phi))/slope
    cd=profile+4*tau*tau;cd_alpha=8*tau*tau_alpha;cd_theta=8*tau*tau_theta
    gain=control_slope/slope
    # Eq.72 applies the quarter-chord couple along the PHYSICAL chord. It
    # differs from the wind-directed sampling point in Eq.155, in both modes.
    arm_factor=math.cos(alpha+twist)
    cm=-.25*cl*arm_factor
    cm_alpha=-.25*(cl_alpha*arm_factor-cl*math.sin(alpha+twist))
    return dict(CL=cl,CD=cd,Cm=cm,section_leakage=value,section_leakage_slope=gradient,
        scalar_residual=residual(cl),normal_velocity_over_speed=tau,
        # State derivatives keep BASE stability axes; the nonlinear CL/CD are wind-axis values.
        alpha=dict(CX=cl-cd_alpha,CL=cl_alpha+cd,Cm=cm_alpha),
        control=dict(CX=-cd_theta*gain,CL=cl_theta*gain,Cm=-.25*cl_theta*gain*arm_factor))
