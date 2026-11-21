"""Manual K/F plume direction, independently observed away from the wing."""
from pathlib import Path
import numpy as np
import pytest
from openswing.asw import parse_asw
from openswing.aero import FlightCondition, evaluate_aerodynamics
from openswing.geometry import model_meshes


@pytest.mark.parametrize('frozen', [True, False])
def test_plume_centerline_follows_frozen_wake_in_loads_sensors_and_survey(frozen):
    c = FlightCondition(speed=30, alpha=10, beta=20, mach=0, stall=False,
                        freeze_influences=frozen, powers={1:250})
    origin = np.array([-2., 0., -.3]); e = c.vectors()[0]
    probes = origin+20*np.array([[1., 0., 0.], e])
    source = Path('examples/rectangular.asw').read_text()+'''
Engine
1 0 1 0 -2 0 -.3 -1 0 0 1 0 1.2 150 0
End
Weight
1 0 18 0 -.3 0 .04
End
Sensor
1 1 0 18 0 -.3
End
'''
    model = parse_asw(source); meshes = model_meshes(model, 4)
    gamma = np.zeros(sum(len(m.tm) for m in meshes if m.beam.lifting))
    result = evaluate_aerodynamics(model, c, meshes, gamma, survey_positions=probes)
    jet = np.array(result['flow_survey']['velocity_body']['jet'])
    inside, outside = (0, 1) if frozen else (1, 0)
    assert jet[inside, 0] > .01
    np.testing.assert_array_equal(jet[outside], 0.)
    # Plume centerline and momentum direction are distinct: this engine's
    # thrust axis remains x-directed even when the slow wake is wind-aligned.
    np.testing.assert_array_equal(jet[:, 1:], 0.)
    np.testing.assert_allclose(result['sensor_airflow'][0]['induced_velocity'], jet[0], atol=2e-14)
    velocity = c.speed*e+jet[0]
    expected = .5*model.constants[1]*.04*np.linalg.norm(velocity)*velocity
    np.testing.assert_allclose(result['point_forces'][0], expected, rtol=2e-13, atol=2e-13)
