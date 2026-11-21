"""Plot the independently checked swept-line field diagnosis."""
from pathlib import Path
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[1]
D=ROOT/'docs/validation'
j=json.loads((D/'swept-lifting-line-limit.json').read_text())
assert j['status']=='PASS_FIELD_DIAGNOSIS_UNRESOLVED_SWEPT_FORCE_VELOCITY_LIMIT'
fig,axes=plt.subplots(1,3,figsize=(13.5,4.2),layout='constrained')
for sweep,color in [(0.,'#0072B2'),(45.,'#D55E00')]:
    rows=[r for r in j['prescribed']['cases'] if r['sweep_deg']==sweep]
    axes[0].plot([r['panels'] for r in rows],[r['samples'][-1]['velocity'][2] for r in rows],
                 'o-',color=color,label=f'{sweep:g}° sweep')
axes[0].axhline(-.25,color='black',ls=':',label='Unswept exact limit')
axes[0].set(xlabel='Intervals',ylabel='Tip-midpoint induced velocity (m/s)',title='Prescribed elliptic circulation')
axes[0].legend(fontsize=8)
rows=[r for r in j['cutoff_integrals'] if r['sweep_deg']==45.]
x=np.log(1/np.array([r['cutoff'] for r in rows]))
even=np.array([r['sweep_even_kernel'] for r in rows])
axes[1].plot(x,even,'o-',color='#D55E00',label='Sweep contribution')
axes[1].plot(x,even[-1]+rows[-1]['expected_logarithmic_slope']*(x-x[-1]),'k:',label='Analytical logarithmic slope')
axes[1].plot(x,[r['odd_kernel'] for r in rows],'-s',color='#0072B2',label='Unswept contribution')
axes[1].set(xlabel='log(semispan / exclusion distance)',ylabel='Induced velocity (m/s)',title='Fixed interior point, y / semispan = 0.5')
axes[1].legend(fontsize=8)
rows=j['sa14_independent_field'];n=[r['specification']['panels'] for r in rows]
for key,label,color in [('independent_wake','Trailing wake','#D55E00'),('independent_bound','Bound vortices','#0072B2')]:
    axes[2].plot(n,[r['samples'][-1][key][2] for r in rows],'o-',label=label,color=color)
axes[2].set(xlabel='Requested intervals',ylabel='Tip induced z velocity (m/s)',title='SA-14 wing only, α = 12.9°')
axes[2].legend(fontsize=8)
for ax in axes:ax.grid(alpha=.2)
fig.suptitle('Field diagnosis: no circulation fit, core change, or production modification',fontsize=12)
for ext in ['png','svg']:
    fig.savefig(D/f'swept-lifting-line-limit.{ext}',dpi=170)
plt.close(fig)
