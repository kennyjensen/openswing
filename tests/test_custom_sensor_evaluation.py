"""Selective trim measurements must equal complete physical sensor reports."""
from pathlib import Path
import numpy as np
import pytest

from openswing import custom_constraints as custom
from openswing.aero import AnalysisError, FlightCondition
from openswing.asw import parse_asw
from openswing.network import StaticNetwork
from openswing.operating import OperatingConstraint
from openswing.recovery import recover_structure
from openswing.sensors import UNITS, network_sensors
from openswing.source_airflow import SourceAirflowNetwork
from openswing.source_coupled import SourceCoupledNetwork


STRUCTURAL = {'force_local', 'moment_local', 'strain', 'curvature_change',
              'shell_strain', 'shell_shear_stress', 'circulation'}


def snapshot(operator='legacy', flow='full', *, singular=False, vacuum=False):
    model = parse_asw(Path('examples/instrumented-oscillator.asw').read_text(),
                      beam_interpolation='drela-segspl-v1')
    # Deliberately nonconsecutive IDs: airflow is indexed by row, not sensor ID.
    model.records['sensor'][0][0] = 4
    model.records['sensor'][1][0] = 9
    if vacuum:
        model.records['engine'] = []
    if singular:
        model.records['sensor'][1][6:12] = [1, 0, 0, 1, 0, 0]
    moving = operator != 'source-steady' and not vacuum
    condition = None if vacuum else FlightCondition(speed=11., alpha=7., beta=-4.,
        mach=0., powers={1:3.}, sensor_flow=flow, attitude=(9., -12., 17.),
        position_earth=(3., -5., 8.), gust={'type':'uniform', 'velocity':[.2, -.3, .4]},
        rates=(.1, -.2, .15) if moving else (0., 0., 0.),
        acceleration=(.3, -.4, .5) if moving else (0., 0., 0.),
        angular_acceleration=(.04, .02, -.03) if moving else (0., 0., 0.))
    cls = {'legacy':StaticNetwork, 'source-steady':SourceCoupledNetwork,
           'source-moving':SourceAirflowNetwork}[operator]
    network = cls(model, 4, condition, [0., 0., -9.81], [],
                  **({'steady_trim':True} if operator == 'source-moving' else {}))
    state = np.zeros(network.size)
    kin = state[:6*network.nn].reshape(network.nn, 6)
    kin[1:, :3] = [.002, -.003, .005]
    kin[1:, 3:] = [.04, -.03, .02]
    internal = state[6*network.nn:6*(network.nn+network.ne)].reshape(network.ne, 6)
    internal[:] = [.01, .02, -.03, .004, -.005, .006]
    options = {}
    if moving:
        fields = [np.tile(v, (network.nn, 1)) for v in
                  ([.2, -.1, .3], [.04, .02, -.03], [.5, -.3, .1], [.02, -.04, .03])]
        options['elastic_motion'] = tuple(fields)
    _, data = network.residual(state, detail=True, **options)
    elements, _ = recover_structure(network, data)
    complete = {s['index']:s for s in network_sensors(network, data, elements)}
    return network, data, complete


def equation(network, expression):
    variable = 'acceleration.y' if network.condition is None else 'power.1'
    return custom.CustomEquation(OperatingConstraint(variable=variable, quantity='user.sensor',
        target=0., expression=expression, residual_scale=1., unit='test units'),
        network.model, network.operating.base, network.condition)


def evaluate(network, data, expression):
    network.operating.custom = {'user.sensor':equation(network, expression)}
    return custom.evaluate_custom(network, data, data['operating_values'], np.zeros(3), np.zeros(3))['user.sensor']


@pytest.mark.parametrize('operator', ['legacy', 'source-steady', 'source-moving'])
@pytest.mark.parametrize('flow', ['full', 'kinematic'])
@pytest.mark.parametrize('singular', [False, True])
def test_all_nonstructural_measurements_equal_complete_report(operator, flow, singular, monkeypatch):
    network, data, complete = snapshot(operator, flow, singular=singular)
    measured = []
    original = custom.measure_sensor
    def record(row, *args, **kwargs):
        measured.append(int(row[0]))
        return original(row, *args, **kwargs)
    def forbidden(*args, **kwargs):
        pytest.fail('A nonstructural expression unnecessarily recovers section reports')
    monkeypatch.setattr(custom, 'measure_sensor', record)
    monkeypatch.setattr(custom, 'recover_structure', forbidden)
    monkeypatch.setattr(custom, 'network_sensors', forbidden)
    for field in sorted(set(UNITS)-STRUCTURAL):
        axes = custom.SENSOR_AXES.get(field)
        for component, axis in enumerate(axes or ['']):
            expression = f'sensor("9.{field}' + (f'.{axis}' if axes else '') + '")'
            reference = complete[9][field]
            if reference is not None and axes:
                reference = reference[component]
            measured.clear()
            if reference is None:
                with pytest.raises(AnalysisError, match='undefined'):
                    evaluate(network, data, expression)
            else:
                assert evaluate(network, data, expression) == reference
            assert measured == [9]
    assert evaluate(network, data, 'sensor("9.position_earth.y")-sensor("4.position_earth.y")') == (
        complete[9]['position_earth'][1]-complete[4]['position_earth'][1])
    # Undefined values stay lazy inside an unselected branch.
    if singular:
        assert evaluate(network, data, 'where(1, sensor("9.position_earth.y"), sensor("9.bank"))') == complete[9]['position_earth'][1]


@pytest.mark.parametrize('operator', ['legacy', 'source-steady', 'source-moving'])
def test_structural_and_mixed_expressions_keep_original_recovery(operator, monkeypatch):
    network, data, complete = snapshot(operator)
    calls = []
    original = custom.recover_structure
    def record(*args, **kwargs):
        calls.append(True)
        return original(*args, **kwargs)
    monkeypatch.setattr(custom, 'recover_structure', record)
    for field in sorted(STRUCTURAL):
        axes = custom.SENSOR_AXES.get(field)
        expression = f'sensor("9.{field}' + ('.s' if axes else '') + '")'
        value = complete[9][field]
        if value is not None and axes:
            value = value[1]
        before = len(calls)
        if value is None:
            with pytest.raises(AnalysisError, match='undefined'):
                evaluate(network, data, expression)
        else:
            assert evaluate(network, data, expression) == value
        assert len(calls) == before+1
    mixed = 'sensor("9.position_earth.y")+sensor("4.force_local.s")'
    assert evaluate(network, data, mixed) == complete[9]['position_earth'][1]+complete[4]['force_local'][1]
    assert evaluate(network, data, 'where(1, sensor("9.position_earth.y"), sensor("9.shell_strain"))') == complete[9]['position_earth'][1]


def test_no_airflow_keeps_position_and_rejects_undefined_flow(monkeypatch):
    network, data, complete = snapshot(vacuum=True)
    def forbidden(*args, **kwargs):
        pytest.fail('Position/flow expressions must not recover section reports')
    monkeypatch.setattr(custom, 'recover_structure', forbidden)
    assert evaluate(network, data, 'sensor("9.position_earth.z")') == complete[9]['position_earth'][2]
    with pytest.raises(AnalysisError, match='undefined'):
        evaluate(network, data, 'sensor("9.speed")')
    assert evaluate(network, data, 'where(1, sensor("9.position_earth.z"), sensor("9.speed"))') == complete[9]['position_earth'][2]
