"""Plot every coupled AE-2 sensor sweep from a completed, frozen suite run.

This only reads saved results. Original NaNs and unavailable predictions remain
missing, and the predeclared m160 grid is used without selecting by agreement.
"""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path


CHANNELS = (
    ('RY_m', 'Sensor Earth Y position [mm]', 1000.),
    ('Psi_deg', 'Sensor heading [deg]', 1.),
    ('sensor_V_m_s', 'Sensor airspeed [m/s]', 1.),
    ('sensor_beta_deg', 'Sensor sideslip [deg]', 1.),
)
# Same first four comparison colors as web/plot-colors.js / VibeLattice.
COLORS = ('#ff4a3d', '#ff9f1a', '#ffd166', '#6dd36f')


def pin(path):
    raw = path.read_bytes()
    return dict(path=str(path.absolute()), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', required=True, type=Path)
    parser.add_argument('--output-prefix', required=True, type=Path)
    args = parser.parse_args()
    plan_path, report_path = args.run/'plan.json', args.run/'report.json'
    plan, report = (json.loads(p.read_text()) for p in (plan_path, report_path))
    if not report['current_code_unchanged'] or report['jobs_finished'] != report['jobs_planned']:
        raise ValueError('A complete, unchanged-code run is required.')
    planned = {j['id']:j for j in plan['jobs']}
    selected = []
    for row in report['jobs']:
        if row.get('case_id') != 'AE-2' or row.get('layup') not in ('m15_02', 'p15_02') or row['mesh'] != 'm160':
            continue
        job = {k:v for k,v in row.items() if k != 'result'}
        if job != planned.get(row['id']):
            raise ValueError('Report job differs from frozen plan: '+row['id'])
        selected.append(row)
    groups = {(layup,beta): sorted([j for j in selected if j['layup']==layup and j['condition']['beta']==beta],
                                 key=lambda j:j['condition']['speed'])
              for layup in ('m15_02','p15_02') for beta in (1,5,10,15)}
    expected = dict(m15_02=(21,21,16,15), p15_02=(31,31,27,22))
    if any(len(groups[(layup,beta)]) != count for layup, counts in expected.items()
           for beta,count in zip((1,5,10,15),counts)):
        raise ValueError('All eight coupled sweeps and their initial rows are required.')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    plt.rcParams.update({'font.size':10, 'figure.facecolor':'#111827', 'axes.facecolor':'#111827',
        'axes.edgecolor':'#64748b', 'axes.labelcolor':'#e5e7eb', 'text.color':'#e5e7eb',
        'xtick.color':'#cbd5e1', 'ytick.color':'#cbd5e1', 'grid.color':'#334155', 'savefig.facecolor':'#111827'})
    fig, axes = plt.subplots(4,2,figsize=(13,15),sharex='col')
    csv = ['layup,beta_command_deg,IAS_command_m_s,channel,archived,predicted_m160,numerically_valid,status']
    stats, plotted = {}, Counter()
    for col,layup in enumerate(('m15_02','p15_02')):
        axes[0,col].set_title(('Negative' if col==0 else 'Positive')+' coupling: ['+layup+']_S')
        for row,(name,label,scale) in enumerate(CHANNELS):
            ax=axes[row,col]; differences=[]
            for beta,color in zip((1,5,10,15),COLORS):
                xs, archive, prediction = [], [], []
                for job in groups[(layup,beta)]:
                    observation=next(o for o in job['observations'] if o['name']==name)
                    result=job['result'] or {}
                    check=next((c for c in result.get('reference_checks',[]) if c['name']==name), {})
                    raw=observation['expected']
                    valid=result.get('status')=='computed' and result.get('numerical_pass') is True
                    value=check.get('predicted') if valid else None
                    if value is not None and not math.isfinite(value):value=None
                    if raw is not None and (not math.isfinite(raw) or check.get('expected',raw)!=raw):
                        raise ValueError('Invalid or changed archived coordinate.')
                    speed=job['condition']['speed'];xs.append(speed)
                    archive.append(float('nan') if raw is None else raw*scale)
                    prediction.append(float('nan') if value is None else value*scale)
                    plotted['original_finite' if raw is not None else 'original_missing']+=1
                    plotted['prediction_finite' if value is not None else 'prediction_missing']+=1
                    if raw is not None and value is not None:differences.append((value-raw)*scale)
                    csv.append(','.join(map(str,[layup,beta,speed,name,'' if raw is None else raw,
                        '' if value is None else value,valid,result.get('status','unrun')])))
                ax.plot(xs,archive,linestyle='none',marker='o',markersize=3.3,
                        markerfacecolor='none',markeredgewidth=.85,color=color)
                ax.plot(xs,prediction,color=color,linestyle='--',linewidth=1.3)
            stats[layup+':'+name]=dict(valid_pairs=len(differences),
                rmse=math.sqrt(sum(d*d for d in differences)/len(differences)) if differences else None,
                maximum_absolute_error=max(map(abs,differences)) if differences else None,display_units=label)
            maximum_speed=max(j['condition']['speed'] for beta in (1,5,10,15) for j in groups[(layup,beta)])
            ax.set_ylabel(label);ax.grid(True,alpha=.7);ax.set_xlim(0,maximum_speed*1.02)
            if row==3:ax.set_xlabel('Commanded IAS [m/s]')
    fig.suptitle('ISAE AE-2: all eight original coupled-layup sensor sweeps',fontsize=17,y=.985)
    legend=[Line2D([],[],color=c,label=f'Commanded beta {b}°') for b,c in zip((1,5,10,15),COLORS)]
    legend += [Line2D([],[],color='#e5e7eb',linestyle='none',marker='o',markerfacecolor='none',label='Archived ASWING'),
               Line2D([],[],color='#e5e7eb',linestyle='--',label='OpenSwing, nominal 160 intervals')]
    fig.legend(handles=legend,loc='upper center',bbox_to_anchor=(.5,.962),ncol=3,frameon=False)
    fig.text(.5,.013,'All original models and sensor positions retained. Historical settings remain conditional.\n'
             'Independent cold starts; connecting lines are visual guides, not continuation trajectories.\n'
             'Missing reference/prediction values stay missing; numerical success does not establish reference or mesh agreement.',
             ha='center',fontsize=10,color='#cbd5e1')
    fig.tight_layout(rect=(.015,.055,.99,.91))
    prefix=args.output_prefix;prefix.parent.mkdir(parents=True,exist_ok=True)
    for suffix in ('.png','.svg'):fig.savefig(prefix.with_suffix(suffix),dpi=160)
    plt.close(fig)
    prefix.with_suffix('.csv').write_text('\n'.join(csv)+'\n')
    metadata=dict(status='SAVED_RESULT_PLOT_NO_SOLVES',physics_calls=0,selected_jobs=len(selected),
        unique_original_rows=len(selected),finite_and_missing_counts=dict(plotted),
        selected_mesh='m160, declared in advance; no choice by closeness and no mesh-pass claim',
        job_status_counts=dict(Counter(j['result']['status'] for j in selected)),
        statistics=stats,sources=[pin(plan_path),pin(report_path)],script=pin(Path(__file__)),
        outputs=[pin(prefix.with_suffix(s)) for s in ('.png','.svg','.csv')])
    prefix.with_suffix('.json').write_text(json.dumps(metadata,indent=2,allow_nan=False)+'\n')
    print(json.dumps({k:v for k,v in metadata.items() if k not in ('statistics','sources','outputs')},indent=2))


if __name__=='__main__':main()
