"""Mass-dual initial conditions against independent constrained ODE solutions."""
from copy import deepcopy
from pathlib import Path
import json
import numpy as np
import pytest
from scipy.linalg import expm
from openswing.aero import AnalysisError,FlightCondition
from openswing.asw import parse_asw
from openswing.initial_response import ConsistentSubspace
from openswing.linear_dynamics import eigensystem
from openswing.reduced_model import real_projection,solve_reduced_model,rom_text
from openswing.rom_initial import projected_response,time_grid


def z(value):return np.array(value['real'])+1j*np.array(value['imag'])


@pytest.mark.parametrize('amplitude',[1.,1e-12,1e-180])
@pytest.mark.parametrize('scaled',[False,True])
def test_constrained_initial_reaction_and_acceleration_survive_mass_dual_projection(amplitude,scaled):
    a=np.array([[0,0,1,0,0],[0,0,0,1,0],[-18,7,-.4,0,1],[7,-24,0,-.8,-1],[1,-1,0,0,0]],float)
    m=np.diag([1.,1.,2.,3.,0.])
    row=np.array([1e-5,3.,1e5,.003,2.]) if scaled else np.ones(5)
    column=np.array([.2,3.,.1,4.,.01]) if scaled else np.ones(5)
    a=row[:,None]*a*column;m=row[:,None]*m*column
    space=ConsistentSubspace(a,m,[0,1,2,3],time_scale=2.3)
    modes,_=eigensystem(a,m,count=1,time_scale=2.3);ar,v,w,_=real_projection(a,m,modes)
    cr=np.vstack((column[:,None]*v,column[2]*(v@ar)[2]));cf=np.vstack((column[:,None]*space.lift,column[2]*(space.lift@space.generator)[2]))
    initial=amplitude*np.array([.01,.01,.02,.02,0])/column
    out=projected_response(space,ar,v,w,cr,cf,initial,[0,.1,.5,2],[0,1,10],0)
    g=np.array([[0,1],[-5.6,-.24]])
    def physical(q):return np.array([q[0],q[0],q[1],q[1],-.2*q[0]-.08*q[1],-5.6*q[0]-.24*q[1]])
    assert out['projection']['relative_dynamic_norm']<1e-8
    for sample in out['time_samples']:
        exact=physical(expm(g*sample['time'])@[.01,.02])
        np.testing.assert_allclose(np.array(sample['full'])/amplitude,exact,rtol=1e-8,atol=1e-10)
        np.testing.assert_allclose(np.array(sample['reduced'])/amplitude,exact,rtol=1e-8,atol=1e-10)
    for sample in out['samples']:
        exact=physical(np.linalg.solve(1j*sample['omega']*np.eye(2)-g,[.01,.02]))
        np.testing.assert_allclose(z(sample['full'])/amplitude,exact,rtol=1e-8,atol=1e-10)
        np.testing.assert_allclose(z(sample['reduced'])/amplitude,exact,rtol=1e-8,atol=1e-10)
        assert sample['full_equation_scaled_residual']<1e-8
    json.dumps(out,allow_nan=False)


def test_omitted_unstable_mode_keeps_full_growth_guard_and_explicit_truncation_error():
    a=np.diag([-1.,2.]);m=np.diag([3.,.5]);a=m@a
    space=ConsistentSubspace(a,m,[0,1]);modes,_=eigensystem(a,m,count=2)
    selected=next(i for i,v in enumerate(modes) if v['eigenvalue'][0]<0)
    ar,v,w,_=real_projection(a,m,modes,[selected]);cr=np.ones((1,2))@v;cf=np.ones((1,2))@space.lift
    result=projected_response(space,ar,v,w,cr,cf,np.array([1.,2.]),[0,.2,1],[0,3],0)
    assert 'spectral abscissa' in result['spectrum_error'] and not result['samples']
    np.testing.assert_allclose(result['omitted_state'],[0,2],atol=1e-14)
    assert result['projection']['relative_dynamic_norm']==pytest.approx(2/np.sqrt(5))
    for row in result['time_samples']:
        assert row['full'][0]==pytest.approx(np.exp(-row['time'])+2*np.exp(2*row['time']))
        assert row['reduced'][0]==pytest.approx(np.exp(-row['time']))
    valid=projected_response(space,ar,v,w,cr,cf,np.array([1.,2.]),[0],[0,3],3.)
    for row in valid['samples']:
        s=3+1j*row['omega']
        assert z(row['full'])[0]==pytest.approx(1/(s+1)+2/(s-2))
        assert z(row['reduced'])[0]==pytest.approx(1/(s+1))
    overflow=projected_response(space,ar,v,w,cr,cf,np.array([1.,2.]),[0,1000],[0],3.)
    assert overflow['time_samples'][0]['converged'] and not overflow['time_samples'][1]['converged']
    json.dumps(overflow,allow_nan=False)


@pytest.fixture(scope='module')
def oscillator():
    profiles=json.loads(Path('examples/initial-spring.json').read_text())
    profiles.append(dict(kind='initial',name='Inconsistent ground motion',state=dict(nodes=[dict(beam=1,t=0,velocity=[0,1,0])])))
    before=deepcopy(profiles)
    result=solve_reduced_model(parse_asw(Path('examples/instrumented-oscillator.asw').read_text()),FlightCondition(speed=10,alpha=0,mach=0),4,
        count=2,selected=[0],gravity=[0,0,0],inputs=[],outputs=['RY[2]','UY[2]','Ay[2]'],frequencies=[0,5,30],
        initial_inputs=profiles,initial_times=[0,.03,.2,.7])
    assert profiles==before
    return result


def test_physical_profiles_match_free_oscillator_and_initial_acceleration_boundary(oscillator):
    result=oscillator;g=np.array([[0,1],[-250,-5]])
    assert result['inputs']==[] and result['matrices']['B']==[[],[]]
    for initial,row in zip(([.002,0],[0,.01]),result['initial_responses']):
        assert row['converged'];assert row['projection']['relative_dynamic_norm']<1e-7
        for sample in row['time_samples']:
            x=expm(g*sample['time'])@initial;exact=[*x,(g@x)[1]]
            for key in ('full','reduced'):np.testing.assert_allclose(sample[key],exact,rtol=2e-6,atol=2e-9)
        for sample in row['samples']:
            s=1j*sample['omega'];x=np.linalg.solve(s*np.eye(2)-g,initial);exact=[*x,(g@x)[1]]
            for key in ('full','reduced'):np.testing.assert_allclose(z(sample[key]),exact,rtol=2e-6,atol=2e-9)
    assert not result['initial_responses'][2]['converged']
    assert 'constraints' in result['initial_responses'][2]['error']
    assert '# initial_conditions ' in rom_text(result)
    json.dumps(result,allow_nan=False)


@pytest.mark.parametrize('times',[[],[-1],[0,0],[1,0],[np.nan],[[0,1]],['bad']])
def test_invalid_initial_time_grids(times):
    with pytest.raises(AnalysisError,match='times'):time_grid(times)


@pytest.mark.parametrize('kind',['integral','lag'])
def test_controller_initial_conditions_match_independent_three_state_dynamics(kind):
    state=dict(beam_fields=[dict(beam=1,displacement=[[0,0,0,0],[2,0,.002,0]],velocity=[[0,0,0,0],[2,0,.01,0]])])
    if kind=='integral':
        law=dict(commands={'RY[2]':2},outputs=[dict(actuator='E1',terms=[dict(input='RY[2]',gain=-200),dict(input='RY[2]',gain=-100,mode='integral')])])
        state['feedback']=dict(integrals={'RY[2]':.003});g=np.array([[0,1,0],[-350,-5,-50],[1,0,0.]])
        initial=[.002,.01,.003]
    else:
        law=json.loads(Path('examples/actuator-lag-controller.json').read_text());law['commands']={'RY[2]':2,'UY[2]':0}
        state['feedback']=dict(states={'lag':.1});g=np.array([[0,1,0],[-250,-5,.5],[-4000,-400,-20.]])
        initial=[.002,.01,.1]
    result=solve_reduced_model(parse_asw(Path('examples/instrumented-oscillator.asw').read_text()),FlightCondition(speed=10,alpha=0,mach=0),4,
        gravity=[0,0,0],controller=law,count=3,inputs=['power.1'],outputs=['RY[2]','UY[2]','Ay[2]'],
        initial_inputs=[dict(kind='initial',state=state)],initial_times=[0,.03,.2,.7],frequencies=[0,5,30],initial_shift=.3)
    row=result['initial_responses'][0];assert row['converged'],row
    for sample in row['time_samples']:
        q=expm(g*sample['time'])@initial;expected=[q[0],q[1],(g@q)[1]]
        for key in ('full','reduced'):np.testing.assert_allclose(sample[key],expected,rtol=3e-6,atol=1e-8)
    for sample in row['samples']:
        q=np.linalg.solve((.3+1j*sample['omega'])*np.eye(3)-g,initial);expected=[q[0],q[1],(g@q)[1]]
        for key in ('full','reduced'):np.testing.assert_allclose(z(sample[key]),expected,rtol=3e-6,atol=1e-8)
    assert result['samples'][0]['converged']


def test_initial_history_and_spectral_units_are_covariant(oscillator):
    source=Path('examples/instrumented-oscillator.asw').read_text().replace('T 1 s','T 2 s').replace('9.80665 1.225 340.294','39.2266 .30625 680.588').replace('1000 .02','1000 .01')
    profiles=json.loads(Path('examples/initial-spring.json').read_text());profiles[1]['state']['beam_fields'][0]['velocity'][-1][2]*=2
    after=solve_reduced_model(parse_asw(source),FlightCondition(speed=20,alpha=0,mach=0),4,gravity=[0,0,0],
        count=2,inputs=[],outputs=['RY[2]','UY[2]','Ay[2]'],initial_inputs=profiles,initial_times=[0,.015,.1,.35],frequencies=[0,10,60])
    for before,row in zip(oscillator['initial_responses'],after['initial_responses']):
        for a,b in zip(before['time_samples'],row['time_samples']):
            for key in ('full','reduced'):np.testing.assert_allclose(b[key],np.array([1,2,4])*a[key],rtol=3e-6,atol=2e-9)
        for a,b in zip(before['samples'],row['samples']):
            for key in ('full','reduced'):np.testing.assert_allclose(z(b[key]),np.array([.5,1,2])*z(a[key]),rtol=3e-6,atol=2e-9)
