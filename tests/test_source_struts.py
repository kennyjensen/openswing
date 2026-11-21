"""Independent composed oracles for braces in the source beam operators.

The axial fixtures reduce to two physical point masses and parallel springs.
Their stiffness, preload, force balance, poles and response are calculated here
without the production strut-law or tangent helpers.
"""
from copy import deepcopy
import json
import os
from pathlib import Path

import numpy as np
import pytest

from openswing.aero import AnalysisError, FlightCondition
from openswing.asw import parse_asw
from openswing.bridge import dispatch
from openswing.frequency_response import FrequencyAnalysis
from openswing.linear_dynamics import make_system, linearize, eigensystem
from openswing.numerical_policy import (SOURCE_DISCRETE, SOURCE_SECTION, SOURCE_COUPLED,
    SOURCE_DYNAMIC, SOURCE_QUIESCENT, SOURCE_MOVING, SOURCE_AIRFLOW)
from test_source_moving_system import AXIAL_SOURCE, PANELS, beam_source, directional
from test_source_airflow_engines import AXIAL_ENGINE


def source(rest_change=-.2, ea=360., *, engine=False):
    return (AXIAL_SOURCE+f'Strut\n1 3 0 2 0 0 4 0 {rest_change} {ea}\nEnd\n'
            +(AXIAL_ENGINE if engine else ''))


def policy(operator):
    return dict(beam_interpolation='drela-segspl-v1', structural_operator=operator)


def condition():
    return dict(speed=23., alpha=0., density=1.2, mach=0., stall=False, gravity_magnitude=0.)


def model(text):
    return parse_asw(text, beam_interpolation='drela-segspl-v1')


def retain(name, result):
    folder = os.environ.get('SOURCE_STRUT_ARTIFACTS')
    if folder:
        p = Path(folder); p.mkdir(parents=True, exist_ok=True)
        (p/(name+'.json')).write_text(json.dumps(result, allow_nan=False)+'\n')


@pytest.mark.parametrize('operator', [SOURCE_DISCRETE, SOURCE_SECTION, SOURCE_COUPLED])
@pytest.mark.parametrize('mode,rest_change', [('bilateral', 0.), ('wire', -.2), ('wire', .2)])
def test_static_parallel_stiffness_preload_and_internal_force_balance(operator, mode, rest_change):
    request = dict(action='solve', mode='mounted' if operator == SOURCE_COUPLED else 'structural',
        source=source(rest_change), panels=deepcopy(PANELS), numerics=policy(operator), strut_mode=mode,
        gravity=[0., 0., 0.], loads=[dict(beam=1, t=3, force=[0., 10., 0.])], tolerance=1e-10)
    if operator == SOURCE_COUPLED:
        request['condition'] = condition()
    before = deepcopy(request)
    result = dispatch(request)
    assert request == before and result['converged']
    slack = mode == 'wire' and rest_change > 0
    k = 0. if slack else 360./(2+rest_change)
    extension = (10-k*rest_change)/(100+k)
    np.testing.assert_allclose(result['nodes'][-1]['position'], [0., 2+extension, 0.], atol=3e-10)
    brace = result['struts'][0]
    assert brace['slack'] == slack
    assert brace['tension_only'] == (mode == 'wire')
    assert brace['tension'] == pytest.approx(-k*(extension+rest_change), abs=3e-8)
    np.testing.assert_allclose(result['applied_force'], [0., 10., 0.], atol=1e-10)
    np.testing.assert_allclose(result['applied_moment'], 0., atol=1e-10)
    assert 'strut_load_transfer' in result['output_scope']
    assert result['equilibrium_state']['identity']['structural_operator'] == operator
    retain(f'static-{operator}-{mode}-{rest_change}', result)


@pytest.mark.parametrize('operator,frame', [(SOURCE_DYNAMIC, 'fixed'), (SOURCE_QUIESCENT, 'fixed'),
    (SOURCE_MOVING, 'free'), (SOURCE_AIRFLOW, 'free')])
@pytest.mark.parametrize('mode,rest_change', [('bilateral', 0.), ('wire', -.2), ('wire', .2)])
def test_modal_parallel_spring_poles_across_media(operator, frame, mode, rest_change):
    c = FlightCondition(**condition()) if operator == SOURCE_AIRFLOW else None
    kwargs = dict(quiescent_density=1.2) if operator == SOURCE_QUIESCENT else {}
    system, _ = make_system(model(source(rest_change)), c, PANELS, frame=frame,
        gravity=[0., 0., 0.], strut_mode=mode, structural_operator=operator, tolerance=1e-10, **kwargs)
    a, m = linearize(system, step=1e-5, sparse=True)
    k = 100.+(0. if mode == 'wire' and rest_change > 0 else 360./(2+rest_change))
    omega = np.sqrt(k*(1/3 if frame == 'fixed' else 1/2+1/3))
    modes, _ = eigensystem(a.toarray(), m.toarray(), time_scale=system.W, count=1,
        shift=(-.1, omega), method='full_shift_invert')
    assert complex(*modes[0]['eigenvalue']) == pytest.approx(1j*omega, abs=2e-7)


@pytest.mark.parametrize('operator', [SOURCE_DYNAMIC, SOURCE_MOVING, SOURCE_AIRFLOW])
def test_wire_kink_keeps_nonunique_tangent_rejection(operator):
    c = FlightCondition(**condition()) if operator == SOURCE_AIRFLOW else None
    system, _ = make_system(model(source(0.)), c, PANELS, frame='fixed', gravity=[0., 0., 0.],
        strut_mode='wire', structural_operator=operator)
    with pytest.raises(AnalysisError, match='slack/taut transition'):
        linearize(system)


@pytest.mark.parametrize('frame,count', [('prescribed', 4), ('free', 4), ('free', 14)])
@pytest.mark.parametrize('mode,rest_change', [('bilateral', 0.), ('wire', -.2), ('wire', .2)])
def test_engine_to_tip_frequency_with_brace_and_reused_matrices(frame, count, mode, rest_change):
    c = FlightCondition(**condition(), powers={1: 0.})
    panels = {'default': count, 'beams': {'1': {'count': count, 'spacing': 'uniform'}}}
    analysis = FrequencyAnalysis(model(source(rest_change, engine=True)), c, panels, frame=frame,
        gravity=[0., 0., 0.], strut_mode=mode, structural_operator=SOURCE_AIRFLOW,
        inputs=['power.1'], matrices=True)
    result = analysis.solve([1., 4., 15.])
    k = 100.+(0. if mode == 'wire' and rest_change > 0 else 360./(2+rest_change))
    effective_k = k if frame == 'prescribed' else 2.5*k
    for sample in result['samples']:
        value = sample['responses'][0]['output']['nodes'][-1]['displacement']
        q = np.array(value['real'])+1j*np.array(value['imag'])
        assert q[1] == pytest.approx(1/(effective_k-3*sample['omega']**2), rel=3e-8, abs=2e-10)
    old_a, old_m = analysis.a, analysis.m
    analysis.solve([2., 8.])
    assert analysis.a is old_a and analysis.m is old_m
    retain(f'frequency-{frame}-{count}-{mode}-{rest_change}', result)


@pytest.mark.parametrize('mode,rest_change', [('bilateral', -.05), ('wire', -.05), ('wire', .2)])
def test_rotating_offset_pylon_dense_sparse_and_complete_residual_tangents(mode, rest_change):
    # Three-dimensional pylon: translational force and follower-arm moment.
    text = beam_source()+f'Strut\n1 2 .15 1 .12 -.3 1.4 -.5 {rest_change} 20\nEnd\n'
    from openswing.inertia import Motion
    system, _ = make_system(model(text), panels=PANELS, frame='prescribed', strut_mode=mode,
        motion=Motion(rates=[.17, -.13, .11], acceleration=[.25, -.18, .12],
                      angular_acceleration=[.04, -.03, .02]),
        gravity=[0., 0., 0.], structural_operator=SOURCE_MOVING, tolerance=1e-10)
    dense = linearize(system, step=1e-5)
    sparse = tuple(a.toarray() for a in linearize(system, step=1e-5, sparse=True))
    for a, b in zip(dense, sparse):
        np.testing.assert_allclose(a, b, rtol=3e-8, atol=3e-9)
    zero = np.zeros(system.size)
    direction = np.random.default_rng(3391).normal(size=system.size)
    direction /= np.linalg.norm(direction)
    expected = directional(lambda v: system.residual(v, zero), direction)
    for a, _ in (dense, sparse):
        np.testing.assert_allclose(a@direction, expected, rtol=3e-7, atol=3e-8)


def test_modal_bridge_preserves_wire_mode_instead_of_defaulting_to_compression():
    # A slack wire must leave the 100 N/m beam spring alone. Bilateral mode
    # would add 360/2.2 N/m and shift this pole by more than 60 percent.
    omega = np.sqrt(100/3)
    request = dict(action='modes', mode='modes', source=source(.2), panels=deepcopy(PANELS),
        numerics=policy(SOURCE_DYNAMIC), strut_mode='wire', gravity=[0., 0., 0.],
        modes=dict(frame='fixed', vacuum=True, count=1, shift=[-.1, omega], method='full_shift_invert'))
    result = dispatch(request)
    assert complex(*result['modes'][0]['eigenvalue']) == pytest.approx(1j*omega, abs=2e-7)
    assert result['base']['struts'][0]['slack']
    retain('modal-wire-slack', result)
