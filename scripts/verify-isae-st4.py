"""Literal ST-4 vacuum modes with mesh refinement and retained failed states."""
from pathlib import Path
import argparse
import hashlib
import json
import sys
import time
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
FOLDER='3 - Structure/CASE - ST4 Concentrated weight'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    p=argparse.ArgumentParser();p.add_argument('--kernel',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();sys.path.insert(0,str(a.kernel.resolve()))
    from openswing.asw import parse_asw
    from openswing.linear_dynamics import solve_modes
    from openswing.geometry import geometry_summary
    manifest=json.loads((ROOT/'.reference/isae-validation/manifest.json').read_text());cache=ROOT/'.reference/isae-validation'/manifest['revision']
    pins={p.name:sha(p) for p in sorted((a.kernel/'openswing').glob('*.py'))}
    inputs=[];groups={}
    for name,pin in manifest['files'].items():
        if not (name.startswith(FOLDER+'/') and name.endswith('.asw')):continue
        path=cache/name;assert sha(path)==pin['sha256'];source=path.read_text();row=dict(path=name,sha256=pin['sha256'])
        try:
            model=parse_asw(source);assert model.dumps()==source;geometry_summary(model,8)
            row.update(status='parsed_and_constructed',reference=model.reference.tolist())
            groups.setdefault(pin['sha256'],dict(source=source,paths=[]))['paths'].append(name)
        except (ValueError,RuntimeError) as exc:row.update(status='rejected',error=type(exc).__name__+': '+str(exc))
        inputs.append(row)
    dest=ROOT/'.reference/isae-st4-native';dest.mkdir(exist_ok=True)
    result=dict(status='RUNNING',revision=manifest['revision'],modules=pins,script_sha256=sha(__file__),
                inputs=inputs,unique_models=len(groups),runs=[],requested=3*len(groups),full_physical_validation=False,
                scope='Literal models; zero airflow and gravity=0, fixed frame. This matches the unloaded vacuum comparison only; it is not a gravity-loaded, still-air-added-mass or flutter validation.')
    for digest,entry in groups.items():
        for panels in [8,16,32]:
            spec=dict(source_sha256=digest,panels=panels,gravity=[0.,0.,0.],count=12,shift=[-.1,0.],method='dense')
            identity=dict(specification=spec,modules=pins,script_sha256=sha(__file__))
            key=hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest();path=dest/(key+'.json')
            if path.exists():
                run=json.loads(path.read_text());assert run['identity']==identity
            else:
                start=time.perf_counter();run=dict(identity=identity,source=entry['source'],paths=entry['paths'])
                try:
                    modes=solve_modes(parse_asw(entry['source']),None,panels,frame='fixed',count=12,shift=[-.1,0.],
                                      method='dense',gravity=[0.,0.,0.],matrices=True)
                    pencil=dest/(key+'.npz');arrays=modes.pop('matrices');np.savez_compressed(pencil,A=arrays['A'],M=arrays['M'])
                    run.update(status='computed',result=modes,matrices=dict(path=pencil.relative_to(ROOT).as_posix(),sha256=sha(pencil)))
                except (ValueError,RuntimeError) as exc:run.update(status='rejected',error=type(exc).__name__+': '+str(exc))
                run['seconds']=time.perf_counter()-start;path.write_text(json.dumps(run,indent=2)+'\n')
            result['runs'].append(dict(specification=spec,paths=entry['paths'],cache=path.relative_to(ROOT).as_posix(),sha256=sha(path),status=run['status'],seconds=run['seconds']))
            a.output.write_text(json.dumps(result,indent=2)+'\n')
            print(len(result['runs']),result['requested'],entry['paths'][0].split('/')[-1],panels,run['status'],f"{run['seconds']:.2f}s",flush=True)
    result['status']='COMPARISONS_COMPUTED_NOT_PHYSICALLY_VALIDATED'
    a.output.write_text(json.dumps(result,indent=2)+'\n')


if __name__=='__main__':main()
