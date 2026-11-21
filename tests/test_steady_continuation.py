"""Accepted-load restarts preserve the equations, branch and failure budgets."""
from copy import deepcopy
import json
import subprocess

import numpy as np
import pytest

from openswing.aero import AnalysisError
from openswing.asw import parse_asw
from openswing.bridge import dispatch
from openswing.hinge_history import current
from openswing.source_discrete import SourceSectionNetwork
from openswing.source_airflow import SourceAirflowNetwork
from openswing.network import StaticNetwork
from openswing.structured_static import equilibrate
from openswing.steady_continuation import ContinuationPending, context, restore, digest
from test_source_joints import source, mounted_source, mounted_condition


def mechanical():
    model = parse_asw(source(distant=False,rigid=True,axis='1 0 0'),
                      beam_interpolation='drela-segspl-v1')
    return SourceSectionNetwork(model,4,None,[0.,0.,0.],
        [dict(beam=2,t=3.,force=[0.,0.,.2])])


def coupled():
    return SourceAirflowNetwork(parse_asw(mounted_source(),beam_interpolation='drela-segspl-v1'),
        4,mounted_condition(),None,[],steady_trim=True)


def midpoint():
    net=mechanical()
    return StaticNetwork(net.model,4,None,[0.,0.,0.],net.loads)


def first(net):
    with pytest.raises(ContinuationPending) as caught:
        equilibrate(net,max_load_steps=1)
    return json.loads(json.dumps(caught.value.checkpoint,allow_nan=False))


@pytest.fixture(scope='module')
def packet():
    return first(mechanical())


@pytest.mark.parametrize('factory',[mechanical,coupled,midpoint])
def test_serial_jobs_match_uninterrupted_states_and_hinge_branches(factory):
    ordinary=factory();expected,expected_steps=equilibrate(ordinary)
    expected_charts=current(ordinary)
    saved=None;targets=[];accepted=0
    for _ in range(40):
        net=factory()
        try:
            actual,steps=equilibrate(net,checkpoint=saved,max_load_steps=1)
        except ContinuationPending as pending:
            saved=json.loads(json.dumps(pending.checkpoint,allow_nan=False))
            assert saved['accepted_load_steps']==accepted+1
            assert saved['physical_residual']<=1e-12
            accepted+=1;targets.append(saved['load_fraction'])
            # Saving did not convert the partial state to full equilibrium.
            state=np.array(saved['coordinates'])
            assert np.max(abs(net.residual(state,saved['load_fraction'])))<=1e-12
            assert np.max(abs(net.residual(state,1.)))>1e-12
        else:
            break
    else:pytest.fail('Synthetic continuation did not finish in bounded jobs')
    assert targets and targets==sorted(set(targets))
    assert steps==expected_steps
    np.testing.assert_array_equal(actual,expected)
    np.testing.assert_array_equal(current(net),expected_charts)
    assert actual.tobytes()==expected.tobytes()
    assert np.asarray(current(net)).tobytes()==np.asarray(expected_charts).tobytes()
    assert np.max(abs(net.residual(actual)))<=1e-12
    assert all(r['accepted_load_rotation_increment_rad']<=np.deg2rad(5)*(1+1e-8)
               for r in net.continuation_diagnostics if r['accepted'])


def test_saved_rejection_budget_and_increment_survive_exactly(packet):
    p=deepcopy(packet);p['rejected_load_attempts']=127
    p['sha256']=digest({k:v for k,v in p.items() if k!='sha256'})
    n=mechanical();ctx=context(n,1e-8,4,True,True)
    state,factor,increment,steps,rejected,charts,_=restore(n,p,ctx)
    assert rejected==127 and increment==p['next_increment']
    assert steps==p['accepted_load_steps'] and factor==p['load_fraction']
    np.testing.assert_array_equal(state,p['coordinates'])
    np.testing.assert_array_equal(charts,p['hinge_charts'])
    # Checking a packet must not leave its branch installed in the caller.
    assert current(n)==(0.,)


@pytest.mark.parametrize('change',[
    lambda p:p.update(load_fraction=0.),lambda p:p.update(load_fraction=1.),
    lambda p:p.update(next_increment=0.),lambda p:p.update(next_increment=2.),
    lambda p:p.update(accepted_load_steps=True),lambda p:p.update(rejected_load_attempts=128),
    lambda p:p['coordinates'].__setitem__(0,.01),
    lambda p:p['hinge_charts'].__setitem__(0,2*np.pi),
    lambda p:p['context'].__setitem__('kernel_sha256','different kernel'),
    lambda p:p['context']['identity'].__setitem__('rigid_weight_attachments',[]),
])
def test_invalid_or_physically_inconsistent_packets_are_rejected(packet,change):
    n=mechanical();ctx=context(n,1e-8,4,True,True);p=deepcopy(packet);change(p)
    # Even after an intentional checksum rewrite, context and physical gates
    # must reject incompatible states. The checksum is not authentication.
    p['sha256']=digest({k:v for k,v in p.items() if k!='sha256'})
    with pytest.raises(AnalysisError):restore(n,p,ctx)
    assert current(n)==(0.,) and n.iteration_fields is None and n.tangent_influences is None


@pytest.mark.parametrize('change',[
    lambda c:c['setup'].update(gravity=[0.,0.,-1.]),
    lambda c:c['setup'].update(loads=[]),
    lambda c:c['setup'].update(panels=8),
    lambda c:c['solver'].update(tolerance=1e-7),
    lambda c:c['solver'].update(continuation_steps=8),
    lambda c:c['solver'].update(reuse_matrices=False),
])
def test_context_changes_cannot_resume(packet,change):
    n=mechanical();ctx=context(n,1e-8,4,True,True);change(ctx)
    with pytest.raises(AnalysisError,match='do not match'):restore(n,packet,ctx)


def test_checksum_and_nonfinite_payloads_fail_before_physics(packet,monkeypatch):
    n=mechanical();ctx=context(n,1e-8,4,True,True)
    def forbidden(*args,**kwargs):pytest.fail('Malformed packet reached the equations')
    monkeypatch.setattr(n,'residual',forbidden)
    p=deepcopy(packet);p['next_increment']*=.9
    with pytest.raises(AnalysisError,match='checksum'):restore(n,p,ctx)
    p=deepcopy(packet);p['coordinates'][0]=float('nan')
    with pytest.raises(AnalysisError,match='finite JSON'):restore(n,p,ctx)


def javascript_roundtrip(value):
    result=subprocess.run(['node','--jitless','--max-old-space-size=32','--input-type=module','-e',
        "import {readFileSync} from 'node:fs';const value=JSON.parse(readFileSync(0,'utf8'));process.stdout.write(JSON.stringify(value));"],
        input=json.dumps(value,allow_nan=False),text=True,capture_output=True,check=True,timeout=15)
    return json.loads(result.stdout)


def test_checksum_uses_numeric_values_across_actual_javascript_json():
    value={'numbers':[1.,-0.,0.,1e-20,1e20,2**54,np.nextafter(1.,2.)],
           'types':[True,False,None,'1',{'x':1}]}
    changed=javascript_roundtrip(value)
    assert type(changed['numbers'][0]) is int
    assert digest(changed)==digest(value)
    assert digest(True)!=digest(1) and digest('1')!=digest(1)


@pytest.mark.parametrize('value',[float('nan'),float('inf'),float('-inf'),2**53+1,10**400])
def test_checksum_rejects_numbers_that_cannot_roundtrip(value):
    with pytest.raises(AnalysisError,match='finite JSON'):digest({'value':value})


def test_javascript_checkpoint_roundtrip_passes_fresh_physical_restore(packet):
    transported=javascript_roundtrip(packet)
    n=mechanical();ctx=context(n,1e-8,4,True,True)
    state,factor,increment,steps,rejected,charts,_=restore(n,transported,ctx)
    np.testing.assert_array_equal(state,packet['coordinates'])
    assert factor==packet['load_fraction'] and increment==packet['next_increment']
    assert steps==packet['accepted_load_steps'] and rejected==packet['rejected_load_attempts']
    assert charts==tuple(packet['hinge_charts'])


def request():
    return dict(action='solve',mode='structural',source=mechanical().model.dumps(),panels=4,
        numerics=dict(beam_interpolation='drela-segspl-v1',structural_operator=SourceSectionNetwork.structural_operator),
        gravity=[0.,0.,0.],loads=[dict(beam=2,t=3.,force=[0.,0.,.2])],
        continuation=dict(max_load_steps=1))


def test_json_boundary_separates_pending_state_from_completed_equilibrium():
    r=request();result=dispatch(r)
    assert not result['converged'] and result['continuation_status']=='pending'
    assert result['analysis']=='equilibrium_continuation' and 'equilibrium_state' not in result
    assert result['checkpoint']['format']!='openswing-equilibrium'
    for _ in range(40):
        r['continuation']['checkpoint']=json.loads(json.dumps(result['checkpoint']))
        result=dispatch(r)
        if result.get('continuation_status')=='complete':break
    else:pytest.fail('JSON continuation did not finish')
    assert result['converged'] and result['residual']<=1e-12
    assert result['equilibrium_state']['format']=='openswing-equilibrium'
    assert result['analysis']=='structural_static' and result['structural_only']


@pytest.mark.parametrize('bound',[None,False,0,-1,1.5])
def test_invalid_job_bound_does_not_start_a_solve(bound):
    r=request();r['continuation']['max_load_steps']=bound
    with pytest.raises(AnalysisError,match='max_load_steps'):dispatch(r)


def test_job_does_not_silently_use_unbounded_fallback(packet):
    with pytest.raises(AnalysisError,match='structured steady route'):
        equilibrate(mechanical(),checkpoint=packet,initial_state={})
    r=request();r['controller']={}
    with pytest.raises(ValueError,match='controller'):dispatch(r)
