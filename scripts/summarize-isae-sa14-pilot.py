"""Report the SA-14 pilot without promoting it to a completed family study."""
from pathlib import Path
import hashlib,json
import numpy as np
ROOT=Path(__file__).resolve().parents[1];D=ROOT/'docs/validation'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    sources=json.loads((D/'isae-sa14-sources.json').read_text())
    native=json.loads((D/'isae-sa14-pilot.json').read_text())
    volume=json.loads((D/'isae-sa14-volume.json').read_text())
    measurements=json.loads((D/'isae-sa14-measurements.json').read_text())
    assert measurements['source_sha256']==sha(D/'isae-sa14-sources.json')
    modules={p.name:sha(p) for p in (ROOT/'openswing').glob('*.py')}
    assert modules==native['provenance']['modules']==sources['modules']==volume['modules']
    assert native['provenance']['source_report_sha256']==volume['source_sha256']==sha(D/'isae-sa14-sources.json')
    assert native['provenance']['script_sha256']==sha(ROOT/'scripts/verify-isae-sa14.py')
    assert native['provenance']['reference_script_sha256']==sha(ROOT/'scripts/isae_sa14_reference.py')
    assert native['computed']==50 and native['rejected']==0
    for r in native['rows']:assert sha(ROOT/r['cache_path'])==r['cache_sha256']
    runtime={}
    for name in ['wasm','browser']:
        path=D/f'isae-sa14-{name}.json'
        if path.exists():
            r=json.loads(path.read_text());assert r['modules']==modules and r['native_sha256']==sha(D/'isae-sa14-pilot.json')
            runtime[name]=dict(status=r['status'],states=len(r['rows']),display=r['display'],sha256=sha(path))
    local=[]
    for row in native['rows']:
        points=row['result']['measured_local_points']
        if not points:continue
        q=row['specification']
        label=('Wing_only' if q['case']=='wing_only' else 'Wing_body')+'_alpha_'+str(q['alpha']).replace('.','_')
        audit=next(r for r in measurements['rows'] if r['label']==label)
        classified=[]
        for point in points:
            annotation=next(p for p in audit['points'] if p['row']==point['source_row'])
            assert annotation['xy']==[point['normalized_y'],point['observed']]
            classified.append(dict(point,classification=annotation['classification']))
        instrumented=[p for p in classified if p['classification']=='instrumented_station']
        good=[p for p in instrumented if p['predicted'] is not None]
        errors=np.array([p['predicted']-p['observed'] for p in good])
        all_errors=np.array([p['predicted']-p['observed'] for p in points if p['predicted'] is not None])
        local.append(dict(specification=row['specification'],requested=len(instrumented),retained_digitized_points=len(points),available=len(good),points=classified,
                          rmse=float(np.sqrt(np.mean(errors**2))),maximum_absolute_error=float(np.max(abs(errors))),
                          all_digitized_points_rmse=float(np.sqrt(np.mean(all_errors**2)))))
    interference=[];tip=[]
    for row in native['rows']:
        q=row['specification'];r=row['result']
        if r['profiles']:
            worst=max(r['profiles'],key=lambda s:s['normal_mach'])
            tip.append(dict(specification=q,maximum_normal_mach=worst['normal_mach'],position=worst['position'],
                            velocity=worst['relative_velocity'],circulation=worst['circulation'],section_cl=worst['cl']))
        if q['case'] not in ['wing_body','infinite_body']:continue
        other=next(s for s in native['rows'] if s['specification']==dict(q,case='wing_only'))['result']
        interference.append(dict(specification=q,
            delta_CL_total=r['primary_normalization']['CL_total']-other['primary_normalization']['CL_total'],
            delta_CL_full_wing=r['primary_normalization']['CL_full_wing']-other['primary_normalization']['CL_full_wing'],
            delta_CL_exposed_wing=r['primary_normalization']['CL_exposed_wing']-other['primary_normalization']['CL_exposed_wing']))
    out=dict(status='PILOT_COMPLETE_FULL_SA14_STUDY_PENDING',provenance=native['provenance'],
        script_sha256=sha(Path(__file__)),native_sha256=sha(D/'isae-sa14-pilot.json'),volume_sha256=sha(D/'isae-sa14-volume.json'),
        measurement_audit_sha256=sha(D/'isae-sa14-measurements.json'),local_comparisons=local,body_interference=interference,maximum_local_flow=tip,runtime=runtime,
        limitations=sources['limitations']+[
            'Integrated coefficients alone do not certify mesh convergence. Maximum local normal speed grows near wing tips in this pilot.',
            'The50-state pilot does not complete the three60-point polars,44 exact measured global-lift angles or the24 iw=4deg points.',
            'Source/body-field agreement and runtime replay are numerical checks, not experimental validation.'])
    (D/'isae-sa14-pilot-comparison.json').write_text(json.dumps(out,indent=2)+'\n')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(2,3,figsize=(14,8),layout='constrained')
    for row_index,name in enumerate(['wing_only','wing_body']):
        for column,alpha in enumerate([4.7,8.8,12.9]):
            ax=axes[row_index,column]
            for n,color,style in [(25,'#e69f00',':'),(50,'#56b4e9','--'),(100,'#0072b2','-')]:
                q=dict(case=name,panels=n,alpha=alpha,pg='speed' if alpha==4.7 else 'zero')
                r=next(r for r in native['rows'] if r['specification']==q)['result']
                p=[p for p in r['profiles'] if p['normalized_y']>=0]
                ax.plot([p['normalized_y'] for p in p],[p['primary_local_load'] for p in p],style,color=color,label=f'N={n}, archive PG')
            q=dict(case=name,panels=50,alpha=alpha,pg='primary_0.19')
            r=next(r for r in native['rows'] if r['specification']==q)['result'];p=[p for p in r['profiles'] if p['normalized_y']>=0]
            ax.plot([p['normalized_y'] for p in p],[p['primary_local_load'] for p in p],'-.',color='#009e73',label='N=50, PG0.19')
            classified=next(v for v in local if v['specification']==q)['points']
            m=[p for p in classified if p['classification']=='instrumented_station']
            ax.scatter([p['normalized_y'] for p in m],[p['observed'] for p in m],s=22,facecolors='none',edgecolors='black',label='Instrumented stations')
            m=[p for p in classified if p['classification']=='drawn_tip_curve_endpoint']
            ax.scatter([p['normalized_y'] for p in m],[p['observed'] for p in m],s=22,marker='x',color='#777',label='Digitized curve endpoint')
            ax.set(title=f'{name}, alpha={alpha:g}°',xlabel='2y/b',ylabel='Wind-axis span load / (q Sw/b)',xlim=(0,1));ax.grid(alpha=.2);ax.legend(fontsize=7)
    fig.suptitle('SA-14 pilot: unchanged models and primary local-force normalization')
    for ext in ['png','svg']:fig.savefig(D/f'isae-sa14-pilot-loads.{ext}',dpi=150)
    plt.close(fig)
    lines=['# SA-14 wing/body pilot','',
        '**The full family study remains unfinished.** All50 native pilot states computed. These use the four original inputs without geometric edits or fitted parameters. [Source audit](isae-sa14-sources.md), [pilot results](isae-sa14-pilot.json), [comparison data](isae-sa14-pilot-comparison.json), and [independent body-field integration](isae-sa14-volume.json) preserve the evidence.','',
        '## Local measured loads','',
        'The primary ordinate is wind-axis force per span divided by q times mean geometric chord Sw/b. It is computed from strip forces. The archived MATLAB chord and area multipliers are retained separately. PG follows the distribution exports for this table: speed-derived Mach at4.7°, zero at8.8° and12.9°. The plots also show a same-mesh primary-Mach0.19 diagnostic.','',
        '| Input | Angle | Compared points | N100 local-load RMSE |','|---|---:|---:|---:|']
    for r in local:
        q=r['specification']
        if q['panels']==100:lines.append(f"| {q['case']} | {q['alpha']:g}° | {r['available']} / {r['requested']} | {r['rmse']:.7g} |")
    lines+=['','The [primary-station audit](isae-sa14-measurements.json) distinguishes 42 instrumented-station points from six digitized tip-curve endpoints. This classification follows primary Figure4, whose outermost pressure station is 2y/b=0.96, and Figure7. All 48 source points remain unchanged. The JSON retains both instrumented-point and all-digitized-point errors; curve endpoints are marked separately in the plot.','',
        '![Local load comparisons](isae-sa14-pilot-loads.png)','',
        'Errors increase at the largest tested incidence. The source section polar is not supplied: its airfoil text file contains coordinates, while the literal models specify a linear slope and CLmax. These are comparisons, not a physical accuracy certificate.','',
        '## Body interference and convergence','',
        'The current model produces a nonzero wing-load increment when either supplied body is added. The table keeps total, full-wing and exposed-wing lift increments distinct, using the primary wing area for every coefficient.','',
        '| Added body, N100 | Angle | Delta total CL | Delta full-wing CL | Delta exposed-wing CL |','|---|---:|---:|---:|---:|']
    for r in interference:
        q=r['specification']
        if q['panels']==100 and q['alpha']>0:lines.append(f"| {q['case']} | {q['alpha']:g}° | {r['delta_CL_total']:.7g} | {r['delta_CL_full_wing']:.7g} | {r['delta_CL_exposed_wing']:.7g} |")
    lines+=['','**Integrated lift is insufficient to establish convergence.** At12.9° in the wing-only case, maximum local normal Mach grows from0.186 to0.298 to0.571 atN25/50/100. The location approaches the wing tip. The sampled tip circulation falls while its local induced speed grows. This remains unresolved and requires finer-mesh/representation checks against the documented lifting-line formulation; no core or local-Mach guard has been changed.','',
        'Independent adaptive quadrature checks the source/doublet body velocity at six external wing locations, at zero and8.8° incidence. AtN100 the maximum component difference is3.48e-7m/s for the finite body and1.04e-5m/s for the long constant-radius body. The long-body field is explicitly nonzero at nonzero incidence. This verifies the implemented regularized field; it does not enforce the missing wake/body impermeability interaction or validate the complete circulation solution.','',
        '## Runtime checks','']
    for name in ['wasm','browser']:
        if name in runtime:lines.append(f"- {name}: {runtime[name]['states']} states, `{runtime[name]['status']}`; [evidence](isae-sa14-{name}.json). Display failures are recorded separately.")
        else:lines.append(f'- {name}: pending.')
    lines+=['','The standalone body-only file is12 times larger than the coupled fuselage and has different reference values. Its native display fails on a tiny negative zero-radius endpoint; it is not silently resized or used as a replacement for the coupled input.','',
        '## Still needed','',
        '- Complete all three60-point polars and the44 measured total/exposed lift points at their exact angles, with documented PG sensitivities.',
        '- Resolve the iw=4° digitization provenance and construct/recover its physical wing/body incidence setup before comparing those24 points.',
        '- Reconcile original load-export mesh and normalization, including manually edited plotting rows and duplicate CSVs.',
        '- Investigate tip-local-flow growth, circulation representation and higher-mesh behavior; add independent complete-flow checks.',
        '- Resolve and release the zero-radius endpoint fix after the pinned validation runs and broader regression checks finish.',
        '- Complete the experimental uncertainty and model-limit audit.','',
        'This pilot does not increase released family coverage or mark any broad ASWING requirement complete.','']
    text='\n'.join(lines)
    for a,b in [('All50','All 50'),('at4.7','at 4.7'),('at8.8','at 8.8'),('and12.9','and 12.9'),('Mach0.19','Mach 0.19'),('At12.9','At 12.9'),('from0.186','from 0.186'),('to0.298','to 0.298'),('to0.571','to 0.571'),('atN25/50/100','at N25/50/100'),('and8.8','and 8.8'),('AtN100','At N100'),('is3.48e-7m/s','is 3.48e-7 m/s'),('and1.04e-5m/s','and 1.04e-5 m/s'),('file is12','file is 12'),('three60-point','three 60-point'),('the44','the 44'),('those24','those 24')]:text=text.replace(a,b)
    (D/'isae-sa14-pilot.md').write_text(text)
    print(out['status'],len(local),'local comparisons',runtime,flush=True)


if __name__=='__main__':main()
