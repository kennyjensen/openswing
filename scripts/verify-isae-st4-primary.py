"""Native hanging-wing spectra for every primary weight-7 test configuration."""
from pathlib import Path
import argparse
import hashlib
import json
import sys
import time
import numpy as np
from isae_st4_primary import configurations,parameters,source,provenance

ROOT=Path(__file__).resolve().parents[1]
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    p=argparse.ArgumentParser();p.add_argument('--kernel',type=Path,default=ROOT);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--endpoint',choices=['lower','upper','both'],default='both');a=p.parse_args();sys.path.insert(0,str(a.kernel.resolve()))
    from openswing.asw import parse_asw
    from openswing.geometry import model_meshes
    from openswing.inertia import InertiaModel
    from openswing.linear_dynamics import solve_modes
    pins={p.name:sha(p) for p in sorted((a.kernel/'openswing').glob('*.py'))};sources=provenance();sources[Path(__file__).name]=sha(__file__)
    specs=[dict(**case,icc_endpoint=endpoint,panels=panels) for case in configurations()
           for endpoint in (['lower','upper'] if a.endpoint=='both' else [a.endpoint]) for panels in [8,16,32]]
    dest=ROOT/'.reference/isae-st4-primary-native';dest.mkdir(exist_ok=True)
    out=dict(status='RUNNING',modules=pins,scripts_and_inputs=sources,requested=len(specs),runs=[],full_physical_validation=False,
        scope='All 42 primary configurations, hanging gravity +z, no aerodynamic mass. Two non-fitted sectional rotary-inertia endpoints; equivalent chordwise point pairs. Exact experimental model remains underdetermined.')
    for spec in specs:
        text=source(spec);params=parameters(spec);model=parse_asw(text);assert model.dumps()==text and model.beams[0].domain==(1.,1.+params['length'])
        meshes=model_meshes(model,8);inertia=InertiaModel(model,meshes)
        mass=inertia.summary(inertia.elements(meshes))['mass']
        np.testing.assert_allclose(mass,params['mass']*params['length']+sum(row[0] for row in params['points']),rtol=1e-13,atol=1e-13)
        identity=dict(specification=spec,source_sha256=hashlib.sha256(text.encode()).hexdigest(),modules=pins,scripts_and_inputs=sources)
        key=hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest();cache=dest/(key+'.json')
        if cache.exists():run=json.loads(cache.read_text());assert run['identity']==identity
        else:
            start=time.perf_counter();run=dict(identity=identity,source=text,parameters=params)
            try:
                result=solve_modes(model,None,spec['panels'],frame='fixed',count=12,shift=[-.1,0.],method='dense',gravity=[0.,0.,params['gravity']],matrices=True)
                arrays=result.pop('matrices');path=dest/(key+'.npz');np.savez_compressed(path,A=arrays['A'],M=arrays['M'])
                run.update(status='computed',result=result,matrices=dict(path=path.relative_to(ROOT).as_posix(),sha256=sha(path)))
            except (ValueError,RuntimeError) as exc:run.update(status='rejected',error=type(exc).__name__+': '+str(exc))
            run['seconds']=time.perf_counter()-start;cache.write_text(json.dumps(run,indent=2)+'\n')
        out['runs'].append(dict(specification=spec,cache=cache.relative_to(ROOT).as_posix(),sha256=sha(cache),status=run['status'],seconds=run['seconds']))
        a.output.write_text(json.dumps(out,indent=2)+'\n')
        print(len(out['runs']),out['requested'],spec,run['status'],f"{run['seconds']:.2f}s",flush=True)
    out['status']='PRIMARY_CONDITIONAL_MODAL_COMPARISONS_COMPUTED_NOT_PHYSICALLY_VALIDATED';a.output.write_text(json.dumps(out,indent=2)+'\n')


if __name__=='__main__':main()
