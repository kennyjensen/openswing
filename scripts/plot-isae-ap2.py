"""Plot all AP2 archived position-grid cells against saved finer-mesh results."""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path


COLORS=('#ff4a3d','#ff9f1a','#ffd166','#6dd36f','#2f7bff')


def pin(path):
    raw=path.read_bytes()
    return dict(path=str(path.resolve()),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',required=True,type=Path)
    parser.add_argument('--output-prefix',required=True,type=Path)
    args=parser.parse_args()
    plan_path,report_path=args.run/'plan.json',args.run/'report.json'
    plan,report=(json.loads(p.read_text()) for p in (plan_path,report_path))
    if report['jobs_finished']!=report['jobs_planned'] or not report['current_code_unchanged']:
        raise ValueError('A terminal run with unchanged numerical code is required.')
    planned={j['id']:j for j in plan['jobs']}
    selected=[]
    for job in report['jobs']:
        if job['adapter']!='ap2' or job['target_kind']!='grid_state' or job['nominal']!=300:continue
        if {k:v for k,v in job.items() if k!='result'}!=planned[job['id']]:
            raise ValueError('Result metadata differs from frozen plan.')
        selected.append(job)
    if len(selected)!=117:raise ValueError('All 117 original cells are required.')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    plt.rcParams.update({'figure.facecolor':'#111827','axes.facecolor':'#111827','text.color':'#e5e7eb',
        'axes.labelcolor':'#e5e7eb','axes.edgecolor':'#64748b','xtick.color':'#cbd5e1','ytick.color':'#cbd5e1',
        'grid.color':'#334155','savefig.facecolor':'#111827','font.size':11})
    fig,axes=plt.subplots(1,2,figsize=(13,6.7))
    csv=['series,grid_row,grid_column,y_p_m,z_p_m,archived_ratio,predicted_ratio,physical_status']
    stats={};finite=0
    for axis,series in zip(axes,('APROPOS1','APROPOS4')):
        jobs=[j for j in selected if j['series_id']==series]
        zindices=sorted({j['source_row']['row_index'] for j in jobs})
        differences=[]
        for zindex,color in zip(zindices,COLORS):
            group=sorted([j for j in jobs if j['source_row']['row_index']==zindex],key=lambda j:j['source_row']['col_index'])
            if len(group)!=13:raise ValueError('Incomplete source grid row.')
            xs,archived,predicted=[],[],[]
            for job in group:
                row=job['source_row'];result=job['result']
                check=next(c for c in result['reference_checks'] if c['name']=='CL_CD_ratio')
                if check['expected']!=row['ratio']:raise ValueError('Archived ratio changed.')
                value=check['predicted'] if result['status']=='computed' and result['numerical_pass'] else None
                if value is not None and not math.isfinite(value):value=None
                xs.append(row['y']/.64);archived.append(row['ratio'])
                predicted.append(value if value is not None else float('nan'))
                if value is not None:
                    finite+=1;differences.append(value-row['ratio'])
                csv.append(','.join(map(str,[series,row['row_index']+1,row['col_index']+1,row['y'],row['z'],
                    row['ratio'],'' if value is None else value,result['status']])))
            label=f"z/R = {group[0]['source_row']['z_over_R']:g}"
            axis.plot(xs,archived,color=color,marker='o',markerfacecolor='none',linestyle='none',markersize=5,label=label)
            axis.plot(xs,predicted,color=color,linestyle='--',linewidth=1.4)
        axis.set_title(f"{series}: alpha {jobs[0]['alpha']:g}°")
        axis.set_xlabel('Propeller lateral position / wing half-span')
        axis.set_ylabel('CL / CD ratio')
        axis.set_xlim(0,1.02);axis.grid(True,alpha=.7);axis.legend(frameon=False,fontsize=9)
        stats[series]=dict(original_cells=len(jobs),valid_pairs=len(differences),
            rmse=math.sqrt(sum(d*d for d in differences)/len(differences)) if differences else None,
            maximum_absolute_error=max(map(abs,differences)) if differences else None)
    fig.suptitle('ISAE AP-2: all 117 archived propeller-position grid cells',fontsize=16,y=.98)
    fig.legend(handles=[Line2D([],[],color='#e5e7eb',marker='o',markerfacecolor='none',linestyle='none',label='Archived ASWING-labelled MAT ratio'),
        Line2D([],[],color='#e5e7eb',linestyle='--',label='OpenSwing distributed aero forces, nominal 300')],loc='upper center',bbox_to_anchor=(.5,.925),ncol=2,frameon=False)
    fig.text(.5,.025,'Only Engine positions are reconstructed from the original producer. Historical setup remains conditional.\n'
        'Independent cold starts; lines are visual guides. Unavailable predictions stay missing.\n'
        'Exact R5.92 exporter formulas remain unresolved. MAT storage identity is not a physical accuracy threshold.',ha='center',fontsize=10,color='#cbd5e1')
    fig.tight_layout(rect=(.01,.14,.99,.88))
    prefix=args.output_prefix;prefix.parent.mkdir(parents=True,exist_ok=True)
    for suffix in ('.png','.svg'):fig.savefig(prefix.with_suffix(suffix),dpi=160)
    plt.close(fig)
    prefix.with_suffix('.csv').write_text('\n'.join(csv)+'\n')
    metadata=dict(status='SAVED_RESULTS_NO_SOLVES',physics_calls=0,original_cells=117,finite_predictions=finite,
        missing_predictions=117-finite,mesh_selection='Predeclared finer grid m300; no selection by agreement.',
        statuses=dict(Counter(j['result']['status'] for j in selected)),statistics=stats,
        source_pins=[pin(plan_path),pin(report_path)],script=pin(Path(__file__)),
        outputs=[pin(prefix.with_suffix(s)) for s in ('.png','.svg','.csv')])
    prefix.with_suffix('.json').write_text(json.dumps(metadata,indent=2,allow_nan=False)+'\n')
    print(json.dumps({k:v for k,v in metadata.items() if k not in ('source_pins','script','outputs')},indent=2))


if __name__=='__main__':main()
