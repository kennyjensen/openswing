"""Plot verified initial spectra and the acceleration boundary term."""
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
study=json.loads((ROOT/'docs/validation/initial-response.json').read_text())
case=next(c for c in study['cases'] if c['name']=='spring-4')
def z(value):return np.asarray(value['real'])+1j*np.asarray(value['imag'])
w=np.geomspace(.1,100,501);s=1j*w;den=2*s*s+10*s+500
q_release=(2*s+10)*.002/den;q_velocity=.02/den
samples=[v for v in case['result']['samples'] if v['omega']>0]
computed_w=[v['omega'] for v in samples]
fig,axes=plt.subplots(1,2,figsize=(10,4.2),constrained_layout=True)
axes[0].loglog(w,abs(q_release),label='Independent displacement release')
axes[0].loglog(w,abs(q_velocity),label='Independent velocity release')
for i,marker in ((1,'o'),(2,'s')):
    axes[0].loglog(computed_w,[abs(z(v['responses'][i]['output']['nodes'][-1]['displacement'])[1]) for v in samples],marker,fillstyle='none',color='black',label='Full descriptor' if i==1 else None)
axes[0].set(title='Spring–mass displacement spectra',xlabel='Angular frequency [rad/s]',ylabel='Displacement transform magnitude [m s]')
correct=s*s*q_velocity-.01
axes[1].loglog(w,abs(correct),label=r'Independent $s^2Q-v_0$')
axes[1].loglog(w,abs(s*s*q_velocity),'--',color='#b95835',label=r'Incorrect: omits $-v_0$')
axes[1].loglog(computed_w,[abs(z(v['responses'][2]['output']['sensors'][-1]['acceleration_sensor'])[1]) for v in samples],'s',fillstyle='none',color='black',label='Full descriptor accelerometer')
axes[1].set(title='Velocity release: acceleration spectrum',xlabel='Angular frequency [rad/s]',ylabel='Acceleration transform magnitude [m/s]')
for ax in axes:ax.grid(True,which='both',alpha=.15);ax.legend(fontsize=8)
fig.suptitle('OpenSwing initial-state verification · m = 2 kg, c = 10 N s/m, k = 500 N/m\nDisplacement release: q₀ = 0.002 m; velocity release: v₀ = 0.01 m/s; σ = 0',fontsize=11)
for suffix in ('svg','pdf'):fig.savefig(ROOT/f'docs/validation/initial-response.{suffix}')
print('Wrote initial-response SVG and PDF.')
