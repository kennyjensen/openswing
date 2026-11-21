"""Audit continuation boundaries, explicitly retaining completed-output timeouts.

A process timeout never becomes a successful exit. With explicit opt-in, a
complete immutable output boundary may undergo every normal fresh physical
and chain check; only that independent audit can authorize its continuation.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]


def completed_output(folder, allow_completed_timeouts=False):
    """Validate the saved-output envelope; this is not a physical certificate."""
    folder=Path(folder).resolve()
    execution=json.loads((folder/'execution.json').read_text())
    code=execution['exit_code']
    assert code==0 or (allow_completed_timeouts and code==124), 'Unaccepted process exit'
    assert not (folder/'failure.json').exists(), 'Helper reported failure'
    report=json.loads((folder/'report.json').read_text())
    result_path=folder/'result.json';data=result_path.read_bytes();result=json.loads(data)
    recorded=report['result']
    assert Path(recorded['path'])==result_path and recorded['bytes']==len(data)
    assert recorded['sha256']==hashlib.sha256(data).hexdigest(), 'Changed saved result'
    expected={'pending':'ACCEPTED_CONTINUATION','complete':'COLD_EQUILIBRIUM_COMPUTED'}
    assert report['status']==expected[result['continuation_status']], 'Incomplete helper report'
    assert math.isfinite(report['seconds']) and report['seconds']>0
    assert isinstance(report['accepted_steps'],int) and report['accepted_steps']>0
    assert math.isfinite(report['rebuilt_residual']) and report['rebuilt_residual']<=1e-12
    return execution,report,result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--study',type=Path,default=ROOT/'artifacts/isae/ffwt4-continuation-20261106')
    p.add_argument('--kernel-root',type=Path,default=ROOT/'.reference/solver-snapshots/ffwt4-continuation-20261106')
    p.add_argument('--mesh-file',type=Path)
    p.add_argument('--helper-copy',type=Path)
    p.add_argument('--allow-completed-timeouts',action='store_true',
        help='Revalidate complete saved boundaries from exit 124; retain failed process accounting')
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();study=args.study.resolve()
    kernel=args.kernel_root.resolve()
    sys.path.insert(0,str(kernel))
    from openswing.asw import parse_asw
    from openswing.aero import FlightCondition
    from openswing.source_airflow import SourceAirflowNetwork
    from openswing.steady_continuation import restore,context
    from openswing.hinge_history import joints,current
    from openswing.equilibrium_state import restore as restore_equilibrium
    import numpy as np
    def read(path):return json.loads(Path(path).read_text())
    def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    def check_pin(item,path=None):
        path=Path(item['path'] if path is None else path)
        assert path.stat().st_size==item['bytes'] and sha(path)==item['sha256'],path
    baseline=read(ROOT/'artifacts/isae/ffwt4-startup-20261106/flare20-full-n8/request.json')
    expected_request=dict(baseline)
    if args.mesh_file is not None:expected_request['panels']=read(args.mesh_file)
    helper_copy=args.helper_copy if args.helper_copy is not None else study/'helper-at-execution.py'
    rows=[];previous=None;factor=0.;steps=0;rejections=0;complete=False;load_targets=[]
    for folder in sorted(study.glob('job-*')):
        if not folder.is_dir():continue
        assert not complete,'Unexpected computation after complete equilibrium'
        execution,report,result=completed_output(folder,args.allow_completed_timeouts)
        plan=read(folder/'plan.json');request=read(folder/'request.json')
        assert {k:v for k,v in request.items() if k!='continuation'}==expected_request
        assert Path(plan['kernel_root'])==kernel
        if args.mesh_file is not None:
            assert Path(plan['mesh_override']['path'])==args.mesh_file.resolve()
            check_pin(plan['mesh_override'])
        for item in plan['kernel']+[plan['source'],plan['driver'],plan['request_baseline']]:check_pin(item)
        check_pin(plan['helper'],helper_copy);check_pin(report['result'])
        if previous is None:
            assert plan['previous'] is None and request['continuation']['checkpoint'] is None
        else:
            assert Path(plan['previous']['path'])==previous/'result.json'
            check_pin(plan['previous'])
            assert request['continuation']['checkpoint']==read(previous/'result.json')['checkpoint']
        log=result['continuation_log'];assert log[0]['reached']==factor
        for entry in log:
            assert entry['reached']==factor
            load_targets.append(entry['target'])
            if entry['accepted']:
                assert entry['residual']<=1e-12
                factor=entry['target'];steps+=1
            else:
                rejections+=1;assert entry['rejected_attempts']==rejections
        rotations=[r['accepted_rotation_increment_rad'] for r in result['iteration_log']
                   if 'accepted_rotation_increment_rad' in r]
        assert max(rotations,default=0.)<=np.deg2rad(5)*(1+1e-12)
        model=parse_asw(request['source'],beam_interpolation=request['numerics']['beam_interpolation'])
        net=SourceAirflowNetwork(model,request['panels'],FlightCondition(**request['condition']),None,[],steady_trim=True)
        if result['continuation_status']=='pending':
            packet=result['checkpoint'];ctx=context(net,request['tolerance'],request['continuation_steps'],True,True)
            state,loaded,increment,count,rejected,centers,_=restore(net,packet,ctx)
            assert (loaded,count,rejected)==(factor,steps,rejections)
            assert not result['converged'] and 'equilibrium_state' not in result
            for joint,angle in zip(joints(net),centers):joint['angle_chart']=angle
            residual=float(np.max(abs(net.residual(state,factor))))
            assert residual<=1e-12
        else:
            assert result['continuation_status']=='complete' and result['converged']
            assert result['residual']<=1e-12 and result['continuation_steps']==steps and factor>=1-1e-12
            state=restore_equilibrium(net,result['equilibrium_state'])
            residual=float(np.max(abs(net.residual(state))))
            assert residual<=request['tolerance'];complete=True
        assert model.dumps()==request['source'] and len(net.rigid_weight_attachments)==2
        assert report['to_load']==factor and report['total_accepted_steps']==steps
        assert report['rebuilt_residual']==residual
        assert report['nodes']==net.nn and report['elements']==net.ne and report['unknowns']==net.size
        assert report['accepted_steps']==sum(bool(entry['accepted']) for entry in log)
        assert report['from_load']==log[0]['reached']
        rows.append(dict(job=folder.name,seconds=report['seconds'],load_fraction=factor,
            process_exit_code=execution['exit_code'],
            boundary_revalidated_after_timeout=execution['exit_code']==124,
            accepted_steps=steps,rejected_attempts=rejections,rebuilt_residual=residual,
            nodes=net.nn,unknowns=net.size,
            hinge_angles_deg=np.rad2deg(current(net)).tolist(),result_sha256=sha(folder/'result.json')))
        previous=folder
    assert rows
    earlier=[json.loads(s)['event'][1] for s in (ROOT/'artifacts/isae/ffwt4-startup-20261106/flare20-full-n8/progress.jsonl').read_text().splitlines()
             if json.loads(s)['event'][0]=='static_load' and json.loads(s)['event'][1]>0]
    compared=min(len(earlier),len(load_targets)) if expected_request['panels']==baseline['panels'] else 0
    prefix_equal=load_targets[:compared]==earlier[:compared] if compared else None
    summary=dict(status='COMPLETE_COLD_EQUILIBRIUM' if complete else 'VERIFIED_PARTIAL_CONTINUATION',
        jobs=rows,accepted_load_steps=steps,rejected_load_attempts=rejections,
        final_load_fraction=factor,complete=complete,total_job_seconds=sum(r['seconds'] for r in rows),
        original_uninterrupted_targets_compared=compared,original_targets_identical=prefix_equal,
        kernel_root=str(kernel),native_values_added=0,
        process_timeouts=sum(r['process_exit_code']==124 for r in rows),
        successful_processes=sum(r['process_exit_code']==0 for r in rows),
        timeout_policy='Complete saved output only, independently rebuilt and chain-checked; exit 124 remains a process timeout.',
        assessor_sha256=sha(__file__),
        mesh=expected_request['panels'],
        qualification='Controlled Flare20 equilibrium with source-preserving qualified pylons; not driver-mesh convergence, a gust history or a native ASWING pass.')
    assert not args.output.exists(),'Preserve prior assessments; use a new output path.'
    args.output.write_text(json.dumps(summary,indent=2,allow_nan=False)+'\n')
    print(json.dumps({k:v for k,v in summary.items() if k!='jobs'}))


if __name__=='__main__':main()
