import numpy as np
import pytest
from openswing.aero import FlightCondition
from openswing.network import StaticNetwork
from openswing.linear_dynamics import DynamicSystem
from openswing.frequency_response import HarmonicInput,input_partials
from openswing.gust_tangent import gust_column,GustDerivativeUnavailable
from openswing.operating import time_load_constraints
from test_direct_circulation import model_for,state_for

@pytest.mark.parametrize('name,frame,extra',[
 ('flexible','fixed',{'circulation_modes':{1:3}}),('wing-body','free',{'ground_effect':1}),
 ('stepped-wing-body','fixed',{'ground_effect':-1}),('stepped-wing-body','free',{'freeze_influences':True}),
 ('stepped-body','fixed',{}),('torsion-joint','free',{}),('jet-0','fixed',{'powers':{1:50000.}}),
 ('jet-1','free',{'powers':{1:50000.}}),('jet-2','fixed',{'powers':{1:50000.}}),('dae','fixed',{})])
@pytest.mark.parametrize('wave',['uniform','convected'])
def test_complete_complex_gust_column_matches_refined_physical_stencils(name,frame,extra,wave):
 n=StaticNetwork(model_for(name),4,FlightCondition(speed=30,alpha=7,beta=3,mach=.2,
  rates=[.03,-.04,.02],position_earth=[0,0,30],attitude=[13,-7,21],
  gust=dict(type='expression',components=['.01*x','0','.02*y']),**extra),None,[],
  operating_constraints=time_load_constraints('prescribed' if frame=='fixed' else frame))
 s=DynamicSystem(n,state_for(n,.08),frame);z=np.zeros(s.size);before=s.residual(z,z).copy()
 channel=HarmonicInput(s,dict(kind='gust',wave=wave,span_mode=1,symmetry='sine',direction=[.1,-.2,1.]),0)
 for omega in [.3,17.]:
  actual,field=gust_column(s,channel,omega,1e-5);assert field is None
  forcing,_=channel.at_frequency(omega)
  for width in [1e-4,3e-5]:
   h=width*channel.scale;parts=[]
   for part in (0,1):
    v=[s.residual(z,z,forcing=forcing(part,f*h)) for f in (1,-1,2,-2)]
    parts.append((8*(v[0]-v[1])-(v[2]-v[3]))/(12*h))
   expected=parts[0]+1j*parts[1]
   assert np.max(abs(actual-expected)/(1+abs(expected)))<2e-8,(name,wave,omega,width)
 np.testing.assert_array_equal(s.residual(z,z),before)
 assert n.iteration_fields is None

@pytest.mark.parametrize('stage',['capture','late'])
def test_failed_gust_partial_restores_full_input_stencil(stage,monkeypatch):
 import openswing.gust_tangent as gust
 n=StaticNetwork(model_for('wing-body'),4,FlightCondition(speed=30,alpha=7,mach=.1),None,[])
 s=DynamicSystem(n,state_for(n,.08));channel=HarmonicInput(s,dict(kind='gust',span_mode=1),0)
 def fail(*args,**kwargs):raise GustDerivativeUnavailable('injected gust derivative failure')
 with monkeypatch.context() as patch:
  patch.setattr(gust,'gust_column',fail)
  reference,_,_=input_partials(s,[channel],17.,1e-5)
 if stage=='capture':monkeypatch.setattr(gust.Capture,'get',fail)
 else:
  original=gust.GustFlow.velocity;calls=[0]
  def late(*args,**kwargs):
   calls[0]+=1
   if calls[0]==3:fail()
   return original(*args,**kwargs)
  monkeypatch.setattr(gust.GustFlow,'velocity',late)
 cache={};actual,_,_=input_partials(s,[channel],17.,1e-5,constant_inputs=cache)
 np.testing.assert_array_equal(actual,reference)
 assert not cache and n.iteration_fields is None

def test_gust_field_packet_contains_only_the_induced_chain():
 from openswing.linear_dynamics import make_system,linearize
 s,_=make_system(model_for('powered'),FlightCondition(speed=20,alpha=3,mach=.1,powers={1:7.}),4,structured_base=True)
 linearize(s,sparse=True,_output_fields=True);fields=s._output_field_tangent;assert fields.active
 channel=HarmonicInput(s,dict(kind='gust',span_mode=1),0)
 actual,field=gust_column(s,channel,17.,1e-5,fields);assert not field.flags.writeable
 z=np.zeros(s.size);forcing,_=channel.at_frequency(17.);parts=[];h=1e-4*channel.scale
 for part in (0,1):
  values=[]
  for m in (1,-1,2,-2):
   f=forcing(part,m*h);_,value=fields.probe(lambda:s.residual(z,z,forcing=f),z,z,f);values.append(value)
  parts.append((8*(values[0]-values[1])-(values[2]-values[3]))/(12*h))
 expected=parts[0]+1j*parts[1]
 assert np.max(abs(field-expected)/(20+abs(expected)))<2e-8
 result,forcings,_=input_partials(s,[channel],17.,1e-5,_field_tangent=fields)
 np.testing.assert_array_equal(result[:,0],actual)
 np.testing.assert_array_equal(fields.input_column(forcings[0]),field)
