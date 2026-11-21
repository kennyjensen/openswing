"""Full modal workflow must retain the ungrouped physical descriptor pencil."""
from pathlib import Path

import numpy as np
import pytest
from scipy.optimize import linear_sum_assignment

from openswing.aero import FlightCondition
from openswing.asw import parse_asw
from openswing.bridge import dispatch
from openswing.linear_dynamics import eigensystem, linearize, make_system


SOURCE = (Path(__file__).parent / 'fixtures/isae-zero-area.asw').read_text()


@pytest.mark.parametrize('operator,lag,circulation_modes', [
    ('midpoint-v1', True, None),
    ('drela-moving-airflow-v1', True, None),
    ('drela-moving-airflow-v1', False, None),
    ('drela-moving-vacuum-v1', True, None),
    ('drela-moving-airflow-v1', True, {1: 3}),
    ('drela-moving-airflow-v1', False, {1: 3}),
])
def test_full_modal_analysis_matches_ungrouped_loaded_pencil(operator, lag, circulation_modes):
    condition = None if operator == 'drela-moving-vacuum-v1' else dict(
        speed=10, alpha=0, beta=1, mach=0, gravity_magnitude=0, aero_lag=lag)
    if circulation_modes is not None:
        condition['circulation_modes'] = circulation_modes
    numerics = dict(beam_interpolation='natural-v1' if operator == 'midpoint-v1' else 'drela-segspl-v1',
                    structural_operator=operator)
    options = dict(frame='fixed', count=4, shift=[-.1, 50.], method='full_shift_invert', matrices=True)
    request = dict(action='modes', source=SOURCE, numerics=numerics, panels=4,
                   modes=options, gravity=[0, 0, 0])
    if condition is not None:
        request['condition'] = condition
    else:
        request.pop('gravity')
        options['gravity_magnitude'] = 0
    result = dispatch(request)
    system, _ = make_system(parse_asw(SOURCE, beam_interpolation=numerics['beam_interpolation']),
        None if condition is None else FlightCondition(**condition), 4,
        frame='fixed', gravity=request.get('gravity'), structural_operator=operator,
        gravity_magnitude=options.get('gravity_magnitude'))
    original_a, original_m = linearize(system)
    original_modes, _ = eigensystem(original_a, original_m, time_scale=system.W,
                                    count=options['count'], shift=options['shift'], method=options['method'])
    scale = np.maximum(np.maximum(np.max(abs(original_a), axis=1),
                                  np.max(abs(original_m * system.W), axis=1)), 1e-30)
    np.testing.assert_allclose(np.asarray(result['matrices']['A']) / scale[:, None],
                               original_a / scale[:, None], atol=2e-7, rtol=2e-7)
    np.testing.assert_allclose(np.asarray(result['matrices']['M']) * system.W / scale[:, None],
                               original_m * system.W / scale[:, None], atol=2e-7, rtol=2e-7)
    roots = np.asarray([complex(*m['eigenvalue']) for m in result['modes']])
    expected = np.asarray([complex(*m['eigenvalue']) for m in original_modes])
    rows, columns = linear_sum_assignment(abs(expected[:, None] - roots))
    np.testing.assert_allclose(roots[columns], expected[rows], atol=2e-7, rtol=2e-7)
    assert result['diagnostics']['matrix_assembly']['structured']
    assert result['diagnostics']['base_residual'] < 1e-8
    for mode in result['modes']:
        assert max(mode['right_backward_error'], mode['left_backward_error']) < 1e-8
    if condition is not None:
        assert abs(result['base']['force'][1]) > .01
