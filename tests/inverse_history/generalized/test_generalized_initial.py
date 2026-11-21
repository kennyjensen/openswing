"""Independent small-DAE acceptance cases for selected initial values/rates."""
import numpy as np
import pytest
from openswing.aero import AnalysisError
from openswing.nonlinear_initial import consistent_initial


@pytest.mark.parametrize('seconds_per_input_time,acceleration,seconds',[(1.,0.,0.),(.001,.6,.2),(7.,-.3,.4)])
def test_free_spring_displacement_with_fixed_initial_acceleration(seconds_per_input_time,acceleration,seconds):
    # q'=v, m v'=F-kq, F(s)=6+5s+7s². Hold v=.4 and v'=a,
    # solve q=(F-ma)/k. Nonzero v''=(F'-kv)/m requires free
    # higher coefficients even when v'(0) is prescribed to zero.
    unit=seconds_per_input_time;mass,stiffness,velocity=2.,3.,.4
    force=lambda s:6+5*s+7*s*s
    def residual(x,d,t):
        d=d/unit;s=t*unit
        return np.array([d[0]-x[1],mass*d[1]+stiffness*x[0]-x[2],x[2]-force(s)])
    initial=np.array([-.8,velocity,0.]);guess=np.array([0.,99.,0.]);before=initial.copy();before_rate=guess.copy()
    state,rate,report=consistent_initial(residual,initial,[0,1],guess,time=seconds/unit,time_scale=unit,
        fixed_state_indices=[1],fixed_rates={1:acceleration*unit})
    np.testing.assert_allclose(state,[(force(seconds)-mass*acceleration)/stiffness,velocity,force(seconds)],rtol=0,atol=2e-7)
    np.testing.assert_allclose(rate[:2]/unit,[velocity,acceleration],rtol=0,atol=2e-7)
    assert rate[2]/unit==pytest.approx(5+14*seconds,abs=2e-6)
    assert rate[1]==acceleration*unit
    np.testing.assert_array_equal(initial,before);np.testing.assert_array_equal(guess,before_rate)
    assert report['fixed_state_indices']==[1]
    assert report['free_state_indices']==[0,2]
    assert report['free_dynamic_rate_indices']==[0]
    assert report['prescribed_coordinate_error']==report['prescribed_rate_error']==0
    assert len(report['refinements'])==2
    for refinement in report['refinements']:
        assert refinement['required_nullspace_defect']<=1e-6
        assert refinement['original_residual']<=1e-8
        assert refinement['one_sided_derivative_defect']<=1e-6


def test_wide_zero_residual_system_rejects_unresolved_initial_coordinate():
    # At the guess all three residual-array rows are zero. The 3x4 Jacobian
    # has full row rank yet x(0) is arbitrary: a thin SVD omits that nullvector.
    with pytest.raises(AnalysisError,match='not uniquely resolved'):
        consistent_initial(lambda x,d,t:np.array([d[0]-1.]),np.array([8.]),[0],np.ones(1),fixed_state_indices=[])


def test_free_physical_rate_still_needs_unique_certificate():
    # Fixing v's initial rate does not resolve the missing q-rate/actuator row.
    with pytest.raises(AnalysisError,match='not uniquely resolved'):
        consistent_initial(lambda x,d,t:np.array([d[0]-x[2],d[1],0.]),np.zeros(3),[0,1],np.zeros(3),fixed_rates={1:0.})


def test_conflicting_fixed_rate_is_not_changed_to_fit_residual():
    with pytest.raises(AnalysisError,match='constraints'):
        consistent_initial(lambda x,d,t:np.array([d[0]-1.]),np.zeros(1),[0],np.zeros(1),fixed_rates={0:2.})


def test_all_required_values_fixed_allows_only_auxiliary_nonuniqueness():
    # Every required state/rate is prescribed; a zero equation imposes no
    # conditions on auxiliary Taylor coefficients. Their rank is correctly 0.
    state,rate,report=consistent_initial(lambda x,d,t:np.zeros(1),np.array([3.]),[0],np.zeros(1),fixed_rates={0:2.})
    np.testing.assert_array_equal(state,[3.]);np.testing.assert_array_equal(rate,[2.])
    assert report['free_state_indices']==report['free_dynamic_rate_indices']==[]
    assert all(r['rank']==0 and r['required_nullspace_defect']==0 for r in report['refinements'])


def test_explicit_default_selection_reproduces_default_path():
    def residual(x,d,t):return np.array([d[0]-x[1],x[1]-2.-3.*t])
    args=(residual,np.array([4.,0.]),[0],np.zeros(2))
    original=consistent_initial(*args)
    explicit=consistent_initial(*args,fixed_state_indices=[0],fixed_rates={})
    np.testing.assert_array_equal(original[0],explicit[0]);np.testing.assert_array_equal(original[1],explicit[1])
    assert original[2]['refinements']==explicit[2]['refinements']
    assert original[2]['residual_evaluations']==explicit[2]['residual_evaluations']


def test_optional_selection_preserves_switching_branch_rejection():
    def residual(x,d,t):return np.array([d[0]-x[1],d[1]-x[2],x[0]-t*abs(t)])
    with pytest.raises(AnalysisError,match='one-sided|constraints|spacing'):
        consistent_initial(residual,np.zeros(3),[0,1],np.zeros(3),fixed_state_indices=[0,1],fixed_rates={})


@pytest.mark.parametrize('options',[
    {'fixed_state_indices':True},{'fixed_state_indices':[False,1]},
    {'fixed_state_indices':[.5]},{'fixed_state_indices':[[0]]},
    {'fixed_state_indices':[0,0]},{'fixed_state_indices':[2]},
    {'fixed_state_indices':[-1]},{'fixed_state_indices':['0']},
    {'fixed_rates':[]},{'fixed_rates':{False:0.}},
    {'fixed_rates':{.5:0.}},{'fixed_rates':{2:0.}},
    {'fixed_rates':{0:True}},{'fixed_rates':{0:np.nan}},
    {'fixed_rates':{0:np.inf}},{'fixed_rates':{0:'1'}},
    {'fixed_rates':{0:np.array([1.])}},
])
def test_invalid_new_selections_are_rejected(options):
    with pytest.raises(AnalysisError,match='Fixed initial'):
        consistent_initial(lambda x,d,t:d,np.zeros(3),[0,1],np.zeros(3),**options)
