"""Saved-only audit of the AE-2 bounded cold-continuation diagnostics."""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import resource
import signal
import sys


def read(p):return json.loads(Path(p).read_text())
def pin(p):
    p=Path(p).resolve()
    return dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest())


def assess(out):
    root=Path(__file__).resolve().parents[1];plan=read(out/'plan.json')
    assert all(pin(p['path'])==p for p in plan['pins'])
    archive=read(root/'artifacts/isae/ae2-beta5-sweeps-current-20261110/plan.json')
    jobs={j['id']:j for j in archive['jobs']}
    cases=[];files=[pin(out/'plan.json')];terminals=[];checks=0
    for case in plan['cases']:
        folder=out/'cases'/case['name'];previous=None;records=[];iterations=[];loads=[];final=None
        for index,stage in enumerate(sorted(folder.glob('[0-9][0-9]'))):
            assert stage.name==f'{index:02d}'
            terminal=read(stage/'terminal.json');assert terminal['process_reaped']
            terminals.append(terminal);request=read(stage/'request.json')
            expected=deepcopy(read(case['request']));expected['continuation']=dict(max_load_steps=1)
            if previous is not None:
                assert previous['continuation_status']=='pending'
                expected['continuation']['checkpoint']=previous['checkpoint']
            assert request==expected
            files += [pin(p) for p in sorted(stage.iterdir()) if p.is_file()]
            if terminal['returncode']:
                records.append(dict(index=index,status='failed',terminal=terminal))
                continue
            result=read(stage/'result.json');report=read(stage/'report.json')
            iterations += result['iteration_log'];loads += result['continuation_log']
            if result['continuation_status']=='pending':
                assert report['status']=='pending' and report['accepted'] is False
                c=result['checkpoint'];assert c['physical_residual']<=1e-12
                assert c['accepted_load_steps']==index+1
                assert c['context']['solver']['continuation_steps']==4
                assert c['context']['solver']['physical_residual_target']==1e-12
                assert c['context']['solver']['reuse_matrices'] is True
                assert c['context']['solver']['full_structure'] is True
                previous=result
            else:
                assert result['continuation_status']=='complete' and report['status']=='computed'
                assert result['converged'] and result['residual']<=1e-12
                assert all(c['passed'] is True for c in report['checks'])
                assert report['fresh_residual']<=1e-8
                checks+=len(report['checks']);final=report
                if 'control_result' in case:
                    assert report['parity']['maximum_coordinate_difference']==0
                    assert all(v==0 for v in report['parity']['values'].values())
            records.append(dict(index=index,status=report['status'],terminal=terminal))
        comparisons=[]
        if final:
            for obs in jobs[case['job']]['observations']:
                x=final['values'][obs['name']];y=obs['expected'];e=abs(x-y)
                allowance=max(obs['tolerance'],.05*abs(y)) if abs(y)>1e-8 else obs['tolerance']
                comparisons.append(dict(name=obs['name'],predicted=x,expected=y,
                    error_percent=100*e/abs(y) if y else None,passed=e<=allowance))
        cases.append(dict(name=case['name'],job=case['job'],status='computed' if final else 'incomplete',
            stages=records,iterations=len(iterations),damped_iterations=sum(i.get('alpha',1)<1 for i in iterations),
            reused_iterations=sum(i['matrix_reused'] for i in iterations),
            full_fallback_iterations=sum(bool(i.get('exact_fallback')) for i in iterations),
            matrix_residual_evaluations=sum(i.get('evaluations',0) for i in iterations),
            load_attempts=loads,final=final,native_comparisons=comparisons,primary_votes_added=0))
    assert not any(n=='openswing' or n.startswith('openswing.') for n in sys.modules)
    report=dict(observed_utc=datetime.now(timezone.utc).isoformat(),status='SAVED_AUDIT_PASS',
        cases=cases,verified_sources=plan['pins'],verified_results=files,assessor=pin(__file__),
        physical_calls=0,production_imports=0,primary_votes_added=0,primary_native_count=dict(passed=548,required=2200),
        physical_checks_passed=checks,terminal_stages=len(terminals),
        stages_exited_zero=sum(t['returncode']==0 for t in terminals),
        maximum_cpu_seconds=max(t['cpu_seconds'] for t in terminals),
        maximum_rss_kib=max(t['peak_rss_kib'] for t in terminals),
        maximum_wall_seconds=max(t['wall_seconds'] for t in terminals),
        maximum_fresh_residual=max(c['final']['fresh_residual'] for c in cases if c['final']),
        limitations=['Diagnostic execution partition, not extra primary votes or a speedup claim.',
            'Original failed suite attempts and the whole-control timeout remain unchanged.',
            'No conclusion about original ASWING convergence, uniqueness or dynamic stability.'])
    target=out/'assessment.json';assert not target.exists()
    target.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print(json.dumps({k:report[k] for k in ['status','physical_checks_passed','terminal_stages','stages_exited_zero','maximum_cpu_seconds','maximum_rss_kib','maximum_fresh_residual']},indent=2))
    for c in cases:print(json.dumps({k:c[k] for k in ['name','status','iterations','damped_iterations','reused_iterations','full_fallback_iterations','native_comparisons']}))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    resource.setrlimit(resource.RLIMIT_AS,(512*1024**2,)*2);resource.setrlimit(resource.RLIMIT_CPU,(15,)*2);signal.alarm(25)
    assess(a.output.resolve())
