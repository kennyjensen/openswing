"""Capture and diagnose the AE-2 beta2.75 dense-fallback trial, never accept it.

All numerical work uses the existing full physical residual. The replay stops
before allocating the failed dense fallback; separate jobs compare complete
geometry and original stencil tangents and their full-system Newton directions.
"""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import resource
import signal
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.probe_isae_ae2_cold_trace import read, write, pin, THREADS
from scripts.probe_isae_ae2_incidence_stages import checked, preload, LIMITS, stage_receipt
from scripts.probe_isae_ae2_incidence_iteration import iteration_geometry


def prepare(out):
    assert not out.exists()
    parent = ROOT/'artifacts/isae/ae2-incidence-refined-20261110'
    old = checked(parent); failed = parent/'beta0275'
    stage_receipt(parent, 'beta0250', 'verify')
    assert read(failed/'solve/terminal.json')['process_reaped']
    assert read(failed/'solve/terminal.json')['returncode'] == 1
    assert not (failed/'result.json').exists()
    request = read(failed/'request.json')
    assert request['initial_state'] == read(parent/'beta0250/result.json')['equilibrium_state']
    assert request['condition']['beta'] == 2.75 and request['condition']['speed'] == 17.
    paths = [Path(p['path']) for p in old['pins']]
    paths += [Path(__file__), parent/'plan.json', parent/'beta0250/result.json', parent/'beta0250/report.json',
        parent/'beta0250/verify/terminal.json', parent/'beta0250/verify/sources-verified.json',
        failed/'request.json', failed/'solve/terminal.json', failed/'solve/progress.jsonl', failed/'solve/stderr.log']
    for ref in read(ROOT/'docs/validation/aswing-authoritative-sources.json')['files']:
        if ref['id'] in ('isae-part-4','drela-steady'):
            for kind, digest in (('pdf','sha256'),('text','text_sha256')):
                p=ROOT/ref['local_'+kind]; assert pin(p)['sha256']==ref[digest];paths.append(p)
    write(out/'request.json', request); paths.append(out/'request.json')
    write(out/'plan.json', dict(observed_utc=datetime.now(timezone.utc).isoformat(), method=__doc__,
        pins=[pin(p) for p in sorted(set(paths))], limits=LIMITS,
        original_progress=str(failed/'solve/progress.jsonl'), phases=['capture','direct','stencil','probe','assess'],
        maximum_scaled_column_difference=2e-5, maximum_relative_direction_difference=1e-4,
        trial_powers=list(range(13)), primary_votes_added=0,
        qualifications=['Captured trial is not converged, not a seed and not a reference pass.',
            'Replay must reproduce the original iteration residual history before stopping.',
            'Beam elimination solves every row of each complete matrix; no small-entry dropping.',
            'Powers 0–8 reproduce the existing line-search range; 9–12 are separately disclosed diagnostic probes.']))
    print('Prepared failed-trial capture and comparison; no numerical job started.',flush=True)


def receipt(out, phase):
    folder=out/phase; r=read(folder/'terminal.json'); s=read(folder/'sources-verified.json')
    assert r['returncode']==0 and r['process_reaped'] and not r['supervisor_timeout']
    assert s['all_pins_checked_before_and_after'] and s['plan']==pin(out/'plan.json')
    assert s['terminal']==pin(folder/'terminal.json')
    return r


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
            assert a['current']==b['current'] and abs(a['total']-b['total'])<=1e-12*(1+abs(b['total']))
        residual,data=n.residual(x,detail=True); error=float(np.max(abs(residual)))
        assert abs(error-old[-1]['total'])<=1e-12 and error>request['tolerance']
        np.savez_compressed(out/'capture/trial.npz',x=x,residual=residual)
        write(out/'capture/state.json',packet(n,x,residual=error,include_launch=False))
        fields=network_snapshot(n,residual,data); assert not fields['converged']
        write(out/'capture/fields.json',plain(fields))
        write(out/'capture/report.json',plain(dict(status='CAPTURED_UNCONVERGED_TRIAL',accepted=False,
            history=history,original_history=old,full_residual=error,tangent_calls=events,
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


def trial(out):
    import numpy as np
    from scripts.probe_isae_ae2_staged_inverse import network
    from openswing.equilibrium_state import restore
    receipt(out,'capture'); report=read(out/'capture/report.json')
    assert report['status']=='CAPTURED_UNCONVERGED_TRIAL' and report['accepted'] is False
    assert all(pin(p['path'])==p for p in report['pins'])
    n=network(read(out/'request.json')); restored=restore(n,read(out/'capture/state.json'))
    with np.load(out/'capture/trial.npz') as data:x=data['x'].copy();r=data['residual'].copy()
    np.testing.assert_allclose(restored,x,rtol=1e-14,atol=2e-15)
    fresh=n.residual(x);np.testing.assert_allclose(fresh,r,rtol=1e-8,atol=1e-12)
    assert np.max(abs(fresh))>1e-12
    return n,x,r


def matrix(out,plan,method):
    import numpy as np
    from scipy.sparse import save_npz
    from openswing.newton_structure import NewtonBeamFactor
    from openswing.steady_continuation import plain
    n,x,r=trial(out);calls=n.nfev;cpu=time.process_time();before=time.monotonic()
    jac=n.jacobian(x,1.,_sparse=True,_direct_geometry=method=='direct')
    timing=dict(cpu_seconds=time.process_time()-cpu,wall_seconds=time.monotonic()-before,residual_calls=n.nfev-calls)
    factor=NewtonBeamFactor(n,jac);direction=factor.solve(-r)
    defect=float(np.max(abs(jac@direction+r)));assert defect<=1e-10*max(1.,np.max(abs(r)))
    save_npz(out/method/'matrix.npz',jac)
    np.savez_compressed(out/method/'direction.npz',direction=direction)
    write(out/method/'report.json',plain(dict(status='COMPLETE',method=method,timing=timing,
        linear_defect=defect,geometry=getattr(n,'geometry_derivative_diagnostics',None),factor=factor.report,
        trial=pin(out/'capture/trial.npz'),capture=pin(out/'capture/report.json'),request=pin(out/'request.json'),
        matrix=pin(out/method/'matrix.npz'),direction=pin(out/method/'direction.npz'),primary_votes_added=0)))
    print(dict(method=method,**timing,linear_defect=defect),flush=True)


def probe(out,plan):
    import numpy as np
    from openswing.aero import AnalysisError
    n,x,r=trial(out);error=float(np.max(abs(r))); rows=[]
    for method in ('direct','stencil'):
        receipt(out,method);rep=read(out/method/'report.json')
        assert all(pin(rep[k]['path'])==rep[k] for k in ('matrix','direction','trial','capture','request'))
        with np.load(out/method/'direction.npz') as data:direction=data['direction'].copy()
        for power in plan['trial_powers']:
            scale=2.**-power;row=dict(method=method,power=power,scale=scale,original_search=power<=8)
            try:
                value=n.residual(x+scale*direction);norm=float(np.max(abs(value)))
                row.update(error=norm,ratio=norm/error,accepted_by_merit=bool(norm<error*(1-1e-4*scale) or norm<=1e-12),
                    controlling_row=int(np.argmax(abs(value))))
            except (AnalysisError,ValueError,FloatingPointError) as exc:
                row.update(error=None,accepted_by_merit=False,exception_type=type(exc).__name__,exception=str(exc))
            rows.append(row)
    write(out/'probe/report.json',dict(status='COMPLETE',baseline_error=error,trials=rows,primary_votes_added=0,
        pins=[pin(out/p/'report.json') for p in ('capture','direct','stencil')]))
    print(dict(accepted=[(r['method'],r['power']) for r in rows if r['accepted_by_merit']]),flush=True)


def assess(out,plan):
    import numpy as np
    from scipy.sparse import load_npz
    for phase in ('capture','direct','stencil','probe'):receipt(out,phase)
    reports={m:read(out/m/'report.json') for m in ('direct','stencil')}
    matrices={};directions={}
    for m,rep in reports.items():
        assert all(pin(rep[k]['path'])==rep[k] for k in ('matrix','direction','trial','capture','request'))
        matrices[m]=load_npz(out/m/'matrix.npz')
        with np.load(out/m/'direction.npz') as data:directions[m]=data['direction'].copy()
    assert matrices['direct'].shape==matrices['stencil'].shape==(2105,2105)
    scaled=0.;difference_squared=reference_squared=0.
    for first in range(0,2105,128):
        a=matrices['direct'][:,first:first+128].toarray();b=matrices['stencil'][:,first:first+128].toarray()
        delta=a-b;scaled=max(scaled,float(np.max(abs(delta)/(1+abs(b)))))
        difference_squared+=float(np.sum(delta*delta));reference_squared+=float(np.sum(b*b))
    relative=float(np.sqrt(difference_squared/reference_squared))
    direction=float(np.linalg.norm(directions['direct']-directions['stencil'])/np.linalg.norm(directions['stencil']))
    gate=scaled<=plan['maximum_scaled_column_difference'] and direction<=plan['maximum_relative_direction_difference']
    probe_report=read(out/'probe/report.json')
    assert all(pin(p['path'])==p for p in probe_report['pins'])
    write(out/'assessment.json',dict(status='TANGENTS_AGREE' if gate else 'TANGENTS_DIFFER',
        comparison_gates_passed=gate,maximum_scaled_column_difference=scaled,relative_matrix_difference=relative,
        relative_direction_difference=direction,reports=reports,probe=probe_report,
        primary_votes_added=0,accepted_state=False,pins=[pin(out/p/'report.json') for p in ('capture','direct','stencil','probe')]))
    print(dict(status='TANGENTS_AGREE' if gate else 'TANGENTS_DIFFER',scaled=scaled,relative=relative,direction=direction),flush=True)


def launch(out,phase):
    assert all(os.environ.get(k)==v for k,v in THREADS.items())
    resource.setrlimit(resource.RLIMIT_AS,(LIMITS['address_space_bytes'],)*2)
    plan=checked(out);assert phase in plan['phases'];folder=out/phase;folder.mkdir(exist_ok=False)
    start=time.monotonic();preload();loading=time.monotonic()-start
    write(folder/'started.json',dict(observed_utc=datetime.now(timezone.utc).isoformat(),phase=phase,library_preload_seconds=loading))
    sys.stdout.flush();sys.stderr.flush();before=time.monotonic();pid=os.fork()
    if pid==0:
        code=0
        try:
            os.setsid();resource.setrlimit(resource.RLIMIT_CPU,(LIMITS['cpu_seconds'],)*2)
            signal.alarm(LIMITS['wall_seconds']+2)
            with (folder/'stdout.log').open('x') as stdout,(folder/'stderr.log').open('x') as stderr:
                os.dup2(stdout.fileno(),1);os.dup2(stderr.fileno(),2)
                try:
                    if phase in ('direct','stencil'):matrix(out,plan,phase)
                    else:globals()[phase](out,plan)
                except BaseException:traceback.print_exc();code=1
                sys.stdout.flush();sys.stderr.flush()
        except BaseException:traceback.print_exc();sys.stderr.flush();code=1
        finally:os._exit(code)
    reaped=0;timeout=False
    try:
        while not reaped:
            reaped,status,usage=os.wait4(pid,os.WNOHANG)
            if reaped:break
            if time.monotonic()-before>LIMITS['wall_seconds']:
                timeout=True;os.kill(pid,signal.SIGKILL);reaped,status,usage=os.wait4(pid,0);break
            time.sleep(.05)
    finally:
        if not reaped:os.kill(pid,signal.SIGKILL);reaped,status,usage=os.wait4(pid,0)
    terminal=dict(returncode=os.waitstatus_to_exitcode(status),supervisor_timeout=timeout,process_reaped=True,
        wall_seconds=time.monotonic()-before,cpu_seconds=usage.ru_utime+usage.ru_stime,peak_rss_kib=usage.ru_maxrss,
        finished_utc=datetime.now(timezone.utc).isoformat())
    write(folder/'terminal.json',terminal);checked(out)
    write(folder/'sources-verified.json',dict(all_pins_checked_before_and_after=True,
        plan=pin(out/'plan.json'),terminal=pin(folder/'terminal.json')))
    print(json.dumps(dict(phase=phase,**terminal)),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['prepare','launch'])
    p.add_argument('--output',type=Path,required=True);p.add_argument('--phase',choices=['capture','direct','stencil','probe','assess'])
    a=p.parse_args()
    if a.action=='prepare':prepare(a.output.resolve())
    else:launch(a.output.resolve(),a.phase)
