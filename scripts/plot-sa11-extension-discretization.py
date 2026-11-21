"""Plot verified mesh/mode controls; no aerodynamic solves or browser jobs."""
import hashlib
import json
from pathlib import Path
import re
import resource
import signal

resource.setrlimit(resource.RLIMIT_AS,(512*1024**2,512*1024**2));resource.setrlimit(resource.RLIMIT_CPU,(15,15));signal.alarm(25)
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'artifacts/isae/sa11-extension-practical-mesh-20261108'
MODES=ROOT/'artifacts/isae/sa11-extension-modes-20261108'
read=lambda p:json.loads(p.read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
small=read(OUT/'analysis.json');modes=read(MODES/'analysis.json');plan=read(MODES/'plan.json')
assert small['verified'] and modes['verified'] and small['modes_analysis_sha256']==sha(MODES/'analysis.json')
for report in small['cases']:assert sha(OUT/report['id']/'report.json')==report['report_sha256']
for report in modes['cases']:assert sha(MODES/report['id']/'report.json')==report['report_sha256']
controls={c['control']['id']:c['control'] for c in plan['cases']}
palette=(ROOT/'web/plot-colors.js').read_text()
colors=re.findall(r'#[0-9a-fA-F]{6}',re.search(r'export const plotColors = Object.freeze\(\[(.*?)\]\);',palette,re.S)[1])
fig,axes=plt.subplots(1,2,figsize=(11.5,4.8),layout='constrained')
for ax,speed,label in zip(axes,(240,272),('0_70','0_80')):
    pointwise=[(r['actual_intervals'],r['relative_percent_errors']['CD']) for r in small['cases'] if r['case']['control']['settings']['speed']==speed]
    pointwise += [(r['intervals'],r['relative_percent_errors']['CD']) for r in controls.values() if r['settings']['speed']==speed]
    pointwise.sort();ax.plot(*zip(*pointwise),'o-',color=colors[0],label='Pointwise circulation',linewidth=2,markersize=5)
    for k,color,marker in zip((20,30,40),colors[1:],('s','^','x')):
        selected=sorted((r['intervals'],r['relative_percent_errors']['CD']) for r in modes['cases'] if r['modes']==k and r['id'].startswith('m'+label))
        ax.plot(*zip(*selected),marker+'--',color=color,label=f'{k} Fourier modes',linewidth=1.3,markersize=6)
    ax.axhspan(-5,1,color='#00804a',alpha=.08);ax.axhline(-5,color='#555555',linestyle=':',label='−5% acceptance boundary')
    ax.set_title(f'{speed} m/s, aircraft angle 3°');ax.set_xlabel('Actual structural intervals')
    ax.set_ylabel('Total drag error vs archived ASWING (%)');ax.set_ylim(-15,1);ax.set_xlim(20,114)
    ax.set_xticks((26,34,44,60,108));ax.grid(alpha=.22);ax.legend(fontsize=8,loc='lower right')
fig.suptitle('SA-11 extended wing: physical mesh matters more than Fourier count\nFixed original model and 16.466 mm minimum spacing',fontsize=12)
for ext in ('png','svg'):
    p=OUT/f'extension-discretization.{ext}';assert not p.exists();fig.savefig(p,dpi=150)
plt.close(fig)
with (OUT/'plot-provenance.json').open('x') as f:
    json.dump(dict(small_mesh_analysis_sha256=sha(OUT/'analysis.json'),modes_analysis_sha256=sha(MODES/'analysis.json'),
        script_sha256=sha(Path(__file__)),palette_sha256=sha(ROOT/'web/plot-colors.js'),
        artifacts={f'extension-discretization.{ext}':sha(OUT/f'extension-discretization.{ext}') for ext in ('png','svg')}),f,indent=2)
signal.alarm(0);print('Saved extension-discretization.png and .svg')
