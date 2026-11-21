"""Independent spectra, branch ambiguity and actual operating-point sweeps."""
from copy import deepcopy
from pathlib import Path
import json
import numpy as np
import pytest
from openswing.aero import AnalysisError,FlightCondition
from openswing.asw import parse_asw
from openswing.stability import trace_spectrum,match_roots,solve_stability,physical_scales,representatives


def mode(root,vector,index=0,scale=10.):
    return dict(root=complex(root),vector=np.asarray(vector,dtype=complex),mode_index=index,real=complex(root).imag==0,scale=scale)


def test_complex_crossing_tracks_shape_through_reordered_spectra_and_refines_physical_zero():
    # Characteristic factors: (s-(p^2-2)-3i)(s-(p^2-2)+3i)(s+2-5i)(s+2+5i).
    def evaluate(p):
        roots=[mode(p*p-2+3j,[1,0]),mode(-2+5j,[0,1],1)]
        if p>1.3:roots.reverse()
        return roots,dict(spectrum_complete=True)
    out=trace_spectrum(evaluate,[1.,1.5,2.],parameter_rtol=1e-6)
    assert out['converged'] and out['tracking_complete'] and len(out['branches'])==2
    boundary=out['boundaries'][0]
    assert boundary['status']=='resolved' and boundary['direction']=='destabilizing'
    assert boundary['value']==pytest.approx(np.sqrt(2),rel=1e-7)
    assert boundary['bracket'][0]<=np.sqrt(2)<=boundary['bracket'][1]
    assert boundary['eigenvalue'][1]==3
    assert boundary['point'] in [s['index'] for s in out['points']]


def test_frequency_order_crossing_keeps_orthogonal_shapes_and_arbitrary_complex_phase():
    def evaluate(p):
        roots=[mode(-1+(3+p)*1j,np.exp(2j*p)*np.array([1,0])),mode(-1+(3-p)*1j,[0,7j],1)]
        roots.sort(key=lambda r:r['root'].imag)
        return roots,{}
    out=trace_spectrum(evaluate,[-.5,0.,.5],refine=False)
    assert out['tracking_complete'] and len(out['branches'])==2
    histories=[[out['points'][s['point']]['roots'][s['root']]['eigenvalue'][1] for s in b['samples']] for b in out['branches']]
    assert histories==[[2.5,3,3.5],[3.5,3,2.5]]


def test_identical_repeated_shapes_are_ambiguous_and_do_not_invent_crossing():
    def evaluate(p):return [mode(p+3j,[1,0]),mode(p+3j,[1,0],1)],{}
    out=trace_spectrum(evaluate,[-1.,1.])
    assert not out['tracking_complete'] and len(out['gaps'])==1 and not out['boundaries']
    assert len(out['branches'])==4


def test_failed_point_and_disappearing_root_break_paths():
    def evaluate(p):
        if p==2:raise AnalysisError('independent failed equilibrium')
        return [mode((p-2)+3j,[1,0])] if p!=4 else [],{}
    out=trace_spectrum(evaluate,[1,2,3,4])
    assert not out['converged'] and len(out['gaps'])==3 and not out['boundaries']
    assert out['points'][1]['error']=='independent failed equilibrium'


def test_real_complex_splitting_and_large_steps_are_not_silently_connected():
    matches,missing,new=match_roots([mode(-1,[1])],[mode(1+1j,[1])])
    assert not matches and missing==new==[0]
    matches,_,_=match_roots([mode(-1+1j,[1],scale=1)],[mode(100+1j,[1],scale=1)],max_distance=.1)
    assert not matches


@pytest.mark.parametrize('factor',[1e-10,1.,1e10])
def test_aperiodic_crossing_and_extreme_time_units_have_identical_parameter_boundary(factor):
    def evaluate(p):return [mode(factor*(p*p-2),[1],scale=10*factor)],{}
    out=trace_spectrum(evaluate,[1.,2.],parameter_rtol=1e-6)
    boundary=out['boundaries'][0]
    assert boundary['status']=='resolved' and boundary['kind']=='aperiodic instability'
    assert boundary['value']==pytest.approx(np.sqrt(2),rel=1e-6)


def test_discontinuous_growth_jump_is_not_a_resolved_flutter_zero():
    def evaluate(p):return [mode((-1 if p<1.5 else 1)+3j,[1])],{}
    out=trace_spectrum(evaluate,[1.,2.],max_iterations=16)
    assert out['boundaries'][0]['status']=='unresolved'
    assert not out['refinement_complete']


def test_stabilizing_crossing_and_unrequested_refinement_are_explicit():
    def evaluate(p):return [mode((2-p*p)+3j,[1])],{}
    out=trace_spectrum(evaluate,[1.,2.],refine=False)
    assert out['boundaries'][0]['direction']=='stabilizing'
    assert out['boundaries'][0]['status']=='unrefined' and len(out['points'])==2


@pytest.mark.parametrize('values',[[1],[1,1],[2,1],[1,float('nan')]])
def test_invalid_parameter_grids(values):
    with pytest.raises(AnalysisError,match='strictly increasing'):trace_spectrum(lambda p:([],{}),values)


@pytest.fixture(scope='module')
def oscillator_sweep():
    source=Path('examples/instrumented-oscillator.asw').read_text()
    model=parse_asw(source)
    result=solve_stability(model,FlightCondition(speed=10,alpha=0,mach=0),4,gravity=[0,0,0],
        values=[10,30],modes=dict(count=2),refine=False)
    return model,result


def test_real_model_preserves_physical_modes_across_changing_numerical_scales(oscillator_sweep):
    model,out=oscillator_sweep
    assert out['converged'] and out['tracking_complete'] and not out['spectrum_complete']
    assert len(out['branches'])==1 and not out['boundaries']
    assert out['branches'][0]['samples'][1]['match']['assurance']==pytest.approx(1,abs=1e-9)
    roots=[complex(*point['roots'][0]['eigenvalue']) for point in out['points']]
    np.testing.assert_allclose(roots,np.roots([2,10,500])[0],rtol=1e-8)
    # Artificially re-express every descriptor coordinate with the second
    # point's scale factors. The recovered physical vector must be identical.
    first=out['points'][0]['result'];second=deepcopy(first)
    l=second['diagnostics']['state_layout']
    for key in ('local_velocity','local_rates','circulation'):l[key]['scale']*=13
    l['internal_loads']['force_scale']*=7;l['internal_loads']['moment_scale']*=7
    old,new=physical_scales(first),physical_scales(second)
    for m in second['modes']:
        for part in ('real','imag'):m['right'][part]=(np.array(m['right'][part])*old/new).tolist()
    a,b=representatives(first,old),representatives(second,old)
    matches,missing,born=match_roots(a,b)
    assert not missing and not born and matches[0]['assurance']==pytest.approx(1,abs=1e-14)
    json.dumps(out,allow_nan=False)


def test_incomplete_spectrum_is_not_claimed_complete_and_parameter_validation(oscillator_sweep):
    model,out=oscillator_sweep
    assert not out['spectrum_complete']
    with pytest.raises(AnalysisError,match='trim unknown'):
        solve_stability(model,FlightCondition(),4,parameter='speed',operating_constraints=[dict(variable='speed',quantity='CL',target=.3)])
    with pytest.raises(AnalysisError,match='Target index'):
        solve_stability(model,FlightCondition(),4,parameter='target.0')
    with pytest.raises(AnalysisError,match='not declared'):
        solve_stability(model,FlightCondition(),4,parameter='control.99')


def test_absolute_parameter_tolerance_handles_a_boundary_close_to_zero():
    def evaluate(p):return [mode((p-1e-9)+3j,[1])],{}
    out=trace_spectrum(evaluate,[-1,1],parameter_atol=1e-7)
    assert out['boundaries'][0]['status']=='resolved'
    assert abs(out['boundaries'][0]['value']-1e-9)<1e-7


def test_boundary_solve_failure_is_retained_and_never_marked_resolved():
    def evaluate(p):
        if 1.1<p<1.9:raise AnalysisError('refinement tangent failed')
        return [mode((p-1.5)+3j,[1])],{}
    out=trace_spectrum(evaluate,[1,2])
    b=out['boundaries'][0]
    assert b['status']=='unresolved' and b['reason']=='refinement tangent failed'
    assert not out['converged'] and out['points'][-1]['kind']=='refinement'


def test_pair_representatives_preserve_repeated_independent_pairs_and_negative_only(oscillator_sweep):
    _,out=oscillator_sweep;result=deepcopy(out['points'][0]['result']);size=result['diagnostics']['full_dimension']
    template=deepcopy(result['modes'][0]);template['eigenvalue']=[-1,3]
    result['modes']=[]
    for coordinate,imag in [(0,-3),(1,3),(0,3),(1,-3)]:
        m=deepcopy(template);m['eigenvalue'][1]=imag
        v=np.zeros(size,dtype=complex);v[coordinate]=(1+2j) if imag>0 else (1-2j)
        m['right']=dict(real=v.real.tolist(),imag=v.imag.tolist());result['modes'].append(m)
    scales=physical_scales(result);roots=representatives(result,scales)
    assert len(roots)==2 and [r['conjugate_index'] for r in roots]==[2,3]
    assert all(r['root']==-1+3j for r in roots)
    result['modes']=result['modes'][:1]
    root=representatives(result,scales)[0]
    assert root['root']==-1+3j and root['conjugate_index'] is None


@pytest.mark.parametrize('parameter',['power.1','target.0'])
def test_bridge_sweeps_actuator_or_operating_target_and_retains_loaded_points(parameter):
    from openswing.bridge import run_json
    source=Path('examples/instrumented-oscillator.asw').read_text()
    request=dict(action='stability',source=source,condition=dict(speed=10,alpha=0,mach=0),panels=4,gravity=[0,0,0],
        modes=dict(count=2),stability=dict(parameter=parameter,values=[0,1],refine=False))
    if parameter=='target.0':request['operating_constraints']=[dict(variable='power.1',quantity='power.1',target=0)]
    result=json.loads(run_json(json.dumps(request)))
    assert result['converged'] and result['tracking_complete']
    for point in result['points']:
        tip=max(point['result']['base']['nodes'],key=lambda n:n['t'])
        assert tip['position'][1]-tip['jig_position'][1]==pytest.approx(point['value']/500,abs=1e-9)
        if parameter=='target.0':assert point['operating_constraints'][0]['target']==point['value']
    assert '"target": 0' in json.dumps(request) if parameter=='target.0' else request['condition'].get('powers') is None


def test_adaptive_grid_follows_rotating_shapes_and_preserves_requested_endpoints():
    def evaluate(p):return [mode(-1+3j,[np.cos(p*np.pi/2),np.sin(p*np.pi/2)])],{}
    coarse=trace_spectrum(evaluate,[0,1],refine=False)
    adaptive=trace_spectrum(evaluate,[0,1],refine=False,adaptive=True)
    assert not coarse['tracking_complete']
    assert adaptive['tracking_complete'] and len(adaptive['branches'])==1
    assert [adaptive['points'][i]['value'] for i in adaptive['tracking_points']]==[0,.25,.5,.75,1]
    assert len(adaptive['subdivisions'])==3 and adaptive['settings']['values']==[0,1]


def test_adaptive_warm_corrector_retries_failed_endpoints_after_intermediate_states():
    last=[None];calls=[]
    def evaluate(p):
        calls.append(p)
        if last[0] is not None and p-last[0]>.3:raise AnalysisError('step exceeds corrector convergence radius')
        last[0]=p
        return [mode(-1+3j,[1])],{}
    out=trace_spectrum(evaluate,[0,1],refine=False,adaptive=True,resample_after_subdivision=True)
    assert out['converged'] and out['tracking_complete'] and calls.count(1)==3
    assert [out['points'][i]['value'] for i in out['tracking_points']]==[0,.25,.5,.75,1]
    failed=[p for p in out['points'] if not p['converged']]
    assert failed and all('superseded_by' in p for p in failed)
    assert all(out['points'][p['superseded_by']]['value']==p['value'] for p in failed)


def test_adaptive_budget_exhaustion_keeps_ambiguity_gaps_even_with_zero_margin():
    def evaluate(p):return [mode(p+3j,[1]),mode(p+3j,[1],1)],{}
    out=trace_spectrum(evaluate,[-1,1],adaptive=True,max_extra_points=2,ambiguity_margin=0)
    assert len(out['subdivisions'])==2 and not out['tracking_complete'] and not out['boundaries']
    assert any(g['adaptive_limit_reached'] for g in out['gaps'])


@pytest.mark.parametrize('options',[{'max_subdivisions':True},{'max_extra_points':257},{'adaptive':'yes'}])
def test_adaptive_invalid_budgets(options):
    with pytest.raises(AnalysisError,match='Adaptive'):trace_spectrum(lambda p:([],{}),[0,1],**options)


def test_warm_trim_sweep_preserves_equilibria_and_input_seed():
    from openswing.network import solve_static
    from test_feedback import configuration,condition,law
    model=configuration();c=condition();control=law(kd=0,ki=100)
    constraints=[dict(variable='command.RY[2]',quantity='force.y',target=2)]
    first=solve_static(model,c,4,gravity=[0,0,0],controller=control,operating_constraints=constraints)
    saved=deepcopy(first['equilibrium_state'])
    out=solve_stability(model,c,4,parameter='target.0',values=[2,3],modes=dict(count=2),gravity=[0,0,0],
        controller=control,operating_constraints=constraints,initial_state=saved,warm_start=True,refine=False,adaptive=True)
    assert out['converged'] and out['tracking_complete']
    for p in out['points']:
        base=p['result']['base']
        assert p['initialization']['warm']
        assert base['sensors'][1]['displacement_body'][1]==pytest.approx(p['value']/500,abs=1e-9)
        assert base['feedback']['commands']['RY[2]']==pytest.approx(2+p['value']/500,abs=1e-9)
    assert out['points'][1]['initialization']['parent_value']==2
    assert saved==first['equilibrium_state'] and constraints[0]['target']==2



def test_boundary_refinement_rejects_an_exact_shape_tie_even_with_zero_margin():
    def evaluate(p):
        roots=[mode(p-1.5+3j,[1])]
        if p==1.5:roots.append(mode(3j,[1],1))
        return roots,{}
    out=trace_spectrum(evaluate,[1,2],ambiguity_margin=0)
    assert out['boundaries'][0]['status']=='unresolved'
    assert out['boundaries'][0]['reason']=='Boundary mode cannot be matched uniquely to both bracket endpoints.'
