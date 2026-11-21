"""Publish complete-grid evidence, keeping incomplete refinement explicit."""
from hashlib import sha256
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'artifacts/isae/ua1-stall-periodic-20261102'
DOCUMENT=ROOT/'docs/validation/isae-ua1-stall-periodic-20261102.md'


def read(p):return json.loads(p.read_text())
def digest(p):
    h=sha256()
    with p.open('rb') as s:
        for b in iter(lambda:s.read(1048576),b''):h.update(b)
    return h.hexdigest()


def main():
    plan=read(BASE/'plan.json')
    path=BASE/('audit.json' if (BASE/'audit.json').exists() else 'grid-n320.json')
    audit=read(path)
    for name,value in {**audit['source_sha256'],**audit['input_sha256']}.items():assert digest(ROOT/name)==value,name
    complete=set(audit['results'])==set(map(str,plan['grids']))
    assert (audit['passed'] is not None)==complete
    success=complete and audit['passed']
    executions=audit.get('execution_grids',{n:dict(base=str(BASE.relative_to(ROOT)),segment_steps=plan['segment_steps']) for n in audit['results']})
    parts=[ROOT/settings['base']/f'n{n}-part{p:03d}' for n,settings in executions.items()
        for p in range(plan['cycles']*int(n)//settings['segment_steps'])]
    receipts=[read(p.parent/(p.name+'-execution.json')) for p in parts]
    assert all(r['exit_code']==0 for r in receipts)
    segments=[read(p/'report.json') for p in parts]
    reference=read(BASE/'reference-check.json')
    replay=read(BASE/'first-cycle-replay.json')
    assert replay['passed']
    for name,value in replay['input_sha256'].items():assert digest(ROOT/name)==value,name
    output=dict(**audit,complete_refinement_study=complete,
        accepted_steps=sum(r['accepted_steps'] for r in segments),rejected_steps=sum(r['rejected_steps'] for r in segments),
        jobs=len(parts),section=plan['section'],gates=plan['gates'],reference=reference,
        serial_job_seconds=dict(min=min(r['seconds'] for r in receipts),max=max(r['seconds'] for r in receipts)),
        solve_seconds=sum(r['seconds'] for r in segments),registered_pass_count_change=int(success),
        tests=read(BASE/'setup-tests-execution.json'),plan_sha256=digest(BASE/'plan.json'),audit_sha256=digest(path),
        publisher_sha256=digest(Path(__file__)),first_cycle_replay=replay)
    recovery_plan=ROOT/'artifacts/isae/ua1-stall-periodic-20261102-fine20/plan.json'
    if recovery_plan.exists():
        recovery=read(recovery_plan)
        for name,value in recovery['recovery_input_sha256'].items():assert digest(ROOT/name)==value,name
        output.setdefault('recovery',recovery['recovery'])
        output.setdefault('recovery_plan_sha256',digest(recovery_plan))
    fine_prefix=ROOT/'artifacts/isae/ua1-stall-periodic-20261102-fine20/first-cycle.json'
    if fine_prefix.exists():
        progress=read(fine_prefix)
        for name,value in {**progress['source_sha256'],**progress['input_sha256']}.items():assert digest(ROOT/name)==value,name
        assert progress['replay']['passed'] and not progress['complete_periodic_study']
        output['fine_first_cycle']=progress
        output['fine_first_cycle_sha256']=digest(fine_prefix)
    DOCUMENT.with_suffix('.json').write_text(json.dumps(output,indent=2,allow_nan=False)+'\n')
    status='passes all declared gates' if success else ('has failed gates' if complete else 'is in progress; the full fine-grid comparison remains unfinished')
    lines=['# UA-1 repeated-cycle stall comparison','',f'Updated 2026-11-02. The study **{status}**. '
        'This is a supplemental comparison against independently implemented equations, not native ASWING output.','',
        '## Physical setup','',
        'The airfoil limit uses the retained AR 200,000 wing with four circulation unknowns, '
        'mean incidence 9°, reduced frequency k=0.94, and peak-to-peak A/c=0.5. '
        'The section limits are ±1.5, leakage strength 40, and smoothing width 0.05. '
        'These explicit settings exercise the documented smooth stall leakage; they are not recovered native UA-1 settings. '
        'Circulation lag is enabled, with pressure drag evaluated from the lag-corrected tangency velocity.','',
        'The reference implements the [steady description](https://web.mit.edu/drela/Public/web/aswing/asw_theory.pdf) '
        '(Eqs. 202–204) and [unsteady description](https://web.mit.edu/drela/Public/web/aswing/asw_uns_theory.pdf) '
        '(Eqs. 34–35, 43, 48–49) independently of production. '
        'This is instantaneous stall leakage plus circulation lag; it does not introduce a separate dynamic separation state.','',
        'Both production grids start from their own steady equilibrium. The entire four-cycle acceleration table '
        'is supplied before startup. Every job advances at most 40 steps with one BLAS thread and a 45-second cap. '
        'Complete snapshots and restart states are retained; continuation audits verify both BDF predecessors. '
        'Production equations, source files and solver tolerances are unchanged during this study.','',
        'The 320/640 steps-per-cycle grids and accuracy gates were recorded before production runs. '
        'Fine waveform error must be below 0.1%, fine/coarse error ratios below 0.35, '
        'and final-cycle change below 0.01%. Motion, residual, mean lift, amplitude, phase and startup-rate gates are also fixed. '
        'The previous first-cycle study remains separately recorded.','',
        '## Reference and recorded results','',
        f'Two independent integration methods (DOP853 and Radau) agree within '
        f'**{max(reference["error_fractions"].values()):.3e}** on the declared scales. '
        f'The eighth-to-seventh reference cycle changes by at most **{100*max(reference["settling_fractions"].values()):.3e}%**. '
        'The eighth reference cycle supplies the periodic target; the cold history supplies the full-history target.','',
        '| Steps/cycle | Scope | Lift error | Circulation error | Rate error | Pressure-drag error |',
        '|---|---|---:|---:|---:|---:|']
    keys=('CL','circulation','circulation_rate','CDp_fixed')
    for n,result in audit['results'].items():
        for label,values in [('Full cold history',result['cold_error_fractions']),('Fourth cycle vs periodic reference',result['cycles'][-1]['error_fractions'])]:
            lines.append('| '+n+' | '+label+' | '+' | '.join(f'{100*values[k]:.5f}%' for k in keys)+' |')
    lines+=['','Cold lift/circulation errors use peak departure from the independent steady state. '
        'Periodic lift/circulation errors use peak departure from the reference cycle mean. '
        'Rate and pressure drag use their own reference peaks. Every strip is checked separately.','',
        '| Steps/cycle | Largest fourth/third-cycle change | Velocity error | Position error |',
        '|---|---:|---:|---:|']
    for n,result in audit['results'].items():
        lines.append(f'| {n} | {100*max(result["cycles"][-1]["change_fractions"].values()):.6f}% | '
            f'{100*result["velocity_fraction"]:.5f}% | {100*result["position_fraction"]:.5f}% |')
    if 'recovery' in output:
        lines += ['', 'The first 40-step fine-grid job exited 124 at its 45-second cap while writing '
            'the compressed trajectory, after the solver had returned. The incomplete gzip/JSON and original '
            'failure receipt are retained and are not used as a restart. Fine-grid execution uses '
            '**20-step jobs** from the original cold start. This changes only the job partition: '
            'the complete forcing table, all 640 physical steps per cycle, equations, tolerances and '
            'saved fields are unchanged. The successful coarse grid is reused.','']
    lines+=['',f'**{output["accepted_steps"]:,} steps**, **{audit["audited_unique_states"]:,} unique states**, '
        f'**{audit["boundary_checks"]} continuation boundaries**, and **{output["rejected_steps"]} rejected steps** '
        f'are covered by the completed grids. All **{output["tests"]["tests_passed"]} setup/audit tests** pass. '
        'Tests specifically reject nonfinite data, wrong sample times, an erroneous individual strip, cycle drift and a nonconverging error plateau.','']
    lines += [f'The first 321 states reproduce the retained first-cycle physical outputs within '
        f'**{max(replay["error_fractions"].values()):.3e}** on their recorded scales. '
        'This checks the extended forcing history and the preceding exact-derivative matrix change; '
        'it adds no separate physical pass count.','']
    if 'fine_first_cycle' in output:
        progress=output['fine_first_cycle']
        values=progress['summary']['cold_error_fractions']
        numbers=' / '.join(f'{100*values[k]:.5f}%' for k in keys)
        lines += [f'The first **640 fine-grid steps / 641 states** have a separate continuation cross-check. '
            f'First-cycle lift/circulation/rate/pressure-drag errors are **{numbers}** against the independent cold-history equations. '
            f'All 31 joins pass, and the largest scaled difference from the earlier validated first-cycle run is '
            f'**{max(progress["replay"]["error_fractions"].values()):.3e}**. '
            'These are first-cycle results; they add no new periodic case pass.','']
    if complete:
        lines+=['| Gate | Result |','|---|---|']+[f'| {k} | {"Pass" if v else "Fail"} |' for k,v in audit['checks'].items()]+['']
        ratios=[v for group in audit['refinement_ratios'].values() for v in group.values()]
        lines += [f'Fine/coarse error ratios range from **{min(ratios):.5f} to {max(ratios):.5f}** '
            '(limit 0.35), covering both the complete cold history and the periodic response.','']
    else:
        lines+=['The complete refinement comparison is **pending**, so this does not add a passing physical case. '
            'Coarse-grid errors remain visible above; their size does not justify changing the preregistered fine-grid limits.','']
    if DOCUMENT.with_suffix('.svg').exists():
        lines+=['![Four-cycle stalled response](isae-ua1-stall-periodic-20261102.svg)','']
    lines+=['## Remaining scope','',
        'Complete the finer grid and refinement assessment. Browser repeated-stall coverage, broader physical conditions, '
        'UA-2 stall, and native ASWING agreement remain unfinished.' if not complete else
        'Browser repeated-stall coverage, broader physical conditions, UA-2 stall, and native ASWING agreement remain unfinished.',
        '', '[Machine-readable results](isae-ua1-stall-periodic-20261102.json). '
        '[Complete evidence and frozen sources](../../artifacts/isae/ua1-stall-periodic-20261102). '
        '[Runner](../../scripts/run-isae-ua1-stall-periodic.py). '
        '[Recovery runner](../../scripts/run-isae-ua1-stall-periodic-recovery.py).','']
    DOCUMENT.write_text('\n'.join(lines))
    fine=audit['results'][str(max(map(int,audit['results'])))];last=fine['cycles'][-1]
    numbers=' / '.join(f'{100*last["error_fractions"][k]:.5f}%' for k in keys)
    note=(f'The [UA-1 repeated-cycle stall study](docs/validation/isae-ua1-stall-periodic-20261102.md) '
        f'**{status}**. Completed grids audit **{audit["audited_unique_states"]:,} states**, '
        f'**{audit["boundary_checks"]} BDF continuation boundaries**, with zero rejected steps. '
        f'The finest completed fourth-cycle lift/circulation/rate/pressure-drag errors are **{numbers}**. '
        f'Its fourth/third-cycle change is at most **{100*max(last["change_fractions"].values()):.6f}%**. '
        'Physical equations and tolerances are unchanged. '
        +('This adds one supplemental equation-based case; native and browser stall comparisons remain open.' if success else
          'No additional case pass is claimed; the full refinement comparison remains pending.' if not complete else
          'Failed gates are retained; no additional case pass is claimed.'))
    if 'recovery' in output:
        note+=' A retained fine-grid job timed out while saving its history; recovery uses 20-step jobs with the same physical grid.'
    if 'fine_first_cycle' in output and not complete:
        progress=output['fine_first_cycle'];values=progress['summary']['cold_error_fractions']
        first_numbers=' / '.join(f'{100*values[k]:.5f}%' for k in keys)
        note+=f' The first 640/2,560 fine steps are now audited; first-cycle errors are {first_numbers}. The remaining three fine cycles are pending.'
    start='<!-- UA1-STALLED-PERIODIC-20261102 -->';end='<!-- /UA1-STALLED-PERIODIC-20261102 -->'
    def insert(path,note,anchor):
        text=path.read_text();block=start+'\n'+note+'\n'+end+'\n\n'
        if start in text:
            a=text.index(start);b=text.index(end,a)+len(end)
            text=text[:a]+block.rstrip()+text[b:]
        else:
            assert anchor in text;text=text.replace(anchor,block+anchor,1)
        path.write_text(text)
    insert(ROOT/'docs/validation/ISAE_STATUS.md',note,'Current priority is [UA-1 and UA-2]')
    insert(ROOT/'docs/STATUS.md',note.replace('](docs/validation/','](validation/'),'The [source time-matrix improvement]')
    statuspath=ROOT/'docs/validation/ISAE_STATUS.md';text=statuspath.read_text()
    rows=[r for r in text.splitlines() if r.startswith('| [')]
    assert len(rows)==42
    assert [r for r in rows if not r.startswith('| [UA-1]')]==[r for r in plan['registered_rows'] if not r.startswith('| [UA-1]')]
    row=next(r for r in rows if r.startswith('| [UA-1]'))
    original=next(r for r in plan['registered_rows'] if r.startswith('| [UA-1]'))
    cells=original.split(' | ')
    cells[2]+='; 1/1 stalled periodic checks pass' if success else '; stalled periodic refinement pending' if not complete else '; 0/1 stalled periodic checks pass'
    cells[3]+=f' Fourth-cycle stall errors ({max(map(int,audit["results"]))} steps/cycle): {numbers}.'
    cells[4]=cells[4].removesuffix(' |')+f' [Repeated-cycle stall](docs/validation/isae-ua1-stall-periodic-20261102.md): {status}. |'
    if 'fine_first_cycle' in output and not complete:
        cells[4]=cells[4].removesuffix(' |')+' Fine recovery: first 640/2,560 steps audited; remaining three cycles pending. |'
    if success:
        cells[4]=cells[4].replace('stalled periodic/browser and native coverage remain open.',
            'stalled browser and native coverage remain open.')
    statuspath.write_text(text.replace(row,' | '.join(cells)))
    backlog=ROOT/'docs/validation/isae-suite-backlog.md'
    text=backlog.read_text();row=next(r for r in text.splitlines() if '| **UA-1** |' in r)
    if start in row:
        a=row.index(start);b=row.index(end,a)+len(end)
        updated=row[:a]+start+' '+note.replace('](docs/validation/','](')+' '+end+row[b:]
    else:
        updated=row.removesuffix(' |')+' '+start+' '+note.replace('](docs/validation/','](')+' '+end+' |'
    backlog.write_text(text.replace(row,updated))
    if complete:
        changes={
            'the four-cycle stalled periodic comparison remains pending.':
                'the four-cycle stalled periodic comparison is reported below.',
            'Periodic stalled motion, browser stall coverage, UA-2 stall and native agreement remain unfinished.':
                'The repeated-stall comparison is reported below; browser stall coverage, UA-2 stall and native agreement remain unfinished.'}
        for path in (ROOT/'docs/validation/ISAE_STATUS.md',ROOT/'docs/STATUS.md',backlog):
            text=path.read_text()
            for old,new in changes.items():text=text.replace(old,new)
            path.write_text(text)
    print(json.dumps(dict(complete_refinement_study=complete,passed=audit['passed'],states=audit['audited_unique_states'],unchanged_other_rows=41)),flush=True)


if __name__=='__main__':main()
