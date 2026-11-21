"""Nonlinear initial consistency against finite-rotation constrained mechanics."""
import numpy as np
import pytest
from openswing.aero import AnalysisError
from openswing.nonlinear_initial import consistent_initial


@pytest.mark.parametrize('unit,scaled',[(1.,False),(.001,False),(1.,True)])
def test_pendulum_preserves_position_velocity_and_recovers_centripetal_reaction(unit,scaled):
    length,mass,g,angle,omega=2.,3.,9.81,1.1,1.3
    initial=np.array([length*np.sin(angle),-length*np.cos(angle),length*omega*np.cos(angle),length*omega*np.sin(angle),0.])
    columns=np.array([.2,3.,.1,4.,.01]) if scaled else np.ones(5)
    rows=np.array([1e-3,3.,1e3,.03,2.]) if scaled else np.ones(5)
    def residual(x,d,t):
        x=x*columns;d=d*columns/unit
        return rows*np.array([d[0]-x[2],d[1]-x[3],mass*d[2]+x[4]*x[0],mass*d[3]+x[4]*x[1]+mass*g,x[0]**2+x[1]**2-length**2])
    guess=np.r_[initial[2:4],0.,0.,0.]*unit/columns
    actual,rate,report=consistent_initial(residual,initial/columns,[0,1,2,3],guess,time_scale=unit)
    multiplier=mass*(omega**2+g*np.cos(angle)/length)
    expected=np.r_[initial[2:4],-multiplier*initial[0]/mass,-multiplier*initial[1]/mass-g]
    np.testing.assert_array_equal(actual[:4],(initial/columns)[:4])
    np.testing.assert_allclose((actual*columns)[:4],initial[:4],atol=0,rtol=3e-16)
    assert actual[4]*columns[4]==pytest.approx(multiplier,rel=2e-6)
    np.testing.assert_allclose((rate*columns/unit)[:4],expected,rtol=2e-6,atol=1e-7)
    assert report['prescribed_coordinate_error']==0
    assert len(report['refinements'])==2
    assert max(r['original_residual'] for r in report['refinements'])<1e-8


@pytest.mark.parametrize('violation',['position','velocity'])
def test_incompatible_pendulum_data_is_rejected_without_changing_the_profile(violation):
    x=np.array([0.,-1.,1.,0.,0.]);x[1 if violation=='position' else 3]+=.1;before=x.copy()
    def residual(x,d,t):return np.array([d[0]-x[2],d[1]-x[3],d[2]+x[4]*x[0],d[3]+x[4]*x[1]+9.81,x[0]**2+x[1]**2-1])
    with pytest.raises(AnalysisError,match='constraints|uniquely'):
        consistent_initial(residual,x,[0,1,2,3],np.r_[x[2:4],0.,0.,0.])
    np.testing.assert_array_equal(x,before)


def test_unresolved_physical_rate_is_rejected_even_with_zero_original_residual():
    with pytest.raises(AnalysisError,match='not uniquely resolved'):
        consistent_initial(lambda x,d,t:np.array([d[0]-x[1],0.]),np.zeros(2),[0],np.zeros(2))


def test_centered_array_cannot_average_opposite_acceleration_constraints():
    # x=t*abs(t) has identical position/velocity but opposite side accelerations.
    def residual(x,d,t):return np.array([d[0]-x[1],d[1]-x[2],x[0]-t*abs(t)])
    with pytest.raises(AnalysisError,match='one-sided|constraints|spacing'):
        consistent_initial(residual,np.zeros(3),[0,1],np.zeros(3))


def test_nonfinite_one_sided_path_cannot_pass_through_a_nan_comparison():
    def residual(x,d,t):return np.array([np.nan if .001<t<.003 else d[0]-1])
    with pytest.raises(AnalysisError,match='Nonfinite'):
        consistent_initial(residual,np.zeros(1),[0],np.zeros(1))
