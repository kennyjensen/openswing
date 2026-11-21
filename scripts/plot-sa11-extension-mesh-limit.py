"""Plot verified fixed-minimum mesh sensitivity, retaining rejected states."""
import hashlib
import json
import os
from pathlib import Path
import re
import resource
import signal

for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):
    assert os.environ.get(key) == '1'
resource.setrlimit(resource.RLIMIT_AS,(512*1024**2,512*1024**2))
resource.setrlimit(resource.RLIMIT_CPU,(15,15))
signal.alarm(25)
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'artifacts/isae/sa11-extension-mesh-limit-20261108'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
analysis=json.loads((OUT/'analysis.json').read_text())
assert analysis['verified']
for row in analysis['cases']:
    assert sha(OUT/row['id']/'report.json')==row['report_sha256']
palette=(ROOT/'web/plot-colors.js').read_text()
colors=re.findall(r'#[0-9a-fA-F]{6}',re.search(r'export const plotColors = Object.freeze\(\[(.*?)\]\);',palette,re.S)[1])
fig,axes=plt.subplots(2,2,figsize=(11,7),layout='constrained',sharex='col')
for col,speed in enumerate((240,272)):
    top,bottom=axes[:,col]
    for alpha,color in zip((3,5),colors):
        group=next(g for g in analysis['groups'] if g['speed']==speed and g['alpha']==alpha)
        valid=[r for r in group['states'] if r['status']=='computed']
        top.plot([r['actual_intervals'] for r in valid],[r['relative_percent_errors']['CD'] for r in valid],
                 'o-',color=color,label=f'{alpha}° accepted',markersize=5)
        bottom.plot([r['actual_intervals'] for r in group['states']],
                    [r['maximum_normal_mach'] if r['status']=='computed' else r['rejection']['maximum']['normal_mach'] for r in group['states']],
                    'o-',color=color,label=f'{alpha}°',markersize=5)
        invalid=[r for r in group['states'] if r['status']=='rejected']
        if invalid:
            top.scatter([r['actual_intervals'] for r in invalid],[7.4]*len(invalid),marker='x',color=color,label=f'{alpha}° rejected (no score)',s=55)
            bottom.scatter([r['actual_intervals'] for r in invalid],[r['rejection']['maximum']['normal_mach'] for r in invalid],marker='x',color=color,s=80)
    top.axhspan(-5,5,color='#00804a',alpha=.08)
    for bound in (-5,5):top.axhline(bound,color='#666666',linestyle=':',linewidth=.8)
    top.axhline(0,color='#666666',linewidth=.7)
    top.set_title(f'{speed} m/s');top.set_ylabel('Total drag error vs archived ASWING (%)')
    top.set_ylim(-12,9);top.legend(fontsize=8,loc='lower right');top.grid(alpha=.2)
    bottom.axhline(1,color='#555555',linestyle=':',label='Section-moment limit')
    bottom.set_ylabel('Maximum local normal Mach');bottom.set_xlabel('Actual intervals after minimum spacing')
    bottom.set_xticks([60,108,160,178]);bottom.tick_params(axis='x',labelsize=8)
    bottom.set_ylim(.5,1.22);bottom.grid(alpha=.2);bottom.legend(fontsize=8)
fig.suptitle('SA-11 extended wing: finer requests with the same 16.466 mm minimum\nOriginal inputs and equations; no reference-selected mesh',fontsize=12)
for ext in ('png','svg'):
    path=OUT/f'extension-mesh-limit-v2.{ext}';assert not path.exists();fig.savefig(path,dpi=150)
plt.close(fig)
with (OUT/'plot-provenance-v2.json').open('x') as stream:
    json.dump(dict(analysis_sha256=sha(OUT/'analysis.json'),script_sha256=sha(Path(__file__)),
                   palette_sha256=sha(ROOT/'web/plot-colors.js'),
                   artifacts={f'extension-mesh-limit-v2.{ext}':sha(OUT/f'extension-mesh-limit-v2.{ext}') for ext in ('png','svg')}),stream,indent=2)
signal.alarm(0)
print('Saved extension-mesh-limit-v2.png and .svg')
