"""Publish the saved wake accounting and prescribed local-tip mesh control."""
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

ROOT=Path(__file__).resolve().parents[1]
AUDIT=ROOT/'artifacts/isae/sa11-winglet-interactions-20261108'
LOCAL=ROOT/'artifacts/isae/sa11-tip-local-mesh-20261108'
FINE=ROOT/'artifacts/isae/sa11-same-mainwing-mesh-20261108'
read=lambda p:json.loads(p.read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
audit=read(AUDIT/'analysis.json');local=read(LOCAL/'analysis.json');fine=read(FINE/'analysis.json')
assert audit['verified'] and local['verified'] and fine['verified']
for analysis in (audit,local,fine):
    for path,digest in analysis['pins'].items():assert sha(ROOT/path)==digest,path
colors=re.findall(r'#[0-9a-fA-F]{6}',(ROOT/'web/plot-colors.js').read_text().split('export const plotColors')[1].split(']);')[0])
plt.rcParams.update({'font.size':10,'text.color':'#e5e7eb','axes.labelcolor':'#e5e7eb',
    'xtick.color':'#cbd5e1','ytick.color':'#cbd5e1','axes.edgecolor':'#64748b',
    'axes.facecolor':'#172033','figure.facecolor':'#101827','savefig.facecolor':'#101827'})
fig,axes=plt.subplots(1,2,figsize=(12,5.7))
series=[('Main 32',fine['previous32']['actual_delta_CD'],fine['previous32']['actual_delta_CDi_trefftz']),
        ('Tip-only 46',local['delta']['CD'],local['delta']['CDi']),
        ('Whole-main 62',fine['current62']['actual_delta_CD'],fine['current62']['actual_delta_CDi_trefftz'])]
for i,(label,total,trefftz) in enumerate(series):
    axes[0].bar([i-.17,i+.17],[-1e3*total,-1e3*trefftz],width=.30,color=[colors[0],colors[2]],
                label=None)
for x,target in [(0,-1e3*local['native']['delta_CD']),(1,-1e3*local['native']['delta_CDi'])]:
    axes[0].axhline(target,color=colors[0 if x==0 else 2],linestyle='--',linewidth=1.4)
axes[0].set(xticks=range(3),xticklabels=[r[0] for r in series],ylabel='Drag reduction × 1000',
            title='Upper-winglet benefit at CL = 0.5, 240 m/s',ylim=(0,4.25))
from matplotlib.patches import Patch
from matplotlib.lines import Line2D
axes[0].legend(handles=[Patch(color=colors[0],label='Total drag'),Patch(color=colors[2],label='Trefftz induced drag'),
                       Line2D([],[],color='#cbd5e1',ls='--',label='Archived ASWING')],fontsize=9,loc='upper right')
change=audit['comparisons']['equal_CL']['change']
values=[1e3*change[f'root_bin_{k}'] for k in range(4)]
axes[1].bar(range(4),values,color=colors[4]);axes[1].axhline(0,color='#cbd5e1',linewidth=.8)
axes[1].set(xticks=range(4),xticklabels=['0–125','125–250','250–500','500–1243'],
            xlabel='Main-wing member: projected distance from tip (mm)',
            ylabel='Change in cross-beam finite-origin ΔCD × 1000',
            title='Where the main 32 → 62 sensitivity occurs',ylim=(-.16,1.65))
axes[1].annotate('99.83% of the signed cross-beam change',xy=(0,values[0]),xytext=(.05,1.51),fontsize=9)
for ax in axes:ax.grid(axis='y',color='#64748b',alpha=.25);ax.set_axisbelow(True)
fig.suptitle('SA-11: the main-wing tip region controls most of this mesh sensitivity',fontsize=14,y=.97)
fig.text(.5,.035,'Tip-only control preserves all 28 interior intervals and both 16-interval winglets.\n'
         'One lift/speed sample; historical generating setup remains qualified. Primary score unchanged: 21/48.',ha='center',fontsize=10)
fig.subplots_adjust(left=.08,right=.98,top=.84,bottom=.22,wspace=.30)
for extension in ('svg','png'):fig.savefig(AUDIT/f'wake-interactions.{extension}',dpi=140)
plt.close(fig)
public=ROOT/'public/isae-sa11-paper'
copies={AUDIT/'wake-interactions.svg':'wake-interactions.svg',AUDIT/'wake-interactions.png':'wake-interactions.png',
        AUDIT/'analysis.json':'wake-interactions-data.json',LOCAL/'analysis.json':'tip-local-data.json',
        LOCAL/'mesh-import.json':'tip-local.mesh.json'}
for source,name in copies.items():(public/name).write_bytes(source.read_bytes())
page=f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>SA-11: wingtip wake interactions</title><style>body{{font:16px/1.5 system-ui;background:#101827;color:#e5e7eb;max-width:1150px;margin:auto;padding:24px}}a{{color:#8fc4ff}}h1{{font-size:1.7rem}}img{{width:100%;height:auto}}table{{border-collapse:collapse;width:100%}}th,td{{padding:9px;text-align:left;border-bottom:1px solid #64748b}}.scroll{{overflow:auto}}small{{color:#cbd5e1}}</style>
<p><a href="./">Primary SA-11 comparison</a> · <a href="same-mainwing.html">Same-main-wing control</a></p>
<h1>SA-11: drag sensitivity is concentrated near the main-wing tip</h1>
<p><strong>Follow-up:</strong> <a href="circulation-sampling.html">full-field accounting separates circulation changes from receiver quadrature</a>. The large separated receiver terms mostly cancel in the full wake field.</p>
<p>Nine saved-state audits locate about <strong>90% of the total mesh-dependent drag change</strong> in finite-origin wake interactions between the main wing and winglets. Almost all of that signed contribution involves the outer <strong>125 mm of projected main-wing span</strong>. All vortex terms remain included.</p>
<p>A follow-up changes only the outer two original main-wing intervals per side, producing 46 main intervals. It retains all 28 interior intervals, both complete 16-interval winglets, the same minimum spacing and aerodynamic equations. <strong>All six new solves are valid.</strong> This local change reproduces <strong>{local['fraction_of_whole_main_mesh_change_percent']:.2f}%</strong> of the total-drag change from refining the whole main wing to 62 intervals.</p>
<div class="scroll"><table><caption>One sample: 240 m/s, upper minus bare at CL = 0.5</caption><thead><tr><th>Quantity</th><th>ASWING</th><th>Main 32</th><th>Tip-only 46</th><th>Whole-main 62</th></tr></thead><tbody>
<tr><th>Total ΔCD</th><td>{local['native']['delta_CD']:+.8f}</td><td>{fine['previous32']['actual_delta_CD']:+.8f}</td><td>{local['delta']['CD']:+.8f}</td><td>{fine['current62']['actual_delta_CD']:+.8f}</td></tr>
<tr><th>Trefftz ΔCDi</th><td>{local['native']['delta_CDi']:+.8f}</td><td>{fine['previous32']['actual_delta_CDi_trefftz']:+.8f}</td><td>{local['delta']['CDi']:+.8f}</td><td>{fine['current62']['actual_delta_CDi_trefftz']:+.8f}</td></tr>
<tr><th>Total benefit error</th><td>—</td><td>37.03% too strong</td><td>15.00% too weak</td><td>18.22% too weak</td></tr></tbody></table></div>
<p>The local trial matches the Trefftz benefit within <strong>0.31%</strong> and the lift increment at 3° within <strong>1.77%</strong>. Total drag benefit remains 15.00% low. The native generating input is not recovered, so these increments retain that qualification.</p>
<p><strong>Primary score remains 21/48.</strong> This is a diagnostic of spacing sensitivity, not a solver correction, convergence proof or selected replacement mesh. The minimum-spacing rule prevents dangerously close horseshoes but does not by itself establish accurate integrated drag.</p>
<img src="wake-interactions.svg" alt="Drag benefits for three main meshes, and localization of cross-beam finite-origin drag changes near the wingtip">
<p><a href="wake-interactions.png">Download plot</a> · <a href="wake-interactions-data.json">Verified interaction accounting</a> · <a href="tip-local-data.json">Verified local-mesh results</a> · <a href="tip-local.mesh.json" download>Diagnostic upper-winglet mesh</a></p>
<p><small>Observed {html.escape(local['observed_utc'])}. Independent velocity/force checks and Decimal reductions; one BLAS thread and bounded serial jobs. No browser or background tests.</small></p></html>'''
(public/'wake-interactions.html').write_text(page)
(AUDIT/'plot-provenance.json').write_text(json.dumps(dict(analysis_sha256=sha(AUDIT/'analysis.json'),
    local_analysis_sha256=sha(LOCAL/'analysis.json'),generator_sha256=sha(Path(__file__)),
    palette_sha256=sha(ROOT/'web/plot-colors.js'),files={name:sha(public/name) for name in (*copies.values(),'wake-interactions.html')}),indent=2)+'\n')
signal.alarm(0);print(public/'wake-interactions.html')
