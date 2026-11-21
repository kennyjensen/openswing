"""Standalone scientific figures from the recorded lag-option study."""
from pathlib import Path
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

study=json.loads(Path('docs/validation/aero-lag.json').read_text())
cases={c['name']:c['result'] for c in study['cases']}
plt.rcParams.update({'font.size':10,'svg.fonttype':'none'})
fig,axes=plt.subplots(1,3,figsize=(13.5,4),layout='constrained')
colors={False:'#147d76',True:'#a64b16'}
for lag in [False,True]:
    label='Lag enabled' if lag else 'Lag disabled';color=colors[lag]
    result=cases[f'frequency/lag={lag}/modes=0'];omega=np.array(result['omega'])
    response=np.array(result['response']);gain=np.linalg.norm(response,axis=1)*30/(2*np.pi)
    axes[0].plot(omega/60,gain,'o',color=color,label=label)
    k=np.geomspace(.01,5,300);reference=abs((1+2j*k)/(1+4j*k)) if lag else np.ones(len(k))
    axes[0].plot(k,reference,color=color,lw=1)
    result=cases['time/lagged/0.005' if lag else 'time/algebraic/[1.0, 1.0, 1.0]']
    axes[1].plot(result['time'],np.array(result['CL'])*1e6,'o',ms=3,color=color)
    axes[1].plot(result['time'],np.array(result['expected'])*1e6,'-',color=color,lw=1)
    result=cases[f'modes/lag={lag}/span=40.0'];poles=np.array(result['poles']);reference=np.array(result['finite_reference'])
    axes[2].plot(reference[:,0],reference[:,1],'+',ms=10,color=color)
    axes[2].plot(poles[:,0],poles[:,1],'o',mfc='none',color=color)
axes[0].set_xscale('symlog',linthresh=.01)
axes[0].set(xlabel='Reduced frequency k = ωc/(2U)',ylabel='Normalized gust lift gain',title='Rigid section gust response')
axes[0].legend(frameon=False)
axes[1].set(xlabel='Time [s]',ylabel='Lift coefficient × 10⁶',title='Vertical gust ramp · U = 30 m/s')
axes[2].axvline(0,color='.6',lw=.7);axes[2].set(xlabel='Growth rate [1/s]',ylabel='Angular frequency [rad/s]',title='Heave/pitch wing · aspect ratio 40')
for ax in axes:ax.grid(alpha=.2)
fig.suptitle('Aerodynamic-lag option: computed markers and independent references',fontsize=12)
fig.savefig('docs/validation/aero-lag.svg');fig.savefig('docs/validation/aero-lag.pdf')
print('Wrote aerodynamic-lag SVG and PDF.')
