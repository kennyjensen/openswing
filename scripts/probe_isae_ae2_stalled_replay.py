"""Roundoff-aware replay of the retained unconverged AE-2 beta2.75 trial.

Only diagnostic replay-history equality changes. Native, equilibrium, tangent
comparison, physical and rank gates remain unchanged. The original stricter
history rejection is retained; this trial never becomes an accepted state.
"""
import argparse
import json
from pathlib import Path
import sys
import time
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts import probe_isae_ae2_stalled_tangent as base
from scripts.probe_isae_ae2_cold_trace import read,write,pin
from scripts.probe_isae_ae2_incidence_iteration import iteration_geometry


def prepare(out):
    base.prepare(out)
    plan=read(out/'plan.json')
    old=ROOT/'artifacts/isae/ae2-stalled-tangent-20261110'
    base.checked(old)
    assert read(old/'capture/terminal.json')['returncode']==1
    assert read(old/'capture/terminal.json')['process_reaped']
    paths=[Path(__file__),old/'plan.json']+[old/'capture'/name for name in ('terminal.json','sources-verified.json','stderr.log','progress.jsonl')]
    plan['pins'] += [pin(p) for p in paths]
    plan.update(replay_atol=1e-12,replay_rtol=1e-7)
    plan['qualifications'].append('A new replay-history gate permits 1e-12 absolute plus 1e-7 relative residual differences with identical iteration indices. It concerns an unconverged diagnostic replay only. The prior absolute-only history rejection is retained. No physical acceptance tolerance changes.')
    write(out/'plan.json',plan)


def capture(out, plan):
    import numpy as np
    from scripts.probe_isae_ae2_staged_inverse import network
    from openswing.equilibrium_state import correct, capture as packet
    from openswing.source_coupled import SourceCoupledNetwork
    from openswing.network import network_snapshot
    from openswing.steady_continuation import plain
    request=read(out/'request.json'); n=network(request)
    cls=SourceCoupledNetwork; owned='jacobian' in cls.__dict__; native=cls.jacobian
    history=[]; events=[]; captured=[]; before=time.monotonic()
    old=[readline for line in Path(plan['original_progress']).read_text().splitlines()
        if (readline:=json.loads(line))['stage']=='equilibrium_iteration']

    class CapturedTrial(Exception):
        pass

    def intercept(net,x,factor,**kwargs):
        if kwargs.get('_sparse',False) or kwargs.get('_direct_geometry') is not False:
            return native(net,x,factor,**kwargs)
        assert net is n and factor==1 and not captured
        assert len(history)==len(old)
        for a,b in zip(history,old):
            assert a['current']==b['current'] and abs(a['total']-b['total'])<=plan['replay_atol']+plan['replay_rtol']*abs(b['total'])
        residual,data=n.residual(x,detail=True); error=float(np.max(abs(residual)))
        assert abs(error-old[-1]['total'])<=plan['replay_atol']+plan['replay_rtol']*abs(old[-1]['total']) and error>request['tolerance']
        np.savez_compressed(out/'capture/trial.npz',x=x,residual=residual)
        write(out/'capture/state.json',packet(n,x,residual=error,include_launch=False))
        fields=network_snapshot(n,residual,data); assert not fields['converged']
        write(out/'capture/fields.json',plain(fields))
        write(out/'capture/report.json',plain(dict(status='CAPTURED_UNCONVERGED_TRIAL',accepted=False,
            history=history,original_history=old,full_residual=error,tangent_calls=events,
            replay_atol=plan['replay_atol'],replay_rtol=plan['replay_rtol'],
            maximum_history_absolute_difference=max(abs(a['total']-b['total']) for a,b in zip(history,old)),
            maximum_history_relative_difference=max(abs(a['total']-b['total'])/abs(b['total']) for a,b in zip(history,old)),
            seeded_corrector=n._seeded_corrector_diagnostics,primary_votes_added=0,
            pins=[pin(out/'capture'/name) for name in ('trial.npz','state.json','fields.json')])) )
        captured.append(True)
        raise CapturedTrial()

    with (out/'capture/progress.jsonl').open('x') as log:
        def progress(stage,current,total):
            event=dict(stage=stage,current=current,total=total,wall_seconds=time.monotonic()-before)
            log.write(json.dumps(event,default=float)+'\n');log.flush()
            if stage=='equilibrium_iteration':history.append(event)
        cls.jacobian=intercept
        try:
            with iteration_geometry(events):
                try:correct(n,request['initial_state'],request['tolerance'],{},progress=progress)
                except CapturedTrial:pass
                else:raise AssertionError('Expected a dense fallback checkpoint, not an accepted solve.')
        finally:
            if owned:cls.jacobian=native
            else:del cls.jacobian
            assert cls.jacobian is native
    assert captured==[True]
    print(dict(status='CAPTURED_UNCONVERGED_TRIAL',residual=read(out/'capture/report.json')['full_residual']),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['prepare','launch'])
    p.add_argument('--output',type=Path,required=True);p.add_argument('--phase',choices=['capture','direct','stencil','probe','assess'])
    a=p.parse_args()
    if a.action=='prepare':prepare(a.output.resolve())
    else:
        base.capture=capture
        base.launch(a.output.resolve(),a.phase)
