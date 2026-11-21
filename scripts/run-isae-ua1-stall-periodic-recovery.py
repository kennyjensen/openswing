"""Resume the fixed UA-1 fine grid in smaller jobs after a persistence timeout.

The original 40-step producer returned from dispatch and was interrupted while
writing its trajectory. Its partial file and exit 124 remain authoritative.
This runner changes only the job partition, retaining all physical time nodes.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import shutil

ROOT=Path(__file__).resolve().parents[1]
ORIGINAL=ROOT/'artifacts/isae/ua1-stall-periodic-20261102'
BASE=ROOT/'artifacts/isae/ua1-stall-periodic-20261102-fine20'
SCRIPT=Path(__file__).resolve()
spec=importlib.util.spec_from_file_location('ua1_stall_original_runner',ROOT/'scripts/run-isae-ua1-stall-periodic.py')
old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)


def prepare():
    plan=old.read(ORIGINAL/'plan.json');old.verify(plan['source_sha256'])
    failed=old.read(ORIGINAL/'n640-part000-execution.json')
    assert failed['status']=='terminal' and failed['exit_code']==124
    partial=ORIGINAL/'n640-part000/trajectory.json.gz.partial'
    assert partial.is_file() and not (ORIGINAL/'n640-part000/trajectory.json.gz').exists()
    coarse=old.read(ORIGINAL/'grid-n320.json')
    old.verify({**coarse['source_sha256'],**coarse['input_sha256']})
    BASE.mkdir(parents=True)
    names=['request-n640.json','reference-DOP853.json','reference-Radau.json',
        'reference-check.json','reference-check-execution.json']
    for name in names:shutil.copyfile(ORIGINAL/name,BASE/name)
    input_paths=[ORIGINAL/'plan.json',ORIGINAL/'grid-n320.json',
        ORIGINAL/'n640-part000-execution.json',ORIGINAL/'n640-part000/request.json',partial,
        *[BASE/name for name in names]]
    recovery=dict(original_base=str(ORIGINAL.relative_to(ROOT)),original_job_steps=plan['segment_steps'],
        job_steps=20,physical_grid_unchanged=True,production_unchanged=True,
        original_failure=dict(path=str((ORIGINAL/'n640-part000-execution.json').relative_to(ROOT)),exit_code=124,
            reason='Dispatch returned; timeout interrupted write_trajectory, leaving incomplete gzip/JSON.'),
        partial_not_used_for_restart=True,all_time_nodes_and_fields_retained=True,
        coarse_result_reused=True,reference_reused=True)
    plan.update(grids=[640],segment_steps=20,recovery=recovery,
        recovery_input_sha256={str(p.relative_to(ROOT)):old.digest(p) for p in input_paths})
    plan['source_sha256'][str(SCRIPT.relative_to(ROOT))]=old.digest(SCRIPT)
    old.write(BASE/'plan.json',plan)
    shutil.copyfile(SCRIPT,BASE/SCRIPT.name)
    print(json.dumps(dict(prepared=True,fine_jobs=128,job_steps=20,physical_grid_changed=False)),flush=True)


def combine(plan):
    coarse=old.read(ORIGINAL/'grid-n320.json')
    rows=[];inputs=dict(coarse['input_sha256']);boundaries=coarse['boundary_checks']
    for part in range(plan['cycles']*640//plan['segment_steps']):
        name=old.name_for(640,part)
        inputs.update(old.completed(BASE,name)['output_sha256'])
        result=old.read(BASE/name/'audit.json')
        rows.extend(result['rows']);boundaries+=result['boundary_checks']
    section=old.Section(**plan['section'])
    fine=old.summarize(section,640,plan['cycles'],rows,old.read(BASE/'reference-DOP853.json'),plan['reference_steps'])
    results={**coarse['results'],'640':fine}
    reference=old.read(BASE/'reference-check.json');assert reference['passed']
    gates,ratios=old.checks(results,reference['passed'],section)
    inputs.update(plan['recovery_input_sha256']);inputs.update(reference['input_sha256'])
    old.verify({**plan['source_sha256'],**inputs})
    report=dict(passed=all(gates.values()),checks=gates,refinement_ratios=ratios,results=results,
        audited_unique_states=sum(r['samples'] for r in results.values()),boundary_checks=boundaries,
        source_sha256=plan['source_sha256'],input_sha256=inputs,
        production_changed=False,native_ASWING_comparison=False,browser_validation=False,
        recovery=plan['recovery'],recovery_plan_sha256=old.digest(BASE/'plan.json'),
        execution_grids={'320':dict(base=str(ORIGINAL.relative_to(ROOT)),segment_steps=40),
                         '640':dict(base=str(BASE.relative_to(ROOT)),segment_steps=20)})
    old.write(ORIGINAL/'audit.json',report)
    print(json.dumps({k:v for k,v in report.items() if k not in ('source_sha256','input_sha256')}),flush=True)
    assert report['passed'],'Retain failed gates; do not relax them'


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=['prepare','run','segment','combine'])
    p.add_argument('--base',type=Path,default=BASE)
    p.add_argument('--steps',type=int);p.add_argument('--part',type=int);p.add_argument('--max-jobs',type=int)
    args=p.parse_args();assert args.base.resolve()==BASE
    if args.action=='prepare':prepare();return
    plan=old.read(BASE/'plan.json')
    assert plan['gates']==old.GATES and plan['grids']==[640] and plan['segment_steps']==20
    original=old.read(ORIGINAL/'plan.json')
    for key in ('section','cycles','reference_cycles','reference_steps','gates'):
        assert plan[key]==original[key],key
    old.verify({**plan['source_sha256'],**plan['recovery_input_sha256']})
    if args.action=='combine':combine(plan)
    elif args.action=='segment':old.segment(BASE,plan,args.steps,args.part)
    else:
        old.SCRIPT=SCRIPT
        old.run(BASE,plan,'production',args.max_jobs)


if __name__=='__main__':main()
