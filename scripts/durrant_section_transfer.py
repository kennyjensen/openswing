"""Independent scalar/vector section transfer and explicit native evaluator adapter.

This checks ASWING empirical lag and apparent-mass force/moment components,
not exact Theodorsen aerodynamics. No equilibrium, beam tangent, eigensolution
or time integration is called. Production imports require an explicit kernel
root and occur only when a Production object is constructed.
"""
import numpy as np

CHORD, SPEED, DENSITY = .09446, 25., 1.225
PARTS = ['circulatory_steady', 'circulation_rate', 'apparent_acceleration', 'apparent_pitch_rate', 'total']


def coefficients(x, r, lag=True):
    """[CL, CM] = Q [h/c, theta], exp(+i*omega*t), M about pitch axis.

    h is positive n, theta positive s, c cross s = n. x is the pitch-axis
    coordinate divided by chord, measured aft from LE. CL uses q*c; CM q*c^2.
    The load components are retained so cancellations cannot hide a bad term.
    """
    a, d, e = .25-x, .5-x, .75-x
    input_velocity = np.array([-1j*r, 1+1j*r*e])
    gamma = 2*np.pi*input_velocity/(1+2j*r if lag else 1)
    lift_steady = np.outer([1., -a], gamma)
    lift_rate = 1j*r*lift_steady if lag else np.zeros((2,2), complex)
    added_acceleration = np.pi/2*r*r*np.array([[1., -d], [-d, d*d+1/32]])
    added_pitch_rate = np.pi/2*1j*r*np.array([[0., 1.], [0., -(d+.25)]])
    parts = dict(circulatory_steady=lift_steady, circulation_rate=lift_rate,
                 apparent_acceleration=added_acceleration,
                 apparent_pitch_rate=added_pitch_rate)
    parts['total'] = sum(parts.values())
    return parts


def vector_wrenches(x, r, lag=True, *, chord=.09446, speed=25., density=1.225):
    """Separate direct vector transcription, evaluated for both unit inputs."""
    c, s, n = np.array([1.,0.,0.]), np.array([0.,0.,1.]), np.array([0.,-1.,0.])
    omega = r*speed/chord
    ma = density*np.pi*chord**2/4
    names = ['circulatory_steady', 'circulation_rate', 'apparent_acceleration', 'apparent_pitch_rate']
    out = {name: np.zeros((2,2), complex) for name in names}
    pressure = .5*density*speed**2
    for j, (h, theta) in enumerate([(chord, 0.), (0., 1.)]):
        velocity = 1j*omega*h*n
        rotation_rate = 1j*omega*theta*s
        acceleration = -omega**2*h*n
        rotation_acceleration = -omega**2*theta*s
        rcp = (.75-x)*chord*c
        rq = (.25-x)*chord*c
        rm = (.5-x)*chord*c
        normal_flow = speed*theta-(velocity+np.cross(rotation_rate, rcp))@n
        gamma = normal_flow/(1/(np.pi*chord)+(2j*omega/(np.pi*speed) if lag else 0))
        force_steady = density*gamma*np.cross(speed*c,s)
        force_rate = density*chord/speed*1j*omega*gamma*np.cross(speed*c,s) if lag else np.zeros(3)
        force_acceleration = -ma*((acceleration+np.cross(rotation_acceleration,rm))@n)*n
        force_pitch_rate = ma*np.cross(speed*c,rotation_rate)@n*n
        wrenches = dict(
            circulatory_steady=(force_steady,np.cross(rq,force_steady)),
            circulation_rate=(force_rate,np.cross(rq,force_rate)),
            apparent_acceleration=(force_acceleration,
                -ma*chord**2/32*(rotation_acceleration@s)*s+np.cross(rm,force_acceleration)),
            apparent_pitch_rate=(force_pitch_rate,
                -ma*chord/4*(np.cross(speed*c,rotation_rate)@n)*s+np.cross(rm,force_pitch_rate)))
        for name,(force,moment) in wrenches.items():
            out[name][:,j] = [(force@n)/(pressure*chord), (moment@s)/(pressure*chord**2)]
    out['total'] = sum(out.values())
    return out


def pack(matrix):
    a = np.asarray(matrix)
    return dict(real=a.real.tolist(),imag=a.imag.tolist())



def independent_checks():
    xs = [-.2, .25, .2505, .3844, .5, .75, 1.2]
    rs = [0., .001, .1, .25, .5, 1., 2., 10., 1e3]
    discrepancies = []
    for lag in (False, True):
        for x in xs:
            for r in rs:
                scalar, vector = coefficients(x,r,lag), vector_wrenches(x,r,lag)
                for key in scalar:
                    discrepancies.append(np.max(abs(scalar[key]-vector[key]))/max(1.,np.max(abs(scalar[key]))))
    assert max(discrepancies) < 5e-14
    covariance = []
    for lag in (False,True):
        for r in rs:
            for x in xs:
                delta = .271
                transform = np.array([[1.,delta],[0.,1.]])
                original, shifted = coefficients(x,r,lag), coefficients(x+delta,r,lag)
                for key in original:
                    expected = transform.T@original[key]@transform
                    covariance.append(np.max(abs(shifted[key]-expected))/max(1.,np.max(abs(expected))))
    assert max(covariance) < 5e-14
    # The still-air mass matrix follows the positive kinetic energy of
    # midchord normal motion and intrinsic flat-plate rotational inertia.
    inertia_errors = []
    for x in xs:
        d = .5-x
        transform = np.array([[1.,-d],[0.,1.]])
        energy = np.pi/2*transform.T@np.diag([1.,1/32])@transform
        actual = coefficients(x,1.)['apparent_acceleration'].real
        inertia_errors.append(float(np.max(abs(energy-actual))))
        assert np.linalg.eigvalsh(actual).min() > 0
    assert max(inertia_errors) < 5e-15
    # Discriminating exact identities at familiar chordwise axes.
    for r in rs:
        quarter, middle, aft = [coefficients(x,r) for x in (.25,.5,.75)]
        assert np.max(abs(quarter['circulatory_steady'][1])) == 0
        assert np.max(abs(quarter['circulation_rate'][1])) == 0
        assert middle['apparent_acceleration'][1,0] == 0
        assert aft['apparent_pitch_rate'][1,1] == 0
        assert abs(quarter['total'][1,0]+np.pi*r*r/8) < 5e-13*max(1,r*r)
        assert abs(quarter['total'][1,1]-(3*np.pi*r*r/64-1j*np.pi*r/4)) < 5e-13*max(1,r*r)
    # High-frequency asymptote of the implied circulatory factor and of total
    # inertial terms. The exact-Theodorsen function is deliberately not used.
    high_r = 1e7
    high_frequency = []
    for x in xs:
        result = coefficients(x, high_r)
        mass = coefficients(x, 1.)['apparent_acceleration']
        error = np.max(abs(result['total']/high_r**2-mass))/max(1,np.max(abs(mass)))
        high_frequency.append(float(error))
    assert max(high_frequency) < 2e-6
    # Representative Durrant geometric axes. Each column remains separately
    # measurable; a heave-only comparison cannot check the pitch-rate column.
    samples = []
    for x in (.2505,.3844):
        for r in (.25,.5,1.):
            parts = coefficients(x,r)
            samples.append(dict(Xax=x,reduced_frequency_k=r/2,r=r,
                                parts={k:pack(v) for k,v in parts.items()}))
    return dict(scalar_vector_max_scaled_difference=float(max(discrepancies)),
        axis_covariance_max_scaled_difference=float(max(covariance)),
        added_mass_energy_max_difference=max(inertia_errors),
        high_frequency_added_mass_max_scaled_difference=max(high_frequency),
        evaluated_axis_frequency_lag_combinations=len(xs)*len(rs)*2, samples=samples)


def source(x, aspect):
    span = aspect*CHORD
    return f'''! Original prescribed-motion transfer verification wing.
Name
Independent finite-speed section comparison
End
Unit
L 1 m
T 1 s
F 1 N
End
Constant
9.80665 {DENSITY} 340.294
End
Reference
{span*CHORD:.17g} {CHORD} {span:.17g}
0 0 0
End
Ground
1 1 0
End
Beam 1
Straight unsymmetrized test surface
t y chord Xax Cdf Cdp dCLda CLmax CLmin
1 0 {CHORD} {x} 0 0 {2*np.pi:.17g} 100 -100
2 {span:.17g} {CHORD} {x} 0 0 {2*np.pi:.17g} 100 -100
End
'''


def independent_finite_transfer(x, r, lag, aspect, panels):
    """Closed Biot-Savart horseshoes, explicit cosine-node/Glauert-point grid.

    Coordinates below are divided by chord. This does not read production
    meshes, influence matrices, residuals, geometric frames or circulation.
    """
    angles = np.linspace(0, np.pi, panels+1)
    edges = aspect*(1-np.cos(angles))/2
    points = aspect*(1-np.cos((angles[:-1]+angles[1:])/2))/2
    da, db = points[:, None]-edges[:-1], points[:, None]-edges[1:]
    ra, rb = np.sqrt(.25+da*da), np.sqrt(.25+db*db)
    influence = -(da/ra-db/rb)/(2*np.pi) + ((1+.5/rb)/db-(1+.5/ra)/da)/(4*np.pi)
    control = np.array([-1j*r, 1+1j*r*(.75-x)])
    lag_matrix = (2j*r/np.pi if lag else 0)*np.eye(panels)
    gamma = np.linalg.solve(-influence+lag_matrix, np.ones((panels, 1))*control)
    mean_gamma = np.diff(edges)@gamma/aspect
    circ = 2*np.outer([1., x-.25], mean_gamma)
    result = coefficients(x, r, lag)
    result['circulatory_steady'] = circ
    result['circulation_rate'] = 1j*r*circ if lag else np.zeros((2, 2), complex)
    result['total'] = sum(result[k] for k in PARTS[:-1])
    return result, gamma, influence


class Production:
    def __init__(self, kernel_root, x, lag, aspect, panels):
        from durrant_unloaded_native import load_kernel
        root, modules = load_kernel(kernel_root)
        from openswing.network import StaticNetwork
        from openswing.local_motion import NetworkMotion, rotation_matrix
        self.evaluate_aerodynamics = modules['aero'].evaluate_aerodynamics
        self.NetworkMotion = NetworkMotion
        self.rotation_matrix = rotation_matrix
        parse_asw = modules['asw'].parse_asw
        FlightCondition = modules['aero'].FlightCondition
        self.source = source(x, aspect)
        self.model = parse_asw(self.source)
        assert not self.model.diagnostics, self.model.diagnostics
        self.condition = FlightCondition(speed=SPEED, alpha=0, beta=0, mach=0, stall=False, aero_lag=lag)
        self.net = StaticNetwork(self.model, panels, self.condition, [0, 0, 0], [])
        self.ng = self.net.ng
        assert self.ng == panels
        self.span = aspect*CHORD
        self.scale = .5*DENSITY*SPEED**2*self.span*np.array([CHORD, CHORD**2])
        self.calls = 0

    def evaluate(self, values):
        # Coordinates: eta=h/c, theta, their first and second derivatives in
        # tau=t*U/c; circulation is Gamma/(U*c), its rate is Gamma_dot/U^2.
        eta, theta, etad, thetad, etadd, thetadd = values[:6]
        n = self.net
        r = n.rj+np.array([0., 0., CHORD*eta])
        q = np.broadcast_to(self.rotation_matrix(np.array([0., theta, 0.])), (n.nn, 3, 3)).copy()
        vectors = [np.array([0., 0., SPEED*etad]), np.array([0., SPEED/CHORD*thetad, 0.]),
                   np.array([0., 0., SPEED**2/CHORD*etadd]), np.array([0., SPEED**2/CHORD**2*thetadd, 0.])]
        field = self.NetworkMotion(n, r, q, *(np.broadcast_to(v, (n.nn, 3)).copy() for v in vectors))
        meshes = n.deformed_meshes(r, q, n.geometry(r, q))
        out = self.evaluate_aerodynamics(self.model, self.condition, meshes, local_motion=field,
            circulation=values[6:6+self.ng]*SPEED*CHORD,
            circulation_rate=values[6+self.ng:]*SPEED**2)
        self.calls += 1
        total = np.array([out['force'][2], out['moment'][1]])/self.scale
        rate = np.array([out['circulation_rate_force'][2], out['circulation_rate_moment'][1]])/self.scale
        apparent = np.array([out['apparent_force'][2], out['apparent_moment'][1]])/self.scale
        # Zero profile/camber/Cm; central differentiation about the unloaded
        # base removes the quadratic residual-pressure contribution.
        return np.r_[out['circulation_residual'], total-apparent-rate, rate, apparent]

    def tangent(self, step):
        size = 6+2*self.ng
        zero = self.evaluate(np.zeros(size))
        assert np.max(abs(zero)) < 1e-12
        columns = []
        for j in range(size):
            direction = np.zeros(size)
            direction[j] = step
            columns.append((self.evaluate(direction)-self.evaluate(-direction))/(2*step))
        return np.asarray(columns).T

    def harmonic(self, tangent, r):
        ng = self.ng
        prescribed = np.vstack([np.eye(2), 1j*r*np.eye(2), -r*r*np.eye(2)])
        residual = tangent[:ng]
        pencil = residual[:, 6:6+ng]+1j*r*residual[:, 6+ng:]
        gamma = np.linalg.solve(pencil, -residual[:, :6]@prescribed)
        state = np.vstack([prescribed, gamma, 1j*r*gamma])
        loads = tangent[ng:]
        result = dict(circulatory_steady=loads[:2]@state, circulation_rate=loads[2:4]@state,
                      apparent_acceleration=loads[4:6, 4:6]@prescribed[4:6],
                      apparent_pitch_rate=loads[4:6, :4]@prescribed[:4])
        result['total'] = sum(result.values())
        residual_error = float(np.max(abs(residual@state)))
        return result, gamma, residual_error


def discrepancy(actual, expected):
    # Shared matrix scale avoids meaningless relative errors on exact zeros.
    return float(np.max(abs(actual-expected))/max(1., float(np.max(abs(expected)))))


def compute(kernel_root, spec):
    """One bounded prescribed-motion case, suitable for native or Pyodide.

    x is axis/chord measured aft from the leading edge; aspect is span/chord;
    r=omega*chord/U. Chord=.09446m, speed=25m/s and density=1.225kg/m3 are
    fixed verification scales. Inputs do not enable stall, camber or prestress.
    """
    if set(spec)-{'x','lag','aspect','panels','steps','frequencies'}:
        raise ValueError('Unknown section verification fields.')
    values={**dict(panels=4,steps=[1e-4,1e-5],frequencies=[0.,.25,.5,1.,2.]),**spec}
    x,lag,aspect=values['x'],values['lag'],values['aspect']
    if type(lag) is not bool or type(values['panels']) is not int or not 2<=values['panels']<=32:
        raise ValueError('Section lag must be boolean and panel count must be2–32.')
    if type(x) not in (int,float) or not np.isfinite(x) or not -1<=x<=2:
        raise ValueError('Section axis/chord must be finite and between−1 and2.')
    if type(aspect) not in (int,float) or not np.isfinite(aspect) or not .1<=aspect<=1e6:
        raise ValueError('Aspect ratio must be finite and between.1 and1e6.')
    steps,frequencies=values['steps'],values['frequencies']
    if not isinstance(steps,list) or len(steps)!=2 or any(type(s) not in (int,float) or not np.isfinite(s) or not 0<s<=.01 for s in steps):
        raise ValueError('Provide two finite centered tangent steps in(0,.01].')
    if not isinstance(frequencies,list) or not 1<=len(frequencies)<=16 or any(type(r) not in (int,float) or not np.isfinite(r) or not 0<=r<=1e4 for r in frequencies):
        raise ValueError('Provide1–16 finite dimensionless frequencies in[0,1e4].')
    production=Production(kernel_root,x,lag,aspect,values['panels'])
    tangents=[production.tangent(step) for step in steps]
    case=dict(x=x,lag=lag,aspect_ratio=aspect,panels=values['panels'],tangent_steps=steps,
        source=production.source,evaluator_calls=production.calls,samples=[])
    for r in frequencies:
        actual,gamma,residual=production.harmonic(tangents[-1],r)
        previous,_,_=production.harmonic(tangents[0],r)
        expected,reference_gamma,_=independent_finite_transfer(x,r,lag,aspect,values['panels'])
        infinite=coefficients(x,r,lag)
        case['samples'].append(dict(r=r,reduced_frequency_k=r/2,
            production={key:pack(value) for key,value in actual.items()},
            independent_finite={key:pack(value) for key,value in expected.items()},
            independent_infinite={key:pack(value) for key,value in infinite.items()},
            finite_comparison={key:discrepancy(actual[key],expected[key]) for key in PARTS},
            infinite_comparison={key:discrepancy(actual[key],infinite[key]) for key in PARTS},
            tangent_step_change={key:discrepancy(actual[key],previous[key]) for key in PARTS},
            circulation_max_scaled_difference=discrepancy(gamma,reference_gamma),
            normalized_harmonic_residual=residual))
    return case

