"""Publish strict structural results without treating unavailable slots as passes."""
from collections import Counter,defaultdict
import hashlib
import importlib
import importlib.metadata
import importlib.util
import json
import math
import platform
from pathlib import Path
import re
from statistics import median

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'artifacts/isae/st1-st6-current-20261103'
spec=importlib.util.spec_from_file_location('suite',ROOT/'scripts/run-isae-suite.py')
suite=importlib.util.module_from_spec(spec);spec.loader.exec_module(suite)
read=lambda p:json.loads(Path(p).read_text())
jobs=[];results={};pins={};original_timeouts=[];recoveries=[]
for adapter in ('st1','st2','structure','modes'):
    folder=BASE/adapter;plan=read(folder/'plan.json')
    assert suite.stable_code(ROOT,plan['code_sha256'])
    recovery=None
    recovery_folder=folder/('grid-recovery' if (folder/'grid-recovery/assessment.json').exists() else 'recovery180')
    if (recovery_folder/'assessment.json').exists():
        recovery=read(recovery_folder/'assessment.json')
        assert recovery['batch']['remaining']==0
        recovered_plan=read(recovery_folder/'plan.json')
        assert recovered_plan['jobs']==plan['jobs']
        assert suite.stable_code(ROOT,recovered_plan['code_sha256'])
        for p,digest in recovered_plan['input_sha256'].items():assert suite.digest(ROOT/p)==digest
        for p in (recovery_folder/'plan.json',recovery_folder/'assessment.json'):
            pins[str(p.relative_to(ROOT))]=suite.digest(p)
        recoveries.append(dict(adapter=adapter,retried_jobs=len(recovered_plan['retry_ids']),cap_seconds=180,
            execution=recovered_plan.get('execution','Same complete case in one child')))
    for job in plan['jobs']:
        key=hashlib.sha256(job['id'].encode()).hexdigest()[:20]
        path=folder/'jobs'/key/'result.json';original=read(path)
        pins[str(path.relative_to(ROOT))]=suite.digest(path)
        if original['status']=='timeout':original_timeouts.append(job['id'])
        code=plan['code_sha256']
        if recovery:
            path=ROOT/recovery['result_paths'][job['id']]
            if job['id'] in recovered_plan['retry_ids']:code=recovered_plan['code_sha256']
        result=read(path)
        assert result['execution_completed'] and result['job_id']==job['id']
        assert result.get('process_reaped') or result['execution_kind']=='inline_blocker_validation'
        assert read(path.with_name('request.json'))==dict(job=job,code_sha256=code)
        results[job['id']]=suite.checked_result(job,result);jobs.append(job)
        pins[str(path.relative_to(ROOT))]=suite.digest(path)
    pins[str((folder/'plan.json').relative_to(ROOT))]=suite.digest(folder/'plan.json')

families=[]
for case in ('ST-1','ST-2','ST-3','ST-4','ST-5'):
    selected=[j for j in jobs if j['case_id']==case]
    done=[results[j['id']] for j in selected]
    errors=defaultdict(list);by_grid=defaultdict(list)
    for r in done:
        if r['status']!='computed':continue
        for c in r.get('reference_checks',[]):
            x,y=c.get('predicted'),c.get('expected')
            if all(isinstance(v,(int,float)) and math.isfinite(v) for v in (x,y)) and abs(y)>1e-8:
                error=100*abs(x-y)/abs(y)
                errors[c['name'].split(':')[-1]].append(error)
                if case=='ST-4' and c['name'].endswith(':imaginary'):by_grid[c['name'].split(':')[0]].append(error)
    metrics={k:dict(count=len(v),median_percent=median(v),maximum_percent=max(v)) for k,v in errors.items()}
    families.append(dict(case=case,jobs=len(selected),statuses=dict(Counter(r['status'] for r in done)),
        counts=suite.output_totals(selected,results),relative_error_metrics=metrics,
        frequency_errors_by_grid={k:dict(count=len(v),median_percent=median(v),maximum_percent=max(v)) for k,v in by_grid.items()},
        job_results=[dict(id=r['job_id'],status=r['status'],counts=r['output_accounting'],
            seconds=r.get('seconds'),supervisor_seconds=r.get('supervisor_seconds'),
            error=r.get('error'),timeout_seconds=r.get('timeout_seconds'),
            mesh_gates_pass=r.get('mesh_gates_pass')) for r in done]))
st6=read(BASE/'st6-source-audit.json')
pins[str((BASE/'st6-source-audit.json').relative_to(ROOT))]=suite.digest(BASE/'st6-source-audit.json')
mesh_diagnostics={}
for adapter in ('st1','st2'):
    module=importlib.import_module(suite.ADAPTERS[adapter])
    mesh_diagnostics[adapter]=module.mesh_diagnostics([j for j in jobs if j['adapter']==adapter],results)
summary=dict(date='2026-11-03',scope='Every current registered ST-1 through ST-5 comparison; explicit ST-6 source boundary.',
    runtime=dict(python=platform.python_version(),numpy=importlib.metadata.version('numpy'),
        scipy=importlib.metadata.version('scipy'),execution='CPython; no new ST-specific browser solve'),
    report_script_sha256=suite.digest(Path(__file__)),
    tolerance='Original strict printed/output tolerances; SA 3% allowance not applied.',
    execution='One numerical child at a time, one BLAS thread; original 45-second attempts retained, selected timeout retries capped at 180 seconds.',
    original_timeouts=original_timeouts,recoveries=recoveries,
    full_families_validated=False,jobs_completed=len(jobs),families=families,ST6=st6,
    adapter_mesh_diagnostics=mesh_diagnostics,input_sha256=pins)
out=ROOT/'docs/validation/isae-st1-st6-current-20261103'
suite.write_json(out.with_suffix('.json'),summary)

def error_text(row):
    m=row['relative_error_metrics'];case=row['case']
    if not m:return 'No current numerical error estimate.'
    if case=='ST-4' and 'n64' in row['frequency_errors_by_grid']:
        fine=row['frequency_errors_by_grid']['n64'];coarse=row['frequency_errors_by_grid']['n16']
        return f"64-panel frequency median {fine['median_percent']:.4g}%, maximum {fine['maximum_percent']:.4g}%; coarse maximum {coarse['maximum_percent']:.4g}%."
    if case in ('ST-2','ST-4'):
        v=m.get('imaginary')
        if v:return f"Frequency median {v['median_percent']:.4g}%; maximum {v['maximum_percent']:.4g}%."
    keys={'ST-3':['z_m','twist_deg','Mc_prime_Nm'],'ST-5':['z-z0','tw-tw0','Mc_prime']}.get(case,[])
    labels={'z_m':'Z','z-z0':'Z','twist_deg':'twist','tw-tw0':'twist','Mc_prime_Nm':'bending moment','Mc_prime':'bending moment'}
    if keys:return '; '.join(f"{labels[k]}: {m[k]['median_percent']:.4g}% median" for k in keys if k in m)+'.'
    if case=='ST-1':return '; '.join(f"{axis.upper()}: {m['row001_sensor1_r'+axis+'_body_m']['median_percent']:.4g}% median" for axis in 'xyz')+'.'
    return '; '.join(f"{k}: {v['median_percent']:.4g}% median" for k,v in m.items())+'.'

lines=['# Current ST-1 through ST-6 test results','',
    'The requested structural rerun follows the [UA-2 assessment](isae-ua2-current-assessment-20261103.md).',
    f'All **{len(jobs)} registered jobs** have terminal records. This does not establish full-family validation.',
    'A job may be a numerical case or an explicit unsupported record; pass counts below refer to individual archived scalar comparisons.',
    'These structural comparisons run in CPython. UA-2 browser verification is reported separately; identical delivered solver files do not constitute ST-specific browser validation.',
    'Original accuracy and physical-validity gates are unchanged. Jobs run serially with one BLAS thread. Original 45-second attempts are retained; selected timeout retries use a 180-second cap on the identical numerical problem.',
    'Timeouts are resource-limited attempts without an accuracy verdict; unsupported comparisons remain in the denominator.',
    '', '| Test | Strict scalar matches | Execution | Typical error in computed values |', '|---|---:|---|---|']
for row in families:
    c=row['counts'];states=', '.join(f'{v} {k}' for k,v in row['statuses'].items())
    mesh_failures=sum(r['mesh_gates_pass'] is False for r in row['job_results'])
    if mesh_failures:states+=f'; {mesh_failures} mesh checks fail'
    lines.append(f"| {row['case']} | {c['passed']:,}/{c['required']:,} | {states} | {error_text(row)} |")
lines+=['| ST-6 | No native target | 19 original files rechecked; no numerical comparison | Not applicable. |','',
    'Percentages use nonzero reference values with magnitude greater than 1e-8; near-zero fields retain their strict absolute comparison.',
    'The table covers the registered scopes, not every unpaired plot or original variant. Full output accounting is in the machine report.',
    '', 'ST-1 retains 194 unavailable scalar comparisons and the unresolved grammar/modal setup of the other original models.',
    'ST-2 now registers 490 slots, including the eight modal jobs; the older completed 406-slot batch and interrupted five-job modal study remain historical evidence. Invalid static attachments and unpaired workbook cells remain unavailable.',
    'ST-3 covers one static snapshot on three meshes; its mesh checks pass. ST-4 covers five runnable vacuum variants plus unsupported airflow/model/aggregate records. ST-5 covers four rigid-joint snapshots on three meshes each; all four fine-mesh checks fail. Reaction display and other original configurations remain unresolved.',
    'The largest relative moment differences occur at small reference values: ST-3 has 13.48% error at -8.52e-5 N m (absolute error 1.149e-5 N m); ST-5 has 140.17% at 5e-5 N m (absolute error 7.009e-5 N m). They remain strict failures. Unless a mesh is named, median percentages cover all computed nonzero values across the declared meshes, so they differ from earlier single-mesh summaries.',
    'ST-6 contains analytical Euler curves and experimental measurements, without an attributable ASWING model/driver/output. Its analytical data are not counted as native validation.',
    '', 'The initial full-inventory planning attempt hit its 45-second cap before any numerical job. The smaller runner reuses the existing suite planners, upstream source verification, worker and strict result accounting; no physical comparison was changed.',
    'ST-2 completes the identical eight modal requests under the longer cap. ST-4 reuses its five verified 16-panel outputs and finishes ten 32/64-panel requests in separate serial children, using the original numerical and mesh verifiers. The prepared whole-case ST-4 180-second retry plan was not executed. No completed coarse solve was repeated for this recovery.',
    '', '[Machine report](isae-st1-st6-current-20261103.json). Requests, results, source hashes and any incomplete artifacts are retained under `artifacts/isae/st1-st6-current-20261103/`.']
out.with_suffix('.md').write_text('\n'.join(lines)+'\n')

p=ROOT/'docs/validation/ISAE_STATUS.md';text=p.read_text()
text=re.sub(r'\n<!-- ST-MODAL-RETRIES-IN-PROGRESS-20261103 -->.*?<!-- /ST-MODAL-RETRIES-IN-PROGRESS-20261103 -->\n','\n',text,flags=re.S)
for row in families:
    case=row['case'];c=row['counts'];states=', '.join(f'{v} {k}' for k,v in row['statuses'].items())
    old=next(line for line in text.splitlines() if line.startswith(f'| [{case}]'))
    name=old.split('|')[2].strip()
    mesh_failures=sum(r['mesh_gates_pass'] is False for r in row['job_results'])
    mesh_note=f' {mesh_failures} mesh-refinement checks fail.' if mesh_failures else ' Mesh checks pass.' if case=='ST-3' else ''
    new=f"| [{case}](docs/validation/isae-st1-st6-current-20261103.md) | {name} | {c['passed']:,}/{c['required']:,} pass | {error_text(row)} | Fresh serial rerun: {states}; {c['numerically_valid']:,} valid scalar values.{mesh_note} Other registered comparisons remain unavailable or failed. |"
    text=text.replace(old,new)
old=next(line for line in text.splitlines() if line.startswith('| [ST-6]'))
text=text.replace(old,'| [ST-6](docs/validation/isae-st1-st6-current-20261103.md) | Column buckling | — No native target | — | All 19 original files rechecked; only analytical/experimental results identified. No native numerical comparison possible. |')
p.write_text(text)
for path,prefix in [(ROOT/'docs/validation/ISAE_STATUS.md',''),(ROOT/'docs/STATUS.md','validation/'),(ROOT/'docs/validation/isae-suite-backlog.md','')]:
    text=path.read_text();notice=f'''<!-- ST1-ST6-CURRENT-20261103 -->
The [fresh structural rerun]({prefix}isae-st1-st6-current-20261103.md)
records all **{len(jobs)} current registered ST-1–ST-5 jobs**, preserving strict
tolerances, timeouts and unavailable comparisons. ST-6's 19 original files were
rechecked: no native ASWING target is identified. These are bounded comparison
results, not whole-family validation. The detailed table supersedes historical
ST counts for this current-kernel attempt.
<!-- /ST1-ST6-CURRENT-20261103 -->
'''
    if '<!-- ST1-ST6-CURRENT-20261103 -->' not in text:
        first,rest=text.split('\n',1);path.write_text(first+'\n\n'+notice+rest)
print(json.dumps([dict(case=r['case'],counts=r['counts'],statuses=r['statuses']) for r in families]))
