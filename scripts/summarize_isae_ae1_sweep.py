"""Independently audit the complete, pinned AE-1 sweep without solver imports."""
from datetime import datetime, timezone
import argparse
import hashlib
import json
from pathlib import Path
from statistics import median
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts import isae_suite_ae1 as adapter
from scripts.isae_acceptance import apply_reference_acceptance
from scripts.replay_isae_ae1_bounded import checked_result
from scripts.finalize_isae_ae1_saved import verify_completed


def read(path):
    return json.loads(Path(path).read_text())


def audit(out, *, partial=False, output_name='summary.json'):
    plan=read(out/'plan.json');pins={};jobs=[];results={};rows=[];timings=[];physical=[]
    def pinned(path, expected):
        path=str(path)
        if path not in pins:pins[path]=hashlib.sha256(Path(path).read_bytes()).hexdigest()
        assert pins[path]==expected,path
    for path,digest in plan['pins'].items():pinned(path,digest)
    for entry in plan['entries']:
        folder=Path(entry['folder']);pinned(folder/'job.json',entry['job_sha256'])
        job=read(folder/'job.json')
        assert job['id']==entry['id'] and job['comparison_scope']==adapter.FROZEN_SCOPE
        if not (folder/'strict-result.json').exists():
            assert partial and not entry['reused']
            assert not (folder/'raw').exists() and not (folder/'terminal.json').exists(), 'Partial attempt must be investigated'
            assert job['condition'] is not None
            for c in job['observations']:
                rows.append(dict(job=job['id'],alpha=job['condition']['alpha'],speed=job['condition']['speed'],
                    mesh=job['nominal'],name=c['name'],expected=c['expected'],predicted=None,
                    absolute_error=None,error_percent=None,passed=False,strict_passed=False,reused=False,
                    availability='unrun',original_tolerance=c['tolerance'],effective_tolerance=None,
                    reference_line=c['source_line'],reference_column=c['source_column_1based']))
            jobs.append(job);results[job['id']]=dict(status='unrun',reference_checks=[])
            continue
        raw=read(folder/'strict-result.json')
        if not entry['reused'] and read(folder/'terminal.json')['returncode']!=0:
            assert verify_completed(folder)
        for pin in job['kernel_pins']+job['source_pins']+raw.get('artifact_files',[]):
            pinned(pin['path'],pin['sha256'])
        strict=checked_result(job,raw)
        assert strict['status'] in ('computed','unsupported'),strict.get('contract_error')
        view=apply_reference_acceptance(strict,relative_tolerance=.05)
        assert view['output_accounting']['required']==6
        if strict['status']=='computed':
            snapshot=read(Path(raw['artifact_directory'])/'result.json')
            restored=read(Path(raw['artifact_directory'])/'restored-result.json')
            assert snapshot['converged'] and restored['converged']
            assert len(strict['physical_checks'])==29 and all(c['passed'] for c in strict['physical_checks'])
            assert raw['operations']==dict(cold_solves=1,fresh_residuals=1,retries=0)
            values=adapter.sensor_values(snapshot['sensors'])
            assert all(c['predicted']==values[c['name']] for c in strict['reference_checks'])
            physical.extend(dict(job=job['id'],**c) for c in strict['physical_checks'])
            timings.append(dict(reused=entry['reused'],**read(folder/'receipt.json')))
        else:
            assert strict['physical_calls']==0
            assert all(c['predicted'] is None and not c['passed'] for c in strict['reference_checks'])
        originals={r['name']:r for r in job['observations']}
        for c in view['reference_checks']:
            target=originals[c['name']]
            assert c['expected']==target['expected'] and c['tolerance']==target['tolerance']
            error=None if c['predicted'] is None else abs(c['predicted']-c['expected'])
            rows.append(dict(job=job['id'],alpha=int(job['id'].split('-a')[1][:2]),
                speed=job['condition']['speed'] if job['condition'] else None,mesh=job['nominal'],
                name=c['name'],expected=c['expected'],predicted=c['predicted'],
                absolute_error=error,error_percent=100*error/abs(c['expected']) if error is not None and c['expected'] else None,
                passed=c['passed'],strict_passed=c['strict_passed'],reused=entry['reused'],
                availability='computed' if strict['status']=='computed' else 'unknown_start',
                original_tolerance=c['original_tolerance'],effective_tolerance=c['effective_tolerance'],
                reference_line=target['source_line'],reference_column=target['source_column_1based']))
        jobs.append(job)
        results[job['id']]=dict(status=strict['status'],reference_checks=strict['reference_checks'])
    mesh=adapter.mesh_diagnostics(jobs,results)
    values=[r for r in rows if r['predicted'] is not None]
    unavailable=[r for r in rows if r['predicted'] is None]
    failed=[r for r in values if not r['passed']]
    unrun=sum(r['availability']=='unrun' for r in rows)
    assert len(rows)==1200 and len(values)+unrun==1176 and len(unavailable)-unrun==24
    assert len(timings)*6==len(values) and len(physical)==29*len(timings)
    assert sum(r['reused'] for r in timings)==12
    assert len(mesh)==100
    if not partial:
        assert len(values)==1176 and len(timings)==196 and len(physical)==5684
        assert sum(not r['reused'] for r in timings)==184
        assert len({(r['alpha'],r['speed'],r['name']) for r in values})==588
        assert sum(m['status']=='COMPARED' for m in mesh)==98
    assert not any(n=='openswing' or n.startswith('openswing.') for n in sys.modules)
    errors=[r['error_percent'] for r in values if r['error_percent'] is not None]
    mesh_changes=[100*c['relative_change'] for m in mesh for c in m['channels'].values() if c['relative_change'] is not None]
    fresh=[r for r in physical if r['name']=='fresh_full_residual']
    timed=[r for r in timings if r['wall_seconds'] is not None]
    measured_memory=[r['peak_rss_kib'] for r in timings if r['peak_rss_kib'] is not None]
    summary=dict(observed_utc=datetime.now(timezone.utc).isoformat(),status='PARTIAL_SAVED_DATA_AUDIT_PASS' if partial else 'COMPLETE_SAVED_DATA_AUDIT_PASS',
        passed=sum(r['passed'] for r in rows),required=1200,valid=len(values),unavailable_unknown_start=24,unrun=unrun,failed_computed=len(failed),
        strict_passed=sum(r['strict_passed'] for r in rows),distinct_computed_native_cells=len({(r['alpha'],r['speed'],r['name']) for r in values}),
        physical_states=len(timings),new_physical_states=sum(not r['reused'] for r in timings),reused_physical_states=12,physical_checks_passed=len(physical),
        maximum_error_percent=max(errors),median_error_percent=median(errors),
        maximum_mesh_change_percent=max(mesh_changes),maximum_fresh_residual=max(r['metric'] for r in fresh),
        wall_seconds_range=[min(r['wall_seconds'] for r in timed),max(r['wall_seconds'] for r in timed)],
        peak_rss_kib=max(measured_memory),numerical_timings_unavailable=len(timings)-len(timed),
        completed_after_worker_deadline=sum(r.get('recovered_from_complete_saved_checks',False) for r in timings),
        mesh_gate='Descriptive sensitivity, no changed acceptance gate',
        relative_tolerance=.05,historical_settings_recovered=False,whole_family_validated=False,
        failed_comparisons=failed,rows=rows,mesh_diagnostics=mesh,physical_checks=physical,timings=timings,
        checked_sha256=pins,production_imports=0,physical_calls=0)
    with (out/output_name).open('x') as stream:
        json.dump(summary,stream,indent=2,allow_nan=False);stream.write('\n')
    print(json.dumps({k:v for k,v in summary.items() if k not in
        ('rows','mesh_diagnostics','physical_checks','timings','checked_sha256','failed_comparisons')},indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('folder',type=Path);parser.add_argument('--partial',action='store_true')
    parser.add_argument('--output-name',default='summary.json');args=parser.parse_args()
    audit(args.folder.resolve(),partial=args.partial,output_name=args.output_name)
