"""Independent prescribed-circulation apparent-rate continuity regression.

No equilibrium or eigenvalue solve. The source axis approaches quarter-chord
smoothly at fixed finite incidence, twist, geometry and nonzero circulation.
The reference integrates vortex lines independently and excludes only the
physical target's own bound segment, retaining its wakes and every image line.
"""
import numpy as np
import pytest
from scipy.integrate import quad_vec

from openswing.asw import parse_asw
from openswing.aero import FlightCondition, evaluate_aerodynamics
from openswing.network import StaticNetwork
from openswing.local_motion import NetworkMotion


def _line_velocity(point, origin, direction, end):
    def integrand(t):
        radius = point-origin-t*direction
        return np.cross(direction, radius)/(4*np.pi*np.linalg.norm(radius)**3)
    return quad_vec(integrand, 0., end, epsabs=2e-12, epsrel=2e-12)[0]


def _axis_induced_velocity(points, ends, wind, gamma, height, ground):
    velocity = np.zeros_like(points)
    for i, point in enumerate(points):
        for j, (a, b, strength) in enumerate(zip(ends[:-1], ends[1:], gamma)):
            if i != j:
                velocity[i] += strength*_line_velocity(point, a, b-a, 1.)
            velocity[i] += strength*(_line_velocity(point, b, wind, np.inf)
                                     - _line_velocity(point, a, wind, np.inf))
            if ground:
                ai, bi, wi = a.copy(), b.copy(), wind.copy()
                ai[2], bi[2], wi[2] = -ai[2]-2*height, -bi[2]-2*height, -wi[2]
                velocity[i] -= strength*(
                    _line_velocity(point, ai, bi-ai, 1.)
                    + _line_velocity(point, bi, wi, np.inf)
                    - _line_velocity(point, ai, wi, np.inf))
    return velocity


def _source(xax):
    return f'''Name
Prescribed apparent-rate continuity
End
Units
L 1 m
T 1 s
M 1 kg
End
Constant
9.80665 1.225 340.29
End
Reference
0.2 0.2 1
0 0 0
End
Ground
1 1 0
End
Beam 1
Wing
t y chord Xax dCLda CLmax CLmin
1 0 0.2 {xax:.17g} 6.283185307179586 100 -100
2 1 0.2 {xax:.17g} 6.283185307179586 100 -100
End
'''


@pytest.fixture(scope='module', params=[False, True], ids=['no-ground', 'solid-ground'])
def prescribed_axis_cases(request):
    ground = request.param
    chord, speed, density, twist, alpha, height = .2, 24., 1.225, .12, .07, .4
    edges = (1-np.cos(np.arange(5)*np.pi/4))/2
    stations = (1-np.cos((np.arange(4)+.5)*np.pi/4))/2
    nodes = np.c_[np.zeros(5), edges, np.zeros(5)]
    points = np.c_[np.zeros(4), stations, np.zeros(4)]
    c = np.array([np.cos(twist), 0., -np.sin(twist)])
    s = np.array([0., 1., 0.])
    n = np.cross(c, s)
    rotation = np.broadcast_to(np.stack([c, s, n], axis=1), (5, 3, 3)).copy()
    wind = np.array([np.cos(alpha), 0., np.sin(alpha)])
    gamma = speed*chord*np.array([.11, .19, .16, .09])
    zero = np.zeros((5, 3))
    rate_step = 1e-5
    cases = {}
    for delta in [-1e-5, -1e-6, 0., 1e-6, 1e-5]:
        xax = .25+delta
        model = parse_asw(_source(xax))
        condition = FlightCondition(speed=speed, alpha=np.rad2deg(alpha), beta=0,
            density=density, mach=0, stall=False, aero_lag=True,
            ground_effect=int(ground), position_earth=(0., 0., height))
        net = StaticNetwork(model, 4, condition, [0., 0., 0.], [])
        assert net.nn == 5 and net.ng == 4
        meshes = net.deformed_meshes(nodes, rotation, net.geometry(nodes, rotation))
        samples = []
        for sign in [-1, 1]:
            motion = NetworkMotion(net, nodes, rotation, zero,
                np.broadcast_to(sign*rate_step*s, (5, 3)), zero, zero)
            result = evaluate_aerodynamics(model, condition, meshes,
                circulation=gamma, circulation_rate=np.zeros(4), local_motion=motion)
            samples.append(np.array([[*row['apparent_force'], *row['apparent_moment']]
                                     for row in result['strips']]))
        actual = (samples[1]-samples[0])/(2*rate_step)
        # Explicit independent geometry: cosine nodes, material Glauert stations,
        # and wind-aligned horseshoes. No production frames/influences are read.
        ends = nodes+((.25-xax)*chord)*wind
        velocity = speed*wind+_axis_induced_velocity(points, ends, wind, gamma, height, ground)
        mass = density*np.pi*chord**2/4*np.diff(edges)
        rate = np.cross(velocity, s)@n
        force = (mass*rate)[:, None]*n
        moment = (-mass*chord/4*rate)[:, None]*s+np.cross((.5-xax)*chord*c, force)
        cases[delta] = actual, np.c_[force, moment]
    return cases


def test_apparent_rate_matches_independent_vortex_line_quadrature(prescribed_axis_cases):
    for actual, expected in prescribed_axis_cases.values():
        scaled_error = np.max(abs(actual-expected))/max(1., np.max(abs(expected)))
        assert scaled_error < 1e-9


def test_apparent_rate_is_continuous_across_quarter_chord_axis(prescribed_axis_cases):
    actual = {delta: pair[0] for delta, pair in prescribed_axis_cases.items()}
    near = max(np.max(abs(actual[delta]-actual[0.])) for delta in [-1e-6, 1e-6])
    far = max(np.max(abs(actual[delta]-actual[0.])) for delta in [-1e-5, 1e-5])
    assert near/far < .11
