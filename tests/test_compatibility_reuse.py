import numpy as np
import pytest
from openswing.aero import FlightCondition
from openswing.network import StaticNetwork
from openswing.linear_dynamics import DynamicSystem
from openswing.structural_outputs import compatibility_columns,StructuralOutputUnavailable
from openswing.tangent_influences import TangentInfluences
from test_direct_circulation import model_for,state_for

@pytest.mark.parametrize('name',['flexible','wing-body','torsion-joint','stepped-body','jet-2'])
def test_compatibility_reuses_complete_section_jacobian(name):
 n=StaticNetwork(model_for(name),4,FlightCondition(speed=30,alpha=7,mach=.2),None,[])
 x=state_for(n,.08);x[:6*n.nn].reshape(-1,6)[:,3:]+=[.5,-.2,.3]
 s=DynamicSystem(n,x);zero=np.zeros(s.size);before=s.residual(zero,zero).copy()
 # Exercise all compliance couplings, including extension/bending/torsion.
 n.S+=np.full_like(n.S,1e-8)
 n.tangent_influences=TangentInfluences(local_geometry=True)
 a=compatibility_columns(s);tangent=s._structural_output_tangent
 for j in range(n.gamma_start):
  for width in [1e-4,3e-5]:
   d=zero.copy();d[j]=width
   v=[s.residual(m*d,zero)[:6*n.ne] for m in (1,-1,2,-2)]
   expected=(8*(v[0]-v[1])-(v[2]-v[3]))/(12*width)
   assert np.max(abs(a[:,j].toarray().ravel()-expected)/(1+abs(expected)))<2e-8,(name,j,width)
 assert compatibility_columns(s).shape==(6*n.ne,n.size)
 assert s._structural_output_tangent is tangent
 assert not tangent.matrix.data.flags.writeable
 n.S-=np.full_like(n.S,1e-8)
 # Addition/subtraction can round compliance; compare the unchanged geometry.
 np.testing.assert_allclose(s.residual(zero,zero),before,atol=1e-13,rtol=1e-13)


def test_shared_section_matrix_uses_current_compliance_and_invalidates_loaded_state():
 n=StaticNetwork(model_for('flexible'),4,FlightCondition(),None,[])
 s=DynamicSystem(n,state_for(n,.08));a=compatibility_columns(s);first=s._structural_output_tangent
 n.S*=1.03;b=compatibility_columns(s)
 assert s._structural_output_tangent is first
 assert np.max(abs((a-b).data))>1e-10
 s.base[6*n.nn]+=1e-3
 compatibility_columns(s)
 assert s._structural_output_tangent is not first


def test_unavailable_section_composition_preserves_previous_complete_rows(monkeypatch):
 from openswing.linear_dynamics import make_system,linearize
 import openswing.structural_outputs as outputs
 s,_=make_system(model_for('flexible'),FlightCondition(speed=20,alpha=3,mach=.1),4,structured_base=True)
 actual,m=linearize(s,sparse=True)
 assert s.state_derivative_diagnostics['compatibility_rows_reused']==6*s.network.ne
 def fail(*args):raise StructuralOutputUnavailable('injected section storage budget')
 monkeypatch.setattr(outputs,'compatibility_columns',fail)
 fallback,fm=linearize(s,sparse=True)
 assert 'storage' in s.state_derivative_diagnostics['compatibility_fallback']
 assert np.max(abs((actual-fallback).toarray())/(1+abs(actual.toarray())))<2e-8
 np.testing.assert_array_equal(m.toarray(),fm.toarray())
 assert s.network.iteration_fields is None and s.network.tangent_influences is None
