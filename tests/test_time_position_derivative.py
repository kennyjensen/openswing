"""BDF nodal velocity must preserve motion below a large jig position's ULP."""
from types import SimpleNamespace
import numpy as np
import pytest
from openswing.time_integration import bdf_coefficients, local_position_derivative


def state(network, displacement, *, rotation=0., load=0.):
    kin=np.zeros((network.nn,6));kin[:,:3]=displacement/network.L;kin[:,3:]=rotation
    return SimpleNamespace(x=np.r_[kin.ravel(),[load]*12],r=network.rj+displacement)


@pytest.mark.parametrize('length',[1.,1e6])
@pytest.mark.parametrize('previous_step',[None,2e-4,7e-5])
def test_analytic_velocity_survives_absolute_coordinate_rounding(length,previous_step):
    h=1e-4
    n=SimpleNamespace(nn=2,L=length,rj=np.array([[1e12,-2e12,3e12],[-4e12,5e12,-6e12]]))
    offset=np.array([[1e-6,-2e-6,3e-6],[-2e-6,4e-6,-1e-6]])
    velocity=np.array([[.001,.002,-.001],[-.002,.003,.004]])
    acceleration=np.zeros((2,3)) if previous_step is None else np.array([[.03,-.04,.05],[-.02,.06,.07]])
    def sample(t):return state(n,offset+t*velocity+.5*t*t*acceleration,rotation=t,load=t*100)
    current,previous=sample(0),sample(-h)
    older=None if previous_step is None else sample(-h-previous_step)
    weights=bdf_coefficients(h,previous_step)
    # Reconstructed absolute positions cannot distinguish these samples.
    np.testing.assert_array_equal(current.r,previous.r)
    actual=local_position_derivative(n,current,previous,older,weights)
    np.testing.assert_allclose(actual,velocity,rtol=0,atol=2e-17)
    absolute=weights[0]*(current.r-previous.r)
    if older is not None:absolute+=weights[2]*(older.r-previous.r)
    assert np.max(abs(absolute-velocity))>.001


def test_stationary_displacement_is_exact_even_when_rotations_and_loads_change():
    n=SimpleNamespace(nn=2,L=7.,rj=np.zeros((2,3)))
    displacement=np.array([[.1,.3,-.2],[.9,-.4,.2]])
    samples=[state(n,displacement,rotation=a,load=100*a) for a in (0.,.1,.3)]
    actual=local_position_derivative(n,samples[2],samples[1],samples[0],bdf_coefficients(.03,.02))
    np.testing.assert_array_equal(actual,np.zeros((2,3)))


def test_equivalence_with_physical_position_derivative_when_well_resolved():
    n=SimpleNamespace(nn=2,L=2.,rj=np.array([[0.,2.,0.],[.1,-3.,.2]]))
    samples=[state(n,np.array([[t,.3*t*t,-t*t],[2*t,-.5*t*t,1.5*t]])) for t in (.2,.27,.4)]
    current,previous,older=samples[2],samples[1],samples[0]
    weights=bdf_coefficients(.13,.07)
    physical=weights[0]*(current.r-previous.r)+weights[2]*(older.r-previous.r)
    actual=local_position_derivative(n,current,previous,older,weights)
    np.testing.assert_allclose(actual,physical,rtol=0,atol=1e-14)
