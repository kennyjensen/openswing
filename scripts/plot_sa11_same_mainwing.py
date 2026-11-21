"""Publish the disclosed geometry-only winglet control and its mesh sensitivity."""
import hashlib
import html
import json
import os
from pathlib import Path
import re
import resource
import signal

for name in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):assert os.environ.get(name)=='1'
resource.setrlimit(resource.RLIMIT_AS,(512*1024**2,512*1024**2))
resource.setrlimit(resource.RLIMIT_CPU,(15,15));signal.alarm(25)
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'artifacts/isae/sa11-same-mainwing-20261108'
MESH=ROOT/'artifacts/isae/sa11-same-mainwing-mesh-20261108'
read=lambda p:json.loads(p.read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
base=read(BASE/'analysis.json');mesh=read(MESH/'analysis.json');proof=read(BASE/'comparison-verification.json')
assert proof['verified'] and proof['analysis_sha256']==sha(BASE/'analysis.json') and proof['mesh_analysis_sha256']==sha(MESH/'analysis.json')
colors=re.findall(r'#[0-9a-fA-F]{6}',(ROOT/'web/plot-colors.js').read_text().split('export const plotColors')[1].split(']);')[0])
plt.rcParams.update({'font.size':10,'text.color':'#e5e7eb','axes.labelcolor':'#e5e7eb',
    'xtick.color':'#cbd5e1','ytick.color':'#cbd5e1','axes.edgecolor':'#64748b',
    'axes.facecolor':'#172033','figure.facecolor':'#101827','savefig.facecolor':'#101827'})
fig,axes=plt.subplots(3,2,figsize=(12,12.5))
for column,label in enumerate(('0_70','0_80')):
    for configuration,color in [('control',colors[0]),('upper',colors[2])]:
        curve=next(c for c in base['curves'] if c['configuration']==configuration and c['label']==label)
        for row,(xkey,ykey) in enumerate([('alpha','CL'),('CL','CD')]):
            for source,style in [('reference','--'),('points','-')]:
                values=curve[source]
                axes[row,column].plot([p[xkey] for p in values],[p[ykey] for p in values],color=color,ls=style,lw=1.8)
            if column==0:
                values=mesh['curves']['wing_alone' if configuration=='control' else 'upper_winglet']
                axes[row,column].plot([p[xkey] for p in values],[p[ykey] for p in values],ls='none',marker='D',ms=4,color=color,markeredgecolor='#e5e7eb')
    changes=[r for r in base['upper_drag_changes'] if r['label']==label]
    for key,style,marker in [('target_delta_CD','--','x'),('actual_delta_CD','-','o')]:
        axes[2,column].plot([r['CL'] for r in changes],[r[key] for r in changes],color=colors[2],ls=style,marker=marker)
    if column==0:axes[2,column].plot(.5,mesh['current62']['actual_delta_CD'],color=colors[4],marker='D',ms=7)
    axes[0,column].set(title=f"Mach label {label.replace('_','.')} · {240 if column==0 else 272} m/s",
        xlabel='Angle of attack (degrees)',ylabel='CL',xlim=(0,6),ylim=(.2,.85))
    axes[1,column].set(xlabel='CL',ylabel='Raw CD',xlim=(.25,.75),ylim=(.007,.032))
    axes[2,column].set(xlabel='Common CL',ylabel='CD(upper winglet) − CD(bare wing)',xticks=[.3,.5,.7],ylim=(-.0085,0))
    for row in range(3):axes[row,column].grid(color='#64748b',alpha=.25)
fig.suptitle('SA-11: remove the winglets, keep the same main wing',fontsize=15,y=.985)
handles=[Line2D([],[],color=colors[0],label='Bare control'),Line2D([],[],color=colors[2],label='Upper winglet'),
    Line2D([],[],color='#e5e7eb',ls='--',label='Archived ASWING'),Line2D([],[],color='#e5e7eb',label='OpenSwing: main 32'),
    Line2D([],[],color=colors[4],marker='D',ls='none',label='Main 62 diagnostic')]
fig.legend(handles=handles,loc='upper center',bbox_to_anchor=(.5,.955),ncol=3,frameon=False)
fig.text(.5,.023,'The OpenSwing pair has identical main-wing geometry, section data and nodes. Winglets stay at 16 intervals each.\n'
    'This disclosed alternative does not establish the historical generating input. Primary score remains 21/48.',ha='center',fontsize=10)
fig.subplots_adjust(left=.10,right=.98,bottom=.09,top=.86,hspace=.36,wspace=.26)
for ext in ('svg','png'):fig.savefig(BASE/f'same-mainwing.{ext}',dpi=140)
plt.close(fig)
destination=ROOT/'public/isae-sa11-paper';destination.mkdir(parents=True,exist_ok=True)
for name in ('same-mainwing.svg','same-mainwing.png'):(destination/name).write_bytes((BASE/name).read_bytes())
for source,target in [(BASE/'analysis.json','same-mainwing-data.json'),(MESH/'analysis.json','same-mainwing-mesh-data.json'),
    (BASE/'comparison-verification.json','same-mainwing-verification.json'),(BASE/'model.asw','same-mainwing-control.asw'),
    (BASE/'mesh-import.json','same-mainwing-control.mesh.json')]:
    (destination/target).write_bytes(source.read_bytes())
old=mesh['previous32'];new=mesh['current62']
page=f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>SA-11: same-main-wing control</title><style>body{{font:16px/1.5 system-ui;background:#101827;color:#e5e7eb;max-width:1100px;margin:auto;padding:24px}}a{{color:#8fc4ff}}h1{{font-size:1.7rem}}img{{width:100%;height:auto}}table{{border-collapse:collapse;width:100%}}th,td{{padding:10px;text-align:left;border-bottom:1px solid #64748b}}.scroll{{overflow:auto}}small{{color:#cbd5e1}}</style>
<p><a href="./">← Primary SA-11 comparison</a></p><h1>SA-11: same main wing, winglets removed</h1>
<p><a href="wake-interactions.html">Follow-up: localized wingtip wake interactions and a tip-only mesh control</a>.</p>
<p>The control removes only the Joint and two winglet Beam blocks from the disclosed report-derived upper-winglet model. Main-wing geometry, section data, nodes, references and operating settings are identical between the pair. The original archive input is preserved.</p>
<p><strong>All 56 new diagnostic solves are valid.</strong> The 32-interval bare control passes all six selected lift checks and fails all six equal-lift drag checks. These alternative results are separate from the unchanged <strong>21/48 primary score</strong>.</p>
<div class="scroll"><table><caption>At CL = 0.5, 240 m/s: upper-winglet drag change</caption><thead><tr><th>Quantity</th><th>ASWING</th><th>Main 32</th><th>Main 62</th></tr></thead><tbody>
<tr><th>Total ΔCD</th><td>{new['target_delta_CD']:+.8f}</td><td>{old['actual_delta_CD']:+.8f}</td><td>{new['actual_delta_CD']:+.8f}</td></tr>
<tr><th>Trefftz ΔCDi</th><td>{new['target_delta_CDi_trefftz']:+.8f}</td><td>{old['actual_delta_CDi_trefftz']:+.8f}</td><td>{new['actual_delta_CDi_trefftz']:+.8f}</td></tr></tbody></table></div>
<p>Changing only the main-wing mesh moves the total-drag benefit from 37.0% too strong to 18.2% too weak. Both winglets retain exactly the same 16-interval geometry and sampling points. The finer main-wing trial matches the Trefftz induced-drag reduction within 0.12% and the lift increment at 3° within 2.97%.</p>
<p>This identifies sensitivity in near-field drag evaluation; it is not a convergence claim or a new acceptance requirement. No solver equation, default, tolerance or primary scope was changed.</p>
<img src="same-mainwing.svg" alt="Same-main-wing control and upper winglet compared with archived ASWING, including a finer-main-wing diagnostic point">
<p><a href="same-mainwing.png">Download plot</a> · <a href="same-mainwing-data.json">Control and force decomposition</a> · <a href="same-mainwing-mesh-data.json">Mesh comparison</a> · <a href="same-mainwing-verification.json">Independent verification</a></p>
<p>Inspect the disclosed control: <a href="same-mainwing-control.asw" download>ASW file</a> and <a href="same-mainwing-control.mesh.json" download>matching mesh</a>. This is a diagnostic model, not the archived bare-wing file.</p>
<p><small>Observed {html.escape(mesh['observed_utc'])}. Small serial foreground jobs; no browser, Vite, build or background solver was started.</small></p></html>'''
(destination/'same-mainwing.html').write_text(page)
(BASE/'plot-provenance.json').write_text(json.dumps(dict(analysis_sha256=sha(BASE/'analysis.json'),
    mesh_analysis_sha256=sha(MESH/'analysis.json'),generator_sha256=sha(Path(__file__)),
    palette_sha256=sha(ROOT/'web/plot-colors.js'),files={name:sha(destination/name) for name in ('same-mainwing.svg','same-mainwing.png','same-mainwing.html')}),indent=2)+'\n')
signal.alarm(0);print(destination/'same-mainwing.html')
