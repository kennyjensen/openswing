"""Bounded replay of the published app fields and saved equilibrium, no solve."""
import argparse
from pathlib import Path
from check_daedalus_load_sensitivity import ROOT,read
from daedalus_bounded_job import run

STUDY=ROOT/'artifacts/daedalus-level-flight-case-20261114'
PROJECT=ROOT/'examples/dae-level-flight-project.json'


def check(folder,args):
    import math
    import numpy as np
    from openswing.aero import FlightCondition
    from openswing.asw import parse_asw
    from openswing.equilibrium_state import restore
    from openswing.linear_dynamics import _dynamic_base
    from openswing.operating import time_load_constraints
    from openswing.source_airflow import SourceAirflowNetwork
    from openswing.time_state import condition_data,read_condition
    project=read(PROJECT);rows=[]
    assert PROJECT.read_bytes()==(ROOT/'public/examples'/PROJECT.name).read_bytes()
    original=read(ROOT/'artifacts/daedalus-regular-mesh-20261114/trim-1/state.json')
    for case in project['cases']:
        config=case['configuration'];f=config['fields'];seed=config['equilibrium']['state']
        assert seed==original and config['equilibrium']['enabled']
        assert config['source']==(ROOT/'examples/dae.asw').read_text()
        assert config['mesh']==seed['launch']['panels']==read(ROOT/'web/daedalus-mesh.json')
        values={k:float(f[k]) for k in ('speed','alpha','beta')}
        for group in ('rates','acceleration','angular_acceleration','position_earth','ground_normal'):
            prefix=group.replace('_','-') if group in ('position_earth','ground_normal') else group
            values[group]=[float(f[f'{prefix}-{axis}'])*(math.pi/180 if group in ('rates','angular_acceleration') else 1) for axis in 'xyz']
        values['attitude']=[float(f[f'attitude-{axis}']) for axis in ('bank','elevation','heading')]
        for key in ('controls','powers','circulation'):
            values['circulation_modes' if key=='circulation' else key]={int(k):float(v) for k,v in config[key].items() if key!='circulation' or float(v)!=0}
        for key in ('body_added_mass_factor','load_factor','wake_core_ratio','stall_factor','stall_width'):
            values[key]=float(f['body-added-mass' if key=='body_added_mass_factor' else key.replace('_','-')])
        for key in ('stall','aero_lag','freeze_influences'):values[key]=f[key.replace('_','-')]
        values.update(altitude_m=float(f['altitude'])*float(f['altitude-unit']),
            density=float(f['density']) if f['density-mode']=='custom' else None,
            gravity_magnitude=float(f['gravity-magnitude']) if f['gravity-mode']=='custom' else None,
            mach=float(f['pg-mach']) if f['mach-mode']=='fixed' else None,
            ground_effect=int(f['ground-effect']),sensor_flow=f['sensor-flow'])
        assert f['gust-kind']=='none' and not f['feedback-enabled']
        condition=FlightCondition(**values)
        assert condition_data(condition)==condition_data(read_condition(seed['launch']['condition']))
        model=parse_asw(config['source'],beam_interpolation=config['numerics']['beam_interpolation'])
        assert sorted(map(int,config['controls']))==sorted(model.controls)
        assert sorted(map(int,config['powers']))==sorted(model.engine_controls)
        assert sorted(map(int,config['circulation']))==sorted(b.index for b in model.beams if b.lifting)
        dynamic=f['mode']=='frequency'
        constraints=time_load_constraints('free') if dynamic else config['constraints']
        if dynamic:
            assert not config['constraints'] and f['frequency-frame']=='free'
            assert f['frequency-count']=='41' and f['frequency-spacing']=='log'
            assert abs(float(f['frequency-start'])/(2*math.pi)-.1)<1e-14
            assert abs(float(f['frequency-end'])/(2*math.pi)-10)<1e-14
        else:assert len(constraints)==7
        n=SourceAirflowNetwork(model,config['mesh'],condition,None,[],
            operating_constraints=constraints,steady_trim=not dynamic,
            strut_mode=f['strut-mode'],mesh_recipe='accurate-arc-v2')
        x=restore(n,seed);residual=float(max(abs(n.residual(x))))
        assert residual<1e-9
        row=dict(case=case['id'],ui_condition_matches_saved_trim=True,
            identity_valid=True,nodes=n.nn,elements=n.ne,circulation=n.ng,residual=residual)
        if dynamic:
            zeros=np.zeros_like(n.rj)
            system=_dynamic_base(n,x,constraints,'free',dict(
                elastic_motion=(zeros,zeros,zeros,zeros),circulation_rate=np.zeros(n.ng)),
                position=condition.position_earth,attitude=condition.attitude,
                velocity=(0,0,0),gravity_magnitude=condition.gravity_magnitude)
            zero=np.zeros(system.size);base=system.base_report()
            error=float(max(abs(system.residual(zero,zero))))
            assert error<1e-9 and base['modal_base']['kinematically_steady']
            assert abs(base['earth_state']['flight_path'])<1e-7
            row.update(dynamic_states=system.size,dynamic_residual=error,
                flight_path_deg=base['earth_state']['flight_path'],
                weight_lb=float(base['mass_properties']['mass']*np.linalg.norm(base['gravity_body'])))
        rows.append(row)
    return dict(cases=rows,qualification='Direct residual checks from exported UI fields; no Jacobian, frequency sweep, browser or WASM run.')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--tag',required=True)
    args=vars(parser.parse_args())
    inputs=list((ROOT/'openswing').glob('*.py'))+[PROJECT,ROOT/'public/examples'/PROJECT.name,
        ROOT/'web/daedalus-mesh.json',ROOT/'web/main.js',ROOT/'examples/dae.asw',
        ROOT/'scripts/publish-daedalus-level-flight.py',ROOT/'docs/validation/ISAE_STATUS.md',
        ROOT/'artifacts/daedalus-regular-mesh-20261114/trim-1/state.json']
    run(STUDY,args['tag'],inputs,check,args,__file__)
