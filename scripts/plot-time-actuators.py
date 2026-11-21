"""Standalone physical reference and temporal-error figure for inverse forcing."""
from pathlib import Path
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

root=Path(__file__).resolve().parents[1]
study=json.loads((root/'docs/validation/time-actuators.json').read_text())
plt.rcParams.update({'font.size':10,'svg.fonttype':'none'})
fig,axes=plt.subplots(1,2,figsize=(10.5,4),layout='constrained')
t=np.linspace(0,.12,101)
axes[0].plot(t,.2+t,color='black',lw=1.5,label='Independent reference: F = m a(t)')
for i,label,marker in [(2,'Solved engine · BDF2, Δt = 0.02 s','o'),(4,'Solved engine · Radau, Δt = 0.04 s','x')]:
    s=study['cases'][i]['result']['snapshots']
    axes[0].plot([x['time'] for x in s],[x['operating_values']['power.1'] for x in s],ls='none',marker=marker,label=label,ms=6)
for i,label in [(0,'BDF1 · 0.02 s'),(1,'BDF1 · 0.01 s'),(2,'BDF2 · 0.02 s'),(3,'BDF2 · 0.01 s'),(4,'Radau · 0.04 s')]:
    s=study['cases'][i]['result']['snapshots'];time=np.array([x['time'] for x in s])
    actual=np.array([x['frame']['velocity_origin_body'][0] for x in s])
    axes[1].plot(time,1000*(actual-(-10+.2*time+.5*time*time)),marker='.',label=label)
axes[0].set(ylabel='Required +x force (N)',title='One-kilogram inverse acceleration target')
axes[1].set(ylabel='Velocity error (mm/s)',title='Error against the analytic trajectory')
for ax in axes:
    ax.set_xlabel('Time (s)');ax.grid(alpha=.22);ax.legend(fontsize=8,loc='upper left')
fig.suptitle('Inverse time forcing: solved thrust and time refinement',fontsize=13)
for suffix in ['svg','pdf','png']:
    path=root/f'docs/validation/time-actuators.{suffix}';fig.savefig(path,dpi=180);print(path)
