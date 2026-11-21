"""Small independent coordinate/reference checks; no aircraft or cold solve."""
from pathlib import Path
from types import SimpleNamespace
import copy
import numpy as np
import pytest
from openswing.aero import AnalysisError, FlightCondition
from openswing.asw import parse_asw
from openswing.forcing import TimeForcing
from openswing.inertia import Motion
from openswing.operating import TimeHistoryConstraint, time_operating_constraints
from openswing.position_history_lift import PositionHistoryLift, position_history_lift
from independent_rotation import Units, rotation_jet, vee

BASE=Path(__file__).resolve().parents[1]


def actual_forcing():
    target=dict(variable='power.1',quantity='position_earth.x',target=0.)
    model=parse_asw((BASE/'inputs/body.asw').read_text())
    forcing=TimeForcing((BASE/'inputs/position.tbl').read_text(), model,
        FlightCondition(speed=10.), Motion(), 1., 'free', actuator_constraints=[target])
    rows=time_operating_constraints('free',None,[target])
    lift=PositionHistoryLift(rows,forcing,length_scale=2.,velocity_scale=10.)
    return forcing,lift


def analytic_state(t):
    R,Rd,Rdd=rotation_jet(t,Units())
    K=R.T@Rd;omega=vee(K);alpha=vee(R.T@Rdd-K@K)
    p=np.array([-10*t+t*t/5-t*t*t/15,1+2*t+.35*t*t,-.5-.3*t-.2*t*t])
    v=np.array([-10+.4*t-.2*t*t,2+.7*t,-.3-.4*t])
    a=np.array([.4-.4*t,.7,-.4])
    state=SimpleNamespace(time=t,position=p,U=R.T@v,orientation=R,position_history=None)
    ra=np.array([.41,.12,-.23])
    # Independent twice-differentiated material reference-point position:
    # acceleration(P+R*r_a)=a+R''r_a, expressed in body coordinates.
    motion=Motion(omega,R.T@(a+Rdd@ra),alpha)
    return state,motion,ra


def test_partial_selection_uses_full_earth_vectors_and_exact_reference_transport():
    forcing,lift=actual_forcing();h=.02
    previous,_,_=analytic_state(.2);state,motion,ra=analytic_state(.2+h)
    lift.bind_initial(previous,forcing,1e-8)
    saved=previous.position_history
    velocity,position=lift.residuals(state,previous,None,np.array([1.,-1.,0.])/h,motion,ra,forcing,'right')
    # Free Earth velocity components are affine, so their BDF1 derivatives
    # equal the true acceleration. The selected defect is identically zero.
    np.testing.assert_allclose(velocity,[0.,0.,0.],atol=2e-11,rtol=0)
    # The independent quadratic free positions incur the usual BDF1 defect.
    np.testing.assert_allclose(position,[0.,-.5*.7*h,+.5*.4*h],atol=2e-12,rtol=0)
    assert previous.position_history is saved
    assert saved.time==.2 and saved.side=='right'
    np.testing.assert_allclose(saved.value,[-10*.2+.2**2/5-.2**3/15,0.,0.],atol=2e-14,rtol=0)
    assert abs(position[1])>1e-3 and abs(position[2])>1e-3
    wrong,_=lift.residuals(state,previous,None,np.array([1.,-1.,0.])/h,motion,np.zeros(3),forcing,'right')
    assert np.max(abs(wrong))>1e-4


def test_empty_selection_leaves_default_body_coordinate_policy_inactive():
    rows=time_operating_constraints('free',None,None)
    assert position_history_lift(rows,None,length_scale=2.,velocity_scale=10.) is None


def test_constant_selected_target_has_zero_jets_and_retains_unselected_state():
    rows=[TimeHistoryConstraint('power.1','position_earth.y',.2)]
    lift=PositionHistoryLift(rows,None,length_scale=2.,velocity_scale=10.)
    state=SimpleNamespace(time=.4,position=np.array([5.,.2,1.]),U=np.array([-10.,0.,0.]),orientation=np.eye(3),position_history=None)
    lift.bind_initial(state,None,1e-8)
    assert state.position_history.value==(0.,.2,0.)
    assert state.position_history.rate==state.position_history.acceleration==(0.,0.,0.)
    E,W=lift.coordinates(state,state.position_history)
    np.testing.assert_array_equal(E,[5.,0.,1.]);np.testing.assert_array_equal(W,[-10.,0.,0.])


def test_missing_or_replacement_history_is_rejected_without_reinterpreting_old_sample():
    forcing,lift=actual_forcing();previous,_,_=analytic_state(.2)
    with pytest.raises(AnalysisError,match='original accepted time/side'):
        lift.history(previous,forcing)
    lift.bind_initial(previous,forcing,1e-8);saved=previous.position_history
    replacement=copy.copy(forcing);replacement.source+='\n'
    with pytest.raises(AnalysisError,match='cannot be reinterpreted'):
        lift.history(previous,replacement)
    assert previous.position_history is saved


def test_incompatible_zero_cutoff_rejects_while_retaining_left_sample():
    forcing,lift=actual_forcing();state,_,_=analytic_state(1.)
    state.position_history=lift.sample(1.,forcing,'left');saved=state.position_history
    with pytest.raises(AnalysisError,match='retained physical origin position or Earth velocity'):
        lift.history(state,forcing)
    assert state.position_history is saved and saved.side=='left'
