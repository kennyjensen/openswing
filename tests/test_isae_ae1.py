"""Check the explicit Pazy mirror, without weakening the production wall guard.

The half-wing image calculation below is a test-only reference. Its root chord
is exactly on y=0; the production clearance method still rejects that contact.
The two models share physical panels/collocation points, not independently
generated half/full Glauert meshes. No coupled equilibrium is solved here.
"""
from copy import deepcopy
from dataclasses import fields, replace
import hashlib
from pathlib import Path
import sys

import numpy as np
import pytest
from scipy.spatial.transform import Rotation

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import isae_ae1 as study
from openswing.aero import evaluate_aerodynamics
from openswing.asw import parse_asw
from openswing.factored_influence import FactoredInfluence
from openswing.frozen_influence import lifting_geometry
from openswing.geometry import PanelMesh, model_meshes, surface_frame
from openswing.ground import GroundIntersectionError, GroundPlane
from openswing.structure import Section

S = np.diag([1., -1., 1.])
D = np.diag([-1., 1., -1., 1., -1., 1.])


@pytest.fixture(scope='module')
def models():
    text, data, panels = study.configuration(2)
    half_text, half_data, _ = study.half_configuration(2)
    return parse_asw(text), parse_asw(half_text), data, half_data, panels


def _section(beam, t):
    return Section(**{f.name: float(beam.value(f.name, t)) for f in fields(Section)})


def _reduced_stiffness(section):
    # Independent strain-energy construction in [eps_s,k_s,k_c,k_n].
    bending = np.array([[section.GJ, section.EIcs, section.EIsn],
                        [section.EIcs, section.EIcc, section.EIcn],
                        [section.EIsn, section.EIcn, section.EInn]])
    axial = np.array([1., 0., -section.Nta, section.Cta])
    result = section.EA * np.outer(axial, axial)
    result[1:, 1:] += bending
    return result


def _tensor(row, gravity):
    xx, yy, zz, xy, xz, yz = np.asarray(row[11:17]) / gravity
    return np.array([[xx, -xy, -xz], [-xy, yy, -yz], [-xz, -yz, zz]])


def test_primary_sources_center_clamp_material_and_point_mass_mirror(models):
    full, half, data, half_data, panels = models
    original = study.source(1)
    assert len(full.beams) == len(half.beams) == 1
    beam, half_beam = full.beams[0], half.beams[0]
    assert beam.index == beam.physical_index == 1
    assert len(full.records['ground']) == 1
    np.testing.assert_array_equal(full.records['ground'][0], [1., 0., 0.])
    assert data['actual_semispan'] == original['coordinates'][-1, 1]
    assert data['nominal_semispan'] == .55
    nodes = np.asarray(panels['beams']['1']['nodes'])
    np.testing.assert_array_equal(nodes, -nodes[::-1])
    assert np.count_nonzero(nodes == 0.) == 1
    assert len(nodes) == 61 and len(data['sections']) == 30
    np.testing.assert_allclose(full.reference[0], [2*.1*nodes[-1], .1, 2*nodes[-1]], rtol=0, atol=1e-16)
    native_signs = np.diag([1., 1., -1., 1.])
    strain_signs = np.diag([1., -1., 1., 1.])
    for i, (a, b) in enumerate(zip(data['material_stations'][:-1], data['material_stations'][1:])):
        t = (a+b)/2
        positive, negative = _section(beam, t), _section(beam, -t)
        primary = original['stiffness'][i].copy()
        primary[0, 1] = primary[1, 0] = 0.  # Explicit pre-existing K12 projection.
        expected = native_signs @ primary @ native_signs
        np.testing.assert_allclose(_reduced_stiffness(positive), expected, rtol=3e-14, atol=3e-12)
        np.testing.assert_allclose(_reduced_stiffness(negative), strain_signs @ expected @ strain_signs,
                                   rtol=3e-14, atol=3e-12)
        np.testing.assert_allclose(negative.compliance(), D @ positive.compliance() @ D, rtol=3e-14, atol=1e-15)
        np.testing.assert_allclose(_section(half_beam, 1+t).compliance(), positive.compliance(), rtol=3e-14, atol=1e-15)
    # Check both traces of every material jump, including the odd root jump.
    for t in data['material_stations'][:-1]:
        for name in ('EA', 'EIcc', 'GJ', 'EInn', 'EIcs', 'EIcn', 'EIsn', 'Cta', 'Nta'):
            sign = -1. if name in {'EIcs', 'EIsn'} else 1.
            assert beam.value(name, -t, side='left') == pytest.approx(sign*beam.value(name, t, side='right'), rel=3e-14, abs=1e-14)
    weights, half_weights = full.records['weight'], half.records['weight']
    assert len(weights) == 34 and len(half_weights) == 17
    for i, half_row in enumerate(half_weights):
        left, right = weights[i], weights[i+17]
        np.testing.assert_allclose(right[2:], half_row[2:], rtol=0, atol=1e-15)
        assert left[1] == -right[1] and half_row[1] == pytest.approx(1+right[1], abs=1e-15)
        np.testing.assert_allclose(left[2:5], S @ right[2:5], rtol=0, atol=0)
        np.testing.assert_allclose(_tensor(left, full.constants[0]), S @ _tensor(right, full.constants[0]) @ S, rtol=0, atol=0)
        assert left[5] == right[5]
        if i < 16:
            np.testing.assert_allclose(_tensor(right, full.constants[0]), original['inertia'][i], rtol=3e-15, atol=1e-20)
            assert right[5]/full.constants[0] == pytest.approx(original['mass'][i], rel=2e-15)
    assert weights[16][5]/full.constants[0] == pytest.approx(.01)
    # The source adapter must not change any pinned input while constructing a model.
    for entry in data['source_pins'] + half_data['source_pins']:
        raw = Path(entry['path']).read_bytes()
        assert len(raw) == entry['bytes']
        assert hashlib.sha256(raw).hexdigest() == entry['sha256']
    flight = study.condition(5., 30.)
    assert flight.ground_effect == 0 and flight.gravity_magnitude == 0 and flight.mach == 0
    assert abs(flight.vectors()[0] @ np.array([0., 1., 0.])) == 0


def _deform(mesh):
    """Prescribed finite bending/sweep/twist with an unchanged root pose."""
    length = mesh.beam.domain[1]
    def pose(t):
        u = abs(t)/length
        position = np.column_stack([.04*length*u*u, t, .22*length*u*u])
        vector = np.column_stack([.45*u, .14*u*u, .10*u])
        vector[t < 0] *= np.array([-1., 1., -1.])  # Axial rotation reflection.
        return position, Rotation.from_rotvec(vector).as_matrix()
    r0, frame0 = pose(mesh.t0)
    r1, frame1 = pose(mesh.t1)
    fraction = (mesh.tm-mesh.t0)/(mesh.t1-mesh.t0)
    local_rotation = Rotation.from_matrix(frame0.transpose(0, 2, 1) @ frame1).as_rotvec()
    frames_mid = frame0 @ Rotation.from_rotvec(fraction[:, None]*local_rotation).as_matrix()
    return replace(mesh, r0=r0, r1=r1, rm=r0+fraction[:, None]*(r1-r0),
                   frames=frames_mid, frame0=frame0, frame1=frame1,
                   length=np.linalg.norm(r1-r0, axis=1))


def _half_from_full(full_mesh, half_beam):
    right = full_mesh.t0 >= 0.
    assert np.count_nonzero(right)*2 == len(right)
    def select(name):
        value = getattr(full_mesh, name)
        return None if value is None else value[right].copy()
    return PanelMesh(half_beam, full_mesh.t0[right]+1, full_mesh.t1[right]+1,
                     full_mesh.tm[right]+1, select('r0'), select('r1'), select('rm'),
                     select('frames'), select('length'), select('frame0'), select('frame1'),
                     full_mesh.ts[right]+1)


def _exact_root_fixture_clearance(plane, meshes, points=(), engine_points=(), engine_rows=(), engine_rotations=None, *, model=None):
    """Permit this asserted test fixture only; never install in production."""
    assert plane.flag == 1 and plane.offset == 0.
    np.testing.assert_array_equal(plane.normal, [0., 1., 0.])
    assert len(meshes) == 1 and len(points) == len(engine_points) == len(engine_rows) == 0
    mesh = meshes[0]
    assert mesh.beam.lifting and mesh.t0[0] == mesh.beam.domain[0] == 1.
    for t, position, frames_end, side in ((mesh.t0, mesh.r0, mesh.frame0, 'right'),
                                         (mesh.t1, mesh.r1, mesh.frame1, 'left')):
        q = surface_frame(mesh.beam, t, side) if frames_end is None else frames_end
        chord = mesh.beam.value('chord', t, side=side)
        axis = mesh.beam.value('Xax', t, side=side)
        root = t == 1.
        for fraction in (-axis, 1-axis):
            distance = plane.distance(position+(chord*fraction)[:, None]*q[..., 0])
            np.testing.assert_array_equal(distance[root], np.zeros(np.count_nonzero(root)))
            assert np.all(distance[~root] > 0)
    assert np.all(plane.distance(mesh.rm) > 0)
    return 0.


@pytest.mark.parametrize('curved', [False, True], ids=['jig', 'curved-twisted'])
@pytest.mark.parametrize('mach', [0., .55], ids=['incompressible', 'PG'])
def test_exact_wall_root_images_equal_explicit_mirror_loads_and_fields(models, monkeypatch, curved, mach):
    full, half, _, _, panels = models
    full, half = deepcopy(full), deepcopy(half)
    # The retained point masses have exactly zero aerodynamic area and volume.
    # Omit them from this lifting-only test to avoid unrelated point clearance.
    for model in (full, half):
        assert all(row[6] == row[7] == 0 for row in model.records['weight'])
        model.records['weight'] = []
    half.reference = full.reference.copy()  # Same coefficient normalization.
    mesh, = model_meshes(full, panels)
    if curved:
        mesh = _deform(mesh)
    hm = _half_from_full(mesh, half.beams[0])
    n = len(hm.tm)
    np.testing.assert_allclose(mesh.rm[:n][::-1], hm.rm @ S, atol=3e-16, rtol=0)
    np.testing.assert_allclose(mesh.frames[:n][::-1], S @ hm.frames @ S, atol=5e-16, rtol=0)
    plane = GroundPlane(1, normal=(0., 1., 0.))
    # Document the retained production rejection before the narrowly asserted test override.
    with pytest.raises(GroundIntersectionError, match='touches or crosses'):
        plane.clearance([hm])
    _exact_root_fixture_clearance(plane, [hm])
    flight = replace(study.condition(7., 30.), mach=mach)
    mirrored = evaluate_aerodynamics(full, flight, [mesh])
    with monkeypatch.context() as patch:
        patch.setattr(GroundPlane, 'clearance', _exact_root_fixture_clearance)
        imaged = evaluate_aerodynamics(half, replace(flight, ground_effect=1), [hm])
    assert mirrored['converged'] and imaged['converged']
    assert mirrored['ground_plane']['flag'] == 0 and imaged['ground_plane']['flag'] == 1
    assert imaged['ground_plane']['minimum_clearance'] == 0.
    fs, hs = mirrored['strips'], imaged['strips']
    def values(strips, key):
        return np.asarray([strip[key] for strip in strips])
    gamma = values(hs, 'circulation')
    assert np.max(abs(gamma)) > .05
    for key in ('circulation', 'cl', 'normal_speed'):
        np.testing.assert_allclose(values(fs[n:], key), values(hs, key), rtol=3e-10, atol=3e-11)
        np.testing.assert_allclose(values(fs[:n], key)[::-1], values(hs, key), rtol=3e-10, atol=3e-11)
    for key in ('force', 'relative_velocity', 'velocity_position'):
        np.testing.assert_allclose(values(fs[n:], key), values(hs, key), rtol=3e-10, atol=3e-11)
        np.testing.assert_allclose(values(fs[:n], key)[::-1], values(hs, key) @ S, rtol=3e-10, atol=3e-11)
    np.testing.assert_allclose(values(fs[:n], 'moment')[::-1], -values(hs, 'moment') @ S, rtol=3e-10, atol=3e-11)
    half_force, half_moment = np.asarray(imaged['force']), np.asarray(imaged['moment'])
    np.testing.assert_allclose(mirrored['force'], half_force + S @ half_force, rtol=3e-10, atol=3e-10)
    np.testing.assert_allclose(mirrored['moment'], half_moment - S @ half_moment, rtol=3e-10, atol=3e-10)
    assert abs(mirrored['CL']) > .05 and abs(mirrored['Cm']) > .01
    for key in ('CL', 'CD', 'Cm', 'CDi', 'CDi_near', 'CDp'):
        assert mirrored[key] == pytest.approx(2*imaged[key], rel=3e-10, abs=3e-11)
    np.testing.assert_allclose([mirrored[key] for key in ('CY', 'Cl', 'Cn')], 0., atol=3e-11)
    # Independent equation-72 transfer uses the physical chord/4 arm, not the
    # wind-parallel numerical horseshoe location. Curvature makes them differ.
    velocity = values(hs, 'relative_velocity')
    circulatory = flight.density*gamma[:, None]*np.cross(velocity, hm.frames[..., 1])*hm.length[:, None]
    chord = hm.beam.value('chord', hm.tm)
    arm = ((.25-hm.beam.value('Xax', hm.tm))*chord)[:, None]*hm.frames[..., 0]
    section_moment = np.cross(arm, circulatory)
    np.testing.assert_allclose(values(hs, 'moment'), section_moment, rtol=3e-11, atol=1e-12)
    expected_moment = np.sum(np.cross(hm.rm-half.reference[1], values(hs, 'force'))+section_moment, axis=0)
    np.testing.assert_allclose(imaged['moment'], expected_moment, rtol=3e-11, atol=1e-12)
    # Direct CP, HV (physical self-bound excluded), and off-surface fields.
    wind = flight.vectors()[0]
    pg = np.eye(3)+(1/np.sqrt(1-mach*mach)-1)*np.outer(wind, wind)
    gf, gh = lifting_geometry([mesh], wind), lifting_geometry([hm], wind)
    full_gamma = values(fs, 'circulation')
    for key in ('cp', 'hv'):
        exclude_half = np.eye(n, dtype=bool) if key == 'hv' else None
        exclude_full = np.c_[np.zeros((n, n), dtype=bool), np.eye(n, dtype=bool)] if key == 'hv' else None
        full_field = FactoredInfluence(gh[key], gf['a'], gf['b'], wind, pg, 0., exclude_bound=exclude_full).apply(full_gamma)
        half_field = FactoredInfluence(gh[key], gh['a'], gh['b'], wind, pg, 0., plane, exclude_bound=exclude_half).apply(gamma)
        np.testing.assert_allclose(full_field, half_field, rtol=3e-10, atol=3e-11)
    probes = np.array([[.12, 0., .13], [-.09, 0., .17], [.23, .19, -.12]])
    full_field = FactoredInfluence(probes, gf['a'], gf['b'], wind, pg).apply(full_gamma)
    half_field = FactoredInfluence(probes, gh['a'], gh['b'], wind, pg, ground=plane).apply(gamma)
    np.testing.assert_allclose(full_field, half_field, rtol=3e-10, atol=3e-11)
    np.testing.assert_allclose(half_field[:2, 1], 0., atol=1e-13)
    assert imaged['trefftz']['available'] and mirrored['trefftz']['available']
    np.testing.assert_allclose(np.asarray(mirrored['trefftz']['velocity_body'])[n:],
                               imaged['trefftz']['velocity_body'], rtol=3e-10, atol=3e-11)


def test_production_guard_still_rejects_wall_contact_and_crossing(models):
    full, half, _, _, panels = models
    mesh, = model_meshes(full, panels)
    hm = _half_from_full(mesh, half.beams[0])
    for flag in (1, -1):
        plane = GroundPlane(flag, normal=(0., 1., 0.))
        for displacement in (0., -.001):
            delta = np.array([0., displacement, 0.])
            shifted = replace(hm, r0=hm.r0+delta, r1=hm.r1+delta, rm=hm.rm+delta)
            with pytest.raises(GroundIntersectionError, match='touches or crosses'):
                plane.clearance([shifted])


def test_finite_rotation_compatibility_and_virtual_work_mirror():
    # Reverse material integration while reflecting polar positions and axial
    # rotations: eps_minus=-S eps_plus, k_minus=S k_plus. This is why the
    # torsion/bending couplings change sign even with equal jig material frames.
    ra = Rotation.from_rotvec([.31, -.19, .24]).as_matrix()
    rb = ra @ Rotation.from_rotvec([-.17, .23, .11]).as_matrix()
    k = Rotation.from_matrix(ra.T @ rb).as_rotvec()
    middle = ra @ Rotation.from_rotvec(k/2).as_matrix()
    la, lb = S @ rb @ S, S @ ra @ S
    km = Rotation.from_matrix(la.T @ lb).as_rotvec()
    lm = la @ Rotation.from_rotvec(km/2).as_matrix()
    dr = np.array([.04, .21, -.07])
    np.testing.assert_allclose(km, S @ k, atol=2e-16)
    np.testing.assert_allclose(lm.T @ (-S @ dr), -S @ middle.T @ dr, atol=1e-16)
    force, moment = np.array([1.3, -.7, 2.1]), np.array([.2, -.3, .8])
    translation, rotation = np.array([.3, .1, -.2]), np.array([-.1, .4, .2])
    expected = force @ translation + moment @ rotation
    assert (S @ force) @ (S @ translation) + (-S @ moment) @ (-S @ rotation) == pytest.approx(expected, abs=1e-15)
