"""Lightweight residuals preserve phase-guard receiver positions, including sensors."""
from copy import deepcopy
import numpy as np
import pytest
from openswing.asw import parse_asw
from openswing.aero import FlightCondition
from openswing.network import StaticNetwork
from test_direct_circulation import model_for,state_for


@pytest.mark.parametrize('example',['wing-body','jet-2'])
@pytest.mark.parametrize('sensors',[False,True])
def test_phase_guard_positions_match_complete_snapshot(example,sensors):
    model=model_for(example)
    if sensors:model=parse_asw(model.dumps()+'\nSensor\n1 1 0 1 .2 .1\nEnd\n')
    condition=FlightCondition(speed=30,alpha=7,beta=3,mach=.2,rates=[.03,-.04,.02],
        position_earth=[2,-3,30],attitude=[13,-7,21],time=.7,
        powers={1:50000.} if example=='jet-2' else {},
        gust=dict(type='sinusoid',amplitude=[.01,.02,.03],wavevector=[.2,-.1,.3],omega=1.))
    n=StaticNetwork(model,4,condition,None,[]);state=state_for(n,.08)
    residual=n.residual(state);light=deepcopy(n.aero_cached)
    full,data=n.residual(state,detail=True)
    np.testing.assert_array_equal(residual,full)
    np.testing.assert_array_equal(light['gust']['sample_positions_earth'],data['aero']['gust']['sample_positions_earth'])
    assert len(light['gust']['sample_positions_earth'])>0
    assert 'sensor_airflow' not in light and 'trefftz' not in light
