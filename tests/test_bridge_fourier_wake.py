"""Browser packets must preserve the optional wake check and its scope."""
import json
from pathlib import Path
import pytest
from openswing.bridge import run_json


def packet(**extra):
    return dict(action='solve', mode='rigid', source=Path('examples/rectangular.asw').read_text(),
                panels=16, condition=dict(speed=30., alpha=5., mach=0., circulation_modes={'1':6}), **extra)


def run(request):
    return json.loads(run_json(json.dumps(request)))


def test_json_wake_check_preserves_solver_outputs_and_exports_finite_reference():
    request = packet()
    original = run(request)
    result = run(dict(request, fourier_wake_diagnostic=True))
    reference = result['trefftz'].pop('continuous_fourier')
    assert reference['available'] and reference['CDi'] > 0
    assert reference['efficiency'] > 0
    assert reference['trace_groups'] == [[0]]
    assert result == original


def test_pointwise_solution_is_retained_with_an_explicit_unavailable_reason():
    request = packet(fourier_wake_diagnostic=True)
    request['condition']['circulation_modes'] = {}
    result = run(request)
    reference = result['trefftz']['continuous_fourier']
    assert result['converged'] and result['CDi'] > 0
    assert reference['available'] is False
    assert reference['CDi'] is None and reference['efficiency'] is None
    assert 'Fourier basis' in reference['reason']


def test_rigid_angle_stack_keeps_each_diagnostic_and_initialization_choice():
    request = packet(fourier_wake_diagnostic=True)
    request.update(action='operating_points', operating_points=dict(
        points=[dict(condition=dict(alpha=3.)), dict(condition=dict(alpha=5.))], initialization='previous'))
    result = run(request)
    assert result['converged_points'] == result['total_points'] == 2
    for point in result['points']:
        assert point['result']['trefftz']['continuous_fourier']['available']
    assert result['points'][1]['initialization']['kind'] == 'previous_point'


@pytest.mark.parametrize('value', [1, 'true', None, [], {}])
def test_json_wake_option_rejects_nonboolean_before_parsing(value):
    with pytest.raises(ValueError, match='must be boolean'):
        run(dict(action='solve', source='invalid', fourier_wake_diagnostic=value))


@pytest.mark.parametrize('action,mode', [('solve', 'mounted'), ('operating_points', 'mounted'),
                                        ('time', 'rigid'), ('inspect', 'rigid')])
def test_unimplemented_analysis_routes_do_not_silently_ignore_requested_check(action, mode):
    with pytest.raises(ValueError, match='rigid steady'):
        run(dict(action=action, mode=mode, source='invalid', fourier_wake_diagnostic=True))
