"""Published instantaneous images checked against explicit moving mirror wings."""
from dataclasses import replace

import numpy as np
import pytest
from scipy.spatial.transform import Rotation

from openswing.aero import evaluate_aerodynamics
from openswing.factored_influence import FactoredInfluence
from openswing.frozen_influence import lifting_geometry
from openswing.ground import GroundIntersectionError, GroundPlane
from openswing.linear_dynamics import make_system, linearize, output_perturbation
from openswing.local_motion import NetworkMotion
from openswing.source_airflow import AIRFLOW_POLICY
from openswing.wall_root import wall_root_derivatives
from test_wall_root import S, configuration, flight, network


def moving_state(n, deformed):
    y = n.rj[:, 1]
    u = abs(y)
    r = n.rj.copy()
    angle = np.zeros_like(r)
    if deformed:
        r[:, 0] += .03*u*u
        r[:, 2] += .12*u*u
        angle = u[:, None]**2*np.array([.25, .10, .08])
        angle[y < 0] *= [-1, 1, -1]
    q = Rotation.from_rotvec(angle).as_matrix()
    fields = [u[:, None]**2*np.array(v) for v in
              ([.07, .03, -.13], [.11, -.21, .09], [-.08, .04, .35], [.14, .31, -.17])]
    for i, value in enumerate(fields):
        value[y < 0] *= [1, -1, 1] if i % 2 == 0 else [-1, 1, -1]
    meshes = n.deformed_meshes(r, q, n.geometry(r, q))
    return meshes, NetworkMotion(n, r, q, *fields)


@pytest.mark.parametrize('deformed', [False, True], ids=['jig', 'bent-twisted'])
@pytest.mark.parametrize('mach', [0., .55], ids=['incompressible', 'PG'])
@pytest.mark.parametrize('lag', [False, True], ids=['algebraic', 'lag'])
def test_moving_half_wing_matches_explicit_full_mirror(deformed, mach, lag, monkeypatch):
    full = network(True)
    half = network(matched=full.meshes[0], monkeypatch=monkeypatch)
    results, meshes = [], []
    for n, mirrored in ((full, True), (half, False)):
        mesh, motion = moving_state(n, deformed)
        y = mesh[0].rm[:, 1]
        gamma = .23*(1-y*y)
        gamma_dot = -.17*(1-y*y)
        result = evaluate_aerodynamics(n.model, replace(flight(mirrored, mach), aero_lag=lag),
            mesh, circulation=gamma, local_motion=motion, circulation_rate=gamma_dot)
        results.append(result); meshes.append(mesh[0])
    fr, hr = results
    count = len(hr['strips'])
    for key in ('circulation', 'circulation_rate', 'cl', 'normal_speed', 'force', 'moment',
                'relative_velocity', 'apparent_force', 'apparent_moment', 'circulation_rate_force'):
        expected = np.asarray([s[key] for s in fr['strips']])[count:]
        actual = np.asarray([s[key] for s in hr['strips']])
        np.testing.assert_allclose(actual, expected, rtol=2e-11, atol=2e-12)
    np.testing.assert_allclose(fr['circulation_residual'][count:], hr['circulation_residual'],
                               rtol=2e-11, atol=2e-12)
    for key in ('force', 'apparent_force', 'circulation_rate_force'):
        value = np.asarray(hr[key])
        np.testing.assert_allclose(fr[key], value+S@value, rtol=2e-11, atol=2e-12)
    for key in ('moment', 'apparent_moment', 'circulation_rate_moment'):
        value = np.asarray(hr[key])
        np.testing.assert_allclose(fr[key], value-S@value, rtol=2e-11, atol=2e-12)
    assert np.linalg.norm(hr['apparent_force']) > .001
    assert (np.linalg.norm(hr['circulation_rate_force']) > .001) == lag
    # An independent wall probe also checks the time-varying induced field.
    e = flight(False, mach).vectors()[0]
    pg = np.eye(3)+(1/np.sqrt(1-mach**2)-1)*np.outer(e, e)
    g = lifting_geometry([meshes[1]], e)
    points = np.array([[.31, 0., .27], [-.19, 0., -.21]])
    field = FactoredInfluence(points, g['a'], g['b'], e, pg,
                             ground=GroundPlane(1, normal=[0., 1., 0.]))
    for strength in ('circulation', 'circulation_rate'):
        values = np.asarray([s[strength] for s in hr['strips']])
        np.testing.assert_allclose(field.apply(values)[:, 1], 0., atol=2e-14, rtol=0)


@pytest.fixture(scope='module')
def wall_system():
    model, panels = configuration(False, intervals=4, interpolation='drela-segspl-v1')
    system, _ = make_system(model, replace(flight(), alpha=0.), panels,
        gravity=[0., 0., 0.], structural_operator=AIRFLOW_POLICY, tolerance=1e-10)
    return system


def test_wall_modal_pencils_keep_complete_residual_and_stationary_clamp(wall_system):
    s = wall_system; n = s.network
    a, m = linearize(s)
    sa, sm = (x.toarray() for x in linearize(s, sparse=True))
    np.testing.assert_allclose(sa, a, rtol=3e-8, atol=3e-9)
    np.testing.assert_allclose(sm, m, rtol=3e-10, atol=3e-11)
    z = np.zeros(s.size)
    rng = np.random.default_rng(7821)
    for _ in range(3):
        direction = rng.normal(size=s.size); direction /= np.linalg.norm(direction)
        rate = z.copy(); rate[s.dynamic_indices] = rng.normal(size=len(s.dynamic_indices))
        rate /= np.linalg.norm(rate)
        with wall_root_derivatives(n, s.base, root_motion=True):
            h = 3e-6
            da = (s.residual(h*direction, z)-s.residual(-h*direction, z))/(2*h)
            dm = -(s.residual(z, h*rate)-s.residual(z, -h*rate))/(2*h)
        for aa, mm in ((a, m), (sa, sm)):
            np.testing.assert_allclose(aa@direction, da, rtol=3e-7, atol=3e-8)
            np.testing.assert_allclose(mm@rate, dm, rtol=3e-9, atol=3e-10)
    root = n.node(1, 1.)
    bad = z.copy(); bad[s.velocity_start+3*root+2] = .001
    with pytest.raises(GroundIntersectionError, match='zero elastic motion'):
        s.residual(bad, z)
    assert n.aero_key is None
    assert np.max(abs(s.residual(z, z))) < 1e-9


def test_modal_output_probes_are_owned_but_physical_root_motion_stays_rejected(wall_system):
    s = wall_system; n = s.network
    z = np.zeros(s.size)
    direction = z.copy(); direction[6*n.node(1, 1.)+1] = 1.
    # Even off-constraint output derivatives have a well-defined extension.
    output = output_perturbation(s, direction, z)
    assert output is not None
    with pytest.raises(GroundIntersectionError):
        s.snapshot(-1e-5*direction, z)
    bad = z.copy(); bad[s.velocity_start+2] = .1
    with wall_root_derivatives(n, s.base):
        with pytest.raises(GroundIntersectionError, match='zero elastic motion'):
            s.residual(bad, z)
    with pytest.raises(RuntimeError):
        with wall_root_derivatives(n, s.base, root_motion=True):
            assert np.isfinite(s.residual(bad, z)).all()
            raise RuntimeError('probe cleanup')
    with pytest.raises(GroundIntersectionError, match='zero elastic motion'):
        s.residual(bad, z)
