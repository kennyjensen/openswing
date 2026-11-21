"""Field-only checks: no circulation or structural equilibrium solves."""
import numpy as np
import pytest

from openswing.asw import parse_asw
from openswing.geometry import model_meshes
from openswing.ground import GroundPlane
from openswing.volume import VolumeField
from openswing.volume_state_tangent import VolumeStateTangent
from openswing.volume_tangent import VolumeDerivativeUnavailable


def model_for(kind='mixed', *, zero_shoulder=False):
    source = '''Name
Volume state field
End
Unit
L 1 m
T 1 s
F 1 N
End
Constant
9.81 1.225 340
End
Reference
2 1 2
End
Ground
1 0
End
'''
    if kind in ('point', 'mixed'):
        # The first row is null, the second mass-only. The aerodynamic point
        # objects therefore have active Weight ordinals 1 and 2, not 0 and 1.
        source += '''Weight
1 0 0 0 0 0 0 0
1 0 .1 -.2 .4 1 0 0
1 .7 .6 -.3 .2 0 .12 .03
1 1.3 1.4 .2 -.1 0 0 .07
End
'''
    source += 'Beam 1\nBody\n'
    if kind in ('body', 'mixed'):
        source += '''t x y z radius
0 0 .1 -.1 .13
1 1.2 .3 .05 .24
2 2.3 .1 .2 .17
'''
    elif kind == 'shoulder':
        left = 0 if zero_shoulder else .12
        source += f'''t x y z
0 0 .1 -.1
2 2 .1 -.1
t radius
0 {left}
1 {left}
1 .28
2 .28
'''
    else:
        source += 't x radius\n0 0 0\n2 2 0\n'
    source += 'End\n'
    if kind == 'mixed':
        source += '''Ground
2 0
End
Beam 2
Shoulder body
t x y z
0 0 1 -.3
2 2 1 -.3
t radius
0 .11
1 .11
1 .23
2 .23
End
'''
    model = parse_asw(source)
    return model, model_meshes(model, 4)


def inputs():
    direction = np.array([.87, -.21, .32])
    pg = np.array([[1.23, .06, -.04], [.06, 1.08, .03], [-.04, .03, 1.15]])
    rng = np.random.default_rng(381)
    de = rng.normal(size=(3, 4))*.2
    dp = rng.normal(size=(3, 3, 4))*.12  # arbitrary, including non-symmetric columns
    points = np.array([[-.3, .7, .4], [.9, -.6, .3], [2.7, .4, -.7], [1.1, .5, .8]])
    dr = rng.normal(size=(len(points), 3, 4))*.15
    return direction, pg, de, dp, points, dr


def stencil(model, meshes, e, pg, de, dp, points, dr, ground, h, exclusions):
    columns = []
    for k in range(de.shape[1]):
        values = [VolumeField(model, meshes, e+sign*h*de[:, k], pg+sign*h*dp[:, :, k],
                              ground=ground).velocity(points+sign*h*dr[:, :, k], **exclusions)
                  for sign in (1, -1)]
        columns.append((values[0]-values[1])/(2*h))
    return np.stack(columns, axis=-1)


@pytest.mark.parametrize('kind', ['body', 'point', 'shoulder', 'mixed'])
@pytest.mark.parametrize('flag', [-1, 0, 1])
def test_full_field_state_columns_against_two_independent_centered_steps(kind, flag):
    model, meshes = model_for(kind)
    e, pg, de, dp, points, dr = inputs()
    ground = GroundPlane(flag, position=[.1, -.2, 1.7], attitude=[11, -7, 13], normal=[.2, -.1, 1])
    tangent = VolumeStateTangent(model, meshes, e, pg, de, dp, ground)
    before = [(mesh.r0.copy(), mesh.r1.copy()) for mesh in meshes]
    actual = tangent.velocity_columns(points, dr)
    for h in (2e-5, 1e-5):
        expected = stencil(model, meshes, e, pg, de, dp, points, dr, ground, h, {})
        np.testing.assert_allclose(actual, expected, rtol=3e-7, atol=2e-10)
    np.testing.assert_array_equal(tangent.volume.velocity(points), VolumeField(model, meshes, e, pg, ground=ground).velocity(points))
    for mesh, (r0, r1) in zip(meshes, before):
        np.testing.assert_array_equal(mesh.r0, r0)
        np.testing.assert_array_equal(mesh.r1, r1)


@pytest.mark.parametrize('flag', [-1, 0, 1])
@pytest.mark.parametrize('exclusions', [
    {'exclude_body': 1}, {'exclude_point': 1},
    {'exclude_body': np.array([1, 2, -1, 1]), 'exclude_point': np.array([1, -1, 2, 0])},
])
def test_body_point_exclusions_preserve_images_and_active_point_indices(flag, exclusions):
    model, meshes = model_for()
    e, pg, de, dp, points, dr = inputs()
    ground = GroundPlane(flag, position=[0, 0, 1.1], attitude=[8, -14, 3])
    tangent = VolumeStateTangent(model, meshes, e, pg, de, dp, ground)
    assert set(tangent.volume.points[tangent.volume.points >= 0]) == {1, 2}
    actual = tangent.velocity_columns(points, dr, **exclusions)
    for h in (2e-5, 1e-5):
        expected = stencil(model, meshes, e, pg, de, dp, points, dr, ground, h, exclusions)
        np.testing.assert_allclose(actual, expected, rtol=3e-7, atol=2e-10)


def test_coincident_positive_radius_shoulder_is_differentiable():
    model, meshes = model_for('shoulder')
    e, pg, de, dp, _, _ = inputs()
    points = np.array([[1., .1, -.1]])
    dr = np.array([[[.1, 0, -.2, .08], [.15, -.1, 0, -.04], [0, .03, .1, -.2]]])
    tangent = VolumeStateTangent(model, meshes, e, pg, de, dp)
    actual = tangent.velocity_columns(points, dr)
    for h in (2e-6, 1e-6):
        np.testing.assert_allclose(actual, stencil(model, meshes, e, pg, de, dp, points, dr, None, h, {}),
                                   rtol=3e-7, atol=2e-9)


def test_coincident_zero_radius_shoulder_rejected_unless_physical_field_excluded():
    model, meshes = model_for('shoulder', zero_shoulder=True)
    e, pg, de, dp, _, _ = inputs()
    points = np.array([[1., .1, -.1]])
    dr = np.ones((1, 3, 4))*.1
    tangent = VolumeStateTangent(model, meshes, e, pg, de, dp)
    with pytest.raises(VolumeDerivativeUnavailable, match='zero-radius shoulder'):
        tangent.velocity_columns(points, dr)
    np.testing.assert_array_equal(tangent.velocity_columns(points, dr, exclude_body=1), 0.)
    ground = GroundPlane(1, position=[0, 0, 1.2])
    tangent = VolumeStateTangent(model, meshes, e, pg, de, dp, ground)
    actual = tangent.velocity_columns(points, dr, exclude_body=1)
    assert np.max(abs(actual)) > 1e-6
    for h in (2e-5, 1e-5):
        np.testing.assert_allclose(actual, stencil(model, meshes, e, pg, de, dp, points, dr, ground, h, {'exclude_body': 1}),
                                   rtol=3e-7, atol=2e-10)


def test_state_columns_are_linear_and_empty_fields_receivers_are_supported():
    e, pg, de, dp, points, dr = inputs()
    model, meshes = model_for('mixed')
    tangent = VolumeStateTangent(model, meshes, e, pg, de, dp)
    coefficients = np.array([.4, -.2, 1.3, .7])
    combined = VolumeStateTangent(model, meshes, e, pg, (de@coefficients)[:, None],
                                  (dp@coefficients)[:, :, None])
    np.testing.assert_allclose(combined.velocity_columns(points, (dr@coefficients)[:, :, None])[:, :, 0],
                               tangent.velocity_columns(points, dr)@coefficients, rtol=2e-13, atol=3e-15)
    assert tangent.velocity_columns(np.empty((0, 3)), np.empty((0, 3, 4))).shape == (0, 3, 4)
    empty, meshes = model_for('empty')
    no_field = VolumeStateTangent(empty, meshes, e, pg, de, dp)
    np.testing.assert_array_equal(no_field.velocity_columns(points, dr), 0.)


@pytest.mark.parametrize('argument', ['direction', 'pg', 'direction_columns', 'pg_columns'])
def test_nonfinite_or_malformed_input_rejected(argument):
    model, meshes = model_for('empty')
    e, pg, de, dp, points, dr = inputs()
    values = dict(direction=e, pg=pg, direction_columns=de, pg_columns=dp)
    values[argument] = values[argument].copy()
    values[argument].flat[0] = np.nan
    with pytest.raises(VolumeDerivativeUnavailable, match='finite'):
        VolumeStateTangent(model, meshes, **values)
    values[argument] = values[argument][..., :-1]
    with pytest.raises(VolumeDerivativeUnavailable):
        VolumeStateTangent(model, meshes, **values)


def test_singular_pg_and_invalid_receiver_columns_rejected():
    model, meshes = model_for('empty')
    e, pg, de, dp, points, dr = inputs()
    with pytest.raises(VolumeDerivativeUnavailable, match='nonsingular'):
        VolumeStateTangent(model, meshes, e, np.zeros((3, 3)), de, dp)
    tangent = VolumeStateTangent(model, meshes, e, pg, de, dp)
    with pytest.raises(VolumeDerivativeUnavailable, match='Receiver columns'):
        tangent.velocity_columns(points, dr[:, :, :3])
    dr[0, 0, 0] = np.inf
    with pytest.raises(VolumeDerivativeUnavailable, match='finite'):
        tangent.velocity_columns(points, dr)


@pytest.mark.parametrize('flag', [-1, 1])
@pytest.mark.parametrize('pair_limit', [4096, 17])
def test_pair_blocks_bound_all_temporaries_without_dropping_sources(monkeypatch, flag, pair_limit):
    import openswing.volume_state_tangent as module
    model, meshes = model_for('mixed')
    e, pg, de, dp, points, dr = inputs()
    points = np.tile(points, (17, 1))[:65]+np.linspace(0, .04, 65)[:, None]
    dr = np.tile(dr, (17, 1, 1))[:65]
    exclusions = dict(exclude_body=np.resize([1, 2, -1], len(points)),
                      exclude_point=np.resize([1, -1, 2, 0], len(points)))
    ground = GroundPlane(flag, position=[0, 0, 1.4], attitude=[8, -14, 3])
    unblocked = VolumeStateTangent(model, meshes, e, pg, de, dp, ground, pair_limit=100000)
    expected = unblocked.velocity_columns(points, dr, **exclusions)
    tangent = VolumeStateTangent(model, meshes, e, pg, de, dp, ground, pair_limit=pair_limit)
    calls = []
    original = module.source_doublet_partials

    def checked(displacement, *args):
        pairs = displacement.shape[0]*displacement.shape[1]
        assert pairs <= pair_limit
        calls.append(pairs)
        return original(displacement, *args)

    monkeypatch.setattr(module, 'source_doublet_partials', checked)
    actual = tangent.velocity_columns(points, dr, **exclusions)
    assert len(calls) > 1
    assert sum(calls) == len(points)*len(tangent.volume.sources)
    if pair_limit >= len(tangent.volume.sources):
        # Receiver-only blocking keeps the exact original summation per row.
        np.testing.assert_array_equal(actual, expected)
    else:
        # Splitting a source sum changes floating-point association only.
        np.testing.assert_allclose(actual, expected, rtol=3e-14, atol=3e-16)
    for h in (2e-5, 1e-5):
        np.testing.assert_allclose(actual, stencil(model, meshes, e, pg, de, dp, points, dr, ground, h, exclusions),
                                   rtol=3e-7, atol=2e-10)


def test_storage_guards_run_before_source_or_receiver_pair_allocation(monkeypatch):
    import openswing.volume_state_tangent as module
    model, meshes = model_for('mixed')
    e, pg, de, dp, points, dr = inputs()

    def forbidden(*args, **kwargs):
        raise AssertionError('A storage guard must reject before this allocation.')

    with monkeypatch.context() as patch:
        patch.setattr(module, 'VolumeField', forbidden)
        with pytest.raises(VolumeDerivativeUnavailable, match='sources exceed the storage budget'):
            VolumeStateTangent(model, meshes, e, pg, de, dp, storage_limit=1)
    original = VolumeStateTangent(model, meshes, e, pg, de, dp)
    budget = original.storage_bytes+8*(len(points)-1)*(24*de.shape[1]+24)
    limited = VolumeStateTangent(model, meshes, e, pg, de, dp, storage_limit=budget)
    with monkeypatch.context() as patch:
        patch.setattr(module, 'source_doublet_partials', forbidden)
        with pytest.raises(VolumeDerivativeUnavailable, match='receiver/output arrays exceed the storage budget'):
            limited.velocity_columns(points, dr)


@pytest.mark.parametrize('options', [{'pair_limit': 0}, {'pair_limit': 2.5},
                                    {'storage_limit': -1}, {'storage_limit': True}])
def test_invalid_storage_options_are_rejected(options):
    model, meshes = model_for('empty')
    e, pg, de, dp, _, _ = inputs()
    with pytest.raises(VolumeDerivativeUnavailable, match='positive integers'):
        VolumeStateTangent(model, meshes, e, pg, de, dp, **options)
