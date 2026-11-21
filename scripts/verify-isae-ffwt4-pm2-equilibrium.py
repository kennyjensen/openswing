"""One small, cold PM2 equilibrium using literal sources and tagged pylons.

This is a compatibility/solver preflight, not a mesh-converged native score.
Run one flare per bounded process; retain failures and the original requests.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--flare',type=int,choices=(10,20,30),required=True)
    parser.add_argument('--panels',type=int,choices=(4,8,16),default=8)
    parser.add_argument('--output-dir',type=Path,required=True)
    args=parser.parse_args()
    folder=args.output_dir.resolve();folder.mkdir(parents=True,exist_ok=False)
    reference=ROOT/'.reference/isae-validation/f62943df20e9e4d7d9f50e070477b22426b5f865'/(
        '4 - Aeroelasticity/FFWT - Flared Folding Wingtips Cases/'
        'FFWT-4-U - Gust Alleviation of a Wing with and wo FFWT - Quantitative')
    name=f'FFWT_Flare{args.flare}'
    source=reference/(name+'_PM2.asw');driver=reference/(name+'.sh')
    import importlib.util
    spec=importlib.util.spec_from_file_location('source_contract',ROOT/'scripts/assess-isae-ffwt4-sources.py')
    helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
    contract=helper.driver_contract(driver.read_text())
    assert contract['requested_model']==name+'_PM2'
    conditions=contract['conditions']
    assert float(conditions['A']['value'])==6 and float(conditions['V']['value'])==22
    from openswing.asw import parse_asw
    from openswing.aero import FlightCondition
    from openswing.bridge import dispatch
    from openswing.source_airflow import SourceAirflowNetwork
    from openswing.equilibrium_state import restore, matching_identity, identity
    import numpy as np
    model=parse_asw(source.read_text(),beam_interpolation='drela-segspl-v1')
    request=dict(action='solve',mode='mounted',source=source.read_text(),panels=args.panels,
        numerics=dict(beam_interpolation='drela-segspl-v1',structural_operator='drela-moving-airflow-v1'),
        condition=dict(speed=22.,alpha=6.,beta=float(conditions.get('B',{}).get('value',0.)),
            density=float(model.constants[1]),mach=0.,gravity_magnitude=float(model.constants[0])),
        tolerance=1e-8,continuation_steps=4)
    def pin(path):
        data=Path(path).read_bytes()
        return dict(path=str(Path(path).resolve()),sha256=hashlib.sha256(data).hexdigest(),bytes=len(data))
    def write(name,value):
        (folder/name).write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')
    plan=dict(source=pin(source),driver=pin(driver),helper=pin(__file__),
        kernel=[pin(p) for p in sorted((ROOT/'openswing').glob('*.py'))],contract=contract,
        qualifications=[
            'Cold equilibrium on a deliberately small cosine mesh with mandatory source stations; not the original driver node count or a mesh-converged result.',
            'Documented A/V and any explicit B are retained. Missing B uses a disclosed zero default, not an authenticated historical value.',
            'Zero Mach, stationary frame, no ground, and initial no-gust field are declared setup choices.',
            'Whole-rigid-beam endpoint-pylon policy is recorded in the result and saved identity. Native out-of-range semantics remain unknown.',
            'No new native comparison count or full history validation is asserted.'])
    write('plan.json',plan);write('request.json',request)
    start=time.monotonic()
    try:
        with (folder/'progress.jsonl').open('w') as stream:
            def progress(*event):
                stream.write(json.dumps(dict(seconds=time.monotonic()-start,event=event))+'\n');stream.flush()
            result=dispatch(request,progress=progress)
        write('result.json',result)
        network=SourceAirflowNetwork(model,args.panels,FlightCondition(**request['condition']),None,[],steady_trim=True)
        assert matching_identity(identity(network),result['equilibrium_state']['identity'])
        residual=float(np.max(abs(network.residual(restore(network,result['equilibrium_state'])))))
        assert result['converged'] and result['residual']<=1e-8 and residual<=1e-8
        assert len(result['rigid_weight_attachments'])==2
        assert model.dumps()==source.read_text()
        for item in plan['kernel']+[plan['source'],plan['driver'],plan['helper']]:assert pin(item['path'])==item
        write('report.json',dict(status='COLD_EQUILIBRIUM_COMPUTED',seconds=time.monotonic()-start,
            residual=result['residual'],rebuilt_residual=residual,nodes=network.nn,elements=network.ne,
            beta_deg=request['condition']['beta'],rigid_weight_attachments=result['rigid_weight_attachments'],
            result=pin(folder/'result.json'),native_values_added=0))
        print(json.dumps(dict(status='COLD_EQUILIBRIUM_COMPUTED',nodes=network.nn,residual=residual)),flush=True)
    except Exception as error:
        write('failure.json',dict(error=repr(error),seconds=time.monotonic()-start))
        raise


if __name__=='__main__':main()
