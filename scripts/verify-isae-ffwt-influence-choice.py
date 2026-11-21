#!/usr/bin/env python3
"""A declared K/F counterpart to the retained original FFWT reference pilot.

Changes only freeze_influences, never model properties or acceptance tolerances.
The historical setting is unknown. A closer result does not recover it.
"""
import argparse
from copy import deepcopy
import importlib.util
from pathlib import Path
import json

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('ffwt_reference',ROOT/'scripts/verify-isae-ffwt-reference.py')
reference=importlib.util.module_from_spec(spec);spec.loader.exec_module(reference)
read,write,pin,require=reference.read,reference.write,reference.pin,reference.require


def prepare(stage,baseline):
    require(not stage.exists(),'Use a new stage; no automatic retries.')
    old=read(baseline/'plan.json');summary=read(baseline/'summary.json')
    require(summary['status']=='PASS_FFWT_STARTUP_PHYSICAL_PARITY_AND_PERFORMANCE','Expected verified current updated-influence baseline.')
    for name,h in old['kernel_pins'].items():
        require(pin(ROOT/'openswing'/name)['sha256']==h,'Baseline kernel changed: '+name)
    stage.mkdir(parents=True)
    cases=[];inputs=[Path(__file__),ROOT/'scripts/verify-isae-ffwt-reference.py',
        baseline/'plan.json',baseline/'summary.json',ROOT/'examples/isae-ffwt-flare10.asw',
        ROOT/'.reference/aswing_doc.txt',ROOT/'.reference/asw_theory.pdf']
    for old_case in old['cases']:
        name=old_case['name'];folder=stage/'cases'/name;prior=baseline/'cases'/name
        original=read(prior/'request.json');request=deepcopy(original)
        require(request['condition']['freeze_influences'] is False,'Baseline K/F must be updated.')
        require('initial_state' not in request,'Counterpart requires cold requests.')
        request['condition']['freeze_influences']=True
        witness=deepcopy(request);witness['condition']['freeze_influences']=False
        require(witness==original,'Additional request difference.')
        project=read(prior/'input-project.json')
        require(len(project['cases'])==1 and not project['solutions'],'Use unsolved one-case project.')
        config=project['cases'][0]['configuration'];require(config['fields']['freeze-influences'] is False,'Project K/F mismatch.')
        config['fields']['freeze-influences']=True
        write(folder/'request.json',request);write(folder/'input-project.json',project)
        cases.append(dict(name=name,request=str(folder/'request.json'),baseline=str(prior)))
        inputs += [folder/'request.json',folder/'input-project.json',prior/'request.json',
                   prior/'input-project.json',prior/'report.json',prior/'result.json']
    inputs += sorted((ROOT/'openswing').glob('*.py'))
    plan=dict(status='PREPARED',cases=cases,reference=old['reference'],gates=old['gates'],
        child_cap_seconds=180,thread_environment=reference.THREADS,cold_solves=2,fresh_residuals=2,
        only_condition_override=dict(freeze_influences=dict(baseline=False,counterpart=True)),
        historical_KF='UNKNOWN',
        interpretation='The embedded original reference contract retains its declared updated setting; only this explicit counterpart override changes it. No historical setting is inferred from closeness.',
        comparison_scope='Both meshes launch based only on unchanged physical gates, not agreement with archived outputs. No production-default change.',
        sampling='Original row4, original182/358interval meshes, all four archived outputs, full physical/restoration checks; no setting search or further coordinates.',
        pins=[pin(p) for p in inputs],kernel_pins=old['kernel_pins'])
    write(stage/'plan.json',plan)
    print(json.dumps(pin(stage/'plan.json')),flush=True)


def summarize(stage):
    plan=read(stage/'plan.json');summary=read(stage/'summary.json')
    require(summary['status']=='PASS_PHYSICAL_CHECKS','Both cold cases must pass physical checks.')
    require(reference.unchanged(plan),'Inputs changed before comparison.')
    comparisons={};airflow={}
    for case in plan['cases']:
        name=case['name'];prior=Path(case['baseline']);folder=stage/'cases'/name
        before=read(prior/'report.json');after=read(folder/'report.json')
        comparisons[name]={key:dict(updated=before['comparison'][key],frozen=after['comparison'][key],
            change=after['outputs'][key]-before['outputs'][key]) for key in before['outputs']}
        airflow[name]={}
        for label,p in [('updated',prior),('frozen',folder)]:
            result=read(p/'result.json')
            request=deepcopy(result['request']) if 'request' in result else read(p/'request.json')
            require(request==read(p/'request.json'),'Returned request differs.')
            strips=result['strips']
            # Compare saved full velocity norms only; no new flow calculation.
            speeds=[sum(v*v for v in s['relative_velocity'])**.5 for s in strips]
            i=max(range(len(speeds)),key=speeds.__getitem__)
            airflow[name][label]=dict(maximum_full_speed=speeds[i],strip_index=i,
                beam=strips[i]['beam'],t=strips[i]['t'],evaluations=result['evaluations'],
                solve_seconds=read(p/'report.json')['solve_seconds'])
    write(stage/'comparison.json',dict(status='PASS_DOCUMENTED_SETTING_COUNTERPART',
        historical_KF='UNKNOWN',production_changed=False,reference_match=summary['archived_match'],
        physical_checks=sum(c['checks_passed'] for c in summary['cases'].values()),
        comparison=comparisons,frozen_mesh=summary['mesh'],frozen_mesh_passed=summary['mesh_passed'],
        saved_airflow=airflow,operations=dict(cold_solves=2,fresh_residuals=2),
        conclusion_scope='Sensitivity to a documented alternative only; closeness does not establish the historical option or exact grid.',
        plan=pin(stage/'plan.json'),summary=pin(stage/'summary.json')))
    print(json.dumps(read(stage/'comparison.json')),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=('prepare','run'))
    parser.add_argument('stage',type=Path);parser.add_argument('--baseline',type=Path)
    args=parser.parse_args()
    if args.action=='prepare':prepare(args.stage.resolve(),args.baseline.resolve())
    else:
        reference.run(args.stage.resolve())
        summarize(args.stage.resolve())
