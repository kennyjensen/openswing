"""Shareable dimensional ST-5 comparison; unsupported cantilever stays explicit."""
from pathlib import Path
import json
import re
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import argparse

ROOT=Path(__file__).resolve().parents[1]
DEST=ROOT/'docs/validation'
parser=argparse.ArgumentParser()
parser.add_argument('--input',default='isae-st5.json')
parser.add_argument('--comparison',default='isae-st5-comparison.json')
parser.add_argument('--output',default='isae-st5-comparison')
parser.add_argument('--literal',action='store_true')
args=parser.parse_args()
study=json.loads((DEST/args.input).read_text())
comparison=json.loads((DEST/args.comparison).read_text())
palette=re.search(r'export const plotColors = Object.freeze\(\[(.*?)\]\);',(ROOT/'web/plot-colors.js').read_text(),re.S)
colors=re.findall(r'#[0-9a-fA-F]{6}',palette[1])
factor=4.4482216152605*.3048
fig,axes=plt.subplots(1,3,figsize=(13,4.3),sharey=True)
plt.rcParams.update({'font.size':10})
for ax,case,reduced in zip(axes,study['cases'][:3],comparison['cases'][:3]):
    final=reduced['comparisons'][-1]
    measured=np.asarray([[np.nan if v is None else v for v in row] for row in case['experiment']])
    for b in final['beams']:
        index=b['beam'];color=colors[index-1];name='Forward' if index==1 else 'Rear'
        for j,curve in enumerate(b['curves']):
            ax.plot(np.asarray(curve['y_ft'])*.3048,np.asarray(curve['Mx_lbft'])*factor,color=color,lw=1.8,
                    label=f'OpenSwing {name.lower()}' if j==0 else None)
        data=case['archived'][str(index)];rows=np.asarray(data['rows']);mx=np.asarray(data['Mx_lbft']);sel=rows[:,0]>=0
        ax.scatter(rows[sel,2]*.3048,mx[sel]*factor,s=18,facecolors='none',edgecolors=color,
                   label=f'Archived MATLAB {name.lower()}')
        values=measured[:,2*(index-1):2*index]
        ax.scatter(values[:,0]*.0254,values[:,1]*factor/12,c=color,marker='x',s=32,
                   label=f'ISAE digitization {name.lower()}',zorder=5)
    ax.set(title=case['name'].removeprefix('JW_1_').replace('_',' / '),xlabel='Spanwise coordinate y (m)')
    ax.grid(alpha=.18)
    ax.spines[['top','right']].set_visible(False)
axes[0].set_ylabel('Body-axis bending moment Mx (N m)')
fig.suptitle('ISAE ST-5: '+('literal signed distributed loads' if args.literal else 'reconstructed static loads')+', rigid joints — discrepancies remain')
handles,labels=axes[0].get_legend_handles_labels()
fig.legend(handles,labels,loc='lower center',ncol=3,frameon=False,bbox_to_anchor=(.5,.035),fontsize=9)
fig.text(.5,.006,f"{study['settings']['meshes'][-1]} intervals per beam before mandatory stations. No load fitting or span rescaling. Cantilever and custom link joint remain unvalidated.",ha='center',fontsize=9)
fig.subplots_adjust(left=.065,right=.99,top=.84,bottom=.29,wspace=.2)
for extension in ['png','svg']:
    fig.savefig(DEST/(args.output+'.'+extension),dpi=170,bbox_inches='tight')
