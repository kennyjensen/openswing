"""The composition must not reinstall mutable network charts during owned replay."""
from copy import deepcopy
from pathlib import Path
import json
import numpy as np
import pytest
from openswing.aero import AnalysisError
from openswing.equilibrium_state import capture,restore,correct
from openswing.hinge_history import current
from test_hinge_chart_state import network

HERE=Path(__file__).resolve().parent/'fixtures'/'hinge-history'

@pytest.fixture(params=[400,-720])
def packet(request):
    angle=request.param
    return angle,json.loads((HERE/'legacy'/f'legacy-{angle:+d}-original.json').read_text())

@pytest.mark.parametrize('legacy',[True,False])
def test_hinge_no_install_restore_and_owned_capture_do_not_mutate_target(packet,legacy):
    angle,saved=packet;saved=deepcopy(saved)
    if not legacy:saved.update(version=2,hinge_charts=[dict(joint=1,angle_rad=float(np.deg2rad(angle)))])
    before=deepcopy(saved);n=network(1000)
    joint=next(c for c in n.constraints if c['type']==3);joint['angle_chart']=-3.125
    x=restore(n,saved,install_hinge_charts=False)
    assert current(n)==(-3.125,) and saved==before
    owned=(float(np.deg2rad(angle)),)
    packed=capture(n,x,hinge_charts_override=owned)
    assert packed['hinge_charts'][0]['angle_rad']==pytest.approx(owned[0],abs=1e-13)
    assert current(n)==(-3.125,) and saved==before


def test_hinge_failed_legacy_no_install_restore_does_not_mutate_target(packet):
    _,saved=packet;saved=deepcopy(saved);saved['launch']['loads'][0]['moment'][0]+=20
    n=network(1000);joint=next(c for c in n.constraints if c['type']==3);joint['angle_chart']=1.5
    with pytest.raises(AnalysisError):restore(n,saved,install_hinge_charts=False)
    assert current(n)==(1.5,)


def test_hinge_original_legacy_to_changed_target_uses_warm_branch(packet):
    angle,saved=packet;target=720 if angle>0 else -940
    n=network(target);x,info=correct(n,saved,1e-8,{})
    assert max(abs(n.residual(x)))<=1e-8
    assert np.rad2deg(capture(n,x)['hinge_charts'][0]['angle_rad'])==pytest.approx(target,abs=2e-7)
