"""Compare a contiguous FFWT2 checkpoint chain with every original output row.

Saved-only assessment. No interpolation, time/phase shift, fitted initialization,
or modulo-angle adjustment is allowed. Short histories retain missing targets.
"""
import argparse
from collections import defaultdict
from decimal import Decimal
import hashlib
import json
import math
from pathlib import Path
import statistics

from isae_acceptance import apply_reference_acceptance


def pin(p):
    p=Path(p).resolve();b=p.read_bytes()
    return dict(path=str(p),bytes=len(b),sha256=hashlib.sha256(b).hexdigest())


def outputs(s):
    frame=s['frame'];sensors={r['index']:r for r in s['sensors']}
    # Source Euler histories carry the continuous Earth bank, unlike atan2's
    # principal displayed angle. Sensor Phi is the published principal angle.
    return [math.degrees(frame['angular_acceleration_body'][0]),
        math.degrees(frame['rates_body'][0]),
        math.degrees(s['restart']['state']['source_attitude'][0]),
        sensors[2]['bank'],sensors[3]['bank']]


def assess(last):
    chain=[];seen=set();folder=Path(last).resolve()
    while True:
        assert folder not in seen,'Cyclic checkpoint ancestry'
        seen.add(folder)
        plan=json.loads((folder/'plan.json').read_text())
        chain.append((folder,plan))
        parent=plan.get('parent_checkpoint')
        if parent is None:break
        assert pin(parent['path'])==parent
        folder=Path(parent['path']).parent
    chain.reverse();plan=chain[0][1]
    for p in plan['source_pins']+plan['kernel_pins']+[plan['helper']]:assert pin(p['path'])==p
    initial_time=plan.get('declared_segment_start',0.)
    prefix=None
    if initial_time:
        if plan.get('continuation_version')==2:
            assert initial_time==.01 and plan['startup']=='jig-zero-motion-zero-circulation'
            for key in ('first_step_result','first_checkpoint','preparation_helper'):
                assert pin(plan[key]['path'])==plan[key]
            prefix=json.loads(Path(plan['first_step_result']['path']).read_text())
            first_checkpoint=json.loads(Path(plan['first_checkpoint']['path']).read_text())
            assert len(prefix['snapshots'])==2 and prefix['accepted_steps']==1 and prefix['rejected_steps']==0
            seed,prior=prefix['snapshots'];raw=seed['restart']['state']
            assert seed['time']==raw['time']==0. and prior['time']==.01
            assert seed['initial_phase']=='declared_uncomputed_jig_seed'
            assert seed['residual']==plan['seed_residual']
            assert all(v==0. for row in raw['position_chart']['coordinates'] for v in row),'Changed jig seed'
            assert all(v==0. for key in ('local_velocity','local_rates') for row in raw[key] for v in row),'Changed jig seed'
            assert all(v==0. for key in ('rates_body','position_earth','source_attitude') for v in raw[key]),'Changed jig seed'
            assert all(v==0. for row in raw['network']['rotations'] for v in row),'Changed jig seed'
            assert raw['body_to_earth']==[[1.,0.,0.],[0.,1.,0.],[0.,0.,1.]],'Changed jig seed'
            assert raw['velocity_origin_body']==[-15.,0.,0.],'Changed jig seed'
            assert all(v==0. for v in raw['network']['circulation']),'Changed jig seed'
            assert first_checkpoint['state']==prior['restart']['state']
            accepted=first_checkpoint['accepted_method']
            assert accepted['kind']=='bdf' and accepted['scheme']=='drela-euler-bdf-v1'
            assert accepted['effective_order']==1 and accepted['previous']==raw and accepted['previous2'] is None
        else:
            assert plan.get('continuation_version')==1
            for key in ('prefix_checkpoint','prefix_report','frozen_prefix_manifest'):
                assert pin(plan[key]['path'])==plan[key]
            prefix=json.loads(Path(plan['prefix_report']['path']).read_text())
            assert prefix['checkpoint']==plan['prefix_checkpoint']
            assert pin(prefix['result']['path'])==prefix['result']
            prior=json.loads(Path(prefix['result']['path']).read_text())['snapshots'][-1]
            assert abs(prior['time']-initial_time)<1e-12
            frozen=json.loads(Path(plan['frozen_prefix_manifest']['path']).read_text())
            frozen={Path(r['original']['path']).name:r for r in frozen}
            changed=[]
            for p in plan['kernel_pins']:
                row=frozen[Path(p['path']).name];old=row['original'];actual=pin(row['frozen_path'])
                assert all(actual[k]==old[k] for k in ('bytes','sha256'))
                if p!=old:changed.append(Path(p['path']).name)
            assert changed==plan['kernel_upgrade']['changed_modules']==['time_integration.py']
    samples={};numerical=[];jobs=[];last_end=None;command_restarts=[]
    for folder,p in chain:
        assert all(p[k]==plan[k] for k in ('source_pins','kernel_pins','helper','nominal'))
        report=json.loads((folder/'report.json').read_text())
        assert report['status']=='SEGMENT_COMPUTED'
        if 'segment_helper' in report:assert pin(report['segment_helper']['path'])==report['segment_helper']
        for k in ('result','checkpoint'):assert pin(report[k]['path'])==report[k]
        result=json.loads((folder/'result.json').read_text())
        assert result['converged'] and result['temporal_policy']=='drela-euler-bdf-v1'
        if plan.get('continuation_version')==2:
            assert all(p[k]==plan[k] for k in ('continuation_version','startup','first_checkpoint','first_step_result','preparation_helper'))
            assert result['checkpoint_validation']['discrete_replayed'],'Missing initial discrete replay'
            assert result['checkpoint_validation']['residual']<=1e-8
        assert abs(result['maximum_step']-.01)<1e-14
        start=result['snapshots'][0]['time'];end=result['snapshots'][-1]['time']
        assert abs(start-(initial_time if last_end is None else last_end))<1e-12
        if command_restarts:assert p.get('command_restarts')==command_restarts
        if p.get('command_restarts') and not command_restarts:
            assert p['command_restarts']==[2.] and abs(start-2.)<1e-12,'Command restart must begin at original boundary'
            command_restarts=p['command_restarts']
        if prefix is not None and last_end is None:
            assert max(abs(a-b) for a,b in zip(outputs(prior),outputs(result['snapshots'][0])))<=1e-8
        for s in result['snapshots']:
            tick=round(s['time']/.01)
            assert abs(tick*.01-s['time'])<1e-10,'Off-grid snapshot; do not interpolate'
            values=outputs(s)
            if p.get('command_restarts'):
                assert p['command_restarts']==[2.]
                if s['time']>2.+1e-12:
                    expected_order=1 if abs(s['time']-2.01)<1e-12 else 2
                    assert s['restart']['accepted_method']['effective_order']==expected_order,'Wrong command-restart stencil'
            assert all(v is not None and math.isfinite(v) for v in values)
            numerical.append(dict(name=f'{folder.name}/t={tick}/residual',
                passed=bool(s['converged'] and math.isfinite(s['residual']) and s['residual']<=1e-8),
                value=s['residual'],limit=1e-8))
            if tick in samples:
                assert max(abs(a-b) for a,b in zip(samples[tick],values))<=1e-8
            samples[tick]=values
        jobs.append(dict(folder=str(folder),seconds=report['seconds'],start=start,end=end,
            accepted_steps=result['accepted_steps'],rejected_steps=result['rejected_steps'],
            result=report['result'],checkpoint=report['checkpoint']))
        last_end=end
    first_tick=round(initial_time/.01)
    assert sorted(samples)==list(range(first_tick,max(samples)+1)),'Missing time step'
    checks=[];names=['roll_acceleration_deg_s2','roll_rate_deg_s','bank_deg','sensor2_bank_deg','sensor3_bank_deg']
    for row in plan['native_rows']:
        tokens=row['tokens'];tick=round(float(tokens[1])/.01)
        assert abs(float(tokens[1])-tick*.01)<1e-10
        for i,(name,token) in enumerate(zip(names,tokens[2:])):
            expected=Decimal(token)
            absolute=Decimal(5).scaleb(expected.as_tuple().exponent-1)
            value=samples.get(tick,[None]*5)[i]
            checks.append(dict(name=f'line{row["line"]}/{name}',channel=name,time=float(tokens[1]),
                expected=float(expected),exact_decimal_expected=str(expected),predicted=value,
                tolerance=float(absolute),exact_decimal_tolerance=str(absolute),
                passed=value is not None and abs(Decimal(str(value))-expected)<=absolute))
    computed=sum(c['predicted'] is not None for c in checks)
    numerical_pass=all(c['passed'] for c in numerical)
    if not numerical_pass:
        for c in checks:c['passed']=False
    result=dict(status='computed',numerical_pass=numerical_pass,
        numerical_checks=numerical,reference_checks=checks,
        output_accounting=dict(required=len(checks),computed=computed,missing=len(checks)-computed))
    result=apply_reference_acceptance(result,relative_tolerance=.05)
    groups=defaultdict(list)
    for c in result['reference_checks']:groups[c['channel']].append(c)
    summary={}
    for name,rows in groups.items():
        failures=[100*c['relative_error'] for c in rows if c['predicted'] is not None
                  and not c['passed'] and c['relative_error'] is not None]
        summary[name]=dict(required=len(rows),computed=sum(c['predicted'] is not None for c in rows),
            passed=sum(c['passed'] for c in rows),failed_median_percent=statistics.median(failures) if failures else None,
            failed_max_percent=max(failures) if failures else None)
    result.update(family='FFWT-2',configuration=plan['configuration'],scope='Declared startup, one source triple',
        jobs=jobs,unique_snapshots=len(samples),start_time=initial_time,end_time=last_end,channels=summary,
        declared_startup=plan.get('startup','zero-local-rate equilibrium'),command_restarts=command_restarts,
        prefix_checkpoint=plan.get('prefix_checkpoint'),
        source_pins=plan['source_pins'],qualifications=plan['qualifications'],
        independent_trajectory_audit=False,temporal_refinement=False,mesh_refinement=False,
        full_family_validated=False)
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--last',required=True,type=Path)
    p.add_argument('--output',required=True,type=Path);args=p.parse_args()
    result=assess(args.last)
    args.output.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps(dict(accounting=result['output_accounting'],channels=result['channels'],end_time=result['end_time'])))
