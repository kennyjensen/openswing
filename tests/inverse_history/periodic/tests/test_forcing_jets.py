"""Independent cubic/units/branch checks; no time solve or browser execution."""
from dataclasses import FrozenInstanceError
from pathlib import Path
from types import SimpleNamespace
import json
import numpy as np
import pytest
from openswing.aero import AnalysisError, FlightCondition
from openswing.asw import parse_asw
from openswing.forcing import TimeForcing
from openswing.inertia import Motion

MODEL = Path(__file__).parents[1]/'source/examples/inertial.asw'


def table(text, *, condition=None, motion=None, frame='prescribed', **kwargs):
    c = FlightCondition(controls={1: 3}) if condition is None else condition
    m = parse_asw(MODEL.read_text())
    return TimeForcing(text, m, c, c.motion() if motion is None else motion,
                       20., frame, **kwargs)


def natural(t, derivative, side='right'):
    """Analytic natural cubic through (0,0),(1,1),(2,0)."""
    if t < 1 or (t == 1 and side == 'left'):
        return [1.5*t-.5*t**3, 1.5-1.5*t*t, -3*t, -3., 0.][derivative]
    u = 2-t
    return [1.5*u-.5*u**3, -1.5+1.5*u*u, -3*u, 3., 0.][derivative]


def test_independent_natural_cubic_and_derivatives_include_ordinary_knot_sides():
    f = table('time F1\n0 0\n1 1\n2 0')
    for t in [0., .13, .6, 1., 1.4, 1.9, 2.]:
        for side in ['left', 'right']:
            for k in range(5):
                assert f.values(t, side, derivative=k)['F1'] == pytest.approx(natural(t, k, side))
    assert f.values(1., 'left', derivative=3)['F1'] == -3
    assert f.values(1., 'right', derivative=3)['F1'] == 3


def test_time_scaling_shift_value_scaling_and_relative_offset_chain_rule():
    # t=5+2q, y=7+6*p(q), and +F1 contributes the initial 3 only at k=0.
    f = table('time +F1\n* 2 6\n+ 5 7\n0 0\n1 1\n2 0', start_time=5.)
    for q in [0., .3, 1., 1.5, 2.]:
        for side in ['left', 'right']:
            for k in range(5):
                expected = 6*natural(q, k, side)/2**k + (10 if k == 0 else 0)
                assert f.values(5+2*q, side, derivative=k)['F1'] == pytest.approx(expected)
    assert f.first_time == 5
    assert f.end_time == 9
    assert f.values(9.01, derivative=0)['F1'] == 0
    jet = f.local_jet(5.)
    for t in [4.9, 5., 6., 7.1]:
        q = (t-5)/2
        expected = [10+6*(1.5*q-.5*q**3), 3*(1.5-1.5*q*q), -4.5*q, -2.25, 0]
        for k in range(5):
            assert jet.values(t, derivative=k)['F1'] == pytest.approx(expected[k])


def test_doubled_time_independent_cubics_and_sided_jets():
    # First branch p(t); second branch 5+2*p((t-2)/2), on [2,6].
    f = table('time F1\n0 0\n1 1\n2 0\n2 5\n4 7\n6 5')
    expected_left = [0., -1.5, 0., 3., 0.]
    expected_right = [5., 1.5, 0., -.75, 0.]
    for side, expected in [('left', expected_left), ('right', expected_right)]:
        jet = f.local_jet(2., side)
        for k in range(5):
            assert f.values(2., side, derivative=k)['F1'] == pytest.approx(expected[k])
            assert jet.values(2., derivative=k)['F1'] == pytest.approx(expected[k])
        for t in [1.8, 2.2]:
            if side == 'left':
                u = 2-t
                oracle = [1.5*u-.5*u**3, -1.5+1.5*u*u, -3*u, 3., 0.]
            else:
                u = (t-2)/2
                oracle = [5+3*u-u**3, 1.5-1.5*u*u, -1.5*u, -.75, 0.]
            for k in range(5):
                assert jet.values(t, derivative=k)['F1'] == pytest.approx(oracle[k])
    assert f.local_jet(2., 'left').report()['channels'][0]['interval'] == [1., 2.]
    assert f.local_jet(2., 'right').report()['channels'][0]['interval'] == [2., 4.]
    assert f.values(np.nextafter(2., -np.inf))['F1'] == pytest.approx(0, abs=1e-14)
    assert f.values(np.nextafter(2., np.inf))['F1'] == pytest.approx(5)


def test_angular_target_units_offsets_and_all_derivative_orders():
    f = table('time +Gz\n* 2 180\n0 0\n1 1\n2 0', frame='free',
              actuator_constraints=[dict(variable='control.1', quantity='angular_acceleration.z', target=np.pi/4)])
    for q in [0., .3, 1., 1.6, 2.]:
        for side in ['left', 'right']:
            for k in range(5):
                degrees = 180*natural(q, k, side)/2**k+(45 if k == 0 else 0)
                assert f.values(2*q, side, derivative=k)['Gz'] == pytest.approx(degrees)
                assert f.targets(2*q, side, derivative=k)['angular_acceleration.z'] == pytest.approx(np.deg2rad(degrees))
    jet = f.local_jet(0.)
    assert jet.targets(-.2, derivative=1)['angular_acceleration.z'] == pytest.approx(np.pi/2*(1.5-1.5*.1**2))
    assert f.targets(4.1, derivative=0) == {'angular_acceleration.z': 0.}
    assert f.local_jet(4., 'right').targets(3.9) == {'angular_acceleration.z': 0.}
    # Physical apply does not overwrite an inverse target's acceleration.
    c, motion = f.apply(.5, FlightCondition(controls={1: 3}), Motion(angular_acceleration=[1,2,3]))
    np.testing.assert_array_equal(motion.angular_acceleration, [1,2,3])
    assert c.controls == {1: 3}


def test_physical_support_and_end_compatibility_are_distinct_from_sided_jets():
    f = table('time +F1\n1 2\n2 4', start_time=1.)
    for k in range(5):
        with pytest.raises(AnalysisError, match='before the first'):
            f.values(.99, derivative=k)
        for side in ['left', 'right']:
            assert f.values(1., side, derivative=k)['F1'] == pytest.approx([5,2,0,0,0][k])
            assert f.values(2., side, derivative=k)['F1'] == pytest.approx([7,2,0,0,0][k])
            assert f.values(2.01, side, derivative=k)['F1'] == 0
    with pytest.raises(AnalysisError, match='prehistory'):
        f.local_jet(.99)
    with pytest.raises(AnalysisError, match='prehistory'):
        f.local_jet(1., 'left')
    assert f.local_jet(1., 'right').values(.99)['F1'] == pytest.approx(4.98)
    left, right = f.local_jet(2., 'left'), f.local_jet(2., 'right')
    assert left.values(2.1)['F1'] == pytest.approx(7.2)
    for t in [1.9, 2., 2.1]:
        for k in range(5):
            assert right.values(t, derivative=k)['F1'] == 0
            assert f.local_jet(2.1, 'left').values(t, derivative=k)['F1'] == 0
    assert f.values(2., 'right')['F1'] == 7
    assert f.values(2.1)['F1'] == 0
    assert right.report()['branch'] == 'zero cutoff'
    assert right.report()['physical_lookup'] is False
    assert 'end-right is zero' in f.report()['local_jet']


def test_ordinary_knot_local_jet_continues_chosen_polynomial_not_next_one():
    f = table('time F1\n0 0\n1 1\n2 0')
    left, right = f.local_jet(1., 'left'), f.local_jet(1., 'right')
    for t in [.8, 1.2]:
        for k in range(5):
            l = [1.5*t-.5*t**3, 1.5-1.5*t*t, -3*t, -3., 0.][k]
            u = 2-t
            r = [1.5*u-.5*u**3, -1.5+1.5*u*u, -3*u, 3., 0.][k]
            assert left.values(t, derivative=k)['F1'] == pytest.approx(l)
            assert right.values(t, derivative=k)['F1'] == pytest.approx(r)
    assert left.values(1.2)['F1'] != pytest.approx(f.values(1.2)['F1'])
    assert right.values(.8)['F1'] != pytest.approx(f.values(.8)['F1'])


def test_jet_freezes_commands_offsets_coefficients_and_channel_mapping():
    controller = SimpleNamespace(signals={'V'}, commands={'V': 7.})
    f = table('time +V\n0 2\n1 4', controller=controller)
    jet = f.local_jet(.4)
    assert jet.values(.3)['V'] == pytest.approx(9.6)
    f.bind_commands({'V': 70.})
    assert f.values(.3)['V'] == pytest.approx(72.6)
    assert jet.values(.3)['V'] == pytest.approx(9.6)
    assert jet.values(.3, derivative=1)['V'] == 2
    f.channels[0]['distribution']._segments[0][2].c[:] = 0
    f.channels[0]['initial'] = 900
    f.channels[0]['name'] = 'changed'
    f.source = 'changed'
    assert jet.values(.3)['V'] == pytest.approx(9.6)
    assert jet.source.startswith('time +V')
    assert jet.report()['channels'][0]['initial'] == 7
    assert jet.targets(.3) == {}
    report = jet.report()
    report['channels'][0]['derivatives'][0] = 0
    assert jet.values(.3)['V'] == pytest.approx(9.6)
    json.dumps(jet.report())
    with pytest.raises(FrozenInstanceError):
        jet.anchor = 0
    with pytest.raises(FrozenInstanceError):
        jet.channels[0].initial = 0


def test_jet_apply_preserves_unchanged_settings_and_uses_table_units():
    f = table('time +F1 Gz Ax\n0 0 0 2\n2 4 180 6')
    jet = f.local_jet(0.)
    c = FlightCondition(controls={1: 3}, powers={8: .25})
    initial = Motion(rates=[.1,.2,.3], acceleration=[0,8,9], angular_acceleration=[4,5,6])
    c2, m2 = jet.apply(-.2, c, initial)
    assert c2.controls == {1: pytest.approx(2.6)}
    assert c2.powers == {8: .25}
    np.testing.assert_allclose(m2.acceleration, [1.6,8,9])
    np.testing.assert_allclose(m2.angular_acceleration, [4,5,-np.pi/10])
    np.testing.assert_array_equal(m2.rates, initial.rates)
    assert c.controls == {1: 3}
    np.testing.assert_array_equal(initial.acceleration, [0,8,9])
    for t in [0., .3, 2.]:
        pc, pm = f.apply(t, c, initial)
        jc, jm = jet.apply(t, c, initial)
        assert pc.controls == jc.controls
        np.testing.assert_allclose(pm.acceleration, jm.acceleration)
        np.testing.assert_allclose(pm.angular_acceleration, jm.angular_acceleration)


@pytest.mark.parametrize('bad', [-1, 1.5, 1., True, np.bool_(False), '1', None, float('nan'), np.array(1)])
def test_invalid_derivative_order_rejected_by_physical_and_jet_apis(bad):
    f = table('time F1\n0 0\n1 2')
    jet = f.local_jet(0.)
    for obj in [f, jet]:
        for method in [obj.values, obj.targets]:
            with pytest.raises(AnalysisError, match='nonnegative integer'):
                method(.5, derivative=bad)


@pytest.mark.parametrize('bad', [True, np.bool_(False), float('nan'), float('inf'), -float('inf'), '0', None, 1j, [1], np.array(.5), 10**400])
def test_invalid_scalar_time_rejected_consistently(bad):
    f = table('time F1\n0 0\n1 2')
    jet = f.local_jet(0.)
    for method in [f.values, f.targets, f.local_jet, jet.values, jet.targets]:
        with pytest.raises(AnalysisError, match='finite real scalar'):
            method(bad)


@pytest.mark.parametrize('bad', ['outside', '', None, True, ['left']])
def test_invalid_side_rejected_including_high_order_and_empty_tables(bad):
    for f in [table('time F1\n0 0\n1 2'), table('')]:
        for method in [f.values, f.targets]:
            with pytest.raises(AnalysisError, match='left/right'):
                method(.5, bad, derivative=4)
        with pytest.raises(AnalysisError, match='left/right'):
            f.local_jet(.5, bad)


def test_empty_forcing_and_numpy_scalar_orders():
    f = table('')
    for k in [0, np.int64(1), 4, 100]:
        assert f.values(np.float64(.2), derivative=k) == {}
        assert f.targets(np.int64(2), derivative=k) == {}
        jet = f.local_jet(-1., 'left')
        assert jet.values(100., derivative=k) == {}
        assert jet.targets(100., derivative=k) == {}
        assert jet.report()['branch'] == 'empty'
    full = table('time F1\n0 0\n1 2')
    assert full.values(np.float64(.2), derivative=np.int64(1))['F1'] == 2
    assert full.values(.2, derivative=100)['F1'] == 0
