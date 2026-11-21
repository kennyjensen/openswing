"""Recover the saved failed trial for tangent diagnostics, without another solve.

network_snapshot assumes its caller established convergence. For this explicitly
unconverged trial, override that display metadata; acceptance is always false.
The original failed process and replay-history qualification remain recorded.
"""
import argparse
import json
from pathlib import Path
import shutil
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts import probe_isae_ae2_stalled_tangent as base
from scripts.probe_isae_ae2_cold_trace import read,write,pin


def prepare(out):
    old=ROOT/'artifacts/isae/ae2-stalled-replay-20261110'
    previous=base.checked(old)
    terminal=read(old/'capture/terminal.json');sources=read(old/'capture/sources-verified.json')
    assert terminal['returncode']==1 and terminal['process_reaped']
    assert sources['all_pins_checked_before_and_after'] and sources['terminal']==pin(old/'capture/terminal.json')
    assert sources['plan']==pin(old/'plan.json')
    assert (old/'capture/trial.npz').exists() and (old/'capture/state.json').exists()
    base.prepare(out);plan=read(out/'plan.json')
    assert read(out/'request.json')==read(old/'request.json')
    paths=[Path(__file__),ROOT/'scripts/probe_isae_ae2_stalled_replay.py',old/'plan.json',old/'request.json']
    paths += [old/'capture'/name for name in ('trial.npz','state.json','terminal.json','sources-verified.json','stderr.log','progress.jsonl')]
    plan['pins'] += [pin(p) for p in paths]
    plan.update(replay_atol=previous['replay_atol'],replay_rtol=previous['replay_rtol'],saved_replay=str(old),
        method=__doc__,operations_at_capture=dict(new_equilibrium_solves=0,fresh_residuals=1))
    plan['qualifications'].append('Recover the raw checkpoint of a failed report-generation process. The fresh residual must match its stored value and replay log, and exceed the acceptance gate. Snapshot convergence metadata is explicitly false; no trial is promoted to equilibrium.')
    write(out/'plan.json',plan)
    print('Saved-trial recovery preparation complete.',flush=True)


def capture(out,plan):
    import numpy as np
    from scripts.probe_isae_ae2_staged_inverse import network
    from openswing.equilibrium_state import restore
    from openswing.network import network_snapshot
    from openswing.steady_continuation import plain
    old=Path(plan['saved_replay'])
    n=network(read(out/'request.json'))
    decoded=restore(n,read(old/'capture/state.json'));assert n.nfev==0
    with np.load(old/'capture/trial.npz') as f:x=f['x'].copy();stored=f['residual'].copy()
    np.testing.assert_allclose(decoded,x,rtol=1e-14,atol=2e-15)
    residual,data=n.residual(x,detail=True);assert n.nfev==1
    np.testing.assert_allclose(residual,stored,rtol=1e-8,atol=1e-12)
    original=[j for line in Path(plan['original_progress']).read_text().splitlines()
        if (j:=json.loads(line))['stage']=='equilibrium_iteration']
    replay=[j for line in (old/'capture/progress.jsonl').read_text().splitlines()
        if (j:=json.loads(line))['stage']=='equilibrium_iteration']
    assert len(original)==len(replay)==10
    for a,b in zip(replay,original):
        assert a['current']==b['current'] and abs(a['total']-b['total'])<=plan['replay_atol']+plan['replay_rtol']*abs(b['total'])
    error=float(np.max(abs(residual)))
    assert error>1e-12 and abs(error-replay[-1]['total'])<=1e-12
    fields=network_snapshot(n,residual,data)
    fields.update(analysis='unconverged_diagnostic_trial',converged=False,accepted=False)
    assert n.nfev==1
    write(out/'capture/fields.json',plain(fields))
    for name in ('trial.npz','state.json'):shutil.copyfile(old/'capture'/name,out/'capture'/name)
    report=dict(status='CAPTURED_UNCONVERGED_TRIAL',accepted=False,full_residual=error,
        recovery_method=__doc__,original_failed_receipt=pin(old/'capture/terminal.json'),
        operations=dict(new_equilibrium_solves=0,fresh_residuals=1),
        history=replay,original_history=original,replay_atol=plan['replay_atol'],replay_rtol=plan['replay_rtol'],
        maximum_history_absolute_difference=max(abs(a['total']-b['total']) for a,b in zip(replay,original)),
        maximum_history_relative_difference=max(abs(a['total']-b['total'])/abs(b['total']) for a,b in zip(replay,original)),
        primary_votes_added=0,pins=[pin(out/'capture'/name) for name in ('trial.npz','state.json','fields.json')])
    write(out/'capture/report.json',report)
    print(dict(status=report['status'],residual=error,history_relative_difference=report['maximum_history_relative_difference']),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['prepare','launch'])
    p.add_argument('--output',type=Path,required=True);p.add_argument('--phase',choices=['capture','direct','stencil','probe','assess'])
    a=p.parse_args()
    if a.action=='prepare':prepare(a.output.resolve())
    else:
        base.capture=capture
        base.launch(a.output.resolve(),a.phase)
