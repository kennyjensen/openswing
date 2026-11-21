"""Standalone equal-aspect field plots from the reproducible survey study."""
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[1]
study=json.loads((ROOT/'docs/validation/flow-survey.json').read_text())
cases={c['name']:c for c in study['cases']}
plt.rcParams.update({'font.size':9,'svg.fonttype':'none','savefig.facecolor':'white'})
fig,axes=plt.subplots(2,2,figsize=(11,8.4),layout='constrained')
for ax,(name,component,quantity,title) in zip(axes.ravel(),[
    ('horseshoe_integrals','lifting','normal','Regularized lifting-vortex field'),
    ('body_integrals','volume','speed','Slender-body sources and doublets'),
    ('oblique_earth_gust','gust','normal','Oblique Earth-plane affine gust'),
    ('momentum_jet','jet','speed','Propeller jet: 100 N thrust, 3 N m torque'),
]):
    case=cases[name];out=case['result'];p=out['plane'];u,v=np.meshgrid(p['u'],p['v']);shape=u.shape
    values=np.array(out['plane_velocity'][component]).reshape(*shape,3);valid=np.array(out['valid']).reshape(shape)
    color=values[:,:,2] if quantity=='normal' else np.linalg.norm(values,axis=2);color=np.ma.masked_where(~valid,color)
    options=dict(cmap='RdBu_r',vmin=-np.max(abs(color)),vmax=np.max(abs(color))) if quantity=='normal' else dict(cmap='viridis',vmin=0)
    im=ax.pcolormesh(u,v,color,shading='nearest',rasterized=False,**options)
    stride=2;selection=np.s_[::stride,::stride];du=np.ma.masked_where(~valid,values[:,:,0]);dv=np.ma.masked_where(~valid,values[:,:,1])
    maximum=float(np.max(np.hypot(du,dv)));arrow_scale=maximum/(min(np.diff(p['u'])[0],np.diff(p['v'])[0])*stride*.7) if maximum else 1.
    ax.quiver(u[selection],v[selection],du[selection],dv[selection],angles='xy',scale_units='xy',scale=arrow_scale,color='black',width=.003,pivot='middle')
    if np.any(~valid):ax.scatter(u[~valid],v[~valid],marker='x',color='gray',s=14,label='Body interior masked');ax.legend(loc='upper left',fontsize=7)
    ax.set_aspect('equal');ax.set(xlabel='u [input L]',ylabel='v [input L]',title=title)
    fig.colorbar(im,ax=ax,label=('Normal velocity' if quantity=='normal' else 'Speed')+' [input L/T]',shrink=.8)
    ax.set_xlabel(f"u [input L]\n{out['coordinates'].capitalize()} coordinates; arrows show in-plane velocity.\nMaximum scaled reference error: {case['checks']['maximum_scaled_reference_error']:.2g}",fontsize=8)
fig.suptitle('OpenSwing external velocity surveys\nCurrent fields, common velocity definitions and independent integral references',fontsize=13)
for suffix in ('svg','pdf'):fig.savefig(ROOT/f'docs/validation/flow-survey.{suffix}',metadata={'Creator':'OpenSwing flow survey verification'})
fig.savefig('/tmp/openswing-flow-survey-figure.png',dpi=130)
print('Wrote docs/validation/flow-survey.svg and .pdf')
