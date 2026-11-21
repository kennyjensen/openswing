"""Finish a real stalled ISAE iteration without relaxing coupled acceptance."""
import json
from pathlib import Path
import numpy as np
import pytest
from openswing.asw import parse_asw
from openswing.aero import FlightCondition
from openswing.network import StaticNetwork
from openswing.operating import time_load_constraints
from openswing.structured_static import _polish_fixed_geometry_circulation

FIXTURES = Path(__file__).parent/'fixtures'
TARGET = 1e-12

def stalled_network(*, free=False):
    request=json.loads((FIXTURES/'isae-circulation-finish-request.json').read_text())
    net=StaticNetwork(parse_asw(request['source']),request['panels'],
        FlightCondition(**request['condition']),None,[],
        operating_constraints=time_load_constraints('free') if free else ())
    x=np.load(FIXTURES/'isae-circulation-finish-state.npz')['x'].copy()
    if free:x=np.r_[x,np.zeros(net.operating.count)]
    return net,x

def test_saved_browser_stall_reaches_unchanged_full_target():
    net,x=stalled_network();before=x.copy();residual=net.residual(x,.5)
    assert np.max(abs(residual))>TARGET
    result=_polish_fixed_geometry_circulation(net,x,.5,residual,TARGET)
    assert result is not None
    trial,value,report=result
    np.testing.assert_array_equal(x,before)
    np.testing.assert_array_equal(trial[:net.gamma_start],x[:net.gamma_start])
    np.testing.assert_array_equal(trial[net.operating_start:],x[net.operating_start:])
    assert report['residual_after']<=TARGET and value@value<residual@residual
    assert net.iteration_fields is None and net.tangent_influences is None and net.aero_key is None
    fresh,_=stalled_network();checked=fresh.residual(trial,.5)
    assert np.max(abs(checked))<=TARGET
    np.testing.assert_array_equal(value,checked)

def test_flow_correction_rejects_new_unbalanced_aerodynamic_loads():
    net,x=stalled_network();_,base=net.residual(x,.5,detail=True)
    x[net.gamma_start:net.operating_start]+=1e-4
    _,changed=net.residual(x,.5,detail=True)
    # Balance this wrong circulation with explicit nodal counterloads. Solving
    # only its flow equation then upsets physical force/moment equilibrium.
    stations,ids=net.station_nodes[1]
    net.loads=[dict(beam=1,t=float(t),
        force=(base['force'][i]-changed['force'][i]).tolist(),
        moment=(base['moment'][i]-changed['moment'][i]).tolist()) for t,i in zip(stations,ids)]
    residual=net.residual(x,.5);before=x.copy()
    assert np.max(abs(residual[:net.gamma_start]))<=TARGET
    assert np.max(abs(residual[net.gamma_start:]))>TARGET
    assert _polish_fixed_geometry_circulation(net,x,.5,residual,TARGET) is None
    np.testing.assert_array_equal(x,before)
    assert net.iteration_fields is None and net.tangent_influences is None and net.aero_key is None

def test_unsatisfied_frame_load_rows_skip_circulation_finish(monkeypatch):
    import openswing.circulation_tangent as tangent
    net,x=stalled_network(free=True);residual=net.residual(x,.5)
    assert np.max(abs(residual[net.operating_start:]))>TARGET
    def forbidden(*args,**kwargs):raise AssertionError('Should not linearize unsatisfied operating rows')
    monkeypatch.setattr(tangent,'circulation_residual_columns',forbidden)
    assert _polish_fixed_geometry_circulation(net,x,.5,residual,TARGET) is None

def test_lagged_field_context_cannot_certify_a_finished_state(monkeypatch):
    from openswing.structured_static import IterationFields
    import openswing.circulation_tangent as tangent
    net,x=stalled_network();residual=net.residual(x,.5)
    fields=IterationFields();fields.phase='geometry';net.iteration_fields=fields
    def forbidden(*args,**kwargs):raise AssertionError('Should not finish inside lagged fields')
    monkeypatch.setattr(tangent,'circulation_residual_columns',forbidden)
    assert _polish_fixed_geometry_circulation(net,x,.5,residual,TARGET) is None
    assert net.iteration_fields is fields

@pytest.mark.parametrize('failure',['unavailable','singular','nonfinite'])
def test_unavailable_correction_restores_context_and_original_state(monkeypatch,failure):
    import openswing.circulation_tangent as tangent
    net,x=stalled_network();residual=net.residual(x,.5);before=x.copy()
    def failed(n,*args,**kwargs):
        if failure=='unavailable':raise tangent.CirculationDerivativeUnavailable('deliberate derivative failure')
        value=np.zeros((n.ng,n.ng))
        if failure=='nonfinite':value[:]=np.nan
        return value
    monkeypatch.setattr(tangent,'circulation_residual_columns',failed)
    assert _polish_fixed_geometry_circulation(net,x,.5,residual,TARGET) is None
    np.testing.assert_array_equal(x,before)
    assert net.iteration_fields is None and net.tangent_influences is None and net.aero_key is None
