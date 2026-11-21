"""Plot saved SA-11 drag components; no solver calls."""
from pathlib import Path
import hashlib
import json
import re

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'artifacts/isae/sa11-drag-sampling-r1-20261108'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    stem='drag-components-v2'
    assert not (BASE/f'{stem}.png').exists()
    data=json.loads((BASE/'analysis.json').read_text())
    palette_source=ROOT/'web/plot-colors.js'
    colors=re.findall(r"'(#\w+)'",palette_source.read_text().split('export const plotColors')[1].split(']);')[0])
    fig,axes=plt.subplots(1,2,figsize=(11.4,5.3),sharey=True)
    for ax,variant,title in zip(axes,['original','combined'],['Original section inputs','Extension slope and drag inputs']):
        rows=[next(r for r in data['cases'] if r['id']==f'{s}-{variant}') for s in ['default','whole_beam','native']]
        near=np.array([r['coefficients']['CDi_near'] for r in rows]);profile=np.array([r['coefficients']['CDp'] for r in rows])
        ax.bar(np.arange(3),near,width=.6,color=colors[0],edgecolor='white',linewidth=.8)
        ax.bar(np.arange(3),profile,bottom=near,width=.6,color=colors[1],edgecolor='white',linewidth=.8)
        ax.scatter(np.arange(3),[r['coefficients']['CDi'] for r in rows],marker='D',color=colors[4],s=30,zorder=4)
        ax.axhline(.0110238,color='#222222',ls='--',lw=1.3)
        for i,r in enumerate(rows):
            ax.text(i,near[i]+profile[i]+.00035,f"{r['CD_error_percent']:+.1f}%",ha='center',fontsize=9,
                    bbox=dict(facecolor='white',edgecolor='none',pad=.8))
        ax.set_xticks(np.arange(3),['Default nodes\nwhole-beam samples\n70 strips','Native nodes\nwhole-beam samples\n64 strips','Native nodes\nnative samples\n64 strips'],fontsize=9)
        ax.set_title(title,fontsize=11);ax.set_ylim(0,.021);ax.set_axisbelow(True);ax.grid(axis='y',alpha=.25)
    axes[0].set_ylabel('Drag coefficient')
    fig.suptitle('SA-11 baseline: drag changes with endpoint and receiver sampling\nα = 1°, speed = 240 m/s, frozen influences; all states below stall/Mach limits',fontsize=12)
    handles=[Patch(color=colors[0],label='Near-field vortex drag'),Patch(color=colors[1],label='Profile drag'),
             Line2D([],[],marker='D',ls='none',color=colors[4],label='Trefftz CDi (separate)'),
             Line2D([],[],ls='--',color='#222222',label='Archived total CD')]
    fig.legend(handles=handles,loc='lower center',ncol=2,fontsize=9,bbox_to_anchor=(.5,.005))
    fig.subplots_adjust(top=.80,bottom=.27,left=.08,right=.98,wspace=.12)
    for suffix in ['png','svg']:fig.savefig(BASE/f'{stem}.{suffix}',dpi=165)
    plt.close(fig)
    (BASE/'plot-verification-v2.json').write_text(json.dumps(dict(analysis_sha256=sha(BASE/'analysis.json'),
        script_sha256=sha(Path(__file__)),palette_sha256=sha(palette_source),new_solver_calls=0,
        artifacts={s:sha(BASE/f'{stem}.{s}') for s in ['png','svg']}),indent=2)+'\n')
    print('Saved drag-components-v2.png and .svg; annotation separated from reference line.')


if __name__=='__main__':main()
