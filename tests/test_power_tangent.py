import numpy as np
import pytest
from openswing.aero import FlightCondition
from openswing.network import StaticNetwork
from openswing.linear_dynamics import DynamicSystem
from openswing.frequency_response import HarmonicInput,input_partials,InputInfluences
from openswing.power_tangent import power_column,PowerDerivativeUnavailable
from openswing.operating import time_load_constraints
from test_direct_circulation import model_for,state_for

@pytest.mark.parametrize('name,frame,extra',[
 ('jet-0','fixed',{'powers':{1:50000.}}),('jet-1','free',{'powers':{1:50000.}}),
 ('jet-2','fixed',{'powers':{1:50000.}}),('jet-2','free',{'powers':{1:50000.},'freeze_influences':True}),
 ('dae','fixed',{}),('dae','free',{}),('jet-0','fixed',{})])
def test_complete_power_column_matches_refined_physical_stencils(name,frame,extra):
 n=StaticNetwork(model_for(name),4,FlightCondition(speed=30,alpha=7,beta=3,mach=.2,
  rates=[.03,-.04,.02],ground_effect=1,position_earth=[0,0,30],**extra),None,[],
  operating_constraints=time_load_constraints('prescribed' if frame=='fixed' else frame))
 s=DynamicSystem(n,state_for(n,.08),frame);z=np.zeros(s.size)
 before=s.residual(z,z).copy();channel=HarmonicInput(s,'power.1',0)
 actual,fields=power_column(s,channel,1e-5)
 assert fields is None and n.iteration_fields is None
 forcing,_=channel.at_frequency(.1)
 for width in [1e-3,3e-4]:
  h=width*channel.scale
  v=[s.residual(z,z,forcing=forcing(0,m*h)) for m in (1,-1,2,-2)]
  expected=(8*(v[0]-v[1])-(v[2]-v[3]))/(12*h)
  assert np.max(abs(actual-expected)/(1+abs(expected)))<2e-8,(name,frame,width)
 np.testing.assert_array_equal(s.residual(z,z),before)

@pytest.mark.parametrize('stage',['capture','late'])
def test_unavailable_power_chain_keeps_original_full_stencils(stage,monkeypatch):
 import openswing.power_tangent as power
 n=StaticNetwork(model_for('jet-2'),4,FlightCondition(speed=30,alpha=7,mach=.1,powers={1:50000.}),None,[])
 s=DynamicSystem(n,state_for(n,.08));channel=HarmonicInput(s,'power.1',0)
 def unavailable(*args,**kwargs):raise PowerDerivativeUnavailable('injected power chain failure')
 with monkeypatch.context() as patch:
  patch.setattr(power,'power_column',unavailable)
  reference,_,_=input_partials(s,[channel],.1,1e-5)
 if stage=='capture':monkeypatch.setattr(power.Capture,'get',unavailable)
 else:monkeypatch.setattr(power.EnginePowerDerivative,'jet',unavailable)
 cache={};actual,_,_=input_partials(s,[channel],.1,1e-5,constant_inputs=cache)
 np.testing.assert_array_equal(actual,reference)
 assert n.iteration_fields is None
 np.testing.assert_array_equal(cache[0][0],actual[:,0])
 assert not cache[0][0].flags.writeable

def test_direct_power_fields_share_the_same_complete_jet_chain():
 from openswing.linear_dynamics import make_system,linearize
 s,_=make_system(model_for('powered'),FlightCondition(speed=20,alpha=3,mach=.1,powers={1:7.}),4,structured_base=True)
 linearize(s,sparse=True,_output_fields=True)
 fields=s._output_field_tangent;assert fields.active
 channel=HarmonicInput(s,'power.1',0);column,field_column=power_column(s,channel,1e-5,fields)
 z=np.zeros(s.size);forcing,_=channel.at_frequency(.1)
 samples=[];h=1e-3*channel.scale
 for m in (1,-1,2,-2):
  f=forcing(0,m*h)
  _,value=fields.probe(lambda:s.residual(z,z,forcing=f),z,z,f);samples.append(value)
 expected=(8*(samples[0]-samples[1])-(samples[2]-samples[3]))/(12*h)
 assert np.max(abs(field_column-expected)/(20+abs(expected)))<2e-8
 assert not field_column.flags.writeable
 actual,forcings,_=input_partials(s,[channel],.1,1e-5,_field_tangent=fields)
 np.testing.assert_array_equal(actual[:,0],column)
 np.testing.assert_array_equal(fields.input_column(forcings[0]),field_column)
