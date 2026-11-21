"""Scientific view of the verified derivative-rank gap and loaded geometry."""
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[1]
s=json.loads((ROOT/'docs/validation/descriptor-mass.json').read_text())
fig,axes=plt.subplots(1,2,figsize=(10,4.2),constrained_layout=True)
for name,label in [('wing-4','4 intervals'),('wing-8','8 intervals')]:
    case=next(c for c in s['cases'] if c['specification']['name']==name);r=case['result']
    values=np.array(r['mass_singular_values']);i=np.flatnonzero(values>0)
    axes[0].semilogy(i+1,values[i],'.-',label=label)
    xyz=np.array([n['position'] for n in r['base']['nodes']]);axes[1].plot(xyz[:,1],xyz[:,2],'o-',label=label)
    if name=='wing-4':
        jig=np.array([n['jig_position'] for n in r['base']['nodes']]);axes[1].plot(jig[:,1],jig[:,2],'--',color='.5',label='Undeformed axis')
axes[0].set(xlabel='Singular-value index',ylabel='Equilibrated derivative singular value',title='Resolved derivative-rank gap',ylim=(1e-20,10))
axes[1].set(xlabel='Body y [m]',ylabel='Body z [m]',title='Loaded swept/twisted flexible wing');axes[1].set_aspect('equal',adjustable='datalim')
for a in axes:a.grid(True,alpha=.2);a.legend(fontsize=9)
fig.suptitle('OpenSwing derivative-matrix verification · 30 m/s, α = 4°, gravity = 0\nThree Fourier circulation unknowns; mesh convergence remains to be established',fontsize=11)
for suffix in ('svg','pdf'):fig.savefig(ROOT/f'docs/validation/descriptor-mass.{suffix}')
print('Wrote descriptor-mass SVG/PDF.')
