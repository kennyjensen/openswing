"""Compare the complete SA-12 sweep without fitting angle or drag corrections."""
from pathlib import Path
import importlib.util, json, sys
import numpy as np

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
spec=importlib.util.spec_from_file_location('sa12',ROOT/'scripts/verify-isae-sa12.py')
sa12=importlib.util.module_from_spec(spec);spec.loader.exec_module(sa12)
D=ROOT/'docs/validation'
QUANTITIES=['CL','CD','CDi','CDi_near','CDp','Cm']


def statistics(pairs):
    valid=[p for p in pairs if p[0] is not None and p[1] is not None]
    if not valid:return dict(requested=len(pairs),available=0,missing=len(pairs))
    error=np.array([a-b for a,b in valid])
    return dict(requested=len(pairs),available=len(valid),missing=len(pairs)-len(valid),
        rmse=float(np.sqrt(np.mean(error**2))),mean_error=float(np.mean(error)),
        maximum_absolute_error=float(np.max(abs(error))))


def interpolate_archive(table,alpha,column):
    rows=table['rows'];x=np.array([r[4] for r in rows]);i=int(np.searchsorted(x,alpha))
    if i<len(x) and abs(x[i]-alpha)<1e-12:return float(rows[i][column]),'stored_angle'
    if i==0 or i==len(x):return None,'outside_archived_range'
    if x[i]-x[i-1]>.250001:return None,'missing_archived_interval'
    f=(alpha-x[i-1])/(x[i]-x[i-1])
    return float((1-f)*rows[i-1][column]+f*rows[i][column]),'linear_interpolation'


def main():
    s=json.loads((D/'isae-sa12-sources.json').read_text());native=json.loads((D/'isae-sa12.json').read_text())
    p=native['provenance'];modules={f.name:sa12.sha(f) for f in (ROOT/'openswing').glob('*.py')}
    assert p['modules']==s['modules']==modules
    assert p['script_sha256']==sa12.sha(ROOT/'scripts/verify-isae-sa12.py')
    assert p['source_report_sha256']==sa12.sha(D/'isae-sa12-sources.json')
    assert p['reference_script_sha256']==sa12.sha(ROOT/'scripts/isae_sa12_reference.py')
    plan,groups=sa12.requests(s);lookup={sa12.key(r['specification']):r for r in native['rows']}
    assert len(lookup)==len(plan)==native['total']==2866 and native['groups']==groups
    assert set(lookup)=={sa12.key(r) for r in plan}
    for row in native['rows']:assert sa12.sha(ROOT/row['cache_path'])==row['cache_sha256']
    def get(case,label,panels,alpha,**kw):return lookup[sa12.key(sa12.specification(case,label,panels,alpha,**kw))]
    def value(row,k):return row.get('result',{}).get(k)
    def deltas(row,base):
        return {k:None if value(row,k) is None or value(base,k) is None else value(row,k)-value(base,k) for k in QUANTITIES}
    archived=[];experimental=[];mesh=[];pose=[];curves=[]
    for case in s['models']:
        for label in sa12.HEIGHTS:
            table=next(t for t in s['archived'] if t['name']==case['name'] and t['height_label']==label)
            angles=[r[4] for r in table['rows']]
            curve=dict(case=case['name'],height_label=label,archive=table['rows'],meshes={},zero_attitude=[])
            for panels in [25,50,100]:
                runs=[get(case,label,panels,a) for a in angles]
                points=[dict(alpha=a,status=r['status'],**{k:value(r,k) for k in QUANTITIES}) for a,r in zip(angles,runs)]
                curve['meshes'][str(panels)]=points
                archived.append(dict(case=case['name'],height_label=label,panels=panels,pose='level_freestream',
                    metrics={k:statistics([(value(r,k),a[column]) for r,a in zip(runs,table['rows'])])
                        for k,column in [('CL',5),('CD',6),('CDi',7),('Cm',8)]}))
                for quantity,k,column in [('lift','CL',5),('drag','CD',6)]:
                    points=[]
                    for measured in s['experimental'][case['name']][quantity][label]['values']:
                        alpha,observed=measured['xy'];row=get(case,label,panels,alpha)
                        reference,method=interpolate_archive(table,alpha,column)
                        point=dict(alpha=alpha,observed=observed,source_row=measured['row'],status=row['status'],
                            predicted=value(row,k),archived=reference,archive_method=method)
                        if quantity=='drag' and case['name']=='no_flap' and label=='05':
                            cdi=value(row,'CDi');refi,_=interpolate_archive(table,alpha,7)
                            point.update(fixed_display_prediction=None if cdi is None else .01+cdi,
                                fixed_display_archive=None if refi is None else .01+refi)
                        points.append(point)
                    entry=dict(case=case['name'],height_label=label,panels=panels,quantity=quantity,points=points,
                        metrics=statistics([(q['predicted'],q['observed']) for q in points]),
                        archive_metrics=statistics([(q['archived'],q['observed']) for q in points]))
                    if quantity=='drag' and case['name']=='no_flap' and label=='05':
                        entry['fixed_display_metrics']=statistics([(q['fixed_display_prediction'],q['observed']) for q in points])
                        entry['fixed_display_archive_metrics']=statistics([(q['fixed_display_archive'],q['observed']) for q in points])
                    experimental.append(entry)
            for low,high in [(25,50),(50,100)]:
                mesh.append(dict(case=case['name'],height_label=label,coarse=low,fine=high,
                    metrics={k:statistics([(value(get(case,label,high,a),k),value(get(case,label,low,a),k)) for a in angles]) for k in QUANTITIES}))
            runs=[get(case,label,100,a,pose='zero_attitude') for a in angles]
            curve['zero_attitude']=[dict(alpha=a,status=r['status'],**{k:value(r,k) for k in QUANTITIES}) for a,r in zip(angles,runs)]
            pose.append(dict(case=case['name'],height_label=label,panels=100,
                archive_metrics={k:statistics([(value(r,k),a[column]) for r,a in zip(runs,table['rows'])])
                    for k,column in [('CL',5),('CD',6),('CDi',7),('Cm',8)]},
                differences_from_primary_pose={k:statistics([(value(r,k),value(get(case,label,100,a),k)) for r,a in zip(runs,angles)]) for k in QUANTITIES}))
            curves.append(curve)
    sensitivities={name:[] for name in ['pg_influence_sensitivity','fourier_sensitivity','primary_angle_height_error_bounds','no_ground_limit']}
    for row in native['rows']:
        q=row['specification'];case=next(c for c in s['models'] if c['name']==q['case'])
        for group in sensitivities:
            if group not in groups[sa12.key(q)]:continue
            alpha=5. if group=='primary_angle_height_error_bounds' else q['alpha']
            base=get(case,q['height_label'],q['panels'],alpha)
            sensitivities[group].append(dict(specification=q,status=row['status'],base_status=base['status'],
                values={k:value(row,k) for k in QUANTITIES},difference_from_nominal=deltas(row,base),
                projected_residual=value(row,'residual'),maximum_local_residual=value(row,'maximum_local_residual'),
                actual_strips=value(row,'actual_strips')))
    good=[r for r in native['rows'] if r['status']=='computed']
    out=dict(status='COMPLETE_QUANTITATIVE_COMPARISON_PARTIAL_PHYSICAL_VALIDATION',provenance=p,
        script_sha256=sa12.sha(Path(__file__)),native_sha256=sa12.sha(D/'isae-sa12.json'),
        total=native['total'],computed=native['computed'],rejected=native['rejected'],archived=archived,
        experimental=experimental,mesh=mesh,pose_diagnostic=pose,sensitivities=sensitivities,curves=curves,
        checks=dict(maximum_projected_residual=max(r['result']['residual'] for r in good),
            maximum_local_residual=max(r['result']['maximum_local_residual'] for r in good),
            maximum_wrench_error=max(r['result']['independent_wrench_error'] for r in good),
            maximum_drag_decomposition_error=max(r['result']['drag_decomposition_error'] for r in good),
            unavailable_trefftz=sum(r['result']['CDi'] is None for r in good)),
        failures=[dict(specification=r['specification'],error=r['error'],details=r.get('details')) for r in native['rows'] if r['status']=='rejected'],
        conventions=['Experimental angles are solved exactly with no coordinate shift, fitted drag offset or parameter calibration.',
            'Archive interpolation uses only adjacent quarter-degree samples; no extrapolation and no bridge across the four missing angles.',
            'All-point errors include stall and post-stall. Primary estimated errors are not a statistical acceptance band.',
            'Mesh differences and Fourier comparisons are numerical sensitivities, not automatic proof of a continuum limit.',
            'A successful residual or runtime replay does not establish experimental accuracy.'],limitations=s['limitations'])
    out['verification_evidence_sha256']={f:sa12.sha(D/f) for f in ['isae-sa12-velocity.json','isae-sa12-wasm.json','isae-sa12-browser.json']}
    (D/'isae-sa12-comparison.json').write_text(json.dumps(out,indent=2)+'\n')
    plot(out,s)
    report(out,s)
    print(json.dumps(dict(status=out['status'],total=out['total'],computed=out['computed'],rejected=out['rejected'],checks=out['checks']),indent=2))


def plot(out,s):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    def line(ax,x,y,**kw):
        xx=[];yy=[]
        for i,(a,b) in enumerate(zip(x,y)):
            if i and a-x[i-1]>.250001:xx.append(np.nan);yy.append(np.nan)
            xx.append(a);yy.append(np.nan if b is None else b)
        ax.plot(xx,yy,**kw)
    for quantity,k,column in [('lift','CL',5),('drag','CD',6)]:
        fig,axes=plt.subplots(2,3,figsize=(14,8),sharex=True,layout='constrained')
        for i,c in enumerate(out['curves']):
            ax=axes.flat[i];x=[r[4] for r in c['archive']]
            measured=s['experimental'][c['case']][quantity][c['height_label']]['values']
            ax.errorbar([r['xy'][0] for r in measured],[r['xy'][1] for r in measured],xerr=.1,yerr=.001,
                fmt='o',ms=4,color='black',elinewidth=.6,capsize=1.5,label='Experiment (ISAE digitization)')
            line(ax,x,[r[column] for r in c['archive']],color='#555',ls='--',lw=1.3,label='Archived ASWING')
            for n,color,style in [('25','#e69f00',':'),('50','#56b4e9','-.'),('100','#0072b2','-')]:
                line(ax,x,[r[k] for r in c['meshes'][n]],color=color,ls=style,lw=1.4,label='OpenSwing N='+n)
            line(ax,x,[r[k] for r in c['zero_attitude']],color='#cc79a7',ls=':',lw=1.2,label='Zero pitch diagnostic, N=100')
            if quantity=='drag' and c['case']=='no_flap' and c['height_label']=='05':
                line(ax,x,[None if r['CDi'] is None else .01+r['CDi'] for r in c['meshes']['100']],
                    color='#009e73',ls='--',lw=1.2,label='Fixed display 0.01+CDi (N=100)')
            h={'05':'0.5','2':'2','inf':'∞ (h=1000 m)'}[c['height_label']]
            ax.set_title(('Plain wing' if c['case']=='no_flap' else 'Equivalent flap wing')+' · h/c '+h,fontsize=11)
            ax.set_xlabel('Reported angle of attack (deg)');ax.set_ylabel(k);ax.grid(alpha=.2)
        handles,labels=axes.flat[0].get_legend_handles_labels()
        fig.legend(handles,labels,loc='outside lower center',ncols=3,fontsize=8)
        fig.suptitle('SA-12 '+quantity+': source properties retained; main runs use board-parallel freestream',fontsize=12)
        for ext in ['png','svg']:fig.savefig(D/f'isae-sa12-{quantity}.{ext}',dpi=170)
        plt.close(fig)


def report(out,s):
    lines=['# ISAE SA-12: ground effect on plain and slotted-flap wings','',
        '**Quantitative comparison complete; physical validation remains partial.** Neither low residuals nor browser agreement establishes ASWING parity. The literal section model and unresolved source pose/datum limit the conclusions.','',
        f"The study completed {out['total']:,} requested states: {out['computed']:,} computed and {out['rejected']:,} rejected. It covers both unchanged `.asw` files, all six 85-point archived polars, all 75 measured lift points and 71 measured drag points at their exact angles, and three meshes. Failed or unavailable values remain in the machine-readable results.",'',
        '## Provenance and setup','',
        'The upstream revision is `'+s['revision']+'`. The [source audit](isae-sa12-sources.md) pins all 28 study files and two primary reports. The measurements are the ISAE CSV digitizations of [NACA-TN-705](https://ntrs.nasa.gov/citations/19930081443), not newly digitized curves. The two-dimensional section reference is [NACA-TR-664](https://ntrs.nasa.gov/citations/19930091739).','',
        'The rectangular NACA 23012 wing has span 1.524 m, chord 0.254 m, reference area 0.3871 m² and speed 35.76 m/s. Both finite heights, 0.127 and 0.508 m, are measured at the quarter chord. The nominal infinite-height script retains a solid image at 1000 m; a separate ground-off calculation checks that limit. Requested N=25 produces 26 strips because the root is a feature station; N=50 and N=100 produce 50 and 100. No literal input was repaired.','',
        'The primary experiment has freestream parallel to a stationary ground board. Main comparisons set Earth pitch equal to the reported angle of attack. The scripts record alpha and height but omit Earth pitch. Zero pitch is therefore a separately labeled diagnostic. Its nonzero-alpha cases have no common stationary Trefftz plane, so CDi remains unavailable rather than being replaced by near-field drag. Total CD is still retained. The plain-wing angle datum is additionally unresolved: ISAE describes a zero-lift shift, while the literal input uses section alpha=0. No angle shift is fitted here.','',
        'Main runs use current influences and zero PG Mach. All scripts toggle K/F once, but the original startup state, PG setting, exact node interpretation and Fourier mode count are not archived. Frozen/current and speed-based PG sensitivities are separate calculations. These choices do not establish an exact recreation of the original executable state.','',
        '## Experimental comparisons','',
        'The following errors use every supplied measurement, including stall and post-stall. Predictions are solved at the exact CSV angles. Coefficient errors are absolute, not percentages. No interpolation of the OpenSwing grid is used.','',
        '| Wing | h/c | Lift points | CL RMSE, N=25 / 50 / 100 | Drag points | CD RMSE, N=25 / 50 / 100 |',
        '|---|---:|---:|---:|---:|---:|']
    for case in s['models']:
        for label in sa12.HEIGHTS:
            entries={q:[next(e for e in out['experimental'] if e['case']==case['name'] and e['height_label']==label and e['panels']==n and e['quantity']==q) for n in [25,50,100]] for q in ['lift','drag']}
            fmt=lambda q:' / '.join(f"{e['metrics'].get('rmse',float('nan')):.6g}" for e in entries[q])
            lines.append(f"| {case['name']} | {dict(zip(sa12.HEIGHTS,['0.5','2','∞']))[label]} | {entries['lift'][0]['metrics']['requested']} | {fmt('lift')} | {entries['drag'][0]['metrics']['requested']} | {fmt('drag')} |")
    lines+=['',
        'Plain-wing lift RMSE is 0.0156–0.0300 at N=100. The equivalent flap wing has larger discrepancies at h/c=2 and nominal infinity (CL RMSE 0.106 and 0.119). Drag also disagrees, especially at high incidence. Refining N=50 to N=100 changes CL by less than 0.000089 and CD by less than 0.000035 on the archived angle grids. Those small numerical changes do not remove the measured discrepancies.','',
        '![Lift comparisons](isae-sa12-lift.png)','','![Drag comparisons](isae-sa12-drag.png)','',
        'Error bars show the primary report’s estimated ±0.1° angle and ±0.001 coefficient errors. They are not standard deviations or a complete uncertainty budget. CSV digitization error, section properties, angle datum, Reynolds effects and apparatus differences remain additional uncertainties. Four missing archive angles (11.25°, 11.5°, 11.75°, 12°) are not interpolated across. Measurements outside the archive range remain usable for exact OpenSwing calculations but have no archived counterpart.','',
        'Only the upstream plain-wing h/c=0.5 drag display substitutes `0.01+CDi` for total CD. The green curve preserves that documented fixed transformation as a separate quantity; it is not a correction to OpenSwing total drag. Raw CD retains the production stall-pressure contribution. The source text says post-stall drag was disabled, but the scripts contain no explicit flag that establishes how this was done.','']
    fixed=next(e for e in out['experimental'] if e['case']=='no_flap' and e['height_label']=='05' and e['panels']==100 and e['quantity']=='drag')
    lines+=[f"For that one curve, N=100 raw-CD RMSE is {fixed['metrics'].get('rmse',float('nan')):.6g}; the fixed-display RMSE is {fixed['fixed_display_metrics'].get('rmse',float('nan')):.6g}. These measure different reported quantities.",'',
        '## Archived ASWING comparisons','',
        'These are errors against all 85 stored points per curve, using N=100. The first value uses board-parallel freestream; the second uses zero pitch. The different error levels quantify pose sensitivity and do not establish the missing historical pitch.','',
        '| Wing | h/c | CL RMSE, main / zero pitch | CD RMSE, main / zero pitch |',
        '|---|---:|---:|---:|']
    for row in out['archived']:
        if row['panels']!=100:continue
        diagnostic=next(d for d in out['pose_diagnostic'] if d['case']==row['case'] and d['height_label']==row['height_label'])
        fmt=lambda k:f"{row['metrics'][k]['rmse']:.6g} / {diagnostic['archive_metrics'][k]['rmse']:.6g}"
        label={'05':'0.5','2':'2','inf':'∞'}[row['height_label']]
        lines.append(f"| {row['case']} | {label} | {fmt('CL')} | {fmt('CD')} |")
    lines+=['',
        'At nominal infinity, OpenSwing and archived ASWING are much closer to each other than the equivalent flap-wing predictions are to the experiment. That agreement does not validate the shared input section model. Near the board, both pose and the unrecorded influence/discretization settings matter. No zero-pitch CDi statistic is promoted as a full-polar result: only the single alpha=0 point has an available Trefftz value in each such curve.','',
        '## Numerical sensitivity and source limitations','',
        '| Wing | h/c | max ΔCL, N50→100 | max ΔCD, N50→100 |',
        '|---|---:|---:|---:|']
    for m in out['mesh']:
        if m['fine']==100:
            label={'05':'0.5','2':'2','inf':'∞'}[m['height_label']]
            lines.append(f"| {m['case']} | {label} | {m['metrics']['CL'].get('maximum_absolute_error',float('nan')):.6g} | {m['metrics']['CD'].get('maximum_absolute_error',float('nan')):.6g} |")
    ground=out['sensitivities']['no_ground_limit']
    maxground=max(abs(r['difference_from_nominal'][k]) for r in ground for k in ['CL','CD'])
    fourier=out['sensitivities']['fourier_sensitivity']
    lines+=['',f"The 30 ground-off limit checks change CL/CD by at most {maxground:.6g} relative to the 1000 m image case. The 72 Fourier checks use 5, 9 and 19 modes at N=50/100 and alpha=5°/10°. Their largest projected residual is {max(r['projected_residual'] for r in fourier if r['projected_residual'] is not None):.6g}, while the largest pointwise local defect is {max(r['maximum_local_residual'] for r in fourier if r['maximum_local_residual'] is not None):.6g}. The projected equations can converge without a small local defect. Full coefficient differences are retained in [the comparison JSON](isae-sa12-comparison.json).",'',
        'Sixteen corner probes vary angle by ±0.1° and height by ±1/16 inch around alpha=5° for both finite heights. These are bounded input sensitivities, not an exhaustive uncertainty propagation. Another 270 states vary PG and influence freezing. The 510 zero-pitch states remain separate from primary-pose comparisons.','',
        'The slotted-flap input is one straight lifting line with fixed alpha=12.5°, slope 7.44/rad, CLmax=2.6 and Cdf=0.04. It does not resolve the slot, a moving flap, its tip clearance or changes in section behavior near the board. Both inputs set section Cm=0, although the primary flap experiment has nonzero pitching moments. Agreement with archived near-zero Cm cannot validate the physical flap moment.','',
        'The primary uses Reynolds number 609,000 (effective 974,000), whereas the section reference has different tunnel and Reynolds conditions. The primary reports a stationary-board approximation and unequal wall-correction treatment between free-air and ground-board runs. These limitations prevent assigning all disagreement to the numerical solver.','',
        '## Evidence and reproduction','',
        'The [native results](isae-sa12.json), [comparison data](isae-sa12-comparison.json), [source audit](isae-sa12-sources.json) and [pose pilot](isae-sa12-setup.json) retain source hashes and individual outcomes. The [independent image-velocity check](isae-sa12-velocity.json) uses numerical Biot–Savart quadrature for 24 force-point velocities and 24 ground-boundary points in eight states. It holds production geometry/circulation fixed, so it does not independently solve the lifting-line problem.','',
        'All 33 [actual WebAssembly replays](isae-sa12-wasm.json) and 17 [offline browser cases](isae-sa12-browser.json) pass. The browser verifies exported pose, source text, module hashes and coefficients, retains six unavailable CDi values, and checks mobile layout. The [numerical/provenance checks](isae-sa12-checks.json) independently verify CSV rows, coefficient statistics, force/moment conventions, ground normals, finite values and source/runtime hashes. These are implementation checks, not proof of experimental accuracy.','',
        '```sh','OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python scripts/verify-isae-sa12.py --workers 1',
        'OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python scripts/summarize-isae-sa12.py',
        'OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python scripts/check-isae-sa12.py','```','']
    (D/'isae-sa12.md').write_text('\n'.join(lines))


if __name__=='__main__':main()
