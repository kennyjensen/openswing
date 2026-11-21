"""Audit the unmodified SA-14 wing/body sources and their normalization."""
from pathlib import Path
import csv
import hashlib
import json
import re
import sys
import numpy as np

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from openswing.asw import parse_asw
from openswing.geometry import model_meshes,geometry_summary
from openswing.volume import body_quadrature
REVISION='f62943df20e9e4d7d9f50e070477b22426b5f865'
CACHE=ROOT/'.reference/isae-validation'/REVISION
FOLDER=next(CACHE.glob('1 - Aerodynamics/SA*/SA - 14 - *'))
D=ROOT/'docs/validation'
MODELS={'wing_body':'NACA_TN_3730_bench.asw','wing_only':'NACA_TN_3730_bench_wing_only.asw',
        'infinite_body':'NACA_TN_3730_bench_infinite_fuselage.asw','body_only':'NACA_TN_3730_bench_fuselage.asw'}
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()


def csv_series(path):
    rows=list(csv.reader(path.read_text().splitlines()));out=[]
    assert all(rows[1][i:i+2]==['X','Y'] for i in range(0,len(rows[1]),2))
    for i in range(0,len(rows[0]),2):
        points=[];empty=[]
        for n,row in enumerate(rows[2:],3):
            assert bool(row[i].strip())==bool(row[i+1].strip())
            if row[i].strip():points.append(dict(row=n,xy=[float(row[i]),float(row[i+1])]))
            else:empty.append(n)
        out.append(dict(label=rows[0][i],columns=[i,i+1],points=points,empty_rows=empty))
    return out


def main():
    manifest=json.loads((CACHE.parent/'manifest.json').read_text());assert manifest['revision']==REVISION
    files={}
    for path in sorted(p for p in FOLDER.rglob('*') if p.is_file()):
        name=path.relative_to(CACHE).as_posix();pin=manifest['files'][name];data=path.read_bytes()
        assert len(data)==pin['bytes'] and sha(path)==pin['sha256']
        assert hashlib.sha1(f'blob {len(data)}\0'.encode()+data).hexdigest()==pin['git_blob_sha1']
        files[name]=pin
    assert len(files)==50
    models=[]
    for name,filename in MODELS.items():
        path=FOLDER/'ASWING_simulations'/filename;source=path.read_text();model=parse_asw(source);setups=[]
        for panels in [25,50,100]:
            meshes=model_meshes(model,panels)
            for mesh in meshes:
                if not mesh.beam.lifting:body_quadrature(mesh)
            setup=dict(panels=panels,mesh_status='constructed',actual_intervals={str(m.beam.index):len(m.tm) for m in meshes},
                       normal_section_area=float(sum(np.sum(m.length*m.beam.value('chord',m.tm)) for m in meshes if m.beam.lifting)))
            try:geometry_summary(model,panels);setup['display_status']='constructed'
            except ValueError as exc:setup.update(display_status='rejected',error=str(exc))
            setups.append(setup)
        beams=[]
        for b in model.beams:
            row=dict(index=b.index,physical_index=b.physical_index,lifting=b.lifting,domain=list(b.domain),
                endpoints=b.position(b.domain).tolist(),distributions={k:dict(t=v.t.tolist(),values=v.values.tolist()) for k,v in b.distributions.items()})
            if not b.lifting:
                row['endpoint_radius']=b.value('radius',b.domain).tolist()
                row['maximum_tabulated_radius']=float(max(b.distributions['radius'].values))
            beams.append(row)
        models.append(dict(name=name,path=path.relative_to(CACHE).as_posix(),sha256=sha(path),source=source,
            constants=model.constants.tolist(),reference=model.reference.tolist(),records={k:[r.tolist() for r in v] for k,v in model.records.items()},beams=beams,setups=setups))
    experimental=[]
    for name in ['Figure7.csv','Figure17.csv','Figure24.csv']:
        copies=[FOLDER/folder/name for folder in ['Experimental_data','ASWING_data','ASWING_simulations']]
        assert len({sha(p) for p in copies})==1
        experimental.append(dict(filename=name,source_sha256=sha(copies[0]),
            identical_copies=[p.relative_to(CACHE).as_posix() for p in copies],series=csv_series(copies[0]),
            interpretation=('Absolute load distributions, primary Figure7, wing alone and wing/body at iw=0.' if name=='Figure7.csv' else
                'Headers/positive values describe absolute iw=4deg loads, consistent with primary Figure15. They cannot be primary Figure17 incremental loads. Exact digitization provenance unresolved.' if name=='Figure17.csv' else
                'Primary Figure24: total wing/body balance, exposed-wing pressure lift with body, exposed-wing lift without body; all use wing reference area.')))
    commands=[];polars=[]
    for name,stem in [('wing_body','WB_polaire_totale'),('infinite_body','WB_polaire_totale_infinite_fuselage'),('wing_only','W_only_polaire_totale')]:
        path=FOLDER/'ASWING_simulations'/(stem+'.sh');source=path.read_text()
        angles=[float(v) for v in re.findall(r'^!A\s+([-+\d.]+)',source,re.M)]
        speeds=[float(v) for v in re.findall(r'^!V\s+([-+\d.]+)',source,re.M)];assert speeds==[70.]
        command=dict(case=name,path=path.relative_to(CACHE).as_posix(),sha256=sha(path),source=source,
                     alpha=angles,speed=70.,explicit_mesh=False,explicit_pg=False,anchored_defaults_explicit=True)
        commands.append(command)
        table=path.with_suffix('.txt');values=np.loadtxt(table);assert values.shape==(len(angles),6)
        assert np.array_equal(values[:,4],angles) and np.array_equal(values[:,0],np.arange(1,len(values)+1))
        polars.append(dict(case=name,path=table.relative_to(CACHE).as_posix(),sha256=sha(table),rows=values.tolist(),
                           columns=['index','t','conv','stall','alpha','CL'],all_convergence_flags_one=bool(np.all(values[:,2]==1))))
    post=FOLDER/'Post_traitement.m';postsource=post.read_text();embedded=[]
    for match in re.finditer(r'(Wing_(only|Body)_data_alpha_(\d+)_(\d+))\s*=\s*\[(.*?)\];',postsource,re.S):
        values=np.array([[float(v) for v in line.split()] for line in match[5].splitlines() if line.strip()])
        assert values.ndim==2 and values.shape[1]==4
        embedded.append(dict(name=match[1],case='wing_only' if match[2]=='only' else 'wing_body',
                             alpha=float(match[3]+'.'+match[4]),rows=values.tolist(),columns=['t','y','normal_chord','section_cl'],
                             source_note='Manually embedded positive-side rows, including inserted root/tip display values; retain separately from original output tables.'))
    assert len(embedded)==6
    distributions=[]
    for name,filename in [('wing_body','Wing_Body_lift_distribution.txt'),('wing_only','Wing_alone_lift_distribution.txt')]:
        path=FOLDER/'ASWING_simulations'/filename;text=path.read_text()
        angles=[float(v) for v in re.findall(r'Alpha\s*:\s*([-+\d.Ee]+)',text)]
        mach=[float(v) for v in re.findall(r'MachPG\s*:\s*([-+\d.Ee]+)',text)]
        assert angles==[4.7,8.8,12.9] and mach==[.2058,0.,0.]
        distributions.append(dict(case=name,path=path.relative_to(CACHE).as_posix(),sha256=sha(path),source=text,
                                  alpha=angles,printed_pg_mach=mach))
    primary_path=ROOT/'.reference/isae-sa14/naca-tn-3730.pdf'
    assert sha(primary_path)=='8c0e31b643c76560af06dcdd4d271a88545678a1916327ef967f1d452252e271'
    primary=dict(path=primary_path.relative_to(ROOT).as_posix(),sha256=sha(primary_path),url='https://ntrs.nasa.gov/citations/19920075067',
        author='Albert P. Martina',date='April 1956',title='The interference effects of a body on the spanwise load distributions of two45deg sweptback wings of aspect ratio8.02 from low-speed tests',
        visually_reviewed_pdf_pages=[1,2,4,6,8,26,32,39,41,47],reynolds=4e6,mach=.19,pressure_atmospheres=2+1/3,dynamic_pressure_psf=125.,
        wing=dict(area_sq_ft=14.021,area_m2=14.021*.3048**2,span_inches=127.26,span_m=127.26*.0254,
                  root_chord_inches=21.941,tip_chord_inches=9.873,mean_aerodynamic_chord_inches=16.672,
                  mean_geometric_chord_m=14.021*.3048**2/(127.26*.0254),quarter_chord_sweep_deg=45.,aspect_ratio=8.02,taper=.45,
                  root_leading_edge_x_inches=36.76,root_leading_edge_z_inches=3.18,airfoil='NACA63_1A012 streamwise'),
        body=dict(length_inches=127.26,diameter_inches=12.73,forebody_length_inches=33.34,constant_body_length_inches=41.68,
                  forebody='elliptic',afterbody='parabolic',incidence_variants_deg=[0.,4.],incidence_pivot='Root leading edge retains its vertical position.'),
        local_coordinate='2*y/b',local_ordinate='section wind-axis lift coefficient * streamwise chord / mean geometric chord Sw/b',
        exposed_range='Primary exposed-wing integrations start at2*y/b=0.1.',
        corrections='Force data corrected for support/interference/stream misalignment; jet-boundary incidence correction0.387*CL degrees. Spanwise pressure-load corrections are also applied. Do not apply these corrections again to digitized final plots.')
    postprocessing=dict(path=post.relative_to(CACHE).as_posix(),sha256=sha(post),embedded_distributions=embedded,
        local_denominator=.42*2/np.sqrt(2),local_plot_formula='section_cl * normal_chord / (.42*2/sqrt(2))',
        total_lift_multiplier=1-(6.352488928255092*.0254*21.941*.0254*2)/1.301,
        total_plot_formula='Archived total CL times1-(maximum diameter*root streamwise chord)/Sref; used for wing-alone as well as both body cases.',
        caution='An area multiplier cannot establish exposed-wing lift when loading varies spanwise. Compare integrated native strip forces with primary definitions; retain this plotting prescription only as a separate archive diagnostic.')
    limitations=[
        'All four original inputs parse. The body-only file uses feet-to-metre factors 0.3048 while the coupled model uses inch-to-metre 0.0254. Its geometry is 12 times larger, with different references; do not substitute it as the coupled fuselage.',
        'Body-only display currently rejects a tiny negative closed-tip radius; native body quadrature constructs. The isolated SA13 endpoint candidate is not applied to these pinned results.',
        'Figure7/17/24 CSVs under ASWING_data and ASWING_simulations are byte-identical to Experimental_data; they are duplicate measurements, not independent archived solver output.',
        'Figure17.csv has absolute iw=4deg labels and positive loads. Primary Figure17 is negative incremental loading. Figure15 is the likely source of the absolute series, but the digitization provenance is unresolved and no iw=4deg input is supplied.',
        'The primary local-load normalization uses mean geometric chord Sw/b, not mean aerodynamic chord. The postprocessor uses 0.42*sqrt(2), with manually copied normal-section cl/chord rows.',
        'Primary Figure24 distinguishes total wing/body balance lift from pressure-integrated exposed-wing lift with/without body. A global CL or a constant area multiplier is not interchangeable with those observables.',
        'Polars contain only CL and do not record mesh or PG. Load-distribution exports use PG Mach 0.2058 at 4.7deg but 0 at 8.8/12.9deg, while the primary test Mach is 0.19; retain the mixed settings explicitly.',
        'The supplied NACA63A012.txt is airfoil coordinates, not the claimed XFOIL polar. Literal inputs set dCLda 6.2832 and CLmax 2; exact section polar provenance and high-angle validity are unresolved.',
        'The ISAE report attributes weak archived constant-body interference to a source-code conditional and reports unresolved instability after modification. The cited conditional alone does not establish that explanation; matching executable/source evidence is unavailable.',
        'No image-vortex body boundary correction is inferred from these measurements. Numerical body-field verification and physical wing/body agreement require separate evidence.',
        'No physical parameter, geometry, digitized value, source label or solver tolerance is fitted or silently changed.']
    report=dict(status='SOURCE_AUDIT_COMPLETE_QUANTITATIVE_COMPARISONS_PENDING',revision=REVISION,files=files,
        modules={p.name:sha(p) for p in (ROOT/'openswing').glob('*.py')},script_sha256=sha(Path(__file__)),
        models=models,experimental=experimental,commands=commands,polars=polars,distribution_exports=distributions,
        postprocessing=postprocessing,primary=primary,limitations=limitations)
    (D/'isae-sa14-sources.json').write_text(json.dumps(report,indent=2)+'\n')
    lines=['# SA-14 wing/body source audit','',
        '**Comparisons are pending.** All 50 upstream files are pinned to the repository revision. The four literal models remain unchanged. [Machine-readable sources](isae-sa14-sources.json) retain all measurements, commands, polars, load exports and geometry tables.','',
        'The primary reference is [Martina, NACA-TN-3730 (April 1956)](https://ntrs.nasa.gov/citations/19920075067). Its test is at Mach 0.19 and Reynolds number 4 million. The swept wing has span 127.26 in, area 14.021 sqft and no twist for the selected comparisons. The body is elliptic/constant/parabolic with fineness ratio 10.','',
        '## Import and geometry','',
        '| Input | Native mesh | Display | Note |','|---|---|---|---|']
    for m in models:
        lines.append(f"| {m['name']} | All 25/50/100 requested meshes construct | {m['setups'][0]['display_status']} | {'12× geometric scale; different reference values' if m['name']=='body_only' else 'Original input'} |")
    lines+=['','## Measurements and normalization','',
        'Figure7 supplies 48 local-load points for wing alone and wing/body at 4.7°, 8.8° and 12.9°. Figure24 supplies 44 total/exposed lift points. Figure17.csv supplies 24 additional points labelled iw=4°; its name conflicts with the primary figure numbering and it has no matching original input.','',
        'The three directories containing Figure7/17/24 CSVs are exact duplicates. The actual ASWING evidence consists of three CL polar tables and two load-distribution text exports, plus manually embedded plotting arrays.','',
        'For local loads, use 2y/b and wind-axis force per unit span divided by q times the mean geometric chord Sw/b. The primary exposed-wing integration starts at 2y/b=0.1. Figure24 total balance lift includes the body; its other two series contain exposed-wing pressure lift.','',
        f"The MATLAB script instead divides normal-section cl times chord by {postprocessing['local_denominator']:.9g}m and multiplies archived global CL by {postprocessing['total_lift_multiplier']:.9g}. Those prescriptions will remain separate diagnostics. Neither supplies a replacement for the primary force normalization.",'',
        'Primary Figure17 shows negative incremental loading from a change of incidence. The positive absolute loads in Figure17.csv resemble the iw=4° branch of primary Figure15. This mapping remains conditional until the digitization can be traced.','',
        '## Remaining qualifications','']+[f'- {x}' for x in limitations]+['']
    (D/'isae-sa14-sources.md').write_text('\n'.join(lines))
    print(report['status'],len(files),'files',[(p['case'],len(p['rows'])) for p in polars],flush=True)


if __name__=='__main__':main()
