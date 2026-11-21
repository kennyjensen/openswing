import numpy as np
import pytest
from openswing.geometry_tangent import geometry_columns,GeometryDerivativeUnavailable
from openswing.support_outputs import SupportTangent
from openswing.tangent_influences import TangentInfluences
from test_support_outputs import system_for,high_precision_support

@pytest.mark.parametrize('name',['dae','tension','compression','wire_taut','wire_slack','zero_stiffness'])
def test_same_strut_blocks_supply_nodal_and_output_matrices(name):
 s=system_for(name);n=s.network;t=SupportTangent(s)
 v=np.random.default_rng(17).normal(size=s.size)+1j*np.random.default_rng(19).normal(size=s.size)
 # Remove ground reactions so the independent 80-digit law isolates struts.
 v[6*n.nn:]=0
 for c in n.constraints:
  if c['b'] is None:v[6*c['a']:6*c['a']+6]=0
 expected=high_precision_support(s,v)
 local=t.nodal_struts@v[:6*n.nn]
 force=local[6*n.ne:6*n.ne+3*n.nn].reshape(n.nn,3)*n.F
 moment=local[6*n.ne+3*n.nn:6*(n.ne+n.nn)].reshape(n.nn,3)*n.F*n.L
 from openswing.struts import strut_load
 original=np.zeros((n.nn,3))
 for row in n.struts:
  i=n.node(*row[:2]);p=s.r0[i]+s.Q0[i]@(row[2:5]-n.rj[i])
  original[i]+=strut_load(row,p,tension_only=n.tension_only)['force']
 position=s.L*v[:6*n.nn].reshape(n.nn,6)[:,:3]
 total=np.r_[force.sum(axis=0),(moment+np.cross(s.r0-n.model.reference[1],force)+np.cross(position,original)).sum(axis=0)]
 assert np.max(abs(total-expected)/(1+abs(expected)))<2e-11
 assert not t.nodal_struts.data.flags.writeable

@pytest.mark.parametrize('name',['dae','tension','wire_taut','wire_slack'])
def test_complete_geometry_reuses_strut_blocks_without_subtraction(name):
 s=system_for(name);n=s.network;z=np.zeros(s.size);t=SupportTangent(s)
 baseline=s.residual(z,z).copy();n.tangent_influences=TangentInfluences(local_geometry=True)
 args=(n,lambda v:s.residual(v,z),lambda v:s.unpack(v,z)[0].x,np.r_[np.maximum(1,abs(s.base)),np.ones(s.size-n.size)])
 a,report=geometry_columns(*args,_direct_geometry=True,_rotation_chart='spatial',_strut_tangent=t)
 b,_=geometry_columns(*args,_direct_geometry=True,_rotation_chart='spatial')
 assert np.max(abs((a-b).toarray())/(1+abs(a.toarray())))<2e-8
 assert report['retained_strut_columns']==np.count_nonzero(np.diff(t.nodal_struts.indptr))
 n.tangent_influences=None;n.aero_key=None
 assert n.iteration_fields is None
 np.testing.assert_array_equal(s.residual(z,z),baseline)


def test_stale_or_wrong_owner_strut_context_restores_full_physics():
 s=system_for('tension');n=s.network;z=np.zeros(s.size);t=SupportTangent(s);before=s.residual(z,z).copy()
 for tangent in [SupportTangent(system_for('tension')),t]:
  if tangent is t:n.struts[0][9]*=1.01
  with pytest.raises(GeometryDerivativeUnavailable,match='match'):
   geometry_columns(n,lambda v:s.residual(v,z),lambda v:s.unpack(v,z)[0].x,np.ones(s.size),
    _direct_geometry=True,_rotation_chart='spatial',_strut_tangent=tangent)
  assert n.iteration_fields is None
  if tangent is t:n.struts[0][9]/=1.01
 np.testing.assert_allclose(s.residual(z,z),before,atol=1e-13,rtol=1e-13)
