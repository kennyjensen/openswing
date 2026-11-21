"""Actual loaded Daedalus balance against independently composed physics.

Expected arrays combine independent aerodynamics, nodal virtual-work transfer,
real mass/gravity, loaded mechanical equilibrium, rigid constraints and frame
kinematics. The complete directional residual also reuses the independently
derived compatibility map. This is one stationary base and four directions,
not equality of the full tangent or historical ASWING/Bode validation.

The five tests make exactly17 full native residual calls when run together:
one base and four fourth-order probes per direction. No trim, linearization,
circulation solve or harmonic solve is performed. A pass-through network
subclass retains detailed loads from the same call used by DynamicSystem.
"""
from dataclasses import replace
import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from openswing.asw import parse_asw
from openswing.equilibrium_state import restore, warm_start_recipe
from openswing.linear_dynamics import DynamicSystem, state_layout
from openswing.network import StaticNetwork
from openswing.operating import time_load_constraints
from openswing.time_state import read_condition


ROOT = Path(__file__).resolve().parents[1]
DATA = Path(__file__).with_name('data')/'daedalus-full-balance'


class DetailedNetwork(StaticNetwork):
    """Retain external wrenches without a second residual/load evaluation."""

    def residual(self, *args, **kwargs):
        requested_detail = kwargs.pop('detail', False)
        value, details = super().residual(*args, detail=True, **kwargs)
        self.last_details = details
        return (value, details) if requested_detail else value


@pytest.fixture(scope='module')
def loaded_balance():
    provenance = json.loads((DATA/'provenance.json').read_text())
    for name, expected in provenance['files'].items():
        content = (DATA/name).read_bytes()
        assert dict(bytes=len(content),sha256=hashlib.sha256(content).hexdigest()) == expected, name
    request = json.loads((DATA/'request.json').read_text())
    configuration = json.loads((ROOT/request['project']).read_text())['cases'][0]['configuration']
    packet = configuration['equilibrium']['state']
    launch = packet['launch']
    model = parse_asw(configuration['source'])
    network = DetailedNetwork(model, launch['panels'], read_condition(launch['condition']),
        launch['gravity'], launch['loads'], operating_constraints=time_load_constraints('free'),
        strut_mode=launch['strut_mode'], mesh_recipe=warm_start_recipe(model,launch['panels'],packet))
    system = DynamicSystem(network,restore(network,packet),'free')
    assert network.mesh_recipe == 'physical-breaks-v1'
    assert launch['gravity'] is None and launch['loads'] == [] and launch['strut_mode'] == 'bilateral'
    assert [network.nn,network.ne,network.ng,network.nc,network.size,system.size] == request['dimensions']
    assert network.operating.count == 6 and state_layout(system) == request['layout']
    assert dict(L=network.L,F=network.F,V=system.V,W=system.W,Gamma_scale=network.gamma_scale) == request['scales']
    assert network.nfev == 0 and np.all(network.damping_times == 0)
    assert np.all(system.Omega0 == 0)
    with np.load(DATA/'inputs.npz',allow_pickle=False) as saved:
        inputs = {key:saved[key].copy() for key in saved.files}
    with np.load(DATA/'expected.npz',allow_pickle=False) as saved:
        expected = {key:saved[key].copy() for key in saved.files}
    for name, actual in (('r0',system.r0),('Q0',system.Q0),('gamma0',system.gamma0),
                         ('U0',system.U0),('base',system.base)):
        np.testing.assert_allclose(actual,inputs[name],atol=2e-13,rtol=2e-13,err_msg=name)
    assert inputs['directions'].shape == inputs['direction_rates'].shape == (4,2044)
    np.testing.assert_array_equal(inputs['control3_delta'],[1.,0.,1.,0.])
    np.testing.assert_array_equal(inputs['frequency_Hz'],[1.,1.,1.15737773741517,1.15737773741517])
    selected = np.r_[np.arange(618,1296),np.arange(1378,2044)]
    np.testing.assert_array_equal(selected,inputs['selected_rows'])

    def evaluate(z,zdot,delta):
        def forcing(state,options):
            condition = options['condition_override']
            controls = dict(condition.controls)
            controls[3] = controls.get(3,0.)+delta
            return dict(options,condition_override=replace(condition,controls=controls))
        before = network.nfev
        residual,_,_ = system.residual(z,zdot,detail=True,forcing=forcing)
        assert network.nfev == before+1
        assert network.iteration_fields is None and network.tangent_influences is None
        detail = network.last_details
        solver = detail['aero']['circulation_solver']
        assert solver['method'] == 'prescribed' and solver['evaluations'] == 0
        assert residual.shape == (2044,) and np.isfinite(residual).all()
        return dict(complete_residual=residual.copy(),selected_residual=residual[selected].copy(),
                    external_force=detail['force'].copy(),external_moment=detail['moment'].copy())
    return evaluate,inputs,expected,network


def assert_expected(actual, expected, prefix, record_property):
    maps = {key.removeprefix(prefix):value for key,value in expected.items() if key.startswith(prefix)}
    assert set(actual) == set(maps)
    metrics = {}
    for key in maps:
        np.testing.assert_allclose(actual[key],maps[key],atol=2e-7,rtol=2e-7,err_msg=key)
        metrics[key] = float(np.max(np.abs(actual[key]-maps[key]),initial=0))
    record_property('maximum_absolute_differences',json.dumps(metrics,sort_keys=True))
    record_property('array_comparisons',len(maps))


def test_loaded_daedalus_full_balance_base(loaded_balance,record_property):
    evaluate,inputs,expected,network = loaded_balance
    before = network.nfev
    zero = np.zeros(2044)
    actual = evaluate(zero,zero,0.)
    assert np.max(np.abs(actual.pop('complete_residual'))) <= 1e-8
    assert_expected(actual,expected,'base__',record_property)
    assert network.nfev-before == 1
    record_property('native_residual_calls',1)


@pytest.mark.parametrize('direction',range(4),ids=('1Hz-real','1Hz-imag','dip-real','dip-imag'))
def test_loaded_daedalus_full_balance_direction(loaded_balance,direction,record_property):
    evaluate,inputs,expected,network = loaded_balance
    before = network.nfev
    z,zdot,control = inputs['directions'][direction],inputs['direction_rates'][direction],inputs['control3_delta'][direction]
    h = 5e-4
    probes = [evaluate(factor*h*z,factor*h*zdot,factor*h*control) for factor in (-2,-1,1,2)]
    actual = {key:(probes[0][key]-8*probes[1][key]+8*probes[2][key]-probes[3][key])/(12*h)
              for key in probes[0]}
    assert_expected(actual,expected,f'd{direction}__',record_property)
    assert network.nfev-before == 4
    record_property('native_residual_calls',4)
