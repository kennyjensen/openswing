"""Plot physical trajectories and measured errors from temporal refinement."""
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[1]
study=json.loads((ROOT/'docs/validation/time-accuracy.json').read_text())
plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False,'svg.fonttype':'none'})
fig,axes=plt.subplots(2,3,figsize=(12,7),layout='constrained')
for column,(kind,title) in enumerate([('spring','Damped spring · BDF2'),('controller','Actuator-lag command step · BDF2'),('gust','Finite-wing gust ramp · Radau')]):
    cases=[c for c in study['cases'] if c['spec']['kind']==kind and 'units' not in c['spec'] and 'amplitude' not in c['spec'] and c['spec'].get('order',2)==2]
    assert len(cases)==2
    for case,color,label in zip(cases,['#a46b21','#137c79'],['Coarser tolerance','Fourfold tighter tolerance']):
        samples=case['samples'];time=np.array([s['time'] for s in samples])
        actual=np.array([s['computed'] for s in samples]);reference=np.array([s['reference'] for s in samples])
        field=2 if kind=='controller' else 0
        axes[0,column].plot(time,actual[:,field],'o-',color=color,markersize=3,label=label)
        error=np.max(abs(actual-reference)/np.array(case['error_scales']),axis=1)
        # Exact zeros have no logarithmic ordinate; leave gaps instead of
        # displaying an invented positive error floor.
        axes[1,column].semilogy(time[1:],np.ma.masked_less_equal(error[1:],0),'o-',color=color,markersize=3)
    axes[0,column].plot(time,reference[:,field],'--',color='#303b45',label='Independent reference')
    axes[0,column].set(title=title,ylabel=case['columns'][field])
    axes[1,column].set(xlabel='Time (s)',ylabel='Maximum scaled physical error')
    for ax in axes[:,column]:ax.grid(alpha=.2)
fig.legend(*axes[0,0].get_legend_handles_labels(),loc='outside lower center',ncol=3,frameon=False)
fig.suptitle('Optional temporal refinement: independent trajectory comparisons\nMeasured global errors are distinct from the accepted local discrepancy',fontsize=12)
for extension in ['svg','pdf','png']:
    target=ROOT/f'docs/validation/time-accuracy.{extension}';fig.savefig(target,dpi=160);print(target.relative_to(ROOT))
