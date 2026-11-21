"""Standalone comparison of retained and omitted initial-condition dynamics."""
from pathlib import Path
import json
import numpy as np
from scipy.linalg import expm
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[1]
study=json.loads((ROOT/'docs/validation/rom-initial.json').read_text())
fig,axes=plt.subplots(1,2,figsize=(10,4.5),constrained_layout=True)
for ax,name,output,title in zip(axes,['lag-truncated','unstable-truncated'],[2,0],['Omitted actuator / structural dynamics','Stable ROM omits an unstable mode']):
    case=next(c for c in study['cases'] if c['specification']['name']==name);spec=case['specification'];r=case['result'];initial=r['initial_responses'][0]
    g=np.array(spec['generator']);q=np.array(spec['physical_initials'][0]);h=np.vstack((np.eye(len(g))[:2],g[1]))
    a=np.array(r['matrices']['A']);c=np.array(r['matrices']['C']);z=np.array(initial['reduced_initial_state']);times=np.linspace(0,.7,250)
    full=[(h@expm(g*t)@q)[output] for t in times];reduced=[(c@expm(a*t)@z)[output] for t in times]
    ax.plot(times,full,color='#172c43',label='Independent full ODE');ax.plot(times,reduced,'--',color='#bc602e',label=f"ROM: {len(a)} real state(s)")
    ax.plot([p['time'] for p in initial['time_samples']],[p['full'][output] for p in initial['time_samples']],'o',color='#338477',label='Full descriptor samples')
    ax.set(xlabel='Time [s]',ylabel='Tip acceleration [m/s²]' if output==2 else 'Tip displacement [m]',title=title)
    ax.grid(alpha=.2);ax.legend(fontsize=8)
fig.suptitle('OpenSwing physical initial-condition projection\nTruncation error remains visible; full-system growth controls spectral convergence',fontsize=11)
for suffix in ('svg','pdf'):fig.savefig(ROOT/f'docs/validation/rom-initial.{suffix}')
print('Wrote rom-initial SVG/PDF.')
