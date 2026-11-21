"""Frozen-grid refinement against mechanics, gust phase and Laplace identities."""
from copy import deepcopy
from pathlib import Path
import json
import numpy as np
import pytest
from openswing.asw import parse_asw
from openswing.aero import FlightCondition,AnalysisError
from openswing.frequency_response import FrequencyAnalysis,frequency_grid
from openswing.frequency_sweep import FrequencySweep
from openswing.bridge import dispatch
from test_frequency_response import powered_oscillator,z
from test_time_integration import rigid_body
from test_network import model,beam


def condition():return FlightCondition(speed=10,alpha=0,mach=0,stall=False)


def test_refinement_retains_samples_and_exact_frozen_pencil_with_owned_inputs(monkeypatch):
    m=powered_oscillator();c=condition();inputs=['power.1'];events=[]
    sweep=FrequencySweep(m,c,4,frequencies=[1,30],inputs=inputs,gravity=[0,0,0],matrices=True,progress=lambda *x:events.append(x))
    before=sweep.report();a=sweep.analysis.a.copy();mass=sweep.analysis.m.copy();events.clear()
    # Original inputs can no longer move the stored operating point or forces.
    c.speed=100;m.records['engine'][0][10]=20;inputs.append('power.99')
    import openswing.frequency_response as kernel
    def forbidden(*a,**kw):raise AssertionError('Refinement recomputed the loaded base or its linearization.')
    monkeypatch.setattr(kernel,'make_system',forbidden);monkeypatch.setattr(kernel,'linearize',forbidden)
    near=float(np.nextafter(16.,np.inf))
    out=sweep.extend([50.,16.,1.,0.,16.,near,np.sqrt(250)],lambda *x:events.append(x))
    assert [s['omega'] for s in out['samples']]==sorted([0.,1.,np.sqrt(250),16.,near,30.,50.])
    assert {e[0] for e in events}=={'frequency','reporting'}
    assert events[-1]==('reporting',5,5)
    assert out['base']==before['base'] and out['matrices']==before['matrices']
    assert out['frequency_refinement']['duplicate_frequencies']==[1.]
    for old in before['samples']:assert old==next(s for s in out['samples'] if s['omega']==old['omega'])
    for row in out['samples']:
        w=row['omega'];exact=1/(500+10j*w-2*w*w)
        assert z(row['responses'][0]['output']['nodes'][-1]['displacement'])[1]==pytest.approx(exact,abs=2e-12)
    np.testing.assert_array_equal(sweep.analysis.a,a);np.testing.assert_array_equal(sweep.analysis.m,mass)
    out['base']['force'][0]=999;out['samples'][0]['responses'][0]['output']['nodes'][-1]['displacement']['real'][1]=999
    unchanged=sweep.extend([0.,1.]);assert unchanged['base']==before['base']
    assert z(unchanged['samples'][0]['responses'][0]['output']['nodes'][-1]['displacement'])[1]==pytest.approx(.002,abs=2e-12)
    assert unchanged['frequency_refinement']['added_frequencies']==[]


def test_failed_batch_is_transactional_and_can_be_retried():
    sweep=FrequencySweep(powered_oscillator(),condition(),4,frequencies=[1.],gravity=[0,0,0]);before=sweep.report()
    def interrupt(*event):raise RuntimeError('Stop this batch')
    with pytest.raises(RuntimeError,match='Stop this batch'):sweep.extend([2.,3.],interrupt)
    assert sweep.report()==before
    after=sweep.extend([2.,3.])
    for row in after['samples']:
        w=row['omega'];assert z(row['responses'][0]['output']['nodes'][-1]['displacement'])[1]==pytest.approx(1/(500+10j*w-2*w*w),abs=2e-12)


def test_gust_refinement_recomputes_streamwise_phase_for_every_new_frequency():
    point=np.array([1.2,.6,-.3]);attachments='Ground\n1 0 0\nEnd\nWeight\n1 0 1.2 .6 -.3 0 .4 0\nEnd\n'
    m=model(beam(stiffness='0 0 0 0 0 0'),attachments)
    inputs=[dict(kind='gust',name=k,symmetry=k,span_mode=1) for k in ('cosine','sine')]
    sweep=FrequencySweep(m,condition(),4,frequencies=[.4],inputs=inputs,gravity=[0,0,0]);out=sweep.extend([36.,12.])
    for row in out['samples']:
        w=row['omega']
        for k,trig in enumerate((np.cos,np.sin)):
            force=np.array([0,0,.5*1.225*.4*10*trig(np.pi*point[1])*np.exp(-1j*w*point[0]/10)])
            o=row['responses'][k]['output'];np.testing.assert_allclose(z(o['global']['force']),force,atol=1e-8)
            np.testing.assert_allclose(z(o['global']['moment']),np.cross(point,force),atol=1e-8)
            assert np.dot(row['gust_profiles'][k]['streamwise_wavevector_earth'],out['inputs'][k]['convection_velocity_earth'])==pytest.approx(w,abs=1e-14)


def test_refinement_keeps_dc_gap_and_free_flight_finite_frequency_motion():
    m=parse_asw(rigid_body().dumps()+'\nEngine\n1 0 1 0 0 0 0 1 0 0 1 0 -1 0 0\nEnd\n')
    sweep=FrequencySweep(m,condition(),4,frequencies=[0.,.3],gravity=[0,0,0],frame='free');before=sweep.report();out=sweep.extend([0.,3.])
    assert not out['converged'] and out['samples'][0]==before['samples'][0]
    assert not out['samples'][0]['responses']
    for row in out['samples'][1:]:
        np.testing.assert_allclose(z(row['responses'][0]['output']['frame']['position_earth']),[-1/row['omega']**2,0,0],atol=2e-10)


def test_initial_spectrum_refinement_keeps_shift_and_initial_rate_subtraction():
    m=parse_asw(Path('examples/instrumented-oscillator.asw').read_text());profiles=json.loads(Path('examples/initial-spring.json').read_text())
    sweep=FrequencySweep(m,condition(),4,frequencies=[0.,30.],inputs=['power.1',*profiles],gravity=[0,0,0],initial_shift=.7)
    out=sweep.extend([1.,10.,100.])
    for row in out['samples']:
        w=row['omega'];s=.7+1j*w
        for i,(q0,v0) in enumerate(((.002,0),(0,.01)),1):
            value=row['responses'][i];o=value['output'];q=((2*s+10)*q0+2*v0)/(2*s*s+10*s+500)
            assert z(o['nodes'][-1]['displacement'])[1]==pytest.approx(q,abs=1e-12)
            assert z(o['nodes'][-1]['velocity'])[1]==pytest.approx(s*q-q0,abs=1e-12)
            np.testing.assert_allclose(z(value['state_rate']),s*z(value['state'])-out['inputs'][i]['resolved_state'],atol=1e-15)
        assert z(row['responses'][0]['output']['nodes'][-1]['displacement'])[1]==pytest.approx(1/(500+10j*w-2*w*w),abs=2e-12)


def test_json_boundary_rejects_changed_source_settings_expired_and_discarded_sessions():
    request=dict(action='frequency',source=powered_oscillator().dumps(),condition=dict(speed=10,alpha=0,mach=0),panels=4,gravity=[0,0,0],retain_frequency=True,frequency=dict(frequencies=[1.]))
    original=deepcopy(request);first=dispatch(request);assert request==original
    more=dict(action='extend_frequency',source=request['source'],session=first['frequency_session'],frequencies=[2.])
    for changed,match in [(dict(more,condition=request['condition']),'only new frequencies'),(dict(more,source=request['source']+'\n'),'exact ASW source')]:
        with pytest.raises(AnalysisError if match=='exact ASW source' else ValueError,match=match):dispatch(changed)
    second=dispatch(more);assert second['samples'][0]==first['samples'][0]
    third=dispatch(request)
    with pytest.raises(AnalysisError,match='expired'):dispatch(more)
    assert not dispatch(dict(action='discard_frequency',session=first['frequency_session']))['released']
    assert dispatch(dict(action='discard_frequency',session=third['frequency_session']))['released']
    with pytest.raises(AnalysisError,match='expired'):dispatch(dict(more,session=third['frequency_session']))
    json.dumps(second,allow_nan=False)


def test_new_run_reuses_loaded_matrices_after_grid_discard_and_input_change(monkeypatch):
    import openswing.frequency_sweep as sessions
    import openswing.frequency_response as kernel
    sessions._active=sessions._retained=None
    request=dict(action='frequency',source=powered_oscillator().dumps(),condition=dict(speed=10,alpha=0,mach=0),
        panels=4,gravity=[0,0,0],retain_frequency=True,frequency=dict(frequencies=[1.],inputs=['power.1']))
    first=dispatch(request);owner=sessions._active.analysis;events=[]
    dispatch(dict(action='discard_frequency',session=first['frequency_session'],retain_model=True))
    assert sessions._active is None and sessions._retained is owner
    with pytest.raises(AnalysisError,match='expired'):
        dispatch(dict(action='extend_frequency',source=request['source'],session=first['frequency_session'],frequencies=[2.]))
    def forbidden(*args,**kwargs):raise AssertionError('Matching operating point rebuilt its equilibrium or matrices.')
    with monkeypatch.context() as patch:
        patch.setattr(kernel,'make_system',forbidden);patch.setattr(kernel,'linearize',forbidden)
        second=dispatch({**request,'frequency':dict(frequencies=[2.,15.],inputs=[dict(kind='gust',name='gust')])},
                        progress=lambda *args:events.append(args))
    assert second['diagnostics']['loaded_matrices_reused']
    assert sessions._active.analysis.a is owner.a and sessions._active.analysis.m is owner.m
    assert sessions._retained is None
    assert {e[0] for e in events}=={'matrix_reuse','frequency','reporting'}
    for frequency in [2.,15.]:
        assert any(s['omega']==frequency for s in second['samples'])
    # Discard without retention really releases the live physical model.
    dispatch(dict(action='discard_frequency',session=second['frequency_session']))
    assert sessions._active is None and sessions._retained is None


@pytest.mark.parametrize('change',['condition','mesh','step','frame','gravity','model','mutated_base','beam_interpolation'])
def test_changed_operator_cannot_reuse_loaded_matrices(change,monkeypatch):
    import openswing.frequency_response as kernel
    source=powered_oscillator().dumps();aircraft=parse_asw(source);c=condition()
    options=dict(gravity=[0,0,0]);original=FrequencyAnalysis(aircraft,c,4,**options)
    panels=4
    if change=='condition':c.speed+=1
    if change=='mesh':panels=6
    if change=='step':options['step']=3e-6
    if change=='frame':options['frame']='free'
    if change=='gravity':options['gravity']=[0,0,-1]
    if change=='model':aircraft.reference[1,0]+=.1
    if change=='mutated_base':original.system.base[0]+=1e-8
    if change=='beam_interpolation':aircraft=parse_asw(source,beam_interpolation='drela-segspl-v1')
    def rebuild(*args,**kwargs):raise RuntimeError('rebuild required')
    monkeypatch.setattr(kernel,'make_system',rebuild)
    with pytest.raises(RuntimeError,match='rebuild required'):
        FrequencyAnalysis(aircraft,c,panels,_base_analysis=original,**options)


def test_frequency_owned_model_and_session_keep_interpolation_policy(monkeypatch):
    import openswing.frequency_sweep as sessions
    monkeypatch.setattr(sessions,'_active',None)
    monkeypatch.setattr(sessions,'_retained',None)
    source=powered_oscillator().dumps()
    aircraft=parse_asw(source,beam_interpolation='drela-segspl-v1')
    result=sessions.start(aircraft,condition(),4,frequencies=[1.],inputs=['power.1'],gravity=[0,0,0])
    assert sessions._active.analysis.system.network.model.beam_interpolation=='drela-segspl-v1'
    assert result['frequency_session']['beam_interpolation']=='drela-segspl-v1'
    with pytest.raises(AnalysisError,match='same beam interpolation'):
        sessions.extend(parse_asw(source),result['frequency_session'],[1.])
    assert sessions.extend(aircraft,result['frequency_session'],[1.])['samples']==result['samples']


@pytest.mark.parametrize('values',[[True],[float('nan')],[float('inf')],[-1.],[],['1'],[1+2j],[[1.]]])
def test_invalid_frequency_grids_reject_ambiguous_values(values):
    with pytest.raises(AnalysisError):frequency_grid(values)


def test_feedback_refinement_preserves_pi_and_acceleration_feedback_dynamics():
    from test_feedback import configuration,law
    inputs=['power.1','command.RY[2]'];controller=law(ki=100,ka=3)
    sweep=FrequencySweep(configuration(),condition(),4,frequencies=[0.,30.],inputs=inputs,controller=controller,gravity=[0,0,0]);before=sweep.report()
    controller['outputs'][0]['terms'][0]['gain']=-900
    out=sweep.extend([1.,10.,100.]);assert out['controller']==before['controller']
    for row in out['samples']:
        s=1j*row['omega'];den=5*s**3+30*s*s+700*s+100
        for i,expected in enumerate((s/den,(200*s+100)/den)):
            assert z(row['responses'][i]['output']['sensors'][1]['displacement_body'])[1]==pytest.approx(expected,abs=3e-9)


def test_millisecond_refinement_preserves_dimensional_mechanical_response():
    source=Path('examples/forced-oscillator.asw').read_text().replace('T 1 s','T 1 ms').replace('9.80665 1.225 340.294','9.80665e-6 1.225e6 .340294').replace('1000 .02','1000 20')
    sweep=FrequencySweep(parse_asw(source),FlightCondition(speed=.01,alpha=0,mach=0),4,frequencies=[.001,.03],gravity=[0,0,0]);out=sweep.extend([0.,.01,.015,.016,.1])
    for row in out['samples']:
        w=row['omega']*1000;exact=1/(500+10j*w-2*w*w);o=row['responses'][0]['output']
        assert z(o['nodes'][-1]['displacement'])[1]==pytest.approx(exact,abs=2e-12)
        assert z(o['nodes'][-1]['velocity'])[1]*1000==pytest.approx(1j*w*exact,abs=2e-12)
