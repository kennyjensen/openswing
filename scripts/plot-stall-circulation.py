"""Standalone figures from the source-hashed circulation continuation study."""
import hashlib
import json
import sys
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from openswing.asw import parse_asw
from openswing.geometry import model_meshes
study=json.loads((ROOT/'docs/validation/stall-circulation.json').read_text())
for name,digest in study['source_sha256'].items():
    assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest,name
model=parse_asw((ROOT/'examples/stall-branch.asw').read_text())
plt.rcParams.update({'font.size':10,'svg.fonttype':'none'})
fig,axes=plt.subplots(2,2,figsize=(11,8),layout='constrained')
ax=axes[0,0]
for c in study['cases']:
    s=c['specification']
    if s.get('mach') is None and s['alpha']==60:
        mesh=model_meshes(model,s['panels'])[0]
        ax.plot(mesh.tm/2.95,c['result']['circulation_m2_s'],label=f"{s['panels']} intervals")
ax.set(xlabel='Normalized span position',ylabel='Circulation [m²/s]',title='60° finite wing: remaining spatial sensitivity')
ax.legend(fontsize=8);ax.grid(alpha=.2)
ax=axes[0,1]
case=next(c for c in study['cases'] if c['specification'].get('alpha')==85 and c['specification'].get('step')==.04)
trace=case['result']['solver']['trace'];arc=np.cumsum([r['step'] for r in trace])
ax.plot(arc,[r['parameter'] for r in trace],color='#006d77')
ax.axhline(1,color='gray',ls=':',lw=1)
ax.set(xlabel='Accumulated numerical arclength',ylabel='Regularization parameter λ',title='85° finite wing: folded path to λ = 1')
ax.grid(alpha=.2)
ax=axes[1,0]
refs=study['two_dimensional_limit'];positive=[c for c in refs if c['alpha']>0]
angles=[c['alpha'] for c in positive]
ax.plot(angles,[c['reference']['CD'] for c in positive],'o-',label='Independent scalar equation')
cs=[next(c for c in study['cases'] if c['specification'].get('span')==59000 and c['specification']['alpha']==a) for a in angles]
ax.plot(angles,[c['result']['coefficients']['CD'] for c in cs],'x',ms=8,label='Aspect ratio 59,000')
ax.set(xlabel='Incidence [degrees]',ylabel='Drag coefficient',title='Literal 2D model limit; no experimental claim')
ax.legend(fontsize=8);ax.grid(alpha=.2)
ax=axes[1,1]
for c in positive:ax.loglog(c['spans'],c['errors'],'o-',label=f"{c['alpha']:.0f}°")
ax.set(xlabel='Aspect ratio',ylabel='Maximum |CL/CD − scalar reference|',title='Convergence toward the independent 2D limit')
ax.legend(fontsize=8);ax.grid(alpha=.2,which='both')
fig.suptitle('OpenSwing circulation continuation — numerical evidence',fontsize=14)
for extension in ['svg','pdf']:
    fig.savefig(ROOT/f'docs/validation/stall-circulation.{extension}',metadata={'Creator':'OpenSwing'})
fig.savefig('/tmp/openswing-stall-circulation.png',dpi=140)
