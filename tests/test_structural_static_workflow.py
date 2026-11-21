from pathlib import Path
import runpy, sys
import numpy as np
import pytest
from openswing.asw import parse_asw
from openswing.bridge import dispatch
from openswing.inertia import Motion, InertiaModel
from openswing.network import StaticNetwork, solve_static
from openswing.structured_static import equilibrate
from openswing.time_initialization import launch_time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from isae_st3_static_reference import solve as reference


def source(name='m15_0'):
    return (ROOT/f'examples/isae-st3-static-{name}.asw').read_text()


@pytest.mark.parametrize('name',['0_3_90','p15_0','m15_0'])
def test_literal_static_couple_and_independent_continuum(name):
    text=source(name);model=parse_asw(text)
    before=model.dumps();result=dispatch(dict(action='solve',mode='structural',source=text,panels=64))
    assert model.dumps()==before==text
    weights=model.records['weight'];moment=.07*(weights[0][5]-weights[1][5])
    exact=reference(name,couple=moment)
    np.testing.assert_allclose(result['nodes'][-1]['position'],exact['positions'][-1],atol=3e-6,rtol=0)
    np.testing.assert_allclose(result['nodes'][-1]['rotation'],exact['rotations'][-1],atol=1e-6,rtol=0)
    if name!='0_3_90':
        coarse=dispatch(dict(action='solve',mode='structural',source=text,panels=32))
        error=lambda r:np.max(abs(np.array(r['nodes'][-1]['rotation'])-exact['rotations'][-1]))
        assert error(result)<error(coarse)/3.5
    assert result['residual']<1e-8 and result['structural_only'] and result['strips']==[]
    np.testing.assert_allclose(result['force_balance'],0,atol=1e-10)
    np.testing.assert_allclose(result['moment_balance'],0,atol=1e-10)
    assert result['mass_properties']['physical'] is False and result['mass_properties']['cg'] is None
    assert 'launch' not in result['equilibrium_state']
    corrected=dispatch(dict(action='solve',mode='structural',source=text,panels=64,initial_state=result['equilibrium_state']))
    np.testing.assert_allclose(corrected['nodes'][-1]['position'],result['nodes'][-1]['position'],atol=1e-10)


def test_inspection_retains_literal_geometry_and_explicit_mass_classification():
    result=dispatch(dict(action='inspect',source=source(),panels=8))
    assert result['signed_point_weights']==[1] and not result['mass_properties']['physical']
    assert result['diagnostics']==[]
    with pytest.raises(ValueError,match='Point weights must be nonnegative'):
        StaticNetwork(parse_asw(source()),8,None,None,[])


@pytest.mark.parametrize('gravity',[[0,0,0],[1.5,-2.,-7.3],[0,0,9.81]])
def test_signed_pylon_wrench_is_exact_at_large_arbitrary_rotation(gravity):
    from scipy.spatial.transform import Rotation
    model=parse_asw(source());n=StaticNetwork(model,8,None,gravity,[],allow_signed_point_weights=True)
    x=np.zeros(n.size);q=Rotation.from_rotvec([.3,-.4,.2]).as_matrix()
    x[:6*n.nn].reshape(-1,6)[:,3:]=[.3,-.4,.2]
    _,data=n.residual(x,detail=True)
    expected_force=np.zeros(3);expected_moment=np.zeros(3)
    for row in model.records['weight']:
        index=n.node(*row[:2]);force=row[5]/model.constants[0]*np.array(gravity)
        point=n.rj[index]+q@(row[2:5]-n.rj[index])
        expected_force+=force;expected_moment+=np.cross(point-model.reference[1],force)
    np.testing.assert_allclose(data['force'].sum(axis=0),expected_force,atol=2e-14)
    moment=(data['moment']+np.cross(data['r']-model.reference[1],data['force'])).sum(axis=0)
    np.testing.assert_allclose(moment,expected_moment,atol=2e-14)


def test_static_gravity_can_be_removed_or_reversed():
    outputs=[dispatch(dict(action='solve',mode='structural',source=source(),panels=16,gravity=g)) for g in [[0,0,0],[0,0,-9.81],[0,0,9.81]]]
    assert outputs[0]['max_displacement']<1e-12
    assert outputs[1]['nodes'][-1]['position'][2]==pytest.approx(-outputs[2]['nodes'][-1]['position'][2],abs=1e-10)


@pytest.mark.parametrize('action,options',[
    ('solve',dict(mode='mounted')),('solve',dict(mode='rigid')),
    ('modes',dict(modes={'vacuum':True})),('time',dict(time={'duration':.01,'dt':.01})),
    ('frequency',dict(frequency={'frequencies':[1.]}))])
def test_physical_analysis_rejects_negative_mass(action,options):
    with pytest.raises(ValueError,match='Point weights must be nonnegative'):
        dispatch(dict(action=action,source=source(),panels=8,condition={'speed':10,'alpha':0},**options))


@pytest.mark.parametrize('extra',[
    {'condition':{'speed':1}}, {'operating_constraints':[{'variable':'acceleration.z','quantity':'force.z','target':0}]},
    {'controller':{}}, {'derivatives':{}}])
def test_static_mode_does_not_silently_consume_flight_or_feedback_settings(extra):
    with pytest.raises(ValueError):dispatch(dict(action='solve',mode='structural',source=source(),panels=8,**extra))


def test_signed_network_rejects_dynamic_residual_and_steady_acceleration():
    model=parse_asw(source())
    with pytest.raises(ValueError,match='zero motion'):
        StaticNetwork(model,8,None,None,[],motion=Motion(acceleration=[0,0,1]),allow_signed_point_weights=True)
    n=StaticNetwork(model,8,None,None,[],allow_signed_point_weights=True);x,_=equilibrate(n)
    for options in [{'elastic_motion':[np.zeros_like(n.rj)]*4}, {'motion_override':Motion(rates=[0,1,0])}]:
        with pytest.raises(ValueError,match='not physical negative masses'):n.residual(x,**options)


def test_positive_mass_static_state_remains_physical_and_can_seed_vacuum_dynamics():
    text=(ROOT/'examples/transient-wing.asw').read_text()+'\nWeight\n1 8 .8 8 .3 9.80665\nEnd\n'
    result=dispatch(dict(action='solve',mode='structural',source=text,panels=4,gravity=[0,0,0]))
    assert result['mass_properties'].get('physical',True) and 'launch' in result['equilibrium_state']
    dynamic=launch_time(parse_asw(text),result['equilibrium_state'],duration=.01,dt=.01,frame='prescribed')
    assert dynamic['converged']
