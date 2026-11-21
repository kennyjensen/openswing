"""Shared physical moving-field derivatives in full Newton corrections."""
import numpy as np
import pytest
from openswing.aero import FlightCondition
from openswing.network import StaticNetwork
from openswing.operating import time_load_constraints
from openswing.geometry_tangent import geometry_columns
from openswing.tangent_influences import TangentInfluences
from test_direct_circulation import model_for,state_for

CASES=[('flexible',{'circulation_modes':{1:3}},.6),
 ('wing-body',{'ground_effect':1},.6),('wing-body',{'ground_effect':-1},.6),
 ('stepped-wing-body',{},.6),('stepped-wing-body',{'freeze_influences':True},.6),
 ('torsion-joint',{},.6),('jet-2',{'powers':{1:50000.}},.6),
 ('wing-body',{},0.),('wing-body',{},1.)]

@pytest.mark.parametrize('example,extra,factor',CASES)
def test_newton_columns_match_refined_complete_physical_residual(example,extra,factor):
 model=model_for(example);model.reference[1]=[.7,-.2,.3];model.reference[2]=[.1,.2,-.1]
 n=StaticNetwork(model,4,FlightCondition(speed=30,alpha=7,beta=3,mach=.2,rates=[.03,-.04,.02],
   position_earth=[0,0,30],attitude=[13,-7,21],**extra),None,[],operating_constraints=time_load_constraints('free'))
 state=state_for(n,.3);baseline=n.residual(state,factor).copy();n._frequency_local_geometry=True
 actual=n.jacobian(state,factor,_sparse=True)
 diagnostic=n.geometry_derivative_diagnostics
 assert diagnostic['difference_order']==1 and diagnostic['difference_step']==1e-6
 assert diagnostic['direct_geometry_columns']==6*n.nn,diagnostic
 assert diagnostic['field_evaluations']==2 and diagnostic['geometry_preparations']==2
 for width in [1e-5,3e-6]:
  for j in range(6*n.nn):
   h=width*max(1.,abs(state[j]));d=np.zeros(n.size);d[j]=h
   p,m,pp,mm=[n.residual(state+a*d,factor) for a in [1,-1,2,-2]]
   expected=(8*(p-m)-(pp-mm))/(12*h)
   error=np.max(abs(actual[:,j].toarray().ravel()-expected)/(1+abs(expected)))
   assert error<2e-5,(example,factor,width,j,error)
 np.testing.assert_array_equal(n.residual(state,factor),baseline)
 assert n.iteration_fields is None and n.tangent_influences is None

@pytest.mark.parametrize('failure',['constructor','late-column'])
def test_unavailable_composition_retains_original_complete_newton_fallback(monkeypatch,failure):
 import openswing.geometry_field_partials as partials
 import openswing.geometry_tangent as geometry
 from openswing.geometry_partials import GeometryPartialsUnavailable
 n=StaticNetwork(model_for('flexible'),4,FlightCondition(speed=30,alpha=7,beta=3,mach=.2),None,[])
 state=state_for(n,.3);n._frequency_local_geometry=True
 original=geometry.geometry_columns
 def stencil(*args,**kwargs):
  kwargs['_direct_geometry']=False
  return original(*args,**kwargs)
 with monkeypatch.context() as patch:
  patch.setattr(geometry,'geometry_columns',stencil)
  stencil_matrix=n.jacobian(state,.6,_sparse=True)
 n._frequency_local_geometry=False
 full=n.jacobian(state,.6,_sparse=True)
 n._frequency_local_geometry=True
 if failure=='constructor':
  def unavailable(*args,**kwargs):raise GeometryPartialsUnavailable('unsupported Newton composition')
  monkeypatch.setattr(partials,'GeometryFieldPartials',unavailable)
 else:
  method=partials.GeometryFieldPartials.columns
  def interrupted(self,columns):
   if min(columns)>=16:raise GeometryPartialsUnavailable('unsupported Newton composition')
   return method(self,columns)
  monkeypatch.setattr(partials.GeometryFieldPartials,'columns',interrupted)
 actual=n.jacobian(state,.6,_sparse=True)
 np.testing.assert_array_equal(actual.toarray(),(stencil_matrix if failure=='constructor' else full).toarray())
 assert 'unsupported Newton composition' in str(n.geometry_derivative_diagnostics)
 assert n.iteration_fields is None and n.tangent_influences is None


def test_refinement_of_local_partial_keeps_exact_shared_field_columns():
 n=StaticNetwork(model_for('wing-body'),4,FlightCondition(mach=.2,alpha=7,beta=3),None,[])
 state=state_for(n,.3);scales=np.maximum(1.,abs(state));n.tangent_influences=TangentInfluences(local_geometry=True)
 values=[];errors=[]
 for h in [1e-6,3e-7]:
  columns,diagnostic=geometry_columns(n,lambda d:n.residual(state+d,.6),lambda d:state+d,scales,
    step=h,factor=.6,difference_order=1,_direct_vortex=True,_direct_volume=True,_direct_geometry=True)
  assert diagnostic['direct_geometry_columns']==6*n.nn
  values.append(columns.toarray())
 n.tangent_influences=None;n.aero_key=None
 np.testing.assert_array_equal(values[0][n.gamma_start:n.operating_start],values[1][n.gamma_start:n.operating_start])
 expected=[]
 for j in range(6*n.nn):
  h=3e-6*scales[j];d=np.zeros(n.size);d[j]=h
  p,m,pp,mm=[n.residual(state+a*d,.6) for a in [1,-1,2,-2]]
  expected.append((8*(p-m)-(pp-mm))/(12*h))
 expected=np.array(expected).T
 errors=[np.max(abs(v-expected)/(1+abs(expected))) for v in values]
 assert errors[0]<2e-5 and errors[1]<max(.5*errors[0],2e-9),errors
