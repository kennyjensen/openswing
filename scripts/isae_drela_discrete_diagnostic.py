"""Independent diagnostic of ASWING steady Eqs. 48, 51, 53–56.

Zero section-axis/CG offsets only. No production imports, model parsing, or
equilibrium solve. Angles are [phi, theta, psi] in radians. Length is explicit:
the caller must not infer that loaded ds and unloaded ds0 are interchangeable.
Eq. 54 prints E_a^{-1}: invert averaged stiffness, not average compliance.
"""
import numpy as np


def transform(angles):
    """Eq. 4, body to local csn."""
    phi, theta, psi = angles
    cp, ct, cs = np.cos([phi, theta, psi])
    sp, st, ss = np.sin([phi, theta, psi])
    return np.array([[ct*cs, ct*ss*cp+st*sp, ct*ss*sp-st*cp],
                     [-ss, cs*cp, cs*sp],
                     [st*cs, st*ss*cp-ct*sp, st*ss*sp+ct*cp]])


def angle_matrix(angles):
    """Eq. 8, maps [dphi,dtheta,dpsi] to csn curvature increment."""
    _, theta, psi = angles
    ct, cs = np.cos([theta, psi])
    st, ss = np.sin([theta, psi])
    return np.array([[cs*ct, 0., -st], [-ss, 1., 0.], [cs*st, 0., ct]])


def angles_from_frame(frame):
    s = frame[:, 1]
    phi, psi = np.arctan2(s[2], s[1]), -np.arcsin(np.clip(s[0], -1., 1.))
    c0 = np.array([np.cos(psi), np.sin(psi)*np.cos(phi), np.sin(psi)*np.sin(phi)])
    n0 = np.array([0., -np.sin(phi), np.cos(phi)])
    return np.array([phi, np.arctan2(-frame[:, 0]@n0, frame[:, 0]@c0), psi])


def operators(left, right, ds0, ds):
    """All inputs explicit; return defects and distinct alternative operators.

    Endpoint keys: r,r0,angles,angles0,F,M,EA,E (3x3 bending stiffness), f.
    F/M/f are body vectors. No finite-width concentrated load is included.
    Axial strain uses Fs_a/EA_a as a declared scalar-property interpretation;
    unlike bending Eq.54, Eq.48 does not explicitly print this scalar average.
    """
    a, b = left, right
    dtheta, dtheta0 = b['angles']-a['angles'], b['angles0']-a['angles0']
    assert np.max(abs(dtheta)) < np.pi and np.max(abs(dtheta0)) < np.pi
    Ta = (transform(a['angles'])+transform(b['angles']))/2
    T0a = (transform(a['angles0'])+transform(b['angles0']))/2
    Ka = (angle_matrix(a['angles'])+angle_matrix(b['angles']))/2
    K0a = (angle_matrix(a['angles0'])+angle_matrix(b['angles0']))/2
    Fbar, Mbar = (a['F']+b['F'])/2, (a['M']+b['M'])/2
    Flocal, Mlocal = Ta@Fbar, Ta@Mbar
    Ebar = (a['E']+b['E'])/2
    curvature = Ka@dtheta-K0a@dtheta0
    bending = np.linalg.solve(Ebar, Mlocal)*ds
    compliance_average = (np.linalg.solve(a['E'], Mlocal)+np.linalg.solve(b['E'], Mlocal))*ds/2
    strain = Flocal[1]/((a['EA']+b['EA'])/2)
    dr, dr0 = b['r']-a['r'], b['r0']-a['r0']
    compatibility = dr-Ta.T@np.array([0., 1.+strain, 0.])*ds0
    jig_defect = dr0-T0a.T@np.array([0., 1., 0.])*ds0
    return dict(T_average=Ta, K_average=Ka, body_force_average=Fbar,
        body_moment_average=Mbar, local_force_average=Flocal, local_moment_average=Mlocal,
        stiffness_average=Ebar, curvature_increment=curvature,
        bending_increment=bending, bending_increment_average_compliance=compliance_average,
        curvature_defect=curvature-bending,
        alternative_average_compliance_defect=curvature-compliance_average,
        axial_strain=strain, compatibility_defect=compatibility, jig_compatibility_defect=jig_defect,
        incremental_compatibility_diagnostic=compatibility-jig_defect,
        force_balance=b['F']-a['F']+(a['f']+b['f'])*ds/2,
        moment_balance=b['M']-a['M']+np.cross(dr,Fbar))


def algebra_checks():
    checks=[]
    def check(name, error, tolerance):
        checks.append(dict(name=name, error=float(error), tolerance=tolerance, passes=bool(error<=tolerance)))
    for i, q in enumerate([[0.,0.,0.],[.4,-.2,.8],[-.7,.3,-.9]]):
        q=np.array(q);T=transform(q)
        check(f'orthogonal/{i}',np.max(abs(T@T.T-np.eye(3))),1e-14)
        check(f'angle-roundtrip/{i}',np.max(abs(angles_from_frame(T.T)-q)),1e-14)
        for j in range(3):
            step=np.eye(3)[j]*1e-6
            dT=(transform(q+step)-transform(q-step))/(2e-6)
            skew=-dT@T.T
            v=np.array([skew[2,1],skew[0,2],skew[1,0]])
            check(f'continuous-K-derivative/{i}/{j}',np.max(abs(v-angle_matrix(q)[:,j])),2e-10)
    for q in [np.zeros(3),np.array([.4,-.2,.8])]:
        T=transform(q);a=dict(r=np.zeros(3),r0=np.zeros(3),angles=q,angles0=q,
            F=np.zeros(3),M=np.zeros(3),EA=1000.,E=np.diag([200.,300.,400.]),f=np.zeros(3))
        b={**a,'r':T.T@np.array([0.,2.,0.]),'r0':T.T@np.array([0.,2.,0.])}
        p=operators(a,b,2.,2.)
        for name in ['curvature_defect','compatibility_defect','force_balance','moment_balance']:
            check('straight-unloaded/'+str(q.tolist())+'/'+name,np.max(abs(p[name])),1e-14)
    a=dict(r=np.zeros(3),r0=np.zeros(3),angles=np.zeros(3),angles0=np.zeros(3),
        F=np.array([0.,10.,0.]),M=np.zeros(3),EA=1000.,E=np.diag([200.,300.,400.]),f=np.zeros(3))
    b={**a,'r':np.array([0.,2.02,0.]),'r0':np.array([0.,2.,0.])}
    check('constant-axial-extension',np.max(abs(operators(a,b,2.,2.)['compatibility_defect'])),1e-14)
    return checks
