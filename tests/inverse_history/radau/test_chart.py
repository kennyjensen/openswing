"""Independent noncommuting kinematics, including free axes and offset r_a."""
from pathlib import Path
import sys
import numpy as np
import pytest
from scipy.spatial.transform import Rotation
root=Path(__file__).parent
sys.path.insert(0,str(root.parent/'lift'/'focused'))
from radau_fixture import prepared
from independent_rotation import rotation_jet,vee
from openswing.position_history_radau import PositionHistoryRadauChart
from openswing.nonlinear_initial import InitialSystem


def trajectory(t):
 R,Rd,Rdd=rotation_jet(t);K=R.T@Rd
 p=np.array([-10*t+.2*t*t-t**3/15,1+2*t+.35*t*t,-.5-.3*t-.2*t*t])
 v=np.array([-10+.4*t-.2*t*t,2+.7*t,-.3-.4*t])
 a=np.array([.4-.4*t,.7,-.4]);omega=vee(K);alpha=vee(R.T@Rdd-K@K)
 return R,Rd,Rdd,p,v,a,omega,alpha


@pytest.mark.parametrize('t',[.13,.47,.83])
def test_independent_noncommuting_trajectory_and_reference_transport(t):
 model,system,seed,_,_=prepared();n=system.network
 ra=np.array([.41,.12,-.23]);model.reference[2]=ra
 R0,_,_,p0,v0,_,w0,_=trajectory(0.)
 seed.position=p0;seed.orientation=R0;seed.U=R0.T@v0;seed.Omega=w0
 chart=PositionHistoryRadauChart(system,seed,'free');original=InitialSystem(system,seed,'free',apply_forcing=True)
 R,Rd,Rdd,p,v,a,omega,alpha=trajectory(t)
 z=np.zeros(chart.size);rate=np.zeros(chart.size);j=chart.frame_start
 # Only x is prescribed. Free y/z retain their independent quadratic path.
 z[j:j+3]=np.array([0.,v[1]-v0[1],v[2]-v0[2]])/chart.V
 z[j+6:j+9]=np.array([0.,p[1]-p0[1],p[2]-p0[2]])/chart.L
 rate[j:j+3]=[0.,a[1]/chart.V,a[2]/chart.V]
 rate[j+6:j+9]=[0.,v[1]/chart.L,v[2]/chart.L]
 z[j+3:j+6]=(omega-w0)/chart.W;rate[j+3:j+6]=alpha/chart.W
 def log_at(time):return Rotation.from_matrix(R0.T@trajectory(time)[0]).as_rotvec()
 z[j+9:j+12]=log_at(t)
 h=1e-4
 rate[j+9:j+12]=(-log_at(t+2*h)+8*log_at(t+h)-8*log_at(t-h)+log_at(t-2*h))/(12*h)
 # Material reference acceleration is the twice-differentiated P+R*r_a.
 reference_acceleration=R.T@(a+Rdd@ra)
 for k,row in enumerate(n.operating.constraints):
  if row.variable.startswith('acceleration.'):
   value=reference_acceleration['xyz'.index(row.variable[-1])]
  elif row.variable.startswith('angular_acceleration.'):
   value=alpha['xyz'.index(row.variable[-1])]
  else:value=.7
  z[n.operating_start+k]=value/n.operating.scale[row.variable]-chart.base[n.operating_start+k]
 residual,state,options=chart.residual(z,rate,t,detail=True)
 np.testing.assert_allclose(state.position,p,atol=2e-14,rtol=0)
 np.testing.assert_allclose(state.U,R.T@v,atol=2e-13,rtol=0)
 np.testing.assert_allclose(state.orientation,R,atol=2e-14,rtol=0)
 np.testing.assert_allclose(residual[j:j+12],0,atol=2e-10,rtol=0)
 assert np.max(abs(p[1:]-p0[1:]))>.01
 # Independent physical chart and physical body velocity derivative.
 body=z.copy();dr=rate.copy()
 body[j:j+3]=(R.T@v-seed.U)/chart.V;body[j+6:j+9]=(p-p0)/chart.L
 dr[j:j+3]=(R.T@a-np.cross(omega,R.T@v))/chart.V;dr[j+6:j+9]=v/chart.L
 physical=original.residual(body,dr,t)
 np.testing.assert_allclose(residual,physical,atol=2e-10,rtol=0)
 # The reference shift must matter: omitting it produces a clear error.
 assert np.linalg.norm(reference_acceleration-R.T@a)>.02
