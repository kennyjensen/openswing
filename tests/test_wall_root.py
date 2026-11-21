"""Steady solid-wall roots: physical images, constrained tangents and Newton.

The exact mirror tests share physical aerodynamic receivers. A test-local mesh
adapter supplies those receivers to the half network; it never changes a
clearance check, residual, image, force law or solver. A separate coupled test
uses the ordinary public half-wing mesh. These are synthetic regressions, not
experimental validation or wall-corrected unsteady apparent-mass validation.
"""
from copy import deepcopy
from dataclasses import replace

import numpy as np
import pytest
from scipy.linalg import solve
from scipy.spatial.transform import Rotation

from openswing.aero import FlightCondition, evaluate_aerodynamics
from openswing.asw import parse_asw
from openswing.factored_influence import FactoredInfluence
from openswing.frozen_influence import lifting_geometry
from openswing.geometry import PanelMesh, model_meshes, surface_frame
from openswing.ground import GroundIntersectionError, GroundPlane
from openswing.network import StaticNetwork, solve_static
from openswing.equilibrium_state import capture, restore
from openswing.wall_root import wall_root_derivatives
import openswing.network as network_module
import openswing.structured_static as static


S = np.diag([1., -1., 1.])


def configuration(mirrored, intervals=4, *, interpolation='natural-v1'):
    """Uniform finite-stiffness reference, with reflected anisotropic coupling."""
    shift = 0 if mirrored else 1
    physical = np.linspace(-1 if mirrored else 0, 1, intervals*(2 if mirrored else 1)+1)
    section = [100, 20, 200, 5, 2, 3, 1e6, 1e5, 1e5]
    rows = ['Name', 'Synthetic mounted wall reference', 'End', 'Unit',
            'L 1 m', 'T 1 s', 'F 1 N', 'End', 'Constant',
            '9.80665 1.225 340.294', 'End', 'Reference', '.4 .2 2',
            '0 0 0', '0 0 0', '0 0 0', 'End', 'Ground',
            f'1 {shift} 0', 'End', 'Weight',
            f'1 {shift} 0 0 0 {2 if mirrored else 1}', 'End', 'Beam 1',
            'Uniform reflected material', 't x y z chord Xax twist']
    def row(values):
        return ' '.join(format(float(v), '.17g') for v in values)
    for y in ([-1, 0, 1] if mirrored else [0, 1]):
        rows.append(row([y+shift, 0, y, 0, .2, .4, 0]))
    rows.append('t EIcc GJ EInn EIcs EIcn EIsn EA GKc GKn')
    for side, points in ([(-1, [-1, 0]), (1, [0, 1])] if mirrored else [(1, [1, 2])]):
        values = section.copy()
        values[3] *= side
        values[5] *= side
        rows.extend(row([t, *values]) for t in points)
    mg = 9.80665*.5
    rows.append('t mg mgcc mgnn')
    rows.extend(row([t, mg, mg*.02**2/12, mg*.2**2/12])
                for t in (physical[0]+shift, physical[-1]+shift))
    rows.append('t dCLda CLmax CLmin alpha Cm Cdf Cdp')
    rows.extend(row([t, 2*np.pi, 2, -2, 0, 0, 0, 0])
                for t in (physical[0]+shift, physical[-1]+shift))
    rows.append('End')
    model = parse_asw('\n'.join(rows)+'\n', beam_interpolation=interpolation)
    panels = dict(default=len(physical)-1, beams={'1': dict(nodes=(physical+shift).tolist())})
    return model, panels


def flight(mirrored=False, mach=0.):
    return FlightCondition(speed=10., alpha=3., beta=0., density=1.225,
                           mach=mach, gravity_magnitude=0., ground_effect=0 if mirrored else 1,
                           ground_normal=[0., 1., 0.], stall=False)


def positive_half(full, beam):
    keep = full.t0 >= 0
    def selected(name):
        value = getattr(full, name)
        return None if value is None else value[keep].copy()
    return PanelMesh(beam, full.t0[keep]+1, full.t1[keep]+1, full.tm[keep]+1,
                     selected('r0'), selected('r1'), selected('rm'), selected('frames'),
                     selected('length'), selected('frame0'), selected('frame1'),
                     full.ts[keep]+1,
                     None if full.theta is None else full.theta[np.flatnonzero(keep)[0]:].copy(),
                     full.mesh_recipe)


def curved(full):
    def pose(t):
        u = abs(t)
        r = np.column_stack([.03*u*u, t, .12*u*u])
        v = np.column_stack([.25*u*u, .10*u*u, .08*u*u])
        v[t < 0] *= [-1, 1, -1]
        return r, Rotation.from_rotvec(v).as_matrix()
    a, qa = pose(full.t0)
    b, qb = pose(full.t1)
    fraction = (full.tm-full.t0)/(full.t1-full.t0)
    relative = Rotation.from_matrix(qa.transpose(0, 2, 1)@qb).as_rotvec()
    qm = qa@Rotation.from_rotvec(fraction[:, None]*relative).as_matrix()
    return replace(full, r0=a, r1=b, rm=a+fraction[:, None]*(b-a),
                   frames=qm, frame0=qa, frame1=qb, length=np.linalg.norm(b-a, axis=1))


def network(mirrored=False, *, matched=None, monkeypatch=None):
    model, panels = configuration(mirrored)
    if matched is None:
        return StaticNetwork(model, panels, flight(mirrored), None, [])
    assert not mirrored and monkeypatch is not None
    shared = positive_half(matched, model.beams[0])
    def shared_mesh(beam, settings, stations, **kwargs):
        assert beam is model.beams[0]
        assert all(t in np.r_[shared.t0, shared.t1[-1]] for t in stations)
        return shared
    with monkeypatch.context() as patch:
        patch.setattr(network_module, 'mesh_beam', shared_mesh)
        return StaticNetwork(model, panels, flight(), None, [])


@pytest.mark.parametrize('deformed', [False, True], ids=['jig', 'curved-twisted'])
@pytest.mark.parametrize('mach', [0., .55], ids=['incompressible', 'PG'])
def test_real_wall_images_match_full_mirror_fields_and_physical_loads(deformed, mach):
    full, panels = configuration(True)
    half, _ = configuration(False)
    fm, = model_meshes(full, panels)
    if deformed:
        fm = curved(fm)
    hm = positive_half(fm, half.beams[0])
    fr = evaluate_aerodynamics(full, flight(True, mach), [fm])
    hr = evaluate_aerodynamics(half, flight(False, mach), [hm])
    n = len(hm.tm)
    assert fr['converged'] and hr['converged']
    assert hr['ground_plane']['minimum_clearance'] == 0.
    # Keep the root point mass in the actual model, including native evaluation.
    np.testing.assert_array_equal(hr['point_forces'], [[0., 0., 0.]])
    def values(result, key):
        return np.asarray([s[key] for s in result['strips']])
    for key in ('circulation', 'cl', 'normal_speed', 'force', 'moment', 'relative_velocity'):
        np.testing.assert_allclose(values(fr, key)[n:], values(hr, key), rtol=3e-10, atol=3e-11)
    gamma = values(hr, 'circulation')
    assert np.max(abs(gamma)) > .01
    force, moment = np.asarray(hr['force']), np.asarray(hr['moment'])
    np.testing.assert_allclose(fr['force'], force+S@force, rtol=3e-10, atol=3e-11)
    np.testing.assert_allclose(fr['moment'], moment-S@moment, rtol=3e-10, atol=3e-11)
    # Equation-72 physical quarter-chord couple, not the numerical HV point.
    velocity = values(hr, 'relative_velocity')
    circulatory = 1.225*gamma[:, None]*np.cross(velocity, hm.frames[..., 1])*hm.length[:, None]
    arm = (.25-.4)*.2*hm.frames[..., 0]
    np.testing.assert_allclose(values(hr, 'moment'), np.cross(arm, circulatory), rtol=3e-11, atol=1e-12)
    e = flight(False, mach).vectors()[0]
    pg = np.eye(3)+(1/np.sqrt(1-mach**2)-1)*np.outer(e, e)
    gf, gh = lifting_geometry([fm], e), lifting_geometry([hm], e)
    plane = GroundPlane(1, normal=[0., 1., 0.])
    for key in ('cp', 'hv'):
        exclude = np.eye(n, dtype=bool) if key == 'hv' else None
        full_exclude = np.c_[np.zeros((n, n), dtype=bool), exclude] if exclude is not None else None
        expected = FactoredInfluence(gh[key], gf['a'], gf['b'], e, pg, 0., exclude_bound=full_exclude).apply(values(fr, 'circulation'))
        actual = FactoredInfluence(gh[key], gh['a'], gh['b'], e, pg, 0., plane, exclude_bound=exclude).apply(gamma)
        np.testing.assert_allclose(actual, expected, rtol=3e-10, atol=3e-11)
    probes = np.array([[.13, 0., .17], [-.11, 0., .21]])
    wall_velocity = FactoredInfluence(probes, gh['a'], gh['b'], e, pg, ground=plane).apply(gamma)
    np.testing.assert_allclose(wall_velocity[:, 1], 0., rtol=0, atol=1e-13)


def test_only_declared_complete_solid_wall_root_and_inert_attached_point_are_admitted():
    model, panels = configuration(False)
    mesh, = model_meshes(model, panels)
    plane = GroundPlane(1, normal=[0., 1., 0.])
    points = [row[2:5] for row in model.records['weight']]
    assert plane.clearance([mesh], points, model=model) == 0.
    with pytest.raises(GroundIntersectionError):
        plane.clearance([mesh], points)  # Historical undeclared contact remains strict.
    for kind in (1, 2):
        bad = deepcopy(model)
        bad.records['ground'][0][-1] = kind
        with pytest.raises(GroundIntersectionError):
            plane.clearance([mesh], points, model=bad)
    with pytest.raises(GroundIntersectionError):
        GroundPlane(-1, normal=[0., 1., 0.]).clearance([mesh], points, model=model)
    for column in (6, 7):
        bad = deepcopy(model)
        bad.records['weight'][0][column] = .01
        with pytest.raises(GroundIntersectionError):
            plane.clearance([mesh], points, model=bad)
    for displacement in (-1e-5, 1e-5):
        q = surface_frame(mesh.beam, mesh.t0)
        q[0] = Rotation.from_rotvec([0., 0., displacement]).as_matrix()@q[0]
        with pytest.raises(GroundIntersectionError):
            plane.clearance([replace(mesh, frame0=q)], points, model=model)
    for displacement in (np.array([0., -1e-5, 0.]), np.array([0., -2., 0.])):
        changed = replace(mesh, r0=mesh.r0+displacement, r1=mesh.r1+displacement,
                          rm=mesh.rm+displacement)
        with pytest.raises(GroundIntersectionError):
            plane.clearance([changed], points, model=model)
    a = mesh.r0.copy()
    a[1, 1] = 0.  # An interior chord does not become a permitted wall root.
    with pytest.raises(GroundIntersectionError):
        plane.clearance([replace(mesh, r0=a)], points, model=model)


def test_wall_root_requires_tangential_steady_imposed_flow():
    model, panels = configuration(False)
    meshes = model_meshes(model, panels)
    for change in (dict(beta=1.), dict(rates=[0., 0., .01])):
        with pytest.raises(GroundIntersectionError):
            evaluate_aerodynamics(model, replace(flight(), **change), meshes)


def test_wall_root_allows_interior_motion_but_keeps_the_mount_stationary():
    net = network()
    x = np.zeros(net.size)
    zero = np.zeros((net.nn, 3))
    baseline = net.residual(x)
    explicit = net.residual(x, elastic_motion=(zero, zero, zero, zero),
                            circulation_rate=np.zeros(net.ng))
    np.testing.assert_allclose(explicit, baseline, rtol=0, atol=1e-14)
    for component in range(4):
        fields = [zero.copy() for _ in range(4)]
        fields[component][-1, 2] = .01
        assert np.isfinite(net.residual(x, elastic_motion=tuple(fields))).all()
        fields[component][net.node(1, 1.), 2] = .01
        with pytest.raises(GroundIntersectionError, match='zero elastic motion'):
            net.residual(x, elastic_motion=tuple(fields))
    assert np.isfinite(net.residual(x, circulation_rate=np.full(net.ng, .01))).all()
    with pytest.raises(GroundIntersectionError, match='explicit elastic motion'):
        evaluate_aerodynamics(net.model, net.condition, net.meshes,
                              circulation=np.zeros(net.ng), local_motion=object())


def test_probe_extension_is_bounded_reference_owned_and_restored_after_failure():
    net = network()
    x = np.zeros(net.size)
    root = net.node(1, 1.)
    trial = x.copy()
    trial[6*root+1] = -1e-6
    trial[6*root+5] = 1e-6
    with pytest.raises(GroundIntersectionError):
        net.residual(trial)
    with pytest.raises(RuntimeError, match='deliberate'):
        with wall_root_derivatives(net, x):
            assert np.isfinite(net.residual(trial)).all()
            # A nested owner must validate its base without inheriting permission.
            with pytest.raises(GroundIntersectionError):
                with wall_root_derivatives(net, trial):
                    pass
            enormous = trial.copy()
            enormous[6*root+1] = -.5
            with pytest.raises(GroundIntersectionError):
                net.residual(enormous)
            interior = trial.copy()
            interior[6*net.node(1, 2.)+1] = -2.
            with pytest.raises(GroundIntersectionError):
                net.residual(interior)
            raise RuntimeError('deliberate')
    assert net.aero_key is None
    with pytest.raises(GroundIntersectionError):
        net.residual(trial)
    with pytest.raises(GroundIntersectionError):
        with wall_root_derivatives(net, trial):
            pass
    with wall_root_derivatives(net, x):
        old = net.condition
        try:
            net.condition = replace(old, position_earth=[0., .01, 0.])
            with pytest.raises(GroundIntersectionError):
                net.residual(trial, condition_override=net.condition)
        finally:
            net.condition = old


def test_full_and_structured_tangents_preserve_clamps_and_admissible_response():
    net = network()
    x = np.zeros(net.size)
    x[net.gamma_start:net.operating_start] = .03
    jac = net.jacobian(x, .7, _direct_geometry=False)
    structured, _ = static.jacobian(net, x, .7)
    assert np.isfinite(jac).all() and np.isfinite(structured.toarray()).all()
    root_columns = 6*net.node(1, 1.)+np.arange(6)
    constraint_rows = 6*(net.nn+net.ne)+np.arange(6)
    expected = np.zeros((6, net.size))
    expected[:, root_columns] = np.eye(6)
    np.testing.assert_allclose(jac[constraint_rows], expected, rtol=0, atol=2e-10)
    rng = np.random.default_rng(5831)
    direction = rng.normal(size=net.size)*.01
    direction[root_columns] = 0.
    h = 1e-4
    samples = [net.residual(x+k*h*direction, .7) for k in (1, -1, 2, -2)]
    centered = (8*(samples[0]-samples[1])-(samples[2]-samples[3]))/(12*h)
    np.testing.assert_allclose(jac@direction, centered, rtol=2e-5, atol=2e-6)
    # Any extension agreeing on the clamp manifold differs only in root
    # columns. The six constraint rows and reaction insertion remain intact.
    rhs = rng.normal(size=net.size)
    rhs[constraint_rows] = 0.
    changed = jac.copy()
    additions = rng.normal(size=(net.size, 6))*.3
    additions[constraint_rows] = 0.
    changed[:, root_columns] += additions
    original = solve(jac, rhs)
    alternate = solve(changed, rhs)
    np.testing.assert_allclose(original[root_columns], 0., rtol=0, atol=1e-12)
    np.testing.assert_allclose(alternate, original, rtol=2e-10, atol=2e-11)
    assert net.iteration_fields is None and net.tangent_influences is None


def test_actual_coupled_wall_solution_equals_shared_mesh_full_mirror(monkeypatch):
    full = network(True)
    half = network(matched=full.meshes[0], monkeypatch=monkeypatch)
    xf, _ = static.equilibrate(full, tolerance=1e-10)
    # Exercise the real full-Jacobian fallback after one failed sparse direction.
    original_solve = static.block_solve
    failures = []
    def fail_once(*args, **kwargs):
        if not failures:
            failures.append(True)
            raise RuntimeError('one forced sparse-factor failure')
        return original_solve(*args, **kwargs)
    with monkeypatch.context() as patch:
        patch.setattr(static, 'block_solve', fail_once)
        xh, _ = static.equilibrate(half, tolerance=1e-10)
    assert failures and any(row.get('exact_fallback') for row in half.structured_iterations)
    rf, df = full.residual(xf, detail=True)
    rh, dh = half.residual(xh, detail=True)
    assert max(np.max(abs(rf)), np.max(abs(rh))) <= 1e-10
    pf, qf, nf, mf, _, gf = full.unpack(xf)
    ph, qh, nh, mh, _, gh = half.unpack(xh)
    n = half.ne
    assert ph[-1, 2] > 1e-4 and np.linalg.norm(qh[-1]-np.eye(3)) > 1e-4
    for actual, expected in ((ph, pf[n:]), (qh, qf[n:]), (nh, nf[n:]), (mh, mf[n:]), (gh, gf[n:])):
        np.testing.assert_allclose(actual, expected, rtol=2e-7, atol=2e-9)
    np.testing.assert_allclose(ph[0], [0., 0., 0.], rtol=0, atol=1e-13)
    np.testing.assert_allclose(qh[0], np.eye(3), rtol=0, atol=1e-13)
    ff, fh = np.asarray(df['aero']['force']), np.asarray(dh['aero']['force'])
    mf, mh = np.asarray(df['aero']['moment']), np.asarray(dh['aero']['moment'])
    np.testing.assert_allclose(ff, fh+S@fh, rtol=2e-7, atol=2e-9)
    np.testing.assert_allclose(mf, mh-S@mh, rtol=2e-7, atol=2e-9)
    plane = dh['aero']['ground_plane']
    assert abs(plane['minimum_clearance']) <= plane['wall_root_roundoff_tolerance']
    assert half.iteration_fields is None and half.tangent_influences is None


def test_native_half_mesh_public_cold_and_saved_equilibrium_paths():
    net = network()
    cold = solve_static(net.model, net.condition, net.panels, tolerance=1e-10)
    x = restore(net, cold['equilibrium_state'])
    residual, data = net.residual(x, detail=True)
    assert np.max(abs(residual)) <= 1e-10
    positions, rotations, *_ = net.unpack(x)
    assert positions[-1, 2] > 1e-4
    np.testing.assert_allclose(positions[0], [0., 0., 0.], rtol=0, atol=1e-13)
    np.testing.assert_allclose(rotations[0], np.eye(3), rtol=0, atol=1e-13)
    plane = data['aero']['ground_plane']
    assert abs(plane['minimum_clearance']) <= plane['wall_root_roundoff_tolerance']
    assert not data['aero']['ground_plane']['wall_root_derivative_probe']
    saved = capture(net, x, residual=float(np.max(abs(residual))))
    unchanged = deepcopy(saved)
    progress = []
    warm = solve_static(net.model, net.condition, net.panels, tolerance=1e-10,
                        initial_state=saved, progress=lambda *args: progress.append(args))
    assert warm['equilibrium_initialization']['initialization'] == 'saved physical equilibrium'
    assert warm['residual'] <= 1e-10 and saved == unchanged
    for key in ('positions', 'rotations', 'internal_force', 'internal_moment', 'reactions', 'circulation'):
        np.testing.assert_allclose(warm['equilibrium_state'][key], saved[key], rtol=2e-8, atol=2e-9)
    for key in ('force', 'moment', 'CL', 'CD', 'Cm'):
        np.testing.assert_allclose(warm[key], cold[key], rtol=2e-8, atol=2e-9)
    assert any(row[0] == 'equilibrium_rank' for row in progress)
    assert not warm['ground_plane']['wall_root_derivative_probe']
