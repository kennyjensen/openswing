"""Independent modal-projection, constrained-mechanics and sensor checks."""
import json
from pathlib import Path
import numpy as np
import pytest
from scipy.linalg import block_diag, expm
from openswing.aero import AnalysisError, FlightCondition
from openswing.asw import parse_asw
from openswing.bridge import run_json
from openswing.linear_dynamics import eigensystem
from openswing.reduced_model import real_projection, algebraic_input_lift, solve_reduced_model, rom_text


def complex_array(value):
    return np.array(value['real'])+1j*np.array(value['imag'])


def reduce(a, m, b, selected=None, count=100):
    modes, _ = eigensystem(a, m, count=count, time_scale=2.3)
    ar, v, w, report = real_projection(a, m, modes, selected)
    direct, diagnostic = algebraic_input_lift(a, m, b, time_scale=2.3)
    return ar, w@b, v, direct, report, diagnostic


@pytest.mark.parametrize('row,column', [(np.ones(5), np.ones(5)),
    (np.array([1e-5, 3., 1e5, .003, 2.]), np.array([.2, 3., .1, 4., .01]))])
def test_constrained_two_mass_response_retains_instantaneous_reaction(row, column):
    # x1=x2, m1=2,m2=3, k1=11,k2=17, c1=.4,c2=.8.
    # Equal motion gives (5s²+1.2s+28)x=f1+f2; reaction includes input.
    a = np.array([[0, 0, 1, 0, 0], [0, 0, 0, 1, 0],
                  [-18, 7, -.4, 0, 1], [7, -24, 0, -.8, -1], [1, -1, 0, 0, 0]], float)
    m = np.diag([1., 1., 2., 3., 0.])
    b = np.array([[0,0], [0,0], [1,0], [0,1], [0,0]], float)
    aa, mm, bb = row[:,None]*a*column, row[:,None]*m*column, row[:,None]*b
    ar, br, v, direct, report, diagnostic = reduce(aa, mm, bb)
    assert report['dimension'] == diagnostic['finite_dimension'] == 2
    for omega in (0., .1, 2., 30., 1e4):
        s=1j*omega; x=1/(5*s*s+1.2*s+28)
        expected=np.array([[x,x], [x,x], [s*x,s*x], [s*x,s*x],
            [(2*s*s+.4*s+11)*x-1, (2*s*s+.4*s+11)*x]])
        actual=column[:,None]*(v@np.linalg.solve(s*np.eye(2)-ar, br)+direct)
        np.testing.assert_allclose(actual, expected, rtol=1e-8, atol=3e-9)
    np.testing.assert_allclose(column[:,None]*direct, [[0,0],[0,0],[0,0],[0,0],[-.6,.4]], atol=1e-9)


def test_pair_completion_and_real_time_evolution():
    a=np.array([[0.,1.],[-250.,-5.]])
    m=np.eye(2);b=np.array([[0.],[.5]])
    ar,br,v,d,report,_=reduce(a,m,b,count=1)
    assert report['dimension']==2 and report['retained'][0]['conjugate_source_index'] is None
    initial=np.linalg.solve(v,np.array([.002,0.]))
    for t in (0., .03, .12, .5):
        np.testing.assert_allclose(v@expm(ar*t)@initial,expm(a*t)@[.002,0.],atol=2e-16)
    assert np.max(abs(d))==0


@pytest.mark.parametrize('scales', [np.ones(3), np.array([.03, 20., .4])])
def test_algebraic_lift_preserves_exact_rate_zeros_and_coupled_mass_nullspace(scales):
    # Physical coordinates obey xdot=-2x+r, wdot=-3w+2r, r=u.
    # w=y+z and r=y-z leave a null combination of two NONZERO mass columns.
    transform=np.array([[1.,0.,0.],[0.,1.,1.],[0.,1.,-1.]])*scales
    a=np.array([[-2.,0.,1.],[0.,-3.,2.],[0.,0.,-1.]])@transform
    m=np.diag([1.,1.,0.])@transform;b=np.array([[0.],[0.],[1.]])
    direct,report=algebraic_input_lift(a,m,b)
    assert direct[0,0]==0.  # Exact kinematic equation, not an output threshold.
    np.testing.assert_allclose(transform@direct,[[0.],[0.],[1.]],atol=3e-15)
    assert report['algebraic_lift_exact_zero_coordinates']==[0]
    assert report['algebraic_lift_zero_mass_columns']==[]


def test_exact_algebraic_constraints_do_not_hide_weak_inertia():
    with pytest.raises(AnalysisError,match='weak inertia'):
        algebraic_input_lift(-np.eye(2),np.diag([1.,1e-12]),np.ones((2,1)))


def test_algebraic_acceleration_output_keeps_force_feedthrough_and_position_integrator():
    # Physical coordinates [v,p,a], vdot=a, pdot=v, 2a+3v=u.
    # The zero position pole is semisimple and must be retained for GPS response.
    a=np.array([[0.,0.,1.],[1.,0.,0.],[-3.,0.,-2.]])
    m=np.diag([1.,1.,0.]);b=np.array([[0.],[0.],[1.]])
    ar,br,v,d,_,_=reduce(a,m,b)
    assert d[2,0]==pytest.approx(.5,abs=1e-13)
    for omega in (.1,1.,30.):
        s=1j*omega
        np.testing.assert_allclose((v@np.linalg.solve(s*np.eye(2)-ar,br)+d)[:,0],
                                  [1/(2*s+3),1/(s*(2*s+3)),s/(2*s+3)],atol=1e-12)


@pytest.mark.parametrize('frequency_scale', [1e-10,1e10])
def test_conjugate_classification_is_invariant_to_extreme_time_scaling(frequency_scale):
    a=np.array([[0.,1.],[-250.,-5.]]);b=np.array([[0.],[.5]])
    modes,_=eigensystem(a*frequency_scale,np.eye(2),count=1,time_scale=frequency_scale)
    ar,v,w,report=real_projection(a*frequency_scale,np.eye(2),modes)
    assert report['dimension']==2
    for omega in (0.,1.,20.):
        actual=v@np.linalg.solve(1j*omega*frequency_scale*np.eye(2)-ar,w@b*frequency_scale)
        np.testing.assert_allclose(actual,np.linalg.solve(1j*omega*np.eye(2)-a,b),rtol=1e-12,atol=1e-14)


def test_truncation_retains_selected_fast_mode_and_has_quantified_error():
    a=block_diag(np.array([[0.,1.],[-4.,-.2]]),np.array([[0.,1.],[-400.,-2.]]))
    m=np.eye(4); b=np.array([[0.],[1.],[0.],[.5]])
    modes,_=eigensystem(a,m,count=4)
    fast=next(i for i,x in enumerate(modes) if abs(complex(*x['eigenvalue']))>10)
    ar,v,w,report=real_projection(a,m,modes,[fast])
    assert report['dimension']==2
    for omega in (0., 3., 20.):
        s=1j*omega; x=v@np.linalg.solve(s*np.eye(2)-ar,w@b)
        np.testing.assert_allclose(x[:,0],[0,0,.5/(s*s+2*s+400),.5*s/(s*s+2*s+400)],atol=1e-14)


def test_repeated_semisimple_modes_are_mass_dualized_as_a_group():
    t=np.array([[1.,2.,1.],[0.,1.,3.],[1.,0.,1.]])
    a=t@np.diag([-2.,-2.,-4.])@np.linalg.inv(t);m=np.eye(3);b=np.array([[1.],[2.],[3.]])
    ar,br,v,d,_,_=reduce(a,m,b)
    for omega in (0.,2.,40.):
        np.testing.assert_allclose(v@np.linalg.solve(1j*omega*np.eye(3)-ar,br)+d,
                                  np.linalg.solve(1j*omega*m-a,b),atol=1e-13)


def test_defective_modes_and_derivative_constraint_inputs_are_rejected():
    a=np.array([[0.,1.],[0.,0.]])
    modes,_=eigensystem(a,np.eye(2),count=2)
    with pytest.raises(AnalysisError,match='pairing|defective|dependent'):
        real_projection(a,np.eye(2),modes)
    # qdot=v, q=u needs v=udot. No constant algebraic state-input lift exists.
    with pytest.raises(AnalysisError,match='input derivatives'):
        algebraic_input_lift(np.array([[0.,1.],[-1.,0.]]),np.diag([1.,0.]),np.array([[0.],[1.]]))


@pytest.fixture(scope='module')
def oscillator_rom():
    source=Path('examples/instrumented-oscillator.asw').read_text()
    request=dict(action='rom',source=source,panels=4,condition=dict(speed=10,alpha=0,mach=0),gravity=[0,0,0],
        rom=dict(count=2,selected=[0],outputs=['RY[2]','UY[2]','Ay[2]'],frequencies=[0.,1.,10.,50.]))
    return request,json.loads(run_json(json.dumps(request)))


def test_complete_mechanical_rom_matches_independent_sensor_transfers(oscillator_rom):
    request,result=oscillator_rom
    assert result['analysis']=='reduced_order_model' and result['diagnostics']['dimension']==2
    for sample in result['samples']:
        s=1j*sample['omega']; exact=np.array([1,s,s*s])/(2*s*s+10*s+500)
        np.testing.assert_allclose(complex_array(sample['reduced'])[:,0],exact,rtol=2e-8,atol=1e-10)
        np.testing.assert_allclose(complex_array(sample['full'])[:,0],exact,rtol=2e-8,atol=1e-10)
    assert result['matrices']['D'][2][0]==pytest.approx(.5,abs=1e-10)
    assert result['output_base'][0]==pytest.approx(2.)
    assert [o['unit'] for o in result['outputs']]==['input L','input L/T','input L/T^2']
    assert result['text_export']==rom_text(result)
    assert 'not an ASWING legacy .rom' in result['text_export']
    assert 'A 2 2\n' in result['text_export'] and 'D_rate 3 1\n' in result['text_export']


def test_controller_lag_rom_preserves_poles_and_acceleration_feedthrough():
    model=parse_asw(Path('examples/instrumented-oscillator.asw').read_text())
    law=json.loads(Path('examples/actuator-lag-controller.json').read_text())
    result=solve_reduced_model(model,FlightCondition(speed=10,alpha=0,mach=0),4,gravity=[0,0,0],
        count=3,controller=law,inputs=['power.1','command.RY[2]'],outputs=['RY[2]','UY[2]','Ay[2]'],frequencies=[0,3,30])
    actual=np.linalg.eigvals(result['matrices']['A']);expected=np.roots([.1,2.5,55,700])
    for pole in expected:assert min(abs(actual-pole))<1e-7
    for sample in result['samples']:
        s=1j*sample['omega'];exact=np.array([1,s,s*s])[:,None]*np.array([1,200])/(.1*s**3+2.5*s*s+55*s+700)
        np.testing.assert_allclose(complex_array(sample['reduced']),exact,rtol=1e-7,atol=2e-8)
    assert result['controller']['state_channels']==['lag']


@pytest.mark.parametrize('selected', [[],[100],[-1],[True],[0,0],'0'])
def test_invalid_mode_selection(selected):
    modes,_=eigensystem(np.diag([-1.,-2.]),np.eye(2),count=2)
    with pytest.raises(AnalysisError,match='mode indices'):
        real_projection(np.diag([-1.,-2.]),np.eye(2),modes,selected)


def test_frequency_dependent_gust_is_not_exported_as_constant_matrix():
    model=parse_asw(Path('examples/instrumented-oscillator.asw').read_text())
    with pytest.raises(AnalysisError,match='phase depends on frequency'):
        solve_reduced_model(model,FlightCondition(speed=10,alpha=0,mach=0),4,gravity=[0,0,0],inputs=[dict(kind='gust')])


def test_time_unit_covariance_of_rom_transfer_and_sensor_acceleration(oscillator_rom):
    request,original=oscillator_rom
    source=(request['source'].replace('T 1 s','T 2 s').replace('9.80665 1.225 340.294','39.2266 .30625 680.588').replace('1000 .02','1000 .01'))
    result=solve_reduced_model(parse_asw(source),FlightCondition(speed=20,alpha=0,mach=0),4,gravity=[0,0,0],
        count=2,outputs=['RY[2]','UY[2]','Ay[2]'],frequencies=[0,2,20,100])
    for before,after in zip(original['samples'],result['samples']):
        np.testing.assert_allclose(complex_array(after['reduced']),np.array([1,2,4])[:,None]*complex_array(before['reduced']),rtol=2e-7,atol=1e-9)
