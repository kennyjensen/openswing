"""Reconcile all SA-14 quantitative substudies without overstating validation."""
from pathlib import Path
from collections import Counter
import hashlib,json,sys
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from isae_sa14_reference import CACHE,sha,csv_series
D=ROOT/'docs/validation'


def main():
    names=['isae-sa14-sources','isae-sa14-pilot','isae-sa14-pilot-comparison','isae-sa14-checks',
        'isae-sa14-measurements','isae-sa14-volume','isae-sa14-polars','isae-sa14-polars-comparison',
        'isae-sa14-polars-checks','isae-sa14-load-exports','isae-sa14-incidence-sources',
        'isae-sa14-incidence','isae-sa14-incidence-comparison','isae-sa14-wasm','isae-sa14-browser',
        'isae-sa14-polars-wasm','isae-sa14-polars-browser','isae-sa14-incidence-wasm','isae-sa14-incidence-browser']
    reports={n:json.loads((D/(n+'.json')).read_text()) for n in names}
    inputs={n+'.json':sha(D/(n+'.json')) for n in names}
    modules={p.name:sha(p) for p in(ROOT/'openswing').glob('*.py')}
    for name,r in reports.items():
        pins=r.get('modules',r.get('provenance',{}).get('modules'))
        if pins is not None:assert pins==modules,name
    sources=reports['isae-sa14-sources'];models={m['name']:m for m in sources['models']}
    for name,pin in sources['files'].items():
        p=CACHE/name;b=p.read_bytes();assert len(b)==pin['bytes'] and sha(p)==pin['sha256']
        assert hashlib.sha1(f'blob {len(b)}\0'.encode()+b).hexdigest()==pin['git_blob_sha1']
    assert len(sources['files'])==50 and len(models)==4
    assert sha(ROOT/sources['primary']['path'])==sources['primary']['sha256']
    native={k:reports['isae-sa14-'+k] for k in ['pilot','polars','incidence']}
    for label,name in [('pilot','isae-sa14-pilot-comparison'),('polars','isae-sa14-polars-comparison'),('incidence','isae-sa14-incidence-comparison')]:
        assert reports[name]['native_sha256']==inputs['isae-sa14-'+label+'.json']
    loads=reports['isae-sa14-load-exports']
    assert loads['pilot_sha256']==inputs['isae-sa14-pilot.json'] and loads['source_report_sha256']==inputs['isae-sa14-sources.json']
    # Every CSV copy is retained, but identical copies do not multiply coverage.
    datasets=[]
    pilot=reports['isae-sa14-pilot-comparison'];incidence=reports['isae-sa14-incidence-comparison']
    polars=reports['isae-sa14-polars-comparison']
    for figure in sources['experimental']:
        for name in figure['identical_copies']:
            assert sha(CACHE/name)==figure['source_sha256']
            assert csv_series(CACHE/name)==figure['series']
        rows=[]
        for series in figure['series']:
            if figure['filename']=='Figure7.csv':
                case='wing_only' if series['label'].startswith('Wing_only') else 'wing_body'
                alpha=float(series['label'].split('alpha_')[1].replace('_','.'))
                comparison=next(c for c in pilot['local_comparisons'] if c['specification']==dict(
                    case=case,panels=100,alpha=alpha,pg='speed' if alpha==4.7 else 'zero'))
                matched={p['source_row']:p for p in comparison['points']}
            elif figure['filename']=='Figure17.csv':
                alpha=float(series['label'].split('alpha_')[1].replace('_','.'))
                comparison=next(c for c in incidence['comparisons'] if c['specification']==dict(
                    case='wing_frame',panels=100,alpha_w=alpha,alpha=alpha,pg='primary_0.19'))
                matched={p['source_row']:p for p in comparison['points']}
            else:
                comparison=next(c for c in polars['comparisons'] if c['label']==series['label'] and
                    c['panels']==100 and c['pg']=='primary_0.19' and not c['frozen'])
                matched={p['source_row']:p for p in comparison['points']}
            assert set(matched)=={p['row'] for p in series['points']}
            for point in series['points']:
                found=matched[point['row']]
                x=found['alpha'] if figure['filename']=='Figure24.csv' else found['normalized_y']
                assert [x,found['observed']]==point['xy']
                classification=found.get('classification','global_experimental_lift')
                rows.append(dict(series=series['label'],row=point['row'],xy=point['xy'],classification=classification,
                    selected_prediction=found['predicted'],selection=('N100, archived mixed PG' if figure['filename']=='Figure7.csv' else
                        'N100, primary Mach0.19, live influences'),
                    source_note='Incidence input is an explicit reconstruction, not an original ASW file.' if figure['filename']=='Figure17.csv' else None))
        datasets.append(dict(filename=figure['filename'],sha256=figure['source_sha256'],copies=figure['identical_copies'],
            source_points=len(rows),rows=rows,classifications=dict(Counter(p['classification'] for p in rows))))
    assert [d['source_points'] for d in datasets]==[48,24,44]
    classifications=Counter(p['classification'] for d in datasets for p in d['rows'])
    assert classifications==Counter(instrumented_station=42,instrumented_surface_station=18,
        upper_surface_measured_lower_interpolated=3,drawn_tip_curve_endpoint=9,global_experimental_lift=44)
    assert all(p['selected_prediction'] is not None for d in datasets for p in d['rows'] if p['classification']!='drawn_tip_curve_endpoint')
    archive_refs=[r for r in native['polars']['references'] if r['kind']=='archive']
    assert len(archive_refs)==180 and len({(r['source_path'],r['row_index']) for r in archive_refs})==180
    exports=loads['exports'];assert len(exports)==6 and sum(len(e['tables']) for e in exports)==9
    assert sum(len(t['rows']) for e in exports for t in e['tables'])==426
    # Count requests and unique conditions separately. Alpha_w only names a
    # reference angle; the actual solver condition uses alpha in its own frame.
    unique={};manifest={};request_counts={};duplicates=[]
    for study,report in native.items():
        request_counts[study]=dict(Counter(r['status'] for r in report['rows']))
        for row in report['rows']:
            path=ROOT/row['cache_path'];assert sha(path)==row['cache_sha256']
            manifest[row['cache_path']]=row['cache_sha256'];q=row['specification'];case=q['case']
            if study=='incidence' and case!='iw0':source=reports['isae-sa14-incidence-sources']['variants'][case]
            else:source=models['wing_body' if case=='iw0' else case]
            # Printed -0.0 and +0.0 denote the same physical angle. Preserve
            # both original requests, but do not count them as distinct cases.
            angle=0. if q['alpha']==0. else q['alpha']
            condition=dict(source_sha256=source['sha256'],speed=70.,panels=q['panels'],alpha=angle,
                pg=q['pg'],frozen=q.get('frozen',False))
            key=json.dumps(condition,sort_keys=True)
            short=dict(study=study,cache_path=row['cache_path'],status=row['status'],condition=condition)
            if key in unique:
                previous,old=unique[key];assert old['status']==row['status']
                error=0.
                if row['status']=='computed':
                    for k,v in row['result']['coefficients'].items():
                        ov=old['result']['coefficients'][k]
                        if v is None or ov is None:assert v is ov is None
                        else:error=max(error,abs(v-ov))
                    assert error<2e-12,(condition,error)
                else:assert old['error']==row['error']
                duplicates.append(dict(first=previous,repeat=short,maximum_coefficient_difference=error))
            else:unique[key]=(short,row)
    totals=Counter(r['status'] for report in native.values() for r in report['rows'])
    dedup=Counter(r['status'] for _,r in unique.values());assert totals==Counter(computed=3008,rejected=48)
    runtime=[]
    for prefix,label in [('isae-sa14','pilot'),('isae-sa14-polars','polars'),('isae-sa14-incidence','incidence')]:
        for engine in ['wasm','browser']:
            name=prefix+'-'+engine;r=reports[name]
            assert r['native_sha256']==inputs['isae-sa14-'+label+'.json']
            if engine=='browser':assert r['offline'] is True
            outcomes=Counter(s['status'] for s in r['rows'])
            assert set(outcomes)<= {'matching_solution','matching_rejection'}
            runtime.append(dict(study=label,engine=engine,status=r['status'],outcomes=dict(outcomes),
                executions=len(r['rows']),report=name+'.json',sha256=inputs[name+'.json']))
    assert sum(r['executions'] for r in runtime if r['engine']=='wasm')==146
    assert sum(r['executions'] for r in runtime if r['engine']=='browser')==35
    files=[]
    for name,pin in sources['files'].items():
        p=Path(name)
        role=('literal_model' if p.suffix=='.asw' else 'operating_script' if p.suffix=='.sh' else
            'digitized_dataset_copy' if p.name in ['Figure7.csv','Figure17.csv','Figure24.csv'] else
            'original_polar' if p.name in ['WB_polaire_totale.txt','WB_polaire_totale_infinite_fuselage.txt','W_only_polaire_totale.txt'] else
            'original_load_export' if p.name in ['Wing_Body_lift_distribution.txt','Wing_alone_lift_distribution.txt'] else
            'source_postprocessing' if p.name=='Post_traitement.m' else
            'geometry_reference' if p.name in ['Fuselage_geometry.csv','NACA63A012.txt'] else
            'figure_or_context' if p.suffix in ['.pdf','.eps','.png','.svg'] else 'filesystem_metadata')
        files.append(dict(path=name,role=role,**pin))
    findings=[
        'All116 digitized CSV points are accounted for without counting three identical copies repeatedly:107 pressure/global-lift points and9 drawn tip endpoints.',
        'All180 original polar rows and426 original distribution rows are retained; source convergence flags, interval midpoints, padding, plotting edits and print precision remain explicit.',
        'Every original ASW file is retained. The standalone body-only model is12x larger than the coupled fuselage and is a diagnostic, not a substitute geometry.',
        'The iw4 setup is explicitly reconstructed in two equivalent frames. Original incidence input and digitization provenance remain unavailable.',
        'Runtime agreement and small integrated mesh changes do not establish force-field convergence or experimental accuracy.',
        'Partial classification means completed quantitative comparisons over documented source data, not a full experimental validation pass.']
    remaining=[
        'Resolve the singular swept force-velocity limit using justified physics and independent/reference-ASWING evidence; propagate any change consistently through loads and derivatives.',
        'Recover section-polar/stall and archive initialization, mesh, circulation-mode and PG/freeze provenance. High-angle measured lift declines while supplied-model predictions continue rising.',
        'Resolve original geometry/normalization discrepancies, including standalone body scale, wing-only moment reference and iw4 source provenance.',
        'Recover experimental/digitization uncertainty and define justified accuracy criteria. Remaining force/moment errors are not waived.',
        'The primary-report screenshots contain additional undigitized context; this completion covers supplied numerical tables/CSVs, not every curve in the primary report.',
        'Complete endpoint regression before releasing the display repair; packaged SA12 application remains unchanged.']
    out=dict(status='QUANTITATIVE_COMPARISONS_COMPLETE_PHYSICAL_VALIDATION_INCOMPLETE',
        case='SA-14',modules=modules,script_sha256=sha(Path(__file__)),source_revision=sources['revision'],
        input_sha256=inputs,fully_validated=False,original_files=files,source_file_roles=dict(Counter(f['role'] for f in files)),
        datasets=datasets,source_digitized_points=116,pressure_and_global_lift_points=107,drawn_tip_endpoints=9,
        archive=dict(polar_rows=180,converged_polar_rows=sum(r['converged'] for r in archive_refs),
            unconverged_polar_rows=sum(not r['converged'] for r in archive_refs),operating_points=6,beam_tables=9,distribution_rows=426),
        native=dict(study_request_counts=request_counts,total_request_observations=sum(totals.values()),
            outcomes=dict(totals),unique_conditions=len(unique),unique_outcomes=dict(dedup),duplicate_requests=duplicates,
            condition_identity='Literal source bytes, panels, speed, actual-frame alpha, PG selection and frozen/live setting. Equivalent coordinate frames remain distinct inputs.',
            cache_manifest=[dict(path=p,sha256=h) for p,h in sorted(manifest.items())]),
        runtime=runtime,findings=findings,remaining=remaining,
        independent_evidence=dict(body_field_report='isae-sa14-volume.json',frame_pairs=18,
            incidence_report='isae-sa14-incidence-comparison.json',swept_limit_report='swept-lifting-line-limit.json'))
    path=D/'isae-sa14-comparison.json';path.write_text(json.dumps(out,indent=2)+'\n')
    checks=dict(status='PASS_SA14_FAMILY_COVERAGE_AUDIT_NOT_PHYSICAL_VALIDATION',modules=modules,
        snapshot_sha256=sha(path),script_sha256=sha(Path(__file__)),source_files=50,digitized_points=116,
        archive_polar_rows=180,archive_distribution_rows=426,request_observations=sum(totals.values()),
        unique_conditions=len(unique),wasm_executions=146,offline_browser_executions=35,pending_numeric_dataset_mappings=0,
        fully_validated=False)
    (D/'isae-sa14-family-checks.json').write_text(json.dumps(checks,indent=2)+'\n')
    lines=['# SA-14 consolidated quantitative comparison','',
        '**The supplied numerical datasets have been compared; physical validation remains incomplete.** This consolidates the original-input pilot, extended lift polars, archived load exports and explicit incidence reconstructions. All 50 upstream case files and 97 solver modules retain their original hashes.', '',
        'The case comes from [ISAE’s validation repository](https://github.com/rom1isae/ISAE_Aswing_Experimental_Validation/tree/'+sources['revision']+'), with experimental definitions from [NACA TN 3730](https://ntrs.nasa.gov/citations/19920075067). The report distinguishes measured pressure/balance data, interpolated lower-surface data, drawn curve endpoints and original ASWING calculations.', '',
        '| Supplied data | Unique rows/points | Evidence |', '|---|---:|---|',
        '| iw=0 span loads, Figure7.csv | 48: 42 pressure stations, 6 drawn tips | [Original-input pilot](isae-sa14-pilot.md) |',
        '| iw=4 span loads, Figure17.csv | 24: 18 standard pressure, 3 partly interpolated, 3 drawn tips | [Explicit incidence reconstruction](isae-sa14-incidence.md) |',
        '| Global lift, Figure24.csv | 44: balance and exposed-wing pressure lift | [Extended polars](isae-sa14-polars.md) |',
        '| Three original ASWING polars | 180: 116 flagged converged, 64 unconverged | [Archive comparison](isae-sa14-polars.md) |',
        '| Two original load exports | 426 rows in 9 beam tables and 6 states | [Staggered-coordinate audit](isae-sa14-load-exports.md) |', '',
        'The three identical copies of each CSV count once. All 107 pressure/global-lift points have predictions in the selected finite-mesh comparisons; nine drawn tip endpoints remain distinct, including null predictions outside native midpoint coverage. This does not supply missing uncertainty or establish a validation threshold. The iw=4 geometry is reconstructed, and its Figure15/17 mapping remains a documented inference.', '',
        '## Numerical coverage', '',
        'The studies contain 3,056 request observations: 3,008 computed and 48 rejected. Deduplication by source bytes and actual condition gives '+str(len(unique))+' distinct conditions ('+str(dedup['computed'])+' computed, '+str(dedup['rejected'])+' rejected); '+str(len(duplicates))+' repeated observations are explicitly linked and their coefficient agreement checked. Equivalent-coordinate inputs remain separate because their stored sources and frame angles differ.', '',
        'The pilot, polar and incidence studies contain 146 WASM executions and 35 offline browser executions. These are replay counts, not additional experimental points. Expected domain rejections are retained. Independent body-field quadrature and 18 incidence frame pairs provide separate numerical checks.', '',
        '## Findings and limits', '',
        'Primary-Mach N100 global CL RMSE is 0.09217 for total wing/body lift, 0.09789 for exposed wing with body, and 0.06976 for exposed wing alone. At iw=4, local-load RMSE is 0.03043, 0.07339 and 0.14400 at wing angles 4.7°, 8.8° and 12.9°. Error definitions and sample counts remain in the linked studies; these values do not constitute a pass.', '',
        'The [swept-force diagnosis](swept-lifting-line-limit.md) identifies a growing force-point velocity under mesh refinement. Higher-angle lift/stall discrepancies remain, even when integrated lift changes modestly with resolution. Original reference settings, moment origin, body geometry scale, incidence provenance and uncertainty also remain unresolved.', '',
        'The source screenshots include additional primary-report context that has not been fully digitized. This consolidation covers every supplied numeric comparison table and CSV; it does not claim to reproduce every primary-report figure, or to validate the full family.', '',
        '## Evidence and reproduction', '',
        '- [Consolidated machine-readable report](isae-sa14-comparison.json) includes all 116 mapped points, source-file roles, duplicate-condition links and native cache hashes.',
        '- [Family coverage audit](isae-sa14-family-checks.json) verifies the pinned studies and all source/cache bytes.',
        '- Run `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python scripts/consolidate-isae-sa14.py` to rebuild this consolidation from existing results. It does not run new solves or alter source models.', '',
        'SA-14 qualifies as a completed quantitative study of part of its scope. It remains **partial**, with every physical limitation above carried into the coverage ledger. This source report does not update the packaged SA-12 application.', '']
    (D/'isae-sa14-comparison.md').write_text('\n'.join(lines))
    print(json.dumps(checks,indent=2),flush=True)


if __name__=='__main__':main()
