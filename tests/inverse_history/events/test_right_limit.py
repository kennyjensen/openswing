from pathlib import Path
from copy import deepcopy
import numpy as np
import pytest
from openswing.asw import parse_asw
from openswing.aero import FlightCondition,AnalysisError
from openswing.inertia import Motion
from openswing.forcing import TimeForcing,RightLimitForcing


def table():
    model=parse_asw((Path(__file__).parent/'inputs/rigid.asw').read_text())
    condition=FlightCondition(speed=10,alpha=0,mach=0,powers={1:3.})
    forcing=TimeForcing('time +E1 Ax\n-1 2 .3\n0 4 .5',model,condition,Motion(),1.,'prescribed')
    return condition,forcing,RightLimitForcing(forcing,0.)


def test_cutoff_right_limit_is_zero_without_changing_legacy_exact_end_values():
    c,original,right=table();before=deepcopy(original.report())
    assert original.values(0.)=={'E1':7.,'Ax':.5}
    assert right.values(0.)=={'E1':0.,'Ax':0.}
    assert right.values(0.,'left')==original.values(0.)
    new,motion=right.apply(0.,c,Motion())
    assert new.powers[1]==0.
    np.testing.assert_array_equal(motion.acceleration,[0,0,0])
    assert c.powers[1]==3. and original.report()==before


@pytest.mark.parametrize('t',[-.75,-.25,1e-12,.2])
@pytest.mark.parametrize('derivative',[0,1,2,3,4])
def test_right_limit_adapter_keeps_physical_support_away_from_anchor(t,derivative):
    _,original,right=table()
    assert right.values(t,derivative=derivative)==original.values(t,derivative=derivative)
    assert right.targets(t,derivative=derivative)==original.targets(t,derivative=derivative)


def test_physical_adapter_does_not_extend_polynomials_into_prehistory():
    _,_,right=table()
    with pytest.raises(AnalysisError,match='before the first'):right.values(-2.)
    with pytest.raises(AnalysisError):right.values(0.,side='future')
    with pytest.raises(AnalysisError):right.values(0.,derivative=True)
