"""Produce shareable SA-6 comparisons without fitting model parameters."""
from pathlib import Path
import json,sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from isae_sa6_reference import sha,IDS
D=ROOT/'docs/validation'


def main():
    study=json.loads((D/'isae-sa6.json').read_text());src=json.loads((D/'isae-sa6-sources.json').read_text())
    checks=json.loads((D/'isae-sa6-checks.json').read_text())
    current=[r for r in study['primary_comparisons'] if not r['frozen'] and r['geometry_matches_label']]
    slopes=[]
    for case in study['cases']:
        if case['id']=='10b_25c' and not case['reconstructed']:continue
        for alpha in [0,8,12]:
            reference=next(r for r in src['primary'] if r['id']==case['id'] and r['body_alpha']==alpha)
            for frozen in [False,True]:
                selected=[r for r in case['runs'] if r['specification']['alpha']==alpha and r['specification']['panels']==160 and r['specification']['frozen']==frozen and r['specification']['delta']<=20]
                if not all(r['status']=='computed' for r in selected):continue
                x=np.array([r['specification']['delta'] for r in selected])
                for key,refkey in [('Cl','Cl_body'),('Cn','Cn_body')]:
                    measured=float(np.polyfit(reference['delta'][:6],reference[refkey][:6],1)[0]);computed=float(np.polyfit(x,[r['result'][key] for r in selected],1)[0])
                    slopes.append(dict(case=case['case_id'],alpha=alpha,frozen=frozen,coefficient=key,primary_slope=measured,openswing_slope=computed,relative_error=(computed-measured)/measured))
    rows=[r for c in study['cases'] for r in c['runs']];computed=[r for r in rows if r['status']=='computed'];rejected=[r for r in rows if r['status']=='rejected']
    out=dict(status='PARTIAL_VALIDATION_DISCREPANCIES_REMAIN',study_sha256=sha(D/'isae-sa6.json'),sources_sha256=sha(D/'isae-sa6-sources.json'),checks_sha256=sha(D/'isae-sa6-checks.json'),script_sha256=sha(Path(__file__)),
        total=len(rows),computed=len(computed),rejected=rejected,primary_current=current,slopes_0_to_20_degrees=slopes,
        maximum_residual=max(r['result']['residual'] for r in computed),maximum_wrench_check=max(r['result']['independent_wrench_error'] for r in computed))
    (D/'isae-sa6-comparison.json').write_text(json.dumps(out,indent=2)+'\n')
    plt.rcParams.update({'font.size':10,'svg.fonttype':'none'})
    colors=['#2563eb','#f97316','#22c55e','#a855f7']
    for family,idents in [('chord',IDS[:4]),('span',IDS[4:])]:
        fig,axes=plt.subplots(3,2,figsize=(11,10),sharex=True,layout='constrained')
        for j,ident in enumerate(idents):
            case=next(c for c in study['cases'] if c['id']==ident and (ident!='10b_25c' or c['reconstructed']))
            label=(ident.split('_')[1].removesuffix('c')+'% chord') if family=='chord' else (ident.split('_')[0].removesuffix('b')+' in span')
            for i,alpha in enumerate([0,8,12]):
                ref=next(r for r in src['primary'] if r['id']==ident and r['body_alpha']==alpha)
                for ax,key,refkey in [(axes[i,0],'Cl','Cl_body'),(axes[i,1],'Cn','Cn_body')]:
                    ax.plot(ref['delta'],ref[refkey],linestyle='none',marker='o',markersize=4,color=colors[j],label=label+' primary')
                    for frozen,style in [(False,'-'),(True,':')]:
                        rr=[r for r in case['runs'] if r['specification']['alpha']==alpha and r['specification']['panels']==160 and r['specification']['frozen']==frozen]
                        ax.plot([r['specification']['delta'] for r in rr],[r['result'][key] if r['status']=='computed' else np.nan for r in rr],style,color=colors[j],label=label+(' frozen' if frozen else ' current'))
                    ax.set_title(f'Body pitch {alpha}° / wing incidence {alpha+4}°');ax.set_ylabel('$C_l$ (body)' if key=='Cl' else '$C_n$ (body, span normalized)');ax.grid(alpha=.2)
                if ident=='10b_25c':
                    literal=next(c for c in study['cases'] if c['id']==ident and not c['reconstructed'])
                    rr=[r for r in literal['runs'] if r['specification']['alpha']==alpha and r['specification']['panels']==160 and not r['specification']['frozen']]
                    for ax,key in [(axes[i,0],'Cl'),(axes[i,1],'Cn')]:ax.plot([r['specification']['delta'] for r in rr],[r['result'][key] if r['status']=='computed' else np.nan for r in rr],'--',color='#777777',linewidth=1.3,zorder=4,label='Literal 10b file (15-inch control)')
        for ax in axes[-1]:ax.set_xlabel('Aileron δ, degrees: right up / left down')
        from matplotlib.lines import Line2D
        labels=[ident.split('_')[1].removesuffix('c')+'% chord' if family=='chord' else ident.split('_')[0].removesuffix('b')+' in span'+(' (reconstructed model)' if ident=='10b_25c' else '') for ident in idents]
        handles=[Line2D([],[],color=colors[j],label=label) for j,label in enumerate(labels)]
        handles += [Line2D([],[],color='black',marker='o',linestyle='none',label='Primary table'),Line2D([],[],color='black',label='Current influences'),Line2D([],[],color='black',linestyle=':',label='Frozen influences')]
        if family=='span':handles.append(Line2D([],[],color='#777777',linestyle='--',label='Literal 10b file (15 in)'))
        fig.legend(handles=handles,loc='outside lower center',ncol=3,fontsize=8)
        fig.suptitle(f'SA-6: varying aileron {family}\nPrimary NACA tables versus OpenSwing, 164 actual strips; no fitted parameters')
        for ext in ['png','svg']:fig.savefig(D/f'isae-sa6-{family}.{ext}',dpi=160,bbox_inches='tight')
        plt.close(fig)
    lines=['# SA-6: aileron rolling and yawing moments','',
        '**Partial validation; experimental and archived-ASWING discrepancies remain.** All seven literal models and one explicit 10-inch control-span reconstruction are compared. No solver equations, tolerances or aerodynamic parameters were changed.','',
        f"The sweep contains {len(rows):,} requested states: **{len(computed):,} converged, {len(rejected)} rejected**, across requested meshes 40/80/160 (44/84/164 actual strips after mandatory station breaks), body pitch 0°/8°/12°, aileron δ=0° to 44° in 4° steps, and current/frozen influence choices. Speed is 20 m/s and PG Mach is zero, as in the raw archived force files. The largest residual is {out['maximum_residual']:.3g}.",'',
        '## Source and convention audit','',
        'The source is Jan’s [ISAE repository](https://github.com/rom1isae/ISAE_Aswing_Experimental_Validation/tree/'+src['revision']+'), pinned to `'+src['revision']+'`. Primary tables are independently transcribed from [NACA TR-298](https://ntrs.nasa.gov/api/citations/19930091367/downloads/19930091367.pdf) Tables V/VI (printed p.18, PDF p.20), and [NACA TR-343](https://ntrs.nasa.gov/api/citations/19930091412/downloads/19930091412.pdf) Tables V/VI and XIII/XIV (printed pp.21/27, PDF pp.23/29). PDF hashes and original data are retained in [the source audit](isae-sa6-sources.json).','',
        '- Primary moments use body axes. TR-343 p.4 defines yaw as N/(q S f), where f is the center-of-rotation-to-tail distance: 25 inches versus the 60-inch span. Multiplying the primary yaw coefficient by 25/60 gives the ASWING span normalization. The reported 0.417 ratio is rounded.',
        '- Raw ASWING fmat moments use stability axes. For fixed body pitch α, Cl_s = cos(α) Cl_b + sin(α) Cn_b and Cn_s = −sin(α) Cl_b + cos(α) Cn_b. These are used only for the archived comparison; primary comparisons use body moments.',
        '- The archived post-stall span measurements come from the 8° body-pitch table; chord measurements come from the 12° table. The model already has 4° incidence, so it is not added again to the flight condition.',
        '- The file named 10b defines 15-inch ailerons. Its literal results remain recorded. The separate reconstruction changes only the doubled dCLdF1/dCMdF1 boundary stations from ±0.381 to ±0.508 m; it is never substituted for the literal input.',
        '- Positive physical δ means right aileron up and left down. It maps to +F1 in chord files and −F1 in span files. Signed moments are retained.',
        f"- The data audit retains {len(checks['matlab_primary_conflicts'])} MATLAB/primary numeric conflicts, {len(checks['csv_primary_conflicts'])} CSV/primary conflicts, {len(checks['ods_matlab_conflicts'])} ODS/MATLAB conflicts and {len(checks['invalid_ods_cells'])} invalid ODS numeric cells. In particular, the post-stall 20-inch yaw series repeats the level-flight values. No archive cells are silently repaired.",
        '- The archived 15c model uses dCLdF=.040 whereas the report gives .039; 35c uses .071 whereas the report prints .71. Literal coefficients are retained. The original fmat mesh and frozen-influence startup state are unknown.',
        '- The primary model includes a fuselage; the supplied aerodynamic models are wing-only. Tables were read from faired curves through observations at three speeds. The input reference area .3871 m² differs from the exact 600 in² area (.387096 m²) by about 0.001%; that input rounding is retained. The tunnel’s ±1% velocity uniformity is not treated as coefficient uncertainty.','',
        '## Primary comparison','',
        'Current-influence results at the finest mesh (160 requested, 164 actual strips) are shown below. RMSE includes all 12 deflections, including zero. “10b reconstructed” uses the explicitly changed control-span boundary. A small residual or agreement with ASWING is not an experimental pass.','',
        '| Aileron | Body pitch | Roll coefficient RMSE | Yaw coefficient RMSE |','|---|---:|---:|---:|']
    for r in current:lines.append(f"| {r['case'].replace('_literal','').replace('_reconstructed',' reconstructed')} | {r['body_alpha']}° | {r['errors']['Cl']['rmse']:.6f} | {r['errors']['Cn']['rmse']:.6f} |")
    lines += ['','Signed control slopes fitted over δ=0°–20° give these percentage-error ranges across the seven physical variants (current influences). A negative percentage for a negative yaw slope means its magnitude is underpredicted. These are descriptive errors, not acceptance tolerances.','','| Body pitch | Roll slope error | Yaw slope error |','|---|---:|---:|']
    for alpha in [0,8,12]:
        bounds={k:[100*r['relative_error'] for r in slopes if r['alpha']==alpha and r['coefficient']==k and not r['frozen']] for k in ['Cl','Cn']}
        lines.append(f"| {alpha}° | {min(bounds['Cl']):+.1f}% to {max(bounds['Cl']):+.1f}% | {min(bounds['Cn']):+.1f}% to {max(bounds['Cn']):+.1f}% |")
    high=[r for r in study['mesh_comparisons'] if r['high']==160 and not r['frozen']]
    lines += ['',f"Refinement from 80 to 160 requested intervals (84→164 actual strips) changes Cl by at most {max(r['errors']['Cl']['maximum_absolute_error'] for r in high):.6f} and Cn by at most {max(r['errors']['Cn']['maximum_absolute_error'] for r in high):.6f} over the sweep. These differences are substantially below the largest experimental discrepancies.",'']
    lines += ['','## Archived ASWING comparison','','The 44 raw fmat outputs identify 12° body pitch, zero PG Mach and stability-axis moments. The table compares those signed moments after the explicit body-to-stability rotation. Original mesh and K/F startup settings are not recorded; both influence choices are retained.','','| Aileron | Influences | Stability roll RMSE | Stability yaw RMSE |','|---|---|---:|---:|']
    for r in study['archived_fmat_comparisons']:
        lines.append(f"| {r['case'].replace('_literal','')} | {'Frozen' if r['frozen'] else 'Current'} | {r['errors']['Cl']['rmse']:.6f} | {r['errors']['Cn']['rmse']:.6f} |")
    lines+=['','![Varying chord](isae-sa6-chord.png)','','![Varying span](isae-sa6-span.png)','','## Numerical verification and remaining work','',
        f"Independent strip-force/moment sums agree with the reported coefficients within {out['maximum_wrench_check']:.3g}. All 48 signed-control reflection checks pass. Sixteen implicit control tangents agree with two centered nonlinear step sizes; mounted and rigid base coefficients agree. The 44 raw fmat roll/yaw pairs match their archived MATLAB values exactly. These checks validate calculations and conventions, not the experimental model.",'',
        'The [numerical report](isae-sa6.json) retains every run, both influence settings, 40→80 and 80→160 differences and all archived-force comparisons. The [comparison summary](isae-sa6-comparison.json) also records signed least-squares slopes over δ=0°–20°; these summarize control effectiveness and do not tune the aerodynamic model. The [check report](isae-sa6-checks.json) retains source contradictions and derivative errors.','',
        'Actual Pyodide replays and the offline browser workflow are recorded separately in [WASM checks](isae-sa6-wasm.json) and [browser checks](isae-sa6-browser.json). They must not be confused with experimental validation.','',
        'Remaining work is to reconcile the literal control geometry and aerodynamic section properties with the actual apparatus, recover the original discretization/startup settings, assess the omitted fuselage and flap-dependent drag/stall model independently, and obtain measurement/setup uncertainty. Mesh sensitivity and derivative agreement alone cannot close these gaps. The full ISAE suite and the full ASWING feature goal remain incomplete.','',
        '## Reproduction','',
        'Restore the source-pinned ISAE cache with `scripts/fetch-isae-validation.py`. The optional SA-6 raw archive retains the pinned NASA PDFs, original inputs, all cached solves and test logs. Run with `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1`:','',
        '```sh','.venv/bin/python scripts/fetch-isae-sa6.py','.venv/bin/python scripts/isae_sa6_reference.py','.venv/bin/python scripts/verify-isae-sa6.py','.venv/bin/python scripts/check-isae-sa6.py','node scripts/test-isae-sa6-wasm.mjs','.venv/bin/python scripts/summarize-isae-sa6.py','npx playwright test tests/browser/isae-sa6.spec.js','```','',
        'The PDFs are US-government works marked public-use permitted by NASA. The source ZIP carries summaries and scripts; the separate raw archive carries full primary scans and source-cache files.','']
    (D/'isae-sa6.md').write_text('\n'.join(lines));print('COMPLETE summaries and two figures',flush=True)

if __name__=='__main__':main()
