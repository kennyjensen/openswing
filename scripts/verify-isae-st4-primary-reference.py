"""Independent hanging-beam convergence and explicit ambient-air sensitivity."""
from pathlib import Path
import argparse
import hashlib
import json
import time
import numpy as np
from isae_st4_primary import configurations,parameters,provenance,inputs
from isae_st4_loaded_reference import modes
from isae_st4_loaded_transfer import frequencies

ROOT=Path(__file__).resolve().parents[1]
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    sources=provenance()
    for name in ['verify-isae-st4-primary-reference.py','isae_st4_reference.py','isae_st4_loaded_reference.py','isae_st4_loaded_transfer.py']:sources[name]=sha(ROOT/'scripts'/name)
    physical,_=inputs();chord=physical['wing_primary']['chord_m'];dest=ROOT/'.reference/isae-st4-primary-reference';dest.mkdir(exist_ok=True)
    out=dict(status='RUNNING',scripts_and_inputs=sources,requested=672,runs=[],full_physical_validation=False,
        scope='Independent gravity-loaded energy and continuous beams. Density0 matches native vacuum studies; density1.225 is an explicitly assumed thin-strip added-mass diagnostic, not a recovered experimental density or an OpenSwing zero-speed aerodynamic solve.')
    for case in configurations():
        for endpoint in ['lower','upper']:
            spec=dict(**case,icc_endpoint=endpoint);params=parameters(spec)
            for rho in [0.,1.225]:
                air=dict(air_mass=np.pi*rho*chord**2/4,air_ip=np.pi*rho*chord**4/128,air_x=chord/2)
                for elements in [64,128,256,None]:
                    kind='energy' if elements else 'continuous';identity=dict(specification=spec,density=rho,kind=kind,elements=elements,parameters=dict(params,**air),sources=sources)
                    key=hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest();cache=dest/(key+'.json')
                    if cache.exists():run=json.loads(cache.read_text());assert run['identity']==identity
                    else:
                        start=time.perf_counter();result=modes(**params,**air,elements=elements) if elements else frequencies(**params,**air,estimates=seed)
                        run=dict(identity=identity,result=result,seconds=time.perf_counter()-start);cache.write_text(json.dumps(run,indent=2)+'\n')
                    if elements==256:seed=run['result']['frequencies_Hz']
                    out['runs'].append(dict(specification=spec,density=rho,kind=kind,elements=elements,cache=cache.relative_to(ROOT).as_posix(),sha256=sha(cache),seconds=run['seconds']))
                    a.output.write_text(json.dumps(out,indent=2)+'\n')
                    print(len(out['runs']),out['requested'],case['variant'],case['position_in'],endpoint,rho,kind,elements,f"{run['seconds']:.2f}s",flush=True)
    assert len(out['runs'])==out['requested'];out['status']='PRIMARY_INDEPENDENT_AND_AIR_SENSITIVITY_COMPUTED_NOT_PHYSICALLY_VALIDATED';a.output.write_text(json.dumps(out,indent=2)+'\n')


if __name__=='__main__':main()
