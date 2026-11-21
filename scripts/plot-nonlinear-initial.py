"""Standalone component-verification figures from the nonlinear initial study."""
import json,runpy
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
root=Path(__file__).resolve().parents[1]
study=json.loads((root/'docs/validation/nonlinear-initial.json').read_text());helpers=runpy.run_path(str(root/'scripts/verify-nonlinear-initial.py'))
plt.rcParams.update({'font.size':9,'svg.fonttype':'none','axes.spines.top':False,'axes.spines.right':False})
fig,axes=plt.subplots(2,3,figsize=(13,6.6),constrained_layout=True)
for row,name in enumerate(('spring','pendulum')):
    case=next(c for c in study['cases'] if c['specification']['name']==name);spec=case['specification'];result=case['result'];j=0 if name=='spring' else 1
    t=np.linspace(0,.12,301);reference=helpers['reference'](spec,t)
    axes[row,0].plot(t,reference[:,j],color='#142f4a',lw=1.6,label='Independent nonlinear ODE')
    for key,label,marker,color in [('trajectory','Radau IIA, maximum step .02','o','#b46316'),('refined','Radau IIA, maximum step .01','x','#247964')]:
        snapshots=result[key]['snapshots'];times=np.array([s['time'] for s in snapshots]);actual=np.array([helpers['physical'](spec,s) for s in snapshots]);exact=helpers['reference'](spec,times)
        axes[row,0].plot(times,actual[:,j],marker,ms=3,color=color,label=label)
        for column,index in [(1,2 if name=='spring' else 7),(2,3 if name=='spring' else 16)]:
            axes[row,column].plot(times,abs(actual[:,index]-exact[:,index]),color=color,marker=marker,ms=3,label=label)
    axes[row,0].set_ylabel('Spring extension [m]' if name=='spring' else 'Pendulum tip y [m]');axes[row,1].set_ylabel('Absolute acceleration error [m/s²]');axes[row,2].set_ylabel('Absolute force error [N]')
    axes[row,0].set_title('Finite displacement with tanh feedback' if name=='spring' else 'Finite-angle rigid pendulum')
    axes[row,1].set_title('Spring acceleration' if name=='spring' else 'Pendulum tip acceleration, y')
    axes[row,2].set_title('Controller force' if name=='spring' else 'Support reaction, y')
    for ax in axes[row]:ax.set_xlabel('Time [s]');ax.grid(alpha=.2);ax.legend(fontsize=7)
fig.suptitle('OpenSwing nonlinear physical initial conditions',fontsize=14)
fig.savefig(root/'docs/validation/nonlinear-initial.svg');fig.savefig(root/'docs/validation/nonlinear-initial.pdf');fig.savefig('/tmp/openswing-nonlinear-initial-figure.png',dpi=150)
print('Wrote nonlinear-initial.svg and .pdf')
