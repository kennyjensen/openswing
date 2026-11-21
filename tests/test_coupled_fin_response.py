"""Independent loaded free-carrier/hinged-fin response at one hertz.

Two n=4 lag cases share one Q32 manufactured equilibrium and one native base
correction. Each compares both control and physical yaw inputs, every declared
physical output, and all mapped kinematic/circulation coordinates. This is a
discrete component regression, not aircraft or experimental validation.
"""
from copy import deepcopy
from dataclasses import replace
import importlib.util
import json
from pathlib import Path
import sys

import numpy as np
import pytest

import coupled_fin_adapter as adapter
import coupled_fin_outputs as outputs
from openswing.equilibrium_state import capture, restore
from openswing.frequency_response import harmonic_solve, input_partials
from openswing.linear_dynamics import DynamicSystem, linearize
from openswing.network import StaticNetwork
from openswing.operating import free_flight_constraints


ROOT = Path(__file__).resolve().parents[1]
for _name in ('coupled_fin_aero_reference', 'coupled_fin_reference'):
    _spec = importlib.util.spec_from_file_location(_name, ROOT/'scripts'/(_name+'.py'))
    _module = importlib.util.module_from_spec(_spec)
    sys.modules[_name] = _module
    _spec.loader.exec_module(_module)
reference = sys.modules['coupled_fin_reference']

DERIVATIVE_STEP = 1e-5
OUTPUT_STEP = 2.5e-6
EPSILON = 1e-24
OMEGA = 2*np.pi
ATOL, RTOL = 2e-7, 2e-8


def _physical_equal(actual, expected):
    assert np.shape(actual) == np.shape(expected)
    np.testing.assert_allclose(actual, expected, atol=ATOL, rtol=RTOL)


def _all_outputs(actual, expected):
    assert actual.keys() == expected.keys()
    for key in expected:
        assert np.shape(actual[key]) == np.shape(expected[key]), key
        np.testing.assert_allclose(actual[key], expected[key], atol=ATOL,
                                   rtol=RTOL, err_msg=key)


def _independent_solve(matrix, rhs, *, harmonic):
    """Solve the full 4x4 base or 11x11 harmonic equations and check them."""
    assert matrix.shape == ((11, 11) if harmonic else (4, 4))
    assert rhs.shape == ((11, 2) if harmonic else (4,))
    rows = np.maximum(np.max(abs(matrix), axis=1), 1e-30)
    rowed = matrix/rows[:, None]
    columns = np.maximum(np.max(abs(rowed), axis=0), 1e-30)
    scaled = rowed/columns
    singular = np.linalg.svd(scaled, compute_uv=False)
    assert singular[-1]/singular[0] >= 1e-12
    scaled_rhs = rhs/rows[:, None] if harmonic else rhs/rows
    solution = np.linalg.solve(scaled, scaled_rhs)
    solution = solution/columns[:, None] if harmonic else solution/columns
    residual = matrix@solution-rhs
    if harmonic:
        envelope = abs(matrix)@abs(solution)+abs(rhs)
        assert not np.any((envelope == 0) & (abs(residual) != 0))
        relative = np.divide(abs(residual), envelope,
            out=np.zeros_like(envelope), where=envelope > 0)
        assert np.all(np.isfinite(relative)) and np.max(relative) <= 1e-10
    else:
        np.testing.assert_allclose(residual, 0., atol=1e-10, rtol=0.)
    return solution


def _snapshot(system, fixture, z, zdot, forcing, counts):
    counts['output_snapshots'] += 1
    assert counts['output_snapshots'] <= 18
    state, _, options = system.physical_state(z, zdot, forcing=forcing)
    _, data = system.network.residual(state.x, detail=True, **options)
    # Output extraction immediately follows this exact detailed evaluation;
    # its already calculated mass cache is not borrowed from another state.
    return outputs.extract(system, state, data, fixture)


@pytest.fixture(scope='module')
def coupled_fin_case():
    fixture = json.loads((ROOT/'docs/validation/coupled-fin-fixture.json').read_text())
    counts = dict(native_residuals=0, base_correctors=0, pencils=0,
                  native_harmonics=0, input_partials=0, output_snapshots=0,
                  reference_base_solves=0, reference_harmonics=0)
    ref = reference.Coupled(4, 32, fixture)
    base = ref.base_system()
    counts['reference_base_solves'] += 1
    gamma = _independent_solve(base['W'], base['rhs'], harmonic=False)
    assert np.max(abs(gamma)) > 1e-8
    manufactured, _ = ref.manufacture(gamma)
    derivatives, reference_base = {}, {}
    for lag in (False, True):
        zero = np.zeros(7)
        packet = ref.evaluate(ref.aero.base_coordinates(), zero, zero, gamma,
                              np.zeros(4), 0., manufactured, lag)
        np.testing.assert_allclose(packet['residual'], 0., atol=1e-10, rtol=0.)
        reference_base[lag] = packet['output']
        derivatives[lag] = ref.linearize(gamma, manufactured, lag, EPSILON)
    assert ref.evaluations == 62 and ref.aero.evaluations == 63
    assert ref.aero.fields == 24 and ref.aero.field_sets == 8

    original = StaticNetwork.residual

    def counted(network, *args, **kwargs):
        counts['native_residuals'] += 1
        assert counts['native_residuals'] <= 5000
        return original(network, *args, **kwargs)

    StaticNetwork.residual = counted
    try:
        prepared = adapter.prepare(fixture, 4, manufactured, lag=False,
                                   reference_geometry=base['geometry'])
        assert all(c['passed'] for c in prepared['geometry_report']['checks'])
        assert counts['native_residuals'] == 0
        counts['base_correctors'] += 1
        system, _, fresh = adapter.build_system(prepared)
        np.testing.assert_allclose(fresh, 0., atol=1e-8, rtol=0.)
        seed = system.fixture_seed_comparison
        assert seed['position_max_abs'] <= 2e-8
        assert seed['rotation_matrix_max_abs'] <= 2e-8
        np.testing.assert_allclose(system.gamma0, gamma, atol=2e-8, rtol=0.)
        frozen = capture(system.network, system.base)
        yield dict(fixture=fixture, ref=ref, gamma=gamma,
                   reference_base=reference_base, derivatives=derivatives,
                   prepared=prepared, base=system, frozen=frozen, counts=counts,
                   setup_counts=counts.copy())
    finally:
        StaticNetwork.residual = original


@pytest.mark.parametrize('lag', [False, True], ids=['lag-off', 'lag-on'])
def test_loaded_free_carrier_fin_matches_independent_response(
        coupled_fin_case, lag, record_property):
    case = coupled_fin_case
    fixture, counts = case['fixture'], case['counts']
    before = counts.copy()
    base = case['base']
    if lag:
        condition = replace(base.condition, aero_lag=True)
        prepared = case['prepared']
        network = StaticNetwork(prepared['model'], prepared['panels'], condition,
            [0., 0., 0.], prepared['loads'], operating_constraints=free_flight_constraints())
        state = restore(network, deepcopy(case['frozen']))
        system = DynamicSystem(network, state, frame='free')
        assert (network.L, network.F, network.gamma_scale) == (
            base.network.L, base.network.F, base.network.gamma_scale)
    else:
        system = base
    zero = np.zeros(system.size)
    np.testing.assert_allclose(system.residual(zero, zero), 0., atol=1e-8, rtol=0.)
    assert system.condition.aero_lag == lag == system.network.condition.aero_lag
    np.testing.assert_allclose(system.motion.acceleration, 0., atol=1e-8, rtol=0.)
    np.testing.assert_allclose(system.motion.angular_acceleration, 0., atol=1e-8, rtol=0.)
    _all_outputs(_snapshot(system, fixture, zero, zero, None, counts),
                 case['reference_base'][lag])

    counts['pencils'] += 1
    a, m = linearize(system, step=DERIVATIVE_STEP, sparse=True, _output_fields=False)
    channels, signs = adapter.native_inputs(system)
    counts['input_partials'] += 1
    native_b, forcings, _ = input_partials(system, channels, 0., DERIVATIVE_STEP,
                                          constant_inputs={})
    b = adapter.physical_input_columns(native_b)
    derivative = case['derivatives'][lag]
    matrix, rhs = reference.Coupled.harmonic(derivative, OMEGA)
    counts['reference_harmonics'] += 1
    expected_state = _independent_solve(matrix, rhs, harmonic=True)
    expected = reference.Coupled.recover(derivative, OMEGA, expected_state)
    counts['native_harmonics'] += 1
    state, diagnostics = harmonic_solve(a, m, b, OMEGA)

    columns = []
    for input_index in range(2):
        vector = state[:, input_index]
        rate = 1j*OMEGA*vector
        width = min(OUTPUT_STEP*channels[input_index].scale,
                    OUTPUT_STEP/max(float(np.max(abs(vector))), 1e-30))
        samples = []
        for part, component in enumerate((np.real, np.imag)):
            for sign in (1, -1):
                forcing = forcings[input_index](part, sign*width*signs[input_index])
                samples.append(_snapshot(system, fixture,
                    sign*width*component(vector), sign*width*component(rate),
                    forcing, counts))
        columns.append({key: ((np.asarray(samples[0][key])-samples[1][key])
                    + 1j*(np.asarray(samples[2][key])-samples[3][key]))/(2*width)
                    for key in samples[0]})
        selected, mask = adapter.kinematic_harmonic_state(system, fixture,
            expected_state[:7, input_index], expected_state[7:, input_index], OMEGA)
        _physical_equal(state[mask, input_index], selected[mask])
    actual = {key: np.stack([row[key] for row in columns], axis=-1)
              for key in columns[0]}
    # Native target.Mz prescribes a load balance. Its negative gives positive
    # physical yaw torque; raw reported loads exclude that applied input.
    physical = actual['global_applied_wrench_body'].copy()
    physical[5, 1] += 1.
    actual['physical_global_balance_body'] = physical
    _all_outputs(actual, expected)
    _physical_equal(physical, np.zeros((6, 2)))
    _physical_equal(expected['physical_global_balance_body'], np.zeros((6, 2)))
    assert counts['base_correctors'] == counts['reference_base_solves'] == 1
    assert counts['native_harmonics'] <= 2 and counts['reference_harmonics'] <= 2
    assert counts['output_snapshots']-before['output_snapshots'] == 9
    assert case['ref'].evaluations == 62 and case['ref'].aero.fields == 24
    maximum = max(float(np.max(abs(actual[key]-expected[key])/
                       (ATOL+RTOL*abs(expected[key])))) for key in expected)
    record_property('maximum_physical_output_gate_fraction', maximum)
    record_property('native_harmonic_diagnostics', json.dumps(diagnostics))
    for key in counts:
        record_property('case_'+key, counts[key]-before[key])
        record_property('shared_setup_'+key, case['setup_counts'][key])
