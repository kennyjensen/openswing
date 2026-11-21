"""One bounded continuation job for the pinned literal Flare20 PM2 model.

Keeps all source/settings and convergence gates. This does not score archived
histories or claim that a chosen mesh resolves the physical solution.
"""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--previous',type=Path,help='Result JSON from the preceding accepted job')
    parser.add_argument('--max-load-steps',type=int,default=2)
    parser.add_argument('--mesh-file',type=Path,
        help='Explicit JSON panel settings for a controlled mesh study; physics stays fixed')
    parser.add_argument('--kernel-root',type=Path,default=ROOT,
        help='Root containing the immutable openswing/ package used for this history')
    parser.add_argument('--output-dir',type=Path,required=True)
    args=parser.parse_args()
    kernel_root=args.kernel_root.resolve()
    assert (kernel_root/'openswing/__init__.py').is_file()
    sys.path.insert(0,str(kernel_root))
    baseline=ROOT/'artifacts/isae/ffwt4-startup-20261106/flare20-full-n8'
    original=json.loads((baseline/'plan.json').read_text())
    request=json.loads((baseline/'request.json').read_text())
    source=Path(original['source']['path']);driver=Path(original['driver']['path'])
    folder=args.output_dir.resolve();folder.mkdir(parents=True,exist_ok=False)
    def pin(path):
        path=Path(path).resolve();data=path.read_bytes()
        return dict(path=str(path),bytes=len(data),sha256=hashlib.sha256(data).hexdigest())
    def write(name,value):
        path=folder/name;temporary=path.with_suffix(path.suffix+'.tmp')
        temporary.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n');temporary.replace(path)
    assert pin(source)==original['source'] and pin(driver)==original['driver']
    assert request['source']==source.read_text()
    assert request['condition']['beta']==16. and request['panels']==8
    if args.mesh_file is not None:
        request['panels']=json.loads(args.mesh_file.read_text())
    previous=None if args.previous is None else json.loads(args.previous.read_text())
    if previous is not None:
        assert previous['continuation_status']=='pending' and not previous['converged']
    request['continuation']=dict(max_load_steps=args.max_load_steps,
        checkpoint=None if previous is None else deepcopy(previous['checkpoint']))
    plan=dict(source=pin(source),driver=pin(driver),helper=pin(__file__),
        request_baseline=pin(baseline/'request.json'),
        previous=None if args.previous is None else pin(args.previous),
        mesh_override=None if args.mesh_file is None else pin(args.mesh_file),
        kernel_root=str(kernel_root),
        kernel=[pin(p) for p in sorted((kernel_root/'openswing').glob('*.py'))],
        qualifications=original['qualifications'],native_values_added=0)
    if args.mesh_file is not None:
        plan['qualifications']=[q for q in plan['qualifications'] if not q.startswith('Cold equilibrium on a deliberately small cosine mesh')]
        plan['qualifications'].append('Only the panel settings differ from the original coarse preflight. A refined mesh is not an assertion of recovered historical node placement or spatial accuracy.')
    write('plan.json',plan);write('request.json',request)
    from openswing.bridge import dispatch
    from openswing.asw import parse_asw
    from openswing.aero import FlightCondition
    from openswing.source_airflow import SourceAirflowNetwork
    from openswing.equilibrium_state import restore,matching_identity,identity
    from openswing.hinge_history import joints
    import numpy as np
    started=time.monotonic()
    try:
        with (folder/'progress.jsonl').open('w') as stream:
            def progress(*event):
                stream.write(json.dumps(dict(seconds=time.monotonic()-started,event=event))+'\n');stream.flush()
            result=dispatch(request,progress=progress)
        write('result.json',result)
        model=parse_asw(request['source'],beam_interpolation=request['numerics']['beam_interpolation'])
        network=SourceAirflowNetwork(model,request['panels'],FlightCondition(**request['condition']),None,[],steady_trim=True)
        pending=result['continuation_status']=='pending'
        if pending:
            packet=result['checkpoint'];state=np.array(packet['coordinates'])
            assert matching_identity(identity(network),packet['context']['identity'])
            for joint,angle in zip(joints(network),packet['hinge_charts']):joint['angle_chart']=angle
            factor=packet['load_fraction'];steps=packet['accepted_load_steps']
            residual=float(np.max(abs(network.residual(state,factor))))
            assert residual<=1e-12 and packet['physical_residual']<=1e-12
            assert not result['converged'] and 'equilibrium_state' not in result
        else:
            assert result['converged'] and result['residual']<=1e-12
            state=restore(network,result['equilibrium_state'])
            residual=float(np.max(abs(network.residual(state))))
            assert residual<=request['tolerance']
            factor=1.;steps=result['continuation_steps']
        start_factor=0. if previous is None else previous['checkpoint']['load_fraction']
        start_steps=0 if previous is None else previous['checkpoint']['accepted_load_steps']
        logs=result['continuation_log']
        assert logs[0]['reached']==start_factor and factor>start_factor
        assert steps-start_steps==sum(bool(r['accepted']) for r in logs)
        assert 0<steps-start_steps<=args.max_load_steps
        for record in logs:
            if record['accepted']:
                assert record['residual']<=1e-12
                # Record the actual unchanged production guard, without
                # imposing a new load-to-load angle rule on accepted states.
        assert len(network.rigid_weight_attachments)==2 and model.dumps()==source.read_text()
        for item in plan['kernel']+[plan['source'],plan['driver'],plan['helper']]:assert pin(item['path'])==item
        if plan['mesh_override'] is not None:assert pin(plan['mesh_override']['path'])==plan['mesh_override']
        if plan['previous'] is not None:assert pin(plan['previous']['path'])==plan['previous']
        report=dict(status='ACCEPTED_CONTINUATION' if pending else 'COLD_EQUILIBRIUM_COMPUTED',
            seconds=time.monotonic()-started,from_load=start_factor,to_load=factor,
            accepted_steps=steps-start_steps,total_accepted_steps=steps,
            rebuilt_residual=residual,nodes=network.nn,elements=network.ne,unknowns=network.size,
            result=pin(folder/'result.json'),native_values_added=0)
        write('report.json',report);print(json.dumps(report),flush=True)
    except Exception as error:
        write('failure.json',dict(error=repr(error),seconds=time.monotonic()-started))
        raise


if __name__=='__main__':main()
