"""Bounded FFWT-4 fixed-wing initial-state comparison, before the first gust.

Use the literal model and commanded speed/incidence. Numerical settings remain
declared; the initial root moment is not a validation of the gust histories.
"""
import argparse
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
REVISION='f62943df20e9e4d7d9f50e070477b22426b5f865'
FAMILY=('4 - Aeroelasticity/FFWT - Flared Folding Wingtips Cases/'
        'FFWT-4-U - Gust Alleviation of a Wing with and wo FFWT - Quantitative')


def pin(path):
    path=Path(path).resolve();raw=path.read_bytes()
    return dict(path=str(path),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())


def write(path,value):
    path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output-dir',required=True,type=Path)
    ap.add_argument('--nominal',type=int,choices=(16,32,64,98),default=16)
    args=ap.parse_args();folder=args.output_dir.resolve();folder.mkdir(parents=True,exist_ok=False)
    cache=ROOT/'.reference/isae-validation'/REVISION;base=cache/FAMILY
    model_path=base/'FFWT_Fixed.asw';driver=base/'FFWT_Fixed.sh'
    outputs=sorted((base/'FFWT_Fixed').glob('*.txt'))
    source_pins=[pin(p) for p in [model_path,driver,*outputs]]
    manifest=json.loads((cache.parent/'manifest.json').read_text())
    for p in source_pins:
        original=manifest['files'][Path(p['path']).relative_to(cache).as_posix()]
        assert all(p[k]==original[k] for k in ('sha256','bytes'))
    commands=[s.strip().lower() for s in driver.read_text().splitlines() if s.strip()]
    assert commands[0]=='#!/bin/sh' and commands[1].endswith('aswing ffwt_fixed <<eof')
    assert '!a 6' in commands and '!v 22' in commands and '13 13' in commands
    assert commands[commands.index('gmod')+1]=='5'
    gust=list(map(float,commands[commands.index('gmod')+2].split()))
    assert gust==[-10.9366,0.,10.9366,.6978]
    native=[]
    for p in outputs:
        for line,raw in enumerate(p.read_text().splitlines(),1):
            if not raw.strip() or raw.startswith('#'):continue
            tokens=raw.split();assert len(tokens)==3
            native.append(dict(source=str(p),line=line,tokens=tokens))
    first=next(r for r in native if Path(r['source']).name=='FFWT_Fixed-1.txt' and r['tokens'][0]=='1')
    assert Decimal(first['tokens'][1])==0
    value=Decimal(first['tokens'][2]);half=Decimal(10)**value.as_tuple().exponent/2
    request=dict(action='solve',mode='mounted',source=model_path.read_text(),
        numerics=dict(beam_interpolation='drela-segspl-v1',structural_operator='drela-moving-airflow-v1'),
        panels=dict(default=args.nominal,beams={'1':dict(count=args.nominal,spacing='cosine')}),
        condition=dict(speed=22.,alpha=6.,beta=0.,density=1.2256,mach=0.,gravity_magnitude=9.81,
            position_earth=[0.,0.,0.],attitude=[0.,0.,0.],rates=[0.,0.,0.],
            acceleration=[0.,0.,0.],angular_acceleration=[0.,0.,0.],ground_effect=0,
            freeze_influences=False,aero_lag=True,circulation_modes={'1':0},
            wake_core_ratio=.25,stall=True,stall_factor=40.,stall_width=.05),
        tolerance=1e-8,continuation_steps=4)
    kernels=[pin(p) for p in sorted((ROOT/'openswing').glob('*.py'))]
    plan=dict(family='FFWT-4',scope='FFWT_Fixed-1 t=0 root Mcprime only',source_pins=source_pins,
        kernel_pins=kernels,helper=pin(__file__),native_target=first,
        fixed_history_slots=len(native),nominal=args.nominal,
        qualifications=[
            'Literal FFWT_Fixed.asw model, whose internal Name is FFWT Removed, is retained unchanged.',
            'Speed22/alpha6 and initial steady solve are commanded. Sensor1 moment is local c component at the left root trace.',
            'Fixed frame, zero pose/rates, PG0, cosine nominal mesh, pointwise circulation and current aerodynamic flags are declared.',
            'The driver requests I100 for beam1 and I40 for nonexistent beams2/3. Exact historical nodes and complete operating defaults remain unrecovered.',
            'At t=0 the type5 gust starts upstream at x=-10.9366, so the wing is outside its support.',
            'Only one initial native value is compared. Subsequent gust response, other models and convergence remain required.'],
        full_family_validated=False)
    write(folder/'plan.json',plan);write(folder/'request.json',request)
    from openswing.asw import parse_asw
    from openswing.aero import FlightCondition
    from openswing.bridge import dispatch
    from openswing.source_airflow import SourceAirflowNetwork
    from openswing.equilibrium_state import restore,identity,matching_identity,warm_start_recipe
    import numpy as np
    model=parse_asw(request['source'],beam_interpolation='drela-segspl-v1')
    assert len(model.beams)==1 and model.beams[0].domain==(-.5,.5) and not model.diagnostics
    cdata=dict(request['condition']);cdata['circulation_modes']={1:0}
    condition=FlightCondition(**cdata)
    started=time.monotonic()
    with (folder/'progress.jsonl').open('w') as stream:
        def progress(*event):
            stream.write(json.dumps(dict(seconds=time.monotonic()-started,event=event))+'\n');stream.flush()
        result=dispatch(request,progress=progress)
    write(folder/'result.json',result)
    assert result['converged'] and result['residual']<=1e-8
    network=SourceAirflowNetwork(model,request['panels'],condition,None,[],steady_trim=True,
        mesh_recipe=warm_start_recipe(model,request['panels'],result['equilibrium_state']))
    assert matching_identity(identity(network),result['equilibrium_state']['identity'])
    residual=network.residual(restore(network,result['equilibrium_state']))
    fresh=float(np.max(abs(residual)));assert fresh<=1e-8 and network.nfev==1
    sensor=next(s for s in result['sensors'] if s['index']==1)
    predicted=sensor['moment_local'][0]
    error=abs(predicted-float(value));allowed=max(float(half),.05*abs(float(value)))
    assert all(pin(p['path'])==p for p in source_pins+kernels+[plan['helper']])
    report=dict(status='INITIAL_COMPARISON_COMPUTED',seconds=time.monotonic()-started,
        cold_solves=1,fresh_residuals=1,residual=fresh,nodes=network.nn,elements=network.ne,
        predicted=predicted,expected=float(value),error_percent=100*error/abs(float(value)),
        tolerance=allowed,passed=error<=allowed,reference_values_computed=1,
        fixed_history_slots=len(native),full_family_validated=False,
        root_sensor=sensor,result=pin(folder/'result.json'),source_pins_unchanged=True,kernel_pins_unchanged=True)
    write(folder/'report.json',report)
    print(json.dumps({k:report[k] for k in ('status','seconds','residual','nodes','elements','predicted','expected','error_percent','passed')}),flush=True)


if __name__=='__main__':main()
