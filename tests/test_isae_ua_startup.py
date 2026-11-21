"""Variable-step heave forcing preserves source BDF consistency and rate errors."""
import importlib.util
import gzip
import json
import math
from pathlib import Path
import sys

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from isae_ua_startup import heave_grid, rate_metrics
from isae_ua_artifacts import write_trajectory


@pytest.mark.parametrize('subdivisions,growth',[(32,1.5),(128,1.5),(256,1.5),(256,1.2),(256,1.125)])
def test_refined_grid_retains_the_period_maximum_step_and_source_BDF_exactness(subdivisions,growth):
    from openswing.time_integration import bdf_coefficients
    period, count = .6613879270715354,160
    times = np.asarray(heave_grid(period,count,subdivisions,growth))
    steps = np.diff(times)
    assert times[0] == 0 and times[-1] == period
    assert np.all(steps > 0)
    assert steps[0] == pytest.approx(period/count/subdivisions,rel=1e-14)
    assert np.max(steps) <= (period/count)*(1+1e-12)
    assert np.max(steps[1:]/steps[:-1]) <= growth*(1+1e-12)
    assert len(steps) <= count+40
    # Eq125 must differentiate both linear and quadratic trajectories exactly
    # on this nonuniform grid, without a constant-step approximation.
    for i in range(2,len(times)):
        coefficients = bdf_coefficients(steps[i-1],steps[i-2])
        local = np.array([0.,times[i-1]-times[i],times[i-2]-times[i]])
        assert coefficients@local == pytest.approx(1.,abs=1e-12,rel=0)
        assert coefficients@(local**2) == pytest.approx(0.,abs=1e-12,rel=0)


def test_default_grid_and_requests_are_preserved_and_refined_forcing_hits_every_knot():
    spec = importlib.util.spec_from_file_location('ua_startup_time',ROOT/'scripts/verify-isae-ua-time.py')
    module = importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    request = module.make_request(steps=160,amplitude_ratio=.001,k=.475,
        aspect_ratio=10.,panels=40,startup_subdivisions=128)
    period = request['time']['duration']
    assert heave_grid(period,160,1) == [period*i/160 for i in range(161)]
    table = np.array([[float(x) for x in row.split()]
        for row in request['time']['forcing'].splitlines()[1:]])
    np.testing.assert_array_equal(table[:,0],heave_grid(period,160,128))
    omega = 2*10*.475
    np.testing.assert_allclose(table[:,1],-.0005*omega**2*np.cos(omega*table[:,0]),atol=1e-15,rtol=0)
    assert request['time']['dt'] == period/160
    assert request['time']['order'] == 2 and request['time']['tolerance'] == 1e-10


def test_rate_metrics_keep_small_tip_values_visible():
    samples = [dict(time=0.,circulation_rate=[0.,0.]),
        dict(time=.01,circulation_rate=[1.,.009]),dict(time=.1,circulation_rate=[10.,.1])]
    reference = [dict(expected=dict(circulation_rate=x)) for x in ([0.,0.],[1.,.01],[10.,.1])]
    measured = rate_metrics(samples,reference)
    assert measured['maximum_first_step_relative_error_fraction'] == pytest.approx(.1)
    assert measured['maximum_per_strip_rate_waveform_error_fraction'] == pytest.approx(.01)
    assert measured['first_step_strip'] == 1


def test_segment_boundary_does_not_cut_off_or_restart_the_forcing():
    from openswing.aero import FlightCondition
    from openswing.asw import parse_asw
    from openswing.forcing import TimeForcing
    spec = importlib.util.spec_from_file_location('ua_segment_time',ROOT/'scripts/verify-isae-ua-time.py')
    module = importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    request = module.make_request(steps=160,amplitude_ratio=.001,k=.475,
        aspect_ratio=10.,panels=20,startup_subdivisions=256,startup_growth=1.125)
    period=request['time']['duration'];cut=heave_grid(period,160,256,1.125)[32]
    model=parse_asw(request['source']);condition=FlightCondition(**request['condition'])
    first=TimeForcing(request['time']['forcing'],model,condition,condition.motion(),cut,'prescribed')
    later=TimeForcing(request['time']['forcing'],model,condition,condition.motion(),period,'prescribed',start_time=cut)
    assert first.end_time == later.end_time == period
    assert first.events[-1] == cut and len(first.events) == 32
    assert cut not in first.breaks and cut not in later.breaks
    assert first.values(cut) == later.values(cut)
    assert len(later.events) == 168


def test_trajectory_writer_preserves_checkpoint_data_and_float_values(tmp_path):
    result = dict(analysis='time_response',restart_context={'name':'Γ and α','version':3},
        snapshots=[dict(time=0.,circulation_rate=[-0.,5e-324],
            restart=dict(state={'value':2**60},older=None)),
            dict(time=.01,circulation_rate=[1.2345678901234567,-3e100],
                restart=dict(state={'value':2**60+1},older={'value':2**60}))],
        converged=True,metadata={'unknown_future_field':[1,False,None]})
    target = tmp_path/'trajectory.json.gz'
    write_trajectory(target,result)
    with gzip.open(target,'rt') as stream:
        restored = json.load(stream)
    assert restored == result
    assert math.copysign(1,restored['snapshots'][0]['circulation_rate'][0]) == -1
    assert not target.with_name(target.name+'.partial').exists()
    with pytest.raises(FileExistsError):
        write_trajectory(target,result)


def test_invalid_trajectory_cannot_appear_as_a_complete_file(tmp_path):
    target = tmp_path/'trajectory.json.gz'
    with pytest.raises(ValueError):
        write_trajectory(target,dict(snapshots=[dict(time=0.),dict(time=float('nan'))]))
    assert not target.exists()
    assert target.with_name(target.name+'.partial').exists()
