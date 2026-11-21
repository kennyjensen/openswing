"""Plot original continuum refinement and the applied custom wing nodes."""
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import NullFormatter
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
study=json.loads((ROOT/'docs/validation/discretization.json').read_text())
fig,axes=plt.subplots(1,2,figsize=(10,4.2),constrained_layout=True)
for spacing,values in study['refinement'].items():
    axes[0].loglog(values['counts'],np.array(values['continuum_tip_errors'])/2,'o-',label=spacing.capitalize())
counts=np.array([4,8,16]);axes[0].loglog(counts,.007*(4/counts)**2,'--',color='.5',label=r'$N^{-2}$ reference')
axes[0].set(xlabel='Beam intervals N',ylabel='Tip position error / beam length',title='90° bend under a constant tip couple',xticks=counts)
axes[0].set_xticklabels(counts);axes[0].legend(fontsize=8);axes[0].grid(True,alpha=.2)
axes[0].xaxis.set_minor_formatter(NullFormatter())
wing=next(c['result'] for c in study['cases'] if c['name']=='wing-custom-8')
nodes=wing['mesh_discretization']['beams'][0]['nodes'];fraction=np.linspace(0,1,501);theta=np.arccos(2*fraction-1)
axes[1].plot(fraction,np.sin(theta),label=r'$\sin\theta$')
axes[1].plot(fraction,np.sin(8*theta),'--',label=r'$\sin8\theta$')
for required,color,label in [(False,'#136e82','Explicit node'),(True,'#a06439','Required node')]:
    rows=[n for n in nodes if bool(n['required'])==required]
    axes[1].scatter([n['fraction'] for n in rows],[-1.3]*len(rows),c=color,s=24,label=label,zorder=3)
axes[1].axhline(-1.3,color='.6',linewidth=.5);axes[1].set(xlabel='Undeformed material arc fraction s/L',ylabel='Basis amplitude',title='Nonuniform wing: 8 physical intervals',ylim=(-1.6,1.7))
axes[1].legend(fontsize=8,ncols=2,loc='upper center');axes[1].grid(True,alpha=.2)
fig.suptitle('OpenSwing editable material mesh — internal verification',fontsize=12)
for suffix in ('svg','pdf'):fig.savefig(ROOT/f'docs/validation/discretization.{suffix}')
print('Wrote material-mesh convergence SVG and PDF.')
