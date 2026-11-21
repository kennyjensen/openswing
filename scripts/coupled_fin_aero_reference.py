"""Independent aerodynamic equations for one rigid fin on a free carrier.

This is a SOURCE-ONLY candidate until the enclosing study authorizes execution.
No production imports, equilibrium routine, factorization or solve is present.

Coordinates are q=(r_E[3], phi_E[3], eta), with R=exp(phi x), hinge
Q=exp(eta k x), and fin rotation R Q.  dq and ddq are coordinate time
derivatives, not a mixture of angular rates and rotation-vector derivatives.
The inertial frame translates at the nominal carrier velocity -U e_x; the
otherwise still atmosphere therefore has velocity +U e_x in these coordinates.

Primary basis: Drela asw_theory.pdf Eqs.155--161 (virtual wind-aligned
horseshoes, control normal and Biot--Savart); asw_uns_theory.pdf Eqs.22--27
(absolute kinematics), 34--36 (circulatory loads), 41--44 (apparent loads),
48--49 (circulation lag).  Sources are https://web.mit.edu/drela/Public/web/
aswing/asw_theory.pdf and .../asw_uns_theory.pdf.  The source-review receipt
pins the cached primary texts and the explicitly compared implementation.

Declared CURRENT model conventions, not a claim of legacy-ASWING parity:
* CP/Hv geometry AND relative-velocity sampling use virtual wind-aligned points.
  Lift/rate moments instead use the material quarter chord.  Unsteady 29--31
  describe material quarter-chord motion, so this distinction remains explicit.
* Axis apparent-rate velocity excludes the source's own bound segment; CP
  includes it, Hv excludes it.  All same-surface core radii are exactly zero.
* Profile drag acts at the beam axis; Cm is an intrinsic span couple, with
  local-normal Mach correction even though the field PG Mach is fixed to zero.
* Apparent force acts at material half chord, with the separate pitch couple.
* Lag toggles both shed-downwash and Gamma-rate lift, never apparent mass.
* Native F3 changes alpha0 by F3*dCLdF3/CLa.  There is no additional degree,
  lift-slope or output scaling.  Fin section incidence is not flight alpha.

All norms/dot products use the analytic bilinear continuation (no conjugates).
The only real-part branches are explicit validity/exclusion tests and stable
SO(3) coefficient evaluation.  This supports complex-step differentiation near
the frozen real, positive-speed, nonsingular manufactured base.
"""

import math
import numpy as np


def norm(value, axis=-1):
    """Analytic continuation of the real Euclidean norm."""
    value = np.asarray(value)
    return np.sqrt(np.sum(value * value, axis=axis))


def skew(value):
    x, y, z = np.asarray(value)
    return np.array([[0, -z, y], [z, 0, -x], [-y, x, 0]],
                    dtype=np.result_type(value, float))


def _coefficient(z, offset, derivative=False):
    """sum_k (-z)^k/(2k+offset)!, or its derivative; stable at phi=0."""
    if abs(z) < 1e-6:
        if derivative:
            return sum(k * (-1)**k * z**(k-1) / math.factorial(2*k+offset)
                       for k in range(1, 8))
        return sum((-1)**k * z**k / math.factorial(2*k+offset)
                   for k in range(8))
    t = np.sqrt(z)
    if offset == 1:
        return ((t*np.cos(t)-np.sin(t))/(2*t**3) if derivative
                else np.sin(t)/t)
    if offset == 2:
        return ((t*np.sin(t)-2*(1-np.cos(t)))/(2*t**4) if derivative
                else (1-np.cos(t))/z)
    if offset == 3:
        return ((t*(1-np.cos(t))-3*(t-np.sin(t)))/(2*t**5)
                if derivative else (t-np.sin(t))/t**3)
    raise ValueError('Unsupported rotation coefficient')


def rotation(phi):
    """Rodrigues exponential of an Earth-axis rotation vector, analytic at 0."""
    phi = np.asarray(phi)
    z = np.sum(phi*phi)
    k = skew(phi)
    return np.eye(3) + _coefficient(z, 1)*k + _coefficient(z, 2)*(k@k)


def left_jacobian(phi):
    """Map rotation-vector time derivative to Earth angular velocity."""
    phi = np.asarray(phi)
    z = np.sum(phi*phi)
    k = skew(phi)
    return np.eye(3) + _coefficient(z, 2)*k + _coefficient(z, 3)*(k@k)


def left_jacobian_rate(phi, phidot):
    """Exact directional/time derivative of the left Jacobian."""
    phi, phidot = np.asarray(phi), np.asarray(phidot)
    z, zdot = np.sum(phi*phi), 2*np.sum(phi*phidot)
    k, kd = skew(phi), skew(phidot)
    return (_coefficient(z, 2)*kd + _coefficient(z, 3)*(kd@k+k@kd)
            + zdot*(_coefficient(z, 2, True)*k
                    + _coefficient(z, 3, True)*(k@k)))


class Reference:
    """Independent field/load map, with no implicit base or response solve.

    Required fixture keys: speed, density, sound_speed; hinge.position,
    hinge.axis, hinge.base_angle_degrees; fin.length/chord/Xax/alpha_degrees/
    CLa/dCLdF3/Cdf/Cdp/Cm.  The fin's unrotated material c,s axes are +x,+z.
    Optional field_recorder(key, geometry, fields, diagnostics) is called once
    for each newly integrated cache entry; it may save data but must not mutate.
    """

    def __init__(self, n, degree, fixture, field_recorder=None):
        if int(n) != n or n < 1 or int(degree) != degree or degree < 1:
            raise ValueError('Positive integer panel and quadrature counts required')
        self.n, self.degree = int(n), int(degree)
        self.fixture, self.fin = fixture, fixture['fin']
        self.speed = float(fixture['speed'])
        self.rho = float(fixture['density'])
        self.sound = float(fixture['sound_speed'])
        self.H = np.asarray(fixture['hinge']['position'], dtype=float)
        self.k = np.asarray(fixture['hinge']['axis'], dtype=float)
        self.k = self.k/norm(self.k)
        self.eta0 = float(fixture['hinge']['base_angle_degrees'])*np.pi/180
        self.chord = float(self.fin['chord'])
        self.xax = float(self.fin['Xax'])
        self.length = float(self.fin['length'])
        self.slope = float(self.fin['CLa'])
        self.control_slope = float(self.fin['dCLdF3'])/self.slope
        self.alpha0 = float(self.fin['alpha_degrees'])*np.pi/180
        if min(self.speed, self.rho, self.sound, self.length,
               self.chord, self.slope) <= 0:
            raise ValueError('Invalid positive physical fixture constant')
        # Independent cosine interval endpoints AND cosine-midangle receivers.
        self.t = self.length/2*(1-np.cos(np.arange(self.n+1)*np.pi/self.n))
        self.t[0], self.t[-1] = 0., self.length
        self.tm = self.length/2*(1-np.cos((np.arange(self.n)+.5)*np.pi/self.n))
        self.ds = np.diff(self.t)
        self.nodes, self.weights = np.polynomial.legendre.leggauss(self.degree)
        self.cache = {}
        self.fields = 0
        self.field_sets = 0
        self.evaluations = 0
        self.field_recorder = field_recorder

    def base_coordinates(self):
        q = np.zeros(7)
        q[6] = self.eta0
        return q

    def kinematics(self, q, dq, ddq):
        q, dq, ddq = (np.asarray(value) for value in (q, dq, ddq))
        if any(value.shape != (7,) for value in (q, dq, ddq)):
            raise ValueError('q, dq and ddq must each have seven entries')
        R = rotation(q[3:6])
        J = left_jacobian(q[3:6])
        Q = R@rotation(q[6]*self.k)
        omega = J@dq[3:6]
        alpha = J@ddq[3:6] + left_jacobian_rate(q[3:6], dq[3:6])@dq[3:6]
        axis = R@self.k
        origin = q[:3]
        hinge_offset = R@self.H
        hinge = origin+hinge_offset
        omega_fin = omega+dq[6]*axis
        alpha_fin = alpha+ddq[6]*axis+dq[6]*np.cross(omega, axis)
        hinge_velocity = dq[:3]+np.cross(omega, hinge_offset)
        hinge_acceleration = (ddq[:3]+np.cross(alpha, hinge_offset)
                              + np.cross(omega, np.cross(omega, hinge_offset)))
        return dict(q=q, dq=dq, ddq=ddq, R=R, Q=Q, J=J,
                    origin=origin, hinge=hinge, hinge_offset=hinge_offset,
                    hinge_axis=axis, omega_carrier=omega, alpha_carrier=alpha,
                    omega_fin=omega_fin, alpha_fin=alpha_fin,
                    hinge_velocity=hinge_velocity,
                    hinge_acceleration=hinge_acceleration)

    @staticmethod
    def point_velocity(points, kinematics):
        """Physical material velocity in the frame translating at -U e_x.

        At a virtual CP/Hv this is the rigid material velocity field sampled
        at that location, not the derivative of the moving virtual point.
        """
        return (kinematics['hinge_velocity']
                + np.cross(kinematics['omega_fin'],
                           np.asarray(points)-kinematics['hinge']))

    @staticmethod
    def point_acceleration(points, kinematics):
        d = np.asarray(points)-kinematics['hinge']
        omega = kinematics['omega_fin']
        return (kinematics['hinge_acceleration']
                + np.cross(kinematics['alpha_fin'], d)
                + np.cross(omega, np.cross(omega, d)))

    def geometry(self, q, dq, ddq):
        kin = self.kinematics(q, dq, ddq)
        c, span = kin['Q'][:, 0], kin['Q'][:, 2]
        normal = np.cross(c, span)
        # Carrier translation is included once: the wake follows relative
        # flow at O, while absolute material velocities are subtracted below.
        free = np.array([self.speed, 0., 0.])-kin['dq'][:3]
        freestream_speed = norm(free)
        if freestream_speed.real <= 0:
            raise ValueError('Nonpositive origin-relative air speed')
        wind = free/freestream_speed
        across = norm(np.cross(wind, span))
        if across.real < 1e-6:
            raise ValueError('Fin aligns with influence wind')
        quarter_virtual = (.25-self.xax)*self.chord/across*wind
        # Build relative coordinates directly, avoiding subtraction of a
        # potentially large absolute translation in the invariant field cache.
        endpoints = kin['hinge_offset']+self.t[:, None]*span
        rm = kin['hinge_offset']+self.tm[:, None]*span
        rel = dict(r0=endpoints[:-1], r1=endpoints[1:], rm=rm,
                   a=endpoints[:-1]+quarter_virtual,
                   b=endpoints[1:]+quarter_virtual, hv=rm+quarter_virtual,
                   cp=rm+quarter_virtual+self.slope/(4*np.pi)*self.chord/across*wind,
                   axis=rm.copy())
        g = {key: value+kin['origin'] for key, value in rel.items()}
        g.update(kinematics=kin, relative=rel, c=c, s=span, normal=normal,
                 wind=wind, free=free, freestream_speed=freestream_speed,
                 across=across, ds=self.ds, t=self.t, tm=self.tm)
        return g

    def _integrate_field(self, g, receiver):
        """Independent theta-quadrature of oriented finite/semi-infinite lines.

        With z=(target-origin).u, d=relative-z*u, q²=d.d, the line integral
        is cross(u,d)/(4pi q²) * integral cos(theta) dtheta, where
        theta=atan((line_coordinate-z)/q).  No production closed formula is used.
        Same-fin cores are zero.  Hv is collinear with all bound segments:
        its own segment is excluded and other disjoint segments contribute
        exactly zero.  Axis excludes only the diagonal bound segment.
        """
        self.fields += 1
        targets = g['relative'][receiver]
        a, b, span, wind = g['relative']['a'], g['relative']['b'], g['s'], g['wind']
        result = np.zeros((self.n, self.n, 3), dtype=np.result_type(targets, span, wind))
        own, collinear = 0, 0
        for j in range(self.n):
            segments = [('wake', b[j], wind, None, 1.),
                        ('wake', a[j], wind, None, -1.),
                        ('bound', a[j], span, self.ds[j], 1.)]
            for kind, origin, direction, length, sign in segments:
                active = np.ones(self.n, dtype=bool)
                if kind == 'bound' and receiver in ('hv', 'axis'):
                    active[j] = False
                    own += 1
                if kind == 'bound' and receiver == 'hv':
                    other = np.arange(self.n) != j
                    if not np.all((self.tm[other] < self.t[j]) |
                                  (self.tm[other] > self.t[j+1])):
                        raise ValueError('A different bound interval contains an Hv receiver')
                    active[other] = False
                    collinear += int(np.sum(other))
                ids = np.flatnonzero(active)
                if not len(ids):
                    continue
                relative = targets[ids]-origin
                z = relative@direction
                radial = relative-z[:, None]*direction
                q2 = np.sum(radial*radial, axis=1)
                if np.any(q2.real <= 0):
                    raise ValueError('Undeclared singular reference filament')
                radius = np.sqrt(q2)
                lo = np.arctan(-z/radius)
                hi = (np.full(len(ids), np.pi/2) if length is None
                      else np.arctan((length-z)/radius))
                half = (hi-lo)/2
                theta = (hi+lo)[:, None]/2+half[:, None]*self.nodes
                integral = np.sum(np.cos(theta)*self.weights, axis=1)*half/q2
                result[ids, j] += sign*np.cross(direction, radial)*integral[:, None]/(4*np.pi)
        return result, dict(own_bound_excluded=own,
                            collinear_disjoint_bound_zero=collinear,
                            same_surface_core=0.)

    def field_matrices(self, g):
        # Canonical complex128 key makes real and complex-step calls with
        # identical coordinates share a cache entry.  Store unnormalized free
        # flow as well: an axial speed probe is deliberately its own entry even
        # when its normalized wake is identical.  This makes the proposed
        # derivative-field budget exact, without fuzzy or magnitude-only reuse.
        state = np.r_[g['kinematics']['q'][3:], g['free']]
        key = np.asarray(state, dtype=np.complex128).tobytes()
        if key not in self.cache:
            self.field_sets += 1
            fields, diagnostics = {}, {}
            for receiver in ('cp', 'hv', 'axis'):
                fields[receiver], diagnostics[receiver] = self._integrate_field(g, receiver)
            self.cache[key] = (fields, diagnostics)
            if self.field_recorder is not None:
                self.field_recorder(key.hex(), g, fields, diagnostics)
        return self.cache[key]

    def base_system(self, q=None, controlrad=0.):
        """Return the steady, finite-incidence linear circulation system.

        No root/solve is performed.  No engine/stall/leakage is in this fixture;
        hence at Gamma_dot=0 the exact tangency equation is W Gamma = rhs.
        """
        q = self.base_coordinates() if q is None else np.asarray(q)
        g = self.geometry(q, np.zeros(7), np.zeros(7))
        fields, diagnostics = self.field_matrices(g)
        alpha = self.alpha0+controlrad*self.control_slope
        nc = np.sin(alpha)*g['c']+np.cos(alpha)*g['normal']
        W = np.einsum('ijk,k->ij', fields['cp'], nc)
        rhs = -np.full(self.n, self.speed*nc[0], dtype=np.result_type(nc, float))
        return dict(W=W, rhs=rhs, geometry=g, fields=fields,
                    field_diagnostics=diagnostics, control_normal=nc)

    def evaluate(self, q, dq, ddq, gamma, gammadot=None, controlrad=0., lag=True):
        """Return circulation residual and aerodynamic loads, with no solve.

        `wrenches`: [total, rate, apparent, remainder] x [carrier, fin, net]
        x [Fx,Fy,Fz,Mx,My,Mz], moments about carrier O in Earth axes.
        The carrier has no aerodynamic geometry. `generalizedloads` is
        [Fnet, J_left(phi).T M_O, k_E.M_H]; apparent mass is included here
        exactly once and must not be separately re-added to real mechanics.
        """
        self.evaluations += 1
        gamma = np.asarray(gamma)
        gammadot = np.zeros_like(gamma) if gammadot is None else np.asarray(gammadot)
        if gamma.shape != (self.n,) or gammadot.shape != (self.n,):
            raise ValueError('Circulation arrays must have one entry per panel')
        g = self.geometry(q, dq, ddq)
        kin = g['kinematics']
        fields, diagnostics = self.field_matrices(g)
        alpha = self.alpha0+controlrad*self.control_slope
        nc = np.sin(alpha)*g['c']+np.cos(alpha)*g['normal']
        atmosphere = np.array([self.speed, 0., 0.])
        velocities = {key: atmosphere+np.einsum('ijk,j->ik', fields[key], gamma)
                      - self.point_velocity(g[key], kin) for key in ('cp', 'hv', 'axis')}
        v, vc, va = velocities['hv'], velocities['cp'], velocities['axis']
        span, normal, chord_direction = g['s'], g['normal'], g['c']
        vp = v-(v@span)[:, None]*span
        S, V = norm(vp), norm(v)
        if np.any(S.real <= g['freestream_speed'].real*1e-12):
            raise ValueError('Section speed reaches the undeclared production floor')
        if np.any((S/self.sound).real >= 1):
            raise ValueError('Section normal Mach reaches unity')
        gd = gammadot if lag else np.zeros_like(gammadot)
        tangency = vc@nc-2/np.pi*gd/S
        factor = self.rho*self.ds[:, None]
        lift = factor*gamma[:, None]*np.cross(v, span)
        rate = factor*(self.chord*gd/S)[:, None]*np.cross(v, span)
        profile = .5*factor*self.chord*(self.fin['Cdf']*V[:, None]*v
                                       + self.fin['Cdp']*S[:, None]*vp)
        profile += 2*factor*self.chord*(tangency*tangency/S)[:, None]*vp
        cm = (.5*self.rho*self.ds*self.chord**2*self.fin['Cm']*S*S
              / np.sqrt(1-(S/self.sound)**2))[:, None]*span
        quarter_arm = (.25-self.xax)*self.chord*chord_direction
        half_arm = (.5-self.xax)*self.chord*chord_direction
        half = g['rm']+half_arm
        half_acceleration = self.point_acceleration(half, kin)
        rate_scalar = np.cross(va, kin['omega_fin'])@normal
        ma = self.rho*np.pi/4*self.chord**2*self.ds
        apparent = (ma*(rate_scalar-half_acceleration@normal))[:, None]*normal
        pitch = (-ma*(self.chord/4*rate_scalar
                       + self.chord**2/32*(kin['alpha_fin']@span)))[:, None]*span
        zeros = np.zeros_like(lift)
        strip_terms = {
            'circulatory_lift': dict(force=lift, moment_about_axis=np.cross(quarter_arm, lift)),
            'circulation_rate_lift': dict(force=rate, moment_about_axis=np.cross(quarter_arm, rate)),
            'profile_drag': dict(force=profile, moment_about_axis=zeros),
            'profile_couple': dict(force=zeros, moment_about_axis=cm),
            'apparent_force': dict(force=apparent, moment_about_axis=np.cross(half_arm, apparent)),
            'apparent_pitch_couple': dict(force=zeros, moment_about_axis=pitch)}
        force = lift+rate+profile+apparent
        moment_axis = np.cross(quarter_arm, lift+rate)+cm+np.cross(half_arm, apparent)+pitch
        rate_moment = np.cross(quarter_arm, rate)
        apparent_moment = np.cross(half_arm, apparent)+pitch
        families = [(force, moment_axis), (rate, rate_moment),
                    (apparent, apparent_moment),
                    (force-rate-apparent, moment_axis-rate_moment-apparent_moment)]
        def aggregate(f, m, origin):
            return np.r_[f.sum(axis=0), (np.cross(g['rm']-origin, f)+m).sum(axis=0)]
        earth = np.array([aggregate(f, m, np.zeros(3)) for f, m in families])
        about_O = np.array([aggregate(f, m, kin['origin']) for f, m in families])
        about_H = np.array([aggregate(f, m, kin['hinge']) for f, m in families])
        generalized = np.array([np.r_[o[:3], kin['J'].T@o[3:], kin['hinge_axis']@h[3:]]
                                for o, h in zip(about_O, about_H)])
        wrenches = np.stack([np.zeros_like(about_O), about_O, about_O], axis=1)
        return dict(residual=tangency/g['freestream_speed'], tangency=tangency,
                    generalizedloads=generalized[0], generalized_families=generalized,
                    wrenches=wrenches, fin_wrench_earth=earth,
                    fin_wrench_origin=about_O, fin_wrench_hinge=about_H,
                    strip_force=force, strip_moment_axis=moment_axis,
                    strip_terms=strip_terms, geometry=g, fields=fields,
                    field_diagnostics=diagnostics, control_normal=nc,
                    cp_velocity=vc, velocity=v, axis_velocity=va,
                    normal_speed=S, total_speed=V, half_acceleration=half_acceleration,
                    apparent_rate_scalar=rate_scalar)
