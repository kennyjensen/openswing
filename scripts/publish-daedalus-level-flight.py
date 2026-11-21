"""Publish the checked Daedalus base as explicit, portable app cases.

No solve or identity editing. The accepted physical state is copied verbatim;
UI fields are taken from its solved flight condition. Historical projects stay
unchanged. Re-run only after separately validating the selected source state.
"""
from copy import deepcopy
from pathlib import Path
import json
import math

ROOT=Path(__file__).resolve().parents[1]
STUDY=ROOT/'artifacts/daedalus-regular-mesh-20261114'


def read(path):return json.loads(path.read_text())


def project():
    seed=read(STUDY/'trim-1/state.json')
    result=read(STUDY/'trim-1/result.json');terminal=read(STUDY/'audit/terminal.json')
    assert result['accepted'] and result['residual_max']<1e-9
    assert terminal['returncode']==0 and terminal['process_reaped'] and terminal['inputs_unchanged']
    old=read(ROOT/'examples/dae-cruise-physical-mesh-project.json')['cases'][0]['configuration']
    case=deepcopy(old);launch=seed['launch'];condition=launch['condition'];fields=case['fields']
    case['source']=(ROOT/'examples/dae.asw').read_text();case['filename']='dae.asw'
    case['mesh']=deepcopy(launch['panels'])
    # Both Daedalus buttons must use the same freshly checked default mesh.
    assert case['mesh']==read(ROOT/'web/daedalus-mesh.json')
    case['numerics']={key:seed['identity'][key] for key in ('beam_interpolation','structural_operator')}
    case['equilibrium']=dict(state=seed,enabled=True,label='Checked Daedalus level flight · 6.7 m/s · regular component mesh')
    case['controls']={str(k):str(v) for k,v in condition['controls'].items()}
    case['powers']={str(k):str(v) for k,v in condition['powers'].items()}
    case['circulation']={str(k):'0' for k in (1,2,3,5)}
    case['constraints']=[]
    for key in ('speed','alpha','beta'):fields[key]=str(condition[key])
    for group in ('rates','acceleration','angular_acceleration','position_earth','ground_normal'):
        prefix=group.replace('_','-') if group in ('position_earth','ground_normal') else group
        for axis,value in zip('xyz',condition[group]):
            fields[f'{prefix}-{axis}']=str(math.degrees(value) if group in ('rates','angular_acceleration') else value)
    for axis,value in zip(('bank','elevation','heading'),condition['attitude']):fields[f'attitude-{axis}']=str(value)
    fields.update({'mode':'frequency','frequency-frame':'free','frequency-inputs':'controls',
        'frequency-start':str(2*math.pi*.1),'frequency-end':str(2*math.pi*10),'frequency-count':'41',
        'frequency-spacing':'log','modal-frame':'free','modal-ordinary-frame':'free',
        'modal-vacuum':False,'modal-quiescent':False,'time-frame':'free',
        'density-mode':'standard','gravity-mode':'file','mach-mode':'fixed','pg-mach':str(condition['mach']),
        'altitude':str(condition['altitude_m']/float(fields['altitude-unit'])),
        'ground-effect':str(condition['ground_effect']),'sensor-flow':condition['sensor_flow'],'gust-kind':'none',
        'aero-lag':condition['aero_lag'],'freeze-influences':condition['freeze_influences'],
        'wake-core-ratio':str(condition['wake_core_ratio']),'stall':condition['stall'],
        'stall-factor':str(condition['stall_factor']),'stall-width':str(condition['stall_width']),
        # Select values are exact strings: Python's "1.0" is not the DOM's "1".
        'body-added-mass':format(condition['body_added_mass_factor'],'g'),'load-factor':str(condition['load_factor']),
        'strut-mode':launch['strut_mode'],'feedback-enabled':False,'derivatives-enable':False,
        'time-initial-enable':False,'time-forcing':'','time-actuators':'','frequency-initial':'[]'})
    trim=deepcopy(case);trim['fields']['mode']='mounted';trim['constraints']=deepcopy(old['constraints'])
    assert [(r['variable'],r['quantity'],r['target']) for r in trim['constraints']]==[
        (r['variable'],r['quantity'],r['target']) for r in launch['released_constraints']]
    return dict(format='openswing-project',version=2,name='Daedalus · checked level flight',
        selected='dae-level-bode',cases=[
            dict(id='dae-level-bode',name='Level flight · Bode response',configuration=case),
            dict(id='dae-level-trim',name='Level flight · steady trim',configuration=trim)],
        solutions=[],selected_solution=None)


if __name__=='__main__':
    data=json.dumps(project(),indent=2,allow_nan=False)+'\n'
    for folder in ('examples','public/examples'):
        path=ROOT/folder/'dae-level-flight-project.json';path.write_text(data)
        print(path.relative_to(ROOT))
