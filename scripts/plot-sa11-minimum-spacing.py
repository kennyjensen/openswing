"""Plot verified SA-11 minimum-spacing polar diagnostics; no solver calls."""
import hashlib
import json
from pathlib import Path
import re
import resource
import signal

resource.setrlimit(resource.RLIMIT_AS,(512*1024**2,512*1024**2))
resource.setrlimit(resource.RLIMIT_CPU,(15,15)); signal.alarm(25)
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

root=Path(__file__).resolve().parents[1]; folder=root/'artifacts/isae/sa11-minimum-spacing-20261108'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
data=json.loads((folder/'analysis.json').read_text())
verification=json.loads((folder/'verification.json').read_text())
assert verification['analysis_sha256']==sha(folder/'analysis.json')
palette=(root/'web/plot-colors.js').read_text()
colors=re.findall(r'#[0-9a-fA-F]{6}',re.search(r'export const plotColors = Object.freeze\(\[(.*?)\]\);',palette,re.S)[1])
fig,axes=plt.subplots(1,3,figsize=(12,4.3),layout='constrained')
for j,(label,speed) in enumerate([('0_70',240),('0_80',272)]):
    rows=[r for r in data['cases'] if r['case']['label']==label]
    x=[r['case']['alpha'] for r in rows]; valid=[r['status']=='COMPUTED_DIAGNOSTIC' for r in rows]
    for key,title,color in zip(['CL','CD','CDi','Cm_origin','efficiency'],['CL','CD','CDi','Cm (origin)','Span efficiency'],colors):
        y=[r['reference_error_percent'][key] if v else None for r,v in zip(rows,valid)]
        axes[j].plot(x,y,'o-',color=color,label=title,markersize=3,linewidth=1.5)
    rejected_x=[xx for xx,v in zip(x,valid) if not v]
    if rejected_x: axes[j].axvspan(rejected_x[0]-.125,5.125,color='#555555',alpha=.12,label='Moment unavailable')
    axes[j].axhspan(-5,5,color='#00804a',alpha=.05)
    axes[j].axhline(0,color='#555555',linewidth=.7)
    axes[j].set_ylim(-5.3,5.3); axes[j].set_title(f'{speed} m/s: {sum(valid)} of 21 points match')
    axes[j].set_ylabel('Accepted-result error against archive (%)')
    axes[2].plot(x,[r['maximum_normal_mach'] for r in rows],color=colors[j],label=f'{speed} m/s',linewidth=1.8)
    for xx,r,v in zip(x,rows,valid): axes[2].plot(xx,r['maximum_normal_mach'],'o',color=colors[j],markerfacecolor=colors[j] if v else 'white',markersize=4)
axes[0].legend(fontsize=8,loc='upper left',ncol=2)
axes[2].axhline(1,color='#555555',linestyle='--',linewidth=1,label='Moment-law limit')
axes[2].set_title('Normal Mach with minimum spacing')
axes[2].set_ylabel('Maximum section-normal Mach'); axes[2].legend(fontsize=8)
for ax in axes:
    ax.set_xlabel('Aircraft angle of attack (degrees)'); ax.set_xlim(-.125,5.125); ax.grid(alpha=.25)
fig.suptitle('SA-11 upper-winglet alternative: minimum horseshoe spacing 16.466 mm',fontsize=12)
for ext in ('png','svg'):
    path=folder/f'minimum-spacing-polar.{ext}'; assert not path.exists(); fig.savefig(path,dpi=160)
plt.close(fig)
(folder/'plot-provenance.json').write_text(json.dumps(dict(analysis_sha256=sha(folder/'analysis.json'),
    verification_sha256=sha(folder/'verification.json'),script_sha256=sha(Path(__file__)),
    palette_sha256=sha(root/'web/plot-colors.js'),artifacts={f'minimum-spacing-polar.{ext}':sha(folder/f'minimum-spacing-polar.{ext}') for ext in ('png','svg')}),indent=2)+'\n')
signal.alarm(0); print('Saved minimum-spacing-polar.png and minimum-spacing-polar.svg')
