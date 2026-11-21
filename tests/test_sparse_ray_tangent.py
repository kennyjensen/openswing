"""Exact-zero wake pruning against the retained dense derivative formula.

The production geometry-direction API is real. Complex linear combinations
are tested through separate real/imaginary applications, not an expanded API.
"""
from copy import copy
from types import MethodType
import numpy as np
import pytest
from openswing.ground import GroundPlane
from openswing.vortex_tangent import VortexFieldTangent, VortexDerivativeUnavailable


# Frozen05 retained dense arithmetic oracle, embedded for portable regressions.
def _dense_ray_change(self, sources, da, db, dc):
        """Combine source-owned motion weights before large ray derivatives."""
        starts = np.zeros_like(self.a); ends = np.zeros_like(self.b)
        starts[sources] = self.gamma[sources, None]*da
        ends[sources] = self.gamma[sources, None]*db
        motion = self.grouping.group_endpoint_weights(starts, ends)
        cores = np.zeros((len(self.gamma), len(self.points)))
        cores[sources] = self.gamma[sources, None]*dc.T
        radii = self.grouping.group_endpoint_weights(cores, cores).T
        return (np.einsum('ijab,jb->ia', self.ray_origin, motion)
                + np.einsum('ija,ij->ia', self.ray_radius, radii))


def _dense_source_columns(self, sources, da, db, dc, *, core_active):
        """Apply source-owned geometry columns, including grouped wake rays.

        Endpoint directions have shape (selected sources, 3, columns); core
        directions have shape (selected sources, columns). ``core_active``
        retains each receiver's physical-index exclusion. Columns share the
        bound contraction, while ray motion is grouped one column at a time:
        this avoids retaining a receiver × source × column core tensor.
        Receiver motion is separate and uses ``receiver``.
        """
        sources = np.asarray(sources)
        da, db, dc = [np.asarray(v, dtype=float) for v in (da, db, dc)]
        active = np.asarray(core_active, dtype=bool)
        if (sources.ndim != 1 or not np.issubdtype(sources.dtype, np.integer)
                or np.any((sources < 0) | (sources >= len(self.gamma)))
                or np.any(np.diff(sources) <= 0)
                or da.ndim != 3 or da.shape[:2] != (len(sources), 3)
                or db.shape != da.shape or not 0 < da.shape[-1] <= 32
                or dc.shape != (len(sources), da.shape[-1])
                or active.shape != (len(self.points), len(sources))):
            raise VortexDerivativeUnavailable('Invalid retained vortex source-column layout.')
        if not all(np.all(np.isfinite(v)) for v in (da, db, dc)):
            raise VortexDerivativeUnavailable('Nonfinite retained vortex source columns.')
        result = np.zeros((len(self.points), 3, da.shape[-1]))
        if not len(sources):return result
        result += np.einsum('ijab,jbk->iak', self.source_a[:, sources], da)
        result += np.einsum('ijab,jbk->iak', self.source_b[:, sources], db)
        result += np.einsum('ija,jk->iak', self.radius[:, sources]*active[:, :, None], dc)
        for k in range(da.shape[-1]):
            result[:, :, k] += self._ray_change(sources, da[:, :, k], db[:, :, k],
                np.where(active, dc[None, :, k], 0.))
        return result

def dense(tangent):
    result = copy(tangent)
    result._ray_change = MethodType(_dense_ray_change, result)
    result.source_columns = MethodType(_dense_source_columns, result)
    return result


def fixture(flag=0, core_kind='shared'):
    points = np.array([[.41, .23, 2.4], [.71, -.18, 2.8], [-.2, .61, 3.2]])
    a = np.array([[0., 0., 0.]]*4 + [[-1., -2., 0.], [-1., -1., 0.], [0., 0., 0.], [0., 0., 0.]])
    b = np.array([[0., 1., 0.], [0., 0., 1.], [0., -1., 0.], [0., 0., -1.],
                  [-1., -1., 0.], [-1., 0., 0.], [1., 1., .5], [-1., 1., .5]])
    wind = np.array([1., .13, -.07]); wind /= np.linalg.norm(wind)
    pg = np.eye(3) + .17*np.outer(wind, wind)
    cores = np.full((len(points), len(a)), .07)
    if core_kind == 'zero': cores[:] = 0.
    elif core_kind == 'mixed':
        cores[:, 6] = [.03, .08, .04]
        cores[0, :6] = 0.
        cores[:, 7] = [0., .07, .07]
    gamma = np.array([2.**20, 1., -2.**20, 1., .25, .25, .7, -.5])
    ground = GroundPlane(flag, [0., 0., 7.], [3., -2., 1.])
    return VortexFieldTangent(points, a, b, wind, pg, cores, gamma, ground)


def directions(tangent, width, imaginary=False):
    rng = np.random.default_rng(68117 + width + 100*imaginary)
    sources = np.arange(len(tangent.gamma))
    da = np.zeros((len(sources), 3, width)); db = np.zeros_like(da)
    dc = np.zeros((len(sources), width))
    for k in range(width):
        j = k % len(sources)
        if k % 4 == 0: da[j, :, k] = rng.normal(size=3)*.03
        elif k % 4 == 1: db[j, :, k] = rng.normal(size=3)*.03
        elif k % 4 == 2: dc[j, k] = rng.normal()*.02
        # Every fourth column remains exactly zero.
    active = np.array([[True, False, True, False, True, False, True, False],
                       [False, True, True, False, False, True, False, True],
                       [True, True, False, True, True, True, False, True]])
    return sources, da, db, dc, active


@pytest.mark.parametrize('flag', [-1, 0, 1])
@pytest.mark.parametrize('kind', ['shared', 'mixed', 'zero'])
@pytest.mark.parametrize('width', [1, 7, 16, 32])
def test_real_columns_match_original_owned_dense_contractions(flag, kind, width):
    tangent = fixture(flag, kind); old = dense(tangent)
    sources, da, db, dc, active = directions(tangent, width)
    original_arrays = [v.copy() for v in (da, db, dc, active)]
    actual = tangent.source_columns(sources, da, db, dc, core_active=active)
    expected = old.source_columns(sources, da, db, dc, core_active=active)
    np.testing.assert_allclose(actual, expected, rtol=5e-15, atol=5e-15)
    for k in range(width):
        masked = np.where(active, dc[None, :, k], 0.)
        np.testing.assert_allclose(tangent._ray_change(sources, da[:, :, k], db[:, :, k], masked),
            old._ray_change(sources, da[:, :, k], db[:, :, k], masked), rtol=5e-15, atol=5e-15)
    for value, original in zip((da, db, dc, active), original_arrays):
        np.testing.assert_array_equal(value, original)


@pytest.mark.parametrize('flag', [-1, 0, 1])
def test_complex_linear_extension_is_two_real_applications(flag):
    tangent = fixture(flag, 'mixed'); old = dense(tangent)
    real, imag = directions(tangent, 7), directions(tangent, 7, imaginary=True)
    def apply(obj, args):
        sources, da, db, dc, active = args
        return obj.source_columns(sources, da, db, dc, core_active=active)
    actual = apply(tangent, real) + 1j*apply(tangent, imag)
    expected = apply(old, real) + 1j*apply(old, imag)
    assert actual.dtype.kind == 'c'
    np.testing.assert_allclose(actual, expected, rtol=5e-15, atol=5e-15)


def test_branch_compensation_precedes_large_derivative_product():
    tangent = fixture(); tangent.gamma = tangent.gamma.copy()
    tangent.gamma[:4] = [2.**54, 1., -2.**54, 1.]
    sources = np.arange(4); da = np.zeros((4, 3)); da[:, 0] = 1.
    db = np.zeros_like(da); dc = np.zeros((len(tangent.points), 4))
    group = tangent.grouping.starts[0]
    assert np.all(tangent.grouping.starts[:4] == group)
    expected = -2.*tangent.ray_origin[:, group, :, 0]
    np.testing.assert_array_equal(tangent._ray_change(sources, da, db, dc), expected)
    np.testing.assert_array_equal(dense(tangent)._ray_change(sources, da, db, dc), expected)


def test_sparse_support_skips_only_exactly_zero_groups_and_core_directions(monkeypatch):
    tangent = fixture(); sources = np.array([4])
    da = np.array([[1e-150, 0., 0.]]); db = np.zeros_like(da)
    dc = np.zeros((len(tangent.points), 1))
    expected = dense(tangent)._ray_change(sources, da, db, dc)
    original = np.einsum; calls = []
    def counted(equation, *args, **kwargs):
        calls.append((equation, args[0].shape))
        return original(equation, *args, **kwargs)
    with monkeypatch.context() as patch:
        patch.setattr(np, 'einsum', counted)
        actual = tangent._ray_change(sources, da, db, dc)
    assert calls == [('ijab,jb->ia', (len(tangent.points), 1, 3, 3))]
    assert np.any(actual != 0.)
    np.testing.assert_array_equal(actual, expected)
    calls.clear()
    with monkeypatch.context() as patch:
        patch.setattr(np, 'einsum', counted)
        zero = tangent._ray_change(sources, np.zeros_like(da), db, dc)
    assert calls == []
    np.testing.assert_array_equal(zero, 0.)


def test_receiver_dependent_core_masks_survive_equal_zero_base_groups():
    tangent = fixture(core_kind='zero')
    # A coefficient-level diagnostic isolates incidence ownership. At an exact
    # zero physical core the actual radius derivative is zero; nonzero synthetic
    # coefficients here test mapping, not a physical zero-core sensitivity.
    tangent.ray_radius = np.ones_like(tangent.ray_radius)
    sources = np.array([0, 1]); da = np.zeros((2, 3)); db = da.copy()
    dc = np.array([[.2, 0.], [0., .3], [.2, .3]])
    actual = tangent._ray_change(sources, da, db, dc)
    expected = dense(tangent)._ray_change(sources, da, db, dc)
    np.testing.assert_array_equal(actual, expected)
    # Include only the common start-group coefficient to prevent trivial total
    # endpoint cancellation from concealing masks.
    tangent.ray_radius[:] = 0.
    group = tangent.grouping.starts[0]
    tangent.ray_radius[:, group, :] = 1.
    expected = -(dc @ tangent.gamma[sources])[:, None]*np.ones((1, 3))
    np.testing.assert_array_equal(tangent._ray_change(sources, da, db, dc), expected)


def test_source_guards_and_empty_valid_support_are_unchanged():
    tangent = fixture(); sources, da, db, dc, active = directions(tangent, 7)
    for method in (tangent.source_columns, dense(tangent).source_columns):
        with pytest.raises(VortexDerivativeUnavailable, match='layout'):
            method(sources[::-1], da, db, dc, core_active=active)
        invalid = da.copy(); invalid[0, 0, 0] = np.nan
        with pytest.raises(VortexDerivativeUnavailable, match='Nonfinite'):
            method(sources, invalid, db, dc, core_active=active)
        value = method(np.array([], dtype=int), da[:0], db[:0], dc[:0], core_active=active[:, :0])
        assert value.shape == (len(tangent.points), 3, 7)
        np.testing.assert_array_equal(value, 0.)


def test_cancelling_group_is_skipped_after_compensation(monkeypatch):
    tangent = fixture(); sources = np.array([4, 5]); da = np.zeros((2, 3)); db = da.copy()
    da[1] = [.125, -.25, .5]; db[0] = da[1]
    dc = np.zeros((len(tangent.points), 2)); calls = []
    original = np.einsum
    def counted(equation, *args, **kwargs):
        calls.append(equation)
        return original(equation, *args, **kwargs)
    expected = dense(tangent)._ray_change(sources, da, db, dc)
    with monkeypatch.context() as patch:
        patch.setattr(np, 'einsum', counted)
        actual = tangent._ray_change(sources, da, db, dc)
    assert calls == []
    np.testing.assert_array_equal(actual, expected)


@pytest.mark.parametrize('packed', [False, True])
def test_original_shared_stencil_batches_match_dense_ray_path(packed):
    from openswing.vortex_tangent import VortexSourceTangent
    base = fixture()
    core = np.full(len(base.a), .07); physical = np.ones(len(core), dtype=int)
    source = VortexSourceTangent(base.a, base.b, core, physical)
    wind = np.array([1., .13, -.07]); wind /= np.linalg.norm(wind)
    tangent = VortexFieldTangent(base.points, base.a, base.b, wind,
        np.eye(3)+.17*np.outer(wind, wind), core, base.gamma, _source=source)
    old = dense(tangent); changes = []; points = []
    for multiplier in (1., -1., 2., -2.):
        a, b, c, p = [value.copy() for value in (base.a, base.b, core, base.points)]
        a[4] += multiplier*1e-5*np.array([.3, -.2, .1])
        b[5] += multiplier*1e-5*np.array([-.1, .2, .3])
        c[6] += multiplier*1e-6
        p[0] += multiplier*1e-5*np.array([.1, .2, -.1])
        changes.append(source.difference(a, b, c, physical)); points.append(p)
    actual = tangent.values_shared(points, changes, [None]*4, _packed=packed)
    expected = old.values_shared(points, changes, [None]*4, _packed=packed)
    np.testing.assert_allclose(actual, expected, rtol=5e-15, atol=5e-15)


def test_nonzero_core_directions_with_all_receivers_excluded_are_exactly_zero(monkeypatch):
    tangent = fixture(core_kind='mixed'); sources = np.arange(len(tangent.gamma))
    da = np.zeros((len(sources), 3, 7)); db = da.copy()
    dc = np.full((len(sources), 7), .125)
    active = np.zeros((len(tangent.points), len(sources)), dtype=bool)
    expected = dense(tangent).source_columns(sources, da, db, dc, core_active=active)
    original = np.einsum; calls = []
    def counted(equation, *args, **kwargs):
        calls.append(equation)
        return original(equation, *args, **kwargs)
    with monkeypatch.context() as patch:
        patch.setattr(np, 'einsum', counted)
        actual = tangent.source_columns(sources, da, db, dc, core_active=active)
    assert calls == ['ijab,jbk->iak', 'ijab,jbk->iak']
    np.testing.assert_array_equal(actual, expected)
    np.testing.assert_array_equal(actual, 0.)


def test_fully_dense_simultaneous_motion_and_core_columns_match_original():
    tangent = fixture(core_kind='mixed'); sources = np.arange(len(tangent.gamma))
    rng = np.random.default_rng(53712)
    da, db = [rng.normal(size=(len(sources), 3, 16))*.03 for _ in range(2)]
    dc = rng.normal(size=(len(sources), 16))*.02
    active = np.ones((len(tangent.points), len(sources)), dtype=bool)
    active[0, ::2] = False
    actual = tangent.source_columns(sources, da, db, dc, core_active=active)
    expected = dense(tangent).source_columns(sources, da, db, dc, core_active=active)
    np.testing.assert_allclose(actual, expected, rtol=5e-15, atol=5e-15)
