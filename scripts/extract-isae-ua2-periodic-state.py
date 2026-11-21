"""Extract every measured state from one accepted periodic trajectory.

Full raw files remain untouched. This saved-only operation retains all sample
times and pins every input, while avoiding repeated large checkpoint reads in
subsequent independent discrete-equation experiments.
"""
import argparse
import gzip
from hashlib import sha256
import json
from pathlib import Path
import time

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'artifacts/isae/ua2-periodic-20261101/accepted-evidence'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--panels',type=int,choices=(20,40),required=True)
    parser.add_argument('--steps',type=int,choices=(80,160),required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();plan_path=args.output.with_suffix('.plan.json')
    if args.output.exists() or plan_path.exists():parser.error('Preserve extraction evidence; choose a fresh output path')
    args.output.parent.mkdir(parents=True,exist_ok=True)
    batch=json.loads((SOURCE/'batch-plan.json').read_text())
    for name,digest in batch['source_sha256'].items():
        assert sha256((ROOT/name).read_bytes()).hexdigest()==digest,name
        assert sha256((SOURCE/'frozen-code'/name).read_bytes()).hexdigest()==digest,name
    jobs=[j for j in batch['jobs'] if j['panels']==args.panels and j['steps']==args.steps]
    reference=json.loads((SOURCE/f'reference-n{args.panels}.json').read_text())
    grid=reference['grids'][str(args.steps)];del reference
    plan=dict(panels=args.panels,nominal_steps=args.steps,amplitude_ratio=.5,k=.95,cycles=8,
        jobs=jobs,batch_plan_sha256=sha256((SOURCE/'batch-plan.json').read_bytes()).hexdigest(),
        extractor_sha256=sha256(Path(__file__).read_bytes()).hexdigest(),source=str(SOURCE.relative_to(ROOT)),
        native_ASWING_comparison=False,original_artifacts_modified=False)
    plan_path.write_text(json.dumps(plan,indent=2)+'\n')
    rows=[];inputs={};last=None;started=time.monotonic()
    for job in jobs:
        folder=SOURCE/job['id'];p=folder/'trajectory.json.gz'
        receipt_path=SOURCE/(job['id']+'-execution.json');receipt=json.loads(receipt_path.read_text())
        report=json.loads((folder/'report.json').read_text());request=json.loads((folder/'plan.json').read_text())
        assert receipt['exit_code']==0 and receipt['report_sha256']==sha256((folder/'report.json').read_bytes()).hexdigest()
        assert report['converged'] and report['rejected_steps']==0 and report['source_unchanged']
        assert request['panels']==args.panels and request['steps']==args.steps and request['cycles']==8
        assert request['amplitude_ratio']==.5 and request['k']==.95
        condition=request['full_request']['condition']
        assert condition['alpha']==0 and condition['mach']==0 and condition['stall'] is False and condition['aero_lag'] is True
        for name in ('plan.json','report.json','trajectory.json.gz'):
            q=folder/name;inputs[str(q.relative_to(ROOT))]=sha256(q.read_bytes()).hexdigest()
        inputs[str(receipt_path.relative_to(ROOT))]=sha256(receipt_path.read_bytes()).hexdigest()
        with gzip.open(p,'rt') as stream:raw=json.load(stream)
        part=raw['snapshots'];assert len(part)==report['accepted_steps']+1
        assert report['accepted_steps']==request['end_index']-request['start_index']
        current=[]
        for sample in part:
            f=sample['frame'];assert max(abs(x) for x in f['rates_body']+f['attitude'])<1e-12
            assert sample['residual']<1e-10
            current.append(dict(time=sample['time'],order=sample['order'],residual=sample['residual'],
                velocity=f['velocity_origin_body'][2],position=f['position_earth'][2],acceleration=f['acceleration_reference_body'][2],
                force=sample['force'],CL=sample['force'][2]/(.5*1.225*100*10),
                circulation=[r['circulation'] for r in sample['strips']],circulation_rate=sample['circulation_rate']))
        if last is not None:
            for name in ('time','velocity','position','acceleration','force','circulation','circulation_rate'):
                assert current[0][name]==last[name],name
        rows.extend(current if last is None else current[1:]);last=current[-1]
    assert len(rows)==len(grid)==8*args.steps+41
    assert max(abs(r['time']-t) for r,t in zip(rows,grid))<1e-12
    assert all(r['order']==(1 if i==1 else 2) for i,r in enumerate(rows) if i>0)
    assert sha256(Path(__file__).read_bytes()).hexdigest()==plan['extractor_sha256']
    output=dict(plan=plan,rows=rows,unique_snapshots=len(rows),input_sha256=inputs,
        extraction_seconds=time.monotonic()-started,all_checkpoint_joins_exact=True,
        native_ASWING_comparison=False,original_artifacts_modified=False)
    args.output.write_text(json.dumps(output,indent=2,allow_nan=False)+'\n')
    print(json.dumps(dict(panels=args.panels,steps=args.steps,snapshots=len(rows),seconds=output['extraction_seconds'])),flush=True)


if __name__=='__main__':main()
