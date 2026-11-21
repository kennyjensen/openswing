"""Standalone figures for frozen frequency-grid refinement."""
from pathlib import Path
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import NullFormatter
ROOT=Path(__file__).resolve().parents[1]
study=json.loads((ROOT/'docs/validation/frequency-refinement.json').read_text());cases={c['specification']['name']:c['result'] for c in study['cases']}
plt.rcParams.update({'font.size':9,'svg.fonttype':'none'})
fig,axes=plt.subplots(2,2,figsize=(11,8),layout='constrained')
z=lambda v:np.asarray(v['real'])+1j*np.asarray(v['imag'])
ax=axes[0,0];case=cases['oscillator'];dense=np.geomspace(1,100,800);h=1/(500+10j*dense-2*dense**2)
ax.loglog(dense,abs(h),color='.6',label='Independent oscillator transfer')
for rows,marker,label in [(case['initial']['samples'],'s','Retained coarse samples'),([r for r in case['result']['samples'] if r['omega'] not in {s['omega'] for s in case['initial']['samples']}],'o','Added samples')]:
    rows=[s for s in rows if s['omega']>0];ax.loglog([r['omega'] for r in rows],[abs(z(r['responses'][0]['output']['nodes'][-1]['displacement'])[1]) for r in rows],marker,fillstyle='none' if marker=='s' else 'full',label=label)
ax.set(xlabel='Angular frequency [rad/s]',ylabel='Tip displacement gain [m/N]',title='Resolve a resonance on the same frozen pencil');ax.grid(True,which='both',alpha=.2);ax.legend(fontsize=8)
ax=axes[0,1];rows=cases['gust_phase']['result']['samples'];w=np.array([r['omega'] for r in rows]);dense=np.linspace(0,36,300)
for i,(name,shift) in enumerate([('Cosine span mode',np.pi),('Sine span mode',0)]):
    line=ax.plot(dense,(shift-.12*dense)*180/np.pi,label=name)[0]
    actual=np.unwrap(np.angle([z(r['responses'][i]['output']['global']['force'])[2] for r in rows]))*180/np.pi
    ax.plot(w,actual,'o',color=line.get_color())
ax.set(xlabel='Angular frequency [rad/s]',ylabel='Point-force phase [deg, unwrapped]',title='Recompute convected gust phase at new frequencies');ax.grid(alpha=.2);ax.legend(fontsize=8)
ax=axes[1,0];case=cases['initial_spectra'];dense=np.geomspace(.5,100,700);s=.7+1j*dense;expected=.002*(2*s+10)/(2*s*s+10*s+500)
ax.loglog(dense,abs(expected),label='Independent Laplace transform')
rows=[r for r in case['result']['samples'] if r['omega']>0];ax.loglog([r['omega'] for r in rows],[abs(z(r['responses'][1]['output']['nodes'][-1]['displacement'])[1]) for r in rows],'o',label='Computed initial-state spectrum')
ax.set(xlabel='Angular frequency [rad/s]',ylabel='Displacement spectrum [m s]',title='Preserve the initial state and σ = 0.7 /s');ax.grid(True,which='both',alpha=.2);ax.legend(fontsize=8)
ax=axes[1,1];case=cases['free_dc_gap'];dense=np.geomspace(.2,4,400);ax.loglog(dense,1/dense**2,label='Independent free-flight |−1/ω²|')
rows=[r for r in case['result']['samples'] if r['converged']];ax.loglog([r['omega'] for r in rows],[abs(z(r['responses'][0]['output']['frame']['position_earth'])[0]) for r in rows],'o',label='Computed finite-frequency response');ax.text(.05,.12,'ω = 0 remains an unresolved integrator gap',transform=ax.transAxes,fontsize=9)
ax.set_xticks([.2,.3,1,3,4],labels=['0.2','0.3','1','3','4']);ax.xaxis.set_minor_formatter(NullFormatter());ax.set(xlabel='Angular frequency [rad/s]',ylabel='Position gain [m/N]',title='Retain a physical gap while extending the grid');ax.grid(True,which='both',alpha=.2);ax.legend(fontsize=8)
fig.suptitle('OpenSwing frequency-grid refinement\nExisting samples retained exactly; additional frequencies use the original loaded equations',fontsize=12)
for suffix in ('svg','pdf'):fig.savefig(ROOT/f'docs/validation/frequency-refinement.{suffix}',metadata={'Creator':'OpenSwing frequency refinement validation'})
fig.savefig('/tmp/openswing-frequency-refinement-figure.png',dpi=135);print('Wrote frequency-refinement.svg and .pdf')
