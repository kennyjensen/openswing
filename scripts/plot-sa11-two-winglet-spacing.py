"""Plot saved upper/lower-winglet comparisons; no solver calls."""
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

root=Path(__file__).resolve().parents[1]; folder=root/'artifacts/isae/sa11-two-winglet-spacing-20261108'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
data=json.loads((folder/'analysis.json').read_text()); check=json.loads((folder/'verification.json').read_text())
plan=json.loads((folder/'plan.json').read_text())
assert check['analysis_sha256']==sha(folder/'analysis.json')
palette=(root/'web/plot-colors.js').read_text()
colors=re.findall(r'#[0-9a-fA-F]{6}',re.search(r'export const plotColors = Object.freeze\(\[(.*?)\]\);',palette,re.S)[1])
fig,axes=plt.subplots(1,3,figsize=(12,4.3),layout='constrained')
for j,label in enumerate(('0_70','0_80')):
    rows=[r for r in data['cases'] if r['case']['label']==label]; speed=int(rows[0]['case']['condition']['speed'])
    path=root/rows[0]['case']['table']; assert sha(path)==plan['pins'][str(path.relative_to(root))]
    raw=[list(map(float,r.split())) for r in path.read_text().splitlines() if len(r.split())==82 and r.split()[0].isdigit()][:21]
    for ax,key,col in ((axes[0],'CL',77),(axes[1],'CD',78)):
        ax.plot([r[71] for r in raw],[r[col] for r in raw],color=colors[j],label=f'ASWING archive, {speed} m/s')
        valid=[r for r in rows if r['status']=='COMPUTED_DIAGNOSTIC']
        ax.plot([r['case']['alpha'] for r in valid],[r['values'][key] for r in valid],'o',color=colors[j],label=f'OpenSwing, {speed} m/s',markersize=5)
        invalid=[r for r in rows if r['status']!='COMPUTED_DIAGNOSTIC']
        ax.plot([r['case']['alpha'] for r in invalid],[r['values'][key] for r in invalid],'x',color=colors[j],markersize=7)
    axes[2].plot([r['case']['alpha'] for r in rows],[r['maximum_normal_mach'] for r in rows],'o',color=colors[j],label=f'{speed} m/s')
axes[0].set_ylabel('Lift coefficient CL'); axes[0].set_title('Archive stays nearly linear')
axes[1].set_ylabel('Total drag coefficient CD'); axes[1].set_title('Raw forces; no plotting allowance')
axes[2].set_ylabel('Maximum section-normal Mach'); axes[2].set_title('Lower-winglet root')
axes[2].axhline(1,color='#555555',linestyle='--',linewidth=1,label='Moment-law limit')
axes[0].legend(fontsize=7.5); axes[2].legend(fontsize=8)
for ax in axes:
    ax.set_xlabel('Aircraft angle of attack (degrees)'); ax.set_xlim(-.15,5.15); ax.grid(alpha=.25)
fig.suptitle('SA-11 upper/lower winglets: transferred 16.466 mm minimum spacing',fontsize=12)
fig.supxlabel('OpenSwing sampled only at 0°, 1°, 5°; × denotes force diagnostics with unavailable moment.',fontsize=9)
for ext in ('png','svg'):
    path=folder/f'two-winglet-spacing.{ext}'; assert not path.exists(); fig.savefig(path,dpi=160)
plt.close(fig)
(folder/'plot-provenance.json').write_text(json.dumps(dict(analysis_sha256=sha(folder/'analysis.json'),
    verification_sha256=sha(folder/'verification.json'),script_sha256=sha(Path(__file__)),palette_sha256=sha(root/'web/plot-colors.js'),
    artifacts={f'two-winglet-spacing.{ext}':sha(folder/f'two-winglet-spacing.{ext}') for ext in ('png','svg')}),indent=2)+'\n')
signal.alarm(0); print('Saved two-winglet-spacing.png and two-winglet-spacing.svg')
