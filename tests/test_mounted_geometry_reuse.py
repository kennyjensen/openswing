"""Complete geometry reuse in mounted full corrections, with a physical oracle."""
import numpy as np
import pytest

from openswing.aero import FlightCondition
from openswing.network import StaticNetwork
from openswing.tangent_influences import TangentInfluences, TangentLoads
from test_direct_circulation import model_for, state_for


def mounted(example='flexible'):
    return StaticNetwork(model_for(example), 4,
        FlightCondition(speed=30, alpha=5, beta=2, mach=.1), None, [])


def test_explicit_geometry_enables_complete_first_order_columns(monkeypatch):
    import openswing.geometry_tangent as geometry
    net = mounted('wing-body')
    x = state_for(net, .3)
    before = net.residual(x, .6).copy()
    net._frequency_local_geometry = False
    original = geometry.geometry_columns
    calls = []

    def capture(*args, **kwargs):
        assert net.tangent_influences.local_geometry is True
        calls.append(kwargs.copy())
        return original(*args, **kwargs)

    monkeypatch.setattr(geometry, 'geometry_columns', capture)
    actual = net.jacobian(x, .6, _direct_geometry=True)
    assert len(calls) == 1
    assert calls[0]['difference_order'] == 1 and calls[0]['step'] == 1e-6
    assert all(calls[0][key] for key in
               ('_direct_vortex', '_direct_volume', '_direct_geometry', '_direct_structural'))
    diagnostic = net.geometry_derivative_diagnostics
    assert diagnostic['direct_geometry_columns'] == 6*net.nn
    assert diagnostic['field_evaluations'] == 2
    # Translation and rotation at both ends test the complete moving-field
    # derivative, not just the cheaper frozen-field local partial. The bound
    # is the existing first-order Newton composition bound, not a solve gate.
    columns = np.unique([0, 2, 4, 6*(net.nn-1), 6*(net.nn-1)+4])
    for column in columns:
        h = 3e-6*max(1., abs(x[column]))
        delta = np.zeros(net.size)
        delta[column] = h
        p, m, pp, mm = [net.residual(x+k*delta, .6) for k in (1, -1, 2, -2)]
        expected = (8*(p-m)-(pp-mm))/(12*h)
        assert np.max(abs(actual[:, column]-expected)/(1+abs(expected))) < 2e-5
    assert net._frequency_local_geometry is False
    assert net.tangent_influences is None and net.iteration_fields is None
    np.testing.assert_array_equal(net.residual(x, .6), before)


def test_explicit_false_overrides_frequency_flag_and_keeps_original_stencil(monkeypatch):
    import openswing.geometry_tangent as geometry
    oracle = mounted()
    x = state_for(oracle, .3)
    expected = oracle.jacobian(x, .6, _direct_geometry=False)
    net = mounted()
    net._frequency_local_geometry = True
    original = net.residual
    observed = []

    def residual(*args, **kwargs):
        observed.append(net.tangent_influences.local_geometry)
        return original(*args, **kwargs)

    def forbidden(*args, **kwargs):
        raise AssertionError('Explicit False must use original geometry stencils.')

    monkeypatch.setattr(net, 'residual', residual)
    monkeypatch.setattr(geometry, 'geometry_columns', forbidden)
    actual = net.jacobian(x, .6, _direct_geometry=False)
    assert observed and not any(observed)
    np.testing.assert_array_equal(actual, expected)
    assert net._frequency_local_geometry is True
    assert net.tangent_influences is None and net.iteration_fields is None


@pytest.mark.parametrize('interrupt', [False, True])
def test_geometry_context_restores_previous_owners_after_success_or_failure(monkeypatch, interrupt):
    net = mounted()
    x = state_for(net, .3)
    before = net.residual(x, .6).copy()
    net._frequency_local_geometry = False
    previous = TangentInfluences(local_geometry=False)
    sentinel = np.array([3., 7.])
    previous.material['sentinel'] = sentinel
    loads = TangentLoads(limit=0)
    loads.entries['sentinel'] = sentinel
    net.tangent_influences, net._tangent_loads = previous, loads
    temporary = TangentLoads()
    original = net.residual
    entered = []

    def residual(*args, **kwargs):
        if net.iteration_fields is not None:
            entered.append(True)
            assert net._tangent_loads is None
            assert net.tangent_influences is not previous
            if interrupt:
                raise RuntimeError('interrupted physical geometry capture')
        return original(*args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(net, 'residual', residual)
        if interrupt:
            with pytest.raises(RuntimeError, match='interrupted physical geometry capture'):
                net.jacobian(x, .6, _direct_geometry=True, _load_cache=temporary)
        else:
            assert np.isfinite(net.jacobian(x, .6, _direct_geometry=True, _load_cache=temporary)).all()
    assert entered
    assert net._frequency_local_geometry is False
    assert net.tangent_influences is previous and net._tangent_loads is loads
    assert net.iteration_fields is None
    assert previous.material == {'sentinel': sentinel}
    assert loads.entries == {'sentinel': sentinel}
    np.testing.assert_array_equal(sentinel, [3., 7.])
    # The ordinary physical aero cache can be invalidated/repopulated, but
    # temporary captured or lagged fields must not leak into a later residual.
    np.testing.assert_array_equal(net.residual(x, .6), before)


def test_unavailable_geometry_retains_complete_original_matrix(monkeypatch):
    import openswing.geometry_tangent as geometry
    net = mounted()
    x = state_for(net, .3)
    expected = net.jacobian(x, .6, _direct_geometry=False)

    def unavailable(*args, **kwargs):
        raise geometry.GeometryDerivativeUnavailable('deliberate unsupported geometry')

    monkeypatch.setattr(geometry, 'geometry_columns', unavailable)
    actual = net.jacobian(x, .6, _direct_geometry=True)
    np.testing.assert_array_equal(actual, expected)
    assert net.geometry_derivative_diagnostics == dict(
        method='original full residual differences', fallback='deliberate unsupported geometry')
    assert net.tangent_influences is None and net.iteration_fields is None


@pytest.mark.parametrize('example', ['flexible', 'wing-body'])
def test_mounted_full_retry_matches_explicit_physical_stencil_equilibrium(monkeypatch, example):
    import openswing.structured_static as static
    outputs = []
    original_block_solve = static.block_solve
    for oracle in (False, True):
        net = mounted(example)
        # No frequency flag is required by a mounted correction.
        assert not getattr(net, '_frequency_local_geometry', False)
        original_jacobian = net.jacobian
        full_calls, rejected = [], []

        def full_jacobian(x, factor, **kwargs):
            if factor > 0:
                assert kwargs.get('_direct_geometry') is True
                full_calls.append(factor)
            if oracle:
                kwargs['_direct_geometry'] = False
            result = original_jacobian(x, factor, **kwargs)
            if factor > 0 and not oracle:
                diagnostic = net.geometry_derivative_diagnostics
                assert diagnostic['geometry_columns'] == 6*net.nn
                assert diagnostic['difference_order'] == 1
                assert diagnostic['difference_step'] == 1e-6
                if diagnostic['direct_geometry_columns'] != 6*net.nn:
                    # Planar initial geometry can lie on the vortex PV mask.
                    # The guarded full physical stencil still supplies every
                    # moving-field column; it must not be replaced by a local
                    # frozen-field partial just to enable the direct path.
                    assert diagnostic['direct_geometry_columns'] == 0
                    assert diagnostic['direct_geometry_fallback'] == 'No owned vortex Jacobian for hv'
                    assert diagnostic['direct_vortex_fallbacks']['hv'] == (
                        'A retained vortex stencil can leave the principal-value mask; use full physical differences.')
                    assert diagnostic['geometry_groups'] > 0
                    assert diagnostic['geometry_stencil_bytes'] > 0
                    assert diagnostic['field_evaluations'] > 2
            return result

        def reject_first_approximate_direction(*args, **kwargs):
            # Exercise the supported full-correction fallback once using an
            # unavailable approximate direction. Physical equations and gates
            # remain unchanged in both runs.
            if not rejected:
                rejected.append(True)
                raise ValueError('deliberate approximate direction failure')
            return original_block_solve(*args, **kwargs)

        with monkeypatch.context() as patch:
            patch.setattr(net, 'jacobian', full_jacobian)
            patch.setattr(static, 'block_solve', reject_first_approximate_direction)
            x, steps = static.equilibrate(net, tolerance=1e-8, full_structure=False)
        assert rejected and full_calls and steps > 0
        assert any(record.get('exact_fallback') for record in net.structured_iterations)
        residual, data = net.residual(x, detail=True)
        assert np.isfinite(x).all() and np.isfinite(residual).all()
        assert np.max(abs(residual)) <= 1e-12
        assert net.tangent_influences is None and net.iteration_fields is None
        assert net._tangent_loads is None
        outputs.append((x, data))
    actual, expected = outputs
    np.testing.assert_allclose(actual[0], expected[0], rtol=1e-8, atol=2e-9)
    for key in ('r', 'Q', 'N', 'M', 'force', 'moment'):
        assert np.isfinite(actual[1][key]).all() and np.isfinite(expected[1][key]).all()
        np.testing.assert_allclose(actual[1][key], expected[1][key], rtol=1e-8, atol=1e-8)
