"""Newton damping must follow configuration changes, not force normalization."""
from pathlib import Path

import numpy as np
import pytest

from openswing.asw import parse_asw
from openswing.network import StaticNetwork, network_result
from openswing.source_discrete import SourceDiscreteNetwork
from openswing.source_dynamics import SourceDynamicNetwork
from openswing.structured_static import equilibrate


SOURCE = Path('examples/fixed-fixed-column-half.asw').read_text()
GRID = dict(default=4, beams={'1': dict(count=4, spacing='uniform')})
POLICIES = [StaticNetwork, SourceDiscreteNetwork, SourceDynamicNetwork]


@pytest.mark.parametrize('cls', POLICIES)
@pytest.mark.parametrize('sign', [-1., 1.])
def test_axial_reactions_take_full_newton_steps_despite_small_force_scale(cls, sign):
    model = parse_asw(SOURCE, beam_interpolation='drela-segspl-v1')
    load = sign*1.5*np.pi**2*100
    net = cls(model, GRID, None, [0., -10., 0.], [])
    # Like initial_equilibrium's posed gravity override, preserve the entered
    # coordinate scales while changing the physical load in the copied system.
    net.gravity = np.array([0., load, 0.])
    assert net.F == 10.
    state, steps = equilibrate(net)
    result = network_result(net, state)
    assert steps == 4 and len(net.structured_iterations) <= 8
    assert all(r['accepted'] for r in net.continuation_diagnostics)
    assert all(r['alpha'] == 1. for r in net.structured_iterations)
    assert result['residual'] <= 1e-12
    positions, rotations, forces, moments, *_ = net.unpack(state)
    np.testing.assert_allclose(positions, net.rj, rtol=0., atol=1e-12)
    np.testing.assert_allclose(rotations, np.broadcast_to(np.eye(3), rotations.shape), atol=1e-12)
    np.testing.assert_allclose(forces, np.tile([0., load, 0.], (net.ne, 1)), atol=1e-9)
    np.testing.assert_allclose(moments, 0., atol=1e-9)
    np.testing.assert_allclose(result['support_force'], [0., -load, 0.], atol=1e-9)
    np.testing.assert_allclose(result['force_balance'], 0., atol=1e-9)
    np.testing.assert_allclose(result['moment_balance'], 0., atol=1e-9)


def test_initial_gravity_override_keeps_coordinate_scales_and_original_equations(monkeypatch):
    import openswing.time_integration as time
    model = parse_asw(SOURCE, beam_interpolation='drela-segspl-v1')
    net = SourceDynamicNetwork(model, GRID, None, None, [])
    gravity, force_scale = net.gravity.copy(), net.F
    load = 1.5*np.pi**2*100
    zero = np.zeros_like(net.rj)
    options = dict(elastic_motion=(zero, zero, zero, zero),
        circulation_rate=np.zeros(net.circulation_basis.panels),
        gravity_override=np.array([0., -load, 0.]))
    copied = []
    original = time.equilibrate
    def capture(n, *a, **kw):
        copied.append(n)
        return original(n, *a, **kw)
    monkeypatch.setattr(time, 'equilibrate', capture)
    state, steps = time.initial_equilibrium(net, options, 1e-8, 4)
    assert len(copied) == 1 and copied[0] is not net
    assert steps == 4 and len(copied[0].structured_iterations) <= 8
    assert np.max(abs(net.residual(state, **options))) <= 1e-12
    assert net.F == copied[0].F == force_scale
    np.testing.assert_array_equal(net.gravity, gravity)


@pytest.mark.parametrize('cls', POLICIES)
def test_large_actual_extension_still_damps_the_complete_correction(cls):
    # The same load now causes a large displacement. It must retain damping,
    # even though the internal-force and reaction increments are no longer capped.
    source = SOURCE.replace('100 100 200 0 0 0 0', '100 100 200 100 0 0 0')
    model = parse_asw(source, beam_interpolation='drela-segspl-v1')
    load = 1500.
    net = cls(model, GRID, None, [0., load, 0.], [])
    state, _ = equilibrate(net)
    assert any(r['alpha'] < 1. for r in net.structured_iterations)
    assert np.max(abs(net.residual(state))) <= 1e-12
    positions, *_ = net.unpack(state)
    expected = net.rj.copy()
    expected[:, 1] *= 1+load/100.
    np.testing.assert_allclose(positions, expected, rtol=0., atol=2e-11)
