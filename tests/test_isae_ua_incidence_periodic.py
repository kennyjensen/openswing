"""Full forcing, physical startup and long-horizon transient reconstruction."""
import math
from pathlib import Path
import sys

import numpy as np
import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from isae_ua_incidence_periodic import full_request,reference_history,PERIOD,ALPHA,K,SPEED,CYCLES
from isae_ua_incidence_reference import trajectory,steady_circulation


def test_initial_request_contains_all_eight_cycles_with_correct_force_direction():
    request=full_request(80)
    table=np.array([[float(v) for v in row.split()] for row in request['time']['forcing'].splitlines()[1:]])
    assert table.shape==(641,3)
    assert table[0,0]==0 and table[-1,0]==pytest.approx(8*PERIOD)
    alpha=math.radians(ALPHA)
    heave=np.array([-math.sin(alpha),math.cos(alpha)])
    wind=np.array([math.cos(alpha),math.sin(alpha)])
    np.testing.assert_allclose(table[:,1:]@wind,0.,rtol=0,atol=2e-14)
    np.testing.assert_allclose(table[:,1:]@heave,-.25*(2*SPEED*K)**2*np.cos(2*SPEED*K*table[:,0]),rtol=0,atol=1e-12)
    assert request['time']['duration']==8*PERIOD and request['condition']['alpha']==9.


def test_long_horizon_transient_matches_direct_adaptive_integration():
    reference=reference_history(24)
    rows=reference['cold_rows']
    direct=trajectory([r['time'] for r in rows],alpha_deg=ALPHA,k=K,boundary='steady',method='DOP853')['rows']
    for key in ('circulation','circulation_rate','CL'):
        expected=np.array([r[key] for r in direct]);actual=np.array([r[key] for r in rows])
        assert np.max(abs(actual-expected))/np.max(abs(expected))<1e-9
    assert rows[0]['circulation']==pytest.approx(steady_circulation(alpha_deg=9.),abs=1e-14,rel=0)
    assert abs(rows[0]['circulation_rate'])<1e-12
    assert abs(rows[0]['circulation']-reference['periodic']['initial_circulation'])>.1


def test_period_boundaries_preserve_the_analytic_transient_without_resets():
    reference=reference_history(24)
    rows=reference['cold_rows'];start=rows[0]['circulation']-reference['periodic']['initial_circulation']
    decay=SPEED*math.cos(math.radians(ALPHA))/2
    for cycle in range(CYCLES+1):
        actual=rows[24*cycle]['circulation']-reference['periodic']['initial_circulation']
        assert actual==pytest.approx(start*math.exp(-decay*cycle*PERIOD),abs=2e-14,rel=1e-12)
