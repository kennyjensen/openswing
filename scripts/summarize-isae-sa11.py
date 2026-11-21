"""Compare SA-11 predictions with the archive and digitized measurements.

An explicit --partial snapshot keeps uncomputed requests visible. It never
produces the completed-study report or changes validation coverage.
"""
from pathlib import Path
from collections import Counter
import argparse, hashlib, importlib.util, json, sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from isae_sa11_reference import sha, NAMES, REVISION
spec=importlib.util.spec_from_file_location('sa11',ROOT/'scripts/verify-isae-sa11.py')
sa11=importlib.util.module_from_spec(spec);spec.loader.exec_module(sa11)
D=ROOT/'docs/validation'


def metrics(predicted, reference):
    a,b=np.array(predicted),np.array(reference)
    assert a.shape==b.shape and np.all(np.isfinite(a)) and np.all(np.isfinite(b))
    if not len(a):return dict(count=0,rmse=None,bias=None,maximum_absolute_error=None)
    error=a-b
    return dict(count=len(a),rmse=float(np.sqrt(np.mean(error**2))),bias=float(error.mean()),
        maximum_absolute_error=float(np.max(abs(error))))


def slope(rows, key):
    if len(rows)<3:return None
    x=np.array([r['alpha'] for r in rows]);y=np.array([r[key] for r in rows])
    if np.ptp(x)<1.:return None
    return float(np.polyfit(x,y,1)[0])


def load_study(sources, partial):
    modules={p.name:sha(p) for p in (ROOT/'openswing').glob('*.py')}
    provenance=dict(revision=REVISION,modules=modules,script_sha256=sha(ROOT/'scripts/verify-isae-sa11.py'),
        reference_script_sha256=sha(ROOT/'scripts/isae_sa11_reference.py'),source_report_sha256=sha(D/'isae-sa11-sources.json'))
    folder=ROOT/'.reference/isae-sa11-runs'/hashlib.sha256(json.dumps(provenance,sort_keys=True).encode()).hexdigest()
    assert json.loads((folder/'identity.json').read_text())==provenance
    cases=sa11.case_entries(sources);plan=sa11.requests(cases,sources);assert len(plan)==5304
    rows={}
    for request in plan:
        key=sa11.request_key(request);path=folder/(key+'.json')
        if not path.exists():
            assert partial, f'Native request not finished: {request}'
            rows[key]=dict(specification=request,status='not_computed');continue
        row=json.loads(path.read_text());assert row['specification']==request
        assert row['status'] in ['computed','rejected']
        row.update(cache_path=path.relative_to(ROOT).as_posix(),cache_sha256=sha(path));rows[key]=row
    for case in cases:case['runs']=[r for r in rows.values() if r['specification']['case']==case['case_id']]
    if not partial:
        report=json.loads((D/'isae-sa11.json').read_text())
        assert report['provenance']==provenance and report['total']==5304
        original={sa11.request_key(r['specification']):r for c in report['cases'] for r in c['runs']}
        assert rows==original
    return cases,rows,provenance


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--partial',action='store_true')
    parser.add_argument('--output-dir',type=Path,default=D);args=parser.parse_args()
    destination=args.output_dir;destination.mkdir(parents=True,exist_ok=True)
    sources=json.loads((D/'isae-sa11-sources.json').read_text())
    normalization=json.loads((D/'isae-sa11-archive.json').read_text())
    assert normalization['source_report_sha256']==sha(D/'isae-sa11-sources.json')
    cases,lookup,provenance=load_study(sources,args.partial)
    case_by_name={c['name']:c for c in cases}
    def state(case,panels,speed,alpha,pg='speed',frozen=False):
        return lookup[sa11.request_key(sa11.specification(case,panels,speed,alpha,pg,frozen))]
    archive=[]
    for table in sources['archived']:
        case=case_by_name[table['name']];speed=table['speeds'][0]
        for panels in [25,50,100]:
            for frozen in [False,True]:
                for pg in ['speed','zero']:
                    selected=table['rows'] if pg=='speed' else [r for r in table['rows'] if r[71] in [0.,5.,10.]]
                    pairs=[];outcomes=Counter()
                    for reference in selected:
                        run=state(case,panels,speed,reference[71],pg,frozen);outcomes[run['status']]+=1
                        if run['status']!='computed':continue
                        result=run['result'];pairs.append(dict(alpha=reference[71],
                            predicted={k:result[k] for k in ['CL','CD','CDi','CDi_near','Cm','Cm_origin']},
                            archived=dict(CL=reference[77],CD=reference[78],CDi=reference[79],Cm=reference[80])))
                    errors={key:metrics([r['predicted'][key] for r in pairs],[r['archived'][key] for r in pairs])
                            for key in ['CL','CD','CDi','Cm']}
                    errors['Cm_origin_diagnostic']=metrics([r['predicted']['Cm_origin'] for r in pairs],[r['archived']['Cm'] for r in pairs])
                    errors['CDi_near_diagnostic']=metrics([r['predicted']['CDi_near'] for r in pairs],[r['archived']['CDi'] for r in pairs])
                    audit=next(r for r in normalization['rows'] if r['path']==table['path'])
                    archive.append(dict(case=case['case_id'],name=case['name'],nominal_mach=table['nominal_mach'],
                        actual_speed=speed,panels=panels,frozen=frozen,pg=pg,requested=len(selected),
                        source_reference_consistent=audit['source_reference_consistent'],
                        implied_area_at_supplied_density=audit['existing_source_area_matching_normalization'],
                        outcomes=dict(outcomes),errors=errors,pairs=pairs))
    experimental=[]
    for mach,data in sources['experimental'].items():
        for name,reference in data['lift'].items():
            case=case_by_name[name];speed=float(mach)*float(sa11.parse_asw(case['source']).constants[2])
            for panels in [25,50,100]:
                pairs=[];outcomes=Counter();all_points=[]
                for point in reference['values']:
                    alpha,measured=point['xy'];run=state(case,panels,speed,alpha);outcomes[run['status']]+=1
                    item=dict(alpha=alpha,measured_CL=measured,csv_row=point['row'],status=run['status'])
                    if run['status']=='computed':
                        item.update(predicted_CL=run['result']['CL'],predicted_CD=run['result']['CD']);pairs.append(item)
                    elif run['status']=='rejected':item['error']=run['error']
                    all_points.append(item)
                measured_slope=slope(pairs,'measured_CL');predicted_slope=slope(pairs,'predicted_CL')
                experimental.append(dict(case=case['case_id'],name=name,nominal_mach=float(mach),speed=speed,panels=panels,
                    requested=len(reference['values']),outcomes=dict(outcomes),
                    CL_error=metrics([r['predicted_CL'] for r in pairs],[r['measured_CL'] for r in pairs]),
                    measured_slope_on_computed_subset=measured_slope,predicted_slope_on_computed_subset=predicted_slope,
                    relative_slope_error=None if measured_slope in [None,0.] else predicted_slope/measured_slope-1,
                    rows=all_points))
    refinement=[]
    for case in cases:
        for speed in [240.,272.]:
            for alpha in [0.,5.,10.]:
                for lower,upper in [(25,50),(50,100)]:
                    a,b=state(case,lower,speed,alpha),state(case,upper,speed,alpha)
                    item=dict(case=case['case_id'],speed=speed,alpha=alpha,meshes=[lower,upper],statuses=[a['status'],b['status']])
                    if a['status']==b['status']=='computed':
                        item['coefficient_changes']={k:b['result'][k]-a['result'][k] for k in ['CL','CD','CDi','Cm']}
                        item['maximum_normal_mach']=[r['result']['maximum_normal_mach']['normal_mach'] for r in [a,b]]
                    refinement.append(item)
    counts=Counter(r['status'] for r in lookup.values());group_counts=[]
    for case in cases:
        for panels in [25,50,100]:
            subset=[r for r in case['runs'] if r['specification']['panels']==panels]
            group_counts.append(dict(case=case['case_id'],panels=panels,requested=len(subset),
                outcomes=dict(Counter(r['status'] for r in subset)),
                rejection_kinds=dict(Counter((r.get('details') or {}).get('kind','circulation_or_other_failure')
                    for r in subset if r['status']=='rejected'))))
    computed=[r['result'] for r in lookup.values() if r['status']=='computed']
    output=dict(status='INCOMPLETE_SNAPSHOT_NOT_VALIDATION' if args.partial else 'PARTIAL_VALIDATION_DISCREPANCIES_REMAIN',
        provenance=provenance,script_sha256=sha(Path(__file__)),requested=len(lookup),outcomes=dict(counts),
        grouped_outcomes=group_counts,archived_comparisons=archive,experimental_lift=experimental,mesh_refinement=refinement,
        maximum_residual=max((r['residual'] for r in computed),default=None),
        maximum_wrench_error=max((r['independent_wrench_error'] for r in computed),default=None),
        maximum_drag_decomposition_error=max((r['drag_decomposition_error'] for r in computed),default=None),
        cache_manifest=[{k:r[k] for k in ['specification','status','cache_path','cache_sha256']} for r in lookup.values() if r['status']!='not_computed'],
        archive_normalization_audit_sha256=sha(D/'isae-sa11-archive.json'),
        comparison_notes=[
            'Every error metric is conditional on the reported computed subset. Missing/rejected states are not scored as zero error.',
            'Experimental comparisons use exact nominal Mach times the source sound speed; archived comparisons use actual recorded speeds.',
            'PG-off and moment-origin/near-field-drag alternatives are diagnostics; none is selected by smallest error.',
            'The archived circulation discretization and initial K/F setting remain unknown; this sweep uses the pointwise default.',
            'Mach .75/.78 archived force/coefficient normalization implies S near97.67 at the supplied density; the comparison inputs use .9329. Those setup conflicts are not solver error measurements.',
            'Source Sref and section properties remain unchanged. No drag offset or parameter fitting is applied.',
            'CL slope is a summary regression on the same computed subset, not a fitted solver parameter or a full-curve accuracy claim.'],
        limitations=sources['limitations'])
    if not args.partial:
        drag=json.loads((D/'isae-sa11-drag.json').read_text());assert drag['identity']['study_sha256']==sha(D/'isae-sa11.json')
        output['fixed_lift_drag']=drag['summary'];output['drag_sha256']=sha(D/'isae-sa11-drag.json')
        output['matched_lift_coverage']=dict(requested=len(drag['rows']),
            single_observed_root=sum(len(r['roots'])==1 for r in drag['rows']),
            multiple_observed_roots=sum(len(r['roots'])>1 for r in drag['rows']),
            no_observed_root=sum(not r['roots'] for r in drag['rows']),
            complete_sampled_scans=sum(s['complete_single_root_scan'] for s in drag['summary']),
            failed_root_brackets=sum(len(r['failed_brackets']) for r in drag['rows']))
        output['study_sha256']=sha(D/'isae-sa11.json')
        output['source_coverage']=dict(archived_polars=len(sources['archived']),
            archived_rows=sum(len(t['rows']) for t in sources['archived']),
            archived_convergence_flags=dict(Counter(str(r[2]) for t in sources['archived'] for r in t['rows'])),
            experimental_lift_points=sum(len(r['values']) for data in sources['experimental'].values() for r in data['lift'].values()),
            experimental_drag_points=sum(len(r['values']) for data in sources['experimental'].values() for r in data['drag'].values()))
    prefix='isae-sa11-progress' if args.partial else 'isae-sa11-comparison'
    (destination/(prefix+'.json')).write_text(json.dumps(output,indent=2)+'\n')
    plt.rcParams.update({'font.size':9,'svg.fonttype':'none'})
    fig,axes=plt.subplots(2,4,figsize=(17,8),layout='constrained')
    for i,(mach,data) in enumerate(sources['experimental'].items()):
        for j,name in enumerate(NAMES):
            ax=axes[i,j];case=case_by_name[name];speed=float(mach)*float(sa11.parse_asw(case['source']).constants[2])
            for panels,color,style in [(25,'#e6362b',':'),(50,'#d87b00','--'),(100,'#326bdd','-')]:
                angles=sorted(set([r['xy'][0] for r in data['lift'][name]['values']]+([-1.]+np.linspace(0,10,41).tolist() if panels>25 else [])))
                runs=[state(case,panels,speed,a) for a in angles]
                ax.plot(angles,[r['result']['CL'] if r['status']=='computed' else np.nan for r in runs],
                    ls=style,color=color,label=f'OpenSwing N={panels}')
            table=next(t for t in sources['archived'] if t['name']==name and t['nominal_mach']==float(mach))
            ax.plot([r[71] for r in table['rows']],[r[77] for r in table['rows']],color='#8b4caf',ls='-.',label='Archived ASWING')
            measured=np.array([r['xy'] for r in data['lift'][name]['values']]);ax.scatter(measured[:,0],measured[:,1],facecolors='none',edgecolors='black',s=23,label='ISAE digitization')
            ax.set(title=f'{name}\nMach {mach}; archive V={table["speeds"][0]:g}',xlabel='Body alpha [deg]',ylabel='CL');ax.grid(alpha=.2)
    axes[0,0].legend(fontsize=7)
    fig.suptitle(('INCOMPLETE SNAPSHOT — ' if args.partial else '')+'SA-11: current influences, speed PG; '+
        ('failures and pending states leave gaps' if args.partial else 'rejected states leave gaps'))
    for suffix in ['png','svg']:fig.savefig(destination/(prefix+'-lift.'+suffix),dpi=170)
    plt.close(fig)
    if not args.partial:
        fig,axes=plt.subplots(2,4,figsize=(17,8),layout='constrained')
        for i,(mach,data) in enumerate(sources['experimental'].items()):
            for j,name in enumerate(NAMES):
                ax=axes[i,j];case=case_by_name[name]
                for panels,color,marker in [(50,'#d87b00','+'),(100,'#326bdd','x')]:
                    group=[r for r in drag['rows'] if r['request']['scan_id']==f"{case['case_id']}_M{mach}_N{panels}"]
                    values=[(r['request']['target_CL'],root['result']['CD']) for r in group for root in r['roots']]
                    ax.scatter([r[0] for r in values],[r[1] for r in values],color=color,marker=marker,
                        label=f'OpenSwing N={panels}: {len(values)}/{len(group)} roots')
                table=next(t for t in sources['archived'] if t['name']==name and t['nominal_mach']==float(mach))
                ax.plot([r[77] for r in table['rows']],[r[78] for r in table['rows']],color='#8b4caf',ls='-.',label='Archived ASWING, raw')
                measured=np.array([r['xy'] for r in data['drag'][name]['values']])
                ax.scatter(measured[:,0],measured[:,1],facecolors='none',edgecolors='black',s=23,label='ISAE digitization')
                ax.set(title=f'{name}\nMach {mach}; archive V={table["speeds"][0]:g}',xlabel='CL',ylabel='CD')
                ax.grid(alpha=.2);ax.legend(fontsize=6.5)
        fig.suptitle('SA-11: raw drag at matched lift; all scans have unresolved intervals; no CD offsets')
        for suffix in ['png','svg']:fig.savefig(destination/(prefix+'-drag.'+suffix),dpi=170)
        plt.close(fig)
    lines=['# SA-11 '+('incomplete comparison snapshot' if args.partial else 'numerical comparison'),'',
        '**This is not a validation pass.** '+('The full sweep is still running. ' if args.partial else '')+
        f"Of {len(lookup):,} planned states, {counts['computed']:,} computed, {counts['rejected']:,} rejected, and {counts['not_computed']:,} are pending.",'',
        'Errors below use only computed states; rejected and pending states remain explicit. '+
        'The measurements use exact nominal Mach, while the archived comparisons use the recorded speed. '+
        'The coefficients retain each source file’s reference area and section properties.','',
        'An [independent archive audit](isae-sa11-archive.md) also finds a force/coefficient normalization conflict at Mach 0.75/0.78. '+
        'At the supplied density those archives imply an area near 97.67 m², versus 0.9329 m² in the comparison inputs.','',
        '| Model | Mach | N | Computed / measured points | Rejected | Pending | CL RMSE | Relative slope error on computed subset |',
        '| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |']
    for row in experimental:
        error=row['CL_error']['rmse'];relative=row['relative_slope_error']
        lines.append(f"| {row['case']} | {row['nominal_mach']:g} | {row['panels']} | {row['outcomes'].get('computed',0)} / {row['requested']} | "+
            f"{row['outcomes'].get('rejected',0)} | {row['outcomes'].get('not_computed',0)} | "+
            ('—' if error is None else f'{error:.5g}')+' | '+('—' if relative is None else f'{100*relative:.2f}%')+' |')
    lines+=['',f'![SA-11 lift comparisons]({prefix}-lift.png)','',
        'The two unchanged standalone wings and three explicitly reconstructed joint inputs are distinguished in the source audit. '+
        'The cant0 input has no assigned experiment. The transonic tunnel data, source geometry and section differences, '+
        'unknown archived discretization, and growing local Mach under refinement prevent an accuracy claim.','',
        'See [source audit](isae-sa11-sources.md), [full numerical data]('+prefix+'.json), '+
        '[Fourier sensitivity](isae-sa11-circulation.json), and [independent velocity integration](isae-sa11-velocity.json).','']
    if not args.partial:
        coverage=output['matched_lift_coverage']
        lines+=['## Completed scope and rejected states','',
            'The completed sweep includes all 656 rows of 16 archived polars and all 88 digitized lift points, '+
            'with three meshes (N25/50/100). All archived convergence flags are one. Current/frozen influences and '+
            'PG-off alternatives are setup diagnostics; they are not selected by lowest discrepancy. '+
            'The cant0 input is retained as an unmeasured diagnostic.','',
            '| Model | N | Computed | Rejected: local Mach | Other solver failure |',
            '| --- | ---: | ---: | ---: | ---: |']
        for row in group_counts:
            kinds=row['rejection_kinds']
            lines.append(f"| {row['case']} | {row['panels']} | {row['outcomes'].get('computed',0)} | "+
                f"{kinds.get('section_normal_mach',0)} | {sum(v for k,v in kinds.items() if k!='section_normal_mach')} |")
        lines+=['','These are invalid or unresolved model states, not measurements of physical supersonic flow. '+
            'The [independent swept-line diagnosis](swept-lifting-line-limit.md) establishes a singular same-line '+
            'force-velocity limit for smooth prescribed circulation. It does not resolve every winglet junction '+
            'or prove how the reference ASWING executable treats them. No core, guard or physical input was tuned.','',
            '## Drag at matched lift','',
            f"All 83 measured drag points were requested at N50 and N100 ({coverage['requested']} requests). "+
            f"There are {coverage['single_observed_root']} requests with one observed root, "+
            f"{coverage['multiple_observed_roots']} with multiple observed roots, and {coverage['no_observed_root']} without a root. "+
            'Every sampled angle scan contains rejected intervals, so an observed root does not establish uniqueness. '+
            'The scan includes −1° to 10° and the exact measured lift angles; failed intervals are not bridged or extrapolated.','',
            '| Model | Mach | N | One observed root / requested | No root | Rejected scan intervals | Raw CD RMSE on observed roots |',
            '| --- | ---: | ---: | ---: | ---: | ---: | ---: |']
        for row in drag['summary']:
            error=row['raw_CD_observed_single_root']['rmse']
            lines.append(f"| {row['case']} | {row['nominal_mach']:g} | {row['panels']} | "+
                f"{row['single_observed_root']} / {row['requested']} | {row['no_observed_root']} | "+
                f"{row['unresolved_scan_intervals']} | "+('—' if error is None else f'{error:.6g}')+' |')
        lines+=['',f'![SA-11 matched-lift drag]({prefix}-drag.png)','',
            'The plot and main errors use raw CD. The upstream MATLAB offsets (+0.0064 at Mach 0.7 and '+
            '+0.0075 at Mach 0.8) appear only as separately labeled diagnostics in '+
            '[the drag data](isae-sa11-drag.json); they are not applied to the solver. '+
            'Errors on the small N100 surviving subset cannot establish an improvement over N50.','',
            '## Runtime verification and remaining work','',
            'The existing 40-state WebAssembly replay matches 16 native solutions and 24 rejections, plus nine literal-input '+
            'rejections. The 14-state offline browser check matches eight solutions and six rejections, plus three literal-input '+
            'rejections. These samples do not replay all 5,304 states or the newly computed drag roots. '+
            'See [numerical audit](isae-sa11-checks.json) and [matched-lift audit](isae-sa11-drag-checks.json).','',
            'Physical validation remains incomplete: resolve the swept/junction flow treatment, source geometry and '+
            'normalization conflicts, recover archived discretization and initialization, and independently extract '+
            'measurements with uncertainties. The ISAE report treats SA-11 as a transonic tendency study; '+
            'PG alone does not model shocks or wave drag. This completed evidence package is ahead of the released app.','']
    (destination/(prefix+'.md')).write_text('\n'.join(lines))
    print(output['status'],dict(counts),destination/prefix,flush=True)


if __name__=='__main__':main()
