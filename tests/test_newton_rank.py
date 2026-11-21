"""Inverse-root uniqueness checks must cover both accepted Newton routes."""
import numpy as np
import pytest
from openswing.time_integration import newton, StepFailure


def plateau(values):
    """C1 monotone residual, linear near 0 and exactly zero for x >= 3/4.

    The initial derivative is -1 and residual 1, so one Newton correction
    lands near x=1 inside a continuum of roots. The joining cubic has value
    3/4 and slope -1 at x=1/4, and value/slope zero at x=3/4.
    """
    x=float(values[0])
    if x <= .25:
        value=1-x
    elif x < .75:
        u=2*(x-.25)
        value=u**3-1.25*u**2-.5*u+.75
    else:
        value=0.
    return np.array([value])


def test_nonunique_root_after_regular_correction_is_rejected():
    with pytest.raises(StepFailure, match='locally unique'):
        newton(plateau,np.array([0.]),1e-10,check_rank=True)


def test_nonunique_root_at_entry_is_rejected():
    with pytest.raises(StepFailure, match='locally unique'):
        newton(plateau,np.array([1.]),1e-10,check_rank=True)


def test_regular_root_after_correction_is_accepted():
    value,_,iterations,builds=newton(lambda x:x-.5,np.array([0.]),1e-10,check_rank=True)
    assert abs(value[0]-.5)<1e-10
    assert iterations==1
    assert builds>=1


def test_regular_root_at_entry_is_accepted():
    value,_,iterations,builds=newton(lambda x:x-.5,np.array([.5]),1e-10,check_rank=True)
    assert value[0]==.5
    assert iterations==0
    assert builds==1


def test_explicitly_optional_rank_check_retains_prior_behavior():
    value,_,iterations,_=newton(plateau,np.array([0.]),1e-10,check_rank=False)
    assert plateau(value)[0]==0.
    assert value[0]>.75
    assert iterations==1
