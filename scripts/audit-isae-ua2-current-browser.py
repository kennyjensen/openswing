"""Freeze and independently audit selected UA-2 built-worker continuations."""
import argparse
import gc
import importlib.util
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'artifacts/isae/ua2-displacement-time-20261103'
spec=importlib.util.spec_from_file_location('ua2_current',ROOT/'scripts/verify-isae-ua2-current-time.py')
study=importlib.util.module_from_spec(spec);spec.loader.exec_module(study)
read,write,pins,verify,digest=study.read,study.write,study.pins,study.verify,study.digest


def prepare():
    plan=read(BASE/'plan.json');summary=read(BASE/'assessment.json')
    assert summary['all_jobs_computed'] and summary['jobs_required']==8
    assert summary['fresh_jobs_passed']==summary['fresh_jobs_required']==4
    verify(plan['source_sha256']);verify(summary['input_sha256'])
    kernel={k:v for k,v in plan['source_sha256'].items() if k.startswith('openswing/')}
    assert len(kernel)==136
    manifest=read(ROOT/'dist/kernel/manifest.json')
    assert sorted(manifest)==sorted(Path(n).name for n in kernel)
    for name in manifest:
        assert digest(ROOT/'dist/kernel'/name)==kernel['openswing/'+name]
    workers=list((ROOT/'dist/assets').glob('worker-*.js'));assert len(workers)==1
    paths=[Path(__file__).resolve(),ROOT/'scripts/run-isae-ua2-current-browser.mjs',
        ROOT/'scripts/isae_ua2_browser_cutoff.py',ROOT/'web/saved-state-data.js',
        *workers,ROOT/'dist/kernel/manifest.json',
        *[ROOT/'dist/kernel'/n for n in manifest],
        *sorted(p for p in (ROOT/'dist/runtime').rglob('*') if p.is_file())]
    output=dict(plan,source_sha256={**plan['source_sha256'],**pins(paths)},
        input_sha256=pins([BASE/'plan.json',BASE/'assessment.json',
            *[ROOT/summary['report_paths'][j['id']] for j in plan['jobs']]]),
        python_report_paths=summary['report_paths'],
        worker_url='/assets/'+workers[0].name,CPython_scaled_difference=2e-8,
        full_periodic_browser_validation=False)
    write(BASE/'browser-plan.json',output)
    print(json.dumps(dict(prepared=True,browser_jobs=8,steps_per_job=16)))


def audit(panels):
    import numpy as np
    from isae_ua2_browser_cutoff import validate_checkpoint
    plan=read(BASE/'browser-plan.json');verify(plan['source_sha256']);verify(plan['input_sha256'])
    folder=BASE/f'browser-n{panels}';outcome=read(folder/'outcome.json')
    assert outcome['computed'] and outcome['error'] is None and outcome['browser_errors']==[]
    assert outcome['plan_sha256']==digest(BASE/'browser-plan.json')
    results=[];dependencies=pins([BASE/'browser-plan.json',folder/'outcome.json'])
    for job in [j for j in plan['jobs'] if j['panels']==panels]:
        sub=folder/job['id'];receipt=read(sub/'receipt.json')
        assert receipt['computed'] and receipt['job']==job['id']
        assert receipt['plan_sha256']==digest(BASE/'browser-plan.json')
        for name,value in receipt['output_sha256'].items():assert digest(sub/name)==value
        target_path=ROOT/job['target'];assert digest(target_path)==job['target_sha256']
        python_path=ROOT/plan['python_report_paths'][job['id']]
        target=read(target_path);python=read(python_path)
        assert python['passed'] or job['kind']=='legacy_replay'
        raw=study.unzip(sub/'trajectory.json.gz')
        assert raw['converged'] and raw['accepted_steps']==16 and raw['rejected_steps']==0
        rows=[study.physical(s,panels) for s in raw['snapshots']]
        assert len(rows)==len(python['physical_rows'])==len(target['rows'])==17
        np.testing.assert_allclose([r['time'] for r in rows],[r['time'] for r in target['rows']],rtol=0,atol=1e-12)
        comparison=max(study.difference(r[k],p[k]) for r,p in zip(rows,python['physical_rows'])
            for k in r if k not in ('time','order','residual'))
        local={k:max(abs(v) for r in rows for v in study.flatten(r[k])) for k in study.LOCAL}
        errors={k:float(np.max(abs(np.array([r[k] for r in rows])-np.array([r[k] for r in target['rows']]))/
            np.array(target['scales'][k]))) for k in ('CL','circulation','circulation_rate')}
        velocity=max(abs(r['velocity']-t['velocity'])/4.75 for r,t in zip(rows,target['rows']))
        position=max(abs(r['position']-t['displacement'])/.25 for r,t in zip(rows,target['rows']))
        acceleration=max(abs(r['acceleration']-t['acceleration']) for r,t in zip(rows,target['rows']))
        chart_count=sum(study.charts(s['restart']) for s in raw['snapshots'])
        assert chart_count>0
        for index in range(2,len(raw['snapshots'])):
            partial={**raw,'snapshots':raw['snapshots'][:index+1]}
            validate_checkpoint(partial,final=False,expected_end=raw['snapshots'][index]['time'])
        checks=dict(CPython=comparison<=plan['CPython_scaled_difference'],
            local_motion=max(local.values())<=study.LIMITS['local_motion'],
            waveforms=max(errors.values())<=study.LIMITS['waveform_fraction'],
            velocity=velocity<=study.LIMITS['velocity_fraction'],position=position<=study.LIMITS['position_fraction'],
            acceleration=acceleration<1e-10,
            residual=max(r['residual'] for r in rows)<study.LIMITS['normalized_residual'])
        result=dict(job=job['id'],kind=job['kind'],passed=all(checks.values()),checks=checks,
            CPython_reference_passed=python['passed'],
            maximum_CPython_scaled_difference=comparison,error_fractions=errors,
            local_motion_maxima=local,charts_checked=chart_count,accepted_BDF_records_checked=15)
        results.append(result)
        dependencies.update(pins([sub/'receipt.json',sub/'trajectory.json.gz',target_path,python_path]))
        del raw,partial,rows;gc.collect()
    verify(plan['source_sha256']);verify(dependencies)
    report=dict(passed=all(r['passed'] for r in results),panels=panels,jobs=results,
        accepted_steps=64,rejected_steps=0,new_native_passes=0,
        native_ASWING_comparison=False,full_periodic_browser_validation=False,
        source_sha256=plan['source_sha256'],input_sha256=dependencies)
    write(BASE/f'browser-audit-n{panels}.json',report)
    print(json.dumps({k:v for k,v in report.items() if k not in ('source_sha256','input_sha256')}))
    if not report['passed']:raise SystemExit(1)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('prepare','audit'))
    parser.add_argument('--panels',type=int,choices=(20,40))
    args=parser.parse_args()
    if args.action=='prepare':prepare()
    else:audit(args.panels)
