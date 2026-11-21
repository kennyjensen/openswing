"""AE-2 continuation using the checked centered complete geometry tangent.

Isolated diagnostic: all physical equations, Newton merit/iteration limits,
rank thresholds and independent physical checks remain unchanged. Both Newton
and fresh final tangents use existing fourth-order geometry decomposition.
"""
import argparse
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime,timezone
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts import probe_isae_ae2_incidence_stages as staged
from scripts import probe_isae_ae2_incidence as original
from scripts.probe_isae_ae2_cold_trace import read,write,pin

native_solve=staged.solve


def prepare(out):
    assert not out.exists()
    parent=ROOT/'artifacts/isae/ae2-incidence-refined-20261110';old=staged.checked(parent)
    staged.stage_receipt(parent,'beta0250','verify')
    tested=ROOT/'artifacts/isae/ae2-centered-tangent-20261110'
    from scripts.probe_isae_ae2_stalled_tangent import receipt
    staged.checked(tested);receipt(tested,'centered');receipt(tested,'verify')
    assert read(tested/'assessment.json')['status']=='DIRECTIONAL_GATE_PASS'
    plan=deepcopy(old)
    paths=[Path(p['path']) for p in old['pins']]
    paths += [Path(__file__),ROOT/'scripts/probe_isae_ae2_incidence_stages.py',parent/'plan.json',
        parent/'beta0250/result.json',parent/'beta0250/report.json',
        tested/'plan.json',tested/'assessment.json',tested/'verify/terminal.json',tested/'verify/sources-verified.json']
    for phase in ('solve','tangent','verify'):
        paths += [parent/'beta0250'/phase/f for f in ('terminal.json','sources-verified.json')]
    plan.update(method=__doc__,observed_utc=datetime.now(timezone.utc).isoformat(),
        pins=[pin(p) for p in sorted(set(paths))],seed_result=str(parent/'beta0250/result.json'),
        geometry_difference_order=4,geometry_difference_step=1e-6)
    plan['cases']=[];previous=None
    for name,beta in [('beta0250',2.5),('beta0275',2.75),('beta0300',3.),('beta0400',4.),('beta0500',5.)]:
        plan['cases'].append(dict(name=name,beta=beta,predecessor=previous));previous=name
    plan['qualifications'] += ['The initial beta2.5 control must reproduce its verified state.',
        'Both iteration and final matrices now use centered complete geometry; no production source changes.',
        'Old failed requests remain intact; this is a separately declared derivative-accuracy diagnostic.']
    write(out/'plan.json',plan)
    print('Prepared centered-tangent control and continuation to beta5.',flush=True)


@contextmanager
def centered_geometry(plan):
    from openswing import geometry_tangent
    native=geometry_tangent.geometry_columns
    def precise(*args,**kwargs):
        kwargs['difference_order']=plan['geometry_difference_order'];kwargs['step']=plan['geometry_difference_step']
        return native(*args,**kwargs)
    geometry_tangent.geometry_columns=precise
    try:yield
    finally:geometry_tangent.geometry_columns=native


def solve(out,plan,case):
    with centered_geometry(plan):native_solve(out,plan,case)


def tangent(out,plan,case):
    from scipy.sparse import save_npz
    n,x,folder,pending=staged.candidate(out,case)
    calls=n.nfev;cpu=time.process_time();before=time.monotonic()
    with centered_geometry(plan):jac=n.jacobian(x,1.,_sparse=True,_direct_geometry=True)
    assert n.geometry_derivative_diagnostics['difference_order']==4
    save_npz(folder/'tangent.npz',jac)
    write(folder/'tangent.json',dict(status='COMPLETE_CENTERED_FINAL_TANGENT',
        candidate=pin(folder/'candidate.json'),matrix=pin(folder/'tangent.npz'),shape=list(jac.shape),
        nonzeros=int(jac.nnz),residual_calls=n.nfev-calls,cpu_seconds=time.process_time()-cpu,
        wall_seconds=time.monotonic()-before,primary_votes_added=0))
    print(dict(beta=case['beta'],residual_calls=n.nfev-calls),flush=True)


def verify(out,plan,case):
    from scipy.sparse import load_npz
    from openswing.equilibrium_state import check_tangent_rank,capture
    from openswing.source_discrete import source_network_result
    from openswing.steady_continuation import plain
    staged.stage_receipt(out,case['name'],'tangent')
    n,x,folder,pending=staged.candidate(out,case)
    t=read(folder/'tangent.json')
    assert t['status']=='COMPLETE_CENTERED_FINAL_TANGENT'
    assert t['candidate']==pin(folder/'candidate.json') and t['matrix']==pin(folder/'tangent.npz')
    jac=load_npz(folder/'tangent.npz');assert jac.shape==(n.size,n.size)
    rank=check_tangent_rank(jac);del jac
    result=source_network_result(n,x);assert result['converged'] and result['residual']<=1e-12
    result.update(numerics=read(folder/'request.json')['numerics'],continuation_steps=1,
        equilibrium_state=capture(n,x,residual=result['residual'],include_launch=False),
        equilibrium_initialization=dict(initialization='saved physical equilibrium',
            newton_iterations=pending['newton']['iterations'],tangent_builds=pending['newton']['builds'],
            residual=result['residual'],**rank),diagnostic_stages=dict(method=__doc__,
            pending=pin(folder/'candidate.json'),final_tangent=pin(folder/'tangent.json'),primary_votes_added=0))
    result['equilibrium_state']['limitations'].append('Static source-discrete policy only; cannot initialize physical dynamics or a different structural operator.')
    write(folder/'result.json',plain(result));original.verify(out,plan,case)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['prepare','launch'])
    p.add_argument('--output',type=Path,required=True);p.add_argument('--case');p.add_argument('--phase',choices=['solve','tangent','verify'])
    a=p.parse_args()
    if a.action=='prepare':prepare(a.output.resolve())
    else:
        staged.solve=solve;staged.tangent=tangent;staged.verify=verify
        staged.launch(a.output.resolve(),a.case,a.phase)
