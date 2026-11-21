"""Publish full-field factorization and retain adverse Fourier diagnostics."""
import hashlib
import html
import json
import os
from pathlib import Path
import re
import resource
import signal

for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):assert os.environ.get(k)=='1'
resource.setrlimit(resource.RLIMIT_AS,(512*1024**2,512*1024**2));resource.setrlimit(resource.RLIMIT_CPU,(15,15));signal.alarm(25)
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'artifacts/isae/sa11-tip-factorization-20261108'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
data=json.loads((OUT/'analysis.json').read_text());assert data['analysis_verified']
for path,digest in data['pins'].items():assert sha(ROOT/path)==digest,path
colors=re.findall(r'#[0-9a-fA-F]{6}',(ROOT/'web/plot-colors.js').read_text().split('export const plotColors')[1].split(']);')[0])
plt.rcParams.update({'font.size':10,'text.color':'#e5e7eb','axes.labelcolor':'#e5e7eb','xtick.color':'#cbd5e1',
    'ytick.color':'#cbd5e1','axes.edgecolor':'#64748b','axes.facecolor':'#172033','figure.facecolor':'#101827','savefig.facecolor':'#101827'})
fig,axes=plt.subplots(1,2,figsize=(12,6))
bottom=[0.,0.]
for key,label,color in [('receiver_total_share_percent','Receiver quadrature',colors[0]),
                        ('main_step_total_share_percent','Main circulation steps',colors[2]),
                        ('winglet_total_share_percent','Winglet circulation',colors[4])]:
    values=data['factorization_summary'][key];axes[0].bar([0,1],values,bottom=bottom,color=color,label=label,width=.55)
    bottom=[a+b for a,b in zip(bottom,values)]
axes[0].set(xticks=[0,1],xticklabels=['2.75°','3°'],ylabel='Share of full cross-beam drag change (%)',
            title='Main 32 → tip-only 46: what changes the force?',ylim=(0,105))
axes[0].legend(loc='upper center',bbox_to_anchor=(.5,-.10),fontsize=9,ncol=1,frameon=False)
axes[0].text(.5,45,'Main circulation steps include changes in\nsource sampling as well as amplitudes.',ha='center',fontsize=9,color='#101827',
             bbox=dict(facecolor='#fef3c7',edgecolor='none',alpha=.95,pad=6))
for modes,label,color,marker in [(0,'Pointwise',colors[0],'o'),(20,'Fourier 20',colors[2],'^'),(30,'Fourier 30',colors[4],'s')]:
    source=data['pointwise_controls'] if modes==0 else data['fourier_cases']
    rows=sorted([r for r in source if r['configuration']=='upper_winglet' and r['main_modes']==modes],key=lambda r:r['main_intervals'])
    axes[1].plot([r['main_intervals'] for r in rows],[r['errors_percent']['CD'] for r in rows],marker=marker,color=color,label=label)
axes[1].axhspan(-5,5,color='#a7f3d0',alpha=.10);axes[1].axhline(0,color='#cbd5e1',lw=.8)
axes[1].set(xticks=[32,46],xticklabels=['Main 32','Tip-only 46'],ylabel='Upper-winglet CD error versus archive (%)',
            title='Main-only Fourier trials: 240 m/s, 3°',xlim=(30,48),ylim=(-10,60))
axes[1].legend(loc='upper left',fontsize=9)
for ax in axes:ax.grid(axis='y',color='#64748b',alpha=.25);ax.set_axisbelow(True)
fig.suptitle('SA-11: circulation sampling drives the full interaction change',fontsize=14,y=.96)
fig.text(.5,.025,'All eight Fourier solves computed; six passed every tight diagnostic gate, two retained conditioning-related failures.\n'
         'No default change or new primary passes. Paper suite remains 21/48.',ha='center',fontsize=10)
fig.subplots_adjust(left=.08,right=.98,top=.84,bottom=.28,wspace=.3)
for ext in ('svg','png'):fig.savefig(OUT/f'circulation-sampling.{ext}',dpi=140)
plt.close(fig)
public=ROOT/'public/isae-sa11-paper'
for ext in ('svg','png'):(public/f'circulation-sampling.{ext}').write_bytes((OUT/f'circulation-sampling.{ext}').read_bytes())
(public/'circulation-sampling-data.json').write_bytes((OUT/'analysis.json').read_bytes())
rows=[]
for r in data['fourier_cases']:
    if r['configuration']=='upper_winglet':
        rows.append(f"<tr><td>{r['main_intervals']}</td><td>{r['main_modes']}</td><td>{r['errors_percent']['CD']:+.2f}%</td><td>{100*r['local_residual_max']:.3f}%</td><td>{'Pass' if r['diagnostic_verified'] else 'Two failed numerical checks retained'}</td></tr>")
page=f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>SA-11: circulation sampling</title><style>body{{font:16px/1.5 system-ui;background:#101827;color:#e5e7eb;max-width:1150px;margin:auto;padding:24px}}a{{color:#8fc4ff}}h1{{font-size:1.7rem}}img{{width:100%;height:auto}}table{{border-collapse:collapse;width:100%}}th,td{{padding:9px;text-align:left;border-bottom:1px solid #64748b}}.scroll{{overflow:auto}}small{{color:#cbd5e1}}</style>
<p><a href="./">Primary SA-11 comparison</a> · <a href="wake-interactions.html">Earlier localization and tip-only control</a></p>
<h1>SA-11: circulation sampling, rather than receiver quadrature, dominates the full interaction change</h1>
<p>The earlier study located large finite-origin wake changes near the main tip. This follow-up keeps the <strong>full wake field</strong>: large receiver-spacing terms cancel between the finite-origin and half-wake contributions. At 2.75° and 3°, receiver quadrature contributes only <strong>0.90%</strong> of the full cross-beam drag change. Main circulation steps contribute about <strong>47.5%</strong> and winglet circulation about <strong>51.6%</strong>.</p>
<p>The main-step contribution includes discrete circulation sampling and jump locations; it is not solely a change in smooth loading. These percentages apply to the main-wing/winglet vortex interaction at fixed incidence, not every drag term or the prior equal-lift comparison.</p>
<p>An independent replay of the unchanged winglet control-point equations recovers the saved circulation to floating-point precision. Outer-main forcing drives the 2.87–2.89% winglet circulation change, with a small opposing interior contribution. Stall leakage is negligible, and the conditional winglet matrix has condition number 9.94.</p>
<h2>Fourier is not a demonstrated fix</h2><p>Eight new trials keep the same main 32 / tip-only 46 meshes, with 20 or 30 Fourier modes on the main wing and pointwise winglets. All compute without Mach rejection. Six pass every tight numerical diagnostic; the two main-32 / 30-mode cases retain failed reconstruction and conditional-replay gates associated with a poorly conditioned basis.</p>
<div class="scroll"><table><caption>Upper winglet at 240 m/s, 3°. Local defect is maximum tangency residual divided by freestream speed.</caption><thead><tr><th>Main intervals</th><th>Main modes</th><th>CD error</th><th>Local flow defect</th><th>Numerical diagnostic</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div>
<p>The main-46 / 20-mode result has a tiny projected residual but a 26% local flow defect and 53.15% drag error. This distinguishes satisfying the weighted Fourier equations from resolving local flow. No representation or mesh is selected as a replacement.</p>
<p><strong>Primary score remains 21/48.</strong> Native generating mesh and mode settings are still unknown. Source equations, inputs, defaults and tolerances are unchanged.</p>
<img src="circulation-sampling.svg" alt="Full cross-beam drag-change attribution and upper-winglet drag errors for pointwise and Fourier representations on two main meshes">
<p><a href="circulation-sampling.png">Download plot</a> · <a href="circulation-sampling-data.json">All results, failed checks and provenance</a></p>
<p><small>Observed {html.escape(data['observed_utc'])}. Small serial jobs with one BLAS thread; no browser or background solver tests.</small></p></html>'''
(public/'circulation-sampling.html').write_text(page)
(OUT/'plot-provenance.json').write_text(json.dumps(dict(analysis_sha256=sha(OUT/'analysis.json'),generator_sha256=sha(Path(__file__)),
    palette_sha256=sha(ROOT/'web/plot-colors.js'),files={name:sha(public/name) for name in ('circulation-sampling.svg','circulation-sampling.png','circulation-sampling.html','circulation-sampling-data.json')}),indent=2)+'\n')
signal.alarm(0);print(public/'circulation-sampling.html')
