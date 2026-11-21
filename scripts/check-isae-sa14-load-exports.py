"""Reconcile original SA-14 staggered load exports, without fitting or new solves."""
from collections import Counter
from pathlib import Path
import hashlib
import json
import re
import sys

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'scripts')]
from openswing.asw import parse_asw
from isae_sa14_reference import sha

D = ROOT/'docs/validation'
NUMBER = r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][+-]?\d+)?'
ROW = re.compile(r'^\s*('+NUMBER+r')\s+('+NUMBER+r')\s+('+NUMBER+r')\s+('+NUMBER+r')\s*$')


def printed(token):
    """Half a unit in the last printed place; formatting precision, not uncertainty."""
    mantissa, *exponent = re.split('[Ee]', token)
    places = len(mantissa.split('.')[1]) if '.' in mantissa else 0
    half = .5 * 10.**((int(exponent[0]) if exponent else 0)-places)
    value = float(token)
    return dict(token=token, value=value, half_last_place=half, interval=[value-half, value+half])


def scalar(text, label):
    match = re.search(re.escape(label)+r'\s*:\s*('+NUMBER+r')', text)
    assert match, label
    return printed(match[1])


def metrics(pairs, predicted, observed):
    if not pairs:
        return dict(count=0, rmse=None, bias=None, maximum_absolute_error=None)
    error = np.array([r[predicted]-r[observed] for r in pairs])
    return dict(count=len(pairs), rmse=float(np.linalg.norm(error)/np.sqrt(len(error))),
                bias=float(np.mean(error)), maximum_absolute_error=float(max(abs(error))))


def parse_exports(sources):
    exports = []
    for source in sources['distribution_exports']:
        path = ROOT/'.reference/isae-validation'/sources['revision']/source['path']
        assert sha(path) == source['sha256'] and path.read_text() == source['source']
        starts = [m.start() for m in re.finditer(r'^ Op.Point:', source['source'], re.M)]
        assert len(starts) == 3
        for start, end in zip(starts, starts[1:]+[len(source['source'])]):
            text = source['source'][start:end]
            parameters = {k: scalar(text, label) for k, label in dict(alpha='Alpha', speed='Velocity',
                beta='Beta', pg='MachPG', mach='Mach', density='Density', q='Dyn.Pr.', area='Ref.Area',
                chord='Ref.Chrd', span='Ref.Span', CL='avg CL', CD='avg CD', CDi='avg CDi', Cm='avg Cm',
                lift='Lift', Fx='sum Fx', Fy='sum Fy', Fz='sum Fz', My='sum My').items()}
            op = int(re.search(r'Op.Point:\s*(\d+)', text)[1])
            tables = []
            heads = list(re.finditer(r'^  (Surface|Fuselage)\s+Beam\s+(\d+):\s*([^\n]+)', text, re.M))
            for j, head in enumerate(heads):
                stop = heads[j+1].start() if j+1 < len(heads) else len(text)
                block = text[head.end():stop]
                assert re.search(r't\s+y\s+chord\s+cl', block)
                rows = []
                for match in re.finditer(r'^.*$', block, re.M):
                    numeric = ROW.fullmatch(match[0])
                    if not numeric:
                        continue
                    offset = start+head.end()+match.start()
                    fields = {k: printed(v) for k, v in zip(['t','y','chord','cl'], numeric.groups())}
                    rows.append(dict(source_line=source['source'][:offset].count('\n')+1, fields=fields))
                assert rows and rows[-1]['fields']['chord']['value'] == rows[-1]['fields']['cl']['value'] == 0.
                intervals = []
                for index, (left, right) in enumerate(zip(rows[:-1], rows[1:])):
                    a, b = left['fields'], right['fields']
                    t = .5*(a['t']['value']+b['t']['value'])
                    y = .5*(a['y']['value']+b['y']['value'])
                    zero_at_break = a['t']['value'] == b['t']['value'] and (abs(t)<1e-5 or head[1]=='Fuselage')
                    status = 'coincident_printed_stations_at_break' if zero_at_break else 'material_interval'
                    intervals.append(dict(row=index+1, source_line=left['source_line'], status=status,
                        printed_left_t=a['t']['value'], printed_right_t=b['t']['value'],
                        printed_left_y=a['y']['value'], printed_right_y=b['y']['value'],
                        midpoint_t=t, midpoint_y=y,
                        midpoint_t_half_last_place=.5*(a['t']['half_last_place']+b['t']['half_last_place']),
                        midpoint_y_half_last_place=.5*(a['y']['half_last_place']+b['y']['half_last_place']),
                        chord=a['chord']['value'], chord_half_last_place=a['chord']['half_last_place'],
                        cl=a['cl']['value'], cl_half_last_place=a['cl']['half_last_place'],
                        rounded_t_equal=a['t']['value']==b['t']['value']))
                tables.append(dict(kind=head[1], beam=int(head[2]), name=head[3].strip(), rows=rows,
                    intervals=intervals, last_row='Dummy derived zeros; node coordinates retained.',
                    counts=dict(Counter(r['status'] for r in intervals))))
            assert [t['kind'] for t in tables] == (['Fuselage','Surface'] if source['case']=='wing_body' else ['Surface'])
            exports.append(dict(case=source['case'], operating_point=op, source_path=source['path'],
                source_sha256=source['sha256'], parameters=parameters, tables=tables))
    return exports


def main():
    sources = json.loads((D/'isae-sa14-sources.json').read_text())
    pilot = json.loads((D/'isae-sa14-pilot.json').read_text())
    modules = {p.name: sha(p) for p in (ROOT/'openswing').glob('*.py')}
    assert sources['modules'] == pilot['provenance']['modules'] == modules
    assert pilot['provenance']['source_report_sha256'] == sha(D/'isae-sa14-sources.json')
    assert pilot['provenance']['script_sha256'] == sha(ROOT/'scripts/verify-isae-sa14.py')
    models = {m['name']: parse_asw(m['source']) for m in sources['models']}
    exports = parse_exports(sources)
    geometry = []; comparisons = []; postprocessing = []; cache_manifest = []
    for export in exports:
        case, parameters = export['case'], export['parameters']
        alpha = parameters['alpha']['value']
        table = next(t for t in export['tables'] if t['kind']=='Surface')
        beam = next(b for b in models[case].beams if b.index==table['beam'])
        material = [r for r in table['intervals'] if r['status']=='material_interval']
        a = np.array([r['cl'] for r in material]); c = np.array([r['chord'] for r in material])
        # Reflection is a direct diagnostic of the staggered pairing, independent of OpenSwing.
        assert np.array_equal(a, a[::-1]) and np.array_equal(c, c[::-1])
        assert len(material) == (40 if case=='wing_only' else 78)
        midpoint_errors = []; node_errors = []; precision_excess = []
        for row in material:
            # Domain clipping bounds the printed rounding interval only. No source row is edited.
            t = np.clip(row['midpoint_t'], *beam.domain)
            lower = np.clip(row['midpoint_t']-row['midpoint_t_half_last_place'], *beam.domain)
            upper = np.clip(row['midpoint_t']+row['midpoint_t_half_last_place'], *beam.domain)
            predictions = beam.value('chord', np.array([lower, t, upper]))
            error = predictions[1]-row['chord']
            node = beam.value('chord', np.clip(row['printed_left_t'], *beam.domain))-row['chord']
            excess = max(0., min(predictions)-row['chord']-row['chord_half_last_place'],
                         row['chord']-row['chord_half_last_place']-max(predictions))
            midpoint_errors.append(float(error)); node_errors.append(float(node)); precision_excess.append(float(excess))
            row['literal_chord_at_estimated_midpoint'] = float(predictions[1])
            row['literal_chord_over_printed_midpoint_interval'] = [float(min(predictions)), float(max(predictions))]
        geometry.append(dict(case=case, alpha=alpha, material_intervals=len(material),
            printed_rows=len(table['rows']), normal_chord_reflection_error=float(max(abs(c-c[::-1]))),
            cl_reflection_error=float(max(abs(a-a[::-1]))),
            midpoint_chord_rmse=float(np.sqrt(np.mean(np.array(midpoint_errors)**2))),
            preceding_node_chord_rmse=float(np.sqrt(np.mean(np.array(node_errors)**2))),
            maximum_chord_discrepancy_beyond_print_precision=max(precision_excess)))
        embedded = next(r for r in sources['postprocessing']['embedded_distributions'] if r['case']==case and r['alpha']==alpha)
        originals = [[r['fields'][k]['value'] for k in ['t','y','chord','cl']] for r in table['rows']]
        maps = []
        for row in embedded['rows']:
            exact = [i+1 for i, r in enumerate(originals) if r==row]
            fields_only = [i+1 for i, r in enumerate(originals) if r[2:]==row[2:] and r[1]>=0]
            maps.append(dict(embedded_row=row, exact_source_rows=exact, source_rows_matching_chord_cl=fields_only,
                classification='exact_printed_row' if exact else 'coordinates_modified' if fields_only else 'unmatched'))
        assert all(m['classification']!='unmatched' for m in maps)
        postprocessing.append(dict(case=case, alpha=alpha, rows=maps,
            counts=dict(Counter(m['classification'] for m in maps)),
            explanation='Exact copied rows still pair midpoint chord/cl with preceding-node coordinates. Modified coordinates remain separately labeled. Terminal zeros are output padding.'))
        for panels in [25,50,100]:
            q = dict(case=case, panels=panels, alpha=alpha, pg='speed' if alpha==4.7 else 'zero')
            native = next(r for r in pilot['rows'] if r['specification']==q)
            path = ROOT/native['cache_path']; assert sha(path)==native['cache_sha256']
            stored = json.loads(path.read_text()); assert stored['specification']==q and stored['status']=='computed'
            result = stored['result']; assert result==native['result']
            cache_manifest.append(dict(path=native['cache_path'], sha256=native['cache_sha256']))
            pg = parameters['pg']; assert pg['interval'][0] <= result['actual_mach'] <= pg['interval'][1]
            profile = result['profiles']; x = np.array([r['position'][1] for r in profile])
            assert np.all(np.diff(x)>0)
            native_cl = np.array([r['cl'] for r in profile]); native_chord = np.array([r['normal_chord'] for r in profile])
            pairs = []
            for row in material:
                y = row['midpoint_y']; inside = x[0]<=y<=x[-1]
                lower, upper = y-row['midpoint_y_half_last_place'], y+row['midpoint_y_half_last_place']
                interval_inside = x[0]<=lower and upper<=x[-1]
                item = dict(row=row['row'], source_line=row['source_line'], midpoint_y=y,
                    normalized_y=2*y/sources['primary']['wing']['span_m'], observed_cl=row['cl'],
                    observed_chord=row['chord'], status='compared' if inside else 'outside_native_midpoint_range',
                    printed_position_interval_within_native_range=bool(interval_inside))
                if inside:
                    item.update(predicted_cl=float(np.interp(y,x,native_cl)), predicted_chord=float(np.interp(y,x,native_chord)))
                if interval_inside:
                    samples=np.r_[lower,x[(x>lower)&(x<upper)],upper]
                    values=np.interp(samples,x,native_cl)
                    item['native_cl_over_printed_position_interval']=[float(min(values)),float(max(values))]
                    item['error_beyond_print_precision']=float(max(0.,min(values)-row['cl']-row['cl_half_last_place'],
                        row['cl']-row['cl_half_last_place']-max(values)))
                pairs.append(item)
            compared = [r for r in pairs if r['status']=='compared']
            physical = result['coefficients']; force = np.array(result['force']); moment = np.array(result['moment'])
            model = models[case]; origin = moment+np.cross(model.reference[1], force)
            Cm_origin = float(origin[1]/result['dynamic_pressure']/model.reference[0,0]/model.reference[0,1])
            comparisons.append(dict(specification=q, actual_pg=result['actual_mach'], printed_pg=pg,
                source_sha256=export['source_sha256'], cache_path=native['cache_path'], cache_sha256=native['cache_sha256'],
                material_intervals=len(material), compared=len(compared), outside=len(pairs)-len(compared), rows=pairs,
                cl_error=metrics(compared,'predicted_cl','observed_cl'), chord_error=metrics(compared,'predicted_chord','observed_chord'),
                coefficients={k:dict(predicted=physical[k], archived=parameters[k]['value'], difference=physical[k]-parameters[k]['value'])
                              for k in ['CL','CD','CDi','Cm']},
                moment_origin_diagnostic=dict(predicted=Cm_origin,archived=parameters['Cm']['value'],difference=Cm_origin-parameters['Cm']['value']),
                input_moment_reference=model.reference[1].tolist(),
                maximum_section_normal_mach=result['maximum_section_normal_mach']))
    output = dict(status='PASS_STAGGERED_EXPORT_AUDIT_COMPARISON_DISCREPANCIES_REMAIN',
        script_sha256=sha(Path(__file__)), modules=modules, source_report_sha256=sha(D/'isae-sa14-sources.json'),
        pilot_sha256=sha(D/'isae-sa14-pilot.json'), document=dict(path='.reference/aswing_doc.txt',sha256=sha(ROOT/'.reference/aswing_doc.txt'),
            url='https://web.mit.edu/drela/Public/web/aswing/aswing_doc.txt',sections=['Displayed Variables','Discrete Variable location','Considerations for Data Discontinuities']),
        exports=exports, geometry=geometry, comparisons=comparisons, postprocessing=postprocessing,
        cache_manifest=cache_manifest, new_solver_runs=0,
        limitations=[
            'Node coordinates and midpoint chord/cl are staggered in ASWING ASCII output. Terminal derived zeros are padding; root break rows are retained but not finite-span load samples.',
            'Printed coordinates have finite precision. Midpoints are estimates; repeated rounded tip stations are not treated as actual zero-length material. No exact archive mesh or circulation basis is recovered.',
            'The matched pilot states use current influences. Archived K/F and circulation discretization remain unknown; three OpenSwing meshes do not reproduce the exact archived mesh.',
            'Perpendicular section cl is not wind-axis lift per span. Without archived relative velocities and force vectors, cl*chord does not reconstruct the primary pressure-load observable.',
            'All original body rows are retained. Their zero chord and nonzero cl do not define lifting-surface coefficients for direct comparison.',
            'Original archived moment values and source-reference OpenSwing values remain distinct; the origin shift is a labeled diagnostic, not a fitted correction.',
            'This audit reuses 18 already verified native states; it does not add new WASM/browser solves or resolve the swept-force velocity limit.'])
    assert modules=={p.name:sha(p) for p in (ROOT/'openswing').glob('*.py')}
    (D/'isae-sa14-load-exports.json').write_text(json.dumps(output,indent=2)+'\n')
    plot_and_report(output, sources, pilot)
    print(output['status'],len(exports),'operating points;',sum(len(t['rows']) for e in exports for t in e['tables']),'original rows;',
          len(comparisons),'native profile comparisons',flush=True)


def plot_and_report(output, sources, pilot):
    plt.rcParams.update({'font.size':9,'svg.fonttype':'none'})
    fig,axes=plt.subplots(3,2,figsize=(12,11),layout='constrained')
    span=sources['primary']['wing']['span_m']
    for i,alpha in enumerate([4.7,8.8,12.9]):
        for j,case in enumerate(['wing_only','wing_body']):
            ax=axes[i,j]
            export=next(e for e in output['exports'] if e['case']==case and e['parameters']['alpha']['value']==alpha)
            table=next(t for t in export['tables'] if t['kind']=='Surface')
            intervals=[r for r in table['intervals'] if r['status']=='material_interval' and r['midpoint_y']>0]
            for n,color,style in [(25,'#e6362b',':'),(50,'#d87b00','--'),(100,'#326bdd','-')]:
                q=dict(case=case,panels=n,alpha=alpha,pg='speed' if alpha==4.7 else 'zero')
                native=next(r for r in pilot['rows'] if r['specification']==q)
                rows=[r for r in native['result']['profiles'] if r['position'][1]>0]
                ax.plot([2*r['position'][1]/span for r in rows],[r['cl'] for r in rows],color=color,ls=style,label=f'OpenSwing N{n}, current')
            ax.scatter([2*r['midpoint_y']/span for r in intervals],[r['cl'] for r in intervals],facecolors='none',edgecolors='black',s=22,label='Archive, midpoint pairing')
            ax.set(title=f'{case}, alpha={alpha:g} deg, PG={export["parameters"]["pg"]["value"]:g}',
                   xlabel='2y/b (estimated midpoint for archive)',ylabel='Perpendicular section cl')
            ax.grid(alpha=.2)
    axes[0,0].legend(fontsize=7)
    fig.suptitle('SA-14 original section coefficients; root-break and terminal dummy rows are excluded')
    for extension in ['png','svg']:fig.savefig(D/('isae-sa14-load-exports.'+extension),dpi=170)
    plt.close(fig)
    lines=['# SA-14 original load-export comparison','',
        '**Comparison evidence, not an experimental validation pass.** All six operating points and nine beam tables are retained from '+
        'the two original text exports. Eighteen existing native solutions provide N25/50/100 comparisons without new solver runs.','',
        'The [ASWING manual](https://web.mit.edu/drela/Public/web/aswing/aswing_doc.txt) explains that t/y are node quantities, '+
        'while chord and cl belong to the following interval midpoint. Their placement on the same printed row is a storage convention. '+
        'The last derived values are dummy zeros. Doubled stations represent breaks; repeated tip coordinates can also result from limited print precision.','',
        '## Recovered sampling and plotting differences','',
        'The wing-only export has 42 wing rows: 40 material intervals, a root-break interval, and the final dummy row. '+
        'The wing/body export has 80 wing rows: 78 material intervals, a root-break interval, and the final dummy row; '+
        'its body table contains 20 rows. Each is repeated at 4.7°, 8.8° and 12.9°. '+
        'Pairing chord/cl with interval midpoints restores exact printed left/right symmetry. '+
        'It does not recover the unrounded mesh or Fourier settings.','',
        '| Input | Angle | Chord RMSE at midpoint [m] | Chord RMSE at preceding node [m] | Excess beyond print precision [m] |',
        '| --- | ---: | ---: | ---: | ---: |']
    for r in output['geometry']:
        lines.append(f"| {r['case']} | {r['alpha']:g} | {r['midpoint_chord_rmse']:.6g} | {r['preceding_node_chord_rmse']:.6g} | {r['maximum_chord_discrepancy_beyond_print_precision']:.6g} |")
    lines+=['','The MATLAB arrays retain preceding-node coordinates for copied midpoint values. In each wing-only array, '+
        'the sample originally at y=0.0889 m is moved to y=0, while the actual root-side sample is omitted. '+
        'The body-case arrays omit the root-side sample and retain a terminal dummy zero. All row mappings and edits are explicit in the JSON.','',
        '## Native comparison','',
        'PG follows the printed export: 0.2058 at 4.7° and zero at 8.8°/12.9°. The native speed-derived Mach falls within '+
        'the printed PG precision. The archive and OpenSwing use different meshes; native values are interpolated at estimated archive midpoints, '+
        'with out-of-range samples retained as unavailable. Errors use both mirrored halves and are not counts of independent measurements.','',
        '| Input | Angle | N | Compared / material intervals | Section-cl RMSE | CL difference | CD difference |',
        '| --- | ---: | ---: | ---: | ---: | ---: | ---: |']
    for r in output['comparisons']:
        q=r['specification'];lines.append(f"| {q['case']} | {q['alpha']:g} | {q['panels']} | {r['compared']} / {r['material_intervals']} | "+
            f"{r['cl_error']['rmse']:.6g} | {r['coefficients']['CL']['difference']:.6g} | {r['coefficients']['CD']['difference']:.6g} |")
    lines+=['','![Original section-cl comparisons](isae-sa14-load-exports.png)','',
        'The section-cl curves are not the primary experimental wind-axis load distribution. '+
        'The archive does not provide the relative velocities and force vectors needed to convert perpendicular cl into that quantity. '+
        'The [pilot](isae-sa14-pilot.md) uses native strip forces for the experimental comparison; the MATLAB cl/chord multiplier remains a separate diagnostic.','',
        '## Moment-reference limitation','',
        'The literal wing-only file sets its moment reference to x=18.5 m. Its native Cm differs greatly from the archived Cm. '+
        'An independently shifted origin moment is much closer, but the archive does not state its reference location. '+
        'This suggests a reference/setup conflict; it does not establish the historical setting. The input is unchanged and the shift is only a diagnostic.','',
        '| Wing-only angle | Archived Cm | Native Cm at source reference, N100 | Native origin Cm, diagnostic |',
        '| ---: | ---: | ---: | ---: |']
    for r in output['comparisons']:
        if r['specification']['case']=='wing_only' and r['specification']['panels']==100:
            lines.append(f"| {r['specification']['alpha']:g} | {r['coefficients']['Cm']['archived']:.6g} | "+
                f"{r['coefficients']['Cm']['predicted']:.6g} | {r['moment_origin_diagnostic']['predicted']:.6g} |")
    lines+=['',
        'The full [data and audit](isae-sa14-load-exports.json) retain global CL/CD/CDi/Cm, a separately labeled moment-origin diagnostic, '+
        'printed precision, every original body row, missing samples and module/cache hashes. '+
        'Archived initialization/discretization, iw=4° geometry/provenance, section-polar provenance and experimental uncertainty remain unresolved. '+
        'The [swept force-velocity limit](swept-lifting-line-limit.md) still prevents a broad physical-validation claim.','']
    (D/'isae-sa14-load-exports.md').write_text('\n'.join(lines))


if __name__=='__main__':main()
