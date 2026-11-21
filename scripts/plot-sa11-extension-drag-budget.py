"""Plot the verified extension drag budget; no solver/browser execution."""
import hashlib
import json
from pathlib import Path
import re
import resource
import signal

resource.setrlimit(resource.RLIMIT_AS,(512*1024**2,512*1024**2))
resource.setrlimit(resource.RLIMIT_CPU,(15,15));signal.alarm(25)
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'artifacts/isae/sa11-extension-drag-budget-r2-20261108'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
data=json.loads((OUT/'analysis.json').read_text())
assert data['verified'] and data['plan_sha256']==sha(OUT/'plan.json')
for row in data['cases']:
    assert row['report_sha256']==sha(OUT/row['id']/'report.json')
palette=(ROOT/'web/plot-colors.js').read_text()
colors=re.findall(r'#[0-9a-fA-F]{6}',re.search(r'export const plotColors = Object.freeze\(\[(.*?)\]\);',palette,re.S)[1])
fig,axes=plt.subplots(2,2,figsize=(11.5,7.4),layout='constrained')
for i,(label,speed) in enumerate([('0_70',240),('0_80',272)]):
    subset=[r for r in data['cases'] if r['case']['original_job']['mach_label']==label]
    for n,color in zip((64,128),colors):
        rows=[r for r in subset if not r['case']['freeze_influences'] and r['case']['original_job']['settings']['panels']==n]
        axes[i,0].plot([r['settings']['alpha'] for r in rows],[r['relative_percent_errors']['CD'] for r in rows],
            'o-',color=color,label=f'Request {n}: {rows[0]["intervals"]} actual strips',linewidth=1.7,markersize=4)
    frozen=[r for r in subset if r['case']['freeze_influences']]
    axes[i,0].plot([r['settings']['alpha'] for r in frozen],[r['relative_percent_errors']['CD'] for r in frozen],
        'x',color=colors[2],label='Frozen controls, 60 strips',markersize=7)
    axes[i,0].axhspan(-5,5,color='#00804a',alpha=.07,label='5% acceptance band')
    axes[i,0].axhline(0,color='#555555',linewidth=.7)
    axes[i,0].set_ylim(-11,5.4);axes[i,0].set_ylabel('Total drag error vs archived ASWING (%)')
    axes[i,0].set_title(f'{speed} m/s: original model, minimum spacing')
    axes[i,0].legend(fontsize=8,loc='lower left')
    fine=[r for r in subset if not r['case']['freeze_influences'] and r['case']['original_job']['settings']['panels']==128]
    x=[r['settings']['alpha'] for r in fine]
    for key,title,color in zip(('near_minus_trefftz','trefftz_error','profile_minus_reference_remainder'),
        ('Near vortex minus Trefftz','Trefftz minus archive CDi','Profile minus archive remainder'),colors):
        axes[i,1].plot(x,[1e4*r['budget'][key] for r in fine],'o-',label=title,color=color,linewidth=1.5,markersize=3)
    axes[i,1].plot(x,[1e4*(r['actual']['CD']-r['reference']['CD']) for r in fine],
        'k--',label='Sum = total drag error',linewidth=1.6)
    axes[i,1].axhline(0,color='#555555',linewidth=.7)
    axes[i,1].set_title(f'{speed} m/s: drag budget, 108 strips')
    axes[i,1].set_ylabel('Drag-coefficient contribution × 10⁴')
    axes[i,1].legend(fontsize=8,loc='lower left')
    for ax in axes[i]:
        ax.set_xlabel('Aircraft angle of attack (degrees)');ax.set_xlim(-.1,5.1);ax.grid(alpha=.23)
fig.suptitle('SA-11 extended wing: drag discrepancy before stall\nArchive remainder = CD − CDi; it is not a measured profile-drag coefficient',fontsize=12)
for ext in ('png','svg'):
    path=OUT/f'extension-drag-budget.{ext}';assert not path.exists();fig.savefig(path,dpi=150)
plt.close(fig)
with (OUT/'plot-provenance.json').open('x') as stream:
    json.dump(dict(analysis_sha256=sha(OUT/'analysis.json'),script_sha256=sha(Path(__file__)),
        palette_sha256=sha(ROOT/'web/plot-colors.js'),artifacts={f'extension-drag-budget.{ext}':sha(OUT/f'extension-drag-budget.{ext}') for ext in ('png','svg')}),stream,indent=2)
signal.alarm(0);print('Saved extension-drag-budget.png and extension-drag-budget.svg')
