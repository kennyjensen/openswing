"""Candidate API/scope checks; physical convergence is verify_candidate.py."""
from pathlib import Path
import json
import numpy as np
import pytest
from openswing.asw import parse_asw
from openswing.aero import FlightCondition,AnalysisError
from openswing.inertia import Motion
from openswing.linear_dynamics import make_system,solve_modes
from openswing.bridge import dispatch
from openswing.equilibrium_state import identity,validate

SOURCE=Path(__file__).parent/'fixtures/isae-zero-area.asw'
@pytest.fixture
def model():return parse_asw(SOURCE.read_text())

@pytest.mark.parametrize('density',[0,-1,np.nan,np.inf,True,'1.225'])
def test_density_must_be_explicit_positive_finite(model,density):
 with pytest.raises(AnalysisError,match='positive finite'):
  make_system(model,quiescent_density=density)

@pytest.mark.parametrize('kwargs,match',[
 ({'frame':'free'},'frame'),({'velocity':[1e-100,0,0]},'zero base velocity'),
 ({'motion':Motion(rates=[0,1e-100,0])},'zero prescribed'),
 ({'controller':{}},'controllers'),({'load_targets':{'Fx':0}},'frame load targets'),
 ({'operating_constraints':[{}]},'operating constraints'),
 ({'condition':FlightCondition(speed=1e-100)},'exactly zero'),
 ({'condition':FlightCondition(speed=0,acceleration=[0,0,1])},'zero prescribed'),
 ({'condition':FlightCondition(speed=0,controls={1:1})},'nonzero control'),
 ({'condition':FlightCondition(speed=0,powers={1:1})},'nonzero control'),
 ({'condition':FlightCondition(speed=0,density=1.)},'density conflicts'),
 ({'condition':FlightCondition(speed=0,mach=.1)},'nonzero Mach'),
 ({'condition':FlightCondition(speed=0,gust={})},'gusts'),
 ({'condition':FlightCondition(speed=0,ground_effect=1)},'ground images'),
 ({'condition':FlightCondition(speed=0,circulation_modes={1:2})},'circulation settings'),
 ({'condition':FlightCondition(speed=0,freeze_influences=True)},'circulation settings'),
])
def test_scope_rejected(model,kwargs,match):
 with pytest.raises(AnalysisError,match=match):make_system(model,quiescent_density=1.225,**kwargs)

def test_mutual_exclusion_and_zero_flow_alone(model):
 with pytest.raises(AnalysisError,match='mutually exclusive'):
  solve_modes(model,quiescent_density=1.225,vacuum=True)
 model.reference[0,0]=1.
 with pytest.raises(AnalysisError,match='speed must be positive'):
  make_system(model,FlightCondition(speed=0))

def test_unsupported_air_objects_rejected(model):
 model.records['weight'][0][7]=1.
 with pytest.raises(AnalysisError,match='point-object'):make_system(model,quiescent_density=1.225)
 model.records['weight'][0][7]=0
 model.beams[0].distributions.pop('chord')
 system,_=make_system(model,quiescent_density=1.225)
 # No chord or radius means a dry mechanical beam, not a fictitious fluid mass.
 np.testing.assert_array_equal(system.base_report()['fluid']['apparent_properties']['spatial_matrix'],np.zeros((6,6)))

def test_zero_flow_never_selects_wind_direction_and_keeps_physical_pose(model,monkeypatch):
 def forbidden(*args):raise AssertionError('Zero flow must not pick a wind direction.')
 monkeypatch.setattr(FlightCondition,'vectors',forbidden)
 cond=FlightCondition(speed=0,alpha=79,beta=-31,attitude=[12,4,7],position_earth=[3,2,1],gravity_magnitude=0)
 system,_=make_system(model,cond,panels=4,quiescent_density=1.225)
 assert system.condition is None and system.network.ng==0
 np.testing.assert_array_equal(system.U0,[0,0,0]);np.testing.assert_array_equal(system.attitude,[12,4,7])
 np.testing.assert_array_equal(system.position,[3,2,1])
 base=system.base_report();assert 'CL' not in base and 'strips' not in base
 assert base['fluid']['wind_direction'] is None and not base['fluid']['circulatory']
 np.testing.assert_array_equal(base['gravity_body'],[0,0,0])
 assert model.reference[0,0]==0


def test_bridge_saves_density_and_rejects_vacuum_or_time_reuse(model):
 result=dispatch(dict(action='modes',source=model.dumps(),panels=4,condition=dict(speed=0,gravity_magnitude=0),modes=dict(quiescent_density=1.225,count=2)))
 assert not result['vacuum'] and result['fluid']['kind']=='quiescent'
 assert result['rom_output_catalog']==[]
 saved=result['base']['equilibrium_state']
 assert saved['identity']['quiescent_density']==saved['launch']['quiescent_density']==1.225
 vac,_=make_system(model,panels=4,gravity=[0,0,0])
 assert 'quiescent_density' not in identity(vac.network)
 with pytest.raises(AnalysisError,match='does not match'):validate(vac.network,saved)
 with pytest.raises(AnalysisError,match='does not match'):
  make_system(model,panels=4,gravity=[0,0,0],quiescent_density=1.0,initial_state=saved)
 air,_=make_system(model,panels=4,gravity=[0,0,0],quiescent_density=1.225,initial_state=saved)
 assert air.network.ng==0
 from openswing.time_initialization import launch_time
 with pytest.raises(AnalysisError,match='cannot launch time response'):
  launch_time(model,saved,duration=.1,dt=.01)
 assert len(json.dumps(result,allow_nan=False))>0


def test_nonmodal_entry_points_reject_quiescent(model):
 from openswing.frequency_response import solve_frequency_response
 from openswing.reduced_model import solve_reduced_model
 from openswing.stability import solve_stability
 cond=FlightCondition(speed=0)
 with pytest.raises(AnalysisError,match='not frequency response'):
  solve_frequency_response(model,cond,frequencies=[0,1],quiescent_density=1.225)
 with pytest.raises(AnalysisError,match='not ROM'):
  solve_reduced_model(model,cond,quiescent_density=1.225)
 with pytest.raises(AnalysisError,match='stability sweep'):
  solve_stability(model,cond,modes={'quiescent_density':1.225})
