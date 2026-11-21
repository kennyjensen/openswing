"""Unchanged pair reuse must preserve full aerodynamic values and tangents."""
from pathlib import Path
import numpy as np
import pytest
from openswing.aero import horseshoe_velocity, FlightCondition
from openswing.asw import parse_asw
from openswing.ground import GroundPlane
from openswing.network import StaticNetwork
from openswing.tangent_influences import TangentInfluences


@pytest.mark.parametrize('flag', [0, 1, -1])
@pytest.mark.parametrize('shape', [(184,184), (1,72), (72,1)])
def test_identical_pairs_skip_relative_transform_and_own_output(flag, shape, monkeypatch):
    import openswing.aero as aero
    rng = np.random.default_rng(826)
    nr, nc = shape
    points, a, b = (rng.normal(size=(n, 3)) for n in (nr, nc, nc))
    direction = np.array([1., .2, -.1]); pg = np.diag([1.2, 1., 1.])
    core = rng.uniform(.01, .2, shape)
    ground = GroundPlane(flag, [0, 0, 10], [10, 20, 30])
    mask = np.eye(nr, nc, dtype=bool)
    cache = TangentInfluences()
    expected = cache.vortex('same', points, a, b, direction, pg, core, ground, mask)
    def unexpected(*args, **kwargs):
        pytest.fail('Unchanged pairs repeated the relative-coordinate transform')
    monkeypatch.setattr(aero, '_relative_pg', unexpected)
    for _ in range(2):
        actual = cache.vortex('same', points.copy(), a.copy(), b.copy(),
                              direction.copy(), pg.copy(), core.copy(), ground, mask.copy())
        np.testing.assert_array_equal(actual, expected)
        actual[:] = np.nan


@pytest.mark.parametrize('flag', [0, 1, -1])
@pytest.mark.parametrize('compressible', [False, True])
@pytest.mark.parametrize('shape', [(72,72),(1,72),(72,1),(8,23)])
def test_every_changed_pair_matches_full_kernel_exactly(flag, compressible, shape):
    rng = np.random.default_rng(528)
    nr,nc=shape
    a = rng.normal(size=(nc, 3)); b = a+rng.normal(size=(nc, 3))
    points = rng.normal(size=(nr, 3)); core = rng.uniform(.01, .3, shape)
    excluded = np.eye(nr,nc,dtype=bool)
    direction = np.array([1., .12, -.08]); direction /= np.linalg.norm(direction)
    pg = np.eye(3)+(0.2 if compressible else 0)*np.outer(direction, direction)
    ground = GroundPlane(flag, [0, 0, 10], [10, 20, 30], [.1, -.2, 1])
    cache = TangentInfluences()
    for change in ['base', 'receiver', 'source', 'both', 'core', 'exclude', 'all', 'base']:
        pp, aa, bb, cc, ee = [v.copy() for v in (points, a, b, core, excluded)]
        if change in ['receiver', 'both']: pp[5%nr, 1] += .001
        if change in ['source', 'both']: aa[12%nc, 2] += .001; bb[13%nc, 0] -= .001
        if change == 'core': cc[2%nr, 3%nc] += .01
        if change == 'exclude': ee[8%nr, 9%nc] = ~ee[8%nr, 9%nc]
        if change == 'all': aa += .001
        actual = cache.vortex('test', pp, aa, bb, direction, pg, cc, ground, ee)
        expected = horseshoe_velocity(pp[:, None, :], aa[None, :, :], bb[None, :, :],
                                      direction, pg, cc, ground, exclude_bound=ee)
        np.testing.assert_array_equal(actual, expected)
        actual[:] = np.nan  # Returned arrays cannot corrupt the stored base.


@pytest.mark.parametrize('change', ['wind', 'pg', 'ground', 'shape', 'mask', 'dtype'])
def test_changed_global_state_does_not_reuse_stale_values(change):
    rng = np.random.default_rng(528)
    a = rng.normal(size=(72, 3)); b = a+rng.normal(size=(72, 3))
    points = rng.normal(size=(72, 3)); core = np.full((1, 72), .1)
    wind = np.array([1., .12, -.08]); pg = np.diag([1.2, 1., 1.]); ground = GroundPlane(1)
    mask = np.eye(72, dtype=bool)
    cache = TangentInfluences()
    cache.vortex('test', points, a, b, wind, pg, core, ground, mask)
    if change == 'wind': wind[2] += .02
    if change == 'pg': pg[0, 0] += .1
    if change == 'ground': ground = GroundPlane(-1, [0, 0, 3], [10, 20, 30])
    if change == 'shape': points = points[:7]; mask = mask[:7]
    if change == 'mask': mask = None
    if change == 'dtype': points, a, b, core = [v.astype(np.float32) for v in (points, a, b, core)]
    expected = horseshoe_velocity(points[:, None, :], a[None, :, :], b[None, :, :],
                                  wind, pg, core, ground, exclude_bound=mask)
    np.testing.assert_array_equal(cache.vortex('test', points, a, b, wind, pg, core, ground, mask), expected)


@pytest.mark.parametrize('example,extra', [
    ('rectangular', {}), ('flexible', {}), ('powered', {}), ('wing-body', {}),
    ('articulated', {}), ('flexible', dict(ground_effect=1, position_earth=[0, 0, 10], attitude=[10, 5, 2])),
    ('flexible', dict(circulation_modes={1: 5})), ('wing-body', dict(freeze_influences=True)),
])
def test_complete_coupled_tangent_matches_full_recomputation(example, extra, monkeypatch):
    model = parse_asw(Path(f'examples/{example}.asw').read_text())
    condition = FlightCondition(alpha=5, beta=2, mach=.25, rates=[.01, -.02, .03], **extra)
    net = StaticNetwork(model, 12, condition, None, [])
    x = np.random.default_rng(937).normal(0, .001, net.size)
    x[net.gamma_start:net.operating_start] += .04
    expected = net.jacobian(x, .7)
    calls = []
    def uncached(self, name, points, a, b, direction, pg, core, ground, exclude_bound=None):
        from openswing.factored_influence import FactoredInfluence
        calls.append(name)
        return FactoredInfluence(points, a, b, direction, pg, core, ground,
                                 exclude_bound=exclude_bound)
    monkeypatch.setattr(TangentInfluences, 'factored_vortex', uncached)
    np.testing.assert_array_equal(net.jacobian(x, .7), expected)
    assert calls or condition.freeze_influences
    assert net.tangent_influences is None


def test_failed_tangent_discards_cache(monkeypatch):
    model = parse_asw(Path('examples/flexible.asw').read_text())
    net = StaticNetwork(model, 4, FlightCondition(mach=0), None, [])
    def fail(*args, **kwargs):
        assert net.tangent_influences is not None
        raise ValueError('deliberate rejected trial')
    monkeypatch.setattr(net, '_jacobian', fail)
    with pytest.raises(ValueError, match='deliberate rejected trial'):
        net.jacobian(np.zeros(net.size), .5)
    assert net.tangent_influences is None


@pytest.mark.parametrize('example', ['rectangular', 'flexible', 'powered', 'wing-body', 'articulated'])
def test_rank_load_cache_retains_exact_first_load_tangent(example, monkeypatch):
    from openswing.tangent_influences import TangentLoads
    import openswing.network as network_module
    model = parse_asw(Path(f'examples/{example}.asw').read_text())
    net = StaticNetwork(model, 4, FlightCondition(alpha=5, mach=0), None, [])
    x = np.random.default_rng(748).normal(0, .001, net.size)
    x[net.gamma_start:net.operating_start] += .04
    cache = TangentLoads()
    net.jacobian(x, 0., _load_cache=cache)
    calls = []
    evaluate = network_module.evaluate_aerodynamics
    def counted(*args, **kwargs):
        calls.append(1)
        return evaluate(*args, **kwargs)
    monkeypatch.setattr(network_module, 'evaluate_aerodynamics', counted)
    reused = net.jacobian(x, .25, _load_cache=cache)
    assert not calls  # All identical physical loads came from the rank pass.
    np.testing.assert_array_equal(reused, net.jacobian(x, .25))
    assert calls and net._tangent_loads is None
    assert cache.bytes <= cache.limit
    # A exhausted cache changes cost only, never the physical tangent.
    np.testing.assert_array_equal(reused, net.jacobian(x, .25, _load_cache=TangentLoads(limit=0)))


def test_elastic_motion_tangent_matches_original_columns(monkeypatch):
    model = parse_asw(Path('examples/flexible.asw').read_text())
    net = StaticNetwork(model, 8, FlightCondition(alpha=5, mach=.2), None, [])
    rng = np.random.default_rng(294)
    x = rng.normal(0, .001, net.size)
    x[net.gamma_start:net.operating_start] += .04
    options = dict(elastic_motion=tuple(rng.normal(0, .01, (4, net.nn, 3))))
    actual = net.jacobian(x, .7, **options)
    # Bypass the complete tangent cache, retaining the original difference
    # assembler and all unsteady aerodynamic/inertial calculations.
    np.testing.assert_array_equal(actual, net._jacobian(x, .7, **options))
