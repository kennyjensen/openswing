"""Applied C/Q/D against independent full physical output perturbations."""
from pathlib import Path
import numpy as np
import pytest
from openswing.aero import FlightCondition
from openswing.asw import parse_asw
from openswing.linear_dynamics import make_system,linearize,DynamicSystem,output_perturbation
from openswing.applied_load_outputs import AppliedLoadTangent,AppliedLoadUnavailable
from openswing.frequency_response import HarmonicInput,input_partials,InputInfluences,FrequencyAnalysis


def freeze(a,m):
 for matrix in (a,m):
  for values in ((matrix.data,matrix.indices,matrix.indptr) if hasattr(matrix,'indptr') else (matrix,)):values.flags.writeable=False
 return a,m


def build(name='flexible',frame='fixed',extra=None):
 model=parse_asw(Path('examples',name+'.asw').read_text())
 c=FlightCondition(speed=20,alpha=3,beta=2,mach=.1,attitude=[13,-7,21],position_earth=[0,0,30],**(extra or {}))
 s,_=make_system(model,c,4,frame=frame,structured_base=True)
 a,m=freeze(*linearize(s,sparse=True))
 return s,a,m,AppliedLoadTangent(s,a,m,1e-5)


def snapshot_values(s,v,rate,width,forcing=None):
 outputs=[];snaps=[]
 for part in (np.real,np.imag):
  phase=0 if part is np.real else 1
  values=[]
  for multiplier in (1,-1,2,-2):
   h=multiplier*width
   applied=None if forcing is None else forcing(phase,h)
   _,data=s.snapshot(h*part(v),h*part(rate),forcing=applied)
   values.append(np.r_[data['applied_force'],data['applied_moment']]);snaps.append(data)
  outputs.append((8*(values[0]-values[1])-(values[2]-values[3]))/(12*width))
 return outputs[0]+1j*outputs[1],snaps


@pytest.mark.parametrize('name,frame,extra',[
 ('flexible','fixed',{}),('flexible','free',{'circulation_modes':{1:3}}),
 ('wing-body','prescribed',{'ground_effect':1}),('powered','free',{'powers':{1:7}})])
def test_complete_applied_C_Q_D_matches_full_physical_outputs(name,frame,extra):
 s,a,m,t=build(name,frame,extra);rng=np.random.default_rng(71)
 v=.02*(rng.normal(size=s.size)+1j*rng.normal(size=s.size))
 rate=.03*(rng.normal(size=s.size)+1j*rng.normal(size=s.size))
 specs=[None,dict(kind='gust',name='convected',span_mode=1,span_reference=15)]
 if name=='powered':specs.append('power.1')
 if frame=='free':specs.append('target.force.z')
 if frame=='prescribed':specs.append('acceleration.z')
 if s.network.model.controls:specs.append('control.'+str(s.network.model.controls[0]))
 for spec in specs:
  forcing=direct=None
  if spec is not None:
   B,forcings,_=input_partials(s,[HarmonicInput(s,spec,0)],.73,1e-5,influence_cache=InputInfluences(s))
   forcing=forcings[0];direct=t.input(forcing,B[:,0])
  for width in [1e-4,3e-5]:
   expected,snaps=snapshot_values(s,v,rate,width,forcing)
   result=t.apply(v,rate,forcing,direct,snaps);actual=np.r_[result['applied_force'],result['applied_moment']]
   assert np.max(abs(actual-expected)/(1+abs(expected)))<2e-8,(name,frame,spec,width,actual,expected)
 assert t.matches(s,a,m,1e-5)
 assert not t.c.flags.writeable and not t.q.flags.writeable and not t.w.data.flags.writeable


def test_off_equilibrium_position_term_is_required():
 s,_,_,_=build('flexible');n=s.network
 x=s.base.copy();x[6*(n.nn+n.ne):n.gamma_start]+=np.linspace(.01,.03,n.nc)
 s=DynamicSystem(n,x,'fixed');zero=np.zeros(s.size);width=1e-4
 a=np.empty((s.size,s.size));m=np.empty_like(a)
 for j in range(s.size):
  d=zero.copy();d[j]=width
  values=[s.residual(k*d,zero) for k in (1,-1,2,-2)]
  a[:,j]=(8*(values[0]-values[1])-(values[2]-values[3]))/(12*width)
  values=[s.residual(zero,k*d) for k in (1,-1,2,-2)]
  m[:,j]=-(8*(values[0]-values[1])-(values[2]-values[3]))/(12*width)
 a,m=freeze(a,m);t=AppliedLoadTangent(s,a,m,1e-5)
 assert np.linalg.norm(t.base_force)>1e-3
 rng=np.random.default_rng(5);v=.01*rng.normal(size=s.size);rate=.03*rng.normal(size=s.size)
 expected,snaps=snapshot_values(s,v,rate,1e-4)
 actual=t.apply(v,rate,None,None,snaps);actual=np.r_[actual['applied_force'],actual['applied_moment']]
 assert np.max(abs(actual-expected)/(1+abs(expected)))<2e-8
 wrong=t.w@(a@v-m@rate)-t.support.matrix@v
 assert np.linalg.norm(wrong-expected)>1e-3


def test_initial_rates_and_complex_scaling_retain_no_direct_input():
 s,a,m,t=build();rng=np.random.default_rng(417)
 v=.01*(rng.normal(size=s.size)+1j*rng.normal(size=s.size));x0=.02*rng.normal(size=s.size)
 rate=(.3+1.7j)*v-x0
 expected,snaps=snapshot_values(s,v,rate,1e-4)
 value=t.apply(v,rate,None,None,snaps);actual=np.r_[value['applied_force'],value['applied_moment']]
 assert np.max(abs(actual-expected)/(1+abs(expected)))<2e-8
 for amplitude in [1e-12,1.,1e12]:
  out=output_perturbation(s,amplitude*v,amplitude*rate,_load_tangent=t)
  measured=np.concatenate([np.array(out['global'][key]['real'])+1j*np.array(out['global'][key]['imag']) for key in ['applied_force','applied_moment']])/amplitude
  np.testing.assert_allclose(measured,actual,atol=2e-11,rtol=2e-11)
 with pytest.raises(AppliedLoadUnavailable,match='homogeneous'):
  t.apply(v,rate,None,object(),snaps)


def test_operator_input_and_physical_context_ownership():
 s,a,m,t=build();z=np.zeros(s.size);_,snaps=snapshot_values(s,z,z,1e-5)
 assert not t.matches(s,a.copy(),m,1e-5)
 assert not t.matches(s,a,m,2e-5)
 with pytest.raises(AppliedLoadUnavailable,match='immutable'):AppliedLoadTangent(s,a.copy(),m,1e-5)
 with pytest.raises(AppliedLoadUnavailable,match='budget'):AppliedLoadTangent(s,a,m,1e-5,limit=0)
 f=lambda *args:None;g=lambda *args:None
 direct=t.input(f,np.ones(s.size))
 with pytest.raises(AppliedLoadUnavailable,match='another'):t.apply(z,z,g,direct,snaps)
 assert not direct.value.flags.writeable
 for array,index in [(s.base,0),(s.network.gravity,2),(s.network.model.reference,(1,0))]:
  original=array[index];array[index]+=1e-4
  assert not t.matches(s,a,m,1e-5)
  with pytest.raises(AppliedLoadUnavailable,match='physical base'):t.apply(z,z,None,None,snaps)
  array[index]=original
 assert t.matches(s,a,m,1e-5)


def test_unavailable_output_matrix_preserves_full_physical_fallback(monkeypatch):
 s,a,m,t=build();rng=np.random.default_rng(90);v=.01*rng.normal(size=s.size);rate=.02*rng.normal(size=s.size)
 expected=output_perturbation(s,v,rate)
 def unavailable(*args,**kwargs):raise AppliedLoadUnavailable('injected output guard')
 monkeypatch.setattr(t,'apply',unavailable)
 actual=output_perturbation(s,v,rate,_load_tangent=t)
 for key in ['applied_force','applied_moment']:
  assert actual['global'][key]==expected['global'][key]
 assert t.fallbacks=={'injected output guard':1}


def test_internal_resultants_have_exactly_zero_applied_load_partial():
 s,a,m,t=build();n=s.network;v=np.zeros(s.size)
 v[6*n.nn:n.gamma_start]=1e8*np.random.default_rng(31).normal(size=n.gamma_start-6*n.nn)
 rate=np.zeros_like(v);expected,snaps=snapshot_values(s,v,rate,1e-5)
 values=t.apply(v,rate,None,None,snaps)
 np.testing.assert_array_equal(np.r_[values['applied_force'],values['applied_moment']],np.zeros(6))
 np.testing.assert_array_equal(expected,np.zeros(6))
