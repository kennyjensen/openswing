"""Shared wakes preserve physics while contracting circulation before cancellation.

The Decimal control is an independent planar Biot--Savart calculation. Other
controls compare wiring/core/image semantics with the original horseshoes;
they do not certify geometry derivatives or complete solver integration.
"""
from decimal import Decimal, localcontext
import math
import weakref

import numpy as np
import pytest

from openswing.aero import horseshoe_velocity
from openswing.factored_influence import FactoredInfluence
from openswing.ground import GroundPlane
from openswing.tangent_influences import TangentInfluences


def pg_stretch(direction, mach):
    direction = np.asarray(direction, dtype=float)
    direction /= np.linalg.norm(direction)
    return np.eye(3) + (1 / math.sqrt(1 - mach**2) - 1) * np.outer(direction, direction)


@pytest.fixture
def geometry():
    points = np.array([[.5, .125, .375], [-.5, -.25, .5], [1., .75, -.25]])
    a = np.array([[-.25, -.5, .125], [.125, .25, -.125], [.5, -.75, -.25]])
    b = np.array([[.125, .25, -.125], [.25, .75, .125], [.75, .625, .125]])
    direction = np.array([1., .25, -.125])
    return points, a, b, direction, pg_stretch(direction.copy(), .43)


def expanded(points, a, b, direction, pg, core=0., ground=None, mask=None):
    return horseshoe_velocity(points[:, None], a[None], b[None], direction, pg,
                              core, ground, exclude_bound=mask)


def assert_close(actual, expected):
    np.testing.assert_allclose(actual, expected, atol=3e-13, rtol=3e-12)


@pytest.mark.parametrize('panels', [32, 200])
@pytest.mark.parametrize('alpha', [-5., 5.])
@pytest.mark.parametrize('core', [0., .0635])
def test_cosine_wing_images_cancel_induced_ground_normal_flow(panels, alpha, core):
    # SA-12 planform and closest quarter-chord height. At zero Euler pitch,
    # an oblique real wake needs an oppositely tilted image wake. Test the
    # physical boundary itself, independently of any archived coefficients.
    nodes = -.762 * np.cos(np.linspace(0., np.pi, panels + 1))
    a = np.column_stack((np.zeros(panels), nodes[:-1], np.zeros(panels)))
    b = np.column_stack((np.zeros(panels), nodes[1:], np.zeros(panels)))
    midpoint = .5 * (nodes[:-1] + nodes[1:])
    gamma = 4 * np.sqrt(1 - (midpoint / .762)**2)
    ground = GroundPlane(1, position=(0, 0, .127))
    angle = math.radians(alpha)
    direction = np.array([math.cos(angle), 0., math.sin(angle)])
    points = np.array([[x, y, -.127] for x in (-.5, 0., .5)
                       for y in (-.5, 0., .5)])
    operator = FactoredInfluence(points, a, b, direction, np.eye(3), core, ground)
    actual = operator.apply(gamma)
    np.testing.assert_allclose(actual @ ground.normal, 0., rtol=0., atol=2e-13)

    direct = expanded(points, a, b, direction, np.eye(3), core, ground)
    assert_close(actual, np.einsum('ijk,j->ik', direct, gamma))

    # An endpoint-only reflection can match SA-12's archived coefficients,
    # yet violates impermeability. Ensure this fixture detects that specific
    # regression in the optimized field, for both zero and finite cores.
    wrong = (expanded(points, a, b, direction, np.eye(3), core)
             - expanded(points, ground.reflect_points(a), ground.reflect_points(b),
                        direction, np.eye(3), core))
    penetration = np.einsum('ijk,j->ik', wrong, gamma) @ ground.normal
    assert np.max(abs(penetration)) > .01


@pytest.mark.parametrize('ground_flag', [0, 1, -1])
@pytest.mark.parametrize('different_cores', [False, True])
def test_nonuniform_circulation_columns_and_projection(geometry, ground_flag, different_cores):
    points, a, b, direction, pg = geometry
    core = np.full((3, 3), .03125)
    if different_cores:
        # Core is receiver-dependent: same physical index gives zero; another
        # index sees that source's radius. A shared position need not merge.
        receiver_ids = np.array([1, 2, 1])
        source_ids = np.array([1, 2, 2])
        core = np.where(receiver_ids[:, None] == source_ids[None], 0.,
                        np.array([.03125, .0625, .0625])[None])
    ground = GroundPlane(ground_flag, position=(0, 0, 2), normal=(.125, .25, 1))
    mask = np.eye(3, dtype=bool)
    operator = FactoredInfluence(points, a, b, direction, pg, core, ground,
                                 exclude_bound=mask)
    reference = expanded(points, a, b, direction, pg, core, ground, mask)
    gamma = np.array([.75, -1.25, .375])
    columns = np.array([[1., .25], [.125, -1.], [-.25, .5]])
    normals = np.array([[.25, -.5, 1.], [.125, 1., .25], [1., -.375, .5]])
    assert operator.shape == (3, 3, 3)
    assert operator.nbytes > 0
    assert_close(operator.matrix(), reference)
    assert_close(operator.apply(gamma), np.einsum('ijk,j->ik', reference, gamma))
    assert_close(operator.apply_columns(columns), np.einsum('ijk,jl->ikl', reference, columns))
    assert_close(operator.project(normals), np.einsum('ijk,ik->ij', reference, normals))
    scalar = operator.projected(normals)
    assert_close(scalar.apply(gamma), np.einsum('ik,ik->i', operator.apply(gamma), normals))
    assert_close(scalar.apply(gamma), np.einsum('ijk,j,ik->i', reference, gamma, normals))
    # The dense accessors associate the three signed terms differently.
    rounding = 4*np.finfo(float).eps
    np.testing.assert_allclose(scalar.matrix(), operator.project(normals),
                               atol=rounding, rtol=rounding)
    if different_cores:
        incorrect = core.copy()
        incorrect[:, 1] = incorrect[:, 0]
        wrong = expanded(points, a, b, direction, pg, incorrect, ground, mask)
        assert np.max(abs(reference - wrong)) > 1e-6  # This fixture detects wrong grouping.


def planar_decimal_velocity(a_y, b_y, gamma, receiver_y, *, exclude_bound=None):
    """Independent scalar formula: bound lines at x=0, rays along +x, x_cp=1."""
    with localcontext() as context:
        context.prec = 100
        decimal = lambda x: Decimal.from_float(float(x))
        pi = Decimal('3.1415926535897932384626433832795028841971693993751058209749445923078164062862089986280348253421170679')
        x, y = Decimal(1), decimal(receiver_y)

        def bound(lo, hi):
            z0, z1 = y - decimal(lo), y - decimal(hi)
            return -(z0 / (x*x + z0*z0).sqrt() - z1 / (x*x + z1*z1).sqrt()) / (4*pi*x)

        def ray(origin):
            d = y - decimal(origin)
            return (1 + x / (x*x + d*d).sqrt()) / (4*pi*d)

        excluded = [False]*len(gamma) if exclude_bound is None else exclude_bound
        total = sum(decimal(g) * ((0 if masked else bound(lo, hi)) + ray(hi) - ray(lo))
                    for lo, hi, g, masked in zip(a_y, b_y, gamma, excluded))
        return np.array([[0., 0., float(total)]])


@pytest.mark.parametrize('jump', [0., 2.**-30, -2.**-30])
def test_shared_wake_cancellation_against_decimal_reference(jump):
    a = np.array([[0., -1., 0.], [0., 0., 0.]])
    b = np.array([[0., 0., 0.], [0., 1., 0.]])
    gamma = np.array([1., 1. + jump])
    y = 2.**-30
    operator = FactoredInfluence(np.array([[1., y, 0.]]), a, b, [1., 0., 0.], np.eye(3))
    expected = planar_decimal_velocity(a[:, 1], b[:, 1], gamma, y)
    # Expanded per-horseshoe contraction loses roughly 1e-8 in the positive
    # jump fixture. The assertion is against Decimal, not that unstable path.
    np.testing.assert_allclose(operator.apply(gamma), expected, atol=2e-15, rtol=2e-15)
    scalar = operator.projected(np.array([[0., 0., 1.]]))
    np.testing.assert_allclose(scalar.apply(gamma), expected[:, 2], atol=2e-15, rtol=2e-15)


def test_coincident_endpoint_with_different_core_is_not_cancelled():
    a = np.array([[0., -1., 0.], [0., 0., 0.]])
    b = np.array([[0., 0., 0.], [0., 1., 0.]])
    points = np.array([[1., .03125, .015625], [.5, -.125, .0625]])
    core = np.array([[0., .125], [.0625, 0.]])
    operator = FactoredInfluence(points, a, b, [1., 0., 0.], np.eye(3), core)
    reference = expanded(points, a, b, np.array([1., 0., 0.]), np.eye(3), core)
    gamma = np.ones(2)
    assert_close(operator.apply(gamma), reference.sum(axis=1))
    wrong = FactoredInfluence(points, a, b, [1., 0., 0.], np.eye(3), 0.).apply(gamma)
    assert np.max(abs(operator.apply(gamma) - wrong)) > 1e-2


def test_nearby_endpoints_are_not_merged():
    a = np.array([[0., -1., 0.], [0., 2.**-30, 0.]])
    b = np.array([[0., 0., 0.], [0., 1., 0.]])
    points = np.array([[1., 2.**-20, 0.]])
    operator = FactoredInfluence(points, a, b, [1., 0., 0.], np.eye(3))
    expected = planar_decimal_velocity(a[:, 1], b[:, 1], np.ones(2), points[0, 1])
    # These distinct rays still require cancellation; no universal precision
    # claim is made. A tolerance-based merge would instead err by about 160.
    np.testing.assert_allclose(operator.apply(np.ones(2)), expected, atol=2e-8, rtol=1e-12)
    merged = a.copy()
    merged[1, 1] = 0.
    wrong = FactoredInfluence(points, merged, b, [1., 0., 0.], np.eye(3)).apply(np.ones(2))
    assert np.max(abs(operator.apply(np.ones(2)) - wrong)) > 100.


def test_branch_incidence_retains_small_remainder(geometry):
    points, _, _, direction, pg = geometry
    a = np.array([[0., -1., 0.], [0., 0., -1.], [0., 1., 0.]])
    b = np.zeros((3, 3))
    operator = FactoredInfluence(points, a, b, direction, pg)
    strengths = operator.wake_strengths(np.array([2.**54, 1., -2.**54]))
    # Three incoming rays share the origin. Ordinary sequential accumulation
    # can erase its +1 circulation remainder; outgoing strengths are separate.
    np.testing.assert_array_equal(np.sort(strengths), np.sort([-2.**54, -1., 2.**54, 1.]))


@pytest.mark.parametrize('mach', [0., 22/340.21, .6])
def test_own_bound_exclusion_keeps_both_wakes(mach):
    pg = pg_stretch([1., 0., 0.], mach)
    a, b = np.array([[0., -1., 0.]]), np.array([[0., 1., 0.]])
    operator = FactoredInfluence(np.zeros((1, 3)), a, b, [1., 0., 0.], pg,
                                 exclude_bound=np.ones((1, 1), dtype=bool))
    np.testing.assert_allclose(operator.apply(np.ones(1)), [[0., 0., -1/(2*math.pi)]],
                               atol=2e-15, rtol=2e-15)


@pytest.mark.parametrize('flag', [-1, 1])
def test_real_bound_exclusion_does_not_remove_image_bounds(geometry, flag):
    points, a, b, direction, pg = geometry
    core, mask = .03125, np.eye(3, dtype=bool)
    ground = GroundPlane(flag, position=(0, 0, 2), normal=(.125, .25, 1))
    operator = FactoredInfluence(points, a, b, direction, pg, core, ground, exclude_bound=mask)
    real = expanded(points, a, b, direction, pg, core, mask=mask)
    image = expanded(points, ground.reflect_points(a), ground.reflect_points(b),
                     ground.reflect_vectors(direction), pg, core)
    assert_close(operator.matrix(), real - flag*image)
    masked_image = expanded(points, ground.reflect_points(a), ground.reflect_points(b),
                            ground.reflect_vectors(direction), pg, core, mask=mask)
    assert np.max(abs(operator.matrix() - (real - flag*masked_image))) > 1e-5


def test_orientation_and_source_receiver_permutations(geometry):
    points, a, b, direction, pg = geometry
    gamma = np.array([.75, -1.25, .375])
    original = FactoredInfluence(points, a, b, direction, pg, .03125)
    reversed_ = FactoredInfluence(points, b, a, direction, pg, .03125)
    assert_close(reversed_.apply(-gamma), original.apply(gamma))
    sources, receivers = np.array([2, 0, 1]), np.array([1, 2, 0])
    permuted = FactoredInfluence(points[receivers], a[sources], b[sources], direction, pg, .03125)
    assert_close(permuted.apply(gamma[sources]), original.apply(gamma)[receivers])


def test_pg_rigid_translation_rotation_and_unit_covariance(geometry):
    points, a, b, direction, pg = geometry
    gamma = np.array([.75, -1.25, .375])
    core = .03125
    base = FactoredInfluence(points, a, b, direction, pg, core).apply(gamma)
    shift = np.array([2.**20, -2.**21, 2.**19])
    moved = FactoredInfluence(points + shift, a + shift, b + shift, direction, pg, core)
    np.testing.assert_array_equal(moved.apply(gamma), base)
    transformed = FactoredInfluence(points@pg.T, a@pg.T, b@pg.T, direction@pg.T, np.eye(3), core)
    assert_close(transformed.apply(gamma)@pg, base)
    axis = np.array([1., 2., -1.]); axis /= np.linalg.norm(axis)
    cross = np.array([[0., -axis[2], axis[1]], [axis[2], 0., -axis[0]], [-axis[1], axis[0], 0.]])
    rotation = np.eye(3) + math.sin(.71)*cross + (1 - math.cos(.71))*(cross@cross)
    rotated = FactoredInfluence(points@rotation.T, a@rotation.T, b@rotation.T,
                                direction@rotation.T, rotation@pg@rotation.T, core)
    assert_close(rotated.apply(gamma), base@rotation.T)
    ground = GroundPlane(1, position=(0, 0, 2), normal=(.125, .25, 1))
    rotated_ground = GroundPlane(1, position=ground.position@rotation.T,
                                 normal=ground.normal@rotation.T)
    with_ground = FactoredInfluence(points, a, b, direction, pg, core, ground)
    rotated = FactoredInfluence(points@rotation.T, a@rotation.T, b@rotation.T,
                                direction@rotation.T, rotation@pg@rotation.T, core, rotated_ground)
    assert_close(rotated.apply(gamma), with_ground.apply(gamma)@rotation.T)
    for length in (.25, 8.):
        scaled = FactoredInfluence(length*points, length*a, length*b, direction, pg, length*core)
        assert_close(scaled.apply(gamma), base/length)
        assert_close(scaled.apply(length**2/3*gamma), length/3*base)


def test_circulation_derivative_is_linear_and_accepts_empty_columns(geometry):
    points, a, b, direction, pg = geometry
    operator = FactoredInfluence(points, a, b, direction, pg, .03125)
    gamma = np.array([.75, -1.25, .375])
    delta = np.array([1., .125, -.25])
    expected = operator.apply_columns(delta[:, None])[:, :, 0]
    step = 2.**-10
    finite_difference = (operator.apply(gamma + step*delta) - operator.apply(gamma - step*delta))/(2*step)
    np.testing.assert_allclose(finite_difference, expected, atol=2e-12, rtol=2e-11)
    assert operator.apply_columns(np.empty((3, 0))).shape == (3, 3, 0)


@pytest.mark.parametrize('receivers,sources', [(0, 3), (3, 0), (0, 0)])
def test_empty_receiver_and_source_contracts(receivers, sources):
    points = np.zeros((receivers, 3))
    a = np.zeros((sources, 3))
    a[:, 1] = np.arange(sources)
    b = a + [0., 1., 0.]
    direction, pg = np.array([1., 0., 0.]), np.eye(3)
    mask = np.zeros((receivers, sources), dtype=bool)
    direct = FactoredInfluence(points, a, b, direction, pg, exclude_bound=mask)
    cached = TangentInfluences().factored_vortex('empty', points, a, b, direction, pg,
                                                0., None, mask)
    for operator in (direct, cached):
        assert operator.shape == (receivers, sources, 3)
        np.testing.assert_array_equal(operator.matrix(), np.zeros(operator.shape))
        np.testing.assert_array_equal(operator.apply(np.ones(sources)), np.zeros((receivers, 3)))
        np.testing.assert_array_equal(operator.apply_columns(np.ones((sources, 2))),
                                      np.zeros((receivers, 3, 2)))
        np.testing.assert_array_equal(operator.project(np.zeros((receivers, 3))),
                                      np.zeros((receivers, sources)))
        scalar = operator.projected(np.zeros((receivers, 3)))
        np.testing.assert_array_equal(scalar.matrix(), np.zeros((receivers, sources)))
        np.testing.assert_array_equal(scalar.apply(np.ones(sources)), np.zeros(receivers))
        assert operator.apply_columns(np.empty((sources, 0))).shape == (receivers, 3, 0)
        if not sources:
            assert operator.wake_strengths(np.empty(0)).shape == (0,)


def test_operator_owns_inputs_and_returned_arrays(geometry):
    points, a, b, direction, pg = geometry
    core = np.full((3, 3), .03125)
    mask = np.eye(3, dtype=bool)
    gamma = np.array([.75, -1.25, .375])
    columns, normals = np.eye(3), np.eye(3)
    inputs = [points, a, b, direction, pg, core, mask, gamma, columns, normals]
    copies = [v.copy() for v in inputs]
    operator = FactoredInfluence(points, a, b, direction, pg, core, exclude_bound=mask)
    expected = operator.apply(gamma).copy()
    memory = operator.nbytes
    for value in [operator.matrix(), operator.project(normals), operator.apply(gamma),
                  operator.apply_columns(columns), operator.wake_strengths(gamma)]:
        if value.flags.writeable:
            value[...] = np.nan
    for actual, original in zip(inputs, copies):
        np.testing.assert_array_equal(actual, original)
    np.testing.assert_array_equal(operator.apply(gamma), expected)
    # A cached operator is a snapshot. Mutating caller storage cannot silently
    # change its grouping, geometry or pair-core semantics.
    for value in [points, a, b, direction, pg, core]:
        value[...] = 123.
    mask[...] = False
    np.testing.assert_array_equal(operator.apply(gamma), expected)
    assert operator.nbytes == memory


def test_projected_operator_owns_scalar_coefficients_without_retaining_vector_fields(geometry):
    points, a, b, direction, pg = geometry
    normals = np.array([[.25, -.5, 1.], [.125, 1., .25], [1., -.375, .5]])
    gamma = np.array([.75, -1.25, .375])
    gamma_before = gamma.copy()
    operator = FactoredInfluence(points, a, b, direction, pg, .03125)
    scalar = operator.projected(normals)
    expected = np.einsum('ik,ik->i', operator.apply(gamma), normals)
    expected_matrix = scalar.matrix()
    rounding = 4*np.finfo(float).eps
    np.testing.assert_allclose(expected_matrix, operator.project(normals),
                               atol=rounding, rtol=rounding)
    memory = scalar.nbytes
    assert scalar.bound.ndim == 2 and scalar.rays.ndim == 2
    assert scalar.bound.nbytes + scalar.rays.nbytes <= memory < operator.nbytes
    parent = weakref.ref(operator)
    del operator
    assert parent() is None  # Keeping scalar residuals must not retain the vector tensors.
    normals[:] = np.nan
    for _ in range(2):
        assert_close(scalar.apply(gamma), expected)
        np.testing.assert_array_equal(scalar.matrix(), expected_matrix)
        scalar.apply(gamma)[:] = np.nan
        scalar.matrix()[:] = np.nan
    np.testing.assert_array_equal(gamma, gamma_before)
    assert scalar.nbytes == memory
    for coefficients in (scalar.bound, scalar.rays):
        assert not coefficients.flags.writeable
        with pytest.raises(ValueError):
            coefficients.flat[0] = 0.


def cache_geometry(receivers, sources):
    rng = np.random.default_rng(16015)
    nodes = rng.normal(size=(sources + 1, 3))
    points = rng.normal(size=(receivers, 3))
    direction = np.array([1., .125, -.0625])
    return (points, nodes[:-1].copy(), nodes[1:].copy(), direction,
            pg_stretch(direction.copy(), .43), np.full((receivers, sources), .03125),
            np.eye(receivers, sources, dtype=bool))


@pytest.mark.parametrize('shape', [(9, 12), (1, 12), (12, 1)])
@pytest.mark.parametrize('flag', [0, 1, -1])
def test_factored_pair_cache_matches_fresh_after_local_changes(shape, flag):
    points, a, b, direction, pg, core, mask = cache_geometry(*shape)
    ground = GroundPlane(flag, position=(0, 0, 10), normal=(.125, .25, 1))
    cache = TangentInfluences()
    gamma = np.linspace(-.75, 1.25, shape[1])
    columns = np.column_stack([gamma, gamma[::-1]])
    normals = np.tile([0., 0., 1.], (shape[0], 1))
    changes = ['base', 'receiver', 'a_split', 'b_split', 'core_split', 'exclude',
               'receiver_and_source', 'all', 'base_merged']
    if shape[1] > 1:
        changes.insert(-1, 'incidence_same_ray_positions')
    for change in changes:
        pp, aa, bb, cc, mm = [v.copy() for v in (points, a, b, core, mask)]
        if change in ['receiver', 'receiver_and_source']:
            pp[2 % shape[0], 0] += .001
        if change in ['a_split', 'receiver_and_source']:
            aa[5 % shape[1], 2] += .001
        if change == 'b_split':
            bb[7 % shape[1], 1] -= .001
        if change == 'core_split':
            cc[3 % shape[0], 4 % shape[1]] += .015625
        if change == 'exclude':
            mm[1 % shape[0], 2 % shape[1]] = ~mm[1 % shape[0], 2 % shape[1]]
        if change == 'incidence_same_ray_positions':
            # The unique ray positions stay present; only source ownership
            # changes. Cached coefficients cannot retain old incidence.
            aa[1] = aa[0]
        if change == 'all':
            pp += .001
            aa -= .001
        cached = cache.factored_vortex('field', pp, aa, bb, direction, pg, cc, ground, mm)
        fresh = FactoredInfluence(pp, aa, bb, direction, pg, cc, ground, exclude_bound=mm)
        np.testing.assert_array_equal(cached.matrix(), fresh.matrix(), err_msg=change)
        np.testing.assert_array_equal(cached.apply(gamma), fresh.apply(gamma), err_msg=change)
        np.testing.assert_array_equal(cached.apply_columns(columns), fresh.apply_columns(columns), err_msg=change)
        np.testing.assert_array_equal(cached.project(normals), fresh.project(normals), err_msg=change)
        assert not cached.bound.flags.writeable and not cached.rays.flags.writeable


@pytest.mark.parametrize('flag', [0, 1, -1])
def test_unchanged_factored_pairs_reuse_kernels_and_own_cached_storage(flag, monkeypatch):
    import openswing.aero as aero

    points, a, b, direction, pg, core, mask = cache_geometry(9, 12)
    ground = GroundPlane(flag, position=(0, 0, 10), normal=(.125, .25, 1))
    cache = TangentInfluences()
    operator = cache.factored_vortex('field', points, a, b, direction, pg, core, ground, mask)
    gamma = np.linspace(-.75, 1.25, len(a))
    expected = operator.apply(gamma).copy()
    saved_inputs = [v.copy() for v in (points, a, b, direction, pg, core, mask)]
    for array in [points, a, b, direction, pg, core]:
        array[...] = 123.
    mask[...] = False

    def unexpected(*args, **kwargs):
        pytest.fail('Unchanged factored pairs repeated a finite/ray kernel evaluation')

    monkeypatch.setattr(aero, 'finite_vortex', unexpected)
    monkeypatch.setattr(aero, 'semi_infinite_vortex', unexpected)
    monkeypatch.setattr(FactoredInfluence, '__init__', unexpected)
    for _ in range(2):
        pp, aa, bb, ee, PP, cc, mm = [v.copy() for v in saved_inputs]
        replay = cache.factored_vortex('field', pp, aa, bb, ee, PP, cc, ground, mm)
        assert replay is operator
        np.testing.assert_array_equal(replay.apply(gamma), expected)
        assert not replay.bound.flags.writeable and not replay.rays.flags.writeable
        replay.apply(gamma)[:] = np.nan
        replay.matrix()[:] = np.nan
        np.testing.assert_array_equal(operator.apply(gamma), expected)


@pytest.mark.parametrize('change', ['wake', 'pg', 'ground', 'shape', 'mask_presence',
                                  'ground_reflection', 'ground_normal', 'ground_offset',
                                  'ground_off', 'dtype', 'signed_zero'])
def test_factored_pair_cache_invalidates_changed_global_inputs(change):
    points, a, b, direction, pg, core, mask = cache_geometry(9, 12)
    ground = GroundPlane(1, position=(0, 0, 10), normal=(.125, .25, 1))
    cache = TangentInfluences()
    if change == 'signed_zero':
        direction[1] = 0.
    original = cache.factored_vortex('field', points, a, b, direction, pg, core, ground, mask)
    if change == 'wake':
        direction[2] += .02
    if change == 'pg':
        pg[0, 0] += .02
    if change == 'ground':
        ground = GroundPlane(-1, position=(0, 0, 11), normal=(.25, .125, 1))
    if change == 'shape':
        points, core, mask = points[:5], core[:5], mask[:5]
    if change == 'mask_presence':
        mask = None
    if change == 'ground_reflection':
        ground.reflection[0, 1] += .01
    if change == 'ground_normal':
        ground.normal[1] += .01
    if change == 'ground_offset':
        ground.offset += .01
    if change == 'ground_off':
        ground.flag = 0
    if change == 'dtype':
        points = points.astype(np.float32)
    if change == 'signed_zero':
        direction[1] = -0.
    cached = cache.factored_vortex('field', points, a, b, direction, pg, core, ground, mask)
    assert cached is not original
    fresh = FactoredInfluence(points, a, b, direction, pg, core, ground, exclude_bound=mask)
    np.testing.assert_array_equal(cached.matrix(), fresh.matrix())
    np.testing.assert_array_equal(cached.apply(np.ones(len(a))), fresh.apply(np.ones(len(a))))


def test_factored_operator_budget_exhaustion_and_query_isolation():
    points, a, b, direction, pg, core, mask = cache_geometry(9, 12)
    cache = TangentInfluences()
    original = cache.factored_vortex('first', points, a, b, direction, pg, core, None, mask)
    size = cache.bytes
    for _ in range(3):
        assert cache.factored_vortex('first', points, a, b, direction, pg, core, None, mask) is original
        assert cache.bytes == size
    other = cache.factored_vortex('second', points, a, b, direction, pg, core, None, mask)
    assert other is not original
    other.assert_equal(original)
    cache.bytes = 64*1024**2
    for _ in range(2):
        uncached = cache.factored_vortex('full', points, a, b, direction, pg, core, None, mask)
        uncached.assert_equal(original)
        assert 'full' not in cache.factored_operators
        assert cache.bytes == 64*1024**2
    # Invalid geometry must still raise after a valid entry was retained.
    points[0, 0] = np.nan
    with pytest.raises(ValueError):
        cache.factored_vortex('first', points, a, b, direction, pg, core, None, mask)


@pytest.mark.parametrize('flag', [0, 1, -1])
@pytest.mark.parametrize('layout', ['fortran', 'strided', 'negative_stride'])
def test_changed_memory_layout_preserves_fresh_kernel_rounding(flag, layout):
    points, a, b, direction, pg, core, mask = cache_geometry(9, 12)
    ground = GroundPlane(flag, position=(0, 0, 10), attitude=(5, 4, 3))
    cache = TangentInfluences()
    original = cache.factored_vortex('layout', points, a, b, direction, pg, core, ground, mask)
    changed = []
    for value in (points, a, b, direction, pg, core, mask):
        if layout == 'fortran':
            other = np.asfortranarray(value)
        elif layout == 'strided':
            storage = np.empty(value.shape[:-1]+(2*value.shape[-1],), dtype=value.dtype)
            other = storage[..., ::2]
            other[:] = value
        else:
            other = value[..., ::-1].copy()[..., ::-1]
        changed.append(other)
    pp, aa, bb, dd, PP, cc, mm = changed
    fresh = FactoredInfluence(pp, aa, bb, dd, PP, cc, ground, exclude_bound=mm)
    actual = cache.factored_vortex('layout', pp, aa, bb, dd, PP, cc, ground, mm)
    actual.assert_equal(fresh)
    assert actual is not original
    assert cache.factored_vortex('layout', points, a, b, direction, pg, core, ground, mask) is original


@pytest.mark.parametrize('jump', [0., 2.**-30, -2.**-30])
def test_complex_shared_wake_columns_against_independent_decimal(jump):
    a = np.array([[0., -1., 0.], [0., 0., 0.]])
    b = np.array([[0., 0., 0.], [0., 1., 0.]])
    points = np.array([[1., 2.**-30, 0.], [1., -2.**-30, 0.], [1., .125, 0.]])
    operator = FactoredInfluence(points, a, b, [1., 0., 0.], np.eye(3))
    gamma = np.array([1., 1.+jump]) + 1j*np.array([.75, .75-jump])
    # Noncontiguous complex columns catch layout, conjugation and discarded
    # imaginary-part errors. Every reference is an independent Decimal sum.
    storage = np.empty((2, 8), dtype=complex)
    columns = storage[:, ::2]
    columns[:] = np.column_stack([gamma, 1j*gamma, -gamma.conj(), gamma.real])
    expected = np.empty((len(points), 3, columns.shape[1]), dtype=complex)
    for k, column in enumerate(columns.T):
        for i, point in enumerate(points):
            expected[i, :, k] = (
                planar_decimal_velocity(a[:, 1], b[:, 1], column.real, point[1])[0]
                + 1j*planar_decimal_velocity(a[:, 1], b[:, 1], column.imag, point[1])[0])
    np.testing.assert_allclose(operator.apply_columns(columns), expected, atol=2e-15, rtol=2e-15)
    normals = np.tile([0., 0., 1.], (len(points), 1))
    for k, column in enumerate(columns.T):
        np.testing.assert_allclose(operator.apply(column), expected[:, :, k], atol=2e-15, rtol=2e-15)
        np.testing.assert_allclose(operator.projected(normals).apply(column), expected[:, 2, k], atol=2e-15, rtol=2e-15)
    empty = operator.apply_columns(np.empty((2, 0), dtype=complex))
    assert empty.shape == (len(points), 3, 0) and np.iscomplexobj(empty)


@pytest.mark.parametrize('count', [32, 256])
@pytest.mark.parametrize('alternating', [False, True])
def test_long_chain_contraction_against_decimal(count, alternating):
    nodes = np.column_stack([np.zeros(count+1), np.linspace(-1., 1., count+1), np.zeros(count+1)])
    gamma = np.ones(count)
    if alternating:gamma += np.where(np.arange(count) % 2, 2.**-30, -2.**-30)
    points = np.array([[1., 2.**-30, 0.]])
    operator = FactoredInfluence(points, nodes[:-1], nodes[1:], [1., 0., 0.], np.eye(3))
    expected = planar_decimal_velocity(nodes[:-1, 1], nodes[1:, 1], gamma, points[0, 1])
    np.testing.assert_allclose(operator.apply(gamma), expected, atol=2e-15, rtol=2e-15)
    np.testing.assert_allclose(operator.apply_columns(gamma[:, None])[:, :, 0], expected,
                               atol=2e-15, rtol=2e-15)
    np.testing.assert_allclose(operator.projected([[0., 0., 1.]]).apply(gamma), expected[:, 2],
                               atol=2e-15, rtol=2e-15)


def test_complex_branch_remainder_survives_large_incident_strengths():
    # Parallel edges make both endpoint groups have three signed terms.
    # Excluding the real bounds isolates the compensated wake contraction;
    # this does not claim compensated accuracy for arbitrary bound sums.
    a = np.tile([0., -1., 0.], (3, 1)); b = np.zeros((3, 3))
    points = np.array([[1., 2.**-30, 0.]])
    gamma = np.array([2.**54*(1+1j), 1+.5j, -2.**54*(1+1j)])
    operator = FactoredInfluence(points, a, b, [1., 0., 0.], np.eye(3),
                                 exclude_bound=np.ones((1, 3), dtype=bool))
    expected = (planar_decimal_velocity(a[:, 1], b[:, 1], gamma.real, points[0, 1], exclude_bound=[True]*3)
                + 1j*planar_decimal_velocity(a[:, 1], b[:, 1], gamma.imag, points[0, 1], exclude_bound=[True]*3))
    np.testing.assert_array_equal(operator.wake_strengths(gamma), [-1-.5j, 1+.5j])
    np.testing.assert_allclose(operator.apply(gamma), expected, atol=2e-15, rtol=2e-15)
    actual = operator.apply_columns(np.column_stack([gamma, 1j*gamma]))
    np.testing.assert_allclose(actual, np.stack([expected, 1j*expected], axis=-1), atol=2e-15, rtol=2e-15)


def test_packed_coefficients_share_cache_storage_and_keep_old_operator():
    points, a, b, direction, pg, core, mask = cache_geometry(9, 12)
    cache = TangentInfluences(); gamma = np.linspace(-.75, 1.25, len(a))
    operator = cache.factored_vortex('packed', points, a, b, direction, pg, core, None, mask)
    expected = operator.apply(gamma).copy()
    for name, matrix in [('bound', operator._bound_matrix), ('rays', operator._ray_matrix)]:
        tensor = getattr(operator, name)
        cached = cache.factored_entries['packed', name][2]
        assert matrix.flags.c_contiguous
        assert np.shares_memory(tensor, matrix) and np.shares_memory(tensor, cached)
        assert not matrix.flags.writeable and not tensor.flags.writeable and not cached.flags.writeable
        with pytest.raises(ValueError):tensor.flat[0] = 0.
    assert operator.nbytes == operator.bound.nbytes + operator.rays.nbytes + operator.endpoint_grouping().nbytes
    # A partial cache update allocates its own changed field and leaves the
    # previously captured operator and baseline pair cache unchanged.
    changed = points.copy(); changed[2, 0] += .001
    updated = cache.factored_vortex('packed', changed, a, b, direction, pg, core, None, mask)
    fresh = FactoredInfluence(changed, a, b, direction, pg, core, exclude_bound=mask)
    np.testing.assert_array_equal(updated.apply(gamma), fresh.apply(gamma))
    np.testing.assert_array_equal(operator.apply(gamma), expected)
    assert not np.shares_memory(updated.bound, operator.bound)
    assert not np.shares_memory(updated.rays, operator.rays)
    for name in ['bound', 'rays']:
        np.testing.assert_array_equal(cache.factored_entries['packed', name][2], getattr(operator, name))
