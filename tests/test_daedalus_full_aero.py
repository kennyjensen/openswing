"""Actual loaded Daedalus aerodynamic loads against independent quadrature.

The baseline and four first-order response directions include lifting, body,
point, engine, jet, stall, circulation-rate and apparent-mass terms. Expected
arrays come from the independent Q32 evaluator, not a saved native output.
The public corrected cruise project supplies the loaded state; no trim,
linearization, circulation solve or harmonic solve is performed here.
"""
import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest

from openswing.asw import parse_asw
from openswing.equilibrium_state import restore, warm_start_recipe
from openswing.linear_dynamics import DynamicSystem
from openswing.network import StaticNetwork
from openswing.operating import time_load_constraints
from openswing.time_state import read_condition

ROOT = Path(__file__).resolve().parents[1]
DATA = Path(__file__).with_name('data')/'daedalus-full-aero'


def native_targets(packet):
    """Expose the complete compared aero maps from pass-through observations."""
    aero = packet['native']['aero']
    strips = [strip for strip in aero['strips'] if strip['lifting']]
    observed = packet['native']['observed_calls']
    assert len(observed['body']) == 1 and not aero['body_shoulders']
    result = {}
    for name, key in (
        ('force', 'force'), ('moment', 'moment'), ('cl', 'cl'),
        ('velocity', 'relative_velocity'), ('rate_force', 'circulation_rate_force'),
        ('apparent_force', 'apparent_force'), ('apparent_moment', 'apparent_moment'),
    ):
        result['lifting_'+name] = np.array([strip[key] for strip in strips])
    result['circulation_local_residual'] = np.array(aero['circulation_local_residual'])
    body = observed['body'][0]
    loads = body['output']
    for key in ('moment', 'force_samples', 'apparent', 'apparent_moment'):
        result['body_'+key] = np.asarray(loads[key])
    result['body_force'] = loads['lift']+loads['profile']+loads['apparent']
    result['body_velocity'] = body['velocity']
    result['point_force'] = np.array(aero['point_forces'])
    incident = {
        tuple(item['key']) if isinstance(item['key'], list) else item['key']: item['value']
        for item in packet['native']['observed_incident']
    }
    result['point_velocity'] = np.array([
        incident['point', i] for i in range(len(aero['point_forces']))
    ])
    engines = aero['engines']
    result['engine_inlet'] = np.array([
        engine['velocity'] for engine in observed['engine'][:len(engines)]
    ])
    for key in ('force', 'moment', 'axial_velocity', 'delta_velocity'):
        result['engine_'+key] = np.array([engine[key] for engine in engines])
    result.update(total_force=np.array(aero['force']), total_moment=np.array(aero['moment']))
    return result


@pytest.fixture(scope='module')
def loaded_aerodynamics():
    config = json.loads((ROOT/'examples/dae-cruise-physical-mesh-project.json').read_text())['cases'][0]['configuration']
    packet = config['equilibrium']['state']
    launch = packet['launch']
    model = parse_asw(config['source'])
    network = StaticNetwork(
        model, launch['panels'], read_condition(launch['condition']),
        launch['gravity'], launch['loads'], operating_constraints=time_load_constraints('free'),
        strut_mode=launch['strut_mode'],
        mesh_recipe=warm_start_recipe(model, launch['panels'], packet),
    )
    system = DynamicSystem(network, restore(network, packet), 'free')
    with np.load(DATA/'inputs.npz', allow_pickle=False) as saved:
        inputs = {key: saved[key].copy() for key in saved.files}
    assert (network.nn, network.ng, system.size) == (108, 82, 2044)
    assert len(network.operating.constraints) == 6
    for name, actual in (('r0', system.r0), ('Q0', system.Q0),
                         ('gamma0', system.gamma0), ('U0', system.U0)):
        np.testing.assert_allclose(actual, inputs[name], atol=2e-13, rtol=2e-13, err_msg=name)
    assert inputs['directions'].shape == inputs['direction_rates'].shape == (4, system.size)
    assert np.isfinite(inputs['directions']).all() and np.isfinite(inputs['direction_rates']).all()
    np.testing.assert_array_equal(inputs['control3_delta'], [1., 0., 1., 0.])
    np.testing.assert_array_equal(inputs['frequency_Hz'], [1., 1., 1.15737773741517, 1.15737773741517])

    # This exact helper captures existing native calls without computing a
    # second flow field or replaying any saved observations.
    spec = importlib.util.spec_from_file_location('_daedalus_full_aero_capture', DATA/'capture.py')
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)

    def evaluate(z, zdot, control3_delta):
        captured = helper.capture(system, z, zdot, control3_delta)
        assert network.iteration_fields is None and network.tangent_influences is None
        solver = captured['native']['aero']['circulation_solver']
        assert solver['method'] == 'prescribed' and solver['evaluations'] == 0
        return native_targets(captured)

    with np.load(DATA/'expected.npz', allow_pickle=False) as saved:
        expected = {key: saved[key].copy() for key in saved.files}
    return evaluate, inputs, expected


def assert_maps(actual, saved, prefix):
    expected = {key.removeprefix(prefix): value for key, value in saved.items() if key.startswith(prefix)}
    assert set(actual) == set(expected)
    for key in expected:
        np.testing.assert_allclose(actual[key], expected[key], atol=2e-7, rtol=2e-7, err_msg=key)


def test_loaded_daedalus_full_aero_base(loaded_aerodynamics):
    evaluate, inputs, expected = loaded_aerodynamics
    zero = np.zeros(inputs['directions'].shape[1])
    assert_maps(evaluate(zero, zero, 0.), expected, 'base__')


@pytest.mark.parametrize('direction', range(4), ids=('1Hz-real', '1Hz-imag', 'dip-real', 'dip-imag'))
def test_loaded_daedalus_full_aero_direction(loaded_aerodynamics, direction):
    evaluate, inputs, expected = loaded_aerodynamics
    z, zdot = inputs['directions'][direction], inputs['direction_rates'][direction]
    control, h = inputs['control3_delta'][direction], 5e-4
    probes = {factor: evaluate(factor*h*z, factor*h*zdot, factor*h*control)
              for factor in (-2, -1, 1, 2)}
    actual = {
        key: (probes[-2][key]-8*probes[-1][key]+8*probes[1][key]-probes[2][key])/(12*h)
        for key in probes[1]
    }
    assert_maps(actual, expected, f'd{direction}__')
