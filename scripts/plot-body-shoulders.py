"""Standalone figures from the source-hashed body-shoulder study."""
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[1]
study=json.loads((ROOT/'docs/validation/body-shoulders.json').read_text());cases={c['specification']['name']:c for c in study['cases']}
plt.rcParams.update({'font.size':9,'svg.fonttype':'none'})
fig,axes=plt.subplots(2,2,figsize=(11,8),layout='constrained')
out=cases['closed']['result'];field=out['plane'];p=field['plane'];u,v=np.meshgrid(p['u'],p['v']);vel=np.array(field['plane_velocity']['volume']).reshape(*u.shape,3)
valid=np.array(field['valid']).reshape(u.shape);speed=np.ma.masked_where(~valid,np.linalg.norm(vel,axis=2));ax=axes[0,0]
im=ax.pcolormesh(u,v,speed,shading='nearest',cmap='viridis');q=ax.quiver(u[::2,::2],v[::2,::2],vel[::2,::2,0],vel[::2,::2,1],angles='xy',scale_units='xy',scale=6,color='white',width=.004,pivot='mid');ax.quiverkey(q,.12,.11,1,'1 m/s',labelpos='E',labelcolor='white');ax.set_aspect('equal');ax.set(title='Closed stepped-body volume field',xlabel='x [m], at z=0.25 m',ylabel='y [m]');fig.colorbar(im,ax=ax,label='Induced speed [m/s]',shrink=.75)
ax=axes[0,1];rows=out['result']['body_shoulders'];ax.axhline(0,color='gray',linewidth=.8);ax.stem([s['t'] for s in rows],[s['force'][2] for s in rows],basefmt=' ');ax.set(xlim=(0,4),xlabel='Body station x [m]',ylabel='Concentrated force z [N]',title='Equal/opposite forces, finite pitching moment')
ax.text(.48,.95,f"Net force: {np.linalg.norm(out['result']['force']):.2g} N\nPitching moment: {out['result']['moment'][1]:.6g} N m",transform=ax.transAxes,va='top')
ax=axes[1,0];case=cases['smooth_limit'];width=np.array([r['width'] for r in case['result']['refinement']]);error=case['checks']['smooth_field_errors'];ax.loglog(width,error,'o-',label='Smooth transition → jump');ax.loglog(width,error[0]*width/width[0],'--',label='Linear width scale');ax.set(xlabel='Transition width [m]',ylabel='Velocity difference norm [m/s]',title='Convergence to the area-integrated core');ax.grid(True,which='both',alpha=.25);ax.legend()
ax=axes[1,1];snapshots=cases['time']['result']['result']['snapshots'];t=np.array([s['time'] for s in snapshots]);dense=np.linspace(t[0],t[-1],200);expected=-1.225*2*np.pi*.2**2*10*.2*np.sin(3*dense)
ax.plot(dense,expected,label='Independent body-law reaction');ax.plot(t,[s['support_moment'][1] for s in snapshots],'o',label='Computed states');ax.set(xlabel='Time [s]',ylabel='Support moment y [N m]',title='Sampled uniform-gust phase and reaction');ax.grid(alpha=.2);ax.legend()
fig.suptitle('OpenSwing concentric body-radius jumps\nWeak limits of the published slender-body laws; no added blunt-face/separation model',fontsize=12)
for suffix in ('svg','pdf'):fig.savefig(ROOT/f'docs/validation/body-shoulders.{suffix}',metadata={'Creator':'OpenSwing body shoulder validation'})
fig.savefig('/tmp/openswing-body-shoulders-figure.png',dpi=135);print('Wrote body-shoulders.svg and .pdf')
