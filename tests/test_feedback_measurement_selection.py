"""Selected feedback channels retain the complete moving sensor measurements."""
from types import SimpleNamespace

import numpy as np
import pytest

from openswing.aero import FlightCondition
from openswing.asw import parse_asw
from openswing.feedback import CHANNELS, GLOBAL_CHANNELS, measurements
from openswing.ground import body_to_earth
from openswing.network import StaticNetwork
from openswing.source_airflow import SourceAirflowNetwork
from test_source_coupled import source
from test_source_fuselage import BODY_SOURCE


@pytest.mark.parametrize('operator', ['midpoint', 'source_surface', 'source_body'])
@pytest.mark.parametrize('partial_axes', [False, True])
@pytest.mark.parametrize('flow', ['full', 'kinematic'])
def test_selected_channels_equal_full_outputs_for_loaded_moving_sensors(
        operator, partial_axes, flow, monkeypatch):
    body = operator == 'source_body'
    text = BODY_SOURCE if body else source().replace('Sensor\n1 1 3 .3 2 .15\nEnd\n', '')
    axes = '1 0 0 1 0 0' if partial_axes else '1 .2 .3 -.1 1 2'
    tip = '2 .2 .1' if body else '.2 2 .1'
    text += f'Sensor\n1 1 1 .1 .2 .3\n7 1 3 {tip} {axes}\nEnd\n'
    model = parse_asw(text, beam_interpolation='drela-segspl-v1')
    condition = FlightCondition(speed=13., alpha=3., beta=2., density=1.2, mach=0.,
        sensor_flow=flow, rates=[.03, -.02, .01], acceleration=[.1, .2, -.3],
        angular_acceleration=[.04, .01, -.02])
    cls = StaticNetwork if operator == 'midpoint' else SourceAirflowNetwork
    network = cls(model, 4, condition, [1., -2., -9.], [])
    rng = np.random.default_rng(4201)
    x = rng.normal(0., .002, network.size)
    local = tuple(rng.normal(0., .02, (network.nn, 3)) for _ in range(4))
    _, data = network.residual(x, detail=True, elastic_motion=local,
        circulation_rate=np.zeros(network.circulation_basis.panels))
    state = SimpleNamespace(orientation=body_to_earth([17., -11., 28.]),
        position=np.array([2., 3., 4.]), U=np.array([-12., 1., 2.]))
    full = measurements(network, state, data)
    active = [key+'[7]' for key in CHANNELS if not key.startswith(('F', 'M')) and key != 'Cr']
    def forbidden(*args, **kwargs):
        pytest.fail('Unused section strain/stress recovered during kinematic feedback')
    with monkeypatch.context() as patch:
        patch.setattr('openswing.feedback.recover_structure', forbidden)
        selected = measurements(network, state, data, active)
        for key in active:
            assert selected[key] == full[key], key
        assert not any(key.endswith('[1]') for key in selected)
        globals_only = measurements(network, state, data, sorted(GLOBAL_CHANNELS))
        assert globals_only == {key: full[key] for key in GLOBAL_CHANNELS}
        assert measurements(network, state, data, []) == globals_only
    for key in ['Fc[7]', 'Ms[7]', 'Cr[7]']:
        assert measurements(network, state, data, [key])[key] == full[key]
