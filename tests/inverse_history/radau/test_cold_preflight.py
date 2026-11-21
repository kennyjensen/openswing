"""An incompatible held position/velocity must fail before costly completion."""
from pathlib import Path
import pytest
root=Path(__file__).parent/'inputs'
from openswing.asw import parse_asw
from openswing.aero import AnalysisError,FlightCondition
from openswing.time_integration import solve_time


@pytest.mark.parametrize('rotating',[False,True])
def test_wrong_initial_earth_velocity_refuses_without_derivative_sweep(monkeypatch,rotating):
 import openswing.time_cold_initial as cold
 def forbidden(*args,**kwargs):raise AssertionError('incompatible initial frame reached derivative completion')
 monkeypatch.setattr(cold,'consistent_initial',forbidden)
 source=(root/('rotating.asw' if rotating else 'rigid.asw')).read_text()
 c=FlightCondition(speed=10.3 if rotating else 10.,alpha=5.,mach=0.,rates=[0,0,3] if rotating else [0,0,0])
 with pytest.raises(AnalysisError,match='incompatible.*Earth velocity'):
  solve_time(parse_asw(source),c,4,duration=.04,dt=.02,order=5,frame='free',gravity=[0,0,0],forcing=(root/'position.tbl').read_text(),actuator_constraints=[dict(variable='power.1',quantity='position_earth.x',target=0.)])


@pytest.mark.parametrize('rotating',[False,True])
def test_compatible_initial_frame_proceeds_to_original_completion(monkeypatch,rotating):
 import openswing.time_cold_initial as cold
 class ReachedCompletion(Exception):pass
 def reached(*args,**kwargs):raise ReachedCompletion()
 monkeypatch.setattr(cold,'consistent_initial',reached)
 source=(root/('rotating.asw' if rotating else 'rigid.asw')).read_text()
 c=FlightCondition(speed=10.3 if rotating else 10.,alpha=0.,mach=0.,rates=[0,0,3] if rotating else [0,0,0])
 with pytest.raises(ReachedCompletion):
  solve_time(parse_asw(source),c,4,duration=.04,dt=.02,order=5,frame='free',gravity=[0,0,0],forcing=(root/'position.tbl').read_text(),actuator_constraints=[dict(variable='power.1',quantity='position_earth.x',target=0.)])
