"""Source airflow transients against independently integrated horseshoe equations."""
from copy import deepcopy
import json
import os
from pathlib import Path

import numpy as np
from scipy.linalg import expm

from openswing.bridge import dispatch
from openswing.source_airflow import AIRFLOW_POLICY, SourceAirflowNetwork
from openswing.time_state import checkpoint, restore_checkpoint
from test_source_airflow import UNIFORM, PANELS, controlled_uniform

POLICY = dict(beam_interpolation='drela-segspl-v1', structural_operator=AIRFLOW_POLICY)
SOURCE = UNIFORM.rsplit('End\n', 1)[0]+'t dCLdF1 dCMdF1\n1 1 0\n3 1 0\nEnd\n'
CONDITION = dict(speed=23., alpha=0., beta=0., density=1.2, mach=0.,
                 gravity_magnitude=0., stall=False, aero_lag=True)
STEP = 1e-4
FORCING = f'time +F1\n0 0\n.004 0\n.004 {STEP}\n.1 {STEP}\n'


def request(dt, duration=.04):
    return dict(action='time', mode='time', source=SOURCE, numerics=deepcopy(POLICY),
        panels=deepcopy(PANELS), condition=deepcopy(CONDITION),
        time=dict(frame='prescribed', duration=duration, dt=dt, order=2,
                  forcing=FORCING, tolerance=1e-11))


def retain(name, result):
    folder = os.environ.get('SOURCE_AIRFLOW_ARTIFACTS')
    if folder:
        directory = Path(folder); directory.mkdir(parents=True, exist_ok=True)
        (directory/(name+'.json')).write_text(json.dumps(result, allow_nan=False)+'\n')


def analytic_matrix():
    # Independent literal four-segment integration. No production aerodynamic
    # geometry, kernels, Jacobians or time-integration coefficients are used.
    u, chord = 23., .8
    edges = np.linspace(-1., 1., 5)
    theta = np.arccos(edges)
    points = np.cos((theta[:-1]+theta[1:])/2)
    ya, yb = points[:,None]-edges[:-1], points[:,None]-edges[1:]
    h = chord/2
    ra, rb = np.sqrt(h*h+ya*ya), np.sqrt(h*h+yb*yb)
    a = -(ya/ra-yb/rb)/(4*np.pi*h)+((1+h/rb)/yb-(1+h/ra)/ya)/(4*np.pi)
    return a


def analytic_response(time):
    u, chord = 23., .8
    edges = np.linspace(-1., 1., 5)
    a = analytic_matrix()
    d = 2/(np.pi*u)
    steady = np.linalg.solve(-a, np.full(4, u*STEP/(2*np.pi)))
    gamma = steady-expm(a/d*(time-.004))@steady
    rate = a/d@(gamma-steady)
    cl = 2*np.dot(u*gamma+chord*rate, np.diff(edges))/(u*u*2*chord)
    return gamma, rate, cl


def test_control_step_refines_to_analytic_circulation_and_unsteady_lift():
    errors = []
    for dt in (.004, .002):
        value = request(dt); before = deepcopy(value)
        result = dispatch(value)
        assert value == before and result['converged']
        assert result['temporal_policy'] == 'drela-euler-bdf-v1'
        assert result['structural_operator'] == AIRFLOW_POLICY
        final = result['snapshots'][-1]
        gamma, rate, cl = analytic_response(final['time'])
        error = abs(final['CL']-cl)/abs(cl)
        errors.append(error)
        np.testing.assert_allclose([row['circulation'] for row in final['strips']], gamma, rtol=.01)
        np.testing.assert_allclose(final['circulation_rate'], rate, rtol=.01)
        assert max(row['residual'] for row in result['snapshots']) <= 1e-10
        assert np.isclose(
            final['Cm'], -(.25-.13)*final['CL'], rtol=2e-7, atol=1e-12)
        retain('step-'+str(dt), result)
    retain('step-refinement', dict(time=.04, relative_CL_errors=errors,
                                  analytical_CL=cl, step=STEP))
    assert errors[1] < .01
    assert errors[1] < .5*errors[0]


def test_checkpoint_preserves_circulation_history_and_replays_source_airflow():
    first = dispatch(request(.002, .024))
    saved = json.loads(json.dumps(checkpoint(first)))
    network, *_, checked = restore_checkpoint(controlled_uniform(), saved)
    assert type(network) is SourceAirflowNetwork
    assert checked['acceptance_validation']['discrete_replayed']
    continued = dispatch(dict(action='resume_time', source=SOURCE, numerics=deepcopy(POLICY),
        checkpoint=saved, time=dict(duration=.016)))
    whole = dispatch(request(.002, .04))
    assert continued['converged'] and continued['structural_operator'] == AIRFLOW_POLICY
    a, b = continued['snapshots'][-1], whole['snapshots'][-1]
    for key in ('CL', 'Cm', 'force', 'moment', 'circulation_rate', 'local_velocity', 'local_rates'):
        np.testing.assert_allclose(a[key], b[key], rtol=2e-9, atol=2e-12, err_msg=key)
    assert continued['restart_context']['setup']['condition'] == first['restart_context']['setup']['condition']
    retain('checkpoint', saved); retain('continued', continued)


def test_aerodynamic_modes_match_analytic_relaxation_rates():
    result = dispatch(dict(action='modes', mode='modes', source=SOURCE,
        condition=deepcopy(CONDITION), panels=deepcopy(PANELS), numerics=deepcopy(POLICY),
        modes=dict(frame='fixed', count=8)))
    expected = np.sort(np.linalg.eigvals(analytic_matrix()/(2/(np.pi*23.))))
    observed = np.sort([complex(*row['eigenvalue']) for row in result['modes']])
    np.testing.assert_allclose(observed, expected, rtol=3e-8, atol=2e-8)
    assert result['converged'] and result['vacuum'] is False
    retain('modes-analytic', dict(expected=[[v.real,v.imag] for v in expected],
        observed=[[v.real,v.imag] for v in observed]))
