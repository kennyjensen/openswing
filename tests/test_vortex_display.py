from dataclasses import replace
from pathlib import Path
import numpy as np
import pytest
from openswing.asw import parse_asw
from openswing.aero import FlightCondition, evaluate_aerodynamics
from openswing.bridge import dispatch
from openswing.geometry import model_meshes, geometry_summary, surface_frame

SOURCE = Path('examples/isae-sa11-wing-alone.asw').read_text()


def test_mirrored_skin_keeps_raw_beam_normal_chords_for_linear_outputs():
    model = parse_asw(SOURCE)
    mesh = model_meshes(model, 8)[0]
    drawing = geometry_summary(model, meshes=[mesh])[0]
    join = drawing['mirror_join']
    assert mesh.t1[join-1] == mesh.t0[join] == 0
    q = np.asarray(drawing['quads'])
    chord = q[:, 3] - q[:, 0]
    frame = surface_frame(mesh.beam, mesh.t0)
    np.testing.assert_allclose(np.linalg.norm(chord, axis=1), mesh.beam.value('chord', mesh.t0))
    np.testing.assert_allclose(np.einsum('ij,ij->i', chord, frame[..., 1]), 0., atol=2e-16)


@pytest.mark.parametrize('frozen', [True, False])
def test_preview_matches_documented_endpoint_offsets_without_solving(frozen):
    model = parse_asw(SOURCE)
    mesh = model_meshes(model, 8)[0]
    data = dispatch(dict(action='vortex_preview', source=SOURCE, panels=8,
                         view=dict(alpha=5., beta=3., freeze_influences=frozen)))
    a, b = np.deg2rad([5., 3.])
    wind = np.array([1., 0., 0.]) if frozen else np.array([np.cos(a)*np.cos(b), -np.sin(b), np.sin(a)*np.cos(b)])
    np.testing.assert_allclose(data['wake_direction'], wind)
    for i, (t, r, side) in enumerate(((mesh.t0, mesh.r0, 'right'), (mesh.t1, mesh.r1, 'left'))):
        span = surface_frame(mesh.beam, t, side)[..., 1]
        offset = (.25-mesh.beam.value('Xax', t, side=side))*mesh.beam.value('chord', t, side=side)/np.sqrt(1-(span@wind)**2)
        np.testing.assert_allclose(np.asarray(data['bound_segments'])[:, i], r+offset[:, None]*wind, atol=1e-15)
    assert data['preview'] and data['frozen'] == frozen


@pytest.mark.parametrize('frozen', [True, False])
def test_solved_overlay_uses_actual_frozen_or_current_influence_sources(frozen):
    model = parse_asw(SOURCE)
    meshes = model_meshes(model, 8)
    shift = np.array([0., 0., .2])
    moved = [replace(m, r0=m.r0+shift, r1=m.r1+shift, rm=m.rm+shift) for m in meshes]
    result = evaluate_aerodynamics(model, FlightCondition(speed=10., alpha=2., mach=0., freeze_influences=frozen), moved)
    expected = dispatch(dict(action='vortex_preview', source=SOURCE, panels=8,
                             view=dict(alpha=2., freeze_influences=frozen)))
    np.testing.assert_allclose(result['vortex_geometry']['bound_segments'],
                               np.asarray(expected['bound_segments'])+(0 if frozen else shift), atol=1e-14)
    assert not result['vortex_geometry']['preview']
    assert result['converged']
