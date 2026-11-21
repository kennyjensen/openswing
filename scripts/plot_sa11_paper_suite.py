"""Render verified SA-11 curves and a small standalone status page."""
import hashlib
import html
import json
import os
from pathlib import Path
import re
import resource
import signal
import sys

for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
    assert os.environ.get(name) == '1'
resource.setrlimit(resource.RLIMIT_AS, (512*1024**2, 512*1024**2))
resource.setrlimit(resource.RLIMIT_CPU, (15,15))
signal.alarm(25)
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

ROOT = Path(__file__).resolve().parents[1]
folder = Path(sys.argv[1]).resolve()
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
result = json.loads((folder/'analysis.json').read_text())
verification = json.loads((folder/'verification.json').read_text())
assert verification['verified'] and verification['analysis_sha256'] == sha(folder/'analysis.json')
palette = (ROOT/'web/plot-colors.js').read_text().split('export const plotColors')[1].split(']);')[0]
colors = re.findall(r'#[0-9a-fA-F]{6}', palette)
configs = result['protocol']['configurations']
influences_match=all(r['matched_influence_convention'] for r in result['drag_increments'])
section_differences=any(r.get('main_wing_airfoil_fields_differ') for r in result['drag_increments'])
qualification=('Frozen/current setups differ; paired winglet benefit remains unverified.' if not influences_match else
    'Flight/influence settings match; the configuration differences also include changes in main-wing airfoil data.' if section_differences else
    'Flight/influence settings match; paired configuration differences are reported separately.')
plt.rcParams.update({'font.size':10, 'text.color':'#e5e7eb', 'axes.labelcolor':'#e5e7eb',
    'xtick.color':'#cbd5e1','ytick.color':'#cbd5e1','axes.edgecolor':'#64748b',
    'axes.facecolor':'#172033','figure.facecolor':'#101827','savefig.facecolor':'#101827'})
fig, axes = plt.subplots(2,2,figsize=(12,9))
for column, label in enumerate(result['protocol']['mach_labels']):
    for ci, config in enumerate(configs):
        curve = next(c for c in result['curves'] if c['configuration']==config['id'] and c['label']==label)
        for row, (xkey,ykey) in enumerate([('alpha','CL'),('CL','CD')]):
            ax = axes[row,column]
            ref = curve['reference']
            ax.plot([p[xkey] for p in ref],[p[ykey] for p in ref],color=colors[ci],ls='--',lw=1.5)
            # Do not draw a continuous prediction across an unrun/rejected gap.
            previous = None
            for point in curve['points']:
                if not point['valid']:
                    previous=None
                    continue
                if previous and point['alpha']-previous['alpha']<=.25+1e-12:
                    ax.plot([previous[xkey],point[xkey]],[previous[ykey],point[ykey]],color=colors[ci],lw=1.9)
                else:
                    ax.plot(point[xkey],point[ykey],marker='o',color=colors[ci],ms=3)
                previous=point
    axes[0,column].set(title=f"Mach label {label.replace('_','.')} · {240 if column==0 else 272} m/s",
                       xlabel='Angle of attack (degrees)',ylabel='CL',xlim=(0,6),ylim=(.2,.9))
    axes[1,column].set(xlabel='CL (compare drag at equal lift)',ylabel='Raw CD',xlim=(.25,.75),ylim=(.007,.031))
    for row in (0,1):
        axes[row,column].grid(color='#64748b',alpha=.25)
        axes[row,column].ticklabel_format(axis='y',style='plain',useOffset=False)
counts=result['counts']
fig.suptitle(f"SA-11: paper-focused comparison — {counts.get('pass',0)} of {result['required']} checks pass at 5%",fontsize=15,y=.985)
handles = [Line2D([],[],color=colors[i],lw=2,label=c['name']) for i,c in enumerate(configs)]
handles += [Line2D([],[],color='#e5e7eb',ls='--',label='Archived ASWING'),Line2D([],[],color='#e5e7eb',label='OpenSwing')]
fig.legend(handles=handles,loc='upper center',bbox_to_anchor=(.5,.95),ncol=3,frameon=False)
fig.text(.5,.025,f"{counts.get('mismatch',0)} mismatches · {counts.get('rejected',0)} rejected · {counts.get('unavailable',0)} missing. Corrected winglet inputs are disclosed; no experimental CD offsets.\n"
         'One fixed setup per configuration. '+qualification,
         ha='center',fontsize=9)
fig.subplots_adjust(left=.08,right=.98,bottom=.12,top=.82,hspace=.32,wspace=.22)
for suffix in ('svg','png'):
    fig.savefig(folder/f'paper-comparison.{suffix}',dpi=140)
plt.close(fig)
fig,axes=plt.subplots(1,2,figsize=(12,5.5))
for column,label in enumerate(result['protocol']['mach_labels']):
    ax=axes[column]
    for ci,config in enumerate(configs[1:],start=1):
        rows=sorted([r for r in result['drag_increments'] if r['configuration']==config['id'] and r['label']==label],key=lambda r:r['CL'])
        ax.plot([r['CL'] for r in rows],[r['target_delta_CD'] for r in rows],color=colors[ci],ls='--',marker='x',ms=5)
        actual=[r for r in rows if r['comparable_delta_CD'] is not None]
        if actual:
            ax.plot([r['CL'] for r in actual],[r['comparable_delta_CD'] for r in actual],color=colors[ci],marker='o',ms=4)
    ax.axhline(0,color='#94a3b8',lw=.8)
    ax.grid(color='#64748b',alpha=.25)
    ax.set(title=f"Mach label {label.replace('_','.')}",xlabel='Common CL',ylabel='CD(configuration) − CD(bare wing)',xticks=[.3,.5,.7])
    ax.ticklabel_format(axis='y',style='plain',useOffset=False)
fig.suptitle('SA-11: drag change at equal lift',fontsize=15,y=.98)
fig.legend(handles=handles[1:],loc='upper center',bbox_to_anchor=(.5,.93),ncol=3,frameon=False)
fig.text(.5,.035,qualification+'\nMissing or unmatched-setup differences are omitted from the plotted predictions; all underlying targets remain recorded.',ha='center',fontsize=9)
fig.subplots_adjust(left=.09,right=.98,bottom=.23,top=.73,wspace=.29)
for suffix in ('svg','png'):
    fig.savefig(folder/f'wingtip-drag-benefit.{suffix}',dpi=140)
plt.close(fig)
destination=ROOT/'public/isae-sa11-paper'
destination.mkdir(parents=True,exist_ok=True)
for name in ('paper-comparison.svg','paper-comparison.png','wingtip-drag-benefit.svg','wingtip-drag-benefit.png','analysis.json','verification.json'):
    (destination/name).write_bytes((folder/name).read_bytes())
rows=[]
for g in result['groups']:
    c=g['counts']; error=g['failed_error_percent']
    errors='—' if not error else f"{error['median']:.2f}% / {error['maximum']:.2f}%"
    rows.append(f"<tr><th>{html.escape(g['name'])}</th><td>{c.get('pass',0)}/{g['required']}</td><td>{c.get('mismatch',0)}</td><td>{c.get('rejected',0)}</td><td>{c.get('unavailable',0)}</td><td>{errors}</td></tr>")
setups=''.join(f"<li><strong>{html.escape(c['name'])}:</strong> {html.escape(c['setup'])}</li>" for c in configs)
upper_checks=[c for c in result['checks'] if c['configuration']=='upper_winglet'
              and c['kind']=='drag_at_equal_lift' and c['x']==.7]
upper_summary='; '.join(f"Mach label {c['label'].replace('_','.')}: {c['status']}"
    +(f" ({c['error_percent']:+.3f}% CD error)" if c['error_percent'] is not None else '') for c in upper_checks)
paired_note=qualification
delta_rows=[]
for r in result['drag_increments']:
    if r['CL']!=.5:continue
    name=next(c['name'] for c in configs if c['id']==r['configuration'])
    actual='Unavailable' if r['comparable_delta_CD'] is None else f"{r['comparable_delta_CD']:+.8f}"
    delta_rows.append(f"<tr><th>{html.escape(name)}</th><td>{r['label'].replace('_','.')}</td><td>{r['target_delta_CD']:+.8f}</td><td>{actual}</td></tr>")
solve_note=('This assessment reuses independently verified runs: '+str(result['new_solve_evidence']['physical_calls'])+
    ' new physical solves and '+str(result['new_solve_evidence']['reused_states'])+' identical saved states; all new runs completed.'
    if 'new_solve_evidence' in result else 'Saved-state assessment; no new physical solves.')
coverage_note = ''
scope_note = 'This is a new comparison scope, not a solver improvement.'
if 'coverage_update' in result:
    evidence = result['new_solve_evidence']
    scope_note = 'The same 48 targets and 5% tolerance are retained. This update adds coverage; it changes no solver equations or settings.'
    solve_note = (f"Latest coverage update: {evidence['physical_calls']} serial physical solves; "
                  f"{evidence['computed']} accepted and {evidence['rejected']} rejected. "
                  'Accepted fields and all 48 comparison decisions were independently checked.')
    lower_checks = [c for c in result['checks'] if c['configuration'] == 'upper_lower_winglets'
                    and c['kind'] == 'drag_at_equal_lift' and c['x'] == .3]
    lower_errors = ' / '.join(f"{c['error_percent']:+.2f}%" for c in lower_checks)
    old_missing = result['coverage_update']['old_counts'].get('unavailable', 0)
    coverage_note = (f'<h2>Upper/lower coverage update</h2><p>Missing comparisons decreased from {old_missing} '
        f"to {counts.get('unavailable',0)}. No new passes: drag at CL = 0.3 differs by {lower_errors} "
        'at the two speeds. The 240 m/s, 3° lift result is 21.21% low; the 272 m/s, 3° state rejects at local normal Mach 1.042. '
        'Original section lift limits remain unchanged.</p>')
    low_lift = folder / 'low-lift-diagnostics.json'
    if low_lift.exists():
        diagnostic = json.loads(low_lift.read_text())
        assert diagnostic['verified'] and diagnostic['pins'][str((folder/'analysis.json').relative_to(ROOT))] == sha(folder/'analysis.json')
        (destination/low_lift.name).write_bytes(low_lift.read_bytes())
        coverage_note += ('<p>The direct stall-pressure drag term is less than 0.6% of the low-lift drag discrepancy; '
            'this does not isolate indirect stall effects on circulation. '
            '<a href="low-lift-diagnostics.json">Matched-lift force accounting and source hashes</a>.</p>')
page=f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>SA-11 paper comparison</title><style>body{{font:16px/1.5 system-ui;background:#101827;color:#e5e7eb;max-width:1100px;margin:auto;padding:24px}}a{{color:#8fc4ff}}h1{{font-size:1.8rem}}img{{width:100%;height:auto}}.scroll{{overflow:auto}}table{{border-collapse:collapse;width:100%}}th,td{{padding:10px;text-align:left;border-bottom:1px solid #64748b}}small{{color:#cbd5e1}}li{{margin:.7em 0}}</style>
<h1>SA-11: {result['counts'].get('pass',0)}/{result['required']} paper-focused checks pass</h1>
<p>5% tolerance. Four configurations, two speeds, CL at 1°, 3°, 5° and CD at CL 0.3, 0.5, 0.7. Targets are the paper's archived ASWING curves, not experiment.</p>
<p>{html.escape(scope_note)} The original archive remains <strong>1,060/9,184</strong>. All {counts.get('unavailable',0)} missing checks and {counts.get('rejected',0)} rejected checks remain required here.</p>
<div class="scroll"><table><thead><tr><th>Configuration</th><th>Pass</th><th>Mismatch</th><th>Rejected</th><th>Missing</th><th>Failed error median / max</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div>
{coverage_note}
<p>The earlier upper-winglet same-angle comparison remains recorded as 294/294. Current equal-lift results at CL=0.7: {html.escape(upper_summary)}. {html.escape(paired_note)}</p>
<img src="paper-comparison.svg" alt="Archived ASWING and OpenSwing lift and drag curves for four wingtip configurations at two speeds">
<h2>Drag benefit at equal lift</h2><p>{html.escape(qualification)} These supplementary differences are not counted again in the 48 checks.</p>
<img src="wingtip-drag-benefit.svg" alt="Drag change relative to the bare wing at equal lift, with archived ASWING and eligible OpenSwing predictions">
<div class="scroll"><table><caption>Selected drag differences at CL = 0.5</caption><thead><tr><th>Configuration</th><th>Mach label</th><th>ASWING ΔCD</th><th>OpenSwing ΔCD</th></tr></thead><tbody>{''.join(delta_rows)}</tbody></table></div>
<p><a href="paper-comparison.png">Download plot</a> · <a href="analysis.json">All 48 checks and source hashes</a> · <a href="verification.json">Independent verification</a> · <a href="/isae-progress/">Progress history</a></p>
<p><a href="same-mainwing.html">Same-main-wing control and main-mesh sensitivity</a>: a separate diagnostic removes the winglets while preserving all main-wing data and nodes. Its results are not added to the primary score.</p>
<h2>Fixed comparison setups</h2><ul>{setups}</ul>
<p><small>Observed {html.escape(result['observed_utc'])}. {html.escape(solve_note)} No browser, Vite or background jobs were started.</small></p></html>'''
(destination/'index.html').write_text(page)
(folder/'plot-provenance.json').write_text(json.dumps(dict(analysis_sha256=sha(folder/'analysis.json'),
    generator_sha256=sha(Path(__file__)),palette_sha256=sha(ROOT/'web/plot-colors.js'),
    files={name:sha(destination/name) for name in ('paper-comparison.svg','paper-comparison.png','wingtip-drag-benefit.svg','wingtip-drag-benefit.png','index.html')}),indent=2)+'\n')
signal.alarm(0)
print(destination/'index.html')
