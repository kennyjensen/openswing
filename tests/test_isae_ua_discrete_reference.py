"""Independent polynomial, kinematic and nonlinear Jacobian identities."""
import math
from pathlib import Path
import sys
import numpy as np
import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from isae_ua_discrete_reference import derivative_weights,kinematics,circulation_residual_jacobian,discrete_trajectory
from isae_ua_wing_nonlinear import StraightWing


@pytest.mark.parametrize('times',([0.,.1,.2],[0.,.03,.16],[2.,2.00001,2.00002125]))
def test_backward_weights_differentiate_quadratics_on_nonuniform_times(times):
    times=np.array(times);k=derivative_weights(times,2);x=times[::-1]-times[-1]
    np.testing.assert_allclose([k@np.ones(3),k@x,k@(x*x)],[0.,1.,0.],rtol=0,atol=2e-11)
    h,hp=times[2]-times[1],times[1]-times[0]
    expected=np.array([1/h+1/(h+hp),-1/h-1/hp,h/(hp*(h+hp))])
    np.testing.assert_allclose(k,expected,rtol=1e-14,atol=1e-14)


def test_constant_velocity_motion_is_exact_on_a_nonuniform_grid():
    times=np.array([0.,.001,.003,.008,.02,.05])
    velocity,position=kinematics(times,np.zeros(len(times)),position0=.25,velocity0=2.)
    np.testing.assert_allclose(velocity,2.,atol=1e-14,rtol=0)
    np.testing.assert_allclose(position,.25+2*times,atol=1e-14,rtol=0)


def test_coupled_jacobian_matches_complex_step_at_finite_bound_induced_speed():
    wing=StraightWing(8);gamma=np.linspace(-2.,3.,8);previous=.95*gamma;older=.9*gamma
    weights=derivative_weights([0.,.03,.07],2)
    _,jac=circulation_residual_jacobian(wing,gamma,previous,older,weights,4.2)
    numeric=np.empty_like(jac)
    for j in range(8):
        perturbed=gamma.astype(complex);perturbed[j]+=1e-25j
        numeric[:,j]=circulation_residual_jacobian(wing,perturbed,previous,older,weights,4.2)[0].imag/1e-25
    np.testing.assert_allclose(jac,numeric,rtol=1e-13,atol=1e-12)


def test_discrete_small_signal_trajectory_matches_direct_linear_system():
    wing=StraightWing(8);times=np.linspace(0,math.pi/9.5,81);height=1e-5
    velocity=-height*19*np.sin(19*times);acceleration=-height*19**2*np.cos(19*times)
    actual=discrete_trajectory(wing,times,velocity,acceleration)
    expected=np.zeros((len(times),8));matrix=np.pi*10/2*wing.C
    for i in range(1,len(times)):
        k0,_,k2=derivative_weights(times,i)
        rhs=k0*expected[i-1]-k2*(expected[max(0,i-2)]-expected[i-1])-np.pi*10/2*velocity[i]
        expected[i]=np.linalg.solve(k0*np.eye(8)+matrix,rhs)
    assert np.max(abs(actual['circulation']-expected))/np.max(abs(expected))<1e-8
    assert actual['maximum_equation_residual']<1e-11
