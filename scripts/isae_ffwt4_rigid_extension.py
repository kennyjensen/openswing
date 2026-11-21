"""Bounded physical tests of explicit rigid-extension condensation.

Synthetic models only: an actual massless rigid auxiliary beam is eliminated
and compared with an endpoint pylon. This does not interpret or rewrite any
original ISAE attachment, or change the production attachment policy.
"""
from dataclasses import dataclass
import numpy as np

from openswing.asw import parse_asw
from openswing.inertia import Motion
from openswing.source_dynamics import SourceMovingNetwork
from openswing.source_recovery import recover_source_structure
from openswing.structured_static import jacobian

GRAVITY = np.array([.3, -.5, -9.])
REFERENCE = np.array([.2, -.1, .3])
MASS = .7
INERTIA = np.array([[.2, -.01, .02], [-.01, .3, -.03], [.02, -.03, .4]])
SPIN = np.array([.06, -.04, .02])
LOCAL = tuple(np.array(v) for v in ([.31, -.19, .27], [.17, .23, -.11],
                                   [-.13, .29, .07], [.09, -.21, .16]))


def rotation(vector):
    vector = np.asarray(vector)
    theta = np.linalg.norm(vector)
    if theta == 0:
        return np.eye(3)
    x, y, z = vector/theta
    k = np.array([[0., -z, y], [z, 0., -x], [-y, x, 0.]])
    return np.eye(3)+np.sin(theta)*k+(1-np.cos(theta))*(k@k)


@dataclass
class Fixture:
    network: object
    upper: bool
    extended: bool
    point: np.ndarray
    physical_nodes: np.ndarray
    physical_elements: np.ndarray


def fixture(*, extended, upper=False, panels=4, moving=True, anchor=None, flexible_extension=False):
    endpoint, outer, ground = (2., 2.2, 1.) if upper else (1., .8, 2.)
    point = np.array([outer-1+.11, .17, -.09])
    attachment_beam = 2 if extended else 1
    attachment = outer if extended else endpoint if anchor is None else anchor
    source = ('Name\nExplicit rigid extension comparison\nEnd\n'
              'Unit\nL 1 m\nT 1 s\nF 1 N\nEnd\nConstant\n10 1.2 340\nEnd\n'
              'Reference\n1 .2 1\n0 0 0\n.2 -.1 .3\nEnd\n'
              f'Ground\n1 {ground} 0\nEnd\n'
              f'Weight\n{attachment_beam} {attachment} {point[0]:.17g} .17 -.09 '
              '7 0 0 .6 -.4 .2 2 3 4 .1 -.2 .3\nEnd\n'
              'Beam 1\nRetained rigid beam\nt x y z\n1 0 0 0\n2 1 0 0\nEnd\n')
    grids = {'1': {'nodes': np.linspace(1., 2., panels+1).tolist()}}
    if extended:
        a, b = sorted((endpoint, outer))
        source += (f'Joint\n1 2 {endpoint} {endpoint} 0\nEnd\n'
                   f'Beam 2\nExplicit massless rigid extension\nt x y z\n{a} {a-1:.17g} 0 0\n{b} {b-1:.17g} 0 0\n')
        if flexible_extension:
            source += f't EIcc\n{a} 100\n{b} 100\n'
        source += 'End\n'
        grids['2'] = {'nodes': np.linspace(a, b, 5).tolist()}
    model = parse_asw(source, beam_interpolation='drela-segspl-v1')
    frame = (Motion([.41, -.28, .33], [.32, -.19, .27], [-.17, .23, .12])
             if moving else Motion())
    net = SourceMovingNetwork(model, {'default': panels, 'beams': grids}, None, GRAVITY, [], motion=frame)
    sl = net.beam_elements[1]
    return Fixture(net, upper, extended, point, net.station_nodes[1][1], np.arange(sl.start, sl.stop))


def certify_extension(f):
    n = f.network
    if not f.extended:
        return
    sl = n.beam_elements[2]
    if np.any(n.source_material_compliance[sl]) or np.any(n.source_weights[sl]):
        raise ValueError('Extension is not exactly rigid and massless')
    beam = n.meshes[1].beam
    if beam.lifting or any(np.any(beam.value(k, [*beam.domain])) for k in
                           ('radius', 'mg', 'mgcc', 'mgnn', 'Dmg', 'Dmgcc', 'Dmgnn')):
        raise ValueError('Extension has physical section loads')


def state(f, tilted=False, local=False):
    n = f.network
    q = np.array([.23, -.17, .12]) if tilted else np.zeros(3)
    R = rotation(q)
    shift = np.array([.07, -.04, .09]) if tilted else np.zeros(3)
    r = n.rj@R.T+shift
    x = np.zeros(n.size)
    pose = x[:6*n.nn].reshape(n.nn, 6)
    pose[:, :3] = (r-n.rj)/n.L
    pose[:, 3:] = q
    if local:
        u, w, a, alpha = LOCAL
        values = (u+np.cross(w, r), np.broadcast_to(w, r.shape),
                  a+np.cross(alpha, r)+np.cross(w, np.cross(w, r)), np.broadcast_to(alpha, r.shape))
    else:
        values = tuple(np.zeros_like(r) for _ in range(4))
    return x, values, R, shift


def balanced_state(f, tilted=False, local=False):
    """Solve only the linear force/moment balance at the prescribed pose.

    This is not a nonlinear equilibrium claim when the pose moves the clamp.
    No displacement is fitted to an archived reference or to the other model.
    """
    certify_extension(f)
    n = f.network
    x, values, R, shift = state(f, tilted, local)
    options = dict(elastic_motion=values)
    rows = np.arange(6*n.ne, 6*(n.ne+n.nn))
    cols = np.arange(6*n.nn, n.size)
    before = n.residual(x, **options)
    block = np.empty((len(rows), len(cols)))
    for i, column in enumerate(cols):
        trial = x.copy(); trial[column] += 1
        block[:, i] = (n.residual(trial, **options)-before)[rows]
    x[cols] = np.linalg.solve(block, -before[rows])
    residual, data = n.residual(x, detail=True, **options)
    if np.max(abs(residual[rows])) > 2e-13:
        raise ValueError('Nodal load balance did not close')
    return x, data, residual, values, R, shift


def point_oracle(f, R, shift, local):
    """Independent inertial transport and intrinsic point couple."""
    p = R@f.point+shift
    frame = f.network.motion
    u, w, a, alpha = LOCAL if local else np.zeros((4, 3))
    v = u+np.cross(w, p)
    acceleration = a+np.cross(alpha, p)+np.cross(w, np.cross(w, p))
    delta = p-REFERENCE
    absolute = (frame.acceleration+np.cross(frame.angular_acceleration, delta)
                +np.cross(frame.rates, np.cross(frame.rates, delta))
                +acceleration+2*np.cross(frame.rates, v))
    omega = frame.rates+w
    angular = frame.angular_acceleration+alpha+np.cross(frame.rates, w)
    I = R@INERTIA@R.T
    force = MASS*(GRAVITY-absolute)
    couple = -I@angular-np.cross(omega, I@omega+R@SPIN)
    return p, force, couple


def physical_loads(f, data):
    elements, _ = recover_source_structure(f.network, data)
    kept = [e for e in elements if e['beam'] == 1]
    return np.array([v for e in kept for t in e['endpoint_traces'] for v in (t['force'], t['moment'])])


def compare_loads(*, upper=False, panels=4, tilted=False, local=False, moving=True):
    pair = [fixture(extended=e, upper=upper, panels=panels, moving=moving) for e in (True, False)]
    checked, residuals, errors = [], [], []
    for f in pair:
        _, data, residual, _, R, shift = balanced_state(f, tilted, local)
        p, force, couple = point_oracle(f, R, shift, local)
        sign = 1 if upper else -1
        expected = []
        n = f.network
        for i in f.physical_elements:
            for node in (n.a[i], n.b[i]):
                expected.extend([sign*force, sign*(couple+np.cross(p-data['r'][node], force))])
        actual = physical_loads(f, data)
        expected = np.array(expected)
        error = float(np.max(abs(actual-expected)/(1+abs(expected))))
        if error > 2e-13:
            raise ValueError(f'Independent section-load oracle differs: {error}')
        checked.append(actual); errors.append(error)
        residuals.append(float(np.max(abs(residual))))
    difference = float(np.max(abs(checked[0]-checked[1])/(1+abs(checked[0]))))
    if difference > 2e-13:
        raise ValueError('Retained section loads changed')
    return dict(upper=upper, panels=panels, tilted=tilted, local_motion=local, moving_frame=moving,
                inward_endpoint_traces=2*panels, maximum_oracle_error=max(errors),
                maximum_pair_difference=difference, complete_residuals=residuals)


def physical_matrix(n, x):
    """Convert the production Jacobian to dimensional state/residual units."""
    matrix, report = jacobian(n, x, 1.)
    columns = np.ones(n.size)
    columns[:6*n.nn].reshape(n.nn, 6)[:, :3] = 1/n.L
    columns[6*n.nn:6*(n.nn+n.ne)].reshape(n.ne, 6)[:, :3] = 1/n.F
    columns[6*n.nn:6*(n.nn+n.ne)].reshape(n.ne, 6)[:, 3:] = 1/(n.F*n.L)
    columns[6*(n.nn+n.ne):].reshape(-1, 6)[:, :3] = 1/n.F
    columns[6*(n.nn+n.ne):].reshape(-1, 6)[:, 3:] = 1/(n.F*n.L)
    rows = np.ones(n.size)
    rows[:6*n.ne].reshape(n.ne, 6)[:, :3] = n.L
    rows[6*n.ne:6*n.ne+3*n.nn] = n.F
    rows[6*n.ne+3*n.nn:6*(n.ne+n.nn)] = n.F*n.L
    rows[6*(n.ne+n.nn):].reshape(-1, 6)[:, :3] = n.L
    return rows[:, None]*matrix.toarray()*columns[None, :], report


def compare_tangent(*, upper=False, tilted=False):
    extended = fixture(extended=True, upper=upper)
    condensed = fixture(extended=False, upper=upper)
    x, *_ = balanced_state(extended, tilted)
    y, *_ = balanced_state(condensed, tilted)
    A, ar = physical_matrix(extended.network, x)
    B, br = physical_matrix(condensed.network, y)
    n = extended.network
    nodes, elements = extended.physical_nodes, extended.physical_elements
    keep_columns = np.r_[(6*nodes[:, None]+np.arange(6)).ravel(),
        (6*n.nn+6*elements[:, None]+np.arange(6)).ravel(), 6*(n.nn+n.ne)+np.arange(6)]
    keep_rows = np.r_[(6*elements[:, None]+np.arange(6)).ravel(),
        (6*n.ne+3*nodes[:, None]+np.arange(3)).ravel(),
        (6*n.ne+3*n.nn+3*nodes[:, None]+np.arange(3)).ravel(), 6*(n.ne+n.nn)+np.arange(6)]
    eliminate_columns = np.setdiff1d(np.arange(n.size), keep_columns)
    eliminate_rows = np.setdiff1d(np.arange(n.size), keep_rows)
    Ae = A[np.ix_(eliminate_rows, eliminate_columns)]
    reduced = A[np.ix_(keep_rows, keep_columns)]-A[np.ix_(keep_rows, eliminate_columns)]@np.linalg.solve(
        Ae, A[np.ix_(eliminate_rows, keep_columns)])
    error = float(np.max(abs(reduced-B)/(1+abs(B))))
    if error > 2e-7:
        raise ValueError(f'Condensed production matrix differs: {error}')
    return dict(upper=upper, tilted=tilted, full_size=n.size, reduced_size=condensed.network.size,
                eliminated_variables=len(eliminate_columns), maximum_scaled_difference=error,
                extension_block_condition=float(np.linalg.cond(Ae)),
                methods=[ar['mechanical_derivative']['method'], br['mechanical_derivative']['method']],
                scope='Steady moving-frame load/pose/internal-force tangent; no local-rate or acceleration columns.')
