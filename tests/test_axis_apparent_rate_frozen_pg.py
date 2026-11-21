"""Independent apparent-rate load with frozen PG influences across two beams.

The source and targets of the independent line integrals use undeformed jig
geometry and zero influence-wind angles; the force frames and strip lengths use
the prescribed current poses. Only physical own-bound lines are omitted. Source
cores regularize different physical beams and leave same-beam lines unsoftened.
"""
import numpy as np
from scipy.integrate import quad_vec
from scipy.spatial.transform import Rotation

from openswing.asw import parse_asw
from openswing.aero import FlightCondition, evaluate_aerodynamics
from openswing.network import StaticNetwork
from openswing.local_motion import NetworkMotion


BEAMS = [
    dict(origin=[0., 0., 0.], span=.8, chord=.2, xax=.2505,
         rotation=[.06, .14, -.04], shift=[.08, .03, .12], stretch=1.12),
    dict(origin=[.13, -.12, .26], span=.65, chord=.18, xax=.41,
         rotation=[-.05, -.09, .08], shift=[-.04, .02, -.06], stretch=.91),
]


def _source():
    text = '''Name
Prescribed frozen two-beam PG apparent rate
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
0.277 0.2 0.8
0 0 0
End
Ground
1 1 0
End
'''
    for index, beam in enumerate(BEAMS, 1):
        x, y, z = beam['origin']
        text += f'''Beam {index}
Wing {index}
t x y z chord Xax dCLda CLmax CLmin
1 {x} {y} {z} {beam['chord']} {beam['xax']} 6.283185307179586 100 -100
2 {x} {y+beam['span']} {z} {beam['chord']} {beam['xax']} 6.283185307179586 100 -100
End
'''
    return text


def _line(point, origin, direction, end, core):
    def integrand(t):
        radius = point-origin-t*direction
        return np.cross(direction, radius)/(4*np.pi*(radius@radius+core*core)**1.5)
    return quad_vec(integrand, 0., end, epsabs=2e-12, epsrel=2e-12)[0]


def prescribed_frozen_case():
    speed, density, mach, core_ratio = 24., 1.225, .6, 1.
    alpha, beta = np.deg2rad([9., -4.])
    freestream = speed*np.array([np.cos(alpha)*np.cos(beta), -np.sin(beta),
                                np.sin(alpha)*np.cos(beta)])
    # Frozen influence geometry has zero wind angles even with live alpha/beta.
    pg = np.diag([1/np.sqrt(1-mach*mach), 1., 1.])
    wake = np.array([1., 0., 0.])
    edges = (1-np.cos(np.arange(5)*np.pi/4))/2
    stations = (1-np.cos((np.arange(4)+.5)*np.pi/4))/2
    jig_nodes, nodes, rotations, targets, starts, ends = [], [], [], [], [], []
    frame, length, chord, axis, core, owner = [], [], [], [], [], []
    for index, b in enumerate(BEAMS):
        origin = np.array(b['origin'])
        jig = origin+np.c_[np.zeros(5), b['span']*edges, np.zeros(5)]
        rot = Rotation.from_rotvec(b['rotation']).as_matrix()
        jig_nodes.extend(jig)
        nodes.extend(origin+b['shift']+b['stretch']*(jig-origin)@rot.T)
        rotations.extend(np.broadcast_to(rot, (5, 3, 3)))
        point = origin+np.c_[np.zeros(4), b['span']*stations, np.zeros(4)]
        quarter = jig+np.array([(0.25-b['xax'])*b['chord'], 0., 0.])
        targets.extend(point);starts.extend(quarter[:-1]);ends.extend(quarter[1:])
        frame.extend(np.broadcast_to(rot, (4, 3, 3)))
        ds = b['span']*np.diff(edges)
        length.extend(b['stretch']*ds)
        chord.extend([b['chord']]*4);axis.extend([b['xax']]*4)
        core.extend(np.maximum(core_ratio*b['chord'], ds));owner.extend([index]*4)
    jig_nodes, nodes, rotations = map(np.asarray, [jig_nodes, nodes, rotations])
    targets, starts, ends, frame = map(np.asarray, [targets, starts, ends, frame])
    length, chord, axis, core, owner = map(np.asarray, [length, chord, axis, core, owner])
    gamma = speed*chord*np.array([.11, .19, .16, .09, -.07, -.12, -.10, -.05])
    # Independent Rosenhead line quadrature in PG coordinates, followed by P^T
    # velocity mapping; the transformed wake direction is a unit vector.
    transformed_wake = pg@wake
    transformed_wake /= np.linalg.norm(transformed_wake)
    groups = {key: np.zeros((8, 3)) for key in
              ['same_beam_other_bounds', 'same_beam_wakes', 'other_beam_bounds', 'other_beam_wakes']}
    for i, point in enumerate(targets@pg.T):
        for j, (a, b, strength) in enumerate(zip(starts@pg.T, ends@pg.T, gamma)):
            same = owner[i] == owner[j]
            radius = 0. if same else core[j]
            if i != j:
                key = 'same_beam_other_bounds' if same else 'other_beam_bounds'
                groups[key][i] += strength*_line(point, a, b-a, 1., radius)@pg
            key = 'same_beam_wakes' if same else 'other_beam_wakes'
            groups[key][i] += strength*(_line(point, b, transformed_wake, np.inf, radius)
                                        - _line(point, a, transformed_wake, np.inf, radius))@pg
    velocity = freestream+sum(groups.values())
    c, s, n = frame[:, :, 0], frame[:, :, 1], frame[:, :, 2]
    mass = density*np.pi*chord**2/4*length
    rate = np.sum(np.cross(velocity, s)*n, axis=1)
    force = (mass*rate)[:, None]*n
    moment = (-mass*chord/4*rate)[:, None]*s+np.cross(((.5-axis)*chord)[:, None]*c, force)
    expected = np.c_[force, moment]

    model = parse_asw(_source())
    condition = FlightCondition(speed=speed, alpha=9., beta=-4., density=density,
        mach=mach, stall=False, aero_lag=True, freeze_influences=True,
        wake_core_ratio=core_ratio)
    net = StaticNetwork(model, 4, condition, [0., 0., 0.], [])
    assert net.nn == 10 and net.ng == 8
    np.testing.assert_allclose(net.rj, jig_nodes, rtol=0., atol=1e-14)
    meshes = net.deformed_meshes(nodes, rotations, net.geometry(nodes, rotations))
    span_rates = rotations[:, :, 1]
    zero = np.zeros_like(nodes)
    step = 1e-5
    samples = []
    for sign in [-1, 1]:
        motion = NetworkMotion(net, nodes, rotations, zero, sign*step*span_rates, zero, zero)
        result = evaluate_aerodynamics(model, condition, meshes, circulation=gamma,
            circulation_rate=np.zeros(8), local_motion=motion)
        assert result['aerodynamic_influences']['frozen']
        np.testing.assert_allclose([row['wake_core_radius'] for row in result['strips']],
                                   core, rtol=0., atol=1e-14)
        samples.append(np.array([[*row['apparent_force'], *row['apparent_moment']]
                                 for row in result['strips']]))
    actual = (samples[1]-samples[0])/(2*step)
    error = float(np.max(abs(actual-expected))/max(1., np.max(abs(expected))))
    return dict(source=_source(),condition=dict(speed=speed,density=density,mach=mach,
        alpha=9.,beta=-4.,freeze_influences=True,wake_core_ratio=core_ratio),
        gamma=gamma.tolist(),actual=actual.tolist(),independent=expected.tolist(),
        axis_velocity=velocity.tolist(),velocity_parts={k:v.tolist() for k,v in groups.items()},
        current_lengths=length.tolist(),jig_source_core=core.tolist(),maximum_scaled_error=error)


def test_apparent_rate_frozen_pg_multiple_beams_matches_independent_lines():
    assert prescribed_frozen_case()['maximum_scaled_error'] < 1e-9
