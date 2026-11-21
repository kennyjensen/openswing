"""Owned material diagnostics stay exact across states, edits and exports."""
from pathlib import Path
from unittest.mock import patch
import numpy as np
from openswing.asw import parse_asw
from openswing.network import StaticNetwork
from openswing.damping import damping_diagnostics


def network():
    return StaticNetwork(parse_asw(Path('examples/flexible.asw').read_text()), 4, None, [0, 0, 0], [])


def test_moving_states_reuse_material_check_and_reports_are_independent():
    n = network()
    z = np.zeros_like(n.rj)
    x = np.zeros(n.size)
    with patch('openswing.damping.damping_diagnostics', wraps=damping_diagnostics) as check:
        _, first = n.residual(x, detail=True, elastic_motion=(z, z, z, z))
        x[0] += .01
        _, second = n.residual(x, detail=True, elastic_motion=(z+.02, z, z, z))
        assert check.call_count == 1
        assert first['damping'] == second['damping'] == damping_diagnostics(n.S, n.damping_times, n.ds)
        first['damping']['elements'][0]['passive'] = 'damaged'
        first['damping']['elements'].clear()
        assert n.damping_report() == second['damping']
        assert check.call_count == 1


def test_each_material_input_invalidates_for_in_place_or_replaced_values():
    n = network()
    with patch('openswing.damping.damping_diagnostics', wraps=damping_diagnostics) as check:
        n.damping_report()
        for index, name in enumerate(('S', 'damping_times', 'ds'), 2):
            array = getattr(n, name)
            array.flat[0] += .1
            assert n.damping_report() == damping_diagnostics(n.S, n.damping_times, n.ds)
            assert check.call_count == index
            setattr(n, name, array.copy())
            n.damping_report()
            assert check.call_count == index
        n.damping_times = n.damping_times+.2
        assert n.damping_report() == damping_diagnostics(n.S, n.damping_times, n.ds)
        assert check.call_count == 5


def test_failed_material_check_does_not_publish_stale_or_partial_result():
    n = network()
    before = n.damping_report()
    n.damping_times += .2
    with patch('openswing.damping.damping_diagnostics', side_effect=RuntimeError('interrupted check')):
        try:
            n.damping_report()
        except RuntimeError as exc:
            assert str(exc) == 'interrupted check'
        else:
            raise AssertionError('The new material check must run before publication.')
    after = n.damping_report()
    assert after == damping_diagnostics(n.S, n.damping_times, n.ds)
    assert after != before


def test_material_reports_belong_to_each_network():
    a, b = network(), network()
    a.damping_times += .3
    with patch('openswing.damping.damping_diagnostics', wraps=damping_diagnostics) as check:
        first, second = a.damping_report(), b.damping_report()
        assert check.call_count == 2 and first != second
        assert a.damping_report() == first and b.damping_report() == second
        assert check.call_count == 2
