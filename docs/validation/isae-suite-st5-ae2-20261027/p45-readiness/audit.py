"""Read saved figures and local documents only; no production or upstream imports."""
from pathlib import Path
import collections
import hashlib
import json
import math
import re
import sys
import numpy as np
from scipy.io import loadmat

ROOT = Path('/home/userland/aswing')
OUT = Path('/tmp/openswing-isae-p45-readiness-20261027')
BASE = ROOT / '.reference/isae-validation'
manifest = json.loads((BASE / 'manifest.json').read_text())
CACHE = BASE / manifest['revision']

def pin(path):
    blob = path.read_bytes()
    return dict(path=str(path), bytes=len(blob), sha256=hashlib.sha256(blob).hexdigest())

def write(name, data):
    (OUT / name).write_text(json.dumps(data, indent=2, allow_nan=False) + '\n')

def native(a):
    return [float(x) if np.isfinite(x) else None for x in np.asarray(a).ravel()]

inventory = json.loads((ROOT / 'docs/validation/isae-figure-inventory.json').read_text())
inventory = {x['sha256']: x for x in inventory['figures']}
raw, figures, sources = [], [], []
for name, expected in manifest['files'].items():
    if '/P-4 -' not in name and '/P-5 -' not in name:
        continue
    path = CACHE / name
    source_pin = pin(path)
    assert source_pin['sha256'] == expected['sha256']
    extract = BASE / 'figure-series' / (source_pin['sha256'] + '.json')
    extract_pin = pin(extract)
    assert extract_pin['sha256'] == inventory[source_pin['sha256']]['extracted_sha256']
    old = json.loads(extract.read_text())
    mat = loadmat(path, simplify_cells=True)
    family = 'P-4' if '/P-4 -' in name else 'P-5'
    component = 'axial' if 'Axial' in name else 'swirl'
    fg = dict(source=source_pin, cached_extraction=extract_pin, family=family,
              component=component, axes=[], raw_series=[], opaque_workspace_bytes=int(mat['__function_workspace__'].size))
    for ai, axis in enumerate(mat['hgS_070000']['children']):
        if axis.get('type') != 'axes':
            continue
        loc = f'hgS_070000.children[{ai}]'
        texts = [{'location': f'{loc}.children[{ti}].properties.String', 'text': str(child['properties'].get('String', ''))}
                 for ti, child in enumerate(axis['children']) if child.get('type') == 'text']
        title = next(x['text'] for x in texts if x['text'].startswith('X/D ='))
        station = float(title.split('=')[1])
        fg['axes'].append(dict(location=loc, x_over_D=station, labels=texts))
        lines = [(li, child) for li, child in enumerate(axis['children']) if 'XData' in child.get('properties', {})]
        assert len(lines) == 3
        for (li, line), kind, color, linestyle in zip(lines, ['Exp', 'ASW', 'ASW-m'], [[0,0,0], [1,0,0], [0,.5,0]], ['-', '-.', '--']):
            props = line['properties']
            assert np.array_equal(props['Color'], color) and props['LineStyle'] == linestyle
            label = props.get('DisplayName', '')
            assert label in ('', kind)
            x, y = native(props['XData']), native(props['YData'])
            pairs = list(map(list, zip(x,y)))
            line_loc = f'{loc}.children[{li}]'
            previous = next(x for x in old['series'] if x['location'] == line_loc)
            assert pairs == previous['xy']
            missing = [i+1 for i, (v,r) in enumerate(pairs) if v is None or r is None]
            rec = dict(source_sha256=source_pin['sha256'], file=path.name, family=family,
                       location=line_loc, series_kind=kind, literal_display_name=label,
                       classification_basis='literal DisplayName' if label else 'same figure first-axis legend, child order, color and LineStyle',
                       color=color, line_style=linestyle, x_over_D=station, component=component,
                       coordinate_mapping={'XData':'velocity_m_s', 'YData':'r_over_R'},
                       stored_rows=len(pairs), finite_rows=len(pairs)-len(missing), unavailable_row_numbers=missing,
                       rows=[dict(row_number=i+1, velocity_m_s=v, r_over_R=r) for i,(v,r) in enumerate(pairs)])
            if kind != 'Exp':
                assert len(pairs) == 100 and y[0] == 0 and y[-1] == 1.5
                rec['uniform_radial_grid_max_roundoff'] = max(abs(r-1.5*i/99) for i,r in enumerate(y))
                if component == 'swirl':
                    assert missing == [1] and y[0] == 0
            raw.append(rec)
            fg['raw_series'].append({k:v for k,v in rec.items() if k != 'rows'})
    figures.append(fg)
    sources.extend([source_pin, extract_pin])

counts = {}
for family in ['P-4','P-5','all']:
    rr = [x for x in raw if family == 'all' or x['family'] == family]
    counts[family] = {kind: dict(series=sum(x['series_kind']==kind for x in rr),
                                stored_scalar_slots=sum(x['stored_rows'] for x in rr if x['series_kind']==kind),
                                finite_scalars=sum(x['finite_rows'] for x in rr if x['series_kind']==kind),
                                unavailable_scalars=sum(len(x['unavailable_row_numbers']) for x in rr if x['series_kind']==kind))
                      for kind in ['ASW','ASW-m','Exp']}
for family in counts:
    rr = [x for x in raw if (family == 'all' or x['family'] == family) and x['series_kind'] == 'ASW']
    coordinate_pairs = collections.defaultdict(dict)
    for rec in rr:
        stem = rec['file'].replace('_Axial_Velocity.fig','').replace('_Swirl_Velocity.fig','')
        coordinate_pairs[(stem, rec['x_over_D'])][rec['component']] = [r['r_over_R'] for r in rec['rows']]
    assert all(set(v) == {'axial','swirl'} and v['axial'] == v['swirl'] for v in coordinate_pairs.values())
    counts[family]['ASW_paired_receiver_rows'] = sum(len(v['axial']) for v in coordinate_pairs.values())

duplicate_keys = collections.Counter((x['file'], x['series_kind'], x['x_over_D'], x['component']) for x in raw)
assert all(n == 1 for n in duplicate_keys.values())
write('raw-figure-series.json', dict(scope='All decoded original HG curves retained, including experiments, ASW-m and NaNs.', series=raw))
write('figure-metadata.json', dict(figures=figures, counts=counts,
    graphic_duplicate_series_with_same_file_kind_station_component=0,
    policy='Any graphic duplicates would be retained as raw evidence and excluded from independent-target count. No repeated graphics with the same file/kind/station/component were found. Numerically equal curves under distinct model labels or physical stations remain distinct evidence.'))

report_path = BASE / 'reports/Experimental_validation_of_ASWING_Part_2_Propellers_V2.txt'
report_pdf = CACHE / '5 - Technical Reports/Experimental_validation_of_ASWING_Part_2_Propellers_V2.pdf'
assert pin(report_pdf)['sha256'] == manifest['files'][str(report_pdf.relative_to(CACHE))]['sha256']
source_ranges = {
    str(report_path): [(206,215),(253,279),(345,393),(804,815),(1063,1137),(1157,1186),(1260,1280),(1461,1477),(1485,1491)],
    str(ROOT/'.reference/asw_theory.txt'): [(1151,1172),(1190,1248),(1269,1298)],
    str(ROOT/'openswing/propulsion.py'): [(34,68),(109,167)],
}
excerpts = []
for name, ranges in source_ranges.items():
    lines = Path(name).read_text().split('\n')
    excerpts.append(dict(source=pin(Path(name)), line_number_convention='1-based LF-delimited lines',
        excerpts=[dict(first_line=a,last_line=b,lines=[dict(line_number=i+1,text=lines[i]) for i in range(a-1,b)]) for a,b in ranges]))
write('source-excerpts.json', excerpts)
sources.extend(pin(p) for p in [BASE/'manifest.json', ROOT/'docs/validation/isae-suite-backlog.json',
    ROOT/'docs/validation/isae-figure-inventory.json', ROOT/'scripts/extract-isae-figures.py', report_pdf])
sources.extend(x['source'] for x in excerpts)

conditions = [
 dict(case='P4_A_GWS', provenance='MATLAB reproduction of ASWING jet model; report lines1088–1092. Not a recovered original ASWING run.',
      nominal_propeller='GWS 5X4.3', nominal_diameter_m=.127, nominal_radius_m=.0635, rpm=5000,
      advance_velocity_m_s=0, x_over_D=[.125,.5,1,2,3], original_model_driver_available=False,
      geometry_rpm_sources=['report lines1100–1104','report lines1461–1465'],
      blocked_inputs=['independent shaft power or thrust/torque and delta-velocity input tuple','density','effective blade drag area CdA','exact historical MATLAB formulation/coefficients']),
 dict(case='P4_B_DA4002_filename', provenance='Static MATLAB reproduction, with unresolved propeller identity.',
      filename_propeller='DA4002', report_second_static_propeller='APC Sport 4.2X2 at 9000 RPM',
      nominal_diameter_candidates_m={'APC_4_2in':.10668,'DA4002_9in':.2286},
      advance_velocity_m_s=0, x_over_D=[.125,.5,1,2,3], original_model_driver_available=False,
      geometry_rpm_sources=['report lines1125–1137','report lines1461–1477'],
      blocked_inputs=['resolve filename versus report APC identity before assigning diameter/RPM','independent power','density','CdA','exact historical MATLAB formulation/coefficients']),
 dict(case='P5_A_GWS', provenance='Report attributes advance-flow predictions to an ASWING numerical-sensor bench; actual model, driver and sensor exports are absent.',
      nominal_propeller='GWS 5X4.3', nominal_diameter_m=.127, nominal_radius_m=.0635, rpm=5000,
      published_advance_ratio=.52, x_over_D=[.125,.5,1,2], original_model_driver_available=False,
      saved_tail_velocity_candidate_m_s=5.486400000000001, candidate_V_over_nD=.5184,
      candidate_qualification='Output-derived freestream candidate, not independently proven driving input; published ratio is rounded and its conversion convention must be bound explicitly.',
      geometry_rpm_sources=['report lines1157–1159','report lines1274–1280','report lines1461–1465'],
      blocked_inputs=['independent shaft power or thrust/torque and delta-velocity input tuple','density','CdA','exact advance speed independent of targets','signed spin and original sensor pose/recovery formula']),
 dict(case='P5_B_DA4002', provenance='Report attributes advance-flow predictions to ASWING; original model/driver/sensor exports are absent.',
      nominal_propeller='DA4002 9in', nominal_diameter_m=.2286, nominal_radius_m=.1143, rpm=5000,
      published_advance_ratio=.64, x_over_D=[.125,.5,1,2], original_model_driver_available=False,
      saved_tail_velocity_candidate_m_s=12.192, candidate_V_over_nD=.64,
      candidate_qualification='Output-derived freestream candidate (also consistent with the rounded report ratio under V/(nD)), not independently proven driving input.',
      geometry_rpm_sources=['report lines1165–1169','report lines1463–1465','report lines1485–1491'],
      blocked_inputs=['independent shaft power or thrust/torque and delta-velocity input tuple','density','CdA','exact advance speed and convention','signed spin and original sensor pose/recovery formula']),
]
for case in conditions:
    prefix=case['case'].split('_filename')[0]
    rr=[x for x in raw if x['file'].startswith(prefix) and x['series_kind']=='ASW']
    case['ASW_series']=len(rr)
    case['ASW_stored_scalar_slots']=sum(x['stored_rows'] for x in rr)
    case['ASW_available_scalar_targets']=sum(x['finite_rows'] for x in rr)

report = dict(status='SOURCE_AUDIT_COMPLETE_EXECUTION_BLOCKED', source_revision=manifest['revision'],
    scope='P-4/P-5 only; saved FIG decoding, source-document and current API reading. No production imports, component calls, solver calls, upstream scripts or repository edits.',
    counts=counts, executable_complete_input_cases=0, conditions=conditions,
    recovered_coordinates=dict(XData='axial or swirl velocity in m/s, not the spatial coordinate',YData='r/R',
        streamwise='axes title X/D, positive downstream from propeller centre', radial_grid='100 stored model rows, r/R from 0 to 1.5 in 99 intervals; original binary64 values retained',
        cartesian_conversion='Once diameter, axis and signed spin are bound: downstream=(X/D)*D and radial_distance=(r/R)*R. A declared axisymmetric local frame can use receiver=(downstream,radial_distance,0); literal historical sensor azimuth/sign is not recovered.',
        swirl_axis='All 18 ASW swirl series have an unavailable first value at r/R=0; keep unavailable, never replace by zero or a pass.',
        axial_total='P5 stored axial tails are 5.486400000000001 or 12.192 m/s, consistent with total axial velocity. Current jet_velocity returns increments, so total-velocity reconstruction must explicitly add freestream and bind original sensor convention.'),
    attribution=dict(ASW='First axis explicitly labelled ASW; other axes bound by identical color/LineStyle/order to that legend; report captions identify ASWING 5.96.',
        ASW_m='Separate modified hub-core model, not an acceptance target for the unchanged ASWING component; source lines 1113–1119 describe modification but give no numeric hub size/mixing rule.',
        Exp='Digitized Deters experimental evidence only, not archived-ASWING acceptance targets; all curves retained separately.'),
    source_cautions=[
        'P4 report calls five locations but omits 2.0 from its bracketed list; FIG titles recover all five including2.0.',
        'Report line1077 says radial extent1.5 diameters, whereas FIG y-axis says r/R. Use saved labelled coordinates; do not double the radius based on prose.',
        'P4 B filename versus APC report contradiction remains unresolved; no relabelling or diameter/RPM guess.',
        'HG properties/ApplicationData expose layout, labels and series, no physical parameter tuple. hgM/meta_data/__function_workspace__ contain opaque MCOS content not exhaustively decoded; absence of hidden parameters is not proved.',
        'Binary64 figure samples are not original text tokens. No historical decimal precision or strict acceptance threshold has been reconstructed.',
        'The current jet_profile code explicitly uses corrected angular-momentum integrals relative to printed Eq138. Without the missing MATLAB/source bench, operator equivalence cannot be asserted or manufactured by fitting.'
    ],
    current_api=dict(path=str(ROOT/'openswing/propulsion.py'),
        actuator_disk='lines 34–68: power,density,velocity,radius,omega,drag_area -> thrust,torque,delta_velocity',
        jet_profile='lines 109–137: engine axial_velocity,delta_velocity,radius,thrust,torque + downstream,density -> radii and axial/swirl increments',
        jet_velocity='lines 140–167: points, engine position/axes/jet_enabled, wind direction and density -> vector increments',
        source_equations='asw_theory.txt lines1151–1298, Eq 122–139',
        executable_route='Existing isolated component API supports unmodified axial/swirl field once inputs and signed projection are supplied; no aircraft equilibrium required.',
        legacy_distinction='P4 targets are MATLAB model reproductions. P5 targets are report-attributed ASWING sensor-derived curves. Neither is currently an exact native table+driver pairing.'),
    next_adapter=dict(preferred='P5_A_GWS unmodified ASW: 8 series / 800 slots / 796 finite; strongest recovered propeller+RPM+ratio identity and an attributed ASWING sensor bench.',
        required_recovery=['Obtain original sensor bench .asw/.sh or independent parameter record for power,density,CdA,actualV,spin and sensor orientation.',
            'Bind total axial velocity and tangential sign/projection to original sensor channels; preserve axis NaNs.',
            'Declare binary64 figure comparison policy separately from printed-table precision; do not widen tolerances to obtain agreement.',
            'For P4 additionally recover MATLAB script/formulation; resolve second propeller identity. Keep ASW-m and experiments separate.'],
        blocked_inventory_scope='Can now enumerate all 36 unmodified ASW curves, 3,600 slots / 3,582 finite and 18 unavailable without promoting any to an executable pass.',
        prohibited_shortcuts='Do not infer power,CdA,density from ASW velocity targets; that would make the comparison circular. Nominal diameter/RPM or experimental measured power alone do not prove the exact historical setup.'),
    source_pins=sources)
write('report.json', report)
md = '''P4/P5 source audit: no complete input set is yet executable.

| Family | ASW series | Stored slots | Finite targets | Unavailable axis values | Separate ASW-m slots | Experimental finite/stored |
|---|---:|---:|---:|---:|---:|---:|
'''
for family in ['P-4','P-5']:
    c=counts[family]
    md += f"| {family} | {c['ASW']['series']} | {c['ASW']['stored_scalar_slots']} | {c['ASW']['finite_scalars']} | {c['ASW']['unavailable_scalars']} | {c['ASW-m']['stored_scalar_slots']} | {c['Exp']['finite_scalars']}/{c['Exp']['stored_scalar_slots']} |\n"
md += '''
The unmodified model curves pair into 1,000 P4 and 800 P5 receiver rows (axial and swirl at each stored radius/station). Experimental curves have different digitized radial grids and are not merged into these receiver counts.

All eight original FIG hashes and cached extraction hashes verify. Raw curves and NaNs are retained. No repeated graphic series within the same file/model/station/component was found; duplicates, if present, would remain raw evidence but not independent targets. Experimental and modified ASW-m curves remain separate.

Saved XData is velocity (m/s); YData is r/R. Model curves have 100 radial rows spanning 0..1.5. FIG titles establish x/D={.125,.5,1,2,3} for P4 and{.125,.5,1,2} for P5. P4 prose omits 2 from its list; use FIG titles. All 18 original ASW swirl curves have NaN at the axis; do not replace it by zero.

P4 is explicitly a MATLAB reproduction of the jet model (report 1088–1092), not a recovered ASWING executable run. GWS 5X4.3 and 5000 RPM are documented. P4_B filenames say DA4002, but the report’s second static case is APC Sport 4.2X2 at 9000 RPM (1125–1137,1461–1477); diameter/RPM pairing remains unresolved.

P5 is attributed to an ASWING sensor bench (1088–1097). GWS 5X4.3 at 5000 RPM / ratio .52 and DA4002 nominal 9 in at 5000 RPM / ratio .64 are documented. Axial tails recover 5.486400000000001 and 12.192 m/s as output-derived freestream candidates, not independent driving-input proof. Total axial velocity needs freestream added to the component API’s increment; original sensor projection and signed swirl remain unbound.

The existing actuator_disk/jet_profile/jet_velocity API can evaluate unmodified fields, but independent power, density and CdA are missing for every case. Exact spin, advance-speed convention and sensor setup also remain unresolved for P5. Nominal propeller geometry and rounded ratios do not establish the historical input tuple. ASW-m additionally needs its omitted hub-core parameters. Readable HG metadata contains graphics settings; opaque MCOS workspace content was not exhaustively decoded.

Preferred next recovery: P5_A_GWS, 8 ASW curves / 800 slots / 796 finite. Obtain its original bench or independent input record before an executable adapter. A blocked inventory can immediately preserve all 36 ASW curves / 3,600 slots / 3,582 finite. Do not recover power/CdA from the acceptance curves, fit experiments, or invent FIG precision tolerances. Source-only audit; no production imports, solvers or repository changes.

Exact pins, line excerpts, per-axis classification and all sample values are in report.json, source-excerpts.json, figure-metadata.json and raw-figure-series.json.
'''
(OUT/'report.md').write_text(md)
assert not any(x == 'openswing' or x.startswith('openswing.') for x in sys.modules)
assert all(pin(Path(p['path'])) == p for p in sources)
receipt=dict(status='completed', physics_calls=0, production_imports=0, upstream_scripts_executed=0,
             repository_mutations=0, original_figures_verified=8, extraction_jsons_verified=8,
             source_pins_unchanged=True, all_raw_series_preserved=True,
             artifacts=[pin(p) for p in sorted(OUT.iterdir()) if p.is_file() and p.name!='receipt.json'])
write('receipt.json', receipt)
print(json.dumps(dict(counts=counts, receipt=pin(OUT/'receipt.json')), indent=2))
