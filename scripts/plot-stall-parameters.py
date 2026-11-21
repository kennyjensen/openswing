"""Published scalar stall law with independently checked infinite-span samples."""
from pathlib import Path
import hashlib,json,runpy
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
ROOT=Path(__file__).resolve().parents[1]
study=json.loads((ROOT/'docs/validation/stall-parameters.json').read_text())
for name,wanted in study['source_sha256'].items():
    assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==wanted,name
reference=runpy.run_path(str(ROOT/'scripts/verify-stall-parameters.py'))['reference']
angles=np.linspace(-35,35,141)
fig,axes=plt.subplots(1,2,figsize=(11.5,4.7),layout='constrained')
fig.suptitle('Section stall parameters: published model sensitivity\nAnalytical infinite-span curves; markers are finite-span solver limits',fontsize=13)
groups=[([(k,.05) for k in [0,10,40,80]],r'Leakage factor $K_s$; $\Delta c_l=0.05$'),
        ([(40,w) for w in [.01,.05,.15]],r'Transition width $\Delta c_l$; $K_s=40$')]
for axis,(settings,title) in zip(axes,groups):
    for factor,width in settings:
        values=[reference(a,factor,width)['CL'] for a in angles]
        label=rf'$K_s={factor:g}$' if axis is axes[0] else rf'$\Delta c_l={width:g}$'
        line,=axis.plot(angles,values,label=label,lw=1.8)
        samples=[c for c in study['cases'] if c['specification'].get('span')==590000 and c['specification']['factor']==factor and c['specification']['width']==width]
        axis.scatter([c['specification']['alpha'] for c in samples],[c['result']['coefficients']['CL'] for c in samples],s=23,facecolors='white',edgecolors=line.get_color(),zorder=3)
    axis.axhline(1.2,color='gray',ls=':',lw=1);axis.axhline(-1.2,color='gray',ls=':',lw=1)
    axis.set(title=title,xlabel='Incidence (degrees)',ylabel='Lift coefficient',xlim=(-35,35))
    axis.grid(alpha=.2);axis.legend(fontsize=9)
fig.supxlabel('Fixed PG Mach zero; prescribed section limits ±1.2. This is model verification, not an experimental stall polar.',fontsize=9)
for ext in ['svg','pdf','png']:
    path=ROOT/f'docs/validation/stall-parameters.{ext}'
    fig.savefig(path,dpi=150);print(path)
