"""Original-residual alternatives, admissible kinks, and actual mass mechanics."""
from pathlib import Path
import numpy as np
import pytest
from openswing.aero import AnalysisError, FlightCondition
from openswing.asw import parse_asw
from openswing.control_expressions import Expression
from openswing.feedback import FeedbackSystem
from openswing.root_diagnostics import controller_alternatives
from openswing import time_integration as api
from openswing import time_accuracy


CLIP = lambda x: np.clip(x, 0., 1.)
SCALARS = [
    ('clip_exact', lambda v: np.array([v[0]-CLIP(v[0])]), [0.], [0], True),
    ('clip_near', lambda v: np.array([v[0]-CLIP(v[0])]), [-1e-9], [0], True),
    ('coupled_family', lambda v: np.array([v[0]-v[1]-v[2], v[1]-CLIP(v[1]), v[2]-.3*v[1]]), [0., 0., 0.], [1, 2], True),
    ('unique_kink', lambda v: np.array([v[0]+CLIP(v[0])]), [0.], [0], False),
    ('explicit_saturation', lambda v: np.array([v[0], v[1]-v[2], v[2]-CLIP(-.2*v[0])]), [0., 0., 0.], [2], False),
    ('coupled_saturation', lambda v: np.array([v[0]-v[1]-v[2], v[1]+.2*CLIP(v[2]), v[2]-.3*CLIP(v[1])]), [0., 0., 0.], [1, 2], False),
    ('smooth_abs_squared', lambda v: np.array([v[0]+abs(v[0])**2]), [0.], [0], False),
    ('unique_hybrid', lambda v: v+np.maximum(v[0]-v[1], 0), [0., 0.], [0, 1], False),
    ('smooth_without_callback', lambda v: 2*v, [0.], None, False),
]


@pytest.mark.parametrize('name,residual,initial,rows,ambiguous', SCALARS, ids=[c[0] for c in SCALARS])
def test_original_residual_alternatives_and_unique_kinks(name, residual, initial, rows, ambiguous):
    x = np.array(initial)
    cache = {}
    def function(v):
        cache['x'] = v.copy()
        return residual(v)
    if rows is not None:
        function.accepted_root_diagnostic = controller_alternatives(rows, 1e-8)
    if ambiguous:
        with pytest.raises(api.UnresolvedControllerAuthority) as caught:
            api.newton(function, x, 1e-8, check_rank=True)
        witness = caught.value.accepted_root_witness
        trials = np.array(witness['trials'])
        actual = np.array([residual(v) for v in trials])
        np.testing.assert_array_equal(actual, witness['residuals'])
        assert np.max(abs(actual)) <= 1e-8
        assert np.min(np.max(abs(np.diff(np.vstack([x, trials]), axis=0)), axis=1)) > 1e-6
        assert witness['centered_predicted_first_change'] > 32e-8
    else:
        value, *_ = api.newton(function, x, 1e-8, check_rank=True)
        np.testing.assert_array_equal(value, x)
    if rows is not None:
        np.testing.assert_array_equal(cache['x'], x)


def test_only_nonsmooth_expression_requests_optional_probe():
    controller = FeedbackSystem.__new__(FeedbackSystem)
    controller.expressions = [Expression("actuator('E1')-.2")]
    assert controller.root_diagnostic([0], 1e-8) is None
    controller.expressions = [Expression("actuator('E1')-clip(actuator('E1'),0,1)")]
    assert callable(controller.root_diagnostic([0], 1e-8))


@pytest.mark.parametrize('error', [AnalysisError, ValueError, FloatingPointError, None, RuntimeError])
def test_optional_domain_probe_preserves_root_and_programming_errors(error):
    cache, trials = {}, []
    def function(x):
        cache['x'] = x.copy()
        trials.append(x.copy())
        if abs(x[0]) > 1e-5:
            if error is None:
                return np.array([np.nan])
            raise error('Declared domain or programming exception')
        return np.array([x[0]+CLIP(x[0])])
    function.accepted_root_diagnostic = controller_alternatives([0], 1e-8)
    if error is RuntimeError:
        with pytest.raises(RuntimeError, match='Declared domain'):
            api.newton(function, np.zeros(1), 1e-8, check_rank=True)
    else:
        value, *_ = api.newton(function, np.zeros(1), 1e-8, check_rank=True)
        np.testing.assert_array_equal(value, [0.])
    np.testing.assert_array_equal(cache['x'], [0.])
    assert all(abs(x[0]) <= 1e-5 for x in trials[:3])
    assert any(abs(x[0]) > 1e-5 for x in trials)


@pytest.mark.parametrize('unavailable', [False, True], ids=['scaled_regular', 'optional_solve_unavailable'])
def test_optional_raw_solve_does_not_override_balanced_rank(monkeypatch, unavailable):
    cache, calls = {}, []
    def function(x):
        cache['x'] = x.copy()
        return np.array([1e150*x[0], 1e-150*x[1]])
    function.accepted_root_diagnostic = controller_alternatives([0, 1], 1e-8)
    if unavailable:
        def solve(a, b):
            calls.append((a, b))
            raise np.linalg.LinAlgError('Unavailable optional diagnostic')
        monkeypatch.setattr(np.linalg, 'solve', solve)
    value, *_ = api.newton(function, np.zeros(2), 1e-8, check_rank=True)
    np.testing.assert_array_equal(value, [0., 0.])
    np.testing.assert_array_equal(cache['x'], value)
    if unavailable:
        assert len(calls) == 1


def test_malformed_controller_row_remains_visible():
    def function(x):
        return x
    function.accepted_root_diagnostic = controller_alternatives([2], 1e-8)
    with pytest.raises(ValueError, match='row ownership'):
        api.newton(function, np.zeros(1), 1e-8, check_rank=True)


def body():
    # One kilogram at the common mass/thrust/reference origin, no aero or jet.
    source = Path('examples/guided-body.asw').read_text()
    return parse_asw(source+'\nEngine\n1 0 1 0 0 0 0 1 0 0 1 0 -1 0 0\nEnd\n')


def public_solve(output, *, order=1, checked=False, progress=None):
    return api.solve_time(body(), FlightCondition(speed=10., alpha=0., mach=0.),
        panels=4, gravity=[0., 0., 0.], duration=.02, dt=.02, order=order,
        frame='free', controller={'outputs':[{'actuator':'E1', **output}]},
        accuracy={'rtol':.1, 'atol':.001} if checked else None, progress=progress)


def test_public_cold_clipping_family_rejected_before_march():
    progress = []
    with pytest.raises(api.UnresolvedControllerAuthority) as caught:
        public_solve({'residual':"actuator('E1')-clip(actuator('E1'),0,1)"},
            progress=lambda *row: progress.append(row))
    witness = caught.value.accepted_root_witness
    assert max(abs(v) for row in witness['residuals'] for v in row) <= witness['tolerance']
    assert [row for row in progress if not isinstance(row[0],str)] == []


@pytest.mark.parametrize('order,checked', [(1, False), (5, False), (1, True), (5, True)],
    ids=['bdf', 'radau', 'checked_bdf', 'checked_radau'])
def test_public_time_opening_family_refused_without_retry(order, checked):
    progress = []
    with pytest.raises(api.UnresolvedControllerAuthority) as caught:
        public_solve({'residual':"actuator('E1')-clip(actuator('E1'),0,time)"},
            order=order, checked=checked, progress=lambda *row: progress.append(row))
    assert [row for row in progress if not isinstance(row[0],str)] == [(0., 0)]
    witness = caught.value.accepted_root_witness
    assert max(abs(v) for row in witness['residuals'] for v in row) <= witness['tolerance']
    # Read the real failure context; do not intercept or replace a solver call.
    frames = []
    owner = time_accuracy.integrate if checked else api.integrate
    tb = caught.value.__traceback__
    while tb is not None:
        if tb.tb_frame.f_code is owner.__code__:
            frames.append(tb.tb_frame)
        tb = tb.tb_next
    assert len(frames) == 1
    local = frames[0].f_locals
    assert len(local['snapshots']) == 1 and local['time'] == .02
    assert local['nonlinear_retries' if checked else 'rejected'] == 0


@pytest.mark.parametrize('order', [1, 5], ids=['bdf', 'radau'])
def test_public_unique_saturation_boundary_preserves_mass_mechanics(order):
    # F = clip(.3-.5*a,0,.2), F = m*a with m=1, has unique F=a=.2.
    result = public_solve({'expression':"clip(.3-.5*measurement('Ax'),0,.2)"}, order=order)
    assert result['converged'] and result['accepted_steps'] == 1
    assert result['rejected_steps'] == 0
    for row in result['snapshots']:
        assert row['feedback']['actuators']['E1'] == pytest.approx(.2, abs=1e-7)
        np.testing.assert_allclose(row['frame']['acceleration_reference_body'], [.2, 0., 0.], atol=1e-7)
        assert row['residual'] <= 1e-8
    final = result['snapshots'][-1]
    assert final['frame']['velocity_origin_body'][0] == pytest.approx(-10+.2*.02, abs=1e-8)
    assert final['frame']['position_earth'][0] == pytest.approx(-10*.02+.2*.02**2*(1 if order==1 else .5), abs=1e-8)
    if order == 5:
        assert final['collocation']['maximum_stage_residual'] <= final['collocation']['stage_tolerance']
