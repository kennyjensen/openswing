"""Combine two terminal saved-history grid audits without rerunning a solve."""
import argparse
from hashlib import sha256
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--panels',type=int,choices=(20,40),required=True)
    parser.add_argument('--base-dir',type=Path,required=True)
    args=parser.parse_args();base=args.base_dir.resolve();output=base/f'audit-n{args.panels}.json'
    if output.exists():parser.error('Preserve completed combined audits')
    plan=json.loads((base/'batch-plan.json').read_text());gates=plan['gates']
    for name,digest in plan['source_sha256'].items():
        assert sha256((ROOT/name).read_bytes()).hexdigest()==digest
        assert sha256((base/'frozen-code'/name).read_bytes()).hexdigest()==digest
    audits=[];components=[]
    for steps in (80,160):
        p=base/f'audit-n{args.panels}-t{steps}.json';data=json.loads(p.read_text())
        receipt=json.loads((base/f'audit-n{args.panels}-t{steps}-execution.json').read_text())
        assert receipt['exit_code']==0 and receipt['audit_sha256']==sha256(p.read_bytes()).hexdigest()
        assert data['panels']==args.panels and data['nominal_steps']==steps
        assert data['amplitude_ratio']==.5 and data['k']==.95 and data['cycles']==8
        assert data['independent_spatial_reference'] and not data['native_ASWING_comparison']
        assert sha256((ROOT/data['auditor_script']).read_bytes()).hexdigest()==data['auditor_sha256']
        assert len(data['records'])==1 and data['records'][0]['nominal_steps']==steps
        assert data['audited_unique_snapshots']==steps*8+41
        components.append(dict(path=str(p.relative_to(ROOT)),sha256=sha256(p.read_bytes()).hexdigest(),
            auditor_script=data['auditor_script'],auditor_sha256=data['auditor_sha256']))
        audits.append(data)
    for name in ('scope','reference_periodic_measurements','reference_closure_fraction','reference_method_difference_fractions'):
        assert audits[0][name]==audits[1][name]
    records=[a['records'][0] for a in audits]
    ratio=records[-1]['cycles'][-1]['waveform_error_fraction']/records[0]['cycles'][-1]['waveform_error_fraction']
    cold_ratio=records[-1]['lift_waveform_error_fraction']/records[0]['lift_waveform_error_fraction']
    passed=records[-1]['periodic_accuracy_gates_passed'] and max(ratio,cold_ratio)<gates['successive_lift_error_ratio_maximum']
    result={k:v for k,v in audits[0].items() if k not in ('nominal_steps','acceptance')}
    result.update(records=records,audited_unique_snapshots=sum(a['audited_unique_snapshots'] for a in audits),
        periodic_check_passed=passed,periodic_refinement_ratio=ratio,lift_refinement_ratio=cold_ratio,
        auditor_script=str(Path(__file__).resolve().relative_to(ROOT)),
        auditor_sha256=sha256(Path(__file__).read_bytes()).hexdigest(),component_audits=components)
    output.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps(dict(panels=args.panels,passed=passed,audited_snapshots=result['audited_unique_snapshots'],
        periodic_error_ratio=ratio,fine_final_cycle=records[-1]['cycles'][-1])),flush=True)
    if not passed:raise SystemExit(1)


if __name__=='__main__':main()
