"""Plot retained repeated-stall histories, without another numerical solve."""
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'artifacts/isae/ua1-stall-periodic-20261102'


def read(p):return json.loads(p.read_text())


def main():
    plan=read(BASE/'plan.json')
    audit=read(BASE/('audit.json' if (BASE/'audit.json').exists() else 'grid-n320.json'))
    reference=read(BASE/'reference-DOP853.json')['rows'][:plan['cycles']*plan['reference_steps']+1]
    period=reference[plan['reference_steps']]['time']
    fig,axes=plt.subplots(3,1,figsize=(9,8),sharex=True,constrained_layout=True)
    keys=('CL','CDp_fixed','section_cl')
    for ax,key in zip(axes,keys):
        ax.plot([r['time']/period for r in reference],[r[key] for r in reference],color='#111827',lw=1.8,label='Independent equations')
    for n,color in [(320,'#d97706'),(640,'#2563eb')]:
        if str(n) not in audit['results']:continue
        rows=[]
        execution=audit.get('execution_grids',{}).get(str(n),dict(base=str(BASE.relative_to(ROOT)),segment_steps=plan['segment_steps']))
        for part in range(plan['cycles']*n//execution['segment_steps']):
            rows+=read(ROOT/execution['base']/f'n{n}-part{part:03d}/audit.json')['rows']
        assert len(rows)==plan['cycles']*n+1
        times=np.array([r['time'] for r in rows])/period
        for ax,key in zip(axes[:2],keys[:2]):
            ax.plot(times,[r[key] for r in rows],color=color,lw=.9,ls='--',label=f'OpenSwing, {n} steps/cycle')
        cl=np.array([r['section_cl'] for r in rows])
        axes[2].plot(times,np.min(cl,axis=1),color=color,lw=.9,ls='--')
        axes[2].fill_between(times,np.min(cl,axis=1),np.max(cl,axis=1),color=color,alpha=.25)
    axes[2].axhline(plan['section']['clmax'],color='#6b7280',ls=':',label='Declared upper stall limit')
    for ax,label in zip(axes,('Fixed-axis lift coefficient','Pressure drag / fixed qS','Bound-vortex section cl')):
        ax.set_ylabel(label);ax.grid(alpha=.25);ax.set_xlim(0,plan['cycles'])
    axes[0].legend(fontsize=9);axes[2].legend(fontsize=9)
    axes[2].set_xlabel('Time / heave period')
    state='Refinement complete' if audit['passed'] is not None else 'Coarse grid complete; refinement pending'
    axes[0].set_title('UA-1 stall supplement: 9°, k=0.94, peak-to-peak A/c=0.5\n'+state+'; no native ASWING comparison')
    path=ROOT/'docs/validation/isae-ua1-stall-periodic-20261102'
    for extension in ('svg','png'):fig.savefig(path.with_suffix('.'+extension),dpi=150)
    plt.close(fig)


if __name__=='__main__':main()
