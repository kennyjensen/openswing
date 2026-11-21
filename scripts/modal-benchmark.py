"""Independent two-dimensional heave/pitch/circulation model and ASW input."""
import numpy as np
from scipy.linalg import eigvals
from openswing.asw import parse_asw

RHO = 1.225
MASS = RHO*np.pi/4*20
J_AXIS = MASS*.06
ECCENTRICITY = .1
X_AXIS = .4
KH = MASS*20**2
KT = J_AXIS*50**2


def typical_section(speed):
    """h is upward, theta about body +y; c=1, forces per unit span.

    Independent 5x5 pencil, state [h, theta, hdot, thetadot, Gamma].
    Lift= rho(V Gamma + c Gamma_dot); tau Gamma_dot+Gamma =
    pi c [V theta - hdot + (quarter_arm+c/2) thetadot].
    Noncirculatory force acts at midchord, with the printed pitch couple.
    """
    c = 1.; ma = RHO*np.pi*c*c/4
    a, d, e = (.25-X_AXIS)*c, (.5-X_AXIS)*c, ECCENTRICITY
    m, j = MASS, J_AXIS
    A, M = np.zeros((5, 5)), np.zeros((5, 5))
    M[0, 0] = M[1, 1] = 1.; A[0, 2] = A[1, 3] = 1.
    M[2, 2:] = [m+ma, -m*e-ma*d, -RHO*c]
    M[3, 2:] = [-m*e-ma*d, j+ma*(d*d+c*c/32), a*RHO*c]
    A[2, [0, 3, 4]] = [-KH, ma*speed, RHO*speed]
    A[3, [1, 3, 4]] = [-KT, -ma*(d+c/4)*speed, -a*RHO*speed]
    M[4, 4] = 2*c/speed
    A[4, [1, 2, 3, 4]] = [np.pi*c*speed, -np.pi*c, np.pi*c*(a+c/2), -1.]
    return eigvals(A, M)


def configuration(span=40):
    # A massless vertical axial spring and a y-axis sprung hinge support a
    # rigid wing. A point Weight provides heave/pitch mass and CG eccentricity.
    g = 9.80665; inertia = (J_AXIS-MASS*ECCENTRICITY**2)*span*g
    return parse_asw(f'''! Original OpenSwing heave/pitch verification example.
Name
Heave and pitch research wing
End
Unit
L 1 m
T 1 s
F 1 N
End
Constant
{g} {RHO} 340.294
End
Reference
{span} 1 {span}
End
Ground
1 0 0
End
Joint
1 2 1 0 3
End
Jangle
1 0 1 0
{-KT*span} {-180/np.pi}
{KT*span} {180/np.pi}
End
Weight
2 0 {ECCENTRICITY} 0 1 {MASS*span*g} 0 0 0 0 0 {inertia} {inertia} {inertia}
End
Beam 1
Massless heave spring
t x y z EA
0 0 0 0 {KH*span}
1 0 0 1 {KH*span}
End
Beam 2
Rigid symmetric wing
t x y z chord Xax Cdf dCLda CLmax CLmin
0 0 0 1 1 {X_AXIS} 0 {2*np.pi} 100 -100
{span/2} 0 {span/2} 1 1 {X_AXIS} 0 {2*np.pi} 100 -100
End
''')
