"""Summarize authenticated ST-5 mechanics results without another solve."""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path

import assess_st5_convergence as audit

ROOT,read,sha=audit.ROOT,audit.read,audit.sha


def summarize(out):
    scope_path=ROOT/'docs/validation/isae-st5-mechanics-scope.json';scope=read(scope_path)
    assert not (out/'summary.json').exists()
    cases=[];pins={str(scope_path.relative_to(ROOT)):sha(scope_path),
                  str(Path(__file__).relative_to(ROOT)):sha(Path(__file__)),
                  str(Path(audit.__file__).relative_to(ROOT)):sha(Path(audit.__file__))}
    for entry in scope['cases']:
        path=out/entry['case']/'assessment.json';result=read(path)
        assert result['scope_sha256']==sha(scope_path)
        assert result['assessment_script_sha256']==sha(Path(audit.__file__))
        assert result['case']==entry['case'] and result['required']==entry['required']
        assert [s['level'] for s in result['levels']]==[0,1,2,3,4]
        assert all(s['physical'] for s in result['levels'])
        final=next(m for m in result['mesh_changes'] if [m['coarse'],m['fine']]==scope['convergence']['final_pair'])
        check=audit.qualify(entry['required'],result['levels'][0]['raw_native_matches'],
            {s['level']:s['physical'] for s in result['levels']},
            {k:v['passes'] for k,v in final['fields'].items()})
        assert all(result[k]==v for k,v in check.items())
        pins[str(path.relative_to(ROOT))]=sha(path)
        for receipt in result['receipts']:
            assert sha(receipt['path'])==receipt['sha256'];r=read(receipt['path'])
            assert r['exit_code']==0 and r['reaped'] and not r['timed_out']
        cases.append(dict(case=entry['case'],passed=result['passed'],required=entry['required'],qualified=result['qualified'],
            raw_matches_by_grid=[s['raw_native_matches'] for s in result['levels']],
            mesh_passed=result['mesh_passed'],mesh_required=14,
            maximum_final_mesh_percent=100*max(v['relative_change'] for v in final['fields'].values()),
            coarse_failures=result['levels'][0]['failures'],finest_failures=result['levels'][-1]['failures'],
            finest_median_nonzero_error_percent=result['levels'][-1]['median_nonzero_error_percent'],
            timing=[s['timing'] for s in result['levels'] if s['timing']],
            solve_seconds=sum(s['solve_seconds'] for s in result['levels'])))
    assert len(cases)==16 and sum(c['required'] for c in cases)==scope['distinct_required']
    timings=[t for c in cases for t in c['timing']]
    # Preserve the original PDF/source correspondence; only add predictions
    # from the already verified final grid at those same source rows.
    paper_path=ROOT/'artifacts/isae/st5-family-current-20261109/report-curves.json'
    paper=read(paper_path);pins[str(paper_path.relative_to(ROOT))]=sha(paper_path)
    for curve in paper['curves']:
        path=out/curve['case']/'run-4/level4/comparison.json';packet=read(path)
        pins[str(path.relative_to(ROOT))]=sha(path)
        for sample in curve['samples']:
            match=[r for r in packet['rows'] if r['beam']==curve['beam'] and r['source_line']==sample['source_line']]
            assert len(match)==1
            sample['converged_Mx_Nm']=match[0]['moment_body'][0]*(.112985/.0833333)
        envelope=max(abs(s['pdf_Mx_Nm']) for s in curve['samples'])
        curve['maximum_converged_error_percent_of_curve_peak']=100*max(abs(s['converged_Mx_Nm']-s['pdf_Mx_Nm']) for s in curve['samples'])/envelope
    (out/'converged-paper-curves.json').write_text(json.dumps(paper,indent=2,allow_nan=False)+'\n')
    result=dict(observed_utc=datetime.now(timezone.utc).isoformat(),scope_sha256=sha(scope_path),cases=cases,
        passed=sum(c['passed'] for c in cases),required=scope['distinct_required'],
        cases_qualified=sum(c['qualified'] for c in cases),
        mesh_passed=sum(c['mesh_passed'] for c in cases),mesh_required=224,
        physical_states_passed=80,new_states=48,reused_current_states=32,
        maximum_final_mesh_percent=max(c['maximum_final_mesh_percent'] for c in cases),
        maximum_new_child_cpu_seconds=max(t['cpu_seconds'] for t in timings),
        maximum_new_child_wall_seconds=max(t['wall_seconds'] for t in timings),
        peak_new_child_rss_kib=max(t['peak_rss_kib'] for t in timings),
        all_grid_solve_seconds=sum(c['solve_seconds'] for c in cases),
        maximum_converged_paper_error_percent_of_curve_peak=max(c['maximum_converged_error_percent_of_curve_peak'] for c in paper['curves']),
        production_changes=False,whole_family_validated=False,pins=pins,
        qualification='Explicit distinct-observation mechanics scope. Archived-grid predictions are compared with native output; five-level physical and final 0.1% convergence gates are independent. Earlier refined-grid/native discrepancies and historical fields remain required separately. No modal or modified-link implementation claim.')
    (out/'summary.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('cases','pins')}))


def plot(out):
    import resource,signal
    resource.setrlimit(resource.RLIMIT_AS,(512*1024**2,)*2)
    resource.setrlimit(resource.RLIMIT_CPU,(15,)*2);signal.alarm(25)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    paper=read(out/'converged-paper-curves.json')
    fig,axes=plt.subplots(3,2,figsize=(11,10),sharex=True)
    colors={1:'#ff0000',2:'#ff8c00'}
    for curve in paper['curves']:
        name=curve['figure'];col=0 if name.startswith('28') else 1
        row=({'b':0,'c':1,'d':2} if col==0 else {'a':0,'b':1,'c':2})[name[-1]]
        ax=axes[row,col];points=curve['samples'];color=colors[curve['beam']];x=[s['pdf_x'] for s in points]
        ax.plot(x,[s['pdf_Mx_Nm'] for s in points],color=color,lw=2.8,alpha=.45)
        ax.plot(x,[s['current_Mx_Nm'][0] for s in points],color=color,lw=1,ls='--')
        ax.plot(x,[s['converged_Mx_Nm'] for s in points],color=color,lw=1.2,ls=':')
        load=curve['case'].split('-')[-1].replace('_',' / ')
        ax.set_title(f'Fig. {name}: {load} — '+('rigid' if col==0 else 'link figure / literal roller'),fontsize=10)
        ax.set_xlim(0,1);ax.set_ylabel('Body-x bending moment (N m)');ax.grid(alpha=.2)
    for ax in axes[-1]:ax.set_xlabel('Published span coordinate y/b')
    handles=[Line2D([],[],color=c,label=label) for c,label in [(colors[1],'Forward wing'),(colors[2],'Rear wing')]]
    handles += [Line2D([],[],color='black',lw=2.8,alpha=.45,label='ASWING: report PDF'),
                Line2D([],[],color='black',ls='--',label='OpenSwing: archived-station grid'),
                Line2D([],[],color='black',ls=':',label='OpenSwing: converged refinement')]
    fig.legend(handles=handles,loc='lower center',ncol=3,fontsize=9)
    fig.suptitle('ST-5: archived-grid agreement and independent mesh convergence',fontsize=14)
    fig.tight_layout(rect=(0,.075,1,.96))
    for suffix in ('png','svg'):
        p=out/f'converged-paper-moments.{suffix}';assert not p.exists();fig.savefig(p,dpi=150)
    print('Wrote converged-paper-moments.png and .svg.')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['summarize','plot'])
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    (summarize if a.action=='summarize' else plot)(a.output.resolve())
