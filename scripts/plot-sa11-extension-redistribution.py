"""Plot the verified redistribution experiment against its original controls."""
import hashlib
import json
import os
from pathlib import Path
import re
import resource
import signal

for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):
    assert os.environ.get(key)=='1'
resource.setrlimit(resource.RLIMIT_AS,(512*1024**2,512*1024**2))
resource.setrlimit(resource.RLIMIT_CPU,(15,15));signal.alarm(25)
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'artifacts/isae/sa11-extension-redistribution-20261108'
OLD=ROOT/'artifacts/isae/sa11-extension-mesh-limit-20261108'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
read=lambda p:json.loads(p.read_text())
new=read(OUT/'analysis.json');old=read(OLD/'analysis.json')
assert new['verified'] and old['verified']
for row in new['cases']:assert sha(OUT/row['id']/'report.json')==row['report_sha256']
group=next(g for g in old['groups'] if g['speed']==240 and g['alpha']==3)
palette=(ROOT/'web/plot-colors.js').read_text()
colors=re.findall(r'#[0-9a-fA-F]{6}',re.search(r'export const plotColors = Object.freeze\(\[(.*?)\]\);',palette,re.S)[1])
fig,axes=plt.subplots(1,2,figsize=(11,4.8),layout='constrained')
rows=new['cases'];counts=[r['actual_intervals'] for r in rows]
axes[0].plot(counts,[r['original_CD_error'] for r in rows],'o-',color=colors[0],label='Original minimum-spacing mesh')
axes[0].plot(counts,[r['relative_percent_errors']['CD'] for r in rows],'s--',color=colors[1],label='Redistributed, same interval counts')
axes[0].axhline(5,color='#555555',linestyle=':',label='5% reference tolerance')
axes[0].set_xticks(counts);axes[0].set_xlabel('Actual intervals');axes[0].set_ylabel('Total drag error vs archived ASWING (%)')
axes[0].set_ylim(0,5.8);axes[0].legend(fontsize=8);axes[0].grid(alpha=.2)
x=np.arange(2);width=.34
axes[1].bar(x-width/2,[r['relative_changes_percent']['CD'] for r in group['successive_changes'][-2:]],width,color=colors[0],label='Original mesh')
axes[1].bar(x+width/2,[r['relative_changes_percent']['CD'] for r in new['changes']],width,color=colors[1],label='Redistributed mesh')
axes[1].axhline(1,color='#555555',linestyle=':',label='1% diagnostic stability threshold')
axes[1].set_xticks(x,['160 → 172','172 → 178']);axes[1].set_xlabel('Successive actual interval counts')
axes[1].set_ylabel('Change in total drag between meshes (%)');axes[1].set_ylim(0,2.8)
axes[1].legend(fontsize=8);axes[1].grid(axis='y',alpha=.2)
fig.suptitle('SA-11 extended wing, 240 m/s, 3°: smoothing widths alone does not remove drag sensitivity\nSame mandatory stations, interval counts, spacing floor and aerodynamic equations',fontsize=11)
for ext in ('png','svg'):
    path=OUT/f'extension-redistribution.{ext}';assert not path.exists();fig.savefig(path,dpi=150)
plt.close(fig)
with (OUT/'plot-provenance.json').open('x') as stream:
    json.dump(dict(analysis_sha256=sha(OUT/'analysis.json'),original_analysis_sha256=sha(OLD/'analysis.json'),
        script_sha256=sha(Path(__file__)),palette_sha256=sha(ROOT/'web/plot-colors.js'),
        artifacts={f'extension-redistribution.{ext}':sha(OUT/f'extension-redistribution.{ext}') for ext in ('png','svg')}),stream,indent=2)
signal.alarm(0);print('Saved extension-redistribution.png and .svg')
