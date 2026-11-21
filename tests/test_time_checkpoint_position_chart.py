"""Checkpointed BDF keeps sub-ULP translations at large jig coordinates."""
from copy import deepcopy
import json
from types import SimpleNamespace

import numpy as np
import pytest

from openswing.aero import AnalysisError
from openswing.time_integration import bdf_coefficients, local_position_derivative
from openswing.time_state import position_chart, restore_position_chart


def fixture():
    n=SimpleNamespace(nn=2,L=200000.,rj=np.array([[0.,-100000.,0.],[0.,100000.,0.]]))
    x=np.zeros(12)
    x.reshape(2,6)[:,:3]=np.array([[1e-30,2e-18,-3e-30],[-2e-30,-3e-18,1e-30]])
    return n,x


def packet(n,x):
    return json.loads(json.dumps(dict(network=dict(positions=(n.rj+n.L*x.reshape(n.nn,6)[:,:3]).tolist()),
                                     position_chart=position_chart(n,x)),allow_nan=False))


def test_roundtrip_retains_hidden_displacement_and_bdf_derivative():
    n,x=fixture(); previous=x*.7;older=x*.4
    restored=[]
    for value in (x,previous,older):
        saved=packet(n,value)
        decoded=np.zeros_like(value)
        decoded.reshape(n.nn,6)[:,:3]=(np.asarray(saved['network']['positions'])-n.rj)/n.L
        assert not np.array_equal(decoded,value)  # Absolute-position decoding loses y.
        restore_position_chart(n,saved,decoded)
        np.testing.assert_array_equal(decoded,value)
        restored.append(SimpleNamespace(x=decoded))
    exact=local_position_derivative(n,*[SimpleNamespace(x=v) for v in (x,previous,older)],bdf_coefficients(.001,.001))
    np.testing.assert_array_equal(local_position_derivative(n,*restored,bdf_coefficients(.001,.001)),exact)


def test_legacy_packet_keeps_its_existing_decode():
    n,x=fixture();saved=packet(n,x);del saved['position_chart']
    decoded=x*0+7.;before=decoded.copy()
    restore_position_chart(n,saved,decoded)
    np.testing.assert_array_equal(decoded,before)


def test_compatible_origin_change_preserves_physical_displacement():
    n,x=fixture();saved=packet(n,x)
    changed=SimpleNamespace(nn=n.nn,L=n.L,rj=n.rj.copy())
    changed.rj[:,1]=np.nextafter(changed.rj[:,1],np.inf)
    decoded=np.zeros_like(x);restore_position_chart(changed,saved,decoded)
    expected=(n.rj-changed.rj)+n.L*x.reshape(n.nn,6)[:,:3]
    np.testing.assert_allclose(changed.L*decoded.reshape(n.nn,6)[:,:3],expected,rtol=2e-16,atol=0)
    np.testing.assert_array_equal(changed.rj+changed.L*decoded.reshape(n.nn,6)[:,:3],saved['network']['positions'])


@pytest.mark.parametrize('change',[
    lambda d:d['position_chart'].update(scheme='unknown'),
    lambda d:d['position_chart'].update(scale=0),
    lambda d:d['position_chart'].update(scale=float('inf')),
    lambda d:d['position_chart'].update(coordinates=[[0,0,0]]),
    lambda d:d['position_chart']['coordinates'][0].__setitem__(0,float('nan')),
    lambda d:d['position_chart']['coordinates'][0].__setitem__(0,1.),
    lambda d:d['position_chart']['origin'][0].__setitem__(1,0.),
    lambda d:d['position_chart'].update(unexpected=True),
])
def test_malformed_or_physically_inconsistent_chart_is_rejected(change):
    n,x=fixture();saved=packet(n,x);change(saved)
    with pytest.raises(AnalysisError):restore_position_chart(n,saved,np.zeros_like(x))
