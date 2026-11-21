"""Standalone comparison plots; failed solves remain gaps in each curve."""
from pathlib import Path
import json
import re
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT/'docs/validation'
plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False})
palette=re.search(r'export const plotColors = Object.freeze\(\[(.*?)\]\);',
                  (ROOT/'web/plot-colors.js').read_text(),re.S)
COLORS=re.findall(r'#[0-9a-fA-F]{6}',palette[1])


def save(fig, name):
    fig.savefig(DEST/(name+'.png'), dpi=170, bbox_inches='tight')
    fig.savefig(DEST/(name+'.svg'), bbox_inches='tight')
    plt.close(fig)


def main():
    p1 = json.loads((DEST/'isae-p1.json').read_text())
    fig, axes = plt.subplots(1,3,figsize=(12,3.7),sharey=True)
    for ax, case in zip(axes,p1['cases']):
        table=np.asarray(case['measured_RPM_CT_CP'])
        ax.scatter(table[:,0],table[:,1],c='black',s=18,label='UIUC measurements',zorder=5)
        for run in case['runs']:
            if run['diameter_name']!='nominal_9_in':continue
            on=run['viscous']=='ON'
            ax.plot(table[:,0],[r['CT'] for r in run['outputs']],color=COLORS[0] if on else COLORS[1],
                    label='OpenSwing: published CdA' if on else 'OpenSwing: CdA = 0')
        archived=np.asarray(case['archived_aswing']['ON'])
        ax.scatter(archived[:,0],archived[:,1],facecolors='none',edgecolors=COLORS[0],s=34,label='Archived ASWING: CdA on')
        ax.set(title=f"P-1 · {case['blades']} blades",xlabel='Rotation speed (RPM)')
        ax.grid(alpha=.18)
    axes[0].set_ylabel('Thrust coefficient CT')
    handles, labels=axes[0].get_legend_handles_labels()
    fig.legend(handles,labels,loc='lower center',ncol=2,bbox_to_anchor=(.5,-.1),frameon=False)
    fig.suptitle('ISAE P-1: archived curves reproduced; measured-thrust differences remain')
    fig.text(.5,-.17,'Nominal 9-inch diameter; measured power is an input. Published CdA was calibrated in the original study.',ha='center',fontsize=9)
    fig.tight_layout(rect=(0,.06,1,.96))
    save(fig,'isae-p1-comparison')

    study=json.loads((DEST/'isae-sa34.json').read_text())
    fig,axes=plt.subplots(2,2,figsize=(11,7))
    colors=COLORS[:4]
    for row,case in enumerate(study['cases']):
        for col,key in enumerate(['CL','CD']):
            ax=axes[row,col]
            for color,mode in zip(colors,study['settings']['modes']):
                records=sorted((r for r in case['cases'] if r['specification']['mode']==mode and r['specification']['panels']==200),key=lambda r:r['specification']['alpha'])
                ax.plot([r['specification']['alpha'] for r in records],
                        [r['result'][key] if r['status']=='computed' else np.nan for r in records],
                        color=color,lw=1.4,label='OpenSwing '+mode)
                rejected=[r['specification']['alpha'] for r in records if r['status']=='rejected']
                # A row of ticks below the axes shows failures without inventing a coefficient.
                ax.plot(rejected,[-.035]*len(rejected),'|',color=color,transform=ax.get_xaxis_transform(),clip_on=False)
            for i,table in enumerate(case['archived_aswing']):
                ax.scatter([r['alpha'] for r in table['rows']],[r[key] for r in table['rows']],s=12,facecolors='none',edgecolors='#666666',label='Archived ASWING' if i==0 else None)
            experiment=np.asarray(case['experiment'][key])
            ax.scatter(experiment[:,0],experiment[:,1],c='black',marker='x',s=22,label='ISAE experimental digitization',zorder=5)
            ax.set(title=f"SA-{case['case']} · {key}",xlabel='Incidence (degrees)',ylabel=key)
            ax.grid(alpha=.18)
    handles,labels=axes[0,0].get_legend_handles_labels()
    fig.legend(handles,labels,loc='lower center',ncol=3,bbox_to_anchor=(.5,.025),frameon=False,fontsize=8)
    fig.suptitle('Literal SA-3/4 inputs: discrepancies and failed solves retained (200 panels)')
    fig.text(.5,.005,'Geometry differs from the report; PG and K/F settings are sensitivities. Gaps and ticks indicate rejected solves.',ha='center',fontsize=9)
    # Mixed data/axes-coordinate failure ticks confuse tight_layout's bounds.
    fig.subplots_adjust(left=.08,right=.98,bottom=.19,top=.9,hspace=.5,wspace=.25)
    save(fig,'isae-sa34-comparison')


if __name__=='__main__':main()
