"""Update the fixed 48 paper targets with independently verified aligned runs."""
import argparse
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import signal
import statistics
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from sa11_paper_suite import bounded,decision,interpolate,write_new
read=lambda p:json.loads(p.read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--spec',type=Path,default=ROOT/'docs/validation/sa11-paper-suite-v2.json')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();bounded()
    assert not args.output.exists()
    spec=read(args.spec);assert spec['version']==2
    old=ROOT/spec['base_assessment'];new=ROOT/spec['aligned_evidence']
    previous=read(old/'analysis.json');proof=read(old/'verification.json')
    assert proof['verified'] and proof['analysis_sha256']==sha(old/'analysis.json')
    aligned=read(new/'analysis.json');plan=read(new/'plan.json')
    assert aligned['verified'] and aligned['plan_sha256']==sha(new/'plan.json')
    pins=dict(previous['pins']);pins.update(aligned['pins'])
    for name,digest in pins.items():assert sha(ROOT/name)==digest,name
    for configuration,digest in aligned['configuration_verification_sha256'].items():
        path=new/f'verification-{configuration}.json';assert sha(path)==digest
        pins[str(path.relative_to(ROOT))]=digest
    for path in (args.spec.resolve(),Path(__file__),old/'analysis.json',old/'verification.json',new/'plan.json',new/'analysis.json'):
        pins[str(path.relative_to(ROOT))]=sha(path)
    result=deepcopy(previous)
    result.update(observed_utc=datetime.now(timezone.utc).isoformat(),suite=spec['name'])
    result['protocol'].update(version=2,name=spec['name'],alignment_spec=spec)
    sources={}
    for row in aligned['cases']:
        case=row['case'];directory=new/case['id'];path=directory/'report.json'
        assert sha(path)==row['report_sha256']
        pins[str(path.relative_to(ROOT))]=row['report_sha256']
        for name,digest in row['artifacts'].items():
            assert sha(directory/name)==digest
            pins[str((directory/name).relative_to(ROOT))]=digest
        key=case['configuration'],case['label']
        valid=row['status']=='computed'
        sources.setdefault(key,[]).append(dict(alpha=case['alpha'],valid=valid,
            CL=row['values']['CL'] if valid else None,CD=row['values']['CD'] if valid else None,
            status=row['status'],source=str(path.relative_to(ROOT))))
    for curve in result['curves']:
        key=curve['configuration'],curve['label']
        if curve['configuration'] in ('wing_alone','wing_extension'):
            curve['points']=sources[key]
        elif key in sources:
            assert not {p['alpha'] for p in curve['points']}&{p['alpha'] for p in sources[key]}
            curve['points'].extend(sources[key])
        curve['points'].sort(key=lambda p:p['alpha'])
        curve['freeze_influences']=True
        curve['setup']=curve['setup'].replace('Current-wind influences.','Frozen influences, aligned to the winglet runs.')
    for configuration in result['protocol']['configurations']:
        configuration['freeze_influences']=True
        configuration['setup']=configuration['setup'].replace('Current-wind influences.','Frozen influences, aligned to the winglet runs.')
        if configuration['id'] in ('wing_alone','wing_extension'):
            configuration.update(source=spec['aligned_evidence'],reader='aligned_saved')
        elif configuration['id']=='upper_winglet':
            configuration.update(supplement=spec['aligned_evidence'],supplement_alpha=5.25)
    transitions=[]
    for c,before in zip(result['checks'],previous['checks'],strict=True):
        curve=next(r for r in result['curves'] if r['configuration']==c['configuration'] and r['label']==c['label'])
        xkey,ykey=('alpha','CL') if c['kind']=='lift' else ('CL','CD')
        value,bracket,reason=interpolate(curve['points'],c['x'],xkey,ykey,result['protocol']['maximum_interpolation_gap_degrees'])
        status,error=decision(value,c['target'],result['protocol']['relative_tolerance'])
        if c['kind']=='lift' and any(p['alpha']==c['x'] and not p['valid'] for p in curve['points']):status='rejected'
        c.update(actual=value,bracket_alpha=bracket,reason=reason,status=status,error_percent=error)
        if status!=before['status']:
            transitions.append(dict(id=c['id'],before=before['status'],after=status))
    assert len(result['checks'])==result['required']==spec['required_checks']==48
    result['counts']=dict(Counter(c['status'] for c in result['checks']))
    for group in result['groups']:
        rows=[c for c in result['checks'] if c['configuration']==group['configuration']]
        errors=[abs(c['error_percent']) for c in rows if c['error_percent'] is not None]
        failed=[abs(c['error_percent']) for c in rows if c['status']=='mismatch']
        group.update(counts=dict(Counter(c['status'] for c in rows)),maximum_error_percent=max(errors,default=None),
            failed_error_percent=dict(median=statistics.median(failed),maximum=max(failed)) if failed else None,
            fields={kind:dict(Counter(c['status'] for c in rows if c['kind']==kind)) for kind in ('lift','drag_at_equal_lift')})
    # Same-flight-condition increments are meaningful configured-model outputs,
    # but only identical main-wing section data would isolate the tip geometry.
    import numpy as np
    sys.path.insert(0,str(ROOT))
    from openswing.asw import parse_asw
    stations=np.array([0.,.2,.5,.75,1.,1.2])
    fields=('dCLda','Cdf','Cdp','alpha','Cm','CLmax','CLmin')
    models={}
    for case in plan['cases']:models.setdefault(case['configuration'],case['model_path'])
    models['upper_lower_winglets']='artifacts/isae/sa11-two-winglet-spacing-20261108/model.asw'
    sections={}
    for name,path in models.items():
        pins[path]=sha(ROOT/path)
        model=parse_asw((ROOT/path).read_text(),beam_interpolation='natural-v1')
        beam=next(b for b in model.beams if b.index==1)
        sections[name]={field:beam.value(field,stations).tolist() for field in fields}
    differences={name:[field for field in fields if sections[name][field]!=sections['wing_alone'][field]]
                 for name in sections if name!='wing_alone'}
    result['shared_main_wing_input_audit']=dict(stations=stations.tolist(),fields=sections,
        differing_fields_from_baseline=differences,source='Parsed literal pinned input values; no parameter transfer or fitting')
    for increment in result['drag_increments']:
        checks={c['configuration']:c for c in result['checks'] if c['kind']=='drag_at_equal_lift'
            and c['label']==increment['label'] and c['x']==increment['CL']}
        base=checks['wing_alone'];tip=checks[increment['configuration']]
        actual=tip['actual']-base['actual'] if tip['actual'] is not None and base['actual'] is not None else None
        increment.update(actual_delta_CD=actual,comparable_delta_CD=actual,matched_influence_convention=True,
            reason=None if actual is not None else 'Missing accepted matched-lift bracket',
            main_wing_airfoil_fields_differ=differences[increment['configuration']],
            isolates_wingtip_geometry=not differences[increment['configuration']],
            qualification='Flight and influence settings match. Original baseline main-wing airfoil data differ; this configured-model difference does not isolate wingtip geometry.')
    result.update(pins=pins,physical_calls=0,transitions=transitions,
        new_solve_evidence={k:aligned[k] for k in ('physical_calls','reused_states','computed','rejected',
            'maximum_residual','maximum_normal_mach','minimum_stall_margin_widths','peak_rss_kib','maximum_batch_seconds')})
    args.output.mkdir(parents=True)
    write_new(args.output/'analysis.json',result)
    signal.alarm(0)
    print(json.dumps({k:result[k] for k in ('counts','groups','transitions','shared_main_wing_input_audit')},indent=2))


if __name__=='__main__':main()
