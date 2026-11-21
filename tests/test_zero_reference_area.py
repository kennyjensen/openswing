"""Reference normalization must not disable dimensional aerodynamic physics."""
from pathlib import Path
import json
import numpy as np
import pytest
from openswing.asw import parse_asw,AswError
from openswing.bridge import dispatch,run_json
from openswing.aero import FlightCondition,evaluate_aerodynamics,AnalysisError
from openswing.geometry import model_meshes
from openswing.linear_dynamics import make_system,linearize,eigensystem

SOURCE=(Path(__file__).parent/'fixtures/isae-zero-area.asw').read_text()


def source(area=0.,chord=.2032,span=1.2192):
    return SOURCE.replace('0.0 0.2032  1.2192',f'{area} {chord} {span}')


@pytest.mark.parametrize('area',[0.,1e-100,1.,100.])
def test_reference_area_is_preserved_without_automatic_geometry_substitution(area):
    text=source(area);model=parse_asw(text)
    assert model.reference[0,0]==area and model.dumps()==text
    again=parse_asw(model.dumps(canonical=True))
    np.testing.assert_array_equal(model.reference,again.reference)
    assert model.diagnostics==[]


@pytest.mark.parametrize('kwargs',[{'area':-1.},{'chord':0.},{'chord':-1.},{'span':0.},{'span':-1.}])
def test_negative_area_or_nonpositive_length_is_still_rejected(kwargs):
    with pytest.raises(AswError,match='nonnegative area and positive chord and span'):
        parse_asw(source(**kwargs))


def test_literal_geometry_and_physical_mass_inspection_needs_no_aerodynamic_area():
    result=json.loads(run_json(json.dumps(dict(action='inspect',source=SOURCE,panels=8))))
    assert result['reference'][0]==[0.,.2032,1.2192] and result['diagnostics']==[]
    assert result['mass_properties']['mass']==pytest.approx(1.2947*1.2192+2*.7237)


def test_programmatic_zero_area_edit_roundtrips_without_changing_physical_fields():
    model=parse_asw(source(1.));model.reference[0,0]=0.
    again=parse_asw(model.dumps())
    np.testing.assert_array_equal(model.reference,again.reference)
    np.testing.assert_array_equal(model.beams[0].distributions['mg'].values,again.beams[0].distributions['mg'].values)


@pytest.mark.parametrize('gravity',[[0.,0.,0.],[0.,0.,9.81]])
def test_original_modal_pencil_is_exactly_independent_of_reference_area(gravity):
    pencils=[]
    for area in [0.,1.]:
        system,_=make_system(parse_asw(source(area)),None,8,frame='fixed',gravity=gravity)
        pencils.append(linearize(system,1e-5))
    for x,y in zip(*pencils):np.testing.assert_array_equal(x,y)
    modes,report=eigensystem(*pencils[0],count=6)
    assert report['finite_dimension']>0
    assert all(max(m['left_backward_error'],m['right_backward_error'])<1e-9 for m in modes)


def test_structural_api_solves_zero_area_with_finite_balanced_results():
    a,b=[dispatch(dict(action='solve',mode='structural',source=source(area),panels=8,
                       gravity=[0,0,0],loads=[dict(beam=1,t=1.2192,force=[0,.1,0])])) for area in [0.,1.]]
    assert a['analysis']=='structural_static' and a['residual']<1e-8
    for field in ['applied_force','applied_moment','support_force','support_moment']:
        np.testing.assert_array_equal(a[field],b[field])
    np.testing.assert_allclose(a['force_balance'],0,atol=1e-10)
    np.testing.assert_allclose(a['moment_balance'],0,atol=1e-10)
    json.dumps(a,allow_nan=False)


COEFFICIENTS = ('CL','CY','CD','CDi','CLi','CYi','CDi_near','CDp','CDam','CDrate',
                'CDbody','CDeng','Cl','Cm','Cn','Cm_origin')


@pytest.mark.parametrize('mode',['rigid','mounted'])
def test_zero_area_preserves_loaded_physics_and_marks_coefficients_unavailable(mode):
    results = [dispatch(dict(action='solve',mode=mode,source=source(area),panels=4,
                            condition=dict(speed=10,alpha=0,beta=1,mach=0,gravity_magnitude=0)))
               for area in (0.,1e-6)]
    zero, positive = results
    assert zero['converged'] and not zero['coefficient_normalization']['available']
    assert positive['coefficient_normalization']['available']
    assert all(zero[k] is None and positive[k] is not None for k in COEFFICIENTS)
    for key in ('force','moment','moment_origin','circulation_residual','strips'):
        assert zero[key] == positive[key]
    assert abs(zero['force'][1]) > .01  # Nontrivial dimensional sideforce.
    for key in ('induced_drag','force_transverse_body','rolling_moment_wind','velocity_body'):
        assert zero['trefftz'][key] == positive['trefftz'][key]
    assert zero['efficiency'] == pytest.approx(positive['efficiency'],rel=2e-15)
    assert zero['trefftz']['available'] and not zero['trefftz']['coefficients_available']
    json.dumps(zero,allow_nan=False)


@pytest.mark.parametrize('loads_only',[False,True])
def test_direct_evaluation_allows_zero_area_and_rejects_negative_area(loads_only):
    model=parse_asw(SOURCE)
    result=evaluate_aerodynamics(model,FlightCondition(speed=10),model_meshes(model,4),_loads_only=loads_only)
    assert result['strips']
    json.dumps(result,allow_nan=False)
    model.reference[0,0] = -1.
    with pytest.raises(AnalysisError,match='finite and nonnegative'):
        evaluate_aerodynamics(model,FlightCondition(speed=10),model_meshes(model,4),_loads_only=loads_only)


def test_flowing_source_pencil_and_modal_outputs_do_not_require_reference_area():
    pencils=[]
    for area in (0.,1e-6):
        system,_=make_system(parse_asw(source(area),beam_interpolation='drela-segspl-v1'),
            FlightCondition(speed=10,alpha=0,beta=0,mach=0,gravity_magnitude=0),4,
            frame='fixed',structural_operator='drela-moving-airflow-v1')
        pencils.append(linearize(system,1e-5))
    for x,y in zip(*pencils):np.testing.assert_array_equal(x,y)
    result=dispatch(dict(action='modes',mode='modes',source=SOURCE,panels=4,
        numerics=dict(beam_interpolation='drela-segspl-v1',structural_operator='drela-moving-airflow-v1'),
        condition=dict(speed=10,alpha=0,beta=0,mach=0,gravity_magnitude=0),
        modes=dict(frame='fixed',count=2,shift=[-.1,100],method='full_shift_invert')))
    assert result['converged'] and not result['vacuum'] and len(result['modes'])==2
    for mode in result['modes']:
        assert mode['output']['global']['CL'] is None
        assert mode['output']['global']['force'] is not None
        assert max(mode['left_backward_error'],mode['right_backward_error']) < 1e-8
    json.dumps(result,allow_nan=False)


def test_coefficient_derivatives_still_require_defined_normalization():
    from openswing.rigid_derivatives import rigid_state_derivatives
    from openswing.derivatives import linearize_equilibrium
    condition=FlightCondition(speed=10,alpha=0,mach=0,gravity_magnitude=0)
    model=parse_asw(SOURCE)
    with pytest.raises(AnalysisError,match='Coefficient derivatives require a positive Reference area'):
        rigid_state_derivatives(model,condition,4)
    system,_=make_system(model,condition,4)
    with pytest.raises(AnalysisError,match='Coefficient derivatives require a positive Reference area'):
        linearize_equilibrium(system.network,system.base)
