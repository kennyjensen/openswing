"""Full geometry feedback against independent complete-residual stencils."""
import numpy as np
import pytest
from openswing.aero import FlightCondition
from openswing.network import StaticNetwork
from openswing.linear_dynamics import DynamicSystem
from openswing.operating import time_load_constraints
from openswing.structured_static import linearization
from openswing.tangent_influences import TangentInfluences
from openswing.geometry_tangent import GeometryFields, geometry_columns
from test_direct_circulation import model_for, state_for


CASES = [
    ('rectangular', 'fixed', {}, .08),
    ('flexible', 'free', {'circulation_modes':{1:3}}, .3),
    ('wing-body', 'free', {'ground_effect':1}, .08),
    ('wing-body', 'fixed', {'ground_effect':-1}, .08),
    ('stepped-wing-body', 'free', {}, .08),
    ('stepped-wing-body', 'fixed', {'freeze_influences':True}, .08),
    ('torsion-joint', 'free', {}, .3),
    ('rectangular', 'free', {}, 1.2),
    ('rectangular', 'free', {'aero_lag':False}, .3),
    ('jet-0', 'free', {'powers':{1:50000.}}, .3),
    ('jet-1', 'free', {'powers':{1:50000.}}, .3),
    ('jet-2', 'free', {'powers':{1:50000.}}, .3),
    ('stepped-body', 'free', {}, .08),
]


@pytest.mark.parametrize('example,frame,extra,circulation', CASES)
def test_complete_geometry_columns_match_refined_full_residual(example, frame, extra, circulation):
    model = model_for(example)
    model.reference[1] = [.7,-.2,.3];model.reference[2] = [.1,.2,-.1]
    condition = FlightCondition(speed=30, alpha=7, beta=3, mach=.2, rates=[.03,-.04,.02],
        position_earth=[0,0,30], attitude=[13,-7,21], **extra)
    n = StaticNetwork(model,4,condition,None,[],operating_constraints=time_load_constraints('prescribed' if frame=='fixed' else frame))
    s = DynamicSystem(n,state_for(n,circulation),frame)
    zero = np.zeros(s.size);baseline = s.residual(zero,zero).copy()
    scales = np.r_[np.maximum(1.,abs(s.base)),np.ones(s.size-n.size)]
    n.tangent_influences = TangentInfluences(local_geometry=True);n.aero_key=None
    actual,diagnostics = geometry_columns(n,lambda d:s.residual(d,zero),lambda d:s.unpack(d,zero)[0].x,scales)
    n.tangent_influences = None;n.aero_key=None
    for step in [1e-5,3e-6]:
        for j in range(6*n.nn):
            h=step*scales[j];d=zero.copy();d[j]=h
            p,m,pp,mm=[s.residual(f*d,zero) for f in (1,-1,2,-2)]
            expected=(8*(p-m)-(pp-mm))/(12*h)
            error=np.max(abs(actual[:,j].toarray().ravel()-expected)/(1+abs(expected)))
            assert error<2e-8,(example,frame,step,j,error)
    assert diagnostics['geometry_columns']==6*n.nn
    if extra.get('circulation_modes'):
        assert diagnostics['local_groups'] < diagnostics['original_local_groups']
    assert diagnostics['field_evaluations']==24*n.nn+1+diagnostics['field_refinement']['extra_evaluations']
    np.testing.assert_array_equal(s.residual(zero,zero),baseline)
    assert n.iteration_fields is None


@pytest.mark.parametrize('lag', [False, True])
def test_fourier_source_geometry_grouping_preserves_complete_flow_rows(lag):
    from pathlib import Path
    from openswing.asw import parse_asw
    from openswing.source_airflow import SourceAirflowNetwork

    source = (Path(__file__).parent / 'fixtures/isae-zero-area.asw').read_text()
    model = parse_asw(source, beam_interpolation='drela-segspl-v1')
    condition = FlightCondition(speed=25, alpha=3, beta=5, mach=.1,
                                circulation_modes={1: 3}, aero_lag=lag)
    n = SourceAirflowNetwork(model, 4, condition, [1., -2., -9.81], [])
    s = DynamicSystem(n, state_for(n, .03), 'fixed')
    zero = np.zeros(s.size)
    baseline = s.residual(zero, zero).copy()
    scales = np.r_[np.maximum(1., abs(s.base)), np.ones(s.size-n.size)]
    n.tangent_influences = TangentInfluences(local_geometry=True)
    actual, diagnostics = geometry_columns(n, lambda d: s.residual(d, zero),
        lambda d: s.unpack(d, zero)[0].x, scales, _direct_structural=True,
        _structural_system=s, _rotation_chart='spatial')
    assert diagnostics['local_groups'] < diagnostics['original_local_groups']
    assert diagnostics['structural_fallback'] is not None
    n.tangent_influences = None
    n.aero_key = None
    # All rows, including the globally projected flow rows, must agree with
    # independent full physical stencils at a smaller difference step.
    for j in range(6*n.nn):
        h = 3e-6*scales[j]
        direction = zero.copy(); direction[j] = h
        plus, minus, plus2, minus2 = [s.residual(k*direction, zero) for k in (1, -1, 2, -2)]
        expected = (8*(plus-minus)-(plus2-minus2))/(12*h)
        error = np.max(abs(actual[:, j].toarray().ravel()-expected)/(1+abs(expected)))
        assert error < 2e-8, (lag, j, error)
    np.testing.assert_array_equal(s.residual(zero, zero), baseline)
    assert n.iteration_fields is None


@pytest.mark.parametrize('example', ['rectangular','stepped-wing-body','jet-2','dae'])
def test_field_only_evaluation_matches_original_queries(example):
    n=StaticNetwork(model_for(example),4,FlightCondition(mach=.2,alpha=7,beta=3,
        ground_effect=1,position_earth=[0,0,30],rates=[.03,-.04,.02],
        powers={1:50000.} if example=='jet-2' else {}),None,[])
    x=state_for(n,.3)
    with linearization(n,x,.6,capture_circulation=True) as (fields,baseline):
        evaluator=GeometryFields(n,fields)
        actual=evaluator(x)
        np.testing.assert_allclose(actual.pop('circulation_residual'),
            baseline[n.gamma_start:n.operating_start],atol=2e-14,rtol=2e-14)
        for name,value in actual.items():
            expected=fields.values['vortex',name].apply(fields.circulation_aero['gamma'])
            expected+=n.condition.speed*fields.values['volume',name].reshape(-1,3)
            if name!='engine':expected+=fields.values['jet',name].reshape(-1,3)
            np.testing.assert_allclose(value,expected,atol=2e-12,rtol=2e-13)


def test_full_dae_circulation_stencil_preserves_composed_finite_step_terms():
    import json
    from pathlib import Path
    from openswing.equilibrium_state import restore, recipe_from_identity
    from openswing.structured_static import IterationFields
    saved=json.loads(Path('tests/fixtures/dae-geometry-equilibrium.json').read_text())
    n=StaticNetwork(model_for('dae'),48,FlightCondition(speed=30,alpha=5,mach=.1),None,[],
                    mesh_recipe=recipe_from_identity(saved['identity']))
    x=restore(n,saved)
    s=DynamicSystem(n,x,'fixed');zero=np.zeros(s.size)
    assert np.max(abs(s.residual(zero,zero)))<1e-9
    fields=IterationFields();fields.capture_circulation=True;n.iteration_fields=fields;n.aero_key=None
    try:
        s.residual(zero,zero);evaluator=GeometryFields(n,fields)
    finally:n.iteration_fields=None;n.aero_key=None
    evaluator(s.unpack(zero,zero)[0].x)
    # Column86/row3314 exposed the finite-stencil product discrepancy on the
    # full mesh. Refined steps also retain the original composed equations.
    for j in [86,433,1388]:
        for step in [1e-5,3e-6]:
            h=step*max(1.,abs(s.base[j]));d=zero.copy();d[j]=h
            actual=[];expected=[]
            for factor in [1.,-1.,2.,-2.]:
                actual.append(evaluator(s.unpack(factor*d,zero)[0].x)['circulation_residual'])
                expected.append(s.residual(factor*d,zero)[n.gamma_start:n.operating_start])
            def derivative(v):return (8*(v[0]-v[1])-(v[2]-v[3]))/(12*h)
            np.testing.assert_allclose(derivative(actual),derivative(expected),atol=2e-10,rtol=2e-10)


@pytest.mark.parametrize('frozen',[False,True])
def test_spatial_gust_driven_jet_geometry_in_both_influence_modes(frozen):
    test_complete_geometry_columns_match_refined_full_residual('jet-2','free',
        dict(powers={1:50000.},ground_effect=1,freeze_influences=frozen,
            gust=dict(type='sinusoid',amplitude=[.2,.1,.4],wavevector=[.21,.3,-.17],omega=.4)),.3)


@pytest.mark.parametrize('factor',[0.,.6,1.])
def test_steady_chart_including_continuation_and_frame_loads(factor):
    n=StaticNetwork(model_for('wing-body'),4,FlightCondition(mach=.2,alpha=7,beta=3),None,[],
        operating_constraints=time_load_constraints('free'))
    x=state_for(n,.08);zero=np.zeros(n.size);scales=np.maximum(1.,abs(x))
    n.tangent_influences=TangentInfluences(local_geometry=True)
    actual,_=geometry_columns(n,lambda d:n.residual(x+d,factor),lambda d:x+d,scales,factor=factor)
    n.tangent_influences=None;n.aero_key=None
    for j in range(6*n.nn):
        h=3e-6*scales[j];d=zero.copy();d[j]=h
        p,m,pp,mm=[n.residual(x+f*d,factor) for f in (1,-1,2,-2)]
        expected=(8*(p-m)-(pp-mm))/(12*h)
        assert np.max(abs(actual[:,j].toarray().ravel()-expected)/(1+abs(expected)))<2e-8


@pytest.mark.parametrize('example', ['wing-body','jet-2'])
def test_large_rotations_and_cached_pair_path_keep_complete_columns(example):
    n=StaticNetwork(model_for(example),16,FlightCondition(mach=.2,alpha=7,beta=3,
        ground_effect=1,position_earth=[0,0,30],rates=[.03,-.04,.02],
        powers={1:50000.} if example=='jet-2' else {}),None,[],
        operating_constraints=time_load_constraints('free'))
    x=state_for(n,.3);x[:6*n.nn].reshape(-1,6)[:,3:]+=[.5,-.2,.3]
    s=DynamicSystem(n,x,'free');zero=np.zeros(s.size)
    scales=np.r_[np.maximum(1.,abs(s.base)),np.ones(s.size-n.size)]
    n.tangent_influences=TangentInfluences(local_geometry=True)
    actual,_=geometry_columns(n,lambda d:s.residual(d,zero),lambda d:s.unpack(d,zero)[0].x,scales)
    assert n.tangent_influences.local_entries
    n.tangent_influences=None;n.aero_key=None
    columns=np.unique(np.r_[np.arange(6),(6*np.array([n.nn//2,n.nn-1])[:,None]+np.arange(6)).ravel()])
    for j in columns:
        h=3e-6*scales[j];d=zero.copy();d[j]=h
        p,m,pp,mm=[s.residual(f*d,zero) for f in (1,-1,2,-2)]
        expected=(8*(p-m)-(pp-mm))/(12*h)
        assert np.max(abs(actual[:,j].toarray().ravel()-expected)/(1+abs(expected)))<2e-8


def test_full_newton_correction_preserves_forward_order_and_refines_to_physical_columns():
    n=StaticNetwork(model_for('wing-body'),4,FlightCondition(mach=.2,alpha=7,beta=3),None,[])
    x=state_for(n,.3);original=n.jacobian(x,.6,_direct_circulation=False)
    n._frequency_local_geometry=True
    actual=n.jacobian(x,.6,_direct_circulation=False)
    assert n.geometry_derivative_diagnostics['geometry_columns']==6*n.nn
    assert n.geometry_derivative_diagnostics['difference_order']==1
    np.testing.assert_array_equal(actual[:,6*n.nn:],original[:,6*n.nn:])
    fine,_=geometry_columns(n,lambda d:n.residual(x+d,.6),lambda d:x+d,
        np.maximum(1.,abs(x)),step=3e-7,factor=.6,difference_order=1,
        _direct_vortex=True,_direct_volume=True)
    expected_columns=[]
    for j in range(6*n.nn):
        h=3e-6*max(1.,abs(x[j]));d=np.zeros(n.size);d[j]=h
        p,m,pp,mm=[n.residual(x+f*d,.6) for f in (1,-1,2,-2)]
        expected=(8*(p-m)-(pp-mm))/(12*h)
        expected_columns.append(expected)
    expected=np.array(expected_columns).T
    def error(value):return np.max(abs(value-expected)/(1+abs(expected)))
    coarse=error(actual[:,:6*n.nn]);refined=error(fine.toarray())
    # The Newton iteration retains its previous first-order approximation;
    # physical acceptance and the fourth-order harmonic pencil are separate.
    assert max(coarse,error(original[:,:6*n.nn]))<2e-5
    assert refined<max(.5*coarse,2e-9)


@pytest.mark.parametrize('example',['flexible','wing-body','dae'])
def test_newton_geometry_assembly_preserves_converged_physical_base(example,monkeypatch):
    from openswing.linear_dynamics import make_system
    from openswing.geometry_tangent import GeometryDerivativeUnavailable
    import openswing.geometry_tangent as module
    model=model_for(example);condition=FlightCondition(speed=30,alpha=5,mach=.1)
    actual,_=make_system(model,condition,4,structured_base=True)
    def original(*args,**kwargs):raise GeometryDerivativeUnavailable('original full Newton oracle')
    monkeypatch.setattr(module,'geometry_columns',original)
    expected,_=make_system(model,condition,4,structured_base=True)
    np.testing.assert_allclose(actual.base,expected.base,atol=1e-9,rtol=1e-9)
    for s in (actual,expected):
        zero=np.zeros(s.size)
        assert np.max(abs(s.residual(zero,zero)))<1e-9


def test_failed_local_partial_restores_full_load_cache(monkeypatch):
    from openswing.tangent_influences import TangentLoads
    n=StaticNetwork(model_for('rectangular'),4,FlightCondition(mach=.1),None,[])
    x=state_for(n);saved=TangentLoads();n._tangent_loads=saved;count=0
    def residual(delta):
        nonlocal count
        count+=1
        assert n._tangent_loads is None
        if count==3:raise ValueError('deliberate local partial failure')
        return n.residual(x+delta)
    with pytest.raises(ValueError,match='local partial failure'):
        geometry_columns(n,residual,lambda d:x+d,np.ones(n.size))
    assert n._tangent_loads is saved and not saved.entries and n.iteration_fields is None


def test_unavailable_field_derivative_restores_full_dynamic_stencils(monkeypatch):
    from openswing.geometry_tangent import GeometryDerivativeUnavailable
    from openswing.linear_dynamics import make_system,linearize
    s,_=make_system(model_for('rectangular'),FlightCondition(speed=20,mach=.1),4,structured_base=True)
    reference,rm=linearize(s)
    def unavailable(*args):raise GeometryDerivativeUnavailable('deliberate field derivative limit')
    # Both grouped geometry and individual refinement call evaluate; __call__
    # is now only the convenience wrapper for an unprepared state.
    monkeypatch.setattr(GeometryFields,'evaluate',unavailable)
    actual,am=linearize(s,sparse=True)
    np.testing.assert_allclose(actual.toarray(),reference,atol=2e-10,rtol=2e-10)
    np.testing.assert_allclose(am.toarray(),rm,atol=3e-12,rtol=3e-12)
    assert s.state_derivative_diagnostics['split_geometry_columns']==0
    assert 'field derivative limit' in s.state_derivative_diagnostics['geometry_fallback']
    assert s.network.iteration_fields is None and s.network.tangent_influences is None


def test_jet_disk_crossing_refuses_split_geometry_columns():
    from openswing.frozen_influence import lifting_geometry
    from openswing.geometry_tangent import GeometryDerivativeUnavailable
    model=model_for('jet-0');model.records['engine']=model.records['engine'][:1]
    condition=FlightCondition(speed=30,alpha=0,beta=0,mach=.1,powers={1:500.})
    n=StaticNetwork(model,4,condition,None,[])
    location=lifting_geometry(n.meshes,np.array([1.,0.,0.]))['hv'][1].copy()
    location[1]+=.2;model.records['engine'][0][4:7]=location
    n=StaticNetwork(model,4,condition,None,[])
    x=np.zeros(n.size);x[n.gamma_start:n.operating_start]=.08
    s=DynamicSystem(n,x,'fixed')
    zero=np.zeros(s.size);baseline=s.residual(zero,zero).copy()
    # An arbitrary state is enough to test the branch refusal. Public Bode
    # correctly requires equilibrium; this fixture does not claim one.
    with pytest.raises(GeometryDerivativeUnavailable,match='jet boundary'):
        geometry_columns(n,lambda z:s.residual(z,zero),lambda z:s.unpack(z,zero)[0].x,np.ones(s.size))
    np.testing.assert_array_equal(s.residual(zero,zero),baseline)
    assert n.iteration_fields is None and n.tangent_influences is None
