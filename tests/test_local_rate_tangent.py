import numpy as np
import pytest
from openswing.aero import FlightCondition
from openswing.network import StaticNetwork
from openswing.linear_dynamics import DynamicSystem
from openswing.local_rate_tangent import local_rate_columns,LocalRateUnavailable
from openswing.tangent_influences import TangentInfluences
from test_direct_circulation import model_for,state_for

@pytest.mark.parametrize('name,extra',[
 ('flexible',{}),('flexible',{'circulation_modes':{1:3}}),
 ('wing-body',{'ground_effect':1}),('stepped-wing-body',{'ground_effect':-1}),
 ('stepped-wing-body',{'freeze_influences':True}),('stepped-body',{}),
 ('jet-2',{'powers':{1:50000.}}),('dae',{})])
def test_complete_local_motion_columns(name,extra):
 model=model_for(name)
 model.reference[1]=[.7,-.2,.3];model.reference[2]=[.1,.2,-.1]
 n=StaticNetwork(model,4,FlightCondition(speed=30,alpha=7,beta=3,mach=.2,
  rates=[.03,-.04,.02],position_earth=[0,0,30],attitude=[13,-7,21],**extra),None,[])
 s=DynamicSystem(n,state_for(n,.08),'free');z=np.zeros(s.size)
 before=s.residual(z,z).copy();n.tangent_influences=TangentInfluences(local_geometry=True)
 a,columns,diagnostics=local_rate_columns(s)
 b,other,_=local_rate_columns(s,amplitude=.37)
 assert diagnostics['columns']+diagnostics['engine_mount_columns']==6*n.nn
 np.testing.assert_array_equal(columns,other)
 assert n.iteration_fields is None
 assert np.max(abs((a-b).toarray())/(1+abs(a.toarray())))<2e-12
 n.tangent_influences=None;n.aero_key=None
 for k,j in enumerate(columns):
  for width in [1e-4,3e-5]:
   d=z.copy();d[j]=width
   v=[s.residual(m*d,z) for m in (1,-1,2,-2)]
   expected=(8*(v[0]-v[1])-(v[2]-v[3]))/(12*width)
   error=np.max(abs(a[:,k].toarray().ravel()-expected)/(1+abs(expected)))
   assert error<2e-8,(name,j,width,error)
 np.testing.assert_array_equal(s.residual(z,z),before)

@pytest.mark.parametrize('name',['torsion-joint'])
def test_unsupported_compositions_fall_back(name):
 n=StaticNetwork(model_for(name),4,FlightCondition(),None,[])
 s=DynamicSystem(n,state_for(n,.08));z=np.zeros(s.size)
 before=s.residual(z,z).copy()
 with pytest.raises(LocalRateUnavailable):local_rate_columns(s)
 np.testing.assert_array_equal(s.residual(z,z),before)
 assert n.iteration_fields is None

@pytest.mark.parametrize('stage',['capture','late'])
def test_failed_local_partial_restarts_original_complete_columns(stage,monkeypatch):
 from openswing.linear_dynamics import make_system,linearize
 import openswing.local_rate_tangent as rates
 s,_=make_system(model_for('flexible'),FlightCondition(speed=20,alpha=3,mach=.1),4,structured_base=True)
 def unavailable(*args,**kwargs):raise LocalRateUnavailable('injected local-motion failure')
 with monkeypatch.context() as patch:
  patch.setattr(rates,'local_rate_columns',unavailable)
  expected,em=linearize(s,sparse=True,_output_fields=True)
 if stage=='capture':monkeypatch.setattr(rates.RateFields,'incident_velocity',unavailable)
 else:
  original=rates.RateFlow.velocity;calls=[0]
  def late(*args,**kwargs):
   calls[0]+=1
   if calls[0]==9:unavailable()
   return original(*args,**kwargs)
  monkeypatch.setattr(rates.RateFlow,'velocity',late)
 actual,am=linearize(s,sparse=True,_output_fields=True)
 np.testing.assert_array_equal(actual.toarray(),expected.toarray())
 np.testing.assert_array_equal(am.toarray(),em.toarray())
 assert s.state_derivative_diagnostics['direct_local_motion_columns']==0
 assert 'injected' in s.state_derivative_diagnostics['local_motion_fallback']
 assert s.network.iteration_fields is None and s.network.tangent_influences is None
 assert s._output_field_tangent.active and s._output_field_tangent.matrix is not None

def test_material_damping_and_arbitrary_combined_rate_directions():
 n=StaticNetwork(model_for('wing-body'),4,FlightCondition(speed=30,alpha=7,beta=3,mach=.2,rates=[.03,-.04,.02]),None,[])
 n.damping_times[:]=np.linspace(.001,.08,n.ne)[:,None]
 s=DynamicSystem(n,state_for(n,.08),'fixed');z=np.zeros(s.size)
 a,columns,_=local_rate_columns(s)
 for seed in range(3):
  direction=np.random.default_rng(seed).normal(size=len(columns));d=z.copy();d[columns]=direction
  expected=a@direction
  for width in [1e-4,3e-5]:
   v=[s.residual(m*width*d,z) for m in (1,-1,2,-2)]
   actual=(8*(v[0]-v[1])-(v[2]-v[3]))/(12*width)
   assert np.max(abs(actual-expected)/(1+abs(expected)))<2e-8

def test_incident_field_budget_restores_physical_context(monkeypatch):
 import openswing.local_rate_tangent as rates
 n=StaticNetwork(model_for('flexible'),4,FlightCondition(),None,[])
 s=DynamicSystem(n,state_for(n,.08));z=np.zeros(s.size);before=s.residual(z,z).copy()
 original=rates.RateFields.incident_velocity
 def limited(self,*args,**kwargs):
  self.bytes=64*1024**2
  return original(self,*args,**kwargs)
 monkeypatch.setattr(rates.RateFields,'incident_velocity',limited)
 with pytest.raises(LocalRateUnavailable,match='storage'):local_rate_columns(s)
 assert n.iteration_fields is None
 np.testing.assert_array_equal(s.residual(z,z),before)


@pytest.mark.parametrize('name,frame,extra',[
 ('wing-body','free',{}),('jet-2','mixed',{'powers':{1:50000.}})])
def test_canonical_frame_load_rows_match_full_rate_columns_and_combined_directions(name,frame,extra):
 from openswing.operating import time_load_constraints
 model=model_for(name)
 model.reference[1]=[.7,-.2,.3];model.reference[2]=[.1,.2,-.1]
 model.reference[3]=[.4,-.3,.2]
 targets={'force.y':.3,'moment.x':-.2,'moment.z':.15} if frame=='mixed' else None
 constraints=time_load_constraints(frame,targets)
 n=StaticNetwork(model,4,FlightCondition(speed=30,alpha=7,beta=3,mach=.2,
  rates=[.03,-.04,.02],position_earth=[0,0,30],attitude=[13,-7,21],**extra),None,[],
  operating_constraints=constraints)
 assert n.operating.count==(6 if frame=='free' else 3)
 n.damping_times[:]=np.linspace(.001,.08,n.ne)[:,None]
 s=DynamicSystem(n,state_for(n,.08),frame);z=np.zeros(s.size)
 before=s.residual(z,z).copy();n.tangent_influences=TangentInfluences(local_geometry=True)
 owner=n.tangent_influences
 a,columns,diagnostics=local_rate_columns(s)
 b,other,_=local_rate_columns(s,amplitude=.37)
 assert diagnostics['operating_load_rows']==n.operating.count
 assert diagnostics['columns']+diagnostics['engine_mount_columns']==6*n.nn
 np.testing.assert_array_equal(columns,other)
 assert np.max(abs((a-b).toarray())/(1+abs(a.toarray())))<2e-12
 assert n.iteration_fields is None and n.tangent_influences is owner
 engine_nodes={n.node(*row[2:4]) for row in n.engines}
 excluded={s.velocity_start+part*3*n.nn+3*node+axis
  for node in engine_nodes for part in range(2) for axis in range(3)}
 assert not excluded.intersection(columns)
 assert np.max(abs(a[n.operating_start:n.size].toarray()))>1e-5
 n.tangent_influences=None;n.aero_key=None
 for k,j in enumerate(columns):
  for width in [1e-4,3e-5]:
   direction=z.copy();direction[j]=width
   values=[s.residual(multiplier*direction,z) for multiplier in (1,-1,2,-2)]
   expected=(8*(values[0]-values[1])-(values[2]-values[3]))/(12*width)
   error=np.max(abs(a[:,k].toarray().ravel()-expected)/(1+abs(expected)))
   assert error<2e-8,(name,frame,j,width,error)
 for seed in range(2):
  direction=z.copy();direction[columns]=np.random.default_rng(seed+821).normal(size=len(columns))
  expected=a@direction[columns]
  for width in [1e-4,3e-5]:
   values=[s.residual(multiplier*width*direction,z) for multiplier in (1,-1,2,-2)]
   actual=(8*(values[0]-values[1])-(values[2]-values[3]))/(12*width)
   assert np.max(abs(actual-expected)/(1+abs(expected)))<2e-8
 np.testing.assert_array_equal(s.residual(z,z),before)


@pytest.mark.parametrize('kind',['cross_axis','custom','feedback','owned_capture'])
def test_canonical_extension_preserves_unsupported_contexts(kind):
 from openswing.operating import OperatingConstraint,time_load_constraints
 from openswing.structured_static import IterationFields
 constraints=time_load_constraints('free')
 if kind=='cross_axis':constraints=[OperatingConstraint('acceleration.x','force.y')]
 if kind=='custom':constraints=[OperatingConstraint('acceleration.x','user.force',
  expression='load("force.x")',residual_scale=1.,unit='input F')]
 n=StaticNetwork(model_for('wing-body'),4,FlightCondition(speed=30,mach=.2),None,[],
  operating_constraints=constraints)
 s=DynamicSystem(n,state_for(n,.08),'free');z=np.zeros(s.size)
 before=s.residual(z,z).copy()
 if kind=='feedback':s.feedback=object() # Eligibility must decline before accessing controller internals.
 if kind=='owned_capture':n.iteration_fields=IterationFields()
 owner=n.iteration_fields
 with pytest.raises(LocalRateUnavailable,match='full local-motion stencils'):
  local_rate_columns(s)
 assert n.iteration_fields is owner
 s.feedback=None;n.iteration_fields=None
 np.testing.assert_array_equal(s.residual(z,z),before)


@pytest.mark.parametrize('failure',[RuntimeError,MemoryError,KeyboardInterrupt])
def test_canonical_rate_capture_releases_owner_when_a_group_fails(failure,monkeypatch):
 from openswing.operating import time_load_constraints
 n=StaticNetwork(model_for('wing-body'),4,FlightCondition(speed=30,mach=.2),None,[],
  operating_constraints=time_load_constraints('free'))
 s=DynamicSystem(n,state_for(n,.08),'free');z=np.zeros(s.size)
 before=s.residual(z,z).copy();original=s.residual;calls=[]
 def fail_group(*args,**kwargs):
  calls.append(1)
  if len(calls)==3:raise failure('group failure after positive capture')
  return original(*args,**kwargs)
 with monkeypatch.context() as patch:
  patch.setattr(s,'residual',fail_group)
  with pytest.raises(failure,match='group failure'):local_rate_columns(s)
 assert n.iteration_fields is None and n.aero_key is None
 np.testing.assert_array_equal(s.residual(z,z),before)


def test_free_frame_optimization_preserves_full_matrices_and_output_field_recovery(monkeypatch):
 from openswing.linear_dynamics import linearize,output_perturbation
 from test_output_fields import system_for,difference
 import openswing.local_rate_tangent as rates
 s=system_for('flexible','free');n=s.network
 assert n.operating.count==6
 s.base_report()
 def unavailable(*args,**kwargs):raise LocalRateUnavailable('full-stencil reference')
 with monkeypatch.context() as patch:
  patch.setattr(rates,'local_rate_columns',unavailable)
  count=n.nfev;expected,mass=linearize(s,sparse=True,_output_fields=True);reference_calls=n.nfev-count
 count=n.nfev;actual,am=linearize(s,sparse=True,_output_fields=True);actual_calls=n.nfev-count
 assert np.max(abs((actual-expected).toarray())/(1+abs(expected.toarray())))<2e-8
 np.testing.assert_array_equal(am.toarray(),mass.toarray())
 assert actual_calls<reference_calls
 assert s.state_derivative_diagnostics['direct_local_motion_columns']==6*n.nn
 fields=s._output_field_tangent
 assert fields.active and fields.matrix is not None and not fields.pending
 assert fields.matrix[:,s.velocity_start:s.frame_start].nnz==0
 rng=np.random.default_rng(1901);direction=np.zeros(s.size,dtype=complex)
 direction[s.velocity_start:s.frame_start]=.002*(rng.normal(size=6*n.nn)+1j*rng.normal(size=6*n.nn))
 rate=1.3j*direction
 full=output_perturbation(s,direction,rate)
 shared=output_perturbation(s,direction,rate,_field_tangent=fields)
 assert difference(shared,full)<2e-8
 assert fields.active and n.iteration_fields is None and n.tangent_influences is None
