"""ROM output channels against independent springs and lifting-line loads."""
from copy import deepcopy
from pathlib import Path
import runpy
import numpy as np
import pytest

from openswing.aero import AnalysisError, FlightCondition
from openswing.asw import parse_asw
from openswing.linear_dynamics import make_system
from openswing.reduced_model import solve_reduced_model
from openswing.rom_outputs import MeasurementOutputs, output_catalog, selector
from openswing.rom_file import export_rom, parse_rom, rom_response, array

ROOT = Path(__file__).resolve().parents[1]
SOURCE = runpy.run_path(str(ROOT/'scripts/verify-section-outputs.py'))['source']
RHO, SOUND = 1.225, 340.294


def pick(base, group, key, index=0, component=None):
    spec = dict(group=group, key=key)
    if component is not None:
        spec['component'] = component
    if group != 'global':
        row = base['elements' if group == 'sections' else group][index]
        spec.update(index=index, beam=row['beam'], t=row['t'])
    return spec


def independent_flow(count):
    edge=-np.cos(np.linspace(0,np.pi,count+1));y=-np.cos((np.arange(count)+.5)*np.pi/count)
    a=y[:,None]-edge[:-1];b=y[:,None]-edge[1:];dx=.5
    ra=np.sqrt(dx*dx+a*a);rb=np.sqrt(dx*dx+b*b)
    return -(a/ra-b/rb)/(4*np.pi*dx)+((1+dx/rb)/b-(1+dx/ra)/a)/(4*np.pi)


@pytest.fixture(scope='module')
def rigid():
    model = parse_asw(SOURCE({}))
    condition = FlightCondition(speed=30, alpha=0, mach=0, controls={1:3.})
    system, _ = make_system(model, condition, 4, gravity=[0,0,0])
    return model, condition, system, system.base_report()


def test_material_inertial_density_uses_rate_and_excludes_concentrated_mass(rigid):
    _, _, system, base = rigid
    outputs = [pick(base, 'strips', 'f_reac', i) for i in range(4)]
    measured = MeasurementOutputs(system, outputs)
    rate=np.zeros(system.size);rate[system.velocity_start:system.velocity_start+3*system.network.nn].reshape(-1,3)[:,2]=.7/system.V
    # Two real mass densities sum to 2.5 kg/m. The separate 10 kg Weight is
    # absent from the density. Flat-plate normal added mass is rho*pi/4.
    expected = -(2.5+RHO*np.pi/4)*.7
    np.testing.assert_allclose(measured.tangent(np.zeros(system.size),rate,1e-5),expected,rtol=2e-10,atol=2e-10)
    assert all(item['unit']=='input F/L' for item in measured.metadata)


@pytest.mark.parametrize('units',[[1.,1.,1.],[.3048,2.,4.4482216152605]])
def test_rom_rate_lift_direct_pitching_moment_and_initial_boundary_match_horseshoes(units):
    L,T,F=units;count=4
    model=parse_asw(SOURCE(dict(units=units)))
    condition=FlightCondition(speed=30*T/L,alpha=0,mach=0,controls={1:3.})
    system,_=make_system(model,condition,count,gravity=[0,0,0]);base=system.base_report()
    outputs=[pick(base,'strips',key,i) for i in range(count) for key in ['cm','f_aero','circulation']]
    before=deepcopy(outputs);initial=.2*np.sin((np.arange(count)+.5)*np.pi/count)
    rom=solve_reduced_model(model,condition,count,gravity=[0,0,0],count=count,outputs=outputs,
        inputs=['control.1',dict(kind='gust',wave='uniform')],frequencies=np.array([0.,3.,25.])*T,
        initial_inputs=[dict(kind='initial',name='circulation',state=dict(circulation=(initial*T/L**2).tolist()))],
        initial_times=[0,.05/T])
    assert outputs==before
    assert rom['diagnostics']['dimension']==count
    w=independent_flow(count);mass=2/(np.pi*30)*np.eye(count)
    output_scales=np.tile([1.,F/L,L**2/T],count)
    input_scales=np.array([1.,L/T])
    for sample,omega in zip(rom['samples'],[0.,3.,25.]):
        gamma=np.linalg.solve(1j*omega*mass-w,np.ones(count))
        expected=np.zeros((count,3,2),complex)
        expected[:,0,0]=.005/np.sqrt(1-(30/SOUND)**2)
        expected[:,1,1]=RHO*(30+1j*omega)*gamma
        expected[:,2,1]=gamma
        for kind in ['full','reduced']:
            actual=array(sample[kind])*output_scales[:,None]/input_scales
            np.testing.assert_allclose(actual,expected.reshape(-1,2),rtol=3e-7,atol=3e-8)
    profile=rom['initial_responses'][0]
    assert profile['converged'],profile
    for sample,omega in zip(profile['samples'],[0.,3.,25.]):
        gamma=np.linalg.solve(1j*omega*mass-w,mass@initial)
        expected=np.column_stack([np.zeros(count),RHO*((30+1j*omega)*gamma-initial),gamma]).ravel()
        for kind in ['full','reduced']:
            np.testing.assert_allclose(array(sample[kind])*output_scales*T,expected,rtol=3e-7,atol=3e-8)
    text=export_rom(rom,model.units);parsed=parse_rom(text)
    assert all(item['name'].startswith('OpenSwing strips.') for item in parsed['outputs'])
    for row,original in zip(rom_response(parsed,[0,3,25])['samples'],rom['samples']):
        np.testing.assert_allclose(array(row['response']),array(original['reduced'])*output_scales[:,None]/input_scales,rtol=1e-11,atol=1e-10)


@pytest.mark.parametrize('preload',[0.,5.])
def test_nodal_structural_and_global_rom_outputs_match_loaded_axial_oscillator(preload):
    source=(ROOT/'examples/instrumented-oscillator.asw').read_text()
    model=parse_asw(source);condition=FlightCondition(speed=10,alpha=0,mach=0,powers={1:preload})
    system,_=make_system(model,condition,4,gravity=[0,0,0]);base=system.base_report()
    tip=max(range(len(base['nodes'])),key=lambda i:base['nodes'][i]['t'])
    outputs=[pick(base,'nodes','displacement',tip,1),pick(base,'nodes','velocity',tip,1),
             pick(base,'sections','strain',0,1),pick(base,'sections','force_local',0,1),
             pick(base,'global','engine_force',component=1),pick(base,'global','support_force',component=1),'RY[2]']
    result=solve_reduced_model(model,condition,4,gravity=[0,0,0],count=2,selected=[0],outputs=outputs,frequencies=[0,10,50])
    assert result['output_base'][0]==pytest.approx(preload/500,abs=2e-12)
    assert result['output_base'][2]==pytest.approx(preload/1000,abs=2e-12)
    for sample in result['samples']:
        s=1j*sample['omega'];h=1/(2*s*s+10*s+500)
        expected=[h,s*h,h/2,(500+10*s)*h,1,-(500+10*s)*h,h]
        for kind in ['full','reduced']:
            np.testing.assert_allclose(array(sample[kind])[:,0],expected,rtol=3e-7,atol=2e-8)
    assert result['matrices']['D'][4][0]==pytest.approx(1.,abs=1e-9)


@pytest.mark.parametrize('change',[
    dict(index=-1),dict(index=True),dict(beam=99),dict(t=.123456),dict(t=True),
    dict(key='unknown'),dict(component=1),dict(extra=2),dict(group=[]),
])
def test_invalid_and_stale_sample_selectors_are_rejected(rigid,change):
    _,_,system,base=rigid
    spec=pick(base,'strips','f_aero');spec.update(change)
    with pytest.raises(AnalysisError):MeasurementOutputs(system,[spec])


def test_duplicate_selectors_and_missing_shell_outputs_do_not_become_zero(rigid):
    _,_,system,base=rigid
    spec=pick(base,'strips','f_aero')
    with pytest.raises(AnalysisError,match='distinct'):MeasurementOutputs(system,[spec,deepcopy(spec)])
    with pytest.raises(AnalysisError,match='unavailable'):MeasurementOutputs(system,[pick(base,'sections','shell_shear_stress')])
    catalog=output_catalog(base)
    assert all('shell_shear_stress' not in row['available'] for row in catalog['stations']['sections'])
    with pytest.raises(AnalysisError,match='sample index'):selector(dict(group='global',key='CL',index=0),base)


def test_incidence_at_stagnant_local_flow_is_unavailable_before_differentiation():
    from openswing.network import StaticNetwork
    from openswing.linear_dynamics import DynamicSystem
    condition=FlightCondition(speed=30,alpha=0,mach=0,gust=dict(type='uniform',velocity=[-30,0,0]))
    network=StaticNetwork(parse_asw(SOURCE({})),4,condition,[0,0,0],[])
    system=DynamicSystem(network,np.zeros(network.size));base=system.base_report()
    assert all('da_eff' not in row['available'] for row in output_catalog(base)['stations']['strips'])
    with pytest.raises(AnalysisError,match='unavailable'):MeasurementOutputs(system,[pick(base,'strips','da_eff')])
