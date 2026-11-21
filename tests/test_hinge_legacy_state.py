"""Migration must certify ORIGINAL loads/law, never fit the target or rotations."""
from copy import deepcopy
import json
from pathlib import Path
import numpy as np
import pytest
from openswing.aero import AnalysisError,FlightCondition
from openswing.asw import parse_asw
from openswing.network import solve_static,StaticNetwork
from openswing.equilibrium_state import restore,capture
from openswing.legacy_hinge_state import recover
from test_hinge_chart_state import SOURCE,network,solve,check


def legacy(result):
    packet=deepcopy(result['equilibrium_state']);packet['version']=1;packet.pop('hinge_charts')
    return json.loads(json.dumps(packet,allow_nan=False))


@pytest.fixture(scope='module')
def packets():
    return {angle:legacy(solve(angle)) for angle in (400,-720)}


@pytest.mark.parametrize('angle',[400,-720])
def test_hinge_original_legacy_large_angle_recovery(packets,angle,tmp_path):
    saved=deepcopy(packets[angle]);before=deepcopy(saved);n=network(angle)
    upgraded=recover(n,saved)
    assert saved==before
    assert upgraded['version']==2
    assert np.rad2deg(upgraded['hinge_charts'][0]['angle_rad'])==pytest.approx(angle,abs=1e-10)
    assert upgraded['legacy_hinge_recovery']['original_residual']<1e-10
    assert not upgraded['legacy_hinge_recovery']['target_settings_used']
    assert not upgraded['legacy_hinge_recovery']['nonlinear_equilibrium_solved']
    x=restore(n,saved);assert max(abs(n.residual(x)))<1e-10
    assert np.rad2deg(capture(n,x)['hinge_charts'][0]['angle_rad'])==pytest.approx(angle,abs=1e-10)
    check(solve(angle,saved),angle)
    (tmp_path/f'legacy-{angle:+d}-migrated.json').write_text(json.dumps(upgraded,indent=2)+'\n')


@pytest.mark.parametrize('start,target',[(400,720),(-720,-940)])
def test_hinge_recovery_uses_original_load_before_changed_target_correction(packets,start,target):
    current=network(target);upgraded=recover(current,packets[start])
    assert np.rad2deg(upgraded['hinge_charts'][0]['angle_rad'])==pytest.approx(start,abs=1e-10)
    x=restore(current,packets[start]);assert max(abs(current.residual(x)))>1e-3
    check(solve(target,packets[start]),target)


@pytest.mark.parametrize('edit',[
    lambda s:s.pop('launch'),
    lambda s:s['launch'].pop('loads'),
    lambda s:s['launch'].pop('condition'),
    lambda s:s['launch'].pop('motion'),
    lambda s:s['launch'].pop('controller'),
    lambda s:s['launch'].update(released_constraints=[dict(variable='speed',quantity='speed',target=1)]),
    lambda s:s['launch']['loads'][0]['moment'].__setitem__(0,720),
    lambda s:s['internal_moment'][0].__setitem__(0,s['internal_moment'][0][0]+1),
    lambda s:[row.__setitem__(0,row[0]+360) for row in s['internal_moment']],
])
def test_hinge_missing_or_inconsistent_original_evidence_rejects_atomically(packets,edit):
    saved=deepcopy(packets[400]);edit(saved);n=network(720)
    joint=next(c for c in n.constraints if c['type']==3);joint['angle_chart']=-8
    with pytest.raises(AnalysisError):restore(n,saved)
    assert joint['angle_chart']==-8


ENGINE='\nEngine\n1 0 2 2 0 4 0 1 0 0 0 1 -1 0 0\nEnd\n'


@pytest.fixture(scope='module')
def controller_packet():
    m=parse_asw(SOURCE+ENGINE);c=FlightCondition(speed=10,alpha=0,mach=0,powers={1:0})
    definition=dict(outputs=[dict(actuator='E1',expression='40')])
    out=solve_static(m,c,4,gravity=[0,0,0],controller=definition)
    saved=legacy(out)
    assert saved['launch']['condition']['powers']=={'1':0}
    assert saved['feedback']['values'][0]==pytest.approx(40)
    return m,c,definition,saved


def test_hinge_controller_defined_original_load_is_rebuilt_and_verified(controller_packet,tmp_path):
    m,c,definition,saved=controller_packet;n=StaticNetwork(m,4,c,[0,0,0],())
    upgraded=recover(n,saved)
    assert upgraded['legacy_hinge_recovery']['controller_verified']
    assert np.rad2deg(upgraded['hinge_charts'][0]['angle_rad'])==pytest.approx(40,abs=1e-7)
    assert upgraded['legacy_hinge_recovery']['original_residual']<1e-8
    # This changed controller is a target. It must not rewrite original evidence.
    changed=dict(outputs=[dict(actuator='E1',expression='50')])
    out=solve_static(m,c,4,gravity=[0,0,0],controller=changed,initial_state=saved)
    check(out,50)
    (tmp_path/'legacy-controller-migrated.json').write_text(json.dumps(upgraded,indent=2)+'\n')


@pytest.mark.parametrize('edit',[
    lambda s:s['launch'].update(controller=None),
    lambda s:s.update(feedback=None),
    lambda s:s['feedback']['values'].__setitem__(0,400),
    lambda s:s['launch']['controller']['outputs'][0].update(expression='41'),
    lambda s:s['launch']['motion']['rates'].__setitem__(0,1),
])
def test_hinge_incomplete_or_corrupt_original_controller_evidence_rejects(controller_packet,edit):
    m,c,definition,packet=controller_packet;saved=deepcopy(packet);edit(saved)
    n=StaticNetwork(m,4,c,[0,0,0],())
    with pytest.raises(AnalysisError):restore(n,saved)
