"""Independent periodic boundary and phase-grid checks."""
import math
import importlib.util
from pathlib import Path
import sys
import numpy as np
import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from isae_ua_wing_nonlinear import StraightWing
from isae_ua_wing_periodic import cycle_grid,periodic_solution
from isae_ua_periodic import fourier


@pytest.mark.parametrize('steps',(80,160))
def test_grid_has_all_cycle_boundaries_and_no_abrupt_step_growth(steps):
    period=math.pi/9.5;t=np.array(cycle_grid(period,steps));dt=np.diff(t)
    assert len(t)==8*steps+41
    assert dt[0]<=period/steps/256
    assert np.max(dt[1:]/dt[:-1])<=1.125*(1+1e-11)
    for cycle in range(1,9):
        assert np.min(abs(t-cycle*period))<1e-14
    np.testing.assert_allclose(dt[48:],period/steps,rtol=1e-11,atol=1e-15)


def test_small_amplitude_periodic_state_matches_direct_linear_complex_solve():
    wing=StraightWing(8);k=.95;amplitude=1e-5;speed=10.;omega=20*k;period=math.pi/(10*k)
    times=np.linspace(0,period,161)
    result=periodic_solution(wing,times,amplitude_ratio=amplitude,k=k)
    # Gamma_dot + (pi V/2) C Gamma = (pi V/2) h omega sin(omega t).
    matrix=np.pi*speed/2*wing.C
    phasor=np.linalg.solve(1j*omega*np.eye(wing.panels)+matrix,
        np.full(wing.panels,-1j*np.pi*speed/2*amplitude/2*omega))
    expected=np.real(np.exp(1j*omega*times[:,None])*phasor)
    gamma=np.array([r['circulation'] for r in result['rows']])
    assert np.max(abs(gamma-expected))/np.max(abs(expected))<1e-8


def test_finite_amplitude_periodic_solution_closes_and_preserves_half_cycle_symmetry():
    wing=StraightWing(8);period=math.pi/9.5;times=np.linspace(0,period,161)
    a=periodic_solution(wing,times,amplitude_ratio=.5,k=.95)
    b=periodic_solution(wing,times,amplitude_ratio=.5,k=.95,method='Radau')
    for key in ('CL','circulation','circulation_rate'):
        x=np.array([r[key] for r in a['rows']]);y=np.array([r[key] for r in b['rows']])
        assert np.max(abs(x-y))/np.max(abs(y))<1e-8
        assert np.max(abs(x[:81]+x[80:]))/np.max(abs(x))<1e-8
    measured=fourier(times,[r['CL'] for r in a['rows']],period)
    assert abs(measured['mean'])<1e-10
    assert measured['harmonics'][2]['amplitude']>1e-3


def test_partial_cycle_reference_is_rejected():
    with pytest.raises(ValueError,match='complete cycle'):
        periodic_solution(StraightWing(4),[0.,.1],amplitude_ratio=.5,k=.95)


def test_production_request_keeps_complete_phase_aligned_forcing_from_cold_start():
    spec=importlib.util.spec_from_file_location('ua2_periodic_segment',ROOT/'scripts/verify-isae-ua2-periodic-segment.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    request=module.full_request(80,20);period=math.pi/9.5
    table=np.loadtxt(request['time']['forcing'].splitlines()[1:])
    assert request['action']=='time' and 'checkpoint' not in request
    assert request['condition']['position_earth']==[0.,0.,.25]
    assert table.shape==(681,2) and table[-1,0]==pytest.approx(8*period)
    np.testing.assert_allclose(table[:,1],-.25*19**2*np.cos(19*table[:,0]),atol=1e-13)
    assert request['time']['order']==2 and request['time']['tolerance']==1e-10
