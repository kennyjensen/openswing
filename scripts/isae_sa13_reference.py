"""Audit SA-13 figure data and construct explicitly labeled graph-based bodies.

No original ASW input or operating script is supplied for this family. Geometry
reconstruction uses only the two outline curves, never a measured force fit.
"""
from pathlib import Path
import hashlib, importlib.util, json, sys
import numpy as np
from scipy.io import loadmat

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from openswing.asw import parse_asw
from openswing.geometry import model_meshes,geometry_summary
from openswing.volume import body_quadrature
REVISION='f62943df20e9e4d7d9f50e070477b22426b5f865'
CACHE=ROOT/'.reference/isae-validation'/REVISION
FOLDER=next(CACHE.glob('1 - Aerodynamics/SA*/SA - 13 - *'))
D=ROOT/'docs/validation'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
spec=importlib.util.spec_from_file_location('extract',ROOT/'scripts/extract-isae-figures.py')
extract=importlib.util.module_from_spec(spec);spec.loader.exec_module(extract)
CASES=[('r33','SA13_A_Airship_R33.fig',10.,16.,'R-33'),
       ('r101','SA13_B_Airship_R101.fig',10.,11.,'R-101'),
       ('rs1','SA13_C_Airship_RS1.fig',9.,6.,'RS-1'),
       ('pressure','SA13_D_Airship_R101_Dynamic_Pressure_Distribution.fig',0.,None,'ZR III (primary; ISAE filename says R101)')]


def axis_properties(value):
    rows=[]
    if isinstance(value,dict):
        if value.get('type')=='axes':
            p=value['properties'];rows.append({k:np.asarray(p[k]).tolist() for k in
                ['XLim','YLim','XTick','XTickLabel','YTickLabel','DataAspectRatio'] if k in p})
        if 'children' in value:rows+=axis_properties(value['children'])
    elif isinstance(value,(list,tuple,np.ndarray)):
        for x in value:rows+=axis_properties(x)
    return rows


def close_outline(rows):
    upper=np.array([[np.nan if v is None else v for v in r] for r in rows[3]['xy']])
    lower=np.array([[np.nan if v is None else v for v in r] for r in rows[4]['xy']])
    assert upper.shape==lower.shape
    mask=np.isfinite(upper).all(1)&np.isfinite(lower).all(1)
    assert np.array_equal(upper[mask,0],lower[mask,0])
    raw_indices=np.flatnonzero(mask);x=upper[mask,0];center=(upper[mask,1]+lower[mask,1])/2
    radius=(upper[mask,1]-lower[mask,1])/2
    assert np.ptp(center)<1e-12 and np.all(np.diff(x)>0)
    positive=np.flatnonzero(radius>0);first,last=positive[0],positive[-1]
    assert np.array_equal(positive,np.arange(first,last+1))
    # A closed hull is established by the primary drawings. Use the nearest
    # outline segment that crosses zero; if no crossing is stored, extrapolate
    # the first/last positive segment. This is an explicit cap reconstruction.
    def zero(i,j):return float(x[i]-radius[i]*(x[j]-x[i])/(radius[j]-radius[i]))
    left_pair=(first-1,first) if first else (first,first+1)
    right_pair=(last,last+1) if last<len(x)-1 else (last-1,last)
    nose=zero(*left_pair);tail=zero(*right_pair)
    assert nose<x[first]<x[last]<tail
    length=tail-nose;diameter=2*max(radius[positive])/length
    table=np.c_[np.r_[0.,(x[positive]-nose)/length,1.],np.r_[0.,radius[positive]/length,0.]]
    note=dict(raw_outline_center=float(center[0]),raw_finite_samples=len(x),
        nonpositive_outline_rows=raw_indices[radius<=0].tolist(),
        nose=nose,tail=tail,raw_reconstructed_length=float(length),
        nose_method='linear_interpolation' if first else 'linear_extrapolation',
        tail_method='linear_interpolation' if last<len(x)-1 else 'linear_extrapolation',
        nose_segment_rows=raw_indices[list(left_pair)].tolist(),tail_segment_rows=raw_indices[list(right_pair)].tolist(),
        retained_positive_rows=raw_indices[positive].tolist(),
        normalized_diameter=float(diameter),length_over_diameter=float(1/diameter),
        raw_sample_extent_over_diameter=float(np.ptp(x)/(2*max(radius))),
        normalized_table=table.tolist(),
        convention='Body length is one input metre. Abscissas and radii use the same outline scale; the plotting center is removed. No force/pressure values determine these parameters.')
    return note


def asw_source(name,outline,length=1.):
    diameter=outline['normalized_diameter']
    header=f'''! Explicit SA-13 graph-based geometry diagnostic, not an original ASWING input.
! See isae-sa13-sources.json for raw outline hashes, closure and scaling.
! Closed caps use outline zero crossings/linear endpoint extrapolation.
! No measured force or pressure was fitted. Cdf=Cdp=0 isolates potential loads.
Name
SA13 {name} outline reconstruction
End
Unit
L 1 m
T 1 s
F 1 N
End
Constant
9.80665 1 340.21
End
Reference
{diameter*length**2:.17g} {length:.17g} {diameter*length:.17g}
0 0 0
End
Ground
1 0 0
End
Beam 1
{name} graph-based body
t x
0 0
1 {length:.17g}
t radius
'''
    return header+'\n'.join(f'{x:.17g} {r*length:.17g}' for x,r in outline['normalized_table'])+'\nt Cdf Cdp\n0 0 0\n1 0 0\nEnd\n'


def main():
    manifest=json.loads((CACHE.parent/'manifest.json').read_text());assert manifest['revision']==REVISION
    files={}
    for path in FOLDER.iterdir():
        assert path.is_file() and path.suffix=='.fig'
        name=path.relative_to(CACHE).as_posix();pin=manifest['files'][name];data=path.read_bytes()
        assert len(data)==pin['bytes'] and sha(path)==pin['sha256']
        assert hashlib.sha1(f'blob {len(data)}\0'.encode()+data).hexdigest()==pin['git_blob_sha1']
        files[name]=pin
    assert len(files)==4
    primary=[]
    for filename,identifier,pin in [('naca-tr-405','19930091479','89d0d19989635e56faf1aeafb15e93ef4336ef302999344b82d7805e10f67a79'),
        ('naca-tm-574','19930094841','e96868752341afc58ba9c5cff5750ae47b56fb384e7537870bc2f1b629fb5423')]:
        path=ROOT/'.reference/isae-sa13'/(filename+'.pdf');assert sha(path)==pin
        primary.append(dict(path=path.relative_to(ROOT).as_posix(),sha256=pin,url=f'https://ntrs.nasa.gov/citations/{identifier}'))
    cases=[]
    for name,filename,alpha,reported_ar,hull in CASES:
        path=FOLDER/filename;mat=loadmat(path,simplify_cells=True)
        nodes=[v for k,v in mat.items() if k.startswith('hgS_')]
        rows=[r for node in nodes for r in extract.series(node)]
        assert len(rows)==5 and rows[3]['label']==rows[4]['label']==''
        outline=close_outline(rows);source=asw_source(name,outline);model=parse_asw(source)
        derived_path=D/f'isae-sa13-{name}-outline.asw';derived_path.write_text(source)
        spline=model.beams[0].distributions['radius']._segments[0][2]
        extrema=np.r_[spline.x,spline.derivative().roots(extrapolate=False)]
        extrema=extrema[np.isfinite(extrema)&(extrema>=0)&(extrema<=1)]
        outline['interpolated_radius_extrema']=dict(minimum=float(np.min(spline(extrema))),maximum=float(np.max(spline(extrema))),
            tabulated_maximum=float(np.max(np.array(outline['normalized_table'])[:,1])),
            endpoint_values=model.beams[0].value('radius',[0.,1.]).tolist())
        setups=[]
        for panels in [32,64,128]:
            try:
                mesh,=model_meshes(model,panels);_,_,radius,_=body_quadrature(mesh)
                setups.append(dict(panels=panels,status='constructed',actual_intervals=len(mesh.tm),minimum_sampled_radius=float(np.min(radius))))
            except ValueError as exc:setups.append(dict(panels=panels,status='rejected',error=str(exc)))
        try:
            geometry_summary(model,32);display=dict(status='constructed',panels=32)
        except ValueError as exc:display=dict(status='rejected',panels=32,error=str(exc))
        cases.append(dict(name=name,filename=filename,path=path.relative_to(CACHE).as_posix(),sha256=sha(path),
            source_labels=[r['label'] for r in rows],series=rows,axes=[r for node in nodes for r in axis_properties(node)],
            primary_hull=hull,primary_alpha=alpha,isae_report_alpha=0. if name=='pressure' else 10.,
            isae_report_aspect_ratio=reported_ar,outline=outline,derived_source=source,
            derived_path=derived_path.relative_to(ROOT).as_posix(),derived_sha256=sha(derived_path),setups=setups,display_geometry=display))
    reviewed=dict(status='VISUAL_PRIMARY_REVIEW_WITH_UNRESOLVED_RECONSTRUCTION',
        tr405=dict(pdf_pages=[9,10],printed_pages=[131,132],figures={
            '6':dict(hull='RS-1',alpha=9.,ordinate='transverse force per axial length / (q * maximum diameter)',original_measurement='Bureau of Standards, Technical Data Files, McCook Field, D527/RS-1'),
            '7':dict(hull='R-33',alpha=10.,ordinate='transverse force per axial length / (q * maximum diameter)',original_measurement='ARC R&M801'),
            '8':dict(hull='R-101',alpha=10.,ordinate='transverse force per axial length / q; dimensional length in the report foot convention',model_length_inches=33.01,model_scale='one-quarter',original_measurement='ARC R&M1169',additional_boundary_layer_reference='R&M1288')},
            theoretical_curves='Local ellipsoid relation and Munk finite-body apparent-mass correction are separately labeled; neither is an unmodified ASWING output.'),
        tm574=dict(pdf_pages=[3,13,30],printed_pages=[1,11,28],figure=3,hull='ZR III',alpha=0.,
            ordinate='100 * (p-p_infinity)/q_infinity = 100 * (1 - |u|^2/U_infinity^2)',
            quantity='Static gauge pressure coefficient in percent, not nonnegative local dynamic-pressure ratio.',
            primary_extent_m=[-12.5,197.5],maximum_radius_m=13.9,geometry_note='Frame coordinate runs aft to fore; nose at197.5 and stern at-12.5. Figure3 contains Klemperer pressure measurements.'))
    limitations=[
        'No asw file, operating command, mesh, units, reference area, sensor placement or exact executable state is supplied for SA-13. Figure legend labels alone do not establish how the curves were computed.',
        'All raw samples and NaN gaps are retained. The first three abscissas are not literal normalized s/L despite that axis label; their x ticks are hidden. Two unlabeled curves resemble the primary hull outlines.',
        'Graph-based reconstruction assumes equal horizontal/vertical geometry scale in each stored outline, removes its center, finds closed caps geometrically and normalizes length to1. It is not an independently measured radius table.',
        'R33 has one negative signed outline radius; the pressure figure has three. These remain in the source record. A separately named closed-body reconstruction uses the contiguous positive outline and zero crossings, without relaxing the parser or radius validity checks.',
        'The three reported aspect ratios16/11/6 are approximately twice the geometric length/diameter ratios of the stored outlines. Do not impose these reported numbers as L/D without reconciliation.',
        'RS-1 primary incidence is9deg, not the10deg ISAE caption. The saved ASWING states do not establish their actual incidence; compare the two as explicit diagnostics.',
        'The R101 primary load ordinate differs dimensionally from the R33/RS1 normalization. The primary model length33.01in can set a conditional dimensional reconstruction, but maximum diameter inferred from a plotted outline carries geometric uncertainty.',
        'The pressure filename identifies R101, whereas the cited primary report and Figure3 identify ZRIII. The pressure ordinate represents100Cp, not100q_local/q_infinity.',
        'Source-series labels Continuous ASWING5.96 and Discrete ASWING5.96 are preserved. ISAE describes a modified radius-derivative implementation, but neither its code nor exact radius/derivative input is supplied.',
        'Natural cubic interpolation, endpoint closure and digitization noise affect radius derivatives and surface velocities. Mesh refinement alone does not remove geometry uncertainty.',
        'The R33 natural spline overshoots the largest radius sample and evaluates its exact zero tail knot as a tiny negative floating-point value. Native quadrature constructs, but current display geometry rejects that radius. This reproducible interpolation/display defect is retained; no positive endpoint was substituted to bypass it.',
        'Body force density must be compared in body transverse axes, not substituted by a global wind-axis lift coefficient. Viscous stern forces, finite-body apparent-mass factors and measured uncertainty require separate treatment.',
        'These are source and reconstruction checks, not experimental validation. No production module or physical-validity guard is changed.']
    out=dict(status='SOURCE_AUDIT_AND_GRAPH_RECONSTRUCTION_NOT_PHYSICAL_VALIDATION',revision=REVISION,
        script_sha256=sha(Path(__file__)),extractor_sha256=sha(ROOT/'scripts/extract-isae-figures.py'),
        modules={p.name:sha(p) for p in (ROOT/'openswing').glob('*.py')},sources=files,primary=primary,
        primary_review=reviewed,cases=cases,limitations=limitations,
        isae_report=dict(path='5 - Technical Reports/Experimental_validation_of_ASWING_Part_1_Aerodynamics_V4.pdf',
            sha256=sha(CACHE/'5 - Technical Reports/Experimental_validation_of_ASWING_Part_1_Aerodynamics_V4.pdf'),scope='Section6.2, Figure24, reference44'))
    (D/'isae-sa13-sources.json').write_text(json.dumps(out,indent=2)+'\n')
    lines=['# SA-13 airship source and reconstruction audit','',
        '**No physical validation claim.** This family supplies four MATLAB figures and no `.asw` models or operating scripts. Four separately named graph-based inputs are available for diagnostic calculations.','',
        'The [pinned source data](isae-sa13-sources.json) retain every numeric sample, gap, label and outline. The primary references are [NACA-TR-405](https://ntrs.nasa.gov/citations/19930091479) and [NACA-TM-574](https://ntrs.nasa.gov/citations/19930094841).','',
        '| Figure | Primary hull | Primary incidence | Finite measured samples | Reported AR | Reconstructed L/D |',
        '|---|---|---:|---:|---:|---:|']
    for c in cases:
        count=sum(x is not None and y is not None for x,y in c['series'][0]['xy'])
        lines.append(f"| {c['name']} | {c['primary_hull']} | {c['primary_alpha']:g}° | {count} | {c['isae_report_aspect_ratio'] or '—'} | {c['outline']['length_over_diameter']:.6g} |")
    lines+=['','## Primary-source conflicts','',
        'TR-405 Figure6 uses 9° for RS-1; ISAE Figure24 labels it 10°. Figures6/7 normalize transverse load per unit axial length by dynamic pressure and maximum diameter. Figure8 (R-101) divides by dynamic pressure alone, so its ordinate is dimensional; its caption specifies a 33.01-inch model. These curves cannot all be treated as the same local lift coefficient.','',
        'TM-574 describes the ZR III hull. Its Figure3 and Bernoulli equation show static gauge pressure as a percentage of freestream dynamic pressure, equivalent to 100Cp. The ISAE pressure filename says R101 and labels the ordinate as a dynamic-pressure ratio. Negative values are consistent with Cp, not with a nonnegative local dynamic pressure.','',
        'The raw outlines imply length/diameter ratios near8.1,5.5,3.2, while ISAE labels the first three16,11,6. The report defines aspect ratio using diameter. This discrepancy must remain visible; no aspect ratio was fitted to a measured force curve.','',
        '## Explicit geometry reconstruction','',
        'The unlabeled upper/lower outlines share their x samples and a constant center. Subtracting that center gives signed radius. Closed tips use the nearest outline zero crossing, or linear extrapolation of the first/last positive segment when no crossing is stored. Only the contiguous positive interior is used, with zero-radius endpoints. The same geometric scale converts x and radius, and reconstructed length is one metre. Original negative samples remain unchanged in the source record.','']
    for c in cases:
        lines.append(f"- [{c['name']} diagnostic input]({Path(c['derived_path']).name}): {c['outline']['nose_method']} at the nose, {c['outline']['tail_method']} at the tail; source center {c['outline']['raw_outline_center']:g}; setup outcomes {', '.join(str(r['panels'])+': '+r['status'] for r in c['setups'])}.")
    lines+=['',
        'The R33 input currently fails display construction: its mathematically zero tail radius evaluates as a tiny negative floating-point value. Native aerodynamic quadrature still constructs. The source audit retains the exact error and spline extrema; no positive endpoint was substituted. The interpolant also overshoots the largest radius sample, which is a separate geometry-accuracy concern.']
    lines+=['','This construction is conditional on the plotted outlines representing physical geometry at equal scale. Natural cubic interpolation and caps introduce further uncertainty. It supplies a reproducible diagnostic model, not recovered original ASWING input. No force/pressure values, drag offsets or solver tolerances were fitted.','',
        '## Remaining work','']+[f'- {note}' for note in limitations]+['']
    (D/'isae-sa13-sources.md').write_text('\n'.join(lines))
    print(out['status'],[(c['name'],[(r['panels'],r['status']) for r in c['setups']]) for c in cases],flush=True)


if __name__=='__main__':main()
