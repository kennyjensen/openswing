"""Exact body/source interaction reuse in geometry finite differences."""
from pathlib import Path
import numpy as np
import pytest
from openswing.tangent_influences import TangentInfluences
from openswing.volume import source_doublet, VolumeField
from openswing.asw import parse_asw
from openswing.aero import FlightCondition
from openswing.network import StaticNetwork
from openswing.ground import GroundPlane


@pytest.mark.parametrize('shape',[(72,83),(1,83),(83,1),(8,23)])
def test_volume_pairs_preserve_every_value_and_invalidate_changed_inputs(shape):
    rng = np.random.default_rng(930)
    nr,nc=shape
    arrays = (rng.normal(size=(nr, 3)), rng.normal(size=(nc, 3)),
              rng.normal(size=nc), rng.normal(size=(nc, 3)), rng.uniform(.01, .2, nc))
    cache = TangentInfluences()
    for change in ('base', 'receiver', 'position', 'strength', 'doublet', 'core', 'both', 'all', 'base', 'shape', 'dtype'):
        p, r, s, d, c = (v.copy() for v in arrays)
        if change in ('receiver', 'both'): p[5%nr, 1] += .01
        if change in ('position', 'both'): r[13%nc, 2] += .02
        if change == 'strength': s[12%nc] *= 1.1
        if change == 'doublet': d[8%nc, 0] += .03
        if change == 'core': c[2%nc] += .01
        if change == 'all': r += .01
        if change == 'shape': p = p[:7]
        if change == 'dtype': p, r, s, d, c = (v.astype(np.float32) for v in (p, r, s, d, c))
        actual = cache.volume_pairs('probe', p, r, s, d, c)
        expected = source_doublet(p[:, None, :]-r[None, :, :], s[None, :], d[None, :, :], c[None, :])
        np.testing.assert_array_equal(actual, expected)
        actual[:] = np.nan
    assert cache.bytes <= 64*1024**2
    cache.bytes = 64*1024**2
    p, r, s, d, c = arrays
    np.testing.assert_array_equal(cache.volume_pairs('uncached', *arrays),
        source_doublet(p[:, None, :]-r[None, :, :], s[None, :], d[None, :, :], c[None, :]))
    assert ('volume', 'uncached') not in cache.entries


@pytest.mark.parametrize('flag', [0, 1, -1])
def test_volume_velocity_keeps_images_exclusions_and_sum_order(flag):
    model = parse_asw(Path('examples/wing-body.asw').read_text())
    net = StaticNetwork(model, 24, FlightCondition(mach=.3), None, [])
    field = VolumeField(model, net.meshes, np.array([1., .1, .05]), np.diag([1.2, 1., 1.]),
                        ground=GroundPlane(flag, [0, 0, 20], [10, 20, 30]))
    rng = np.random.default_rng(691)
    points = rng.normal(size=(72, 3))+[0, 0, 3]
    cache = TangentInfluences()
    for change in ('base', 'receiver', 'source', 'both', 'scalar_body', 'array_body', 'point', 'all'):
        p = points.copy(); original = field.positions.copy(); options = {}
        if change in ('receiver', 'both'): p[3] += .01
        if change in ('source', 'both'): field.positions[3] += .02
        if change == 'scalar_body': options['exclude_body'] = 2
        if change == 'array_body': options['exclude_body'] = np.where(np.arange(72)%2, 2, -1)
        if change == 'point': options['exclude_point'] = 0
        if change == 'all': p += .02
        np.testing.assert_array_equal(field.velocity(p, _tangent=cache, _cache_name='probe', **options),
                                      field.velocity(p, **options))
        field.positions[:] = original


@pytest.mark.parametrize('example,dynamic', [('wing-body', False), ('wing-body', True), ('dae', False)])
def test_full_body_tangent_equals_original_residual_assembly(example, dynamic):
    model = parse_asw(Path(f'examples/{example}.asw').read_text())
    condition = FlightCondition(alpha=5, beta=2, mach=.2, rates=[.01, -.02, .03],
                                ground_effect=-1, position_earth=[0, 0, 30])
    net = StaticNetwork(model, 8, condition, None, [])
    rng = np.random.default_rng(522)
    x = rng.normal(0, .0001, net.size)
    x[net.gamma_start:net.operating_start] += .03
    options = dict(elastic_motion=tuple(rng.normal(0, .001, (4, net.nn, 3)))) if dynamic else {}
    np.testing.assert_array_equal(net.jacobian(x, .6, **options), net._jacobian(x, .6, **options))
    assert net.tangent_influences is None
