"""Compare SA-14 global lift without treating failed archive states as truth."""
from pathlib import Path
import hashlib
import json
import numpy as np
ROOT=Path(__file__).resolve().parents[1];D=ROOT/'docs/validation'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()


def metrics(points):
    available=[p for p in points if p['predicted'] is not None]
    errors=np.array([p['predicted']-p['observed'] for p in available])
    return dict(requested=len(points),compared=len(available),unavailable=len(points)-len(available),
        compared_alpha_range=[min(p['alpha'] for p in available),max(p['alpha'] for p in available)] if available else None,
        rmse=float(np.sqrt(np.mean(errors**2))) if len(errors) else None,
        bias=float(np.mean(errors)) if len(errors) else None,
        maximum_absolute_error=float(np.max(abs(errors))) if len(errors) else None)


def main():
    native_path=D/'isae-sa14-polars.json';native=json.loads(native_path.read_text())
    assert native['status']=='FULL_POLAR_CALCULATIONS_COMPLETE_COMPARISONS_PENDING'
    assert len(native['rows'])==native['computed']+native['rejected']==2952
    for name,pin in native['provenance']['inputs'].items():assert sha(ROOT/name)==pin,name
    assert native['provenance']['modules']=={p.name:sha(p) for p in (ROOT/'openswing').glob('*.py')}
    for row in native['rows']:assert sha(ROOT/row['cache_path'])==row['cache_sha256']
    def key(q):return (q['case'],q['panels'],q['alpha'],q['pg'],q['frozen'])
    lookup={key(r['specification']):r for r in native['rows']};assert len(lookup)==2952
    grouped={}
    for ref in native['references']:
        for n in [25,50,100]:
            for frozen in [False,True]:
                for pg in (['zero','speed'] if ref['kind']=='archive' else ['primary_0.19','zero','speed']):
                    spec=dict(case=ref['case'],panels=n,alpha=ref['alpha'],pg=pg,frozen=frozen)
                    row=lookup[key(spec)];predicted=None;proxy=None
                    if row['status']=='computed':
                        parent,field=ref['observable'].split('.');predicted=row['result'][parent][field]
                        proxy=row['result']['archived_area_multiplier_CL']
                    point=dict(ref,predicted=predicted,openswing_status=row['status'],
                        error=row.get('error'),cache_path=row['cache_path'],cache_sha256=row['cache_sha256'],
                        source_matlab_area_multiplier_proxy=proxy)
                    group=(ref['kind'],ref['case'],ref.get('label'),ref['observable'],n,pg,frozen)
                    grouped.setdefault(group,[]).append(point)
    comparisons=[]
    for group,points in grouped.items():
        kind,case,label,observable,n,pg,frozen=group
        points.sort(key=lambda p:p['alpha'])
        row=dict(kind=kind,case=case,label=label,observable=observable,panels=n,pg=pg,frozen=frozen,
            points=points,all_available=metrics(points),within_13_degrees=metrics([p for p in points if abs(p['alpha'])<=13]))
        if kind=='archive':
            row['converged_archive_only']=metrics([p for p in points if p['converged']])
            row['unconverged_archive_diagnostic']=metrics([p for p in points if not p['converged']])
        comparisons.append(row)
    assert len(comparisons)==90
    rejections=[]
    for row in native['rows']:
        if row['status']=='rejected':rejections.append({k:row[k] for k in ['specification','error','details','cache_path','cache_sha256']})
    mesh=[]
    for ref in native['references']:
        for frozen in [False,True]:
            for pg in (['zero','speed'] if ref['kind']=='archive' else ['primary_0.19','zero','speed']):
                values=[]
                for n in [25,50,100]:
                    row=lookup[(ref['case'],n,ref['alpha'],pg,frozen)]
                    parent,field=ref['observable'].split('.')
                    values.append(row['result'][parent][field] if row['status']=='computed' else None)
                mesh.append(dict(reference=ref,pg=pg,frozen=frozen,panels=[25,50,100],values=values,
                    deltas=[b-a if a is not None and b is not None else None for a,b in zip(values,values[1:])]))
    flags={case:dict(total=60,converged=sum(r['converged'] for r in native['references'] if r['kind']=='archive' and r['case']==case))
           for case in ['wing_body','infinite_body','wing_only']}
    assert [flags[c]['converged'] for c in ['wing_body','infinite_body','wing_only']]==[13,43,60]
    mesh_summary=[]
    for label in ['CL_WB_S_WB','CL_WB_SW','CL_W_SW']:
        for bound in [13.,32.]:
            selected=[r for r in mesh if r['reference'].get('label')==label and abs(r['reference']['alpha'])<=bound and r['pg']=='primary_0.19' and not r['frozen']]
            steps=[]
            for i in [0,1]:
                values=[abs(r['deltas'][i]) for r in selected if r['deltas'][i] is not None]
                steps.append(dict(panels=[25,50] if i==0 else [50,100],compared=len(values),requested=len(selected),maximum_CL_change=max(values) if values else None))
            mesh_summary.append(dict(label=label,absolute_angle_limit=bound,pg='primary_0.19',frozen=False,steps=steps))
    runtime={}
    for name in ['wasm','browser']:
        path=D/f'isae-sa14-polars-{name}.json'
        if path.exists():
            r=json.loads(path.read_text());assert r['native_sha256']==sha(native_path) and r['modules']==native['provenance']['modules']
            runtime[name]=dict(status=r['status'],states=len(r['rows']),computed=sum(x['status']=='matching_solution' for x in r['rows']),
                rejected=sum(x['status']=='matching_rejection' for x in r['rows']),sha256=sha(path))
    output=dict(status='GLOBAL_LIFT_COMPARISONS_COMPLETE_FULL_FAMILY_VALIDATION_INCOMPLETE',
        native_sha256=sha(native_path),script_sha256=sha(Path(__file__)),provenance=native['provenance'],
        archive_flags=flags,native_outcomes=dict(computed=native['computed'],rejected=native['rejected']),
        comparisons=comparisons,mesh_comparisons=mesh,primary_mesh_summary=mesh_summary,rejections=rejections,runtime=runtime,
        interpretation=[
            'All224 source points remain present; unavailable OpenSwing predictions are null, not zero or interpolated.',
            'Archive metrics distinguish source-converged points from unconverged diagnostics. Printed convergence is necessary but not sufficient evidence of reference accuracy.',
            'Every experimental curve uses its primary observable and wing reference area. The source MATLAB constant-area proxy remains a separately labelled diagnostic.',
            'RMSE covers only the explicitly counted available states. Missing high-angle states invalidate a full-range accuracy or convergence claim.',
            'These calculations do not resolve swept-line force velocity, iw4 geometry/provenance, archive settings or experimental uncertainty.'])
    (D/'isae-sa14-polars-comparison.json').write_text(json.dumps(output,indent=2,allow_nan=False)+'\n')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,3,figsize=(14,4.7),layout='constrained')
    labels=['CL_WB_S_WB','CL_WB_SW','CL_W_SW']
    titles=['Wing/body total balance lift','Exposed wing with body','Exposed wing without body']
    for ax,label,title in zip(axes,labels,titles):
        for n,color,style in [(25,'#E69F00',':'),(50,'#56B4E9','--'),(100,'#0072B2','-')]:
            row=next(r for r in comparisons if r['label']==label and r['panels']==n and r['pg']=='primary_0.19' and not r['frozen'])
            ax.plot([p['alpha'] for p in row['points']],[p['predicted'] if p['predicted'] is not None else np.nan for p in row['points']],
                    style,color=color,marker='.',label=f'N{n}, {row["all_available"]["compared"]}/{row["all_available"]["requested"]} computed')
        ax.scatter([p['alpha'] for p in row['points']],[p['observed'] for p in row['points']],facecolors='none',edgecolors='black',s=25,label='Primary experiment')
        ax.set(title=title,xlabel='Angle of attack (degrees)',ylabel='CL, primary wing area');ax.grid(alpha=.2);ax.legend(fontsize=8)
    fig.suptitle('SA-14: exact measured angles, PG Mach 0.19, live influences; unresolved force-velocity limit',fontsize=11)
    for ext in ['png','svg']:fig.savefig(D/f'isae-sa14-global-lift.{ext}',dpi=160)
    plt.close(fig)
    fig,axes=plt.subplots(2,3,figsize=(14,8),layout='constrained')
    for column,case in enumerate(['wing_only','wing_body','infinite_body']):
        for row_index,n in enumerate([50,100]):
            ax=axes[row_index,column]
            for pg,frozen,color,style in [('zero',False,'#0072B2','-'),('speed',False,'#D55E00','-'),('zero',True,'#009E73','--'),('speed',True,'#CC79A7','--')]:
                row=next(r for r in comparisons if r['kind']=='archive' and r['case']==case and r['panels']==n and r['pg']==pg and r['frozen']==frozen)
                ax.plot([p['alpha'] for p in row['points']],[p['predicted'] if p['predicted'] is not None else np.nan for p in row['points']],
                    style,color=color,label=f'PG {pg}, {"frozen" if frozen else "live"}')
            for conv,color,marker,label in [(True,'black','o','Archive conv=1'),(False,'#777777','x','Archive conv=0')]:
                points=[p for p in row['points'] if p['converged']==conv]
                ax.scatter([p['alpha'] for p in points],[p['observed'] for p in points],s=16,marker=marker,color=color,label=label)
            ax.set(title=f'{case}, N{n}',xlabel='Angle of attack (degrees)',ylabel='CL, input reference area');ax.grid(alpha=.2);ax.legend(fontsize=7)
    fig.suptitle('SA-14 archived polars: unknown PG/freeze settings remain explicit alternatives',fontsize=12)
    for ext in ['png','svg']:fig.savefig(D/f'isae-sa14-archived-polars.{ext}',dpi=160)
    plt.close(fig)
    lines=['# SA-14 global lift comparisons','',
        '**The full family validation remains incomplete.** This study evaluates all 180 archived polar rows and all 44 digitized total/exposed-wing lift points at their exact angles. It preserves original inputs, archive convergence flags and unavailable OpenSwing states. [Source audit](isae-sa14-sources.md), [native results](isae-sa14-polars.json), [comparisons](isae-sa14-polars-comparison.json).','',
        f"The 2,952 requests produced {native['computed']:,} computed states and {native['rejected']} rejections. Three meshes, live/frozen influences, and explicit PG alternatives remain separate. These are finite-mesh comparisons, not a resolution of the [swept force-velocity limit](swept-lifting-line-limit.md).",'',
        '## Experimental lift','',
        'The table uses primary Mach 0.19, live influences and N100. All coefficients use the primary wing area. Total wing/body balance lift includes the body; the other two series use pressure-integrated exposed-wing lift outside 2|y|/b=0.1. Partial boundary strips use their exposed fraction. No source MATLAB area multiplier is substituted for these observables.','',
        '| Observable | Compared / source points | CL RMSE on available states | CL RMSE within ±13° |','|---|---:|---:|---:|']
    def fmt(v):return 'unavailable' if v is None else f'{v:.6g}'
    for label,title in zip(labels,titles):
        r=next(r for r in comparisons if r['label']==label and r['panels']==100 and r['pg']=='primary_0.19' and not r['frozen'])
        m=r['all_available'];small=r['within_13_degrees']
        lines.append(f"| {title} | {m['compared']} / {m['requested']} | {fmt(m['rmse'])} | {fmt(small['rmse'])} ({small['compared']}/{small['requested']}) |")
    changes={bound:[next(r for r in mesh_summary if r['label']==label and r['absolute_angle_limit']==bound)['steps'][1]['maximum_CL_change'] for label in labels] for bound in [13.,32.]}
    small=', '.join(f'{v:.5f}' for v in changes[13.]);full=', '.join(f'{v:.5f}' for v in changes[32.])
    lines+=['','All 44 points have computed predictions in this selected setting. Across the full sweep, missing predictions remain null values and breaks in plotted curves; a counted RMSE does not certify an omitted range. The exposed-wing predictions keep increasing at the largest sampled angles, while the measured exposed-wing lift declines after its peak. The supplied section properties do not reproduce that behavior.','',
        '![Global lift comparisons](isae-sa14-global-lift.png)','',
        f'Between N50 and N100, the largest primary-Mach/live-influence CL changes within ±13° are {small} for total wing/body lift, exposed wing/body lift and exposed wing-only lift respectively. Across the full measured range they are {full}. These are smaller than the experimental discrepancies, but do not establish a convergent force-point velocity.','',
        '## Archived ASWING curves','',
        '| Original input | Archive rows | Flagged converged | Flagged unconverged |','|---|---:|---:|---:|']
    for case,f in flags.items():lines.append(f"| {case} | {f['total']} | {f['converged']} | {f['total']-f['converged']} |")
    lines+=['','All archive rows remain available. Main archive error metrics use only rows flagged converged; separate diagnostics retain the other rows. The scripts toggle PG mode without recording its starting state and do not record mesh, circulation mode count or frozen-influence setting. Zero-PG and speed-derived PG, with live and frozen influences, are hypotheses rather than a fitted choice of the closest curve.','',
        '![Archived polar comparisons](isae-sa14-archived-polars.png)','',
        '## Runtime checks','']
    for name in ['wasm','browser']:
        if name in runtime:
            r=runtime[name];lines.append(f"- {name}: {r['states']} cases, {r['computed']} matching solutions and {r['rejected']} matching rejections. [Evidence](isae-sa14-polars-{name}.json).")
        else:lines.append(f'- {name}: pending for the extended sweep.')
    lines+=['','Runtime agreement verifies the executed numerical path; it does not resolve the physical model or source uncertainties.','',
        '## Remaining work','',
        '- Resolve the swept bound-line force-velocity treatment and verify it against both independent physics and reference ASWING behavior.',
        '- Recover or document the archive discretization and settings; compare original local-load exports independently of manually modified plotting arrays.',
        '- Resolve the iw=4° Figure15/17 source mapping and physical incidence geometry before comparing those 24 points.',
        '- Complete section-polar provenance, experimental uncertainty and higher-angle model-limit analysis.',
        '- Release the isolated endpoint repair after its broader regression and the pinned SA-11 studies finish.','',
        'The released family coverage count and broad feature-completion claims are unchanged.','']
    (D/'isae-sa14-polars.md').write_text('\n'.join(lines))
    print(output['status'],native['computed'],native['rejected'],flush=True)


if __name__=='__main__':main()
