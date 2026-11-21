"""Report conditional airship comparisons without fitting geometry or loads."""
from pathlib import Path
import hashlib
import json
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
D = ROOT / 'docs/validation'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def metrics(points):
    good = [p for p in points if p.get('predicted') is not None]
    error = np.array([p['predicted'] - p['observed'] for p in good])
    return dict(requested=len(points), available=len(good), missing=len(points)-len(good),
                rmse=float(np.sqrt(np.mean(error**2))), mean_error=float(np.mean(error)),
                maximum_absolute_error=float(np.max(abs(error))))


def multiplier(case):
    # TR405 Fig8 uses force per unit length divided by q, not by q*D.
    # The figure's 33.01-inch model and the reconstructed L/D supply a
    # conditional dimensional conversion into the report's foot convention.
    return case['outline']['normalized_diameter'] * 33.01 / 12 if case['name'] == 'r101' else 1.


def main():
    sources = json.loads((D / 'isae-sa13-sources.json').read_text())
    native = json.loads((D / 'isae-sa13.json').read_text())
    velocity = json.loads((D / 'isae-sa13-velocity.json').read_text())
    wasm = json.loads((D / 'isae-sa13-wasm.json').read_text())
    browser = json.loads((D / 'isae-sa13-browser.json').read_text())
    candidate = {name:json.loads((D/f'isae-sa13-endpoint-candidate-{name}.json').read_text())
                 for name in ['native','wasm','browser']}
    p = native['provenance']
    assert p['modules'] == {f.name: sha(f) for f in (ROOT / 'openswing').glob('*.py')}
    assert p['source_report_sha256'] == sha(D / 'isae-sa13-sources.json')
    assert p['script_sha256'] == sha(ROOT / 'scripts/verify-isae-sa13.py')
    assert p['reference_script_sha256'] == sha(ROOT / 'scripts/isae_sa13_reference.py')
    assert velocity['native_sha256'] == wasm['native_sha256'] == sha(D / 'isae-sa13.json')
    assert len(native['rows']) == native['computed'] == 38 and native['rejected'] == 0
    for row in native['rows']:
        assert sha(ROOT / row['cache_path']) == row['cache_sha256']
    cases = {c['name']: c for c in sources['cases']}
    comparisons = []
    for row in native['rows']:
        q = row['specification']; case = cases[q['case']]; r = row['result']
        if q['length'] != 1. or (q['case'] != 'pressure' and q['alpha'] == 0.):
            continue
        factor = multiplier(case)
        points = []
        for m in r['measured_points']:
            value = m.get('predicted_Cp_percent') if q['case'] == 'pressure' else m.get('transverse_density')
            point = dict(m, predicted=None if value is None else float(value * factor))
            if 'independent_pointwise_density' in m:
                point['independent_pointwise_prediction'] = m['independent_pointwise_density'] * factor
            points.append(point)
        comparisons.append(dict(specification=q, points=points, metrics=metrics(points),
            normalization=('f_transverse/q in feet; conditional 33.01-inch model scale' if q['case']=='r101'
                           else '100Cp' if q['case']=='pressure' else 'f_transverse/(q*D_tabulated_outline)'),
            primary_angle=q['alpha']==case['primary_alpha'],
            maximum_radius_overshoot_ratio=2*case['outline']['interpolated_radius_extrema']['maximum']/case['outline']['normalized_diameter'],
            source_scale_factor=factor))
    assert len(comparisons) == 22
    mesh = []
    for name, case in cases.items():
        for low, high in [(32,64),(64,128),(128,256)]:
            def select(n):
                return next(c for c in comparisons if c['specification']==dict(case=name,panels=n,
                    alpha=case['primary_alpha'],length=1.,surface_offset=1e-6))
            a,b=select(low),select(high)
            assert [v['source_index'] for v in a['points']]==[v['source_index'] for v in b['points']]
            matched=[(x['predicted'],y['predicted']) for x,y in zip(a['points'],b['points'])
                     if x['predicted'] is not None and y['predicted'] is not None]
            delta=np.array([y-x for x,y in matched])
            mesh.append(dict(case=name,coarse=low,fine=high,matched_points=len(matched),
                             maximum_absolute_change=float(np.max(abs(delta))),
                             rms_change=float(np.sqrt(np.mean(delta**2)))))
    scale=[]
    for scaled in native['rows']:
        q=scaled['specification']
        if q['length']==1.:continue
        base=next(r for r in native['rows'] if r['specification']==dict(q,length=1.))
        a,b=scaled['result'],base['result'];length=q['length']
        scale.append(dict(panels=q['panels'],length_metres=length,
            maximum_coefficient_difference=max(abs(v-b['coefficients'][k]) for k,v in a['coefficients'].items() if v is not None),
            maximum_force_scaling_error=float(np.max(abs(np.array(a['force'])/length**2-b['force']))),
            maximum_moment_scaling_error=float(np.max(abs(np.array(a['moment'])/length**3-b['moment']))),
            maximum_density_scaling_error=float(np.max(abs(np.array([v['transverse_density'] for v in a['profiles']])-np.array([v['transverse_density'] for v in b['profiles']]))))))
    conservation=[dict(specification=r['specification'],normalized_net_force_error=r['result']['normalized_net_force_error'],
                       normalized_moment_error=r['result']['normalized_moment_error'],
                       independent_closed_body_moment=r['result']['independent_closed_body_moment']) for r in native['rows']]
    out=dict(status='CONDITIONAL_COMPARISONS_COMPLETE_PHYSICAL_VALIDATION_UNRESOLVED',
        provenance=p,script_sha256=sha(Path(__file__)),native_sha256=sha(D/'isae-sa13.json'),
        evidence_sha256={f:sha(D/f) for f in ['isae-sa13-sources.json','isae-sa13-velocity.json','isae-sa13-wasm.json',
            'isae-sa13-browser.json','isae-sa13-endpoint-candidate.patch','isae-sa13-endpoint-candidate-native.json',
            'isae-sa13-endpoint-candidate-wasm.json','isae-sa13-endpoint-candidate-browser.json']},
        comparisons=comparisons,mesh=mesh,physical_scale_checks=scale,conservation=conservation,
        runtime_status=wasm['status'],runtime_display=wasm['display'],
        archived_curve_policy='All original labels and NaN gaps are retained in the source audit and raw-series plot. Archived curves have no supplied executable inputs or radius derivatives. No physical parity score is assigned to these ambiguous curves.',
        conventions=['No fitted forces, pressures, geometry, core radii, angle shifts or solver tolerances.',
            'All 75 finite force points and 22 pressure points are retained. One R33 force point lies outside the explicitly reconstructed hull and is not extrapolated.',
            'Force comparison uses body-axis transverse force per axial length. A global wind-axis lift coefficient is not substituted.',
            'Primary load normalization is assumed for the digitized experimental ordinates. R101 uses an explicitly conditional dimensional scale; its archived ASWING ordinate is unresolved.',
            'R33/RS1 reference diameter is the maximum tabulated outline diameter; cubic overshoot is recorded separately.',
            'The primary RS1 angle9deg is the main comparison; the ISAE-caption10deg case remains a separate diagnostic.',
            'Body strips are averaged over each interval and linearly interpolated only inside their midpoint range. An independent pointwise body-law value is retained separately.',
            'Pressure is100Cp sampled just outside the public body mask, with two surface-offset sensitivity cases.',
            'Successful numerical convergence and runtime replay do not establish experimental accuracy.'],
        limitations=sources['limitations'])
    (D/'isae-sa13-comparison.json').write_text(json.dumps(out,indent=2)+'\n')
    plots(out,sources,native)
    report(out,velocity,wasm,browser,candidate)
    print(out['status'],len(comparisons),'comparison groups',flush=True)


def plots(out,sources,native):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    colors=['#e69f00','#56b4e9','#009e73','#0072b2']
    fig,axes=plt.subplots(2,2,figsize=(13,9),layout='constrained')
    for ax,case in zip(axes.flat,sources['cases']):
        name=case['name'];factor=multiplier(case)
        for n,color in zip([32,64,128,256],colors):
            row=next(r for r in native['rows'] if r['specification']==dict(case=name,panels=n,
                alpha=case['primary_alpha'],length=1.,surface_offset=1e-6))
            r=row['result'];curve=r['pressure_profile'] if name=='pressure' else r['profiles']
            ax.plot([v['t'] for v in curve],[v['Cp_percent'] if name=='pressure' else v['transverse_density']*factor for v in curve],
                    color=color,lw=1.15,label=f'OpenSwing N={n}')
        measured=next(c for c in out['comparisons'] if c['specification']==row['specification'])['points']
        ax.scatter([v['t'] for v in measured],[v['observed'] for v in measured],s=20,facecolors='none',edgecolors='black',label='ISAE measured points')
        ax.set(xlabel='Reconstructed x/L',ylabel='100 Cp' if name=='pressure' else 'f transverse / q [ft]' if name=='r101' else 'f transverse / (q D)',
               title=f"{'ZR III' if name=='pressure' else case['primary_hull']}, alpha={case['primary_alpha']:g}° (conditional geometry)")
        ax.grid(alpha=.2);ax.legend(fontsize=8)
    fig.suptitle('SA-13: conditional outline reconstructions; no parameter fitting')
    for extension in ['png','svg']:fig.savefig(D/f'isae-sa13-comparison.{extension}',dpi=150)
    plt.close(fig)
    fig,axes=plt.subplots(2,2,figsize=(13,9),layout='constrained')
    for ax,case in zip(axes.flat,sources['cases']):
        for series,style,color in zip(case['series'][:3],['o','-','--'],['black','#0072b2','#e69f00']):
            a=np.array([[np.nan if v is None else v for v in r] for r in series['xy']])
            ax.plot(a[:,0],a[:,1],style,color=color,ms=3,lw=1,label=series['label'])
        ax.set(title=case['name']+' — original stored series',xlabel='Stored abscissa (unscaled)',ylabel='Stored ordinate (unscaled)')
        ax.grid(alpha=.2);ax.legend(fontsize=8)
    fig.suptitle('Raw SA-13 series: original labels preserved; archived normalization unresolved')
    for extension in ['png','svg']:fig.savefig(D/f'isae-sa13-raw-series.{extension}',dpi=150)
    plt.close(fig)


def report(out,velocity,wasm,browser,candidate):
    lines=['# SA-13 airships: conditional numerical comparison','',
        '**Physical validation remains unresolved.** All 38 native calculations and 38 WebAssembly numerical replays completed. These use four explicitly reconstructed hulls, because the upstream family supplies figures without original `.asw` inputs. The WebAssembly display check exposes an endpoint-roundoff defect, recorded below.','',
        '[Source audit and primary references](isae-sa13-sources.md) · [Machine-readable comparison](isae-sa13-comparison.json) · [Native results](isae-sa13.json) · [Independent velocity integration](isae-sa13-velocity.json) · [WebAssembly results](isae-sa13-wasm.json) · [Offline browser results](isae-sa13-browser.json) · [Evidence audit](isae-sa13-checks.json)','',
        '## Comparison with measured points','',
        'The table uses the primary-source angle, N=256, and the explicitly stated normalization. It reports discrepancies, not a pass/fail accuracy certification. Experimental uncertainty and the exact original geometry/operating inputs have not been recovered.','',
        '| Hull | Angle | Compared / retained points | Ordinate | RMSE | N128→256 maximum change |',
        '|---|---:|---:|---|---:|---:|']
    for c in out['comparisons']:
        q=c['specification']
        if q['panels']!=256 or not c['primary_angle']:continue
        m=c['metrics'];delta=next(v for v in out['mesh'] if v['case']==q['case'] and v['fine']==256)
        unit='100Cp' if q['case']=='pressure' else 'f/q [ft], conditional scale' if q['case']=='r101' else 'f/(qD)'
        lines.append(f"| {q['case']} | {q['alpha']:g}° | {m['available']} / {m['requested']} | {unit} | {m['rmse']:.7g} | {delta['maximum_absolute_change']:.7g} |")
    lines+=['','![Conditional comparisons](isae-sa13-comparison.png)','',
        'The one excluded R33 point is outside the reconstructed closed hull; its source coordinate and measurement remain in the JSON. No extrapolation fills it. The finite measured sample count is 75 for force and 22 for pressure.','',
        'RS-1 is 9° in NACA-TR-405, although the ISAE caption says 10°. The separate 10° diagnostic has larger force RMSE. R101 uses a different, dimensional force ordinate: the 33.01-inch model length supplies a conditional conversion to feet. R33 and RS1 use maximum tabulated outline diameter; natural cubic radius overshoot is a separate geometry uncertainty.','',
        'Pressure is static gauge pressure coefficient100Cp. The primary NACA-TM-574 case is ZR III, while the ISAE filename says R101. Treating these values as nonnegative local dynamic pressure would be incorrect.','',
        '## Numerical checks and remaining physics','',
        'The native study spans 32, 64, 128 and 256 intervals. Closed-body net force tends to zero, and the integrated moment tends to the independently integrated squared-radius volume law. Local force profiles remain sensitive to radius derivatives and digitization noise; their mesh changes are not uniformly decreasing. These checks concern the implemented body law and do not add finite-body apparent-mass corrections, viscous stern forces, boundary-layer displacement or an independently measured geometry.','',
        '| Pressure intervals | Max velocity difference [m/s] | Max 100Cp difference [percentage points] |',
        '|---:|---:|---:|']
    for r in velocity['rows']:
        if r['specification']['surface_offset']!=1e-6:continue
        lines.append(f"| {r['specification']['panels']} | {r['maximum_velocity_difference']:.7g} | {r['maximum_Cp_percent_difference']:.7g} |")
    lines+=['','The independent calculation integrates the declared axial source law with adaptive quadrature split at every spline knot. It retains the implemented source core R/2. Its finest-mesh discrepancy is much smaller than the measurement discrepancy. This verifies numerical integration of that regularized field; it does not establish an impermeable surface or experimental pressure accuracy. Surface offsets 1e-4, 1e-6 and 1e-8 are reported without changing the body mask.','',
        'Four R101 scale checks use the physical 33.01-inch length and verify coefficient invariance, force scaling with length squared and moment scaling with length cubed. The full report retains all errors and all 38 conservation checks.','',
        'The evidence audit also compares every native strip against exact area-difference transverse forces and piecewise-polynomial local moments. This separates body quadrature error from the subsequent strip-profile interpolation and from uncertainty in the radius table.','',
        '## Runtime and display defect','',
        f"All 38 numerical states meet the native/WebAssembly comparison tolerances. Overall runtime status is `{wasm['status']}` because display behavior is checked separately.",'',
        '| Hull | Native display | WebAssembly display | WebAssembly tail radius |','|---|---|---|---:|']
    for r in wasm['display']:
        lines.append(f"| {r['case']} | {r['native_result']['status']} | {r['result']['status']} | {r['endpoint_radii'][-1]:.7g} |")
    lines+=['','The offline browser reproduces both failures, and its eight available body-load solves match the native calculations. Pressure at the exact measurement stations is checked in Pyodide; the browser pressure-plane UI does not supply those same stations.','',
        'A mathematically zero spline endpoint can evaluate as a tiny negative number. The display correctly rejects negative radii, so this roundoff prevents loading affected models. An [isolated endpoint candidate](isae-sa13-endpoint-candidate.patch) returns the exact tabulated value at a segment endpoint. It does not clip radii, change nearby values or alter spline derivatives.','',
        'Candidate evidence: all 279 original input files retain their parse outcomes; 4,767 distributions are checked; first through third derivatives remain bitwise unchanged. All 38 candidate WebAssembly numerical cases match the native baseline. All four candidate display models construct with exactly zero endpoint radii. The offline candidate browser passes 16 solve/export cases and still rejects both genuinely negative-radius controls. See [native audit](isae-sa13-endpoint-candidate-native.json), [WebAssembly replay](isae-sa13-endpoint-candidate-wasm.json), and [browser replay](isae-sa13-endpoint-candidate-browser.json).','',
        'The candidate is not applied to production or the released app. The active winglet calculations still use pinned modules. Applying it requires a controlled source transition and broader regression checks; it also leaves interior spline overshoot and geometric uncertainty unresolved.','',
        '## Archived ASWING curves','',
        'The original Continuous/Discrete ASWING 5.96 labels and NaN gaps are preserved below. The archive supplies no matching input files or modified radius-derivative implementation. R101 normalization and the plotted geometry scale remain unresolved, so these curves do not receive a physical parity score.','',
        '![Original archived series](isae-sa13-raw-series.png)','',
        '## Work needed for a physical validation claim','',
        '- Recover or independently establish the radius tables, geometric scale, maximum diameter, operating states and measurement uncertainty.',
        '- Reconcile the RS1 incidence, R101 dimensional ordinate, pressure hull identity, and reported aspect ratios.',
        '- Apply the tested endpoint candidate through a controlled source transition, finish broader regression checks and verify the released browser build.',
        '- Establish the expected finite-body and viscous contributions, and compare them without fitting corrections to the measured curves.',
        '- Reproduce the archived ASWING Continuous/Discrete states with traceable executable inputs and radius derivatives.','',
        'This study does not increase the released family coverage or mark an ASWING-parity requirement complete.','']
    (D/'isae-sa13.md').write_text('\n'.join(lines))


if __name__=='__main__':
    main()
