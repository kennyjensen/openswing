from copy import deepcopy
from pathlib import Path
import json
import numpy as np
import pytest
from openswing.aero import AnalysisError
from openswing.asw import parse_asw
from openswing.network import StaticNetwork
from openswing.hinge_history import current,lifted
from openswing.local_motion import rotation_matrix as exp
from openswing.time_state import checkpoint,restore_checkpoint,pack_state,unpack_state

HERE=Path(__file__).resolve().parent/'fixtures'/'hinge-history'

@pytest.fixture
def network():
    model=parse_asw((HERE/'source'/'rigid-hinge-release.asw').read_text())
    return StaticNetwork(model,4,None,[0,0,0],[])

@pytest.mark.parametrize('angle,delta',[(400,-20),(-400,20),(720,10),(-720,-10)])
def test_hinge_trial_rotation_is_lifted_from_owned_history_without_mutating_network(network,angle,delta):
    n=network;c=next(c for c in n.constraints if c['type']==3)
    previous=np.tile(np.eye(3),(n.nn,1,1));previous[c['b']]=exp(np.deg2rad(angle)*c['law'].axis)
    q=previous.copy();q[c['b']]=exp(np.deg2rad(angle+delta)*c['law'].axis)
    centers=(float(np.deg2rad(angle)),);before=current(n)
    actual=lifted(n,q,centers,previous)
    assert actual[0]==pytest.approx(np.deg2rad(angle+delta),abs=1e-13)
    assert current(n)==before and centers==(float(np.deg2rad(angle)),)

def test_hinge_opposite_node_rotations_cannot_hide_a_relative_full_turn(network):
    n=network;c=next(c for c in n.constraints if c['type']==3)
    before=np.tile(np.eye(3),(n.nn,1,1));trial=before.copy()
    trial[c['a']]=exp(np.deg2rad(100)*c['law'].axis);trial[c['b']]=exp(np.deg2rad(-100)*c['law'].axis)
    with pytest.raises(AnalysisError,match='Relative hinge travel'):lifted(n,trial,(0.,),before)
    assert current(n)==(0.,)

@pytest.mark.parametrize('centers',[None,[],[True],[float('nan')],[10**400],[0.,0.]])
def test_hinge_malformed_history_does_not_change_network(network,centers):
    with pytest.raises(AnalysisError):lifted(network,np.tile(np.eye(3),(network.nn,1,1)),centers)
    assert current(network)==(0.,)

@pytest.fixture(scope='module')
def trajectory():
    row=json.loads((HERE/'history'/'owned-v2-release-400-0.35-0.02-order2.json').read_text())
    assert row['status']=='COMPUTED_INDEPENDENT_COMPARISON_REFINEMENT_REQUIRED'
    model=parse_asw((HERE/'source'/'rigid-hinge-release.asw').read_text())
    return model,row['result']

def test_hinge_checkpoint_members_keep_distinct_hinge_angles_and_do_not_install_network_charts(trajectory):
    model,out=trajectory;saved=checkpoint(out,-1);original=deepcopy(saved)
    n,f,state,older,*_=restore_checkpoint(model,saved)
    assert state.hinge_charts!=older.hinge_charts
    assert current(n)==(0.,)
    for s in (state,older):
        packed=pack_state(n,s);restored=unpack_state(n,packed,f)
        np.testing.assert_allclose(restored.hinge_charts,s.hinge_charts,rtol=0,atol=1e-13)
    assert current(n)==(0.,) and saved==original

@pytest.mark.parametrize('member',['state','older'])
def test_hinge_whole_turn_edit_cannot_pass_checkpoint_replay(trajectory,member):
    model,out=trajectory;saved=checkpoint(out,-1)
    saved[member]['network']['hinge_charts'][0]['angle_rad']+=2*np.pi
    with pytest.raises(AnalysisError):restore_checkpoint(model,saved)

def test_hinge_residual_chart_edit_cannot_pass_checkpoint_replay(trajectory):
    model,out=trajectory;saved=checkpoint(out,-1)
    saved['options']['hinge_charts'][0]+=2*np.pi
    with pytest.raises(AnalysisError):restore_checkpoint(model,saved)


@pytest.mark.parametrize('index',[0,-1])
def test_hinge_physical_only_checkpoint_cannot_hide_whole_turn_with_unchanged_residual_reference(trajectory,index):
    model,out=trajectory;saved=checkpoint(out,index)
    assert saved['version']==2
    saved.pop('accepted_method',None)
    saved['state']['network']['hinge_charts'][0]['angle_rad']+=2*np.pi
    with pytest.raises(AnalysisError,match='cached residual branch'):restore_checkpoint(model,saved)

def test_hinge_initial_coherent_record_edit_still_checks_original_residual_branch(trajectory):
    model,out=trajectory;saved=checkpoint(out,0)
    saved['state']['network']['hinge_charts'][0]['angle_rad']+=2*np.pi
    saved['accepted_method']['endpoint']['state']['network']['hinge_charts'][0]['angle_rad']+=2*np.pi
    with pytest.raises(AnalysisError,match='cached residual branch'):restore_checkpoint(model,saved)

def test_hinge_hinged_checkpoint_has_explicit_version2_in_snapshots_and_packet(trajectory):
    model,out=trajectory
    for index,snapshot in enumerate(out['snapshots']):
        assert snapshot['restart']['version']==2
        assert checkpoint(out,index)['version']==2
    old=checkpoint(out,0);old['version']=1
    with pytest.raises(AnalysisError,match='require version-2'):restore_checkpoint(model,old)
