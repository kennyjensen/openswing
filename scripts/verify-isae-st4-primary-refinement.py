"""Finer meshes for explicitly identified ST-4 numerical discrepancies."""
from pathlib import Path
import argparse
import hashlib
import json
import sys
import time
import numpy as np
from isae_st4_primary import configurations, parameters, source, provenance

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from openswing.asw import parse_asw
from openswing.linear_dynamics import solve_modes


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    selections = [('7c', 34, 'lower'), ('7c', 34, 'upper'), ('7e', 48, 'upper'), ('unloaded', None, 'upper')]
    modules = {p.name:sha(p) for p in sorted((ROOT/'openswing').glob('*.py'))}
    pins = provenance(); pins[Path(__file__).name] = sha(__file__)
    destination = ROOT/'.reference/isae-st4-primary-refinement'; destination.mkdir(exist_ok=True)
    report = dict(status='RUNNING', modules=modules, scripts_and_inputs=pins, requested=4, runs=[],
        full_physical_validation=False, selection_reason={
            '7c_34_lower_and_upper':'N16 second-mode frequency error was below N32; check cancellation under further refinement.',
            '7e_48_upper':'Smallest N32 sixth-mode kinetic shape assurance in the interim study.',
            'unloaded_upper':'Largest N32 sixth-mode relative frequency error in the interim study.'})
    for variant, position, endpoint in selections:
        case = next(c for c in configurations() if (c['variant'],c['position_in'])==(variant,position))
        spec = dict(**case, icc_endpoint=endpoint, panels=64); text = source(spec); params = parameters(spec)
        identity = dict(specification=spec, count=16, modules=modules, scripts_and_inputs=pins,
                        source_sha256=hashlib.sha256(text.encode()).hexdigest())
        key = hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest(); path = destination/(key+'.json')
        if path.exists():
            saved = json.loads(path.read_text()); assert saved['identity']==identity
        else:
            start=time.perf_counter(); saved=dict(identity=identity,source=text,parameters=params)
            try:
                result=solve_modes(parse_asw(text),None,64,frame='fixed',count=16,shift=[-.1,0.],method='dense',
                                   gravity=[0.,0.,params['gravity']],matrices=True)
                matrices=result.pop('matrices'); matrix_path=destination/(key+'.npz')
                np.savez_compressed(matrix_path,A=matrices['A'],M=matrices['M'])
                saved.update(status='computed',result=result,matrices=dict(path=matrix_path.relative_to(ROOT).as_posix(),sha256=sha(matrix_path)))
            except (ValueError,RuntimeError) as exc:
                saved.update(status='rejected',error=type(exc).__name__+': '+str(exc))
            saved['seconds']=time.perf_counter()-start;path.write_text(json.dumps(saved,indent=2)+'\n')
        report['runs'].append(dict(specification=spec,cache=path.relative_to(ROOT).as_posix(),sha256=sha(path),status=saved['status'],seconds=saved['seconds']))
        args.output.write_text(json.dumps(report,indent=2)+'\n')
        print(len(report['runs']),spec,saved['status'],saved['seconds'],flush=True)
    report['status']='PRIMARY_TARGETED_REFINEMENT_COMPUTED_NOT_PHYSICALLY_VALIDATED'
    args.output.write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':
    main()
