"""Complete ST2 native scope and predeclared conditional modal comparisons.

Planning and validation use only the standard library and strict source readers.
Both original null Weight rows remain literal. Static attachment/pairing and
workbook provenance gaps stay blocked; modal medium/base choices are qualified.
"""
from copy import deepcopy
from decimal import Decimal
import hashlib
import json
import math
from pathlib import Path
import re
import tempfile
import traceback
import xml.etree.ElementTree as ET
from zipfile import ZipFile

from scripts.isae_st2_archive import COLUMNS, NUMBER, decode_archive_profile


REVISION = 'f62943df20e9e4d7d9f50e070477b22426b5f865'
MANIFEST_SHA256 = '813347a3bd9fcbd029a1ec86e0c3141f82422af26f33ebde7c2f732a16bf27f6'
READINESS = 'docs/validation/isae-suite-expanded-20261026/st2-readiness.json'
READINESS_SHA256 = 'b8e11b4eb5486fa56f797dec4f1930a381ef4affa1a12cb00fb8b526ed9026dd'
MODAL_READINESS = 'docs/validation/isae-st2-modal-readiness-20261027/report.json'
MODAL_READINESS_SHA256 = 'c14e0cb1c3b4dcea029fedaf7f96343e302984c4f336f1c0624d26387731dee3'
MODAL_PREFLIGHT = 'docs/validation/isae-st2-modal-readiness-20261027/preflight.json'
MODAL_PREFLIGHT_SHA256 = '49fdadec7620368838a3185a780421a2e99e29f8a48a3ad39c46dbb3537ba6ed'
PROSPECTIVE_PROTOCOL = 'docs/validation/isae-st2-modal-readiness-20261027/prospective-protocol.json'
PROSPECTIVE_PROTOCOL_SHA256 = '6741d0522887862fc36e5dd226928dcfba67f69de5ac17e4ba232373791d00a9'
NOMINALS = (40, 80)
MEDIA = ('vacuum', 'still_air')
MODAL_PROTOCOL = dict(count=20, shift=[-.01, 0.], method='full_shift_invert', step=1e-5,
    rank_tolerance=1e-9, selected_positive_roots=7, positive_imaginary_threshold=0.)
GATES = dict(base=1e-9, pencil=1e-8, root_absolute=2e-8, root_relative=2e-8,
    neutral_relative=1e-8, mass_pairing=1e-8, mesh_relative=.001,
    relative_balance=1e-7, clamp=1e-10, restored_parity=2e-10)
MODAL_OPERATIONS = dict(cold_bridge_calls=1, equilibrium_solves=1, modal_solves=1, fresh_residuals=1, retries=0)
BLOCKED_OPERATIONS = dict(cold_bridge_calls=0, equilibrium_solves=0, modal_solves=0, fresh_residuals=0, retries=0)
FAMILY = '3 - Structure/CASE - ST2 Pazy_Wing'
MODEL_NAMES = (
    '01_Modal_Undeformed/Pazy_wing.asw',
    '02_Modal_Gravity/Pazy_wing.asw',
    '03_Static_Structural/Pazy_wing_bending_bench.asw',
    '03_Static_Structural/Pazy_wing_torsion_bench.asw',
    'Pazy_wing_bending_bench.asw', 'Pazy_wing_torsion_bench.asw')
STATIC_DRIVERS = ('03_Static_Structural/temp_analysis1.sh',
                  '03_Static_Structural/temp_analysis2.sh')
STATIC_MUTATORS = tuple('03_Static_Structural/'+name for name in
    ('change_mass.m', 'change_mass2.m', 'change_mass3.m',
     'tip_forces_analysis1.m', 'tip_forces_analysis2.m', 'tip_forces_analysis3.m'))
BOOKS = {
    '01_Modal_Undeformed/00_Comparisons/GFEM_vs_Beam_VS_ASWING.xlsx': ('I10', 11, 'I'),
    '02_Modal_Gravity/00_Comparisons/GFEM_vs_Beam.xlsx': ('G2', 3, 'G')}
BLOCKS = {
    'LITERAL_ATTACHMENT_OUTSIDE_DOMAIN':
        'Both original Weight anchors are t=.558 outside the literal [.0001,.55] beam domain. '
        'No source-supported attachment interpretation permits literal construction; no clamp or object deletion is authorized.',
    'SUMMARY_PAIRING_UNRESOLVED':
        'ASWING-labelled workbook frequencies have no exact generating model/settings or native-export branch pairing. '
        'Their stored-cell precision is separate from native printed complex eigenvalues.',
    'MODAL_SCOPE_REGISTERED_SEPARATELY':
        'Original null Weight records remain intact and inactive. This zero-target model inventory is covered by '
        'the separately registered conditional native modal jobs; it is not a separate solve or comparison pass.'}
CELL_PRECISION = ('Stored workbook XML token only; spreadsheet storage precision is not a recovered '
                  'ASWING print format or an established physical comparison gate.')
NATIVE_PRECISION = 'Original printed token half-last-place; no tolerance relaxation or coordinate fitting.'
QUALIFICATIONS = [
    'Registration preserves the complete native scope; only declared conditional modal workers can execute.',
    'All six literal models retain both Weight objects and their .558 anchors; .558 is not a decimal alias of .55.',
    'Native exports require all fourteen complex roots (28 components) and all 46 static rows (368 non-coordinate fields).',
    'The ten workbook frequency cells are separately qualified summaries, never substitutes for native complex targets.',
    'Modal folder names and matching basenames do not recover gravity, medium, saved base, mesh, shift or root selection.',
    'Both static drivers overwrite temp.txt after MATLAB changes Weight records. The retained3kg bending model is a candidate, not a proven generating-byte pair.',
    'Static local Euler twist keeps its original sign; no experimentally projected chord twist is substituted.',
    'Static cl is interval-derived with a final dummy; all-zero a_flap has no independently established nonzero semantics.',
    'Experimental77 static observations and Beam/GFEM UM/NAST or finite-element results are excluded from this ASWING target scope.',
    'No new missing kernel or physical tolerance is inferred from this registration.']
MODAL_QUALIFICATIONS = [
    'Both unchanged models use a stationary loaded equilibrium with explicit body gravity [0,0,-9.81], no FlightCondition and zero added loads. Upright does not mean zero gravity or forced jig geometry.',
    'Vacuum and still-air density 1.23 are separate predeclared conditional branches, never chosen by reference closeness.',
    'Nominal 40/80 cosine intervals plus the exact .52 property break are prospective meshes, not recovered historical forty-node arrays.',
    'The fixed local count-20 shift-invert survey uses shift [-.01,0], step 1e-5 and rank tolerance 1e-9 without retries or adaptive changes.',
    'The first seven retained positive-imaginary roots in ascending imaginary order map to the seven native rows conditionally. This is not verified historical branch identity or a globally lowest-mode claim.',
    'All returned roots, both complex components, negative partners, extras and vectors are saved. No nearest-target pairing, frequency-only replacement or real-part snapping is permitted.',
    'Physical near-neutral and pencil gates are distinct from exact decimal native intervals, including real-component half-widths down to 5E-22.',
    'Full A/M matrices, raw loaded-base restoration residual and requests/results are retained for a separate audit. No complete finite spectrum or full-family reproduction is claimed.']
UNKNOWN_MODAL = ['generating driver', 'saved operating base', 'gravity and medium',
                 'mesh', 'shift and selected-root count', 'physical branch mapping']
UNKNOWN_STATIC = ['unique generating model byte state', 'original attachment interpretation',
                  'exact nodes', 'startup/display settings', 'explicit operating constraints']
STATIC_UNITS = ('m', 'm', 'deg', 'N m', 'N m', 'N', 'dimensionless', 'unresolved display units')


def _require(ok, message):
    if not ok:
        raise ValueError(message)


def _pin(path):
    path = Path(path).resolve()
    raw = path.read_bytes()
    return dict(path=str(path), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def _kernel_pins(root):
    return [_pin(p) for p in sorted((root/'openswing').glob('*.py'))]


def _build_records(root, specs):
    # Every modal job in this registration describes the same production
    # sources. Read those once, then rehash the complete inventory before
    # returning. This cache is local to this call, never mtime-based or reused
    # by later registration/worker verification. Changes during registration
    # must reject the entire plan rather than leave jobs with mixed kernels.
    kernel_pins = _kernel_pins(root)
    records = [_make_record(root, spec, kernel_pins=kernel_pins) for spec in specs]
    _require(_kernel_pins(root) == kernel_pins,
             'ST2 production sources changed during registration.')
    return records


def _number(token, power10=0):
    _require(isinstance(token, str) and NUMBER.fullmatch(token) is not None, 'Invalid finite ST2 numeric token.')
    value = Decimal(token.replace('D', 'E').replace('d', 'e'))
    half = Decimal(5).scaleb(value.as_tuple().exponent-1)
    scale = Decimal(10)**power10
    values = [float(value), float(half), float(value*scale), float(half*scale)]
    _require(all(math.isfinite(v) for v in values) and values[1] > 0 and values[3] > 0,
             'Unrepresentable ST2 target precision.')
    return dict(expected_token=token, expected=values[2], tolerance=values[3],
                printed_value=values[0], printed_tolerance=values[1], power10=power10,
                exact_decimal_expected=str(value*scale), exact_decimal_tolerance=str(half*scale))


def decode_modal(text):
    lines = text.splitlines()
    _require(len(lines) >= 4 and lines[1].strip() ==
             '# Eigen value moduli to be divided by 2pi to get the frequency' and
             lines[2].split() == ['#', 'Op.Point', 'Eigenvalue'], 'ST2 modal header changed.')
    rows = []
    for line, raw in enumerate(lines[3:], 4):
        if not raw.strip():
            continue
        tokens = raw.split()
        _require(len(tokens) == 3 and tokens[0] == '1', 'ST2 modal row shape or operating point changed.')
        real, imaginary = [_number(token) for token in tokens[1:]]
        _require(imaginary['expected'] > 0, 'ST2 modal root must retain positive imaginary part.')
        rows.append(dict(line_number=line, row_number=len(rows)+1, raw_line=raw,
                         tokens=tokens, operating_point=1,
                         real=real, imaginary=imaginary,
                         frequency_modulus_Hz=math.hypot(real['expected'], imaginary['expected'])/(2*math.pi)))
    _require(len(rows) == 7, 'ST2 requires all seven original complex rows per export.')
    return rows


def decode_model(text):
    """Narrow literal-source audit, not a replacement for the ASW parser."""
    lines = text.splitlines()
    starts = [i for i, line in enumerate(lines) if line.strip().lower() == 'weight']
    _require(len(starts) == 1, 'ST2 Weight section changed.')
    start = starts[0]
    end = next(i for i in range(start+1, len(lines)) if lines[i].strip().lower() == 'end')
    scales = [i for i in range(start+1, end) if lines[i].lstrip().startswith('*')]
    _require(len(scales) == 1, 'ST2 Weight scaling changed.')
    scale_tokens = lines[scales[0]].lstrip()[1:].split()
    _require(len(scale_tokens) == 5, 'ST2 Weight scale width changed.')
    weights = []
    for i in range(start+1, end):
        raw = lines[i].strip()
        if not raw or raw.startswith(('#', '*')):
            continue
        tokens = raw.split()
        _require(len(tokens) == 6 and tokens[0] == '1', 'ST2 Weight row changed.')
        scaled = [Decimal(tokens[0])] + [Decimal(t)*Decimal(s) for t, s in zip(tokens[1:], scale_tokens)]
        weights.append(dict(line_number=i+1, tokens=tokens, scaled_values=list(map(float, scaled)),
                            exact_scaled_values=list(map(str, scaled))))
    headers = [i for i, line in enumerate(lines) if line.split()[:5] == ['t', 'x', 'z', 'y', 'chord']]
    _require(len(headers) == 1, 'ST2 beam main-table scope changed.')
    records = []
    for i in range(headers[0]+2, len(lines)):
        raw = lines[i].strip()
        if raw.split() and raw.split()[0] == 't':
            break
        if raw and not raw.startswith(('#', '*')):
            records.append(dict(line_number=i+1, tokens=raw.split()))
    domain = [min(Decimal(r['tokens'][0]) for r in records), max(Decimal(r['tokens'][0]) for r in records)]
    _require(len(weights) == 2 and all(Decimal(w['exact_scaled_values'][1]) == Decimal('.558') for w in weights)
             and domain == [Decimal('.0001'), Decimal('.55')], 'ST2 literal attachment blocker changed.')
    return dict(weight_scale_tokens=scale_tokens, weights=weights, beam_main_table_records=records,
                beam_parameter_domain=list(map(float, domain)), exact_beam_parameter_domain=list(map(str, domain)),
                all_zero_point_objects=all(w['scaled_values'][5] == 0 for w in weights),
                attachment_status='outside_literal_domain', construction_attempted=False)


def decode_workbook(path, name):
    _require(name in BOOKS, 'Unreviewed ST2 workbook.')
    ns = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
    with ZipFile(path) as archive:
        strings = [''.join(node.itertext()) for node in ET.fromstring(archive.read('xl/sharedStrings.xml')).findall('s:si', ns)]
        sheet = ET.fromstring(archive.read('xl/worksheets/sheet1.xml'))
    cells = {}
    for cell in sheet.findall('.//s:c', ns):
        node = cell.find('s:v', ns)
        if node is not None:
            token = node.text
            cells[cell.attrib['r']] = (token, strings[int(token)] if cell.attrib.get('t') == 's' else token)
    label, first, column = BOOKS[name]
    _require(cells[label][1] == 'ASWING', 'ST2 ASWING workbook column changed.')
    rows = []
    for row in range(first, first+5):
        cell = column+str(row)
        token, value = cells[cell]
        _require(token == value, 'ST2 workbook frequency must be an original numeric XML token.')
        rows.append(dict(name='cell:'+cell, **_number(token), source_line=row,
            source_column_1based=ord(column)-ord('A')+1, value_cell=cell,
            sheet_xml='xl/worksheets/sheet1.xml', ASWING_label_cell=label,
            B_mode_label=cells['B'+str(row)][1], D_adjacent_label=cells['D'+str(row)][1],
            units='Hz', precision_scope=CELL_PRECISION))
    _require([r['B_mode_label'] for r in rows] == ['OOP1', 'OOP2', 'T1', 'IP1', 'OOP3'] and
             [r['D_adjacent_label'] for r in rows] == ['OOP1', 'OOP2', 'T1', 'OOP3', 'IP1'],
             'ST2 conflicting workbook mode-label provenance changed.')
    return rows


def _specs():
    records = []
    for model in MODEL_NAMES[:2]:
        for medium in MEDIA:
            for nominal in NOMINALS:
                records.append(dict(id=f'ST-2:modal:{Path(model).parts[0]}:{medium}:m{nominal}',
                    target_kind='native_modal', model=model, table=model.replace('.asw', '.e00'),
                    medium=medium, nominal=nominal))
    records.append(dict(id='ST-2:native:03_Static_Structural/temp.txt', target_kind='native_static',
                        model=MODEL_NAMES[2], table='03_Static_Structural/temp.txt'))
    for book in BOOKS:
        records.append(dict(id='ST-2:workbook:'+book, target_kind='workbook_summary', model=None, table=book))
    for model in MODEL_NAMES:
        records.append(dict(id='ST-2:model:'+model, target_kind='model_inventory', model=model, table=None))
    return records


def _base(root):
    return Path(root).resolve()/'.reference/isae-validation'/REVISION/FAMILY


def _paths(root, spec):
    root = Path(root).resolve()
    base = _base(root)
    paths = [root/'scripts/isae_suite_st2.py', root/'scripts/isae_st2_archive.py',
             root/READINESS, base.parents[2]/'manifest.json', base/'README.txt']
    paths += [base/spec[k] for k in ('model', 'table') if spec[k] is not None]
    if spec['target_kind'] == 'native_static':
        paths += [base/name for name in (*MODEL_NAMES[2:], *STATIC_DRIVERS, *STATIC_MUTATORS)]
    if spec['model'] in MODEL_NAMES[:2]:
        paths += [root/name for name in (MODAL_READINESS, MODAL_PREFLIGHT, PROSPECTIVE_PROTOCOL)]
        paths += [root/'scripts/isae_suite_st2_modal.py']
    if spec['table'] is not None:
        folder = Path(spec['table']).parts[0]
        paths.append(base/folder/'README.txt')
    return sorted(set(paths))


def _static_observations(profile):
    observations = []
    for row in profile['rows']:
        for column, (name, units) in enumerate(zip(COLUMNS[1:], STATIC_UNITS), 1):
            field = row['fields'][name]
            observations.append(dict(name=f"row{row['row_index']:04d}:{name}",
                **_number(row['tokens'][column], field['power10']), quantity=name, units=units,
                source_line=row['line_number'], source_column_1based=column+1,
                coordinate_token=row['tokens'][0], coordinate_value=row['fields']['t']['value'],
                coordinate_tolerance=row['fields']['t']['tolerance'], precision_scope=NATIVE_PRECISION))
    return observations


def _modal_observations(rows):
    return [dict(name=f'row{ordinal:04d}:{component}', **row[component],
                 source_line=row['line_number'], source_column_1based=column,
                 source_character_1based=list(re.finditer(r'\S+', row['raw_line']))[column-1].start()+1,
                 raw_line=row['raw_line'], raw_tokens=row['tokens'], row_number=ordinal,
                 operating_point=row['operating_point'], units='1/s', precision_scope=NATIVE_PRECISION)
            for ordinal, row in enumerate(rows, 1)
            for component, column in (('real', 2), ('imaginary', 3))]


def _modal_setup(root, spec, *, kernel_pins=None):
    """Bind prospective settings to verified source/preflight bytes, without physics."""
    for name, expected in ((MODAL_READINESS, MODAL_READINESS_SHA256),
                           (MODAL_PREFLIGHT, MODAL_PREFLIGHT_SHA256),
                           (PROSPECTIVE_PROTOCOL, PROSPECTIVE_PROTOCOL_SHA256)):
        _require(_pin(root/name)['sha256'] == expected, 'ST2 modal source/prospective evidence changed.')
    audit = json.loads((root/MODAL_READINESS).read_bytes())
    preflight = json.loads((root/MODAL_PREFLIGHT).read_bytes())
    folder = Path(spec['model']).parts[0]
    source = _base(root)/spec['model'];raw = source.read_text()
    case = next(row for row in audit['cases'] if row['id'] == folder)
    for name in ('model', 'native_export'):
        actual = _pin(root/case[name]['path'])
        _require(all(actual[k] == case[name][k] for k in ('bytes', 'sha256')), 'ST2 modal source pairing changed.')
    expected_operator = 'drela-fixed-vacuum-v1' if spec['medium'] == 'vacuum' else 'drela-fixed-still-air-v1'
    evidence = next(row for row in preflight['cases'] if row['model'] == folder and
        row['nominal_intervals'] == spec['nominal'] and row['structural_operator'] == expected_operator)
    request = deepcopy(evidence['bridge_request'])
    _require(request['source'] == raw and evidence['nodes'] == spec['nominal']+2 and
        evidence['actual_intervals'] == spec['nominal']+1 and evidence['nfev'] == 0,
        'ST2 preflight source/mesh construction evidence changed.')
    # The preflight preserved API defaults; this protocol was independently
    # fixed before comparisons and intentionally replaces those defaults.
    request['modes'].update({key:deepcopy(MODAL_PROTOCOL[key]) for key in
        ('count', 'shift', 'method', 'step', 'rank_tolerance')})
    lines = raw.splitlines()
    sensors = [[float(token) for token in lines[number-1].split()] for number in case['source_lines']['sensor_rows']]
    model = decode_model(raw)
    _require(model['all_zero_point_objects'], 'ST2 modal Weight row became physically active.')
    weights = [row['scaled_values']+[0.]*11 for row in model['weights']]
    return dict(request=request, panels=deepcopy(request['panels']), source=str(source),
        medium=spec['medium'], density=None if spec['medium'] == 'vacuum' else 1.23,
        nominal=spec['nominal'], mesh=f"m{spec['nominal']}",
        coordinate_id=folder+':'+spec['medium'],
        settings=deepcopy(request['numerics']), modal_protocol=deepcopy(MODAL_PROTOCOL),
        numerical_gates=deepcopy(GATES), condition=None, gravity=[0.,0.,-9.81],
        continuation_steps=4, literal_model_sha256=case['model']['sha256'],
        literal_reference=[[.055,.1,.55],[0.,0.,0.],[0.,0.,0.],[0.,0.,0.]],
        literal_weight_rows=weights, literal_sensor_rows=sensors,
        mandatory_stations=[.0001,.52,.55], root_position=[0.,0.,0.], expected_real_mass=.373285,
        expected_elements=spec['nominal']+1, expected_nodes=spec['nominal']+2,
        reference_pairing=deepcopy(case), modal_readiness=_pin(root/MODAL_READINESS),
        preflight_evidence=_pin(root/MODAL_PREFLIGHT), prospective_protocol_source=_pin(root/PROSPECTIVE_PROTOCOL),
        source_mesh_scope='Original report forty nodes; prospective 40/80 cosine intervals plus .52 break. Historical node arrays unknown.',
        root_selection_scope='First seven retained positive-imaginary roots sorted ascending imaginary part; conditional local ordinal correspondence only.',
        complete_finite_spectrum=False, historical_settings_recovered=False,
        kernel_pins=_kernel_pins(root) if kernel_pins is None else deepcopy(kernel_pins))


def _make_record(root, spec, *, kernel_pins=None):
    root = Path(root).resolve()
    base = _base(root)
    kind = spec['target_kind']
    model = base/spec['model'] if spec['model'] else None
    table = base/spec['table'] if spec['table'] else None
    if spec['model'] in MODEL_NAMES[:2]:
        for name, sha in ((MODAL_READINESS,MODAL_READINESS_SHA256),
                          (MODAL_PREFLIGHT,MODAL_PREFLIGHT_SHA256),
                          (PROSPECTIVE_PROTOCOL,PROSPECTIVE_PROTOCOL_SHA256)):
            _require(_pin(root/name)['sha256'] == sha, 'ST2 modal immutable evidence changed.')
    blocker = ('SUMMARY_PAIRING_UNRESOLVED' if kind == 'workbook_summary' else
        'MODAL_SCOPE_REGISTERED_SEPARATELY' if kind == 'model_inventory' and spec['model'] in MODEL_NAMES[:2]
        else 'LITERAL_ATTACHMENT_OUTSIDE_DOMAIN')
    record = dict(id=spec['id'], case_id='ST-2', adapter='st2', target_kind=kind,
        execution_route='unsupported', blocker_code=blocker, unsupported_reason=BLOCKS[blocker],
        model_path=model.relative_to(root).as_posix() if model else None,
        table_path=table.relative_to(root).as_posix() if table else None,
        driver_paths=[(base/p).relative_to(root).as_posix() for p in STATIC_DRIVERS] if kind == 'native_static' else [],
        reference_rows=[], observations=[], required_components=[], grid_counts=[], settings=None,
        expected_operations=deepcopy(BLOCKED_OPERATIONS),
        source_pins=[_pin(p) for p in _paths(root, spec)], kernel_pins=[], suggested_cap_seconds=10,
        complete_family_reproduction=False, qualifications=list(QUALIFICATIONS),
        reference_scope='Original native ASWING exports and separately qualified workbook cells; blocked registration only.',
        pairing_status='not_established', literal_input_modified=False, model_record=None)
    if model:
        record['model_record'] = dict(source=_pin(model), **decode_model(model.read_text()))
    if kind == 'native_modal':
        record['reference_rows'] = decode_modal(table.read_text())
        record['observations'] = _modal_observations(record['reference_rows'])
        record['required_components'] = ['real', 'imaginary']
        record['unknown_setup'] = list(UNKNOWN_MODAL)
        record.update(_modal_setup(root, spec, kernel_pins=kernel_pins))
        record.update(execution_route='worker', blocker_code=None, unsupported_reason=None,
            expected_operations=deepcopy(MODAL_OPERATIONS), grid_counts=[spec['nominal']], suggested_cap_seconds=180,
            qualifications=list(QUALIFICATIONS)+list(MODAL_QUALIFICATIONS),
            pairing_status='conditional_same_folder_basename',
            pairing_evidence='Same-folder basename/title candidate; predeclared loaded base and both media do not recover historical setup.',
            reference_scope='All seven native complex roots, both components, under a declared conditional local ordinal correspondence.')
    elif kind == 'native_static':
        profile = decode_archive_profile(table.read_text())
        _require(len(profile['rows']) == 46 and profile['resultant_exponents'] == {"Mc'/10": 1, "Ms'/10": 0, 'Fn/10': 1},
                 'ST2 static row or resultant scaling scope changed.')
        record['target_profile'] = profile
        record['reference_rows'] = profile['rows']
        record['observations'] = _static_observations(profile)
        record['required_components'] = list(COLUMNS[1:])
        record['unknown_setup'] = list(UNKNOWN_STATIC)
        record['pairing_evidence'] = ('Retained3kg bending model gives31.45061475N including distributed mass, consistent '
                                      'with printed31.45N. Both bending/torsion drivers overwrite temp.txt; not a unique pair.')
        for name, model_name in zip(STATIC_DRIVERS, MODEL_NAMES[2:4]):
            lines = (base/name).read_text().splitlines()
            _require(lines[1].endswith('aswing '+Path(model_name).stem+' <<EOF') and
                     [s.strip() for s in lines[2:] if s.strip()] == ['plpa', 'g', 'oper', 'x', 'w', 'temp.txt', 'O', 'EOF'],
                     'ST2 shared-output driver declaration changed.')
    elif kind == 'workbook_summary':
        record['observations'] = decode_workbook(table, spec['table'])
        record['required_components'] = ['frequency_Hz']
        record['unknown_setup'] = list(UNKNOWN_MODAL)
        record['pairing_evidence'] = 'B and adjacent D labels disagree for the last two cells; no e00 branch mapping is assigned.'
    else:
        record['unknown_setup'] = (list(UNKNOWN_MODAL) if spec['model'] in MODEL_NAMES[:2] else
                                  ['literal attachment interpretation', 'exact generating output/setup pair'])
        record['pairing_evidence'] = 'Literal model inventory; no separate scalar denominator is invented.'
    record['expected_outputs'] = len(record['observations'])
    validate_record_contract(record)
    return record


def _validate_modal_setup(job, spec):
    nominal = spec['nominal'];vacuum = spec['medium'] == 'vacuum'
    operator = 'drela-fixed-vacuum-v1' if vacuum else 'drela-fixed-still-air-v1'
    settings = dict(beam_interpolation='drela-segspl-v1', structural_operator=operator)
    panels = dict(default=nominal, beams={'1':dict(count=nominal, spacing='cosine')})
    request = job.get('request', {})
    modes = dict(frame='fixed', count=20, shift=[-.01,0.], method='full_shift_invert', step=1e-5,
        rank_tolerance=1e-9, matrices=True, tolerance=GATES['base'], continuation_steps=4,
        position=[0.,0.,0.], attitude=[0.,0.,0.], vacuum=vacuum)
    if not vacuum:
        modes['quiescent_density'] = 1.23
    _require(job.get('execution_route') == 'worker' and job.get('blocker_code') is None and
        job.get('unsupported_reason') is None and job.get('settings') == settings and
        job.get('panels') == panels and job.get('grid_counts') == [nominal] and
        job.get('nominal') == nominal and job.get('medium') == spec['medium'] and
        job.get('density') == (None if vacuum else 1.23) and job.get('modal_protocol') == MODAL_PROTOCOL and
        job.get('numerical_gates') == GATES and job.get('expected_operations') == MODAL_OPERATIONS and
        job.get('condition') is None and job.get('gravity') == [0.,0.,-9.81] and
        job.get('expected_elements') == nominal+1 and job.get('expected_nodes') == nominal+2 and
        job.get('mandatory_stations') == [.0001,.52,.55] and job.get('expected_real_mass') == .373285 and
        job.get('root_position') == [0.,0.,0.] and job.get('continuation_steps') == 4 and
        job.get('complete_finite_spectrum') is False and job.get('historical_settings_recovered') is False and
        job.get('pairing_status') == 'conditional_same_folder_basename' and
        job.get('qualifications') == QUALIFICATIONS+MODAL_QUALIFICATIONS and
        job.get('suggested_cap_seconds') == 180,
        'ST2 prospective modal protocol, physical gate or claim changed.')
    _require(request == dict(action='modes', mode='modes', source=request.get('source'), panels=panels,
        condition=None, gravity=[0.,0.,-9.81], loads=[], numerics=settings, modes=modes),
        'ST2 literal modal bridge request changed.')
    source = request.get('source')
    _require(isinstance(source,str) and hashlib.sha256(source.encode()).hexdigest() == job.get('literal_model_sha256') and
        isinstance(job.get('kernel_pins'),list) and bool(job['kernel_pins']) and
        job.get('model_record',{}).get('all_zero_point_objects') is True,
        'ST2 literal modal source or kernel pins missing.')
    _require(job.get('literal_reference') == [[.055,.1,.55],[0.,0.,0.],[0.,0.,0.],[0.,0.,0.]] and
        job.get('literal_weight_rows') == [row['scaled_values']+[0.]*11 for row in job['model_record']['weights']] and
        len(job.get('literal_sensor_rows',[])) == 2,
        'ST2 literal modal reference/objects changed.')


def validate_record_contract(job):
    """Validate saved row/field scope without production imports or file reads."""
    if job.get('comparison_scope') == 'st2-mechanics':
        from scripts import isae_suite_st2_mechanics as mechanics
        mechanics.reference_contract(job)
        return True
    specs = [s for s in _specs() if s['id'] == job.get('id')]
    _require(len(specs) == 1, 'Unknown ST2 record.')
    spec = specs[0];kind = spec['target_kind']
    blocker = ('SUMMARY_PAIRING_UNRESOLVED' if kind == 'workbook_summary' else
        'MODAL_SCOPE_REGISTERED_SEPARATELY' if kind == 'model_inventory' and spec['model'] in MODEL_NAMES[:2]
        else 'LITERAL_ATTACHMENT_OUTSIDE_DOMAIN')
    _require(job.get('case_id') == 'ST-2' and job.get('adapter') == 'st2' and job.get('target_kind') == kind and
             job.get('complete_family_reproduction') is False and job.get('literal_input_modified') is False,
             'ST2 source identity/claim changed.')
    if kind == 'native_modal':
        _validate_modal_setup(job, spec)
    else:
        _require(job.get('execution_route') == 'unsupported' and job.get('blocker_code') == blocker and
             job.get('unsupported_reason') == BLOCKS[blocker] and job.get('settings') is None and
             job.get('grid_counts') == [] and job.get('kernel_pins') == [] and
             job.get('pairing_status') == 'not_established' and job.get('expected_operations') ==
             BLOCKED_OPERATIONS, 'ST2 blocked source contract changed.')
    if kind == 'native_modal':
        rows = job['reference_rows']
        text = '# Pazy\n# Eigen value moduli to be divided by 2pi to get the frequency\n# Op.Point Eigenvalue\n'
        rebuilt = decode_modal(text+'\n'.join(r['raw_line'] for r in rows))
        for expected, row in zip(rebuilt, rows):
            expected['line_number'] = row['line_number']
        _require(rows == rebuilt and job['required_components'] == ['real', 'imaginary'], 'ST2 modal target contract changed.')
        expected = _modal_observations(rows)
    elif kind == 'native_static':
        profile = job['target_profile']
        _require(profile['columns'] == list(COLUMNS) and len(profile['rows']) == 46 and
                 profile['resultant_exponents'] == {"Mc'/10": 1, "Ms'/10": 0, 'Fn/10': 1} and
                 job['reference_rows'] == profile['rows'] and job['required_components'] == list(COLUMNS[1:]),
                 'ST2 complete static field scope changed.')
        rebuilt = decode_archive_profile('1 0 1\n'+' '.join(COLUMNS)+'\n'+' '.join(['---']*9)+'\n'+
                                          '\n'.join(' '.join(r['tokens']) for r in profile['rows']))
        for decoded, row in zip(rebuilt['rows'], profile['rows']):
            decoded['line_number'] = row['line_number']
        _require(rebuilt['rows'] == profile['rows'] and rebuilt['values'] == profile['values'] and
                 rebuilt['physical_values'] == profile['physical_values'], 'ST2 static token/precision contract changed.')
        expected = _static_observations(profile)
    elif kind == 'workbook_summary':
        label, first, column = BOOKS[specs[0]['table']]
        expected = deepcopy(job['observations'])
        _require(len(expected) == 5 and job['reference_rows'] == [] and job['required_components'] == ['frequency_Hz'],
                 'ST2 summary cell scope changed.')
        for index, target in enumerate(expected):
            row = first+index
            _require(target['name'] == 'cell:'+column+str(row) and target['value_cell'] == column+str(row) and
                     target['ASWING_label_cell'] == label and target['source_line'] == row and
                     target['source_column_1based'] == ord(column)-ord('A')+1 and
                     target['units'] == 'Hz' and target['precision_scope'] == CELL_PRECISION and
                     target['sheet_xml'] == 'xl/worksheets/sheet1.xml' and
                     target['B_mode_label'] == ['OOP1', 'OOP2', 'T1', 'IP1', 'OOP3'][index] and
                     target['D_adjacent_label'] == ['OOP1', 'OOP2', 'T1', 'OOP3', 'IP1'][index] and
                     all(target[k] == v for k, v in _number(target['expected_token']).items()),
                     'ST2 workbook target/qualification contract changed.')
    else:
        _require(job['reference_rows'] == [] and job['required_components'] == [] and job['table_path'] is None and
                 isinstance(job['model_path'], str) and job.get('model_record') is not None,
                 'ST2 zero-target inventory scope changed.')
        expected = []
    _require(job['observations'] == expected and job['expected_outputs'] == len(expected),
             'ST2 observation target, precision, location or scalar count changed.')
    return True


def reference_contract(job):
    """Summary contract: checks must preserve every observation metadata field."""
    if job.get('comparison_scope') == 'st2-mechanics':
        from scripts import isae_suite_st2_mechanics as mechanics
        return {name: {k:v for k,v in row.items() if k != 'name'}
                for name,row in mechanics.reference_contract(job).items()}
    validate_record_contract(job)
    return {row['name']: {key: value for key, value in row.items() if key != 'name'}
            for row in job['observations']}


def build_jobs(root):
    root = Path(root).resolve()
    base = _base(root)
    manifest_path = base.parents[2]/'manifest.json'
    _require(_pin(manifest_path)['sha256'] == MANIFEST_SHA256, 'Original ST2 manifest changed.')
    _require(_pin(root/READINESS)['sha256'] == READINESS_SHA256, 'ST2 readiness evidence changed.')
    manifest = json.loads(manifest_path.read_text())
    readiness = json.loads((root/READINESS).read_text())
    _require(manifest['revision'] == REVISION and readiness['family'] == 'ST-2', 'ST2 archive revision changed.')
    files = sorted(p for p in base.rglob('*') if p.is_file())
    _require(len(files) == 146 and set(p.relative_to(base).as_posix() for p in base.rglob('*.asw')) == set(MODEL_NAMES) and
             set(p.relative_to(base).as_posix() for p in base.rglob('*.e00')) ==
             {name.replace('.asw', '.e00') for name in MODEL_NAMES[:2]}, 'ST2 original family inventory changed.')
    readiness_pins = {p['path']: p for p in readiness['source_pins']}
    for path in files:
        actual = _pin(path)
        original = manifest['files'][path.relative_to(base.parents[1]).as_posix()]
        audit = readiness_pins[path.relative_to(root).as_posix()]
        _require(all(actual[k] == original[k] == audit[k] for k in ('bytes', 'sha256')), 'ST2 original source changed: '+str(path))
    jobs = _build_records(root, _specs())
    _require(len(jobs) == 17 and sum(j['expected_outputs'] for j in jobs if j['target_kind'].startswith('native_')) == 480 and
             sum(j['expected_outputs'] for j in jobs if j['target_kind'] == 'workbook_summary') == 10 and
             sum(j['target_kind'] == 'model_inventory' for j in jobs) == 6 and
             len({(j['table_path'],o['name']) for j in jobs for o in j['observations']}) == 406,
             'ST2 family scalar/inventory accounting changed.')
    return jobs


def plan(root, *, comparison_scopes=()):
    if comparison_scopes:
        _require(list(comparison_scopes) == ['st2-mechanics'], 'Unknown ST2 mechanics selection.')
        from scripts import isae_suite_st2_mechanics as mechanics
        return mechanics.plan(root)
    return build_jobs(root)


def verify_reference_sources(root, job):
    """Bind all fields and source pairing qualifications to immutable originals."""
    if job.get('comparison_scope') == 'st2-mechanics':
        from scripts import isae_suite_st2_mechanics as mechanics
        return mechanics.verify_reference_sources(root, job)
    validate_record_contract(job)
    spec = next(s for s in _specs() if s['id'] == job['id'])
    canonical = _make_record(root, spec)
    _require(all(job.get(key) == value for key, value in canonical.items()), 'ST2 prepared record differs from original sources.')
    root = Path(root).resolve()
    manifest_path = _base(root).parents[2]/'manifest.json'
    _require(_pin(manifest_path)['sha256'] == MANIFEST_SHA256 and _pin(root/READINESS)['sha256'] == READINESS_SHA256,
             'ST2 immutable source evidence changed.')
    manifest = json.loads(manifest_path.read_text())
    cache = _base(root).parents[1]
    for item in canonical['source_pins']:
        path = Path(item['path'])
        if path.is_relative_to(cache):
            original = manifest['files'][path.relative_to(cache).as_posix()]
            _require(all(item[k] == original[k] for k in ('bytes', 'sha256')), 'ST2 source differs from immutable manifest.')
    return True


def validate_blocked(root, job):
    validate_record_contract(job)
    _require(job['execution_route'] == 'unsupported', 'ST2 executable modal job cannot use blocked validation.')
    spec = next(s for s in _specs() if s['id'] == job['id'])
    try:
        stable = job['source_pins'] == [_pin(path) for path in _paths(root, spec)]
    except OSError:
        stable = False
    if stable:
        verify_reference_sources(root, job)
    reason = job['unsupported_reason'] if stable else 'Pinned ST2 input/evidence changed; no comparison attempted.'
    checks = [dict(row, predicted=None, abs_error=None, passed=False, comparison='<=', unavailable_reason=reason)
              for row in job['observations']]
    return dict(id=job['id'], case_id='ST-2', adapter='st2', target_kind=job['target_kind'],
        status='unsupported' if stable else 'source_mismatch', numerical_pass=False, reference_match=False,
        reference_status='NOT_ESTABLISHED', reference_checks=checks, physical_calls=0,
        production_imports=0, equilibrium_solves=0, modal_solves=0, retries=0,
        operations=deepcopy(BLOCKED_OPERATIONS), physical_checks=[], kernel_pins_unchanged=True,
        blocker_code=job['blocker_code'], unsupported_reason=job['unsupported_reason'], source_pins_unchanged=stable,
        complete_family_reproduction=False, qualifications=job['qualifications'], reference_scope=job['reference_scope'])


def _finite(value):
    return isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value)


def _reference_checks(job, values=None, reason=None):
    values = values or {}
    result = []
    for row in job['observations']:
        prediction = values.get(row['name'])
        available = _finite(prediction)
        passed = (available and abs(Decimal(str(prediction))-Decimal(row['exact_decimal_expected'])) <=
                  Decimal(row['exact_decimal_tolerance']))
        result.append(dict(row,predicted=prediction if available else None,
            abs_error=abs(prediction-row['expected']) if available else None, passed=bool(passed),comparison='<=',
            **({} if available else dict(unavailable_reason=reason or 'Original component unavailable.'))))
    return result


def validate_physical_checks(job, checks):
    from scripts.isae_suite_st2_modal import validate_physical_checks as validate
    return validate(job,checks)


def validate_result_contract(job, result):
    """Reject fabricated execution, partial physical evidence and target changes."""
    if job.get('comparison_scope') == 'st2-mechanics':
        from scripts import isae_suite_st2_mechanics as mechanics
        return mechanics.validate_result_contract(job, result)
    contract = reference_contract(job)
    checks = result.get('reference_checks',[])
    complete = result.get('status') in ('computed','unsupported')
    _require(isinstance(checks,list) and len(checks) <= len(contract) and
        (not complete or len(checks) == len(contract)) and
        len({c.get('name') for c in checks}) == len(checks) and
        all(c.get('name') in contract and all(c.get(k)==v for k,v in contract[c['name']].items()) and
            c.get('comparison')=='<=' for c in checks), 'ST2 saved reference scope or token metadata changed.')
    _require(result.get('complete_family_reproduction') is not True and
        result.get('historical_settings_recovered') is not True and result.get('complete_finite_spectrum') is not True,
        'ST2 conditional scope cannot claim full reproduction or a complete spectrum.')
    if job['execution_route'] == 'unsupported':
        _require(result.get('status') != 'computed' and result.get('numerical_pass') is not True and
            result.get('numerical_passed') is not True and result.get('reference_match') is not True and
            all(c.get('predicted') is None and c.get('passed') is False for c in checks) and
            all(result.get(k,0)==0 for k in ('physical_calls','physical_solver_calls','production_imports',
                'equilibrium_solves','modal_solves','retries')) and
            (result.get('operations') == BLOCKED_OPERATIONS or not complete and result.get('operations') is None) and
            result.get('physical_checks',[]) == [], 'ST2 blocked scope claimed numerical execution or outputs.')
        if result.get('status') == 'unsupported':
            _require(result.get('source_pins_unchanged') is True, 'ST2 blocked registration lacks verified sources.')
    elif result.get('status') == 'computed':
        _require(result.get('numerical_pass') is True and result.get('source_pins_unchanged') is True and
            result.get('kernel_pins_unchanged') is True and result.get('physical_calls')==2 and
            result.get('operations')==MODAL_OPERATIONS and
            validate_physical_checks(job,result.get('physical_checks',[])), 'ST2 computed modal result lacks full physical evidence.')
        from scripts.isae_suite_st2_modal import spectrum_evidence, validate_modal_evidence
        evidence = result.get('modal_evidence',{})
        values = validate_modal_evidence(job,evidence)
        physical = {row['name']:row for row in result['physical_checks']}
        _require(physical['modal_spectrum']['evidence']==spectrum_evidence(evidence['eigenvalues']),
            'ST2 reported spectrum detached from physical modal evidence.')
        pencil = evidence.get('pencil_checks',{})
        _require(set(pencil)=={'right','left','mass_pairing'} and all(pencil[key]==physical[name]['entries']
            for key,name in (('right','modal_right_pencil'),('left','modal_left_pencil'),
                             ('mass_pairing','modal_mass_pairing'))),
            'ST2 reported pencil or normalization detached from physical modal evidence.')
        pairing = evidence.get('mass_pairing_matrix',{})
        _require(all(isinstance(pairing.get(part),list) and len(pairing[part])==20 and
            all(isinstance(row,list) and len(row)==20 and all(_finite(value) for value in row)
                for row in pairing[part]) for part in ('real','imag')),
            'ST2 full left/right mass-pairing matrix missing or malformed.')
        _require(all(abs(complex(pairing['real'][i][i],pairing['imag'][i][i])-complex(*entry['value']))<=GATES['mass_pairing']
            for i,entry in enumerate(pencil['mass_pairing'])),
            'ST2 full mass-pairing matrix detached from normalization evidence.')
        _require(len(values)==14 and all(_finite(c.get('predicted')) and c['predicted']==values.get(c['name'])
            for c in checks), 'ST2 predictions detached from retained ordered complex roots.')
        for check in checks:
            passed = abs(Decimal(str(check['predicted']))-Decimal(check['exact_decimal_expected'])) <= Decimal(check['exact_decimal_tolerance'])
            _require(check.get('abs_error') == abs(check['predicted']-check['expected']) and check.get('passed') is passed,
                'ST2 exact decimal reference comparison changed.')
        _require(result.get('reference_match') is all(c['passed'] for c in checks), 'ST2 full-job match flag changed.')
    else:
        _require(result.get('numerical_pass') is not True and result.get('numerical_passed') is not True and
            result.get('reference_match') is not True,
            'ST2 failed modal job claimed numerical success.')
    return True


def _write(path, data):
    Path(path).write_text(json.dumps(data,indent=2,allow_nan=False)+'\n')


def _stable(pins):
    try:
        return all(_pin(item['path'])==item for item in pins)
    except OSError:
        return False


def run(root, job):
    if job.get('comparison_scope') == 'st2-mechanics':
        from scripts import isae_suite_st2_mechanics as mechanics
        return mechanics.run(root, job)
    if job['execution_route'] == 'unsupported':
        return validate_blocked(root, job)
    root = Path(root).resolve();verify_reference_sources(root,job)
    from scripts.isae_suite_st2_modal import execute
    stage=Path(tempfile.mkdtemp(prefix='openswing-isae-st2-modal-'))
    _write(stage/'job.json',job)
    packet={};error=None
    try:
        packet=execute(root,job,stage)
    except Exception as exc:
        error=dict(type=type(exc).__name__,message=str(exc),traceback=traceback.format_exc())
        _write(stage/'exception.json',error)
    operations=json.loads((stage/'operations.json').read_bytes()) if (stage/'operations.json').exists() else deepcopy(BLOCKED_OPERATIONS)
    checks=_reference_checks(job,packet.get('values',{}),'Modal worker failed or component unavailable.')
    physical=packet.get('physical_checks',[])
    sources_ok=_stable(job['source_pins']);kernel_ok=_stable(job['kernel_pins']) and {
        p['path'] for p in job['kernel_pins']}=={str(p.resolve()) for p in (root/'openswing').glob('*.py')}
    numerical=bool(error is None and sources_ok and kernel_ok and operations==MODAL_OPERATIONS and
        physical and validate_physical_checks(job,physical) and all(c['predicted'] is not None for c in checks))
    result=dict(id=job['id'],case_id='ST-2',adapter='st2',target_kind='native_modal',
        status='computed' if numerical else 'numerical_failure',numerical_pass=numerical,
        reference_match=numerical and all(c['passed'] for c in checks),reference_checks=checks,
        physical_checks=physical,modal_evidence=packet.get('modal_evidence',{}),operations=operations,
        physical_calls=operations['cold_bridge_calls']+operations['fresh_residuals'],
        source_pins_unchanged=sources_ok,kernel_pins_unchanged=kernel_ok,error=error,
        complete_family_reproduction=False,historical_settings_recovered=False,complete_finite_spectrum=False,
        qualifications=job['qualifications'],unknown_setup=job['unknown_setup'],reference_scope=job['reference_scope'],
        artifact_directory=str(stage),artifact_files=[_pin(p) for p in sorted(stage.iterdir()) if p.is_file()])
    validate_result_contract(job,result);_write(stage/'adapter-result.json',result)
    return result


def mesh_diagnostics(jobs,results):
    if any(j.get('comparison_scope') == 'st2-mechanics' for j in jobs):
        from scripts import isae_suite_st2_mechanics as mechanics
        return mechanics.mesh_diagnostics(jobs, results)
    groups={}
    for job in jobs:
        if job.get('adapter')=='st2' and job.get('target_kind')=='native_modal':
            groups.setdefault(job['coordinate_id'],[]).append(job)
    records=[]
    for coordinate,pair in sorted(groups.items()):
        pair.sort(key=lambda row:row['nominal'])
        _require(len(pair)<=2 and len({j['nominal'] for j in pair})==len(pair),'ST2 duplicated declared mesh.')
        packets=[results.get(j['id'],{}) for j in pair]
        row=dict(coordinate_id=coordinate,jobs=[j['id'] for j in pair],medium=pair[0]['medium'],
            status='UNAVAILABLE',passed=None,acceptance_gate=None,channels={},
            scope='Declared 40/80 mesh sensitivity within one medium; no historical correspondence or global-spectrum claim.')
        if len(pair)==2 and all(p.get('status')=='computed' for p in packets):
            values=[{c['name']:c['predicted'] for c in p['reference_checks']} for p in packets]
            row['status']='COMPARED'
            for name in values[0]:
                a,b=(v[name] for v in values);difference=abs(b-a)
                row['channels'][name]=dict(coarse=a,fine=b,abs_change=difference,
                    relative_change=difference/abs(b) if b else (0. if difference==0 else None))
        records.append(row)
    return records
