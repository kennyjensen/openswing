"""Reproduce the original positive-Nstep X restart at t=2 s.

One ordinary resume call requests BDF1 for the first new step; the next selects
BDF2 with that step's retained predecessor. Inputs and physical state are held.
The original continuous-history diagnostic remains a separate retained branch.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
spec=importlib.util.spec_from_file_location('ffwt2_original',ROOT/'scripts/verify-isae-ffwt2-time.py')
original=importlib.util.module_from_spec(spec);spec.loader.exec_module(original)
pin,write=original.pin,original.write


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--resume-from',required=True,type=Path)
    p.add_argument('--output-dir',required=True,type=Path)
    p.add_argument('--order',required=True,type=int,choices=(1,2))
    p.add_argument('--duration',required=True,type=float)
    a=p.parse_args();parent=a.resume_from.resolve();folder=a.output_dir.resolve()
    folder.mkdir(parents=True,exist_ok=False)
    plan=json.loads((parent/'plan.json').read_text())
    prior=json.loads((parent/'report.json').read_text())
    assert prior['status']=='SEGMENT_COMPUTED' and plan['continuation_version']==2
    for key in ('result','checkpoint'):assert pin(prior[key]['path'])==prior[key]
    saved=json.loads((parent/'checkpoint.json').read_text());start=saved['state']['time']
    if a.order==1:
        assert abs(start-2.)<1e-12 and a.duration==.01 and 'command_restarts' not in plan
        plan['command_restarts']=[2.]
    else:
        assert abs(start-2.01)<1e-12 and plan['command_restarts']==[2.]
        assert saved['accepted_method']['effective_order']==1
    plan.update(parent_checkpoint=pin(parent/'checkpoint.json'),duration=a.duration)
    producer=pin(__file__)
    request=dict(action='resume_time',source=Path(plan['source_pins'][0]['path']).read_text(),
        numerics=dict(beam_interpolation='drela-segspl-v1',structural_operator='drela-moving-airflow-v1'),
        checkpoint=saved,time=dict(duration=a.duration,order=a.order))
    for row in plan['source_pins']+plan['kernel_pins']+[plan['helper'],plan['preparation_helper']]:assert pin(row['path'])==row
    write(folder/'plan.json',plan);write(folder/'request.json',request)
    write(folder/'started.json',dict(wall_time=time.time(),segment_helper=producer))
    from openswing.bridge import dispatch
    from openswing.time_state import checkpoint
    began=time.monotonic()
    with (folder/'progress.jsonl').open('w') as stream:
        def progress(*event):
            stream.write(json.dumps(dict(seconds=time.monotonic()-began,event=event))+'\n');stream.flush()
        result=dispatch(request,progress=progress)
    assert result['converged'] and result['checkpoint_validation']['discrete_replayed']
    assert result['rejected_steps']==0
    assert all(s['converged'] and s['residual']<=1e-8 for s in result['snapshots'])
    for s in result['snapshots'][1:]:
        assert s['restart']['accepted_method']['effective_order']==a.order
    write(folder/'result.json',result);write(folder/'checkpoint.json',checkpoint(result,-1))
    for row in plan['source_pins']+plan['kernel_pins']+[plan['helper'],plan['preparation_helper'],producer]:assert pin(row['path'])==row
    report=dict(status='SEGMENT_COMPUTED',seconds=time.monotonic()-began,
        times=[s['time'] for s in result['snapshots']],snapshots=len(result['snapshots']),
        result=pin(folder/'result.json'),checkpoint=pin(folder/'checkpoint.json'),
        checkpoint_validation=result['checkpoint_validation'],segment_helper=producer,
        native_comparisons_assessed=False,full_family_validated=False)
    write(folder/'report.json',report);print(json.dumps(report),flush=True)


if __name__=='__main__':main()
