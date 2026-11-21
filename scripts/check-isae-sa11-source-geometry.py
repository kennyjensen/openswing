"""SA-11 source geometry and reflection diagnostics; no aerodynamic fit or validation pass."""
from pathlib import Path
import json, sys
import numpy as np

ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from openswing.asw import parse_asw
from openswing.geometry import surface_frame
from isae_sa11_reference import sha, NAMES


def main():
    destination=ROOT/'docs/validation'; source_path=destination/'isae-sa11-sources.json'
    source=json.loads(source_path.read_text()); rows=[]; reflection=np.diag([1.,-1.,1.])
    for name in NAMES+['wingtip_up_cant0']:
        original=next(row for row in source['models'] if row['name']==name)
        row=next((row for row in source['derived'] if row['name']==name),original)
        model=parse_asw(row['source']); assert model.units.declarations['L']==(1.,'m')
        geometry=[]
        for beam in row['beams']:
            a,b=np.array(beam['endpoints']); d=b-a
            geometry.append(dict(beam=beam['index'],endpoints=beam['endpoints'],
                frontal_axis_cant_from_vertical_deg=float(np.rad2deg(np.arctan2(abs(d[1]),abs(d[2])))) if beam['index']!=1 else None,
                frontal_endpoint_distance=float(np.hypot(d[1],d[2])),
                geometry_diagnostic=beam['geometry_diagnostic']))
        mirrors=[]
        for right_index,left_index in [(1,1),(2,3),(4,5)]:
            right=next((b for b in model.beams if b.index==right_index),None)
            left=next((b for b in model.beams if b.index==left_index),None)
            if right is None or left is None: continue
            lo,hi=right.domain; lo=max(0.,lo)
            t=lo+(hi-lo)*np.linspace(.01,.99,23)
            a=surface_frame(right,t); b=surface_frame(left,-t)
            expected=np.einsum('ij,njk,kl->nil',reflection,a,np.diag([1.,-1.,1.]))
            mirrors.append(dict(right=right_index,left=left_index,
                maximum_axis_position_error=float(np.max(abs(left.position(-t)-right.position(t)@reflection))),
                maximum_section_frame_component_error=float(np.max(abs(b-expected)))))
        rows.append(dict(name=name,case_id=row.get('case_id',name+'_literal'),
            reconstructed=row is not original,reference=row['reference'],beams=geometry,reflection=mirrors,
            main_constant_body_y_incidence_deg=row['beams'][0]['geometry_diagnostic']['main_wing_horizontal_cut_incidence_deg']))
    out=dict(status='SOURCE_GEOMETRY_DIAGNOSTIC_NOT_EXPERIMENTAL_VALIDATION',rows=rows,
        source_report_sha256=sha(source_path),script_sha256=sha(Path(__file__)),
        modules={p.name:sha(p) for p in (ROOT/'openswing').glob('*.py')},
        primary=dict(pdf_sha256=source['primary']['sha256'],upper_cant_from_vertical_deg=15.,lower_cant_from_vertical_deg=36.,
            geometric_root_incidence_deg=2.,exposed_semispan_reference_area_m2=.4648,geometry_pdf_pages=[5,6,18,19]),
        incidence_definition='atan2(n_x,n_z): incidence of the surface-plane intersection at constant body y, in a vertical x-z plane. The pinned source audit calls this field main_wing_horizontal_cut_incidence_deg; that field name is imprecise. Its numerical value is unchanged here.',
        limitations=['Front-view axis cant is evaluated directly from endpoint coordinates. Section frame diagnostics use the current documented ASWING frame convention.',
            'Normal chord and beam-axis twist are not streamwise chord and body-axis incidence. Section alpha also describes zero-lift offset; no parameter is adjusted here.',
            'The cant0 file has no measured/archived comparison and is not rescaled to pretend it is the measured winglet configuration.'])
    (destination/'isae-sa11-source-geometry.json').write_text(json.dumps(out,indent=2)+'\n')
    lines=['# SA-11 source and geometry audit','',
        '**Source audit complete; aerodynamic comparisons remain in progress. No experimental validation pass.**','',
        'The pinned ISAE case contains 65 files, five aircraft inputs, 16 archived polars and five airfoil coordinate sets. The [source record](isae-sa11-sources.json) retains their hashes, original content, CSV row mappings and commands. Upstream shell and MATLAB scripts were read, never executed.','',
        'The primary source is Jacobs, Flechner and Montoya, [NASA-TN-D-8473 (1977)](https://ntrs.nasa.gov/citations/19780012121), a semispan KC-135A experiment. The ISAE heading says KC-130, but the apparatus and primary citation identify KC-135A. The NASA report was recovered and its geometry drawings and measurement description were reviewed.','',
        '## Literal inputs and explicit reconstructions','',
        '| Input | Literal result | Separate reconstruction |','|---|---|---|']
    for original in source['models']:
        derived=next((r for r in source['derived'] if r['name']==original['name']),None)
        if not original['parsed']:result=original['error']
        elif any(s['status']=='rejected' for s in original['setups']):result=original['setups'][0]['error']
        else:result='Constructs at all three checked meshes'
        link='—' if derived is None else f"[{derived['kind']}]({Path(derived['artifact']).name})"
        lines.append(f"| {original['name']} | {result} | {link} |")
    lines+=['','All reconstructions preserve the geometry, section properties and reference quantities. Two correct joint station scaling; the cant0 reconstruction corrects only the winglet-side joint parameters. They are distinct inputs and do not count as successful literal imports.','',
        '## Geometry and reference differences','',
        '- The upper-winglet axes have about 15.001° front-view cant from vertical, consistent with the stated 15°. The lower-winglet axes instead have 56.041°, versus the primary 36°. This mismatch is preserved.',
        '- The main-wing input twist is 2° about the swept beam axis; its evaluated surface plane intersects a constant-body-y vertical plane at about 1.607° incidence. The primary describes 2° root incidence. The separate airfoil zero-lift offsets are retained and are not fitted to hide the difference.',
        '- Primary coefficients use exposed semispan area 0.4648 m². Half the main input reference area is 0.46645 m². The inputs also use different moment-reference locations. Reference conventions require reconciliation before claiming matched predictions.',
        '- The cant0 variant uses geometry ten times larger, a different reference area and opposite signed left/right winglet twist. No measured or archived curve is assigned to it.',
        '- Primary geometry includes winglet fillets, flow-through nacelles, a fuselage and representative cruise flexibility. The literal rigid lifting-surface calculation is not established as an equivalent apparatus.',
        '', 'The [geometry diagnostic](isae-sa11-source-geometry.json) records physical frames, section-surface areas, endpoint cant and reflection differences. Raw normal-section chord dimensions must not be mistaken for streamwise chord.','',
        '## Measurement and postprocessing audit','',
        '- CSV headers assign the third pair to upper/lower winglets and the fourth to the extension. MATLAB lift plotting interchanges those two labels; this study follows the headers and retains that provenance uncertainty.',
        '- The lift CSVs have two header lines. MATLAB skips three and repeatedly uses baseline columns for the experimental slope calculations. The study retains all numeric rows and compares each labeled configuration separately.',
        '- MATLAB adds constant CD offsets of 0.0064 at Mach 0.7 and 0.0075 at Mach 0.8. These are documented postprocessing transformations, not raw solver output.',
        '- The archived tables and scripts use speeds 240, 255, 266 and 272 m/s. Their Mach labels are approximate with the input sound speed of 340.21 m/s. Experimental lift comparisons will also evaluate the exact nominal Mach values.',
        '- The ISAE report explicitly states that PG is enabled. PG-off states are numerical diagnostics. Exact archived PG values, initial K/F state and solution-branch history remain unresolved.',
        '- The NASA report warns that the wing/fuselage gap affects absolute axial force and thus lift and drag. Cruise repeat differences of about 0.0002 in CD, less than 0.2% in CL and less than 0.4% in rolling coefficient indicate repeatability, not complete uncertainty bounds.',
        '', 'Transonic shocks and wave drag are outside this ASWING model. Large local velocities at the winglet junctions are also reproduced by [independent line quadrature](isae-sa11-velocity.json); they are not converted into accepted physical solutions.','']
    (destination/'isae-sa11-sources.md').write_text('\n'.join(lines))
    print('SA11 source geometry report written; no coverage increment.',flush=True)


if __name__=='__main__':main()
