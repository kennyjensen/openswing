"""A free two-mass oscillator crosses a wire's slack/taut boundary.

The exact solution is two sinusoidal arcs joined with continuous position and
velocity at the known wire length. Internal brace forces cannot accelerate
the aircraft center of mass.
"""
from copy import deepcopy
import numpy as np
import pytest

from openswing.bridge import dispatch
from openswing.time_state import checkpoint
from test_source_struts import source, policy, SOURCE_MOVING, PANELS, retain
from test_source_moving_time import spring_state, earth_com


KB = 360/2.2
Q0 = -.3
QB = -.2
QE = -KB*.2/(100+KB)
WT = np.sqrt((100+KB)*(1/2+1/3))
WS = np.sqrt(100*(1/2+1/3))
TC = np.arccos((QB-QE)/(Q0-QE))/WT
VC = -(Q0-QE)*WT*np.sin(WT*TC)


def exact(time):
    if time <= TC:
        return np.array([QE+(Q0-QE)*np.cos(WT*time), -(Q0-QE)*WT*np.sin(WT*time)])
    tau = time-TC
    return np.array([QB*np.cos(WS*tau)+VC/WS*np.sin(WS*tau),
                     -QB*WS*np.sin(WS*tau)+VC*np.cos(WS*tau)])


def request(dt=.0025, duration=.18):
    # Start at a taut static equilibrium, then remove the force. Wire rest
    # extension is +.2 m; its force vanishes at q=-.2 m during the release.
    initial_force = (100+KB)*Q0+KB*.2
    return dict(action='time', mode='time', source=source(.2), panels=deepcopy(PANELS),
        numerics=policy(SOURCE_MOVING), strut_mode='wire', condition=None, loads=[],
        initial_loads=[dict(beam=1, t=3, force=[0., initial_force, 0.]),
                       dict(beam=1, t=1, force=[0., -initial_force, 0.])],
        time=dict(frame='free', duration=duration, dt=dt, order=2, gravity_magnitude=0., tolerance=1e-10))


@pytest.fixture(scope='module')
def histories():
    results = []
    for dt in (.005, .0025):
        value = request(dt); before = deepcopy(value)
        result = dispatch(value)
        assert value == before and result['converged']
        retain(f'wire-crossing-{dt}', result)
        results.append(result)
    return results


def test_wire_crossing_refines_to_piecewise_exact_motion_and_conserves_com(histories):
    errors = []
    for result in histories:
        states = result['snapshots']
        assert not states[0]['struts'][0]['slack'] and states[-1]['struts'][0]['slack']
        com0, _ = earth_com(states[0])
        error = 0.
        for row in states:
            time = row['time']; actual = spring_state(row)
            error = max(error, float(np.max(abs((actual-exact(time))/[.3, 3.]))))
            com, velocity = earth_com(row)
            np.testing.assert_allclose(com, com0, atol=2e-9)
            np.testing.assert_allclose(velocity, 0., atol=2e-9)
            assert row['struts'][0]['tension'] >= 0
            if row['struts'][0]['slack']:
                assert row['struts'][0]['energy'] == 0
        errors.append(error)
    assert errors[1] < .35*errors[0]
    assert errors[1] < .004
    retain('wire-crossing-accuracy', dict(errors=errors, crossing_time=TC, crossing_velocity=VC))


def test_wire_checkpoint_continues_across_transition_without_changing_law(histories):
    first = dispatch(request(.0025, .06))
    saved = checkpoint(first, len(first['snapshots'])-1)
    assert saved['context']['setup']['strut_mode'] == 'wire'
    resumed = dispatch(dict(action='resume_time', mode='time', source=source(.2),
        numerics=policy(SOURCE_MOVING), checkpoint=saved, time=dict(duration=.12)))
    assert resumed['converged']
    actual, expected = resumed['snapshots'][-1], histories[1]['snapshots'][-1]
    np.testing.assert_allclose(spring_state(actual), spring_state(expected), rtol=3e-8, atol=3e-10)
    assert actual['struts'][0]['slack']
    retain('wire-checkpoint', saved)
    retain('wire-resumed', resumed)


def test_saved_wire_setup_cannot_be_overridden_by_request(histories):
    saved = checkpoint(histories[0], 1)
    with pytest.raises(ValueError, match='Unsupported source-discrete request options'):
        dispatch(dict(action='resume_time', mode='time', source=source(.2), numerics=policy(SOURCE_MOVING),
                      checkpoint=saved, strut_mode='bilateral', time=dict(duration=.01)))
