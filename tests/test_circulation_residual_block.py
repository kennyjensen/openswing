"""The small finish block retains the complete physical flow derivative."""
import numpy as np
import pytest

from openswing.aero import FlightCondition
from openswing.network import StaticNetwork
from openswing.source_airflow import SourceAirflowNetwork
from openswing.structured_static import linearization
import openswing.circulation_tangent as tangent
from test_direct_circulation import model_for, state_for


@pytest.mark.parametrize('network',[StaticNetwork,SourceAirflowNetwork])
@pytest.mark.parametrize('example,extra,circulation',[
    ('flexible',{},.08), ('wing-body',{},.08),
    ('stepped-wing-body',{},.08), ('torsion-joint',{},.3),
    ('dae',{},.08), ('flexible',{'circulation_modes':{1:3}},.3),
    ('wing-body',{'freeze_influences':True},.3),
    ('rectangular',{},1.2), ('rectangular',{'stall':False},1.2),
    ('jet-0',{'powers':{1:50000.}},.3),
    ('jet-1',{'powers':{1:50000.}},.3),
    ('jet-2',{'powers':{1:50000.}},.3),
])
def test_small_block_matches_full_columns_and_physical_differences(network,example,extra,circulation,monkeypatch):
    net=network(model_for(example),4,FlightCondition(mach=.2,alpha=7,beta=3,
        rates=[.03,-.04,.02],ground_effect=1,position_earth=[0,0,30],**extra),None,[])
    x=state_for(net,circulation);factor=.6
    with linearization(net,x,factor,capture_circulation=True) as (fields,_):
        full=tangent.circulation_columns(net,fields,factor)
        def forbidden(*args,**kwargs):
            raise AssertionError('Circulation-only finish must not transfer mechanical loads')
        monkeypatch.setattr(tangent,'flow_load_columns',forbidden)
        short=tangent.circulation_residual_columns(net,fields)
    np.testing.assert_array_equal(short,full[net.gamma_start:net.operating_start])
    assert short.shape==(net.ng,net.ng)
    # Two independent centered physical-residual stencils, including stall,
    # Fourier projection, ground images, engines and both mechanical schemes.
    direction=np.random.default_rng(78).normal(size=net.ng)
    analytic=short@direction
    for step in (1e-5,3e-6):
        plus=x.copy();minus=x.copy()
        plus[net.gamma_start:net.operating_start]+=step*direction
        minus[net.gamma_start:net.operating_start]-=step*direction
        fd=((net.residual(plus,factor)-net.residual(minus,factor))/(2*step))[net.gamma_start:net.operating_start]
        assert np.max(abs(analytic-fd)/(1+abs(fd)))<1e-7
    assert net.iteration_fields is None and net.tangent_influences is None


def test_missing_capture_is_rejected():
    class Empty:circulation_aero=None
    with pytest.raises(tangent.CirculationDerivativeUnavailable,match='Missing'):
        tangent.circulation_residual_columns(None,Empty())
