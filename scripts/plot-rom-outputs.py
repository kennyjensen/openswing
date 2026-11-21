"""Plot sampled physical ROM transfers and their independent references."""
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[1]
study=json.loads((ROOT/'docs/validation/rom-outputs.json').read_text())
assert len(study['cases'])==9
plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False,'svg.fonttype':'none'})
fig,axes=plt.subplots(2,3,figsize=(12,7),layout='constrained')
specs=[('mechanical',None,0,0,'Loaded axial spring','Displacement / engine setting (m)'),
       ('rigid',4,1,1,'Rigid wing with circulation lag','Normal aerodynamic load / gust (N s/m²)'),
       ('coupled',8,1,1,'Coupled heave/pitch, N = 8','Normal inertial load / gust (N s/m²)')]
for column,(kind,panels,j,i,title,unit) in enumerate(specs):
    case=next(c for c in study['cases'] if c['spec']==({'kind':kind} if panels is None else {'kind':kind,'panels':panels}))
    omega=case['frequencies_rad_per_s']
    for key,color,style,label in [('reference','#303b45','-','Independent equations'),('full','#9361a6','x','Full descriptor'),('computed','#137c79','o','Reduced model')]:
        z=np.array(case[key]['real'])[:,j,i]+1j*np.array(case[key]['imag'])[:,j,i]
        axes[0,column].plot(omega,abs(z),style,color=color,label=label,fillstyle='none',markersize=7)
        axes[1,column].plot(omega,np.angle(z,deg=True),style,color=color,fillstyle='none',markersize=7)
    axes[0,column].set(title=title,ylabel=unit)
    axes[1,column].set(xlabel='Angular frequency (rad/s)',ylabel='Phase (degrees)')
    for ax in axes[:,column]:ax.grid(alpha=.2)
fig.legend(*axes[0,0].get_legend_handles_labels(),loc='outside lower center',ncol=3,frameon=False)
fig.suptitle('Physical reduced-order outputs: sampled transfer comparisons\nOriginal analytical models; not an ASWING-executable or experimental validation',fontsize=12)
for extension in ['svg','pdf','png']:
    target=ROOT/f'docs/validation/rom-outputs.{extension}';fig.savefig(target,dpi=160);print(target.relative_to(ROOT))
