"""Audit archived force/coefficient normalization without assuming a model match."""
from pathlib import Path
import hashlib, json, sys
import numpy as np

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from isae_sa11_reference import CACHE, sha
D=ROOT/'docs/validation'


def main():
    source_path=D/'isae-sa11-sources.json';sources=json.loads(source_path.read_text())
    checked=[]
    for name,pin in sources['sources'].items():
        path=CACHE/name;data=path.read_bytes()
        assert len(data)==pin['bytes'] and sha(path)==pin['sha256']
        assert hashlib.sha1(f'blob {len(data)}\0'.encode()+data).hexdigest()==pin['git_blob_sha1']
        checked.append(name)
    assert len(checked)==65
    parsed={m['name']:m for m in sources['models'] if m['parsed']}
    density=parsed['wing_alone']['constants'][1]
    small_area=parsed['wing_alone']['reference'][0][0]
    alternate_area=parsed['wingtip_up_cant0']['reference'][0][0]
    assert all(m['constants'][1]==density for m in parsed.values())
    assert small_area==.9329 and alternate_area==97.67
    rows=[]
    for table in sources['archived']:
        a=np.array(table['rows']);assert a.shape==(41,82)
        assert np.array_equal(a,np.loadtxt(CACHE/table['path']))
        assert np.array_equal(a[:,69:72],a[:,72:75])
        assert np.all(a[:,2]==1) and np.all(a[:,66:69]==0)
        assert np.all(a[:,70]==0) and np.array_equal(a[:,71],np.linspace(0,10,41))
        assert np.all(a[:,75:80]>0)
        inferred_lift=2*a[:,75]/(a[:,69]**2*a[:,77])
        inferred_drag=2*a[:,76]/(a[:,69]**2*a[:,78])
        # These are two existing source reference areas, not fitted values.
        diagnostic_area=small_area if table['nominal_mach'] in [.7,.8] else alternate_area
        qS=.5*density*a[:,69]**2*diagnostic_area
        relative_lift=float(np.max(abs(a[:,75]/qS/a[:,77]-1)))
        relative_drag=float(np.max(abs(a[:,76]/qS/a[:,78]-1)))
        assert max(relative_lift,relative_drag)<2e-5
        source_qS=.5*density*a[:,69]**2*small_area
        rows.append(dict(name=table['name'],nominal_mach=table['nominal_mach'],actual_speed=table['speeds'][0],
            path=table['path'],sha256=table['sha256'],rows=len(a),supplied_density=density,
            comparison_model_reference_area=small_area,
            inferred_density_times_area_from_lift_range=[float(inferred_lift.min()),float(inferred_lift.max())],
            inferred_density_times_area_from_drag_range=[float(inferred_drag.min()),float(inferred_drag.max())],
            implied_area_at_supplied_density_from_lift_range=[float(inferred_lift.min()/density),float(inferred_lift.max()/density)],
            implied_area_at_supplied_density_from_drag_range=[float(inferred_drag.min()/density),float(inferred_drag.max()/density)],
            existing_source_area_matching_normalization=diagnostic_area,
            ratio_to_comparison_model_area=diagnostic_area/small_area,
            source_reference_consistent=diagnostic_area==small_area,
            maximum_relative_lift_rounding_error=relative_lift,maximum_relative_drag_rounding_error=relative_drag,
            source_area_CL_maximum_absolute_difference=float(np.max(abs(a[:,75]/source_qS-a[:,77]))),
            source_area_CD_maximum_absolute_difference=float(np.max(abs(a[:,76]/source_qS-a[:,78])))))
    similarity=[]
    for name in ['wing_alone','wingtip_up','wingtip_up_and_down','wing_extension']:
        a,b=[np.array(next(t['rows'] for t in sources['archived'] if t['name']==name and t['nominal_mach']==mach)) for mach in [.75,.78]]
        similarity.append(dict(name=name,nominal_mach_pair=[.75,.78],
            maximum_coefficient_differences={key:float(np.max(abs(a[:,column]-b[:,column])))
                for key,column in [('CL',77),('CD',78),('CDi',79),('Cm',80),('span_efficiency',81)]}))
    report=dict(status='SOURCE_NORMALIZATION_CONFLICT_CONFIRMED',script_sha256=sha(Path(__file__)),
        source_report_sha256=sha(source_path),source_files_verified=len(checked),source_files=checked,
        rows=rows,adjacent_mach_similarity=similarity,
        interpretation=[
            'Lift and drag independently imply rho*S = 2*force/(V^2*coefficient). This quantity is obtained from the archived columns without assuming the area or density separately.',
            'At the supplied density, all eight Mach .75/.78 tables imply S near97.67, whereas all eight Mach .7/.8 tables imply S near.9329.',
            'The four comparison model files use S=.9329. The separate unmeasured cant0 input has S=97.67 and tenfold geometry. The normalization match is evidence of an archive/input conflict; it does not identify the original run geometry.',
            'Different density, dimensional-force units, runtime reference settings or model revisions cannot be excluded. Do not silently rescale the input or assign the cant0 geometry to these archived polars.',
            'For three configurations, Mach .75/.78 CL/CD/CDi curves are almost identical at archive precision, unlike the combined upper/lower configuration. This does not establish the PG startup state.',
            'Agreement of printed forces and coefficients with an area is an internal consistency check, not experimental validation or proof of identical geometry/section properties.'])
    (D/'isae-sa11-archive.json').write_text(json.dumps(report,indent=2)+'\n')
    lines=['# SA-11 archived normalization conflict','',
        'The Mach 0.75/0.78 archives do not use the force/coefficient normalization of the supplied comparison files. '+
        'Their lift and drag columns independently imply a reference area near **97.67 m²**, assuming the supplied density 1.2256 kg/m³. '+
        'The Mach 0.70/0.80 archives imply **0.9329 m²**, matching the four comparison inputs.','',
        'The inference uses `rho*S = 2*force/(V²*coefficient)`. It does not independently determine density or area. '+
        'The separate cant0 input also specifies 97.67 m² and tenfold geometry, but that coincidence does not establish which geometry generated any archive. '+
        'Unknown force units, runtime reference changes, density or older input revisions remain possible. No model or coefficient has been rescaled.','',
        '| Configuration | Nominal Mach | Recorded V | Implied area range from lift, at supplied density | Supplied comparison area |',
        '| --- | ---: | ---: | ---: | ---: |']
    for row in rows:
        lo,hi=row['implied_area_at_supplied_density_from_lift_range']
        lines.append(f"| {row['name']} | {row['nominal_mach']:g} | {row['actual_speed']:g} | {lo:.6f}–{hi:.6f} | {small_area:g} |")
    lines+=['','All 16 tables contain 41 converged rows. '+
        'Using their implied area, printed force and coefficient differences are within 2×10⁻⁵ relative. '+
        'All 65 upstream files pass their pinned SHA-256, Git blob SHA-1 and byte-count checks.','',
        'The Mach 0.75/0.78 baseline, extension and upper-only lift/drag curves are almost identical at archive precision. '+
        'The combined upper/lower winglets change between those speeds. PG settings and exact model revisions remain unverified.','',
        'Numerical comparisons at these two Mach labels must therefore be interpreted as comparisons against unmatched source configurations. '+
        'See [machine-readable audit](isae-sa11-archive.json) and [source geometry audit](isae-sa11-sources.md).','']
    (D/'isae-sa11-archive.md').write_text('\n'.join(lines))
    print(report['status'],len(rows),'tables;',len(checked),'source files verified',flush=True)


if __name__=='__main__':main()
