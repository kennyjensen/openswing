"""Authenticate and summarize the complete current ST-5 static replay."""
import argparse
from datetime import datetime, timezone
from decimal import Decimal
import json
from pathlib import Path
import statistics

import assess_st5_current as check

ROOT,read,sha,verify=check.ROOT,check.read,check.sha,check.verify


def assess(out):
    assert not (out/'assessment.json').exists()
    plan=read(out/'plan.json');cases=[];paths=[out/'plan.json',Path(__file__),Path(check.__file__)]
    for case in plan['cases']:
        folder=Path(case['directory']);study=read(folder/'study.json')
        verify(study['pins']);verify(study['source_pins'])
        a=read(folder/'assessment.json');paths.extend([folder/'study.json',folder/'assessment.json'])
        assessor=Path(check.__file__) if not case['reused_current_states'] else out/'assess_st5_current_before_family.py'
        assert sha(assessor)==a['assessment_script_sha256'];paths.append(assessor)
        target=read(Path(read(folder/'plan.json')['target']))
        original=next(Path(p['path']) for p in target['source_pins'] if p['path'].endswith('.txt') and 'isae-validation' in p['path'])
        lines=original.read_text().splitlines()
        references=[(b,r) for b in target['beams'] for r in b['rows']]
        physical=[];all_failures=[];seconds=[];rss=[];field_stats=[]
        for level in (0,1):
            receipt=read(folder/f'run-{level}/execution.json')
            assert receipt['exit_code']==0 and receipt['reaped'] and not receipt['timed_out']
            verify(receipt['outputs']);verify(receipt['retained'])
            paths.append(folder/f'run-{level}/execution.json')
            packet=read(folder/f'run-{level}/level{level}/comparison.json')
            assert packet['numerical_gates_pass'] and len(packet['rows'])==case['rows']
            counts={j:0 for j in range(1,28)};failures=[];errors={j:[] for j in check.STRUCTURAL}
            for (block,ref),row in zip(references,packet['rows']):
                tokens=lines[ref['source_line']-1].split();assert tokens==ref['raw_tokens']
                values=[float(t)*s for t,s in zip(tokens,block['physical_multipliers'])]
                assert values==row['expected']
                half=[float(Decimal(10)**Decimal(Decimal(t).as_tuple().exponent))/2*s
                      for t,s in zip(tokens,block['physical_multipliers'])]
                assert half==row['half_last_place']
                for j in range(1,28):
                    difference=abs(row['values'][j]-values[j])
                    passed=difference<=.05*abs(values[j])+half[j]
                    counts[j]+=passed
                    if j in check.STRUCTURAL:
                        if values[j]:errors[j].append(100*difference/abs(values[j]))
                        if not passed:failures.append(dict(beam=block['beam'],source_line=ref['source_line'],
                            column=target['columns'][j]['name'],t=row['t_evaluated'],
                            reference=values[j],actual=row['values'][j],absolute_error=difference,
                            relative_percent=100*difference/abs(values[j]) if values[j] else None))
            for j,n in counts.items():assert a['grids'][level]['fields'][target['columns'][j]['name']]['passed']==n
            assert sum(counts[j] for j in check.STRUCTURAL)==a['grids'][level]['passed']
            all_failures.append(failures);physical.append(packet['checks']);seconds.append(packet['seconds'])
            rss.append(receipt['peak_child_rss_kib'])
            field_stats.append({target['columns'][j]['name']:statistics.median(errors[j]) if errors[j] else None
                                for j in check.STRUCTURAL})
        cases.append(dict(case=case['case'],directory=case['directory'],required=case['structural_targets'],
            passed=[g['passed'] for g in a['grids']],mesh_passed=a['mesh_passed'],mesh_required=14,
            failures=all_failures,median_nonzero_error_percent=field_stats,physical=physical,
            solve_seconds=seconds,peak_rss_kib=max(rss),
            source_decoder_failures=study.get('source_decoder_failures',[])))
    result=dict(observed_utc=datetime.now(timezone.utc).isoformat(),cases=cases,
        distinct_structural_targets=sum(c['required'] for c in cases),
        passed_by_grid=[sum(c['passed'][i] for c in cases) for i in (0,1)],
        mesh_passed=sum(c['mesh_passed'] for c in cases),mesh_required=14*len(cases),
        physical_states_passed=32,new_states=30,reused_current_states=2,
        peak_rss_kib=max(c['peak_rss_kib'] for c in cases),
        physical_solve_seconds=sum(sum(c['solve_seconds']) for c in cases),
        pins={str(p.relative_to(ROOT)):sha(p) for p in set(paths)},
        primary_passes_added=0,full_family_validated=False,production_changes=False,
        qualification='The two grids repeat the same native observations. First refinement is not converged. Literal roller outputs do not authenticate the paper modified-link implementation.')
    (out/'assessment.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('cases','pins')}))


def plot(out):
    import resource,signal
    resource.setrlimit(resource.RLIMIT_AS,(512*1024**2,)*2)
    resource.setrlimit(resource.RLIMIT_CPU,(15,)*2);signal.alarm(25)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    data=read(out/'report-curves.json')
    figure,axes=plt.subplots(3,2,figsize=(11,10),sharex=True)
    colors={1:'#ff0000',2:'#ff8c00'}
    for record in data['curves']:
        label=record['figure'];col=0 if label.startswith('28') else 1
        row=({'b':0,'c':1,'d':2} if col==0 else {'a':0,'b':1,'c':2})[label[-1]]
        ax=axes[row,col];p=record['samples'];color=colors[record['beam']]
        x=[s['pdf_x'] for s in p]
        ax.plot(x,[s['pdf_Mx_Nm'] for s in p],color=color,lw=2.4,alpha=.5)
        ax.plot(x,[s['current_Mx_Nm'][0] for s in p],color=color,ls='--',lw=1.1)
        ax.plot(x,[s['current_Mx_Nm'][1] for s in p],color=color,ls=':',lw=1.1)
        load=record['case'].split('-')[-1].replace('_',' / ')
        ax.set_title(f'Fig. {label}: {load} — '+('rigid' if col==0 else 'link figure / literal roller'),fontsize=10)
        ax.grid(alpha=.2);ax.set_xlim(0,1);ax.set_ylabel('Body-x bending moment (N m)')
    for ax in axes[-1]:ax.set_xlabel('Published span coordinate y/b')
    handles=[Line2D([],[],color=colors[1],lw=2,label='Forward wing'),
             Line2D([],[],color=colors[2],lw=2,label='Rear wing'),
             Line2D([],[],color='black',alpha=.5,lw=2.4,label='ASWING: report PDF'),
             Line2D([],[],color='black',ls='--',label='OpenSwing: archived-station grid'),
             Line2D([],[],color='black',ls=':',label='OpenSwing: subdivided grid')]
    figure.legend(handles=handles,loc='lower center',ncol=3,fontsize=9)
    figure.suptitle('ST-5: current structural moments against Part III Figures 28–29',fontsize=14)
    figure.tight_layout(rect=(0,.075,1,.96))
    for suffix in ('png','svg'):
        path=out/f'paper-moments.{suffix}';assert not path.exists();figure.savefig(path,dpi=150)
    print('Wrote paper-moments.png and paper-moments.svg.')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['assess','plot'])
    p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    (assess if args.action=='assess' else plot)(args.output.resolve())
