"""Periodic reference and measurement checks independent of a production run."""
import importlib.util
import math
from pathlib import Path
import sys

import numpy as np
import pytest
from scipy.integrate import solve_ivp

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from isae_ua_periodic import periodic_reference,fourier,phase_difference
from isae_suite_unsteady import source_formula


def test_fourier_recovers_mean_phase_and_three_harmonics_without_endpoint_deletion():
    t=np.linspace(0,2.,161);p=math.pi*t
    y=1.2+3*np.cos(p+.7)-.8*np.sin(2*p)+.4*np.cos(3*p-.2)
    result=fourier(t,y,2.)
    assert result['mean']==pytest.approx(1.2,abs=1e-14)
    for row,amp,angle in zip(result['harmonics'],(3.,.8,.4),(.7,math.pi/2,-.2)):
        assert row['amplitude']==pytest.approx(amp,abs=1e-14)
        assert abs(phase_difference(row['phase_deg'],math.degrees(angle)))<1e-12
    y[-1]+=1
    assert fourier(t,y,2.)['mean']-result['mean']==pytest.approx(1/320)


@pytest.mark.parametrize('k',(.06785714285714285,.475,.95))
def test_periodic_small_signal_phasor_matches_source_amplitude_and_phase(k):
    amplitude=1e-6;period=math.pi/(10*k);times=np.linspace(0,period,161)
    ref=periodic_reference(times,amplitude_ratio=amplitude,k=k)
    measured=fourier(times,[r['CL'] for r in ref['rows']],period)
    target=-amplitude*source_formula(k);first=measured['harmonics'][0]
    assert first['cosine']==pytest.approx(target.real,rel=1e-10,abs=1e-15)
    assert -first['sine']==pytest.approx(target.imag,rel=1e-10,abs=1e-15)
    assert abs(measured['mean'])<1e-14


def test_periodic_finite_amplitude_boundary_and_cold_transient_match_independent_ode():
    k=.95;amplitude=.5;period=math.pi/(10*k);times=np.linspace(0,period,81)
    ref=periodic_reference(times,amplitude_ratio=amplitude,k=k)
    initial=ref['initial_circulation']
    def rhs(t,y):
        w=-amplitude/2*(20*k)*math.sin(20*k*t)
        return [-5*y[0]-math.pi*math.hypot(10,w)*w/2]
    ode=solve_ivp(rhs,(0,period),[initial],t_eval=times,method='DOP853',rtol=1e-12,atol=1e-13)
    expected=np.array([r['circulation'] for r in ref['rows']])
    np.testing.assert_allclose(ode.y[0],expected,rtol=1e-10,atol=1e-11)
    assert expected[-1]==pytest.approx(initial,abs=1e-12)
    cold=solve_ivp(rhs,(0,period),[0.],t_eval=times,method='DOP853',rtol=1e-12,atol=1e-13)
    np.testing.assert_allclose(cold.y[0],expected-initial*np.exp(-5*times),rtol=1e-10,atol=1e-11)
    measured=fourier(times,[r['CL'] for r in ref['rows']],period)
    assert abs(measured['mean'])<1e-12
    assert measured['harmonics'][2]['amplitude']>1e-3


def test_cycle_resume_preserves_whole_forcing_and_history_ownership():
    spec=importlib.util.spec_from_file_location('periodic_cycle',ROOT/'scripts/verify-isae-ua-periodic-cycle.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    request=module.full_request(80,.5);period=request['time']['duration']
    table=np.loadtxt(request['time']['forcing'].splitlines()[1:])
    assert len(table)==641 and table[-1,0]==pytest.approx(8*period)
    np.testing.assert_allclose(table[:,1],-.25*19**2*np.cos(19*table[:,0]),atol=1e-13)
    saved=dict(state=dict(time=period),older=dict(time=period*79/80))
    resumed=module.resume_request(request,saved,2*period)
    assert resumed['checkpoint'] is saved
    assert 'forcing' not in resumed['time'] and 'condition' not in resumed
    assert resumed['time']['duration']==period and resumed['action']=='resume_time'


def test_incomplete_cycle_is_rejected():
    with pytest.raises(ValueError,match='complete cycle'):
        fourier(np.linspace(0,.9,20),np.zeros(20),1.)
