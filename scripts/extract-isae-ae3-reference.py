#!/usr/bin/env python3
"""Catalog every retained AE-3 native export and embedded ASWING-labelled array.

Source-only, standard library only: no upstream script, solver, or model parser
is executed. All paths are ROOT-relative and every original file is checked
against the immutable upstream manifest before extraction.
"""
import argparse
from collections import Counter
import csv
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
REVISION = 'f62943df20e9e4d7d9f50e070477b22426b5f865'
MANIFEST_SHA256 = '813347a3bd9fcbd029a1ec86e0c3141f82422af26f33ebde7c2f732a16bf27f6'
FAMILY = '4 - Aeroelasticity/AE - Aeroelastic Cases/AE-3-S - Ailerons Reversal'
ORIGINAL = f'.reference/isae-validation/{REVISION}'
BASE = f'{ORIGINAL}/{FAMILY}'
MODELS = f'{BASE}/ASWING_Model/Straight_Wing'
CATALOG_PATH = 'docs/validation/isae-ae3-reference.json'
NOTES_PATH = 'docs/validation/isae-ae3-reference.md'
EXTRACTOR_PATH = 'scripts/extract-isae-ae3-reference.py'
NUMBER = r'[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[EeDd][-+]?\d+)?'
NUMERIC = re.compile(r'(?<![\w.])' + NUMBER + r'(?![\w.])')
SPEED_TOKENS = ('27.0934', '38.5020', '43.0429', '47.2340', '50.9245', '59.4556')
VARIANTS = ('20O', '40O', '60O', '80O', '95O')
EXPECTED_CATEGORIES = dict(base_coefficient=6, stability_derivative=36,
                           control_derivative=6, mass_inertia=33,
                           centroid=9, normalized_rate=6)


def require(ok, message):
    if not ok:
        raise ValueError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def pin(root, path):
    path = Path(path)
    if not path.is_absolute():
        path = root / path
    raw = path.read_bytes()
    return dict(path=path.relative_to(root).as_posix(), bytes=len(raw),
                sha256=hashlib.sha256(raw).hexdigest())


def lines_at(root, path):
    # splitlines removes only the line terminator; indentation, tabs, trailing
    # spaces, and original numeric spelling remain in raw_line.
    return (root / path).read_bytes().decode('utf-8').splitlines()


def scalar(name, token, line, start, raw, category, field_index=None):
    value = Decimal(token.replace('D', 'E').replace('d', 'e'))
    require(value.is_finite(), f'Nonfinite {name}')
    tolerance = Decimal(5).scaleb(value.as_tuple().exponent - 1)
    return dict(name=name, category=category, expected=float(value), expected_token=token,
                expected_decimal=str(value), tolerance=float(tolerance),
                tolerance_decimal=str(tolerance), negative_zero=value.is_zero() and value.is_signed(),
                source_line=line, source_column_1based=len(raw[:start].split()) + 1,
                source_character_1based=start + 1, source_field_1based=field_index,
                raw_line=raw, precision='Original literal half-last-place; no widened gate.')


def read_native(root, index):
    path = f'{MODELS}/Straight_20O.fmat_{index:03d}'
    lines = lines_at(root, path)
    require(len(lines) == 106 and 'Mass and Inertia tensors in body axes' in lines[3],
            f'Unexpected native export layout: {path}')
    require(re.search(rf'operating point\s+{index}\s', lines[6]), 'Operating point changed')
    require('Normalized forces in: Stability axes, x fwd, z down' in lines[66] and
            'Derivatives in: Stability axes, x fwd, z down' in lines[71], 'Axis header changed')
    outputs, context = [], []

    def select(line, pattern, names, category, dest=outputs):
        raw = lines[line - 1]
        match = re.search(pattern, raw)
        require(match is not None and len(match.groups()) == len(names),
                f'Unexpected fields {path}:{line}: {names}')
        for column, name in enumerate(names, 1):
            dest.append(scalar(name, match.group(column), line, match.start(column), raw, category, column))

    def numbers(line, names, category):
        raw = lines[line - 1]
        matches = list(NUMERIC.finditer(raw))
        require(len(matches) == len(names), f'Native column count changed: {path}:{line}')
        for column, (name, match) in enumerate(zip(names, matches), 1):
            outputs.append(scalar(name, match.group(), line, match.start(), raw, category, column))

    select(9, r'=\s*\(\s*(' + NUMBER + r')\s+(' + NUMBER + r')\s+(' + NUMBER + r')',
           ['mass_centroid_' + axis for axis in 'xyz'], 'centroid')
    select(11, r'=\s*(' + NUMBER + ')', ['density_ratio'], 'context', context)
    numbers(15, ['real_mass_xx', 'apparent_mass_xx', 'apparent_mass_xy', 'apparent_mass_xz'], 'mass_inertia')
    numbers(16, ['real_mass_yy', 'apparent_mass_yy', 'apparent_mass_yz'], 'mass_inertia')
    numbers(17, ['real_mass_zz', 'apparent_mass_zz'], 'mass_inertia')
    for line, origin in ((21, 'origin'), (27, 'centroid')):
        numbers(line, [f'{kind}_inertia_{origin}_{axis}' for kind in ('real', 'apparent')
                       for axis in ('xx', 'xy', 'xz')], 'mass_inertia')
        numbers(line + 1, [f'{kind}_inertia_{origin}_{axis}' for kind in ('real', 'apparent')
                           for axis in ('yy', 'yz')], 'mass_inertia')
        numbers(line + 2, [f'{kind}_inertia_{origin}_zz' for kind in ('real', 'apparent')], 'mass_inertia')
    select(36, r'Mach\s*=\s*(' + NUMBER + r').*=\s*(' + NUMBER + ')',
           ['Mach', 'PG_factor'], 'context', context)
    for line, name in ((38, 'reference_chord'), (39, 'reference_span'), (40, 'reference_area'),
                       (41, 'dynamic_pressure'), (42, 'speed'), (44, 'moment_reference_x'),
                       (45, 'moment_reference_y'), (46, 'moment_reference_z')):
        select(line, r'=\s*(' + NUMBER + ')', [name], 'context', context)
    for line, axis in zip((48, 49, 50), 'xyz'):
        select(line, r'=\s*(' + NUMBER + r').*=\s*(' + NUMBER + ')',
               [f'center_of_mass_{axis}', f'jig_center_of_mass_{axis}'], 'centroid')
    for line, names in ((53, ['body_speed', 'body_Wx']), (54, ['body_alpha_deg', 'body_Wy']),
                        (55, ['body_beta_deg', 'body_Wz'])):
        select(line, r'=\s*(' + NUMBER + r').*W[xyz]\s*=\s*(' + NUMBER + ')', names, 'context', context)
    for line, name in ((58, 'body_Wx_b_2V'), (59, 'body_Wy_c_2V'), (60, 'body_Wz_b_2V'),
                       (63, 'stability_p_b_2V'), (64, 'stability_q_c_2V'), (65, 'stability_r_b_2V')):
        select(line, r'=\s*(' + NUMBER + ')', [name], 'normalized_rate')
    for line, names in ((68, ['CX', 'Cl']), (69, ['CY', 'Cm']), (70, ['CL', 'Cn'])):
        select(line, names[0] + r'\s*=\s*(' + NUMBER + r').*' + names[1] + r'\s*=\s*(' + NUMBER + ')',
               names, 'base_coefficient')
    for first, suffixes in ((76, 'uab'), (86, 'pqr')):
        for offset, coeff in zip((0, 1, 2, 4, 5, 6), ('CX', 'CY', 'CL', 'Cl', 'Cm', 'Cn')):
            names = [coeff + suffix for suffix in suffixes]
            select(first + offset, r'.*'.join(re.escape(name) + r'\s*=\s*(' + NUMBER + ')'
                                             for name in names), names, 'stability_derivative')
    for line, coeff in zip((97, 98, 99, 102, 103, 104), ('CX', 'CY', 'CL', 'Cl', 'Cm', 'Cn')):
        select(line, re.escape(coeff) + r'dF1\s*=\s*(' + NUMBER + ')', [coeff + 'dF1'], 'control_derivative')
    require(Counter(row['category'] for row in outputs) == EXPECTED_CATEGORIES and len(context) == 17,
            'Native denominator changed')
    require(len({row['name'] for row in outputs + context}) == 113, 'Duplicate native field names')
    echoed = {row['name']: row for row in context}
    require(echoed['speed']['expected_token'] == SPEED_TOKENS[index - 1], 'Driver/native speed mismatch')
    require(all(echoed[name]['expected'] == 0 for name in
                ('Mach', 'body_alpha_deg', 'body_beta_deg', 'body_Wx', 'body_Wy', 'body_Wz')) and
            echoed['density_ratio']['expected'] == echoed['PG_factor']['expected'] == 1,
            'Native operating setup changed')
    q = Decimal(echoed['dynamic_pressure']['expected_token'])
    speed = Decimal(echoed['speed']['expected_token'])
    half_speed = Decimal(echoed['speed']['tolerance_decimal'])
    rho = Decimal('1.2256')
    q_low = rho * (speed - half_speed) ** 2 / 2
    q_high = rho * (speed + half_speed) ** 2 / 2
    half_q = Decimal(echoed['dynamic_pressure']['tolerance_decimal'])
    require(q - half_q <= q_high and q + half_q >= q_low, 'Printed density/speed/q intervals inconsistent')
    cells = {(row['source_line'], row['source_character_1based']): row for row in outputs + context}
    all_rows = []
    for line, raw in enumerate(lines, 1):
        numeric = []
        for match in NUMERIC.finditer(raw):
            classified = cells.get((line, match.start() + 1))
            numeric.append(dict(token=match.group(), source_character_1based=match.start() + 1,
                                role=classified['category'] if classified else 'header_unit_or_identifier',
                                name=classified['name'] if classified else None))
        all_rows.append(dict(line_number=line, raw_line=raw, numeric_tokens=numeric))
    return dict(id=f'Straight_20O-fmat-{index:03d}', operating_point=index, table_path=path,
                model_path=f'{MODELS}/Straight_20O.asw', driver_path=f'{MODELS}/Roll_rate.sh',
                reference_row=dict(row_number=index, source_line=7, raw_line=lines[6]),
                export_name=lines[33].strip(), observations=outputs, context=context, raw_lines=lines,
                rows=all_rows, condition=dict(speed=float(speed), alpha_deg=-0.0, beta_deg=0.0,
                    mach=0.0, density=1.2256, gravity=9.81, flap1=1.0, angular_rates_deg_s=[0.0]*3),
                reference=dict(area=.185, chord=.15, span=1.2192, moment_origin=[0.0]*3),
                pairing_status='BASENAME_DRIVER_SPEEDS_MATCH_WITH_UNRECOVERED_LEGACY_SETUP',
                pairing_qualifications=[
                    'Driver !!F1 1.0 applies to all six points; finite file control is +1, not zero. '
                    'The format permits any flap unit; degree calibration is an interpretation supported by the source report/postprocessor.',
                    'Native export name Mowe_temp differs from literal model Name; exact legacy build/model identity is not authenticated.',
                    'No NODE command or archived node arrays; any new comparison grid is a declared reconstruction.',
                    'Driver constraint commands % / 4 23 / P / d are retained; no hidden constraint defaults are inferred.',
                    'No derivative unit conversion, sign flip, density substitution, or experimental-area correction is applied.'])


def text_rows(root, path):
    return [dict(line_number=i, raw_line=line, tokens=line.split())
            for i, line in enumerate(lines_at(root, path), 1)]


def model_inventory(root):
    records = []
    for model in ('Roll',) + tuple('Straight_' + v for v in VARIANTS):
        path = f'{MODELS}/{model}.asw'
        lines = lines_at(root, path)
        blocks, block = [], None
        for row in text_rows(root, path):
            first = row['tokens'][0] if row['tokens'] else ''
            if first in ('Name', 'Unit', 'Constant', 'Reference', 'Ground', 'Weight', 'Beam'):
                block = dict(name=first, line_number=row['line_number'], rows=[])
                blocks.append(block)
            if block is not None:
                block['rows'].append(row)
                if first in ('End', 'E'):
                    block = None
        by_name = {block['name']: block for block in blocks}
        require(set(by_name) == {'Name', 'Unit', 'Constant', 'Reference', 'Ground', 'Weight', 'Beam'},
                'Literal model sections changed')
        constants = [row for row in by_name['Constant']['rows'] if row['tokens'] and NUMERIC.fullmatch(row['tokens'][0])]
        refs = [row for row in by_name['Reference']['rows'] if row['tokens'] and NUMERIC.fullmatch(row['tokens'][0])]
        weight_rows = [row for row in by_name['Weight']['rows'] if row['tokens'] and row['tokens'][0] == '1']
        weight_scale = next(row for row in by_name['Weight']['rows'] if row['tokens'] and row['tokens'][0] == '*')
        require(len(weight_rows) == 2 and weight_scale['tokens'][5] == '0.0', 'Null Weight records changed')
        control_header = next(i for i, line in enumerate(lines) if line.split() == ['t', 'dCLdF1', 'dCMdF1'])
        control_rows = [dict(line_number=i + 1, raw_line=lines[i], tokens=lines[i].split())
                        for i in range(control_header + 1, len(lines)) if lines[i].split() and
                        lines[i].split()[0] not in ('End', 'E')]
        records.append(dict(model_path=path, name=by_name['Name']['rows'][1]['raw_line'].strip(),
                            source_pin=pin(root, path), raw_lines=lines, blocks=blocks,
                            constants=constants, reference_rows=refs,
                            weight=dict(scale_row=weight_scale, rows=weight_rows, scaled_Mg=[0.0, 0.0],
                                        qualification='Both raw Mg=1 rows have literal Mg scale0; records are retained unchanged.'),
                            control=dict(header_line=control_header + 1, rows=control_rows,
                                         duplicate_knots_retained=True, coordinate_scale='0.6096',
                                         file_unit='arbitrary flap unit in ASWING format; degree calibration supported by report/postprocessor',
                                         side_sign='negative left, positive right'),
                            paired_native_exports=[f'Straight_20O-fmat-{i:03d}' for i in range(1, 7)]
                                if model == 'Straight_20O' else [],
                            qualification='Native six-state basename/driver pairing with legacy-setup qualifications.'
                                if model == 'Straight_20O' else
                                'No retained native fmat/operating export for this literal model; embedded arrays are separately qualified.'))
    return records


def literal_arrays(root, path):
    arrays = {}
    for line, raw in enumerate(lines_at(root, path), 1):
        match = re.fullmatch(r'\s*([A-Za-z]\w*)\s*=\s*\[([^\]]*)\]\s*;?\s*', raw)
        if match is None:
            continue
        body = match.group(2)
        tokens = list(NUMERIC.finditer(body))
        require(not NUMERIC.sub('', body).strip(' \t,;'), f'Nonliteral array {path}:{line}')
        values = [scalar(match.group(1), token.group(), line, match.start(2) + token.start(), raw,
                         'literal_array', i) for i, token in enumerate(tokens, 1)]
        require(match.group(1) not in arrays, 'Duplicate literal array assignment')
        arrays[match.group(1)] = dict(name=match.group(1), source_path=path, source_line=line,
                                    raw_line=raw, values=values)
    return arrays


def postprocessor(root):
    source, backup = f'{BASE}/Post_analysis.m', f'{BASE}/Post_analysis.asv'
    original, witness = literal_arrays(root, source), literal_arrays(root, backup)
    series = []
    for variant, count, roll_count, plotted in zip(VARIANTS, (8, 8, 9, 9, 9), (6, 6, 5, 5, 5), (5, 6, 3, 2, 2)):
        prefix = f'dCM_d_deltaF_ASW_{variant}'
        for kind, name in (('original_aswing_locked', prefix), ('modified_aswing_locked', prefix + '_mod'),
                           ('modified_aswing_roll', 'p' + variant)):
            item = original[name]
            require(len(item['values']) == (roll_count if kind.endswith('roll') else count), 'Array row count changed')
            require([v['expected_token'] for v in item['values']] ==
                    [v['expected_token'] for v in witness[name]['values']], 'Backup numeric witness differs')
            speeds = original[prefix + '_V']['values'] if not kind.endswith('roll') else []
            for row_number, value in enumerate(item['values'], 1):
                value.update(name=f'{name}[{row_number}]', category=kind, row_number=row_number)
            series.append(dict(id=name, variant=variant, kind=kind, source_path=source,
                               model_path=f'{MODELS}/Straight_{variant}.asw', values=item['values'], speeds=speeds,
                               witness=witness[name], status='BLOCKED_UNPAIRED_POSTPROCESSOR_VALUES',
                               plotted_rows=list(range(1, (roll_count if kind.endswith('roll') else plotted) + 1)),
                               qualification=(
                                   'Comment labels modified ASWING; p units, control/mount setup and producer unavailable. '
                                   'Speed expression uses experimental CSV pressure and rho1.292; b is undefined in this cleared script.'
                                   if kind.endswith('roll') else
                                   'Complete stored array, including unplotted rows. Plot label is dCl/d(delta_A) perdegree; '
                                   'native derivative/control-sign equivalence is unresolved. Density in postprocessing is1.292 '
                                   'versus literal/native1.2256; exact generating models/build/control amplitude are unpaired.')))
    scalar_assignments = []
    for path in (source, backup):
        for line, raw in enumerate(lines_at(root, path), 1):
            match = re.fullmatch(r'\s*([A-Za-z]\w*)\s*=\s*(' + NUMBER + r')\s*;?\s*', raw)
            if match:
                scalar_assignments.append(dict(source_path=path, **scalar(
                    match.group(1), match.group(2), line, match.start(2), raw,
                    'postprocessor_literal_or_derived_annotation')))
    return dict(series=series, original_arrays=list(original.values()), backup_arrays=list(witness.values()),
                scalar_assignments=scalar_assignments,
                raw_sources=[dict(path=path, rows=text_rows(root, path)) for path in (source, backup)],
                duplicate_witness_policy='Backup arrays are retained with source positions, not additional independent target slots.',
                reversal_policy='All signed rows retained; no zero-crossing fit or invented reversal-speed target.',
                known_postprocessing_issues=[
                    'rho=1.292 is distinct from native/literal1.2256; no substitution is performed.',
                    'b is used in modified roll helix formulas but has no assignment after clear all.',
                    'The 95O experimental fit assigns x=q80O; this is preserved, not executed or repaired.',
                    'The backup additionally stores q=[10 15 20 25 30 35 40], V_reversal=61.468 and err_V=0.89408; '
                    'these postprocessing annotations are retained separately, not promoted to native exported targets.'])


def ancillary_tables(root, file_paths):
    tables = []
    for path in file_paths:
        if path.endswith('.csv'):
            rows = []
            for number, raw in enumerate(lines_at(root, path), 1):
                fields = next(csv.reader([raw]))
                require(fields == raw.split(','), 'Unexpected CSV quoting: explicit source mapping required')
                numeric_cells, offset = [], 0
                for column, value in enumerate(fields, 1):
                    token = value.strip()
                    if NUMERIC.fullmatch(token):
                        numeric_cells.append(scalar(f'column_{column}', token, number,
                            offset + len(value) - len(value.lstrip()), raw, 'experimental_or_stiffness_input', column))
                    offset += len(value) + 1
                rows.append(dict(row_number=number, source_line=number, raw_line=raw, fields=fields,
                                 numeric_cells=numeric_cells))
            tables.append(dict(path=path, kind='experimental_digitization_or_stiffness_input', rows=rows,
                               native_aswing_target=False, all_empty_cells_retained=True))
        elif '/airfoil_analysis/' in path and path.endswith('.txt'):
            lines = lines_at(root, path)
            xfoil = 'Version 6.97' in '\n'.join(lines[:3])
            start = 12 if xfoil else 1
            names = ('alpha', 'CL', 'CD', 'CDp', 'CM', 'Top_Xtr', 'Bot_Xtr') if xfoil else ('x', 'y')
            rows = []
            for line, raw in enumerate(lines[start:], start + 1):
                if not raw.strip():
                    continue
                matches = list(NUMERIC.finditer(raw))
                require(len(matches) == len(names) and not NUMERIC.sub('', raw).strip(), 'Ancillary table layout changed')
                rows.append(dict(row_number=len(rows) + 1, source_line=line, raw_line=raw,
                                 values=[scalar(name, m.group(), line, m.start(), raw, 'xfoil_or_geometry_input', col)
                                         for col, (name, m) in enumerate(zip(names, matches), 1)]))
            tables.append(dict(path=path, kind='xfoil_section_polar' if xfoil else 'airfoil_coordinates',
                               raw_lines=lines, rows=rows, native_aswing_target=False))
    return tables


def validate_catalog(catalog):
    """Check field coverage and lossless token/position/precision reconstruction."""
    counter = Counter()
    checked = 0

    def verify_scalar(row):
        raw, token = row['raw_line'], row['expected_token']
        start = row['source_character_1based'] - 1
        require(raw[start:start + len(token)] == token, 'Numeric token position mismatch')
        rebuilt = scalar(row['name'], token, row['source_line'], start, raw,
                         row['category'], row['source_field_1based'])
        require(all(row.get(key) == value for key, value in rebuilt.items()), 'Numeric precision metadata mismatch')

    for record in catalog['native_exports']:
        counter.update(row['category'] for row in record['observations'])
        require(len(record['raw_lines']) == 106, 'Native raw row loss')
        for row in record['observations'] + record['context']:
            line = record['raw_lines'][row['source_line'] - 1]
            start = row['source_character_1based'] - 1
            token = row['expected_token']
            require(line == row['raw_line'] and line[start:start + len(token)] == token, 'Native token position mismatch')
            verify_scalar(row)
            checked += 1
        require(len({(row['source_line'], row['source_character_1based']) for row in
                     record['observations'] + record['context']}) == 113, 'Overlapping native fields')
    require(counter == Counter({key: value * 6 for key, value in EXPECTED_CATEGORIES.items()}), 'Native coverage mismatch')
    post = catalog['postprocessor']
    require(Counter({kind: sum(len(row['values']) for row in post['series'] if row['kind'] == kind)
                     for kind in ('original_aswing_locked', 'modified_aswing_locked', 'modified_aswing_roll')}) ==
            Counter(original_aswing_locked=43, modified_aswing_locked=43, modified_aswing_roll=27), 'Embedded coverage mismatch')
    for array in post['original_arrays'] + post['backup_arrays']:
        for row in array['values']:
            verify_scalar(row)
            checked += 1
    native_and_arrays = checked
    for row in post['scalar_assignments']:
        verify_scalar(row)
        checked += 1
    for table in catalog['ancillary_tables']:
        for row in table['rows']:
            for value in row.get('values', row.get('numeric_cells', [])):
                verify_scalar(value)
                require(value['raw_line'] == row['raw_line'], 'Ancillary source row mismatch')
                checked += 1
    for record in catalog['native_exports']:
        for row in record['rows']:
            expected = [(m.group(), m.start() + 1) for m in NUMERIC.finditer(row['raw_line'])]
            require([(v['token'], v['source_character_1based']) for v in row['numeric_tokens']] == expected,
                    'Raw native numeric ledger lost or changed a field')
    return dict(status='PASS_SOURCE_EXTRACTION_ONLY', native_output_cells=576, native_context_cells=102,
                native_raw_rows=636, native_category_counts=dict(sorted(counter.items())),
                embedded_original_values=43, embedded_modified_locked_values=43, embedded_modified_roll_values=27,
                checked_native_and_array_token_positions=native_and_arrays, all_checked_numeric_token_positions=checked,
                solver_calls=0, production_imports=0)


def build_catalog(root=ROOT):
    root = Path(root).resolve()
    manifest_path = '.reference/isae-validation/manifest.json'
    require(pin(root, manifest_path)['sha256'] == MANIFEST_SHA256, 'Upstream manifest changed')
    manifest = json.loads((root / manifest_path).read_bytes())
    require(manifest['revision'] == REVISION, 'Upstream revision changed')
    names = sorted(name for name in manifest['files'] if name.startswith(FAMILY + '/'))
    require(len(names) == 44, 'AE3 original inventory changed')
    source_pins = [pin(root, manifest_path), pin(root, EXTRACTOR_PATH)]
    for name in names:
        current = pin(root, f'{ORIGINAL}/{name}')
        expected = manifest['files'][name]
        require(all(current[key] == expected[key] for key in ('bytes', 'sha256')), f'Original source changed: {name}')
        source_pins.append(current)
    report_pdf = '5 - Technical Reports/Experimental_validation_of_ASWING_Part_4_Aeroelasticity_V4 .pdf'
    report = pin(root, f'{ORIGINAL}/{report_pdf}')
    require(all(report[key] == manifest['files'][report_pdf][key] for key in ('bytes', 'sha256')), 'Primary PDF changed')
    source_pins += [report, pin(root, '.reference/isae-validation/reports/Experimental_validation_of_ASWING_Part_4_Aeroelasticity_V4.txt'),
                    pin(root, '.reference/aswing_doc.txt')]
    driver_path = f'{MODELS}/Roll_rate.sh'
    driver_lines = [line.strip() for line in lines_at(root, driver_path)]
    require([line.split()[1] for line in driver_lines if line.startswith('!V ')] == list(SPEED_TOKENS) and
            driver_lines.count('+') == 5 and driver_lines.count('!!F1 1.0') == 1 and
            driver_lines.index('!!F1 1.0') > max(i for i, line in enumerate(driver_lines) if line.startswith('!V ')),
            'Native driver stack/control pairing changed')
    inventory = [dict(**pin(root, f'{ORIGINAL}/{name}'), role=(
        'native_export' if '.fmat_' in name else 'literal_model' if name.endswith('.asw') else
        'source_driver' if name.endswith('.sh') else 'postprocessor_witness' if name.endswith(('.m', '.asv')) else
        'experimental_or_section_input' if name.endswith(('.csv', '.txt')) else 'figure_or_ancillary_inventory')) for name in names]
    result = dict(schema_version=1, family_id='AE-3', status='SOURCE_CATALOG_NOT_NUMERICAL_VALIDATION',
                  revision=REVISION, source_pins=source_pins, source_inventory=inventory,
                  native_exports=[read_native(root, i) for i in range(1, 7)], model_inventory=model_inventory(root),
                  drivers=[dict(path=f'{ORIGINAL}/{name}', rows=text_rows(root, f'{ORIGINAL}/{name}'))
                           for name in names if name.endswith('.sh')],
                  postprocessor=postprocessor(root),
                  ancillary_tables=ancillary_tables(root, [f'{ORIGINAL}/{name}' for name in names]),
                  provenance=dict(original_native_exports=6, original_models=6, original_family_files=44,
                                  derivative_axes='Stability axes, x fwd, z down',
                                  coefficient_definitions=dict(CX='Fx/(q*S)', CY='Fy/(q*S)', CL='-Fz/(q*S)',
                                                               Cl='Mx/(q*S*b)', Cm='My/(q*S*c)', Cn='Mz/(q*S*b)'),
                                  control_parameter='F1=+1 original file control unit; original manual !! prefix applies to every existing stack point',
                                  control_unit_qualification='Manual1184 permits any flap unit; degree calibration is supported by the primary report/postprocessor, not encoded by the native format.',
                                  manual_stack_lines=[2174, 2204],
                                  manual_constraint_lines=[1945, 1995],
                                  constraint_command_semantics='% requests keyboard (column,row) toggles; P applies displayed settings to all points; D returns. The exact saved cell4,23 table meaning is unavailable.',
                                  original_executables='Driver names local AswingMAC_12_02_21 executable; binary/build not retained.',
                                  primary_report='Part4 §3.3 distinguishes straight-wing locked and free-roll tests, original ASWING and modified ASWING-m.',
                                  derivative_units='Original column labels u/V,alpha,beta,p,q,r,dFlap1 retained; no unstated angular/rate conversion.'),
                  blockers=[
                      'Native export model title Mowe_temp differs from literal model title; no archived build or exact serialized equilibrium.',
                      'No driver NODE setting or native node arrays; comparison meshes must be declared reconstructions.',
                      'Constraint table command 4 23 is preserved, but the saved table/defaults are absent.',
                      'Native derivatives require separately qualified source-coupled differentiation and exact output/unit mapping.',
                      'Apparent mass/inertia and deformed centroids require explicit comparison implementations; no zero-fill predictions.',
                      'Embedded ASWING, ASWING-m and modified-roll arrays lack independently paired full generating setups; retain all113 values blocked.',
                      'temp_analysis.sh uses single !F1 after nine Straight_60O points, unlike native driver !!F1; no native60O export.',
                      'Roll_analysis.sh specifies seven nonzero body roll rates with zero literal control slopes; no nativeRoll export.',
                      'Swept-wing experimental digitizations have no paired swept ASWING model or native result in this tree.',
                      'No independently exported reversal-speed scalar; do not fit or interpolate retained signs into a new target.'])
    result['extraction_verification'] = validate_catalog(result)
    result['counts'] = dict(native_exports=6, native_rows=636, native_output_cells=576, native_context_cells=102,
                          original_embedded_targets=43, modified_embedded_targets=43, modified_roll_targets=27,
                          unique_output_targets_before_mesh_expansion=689, literal_models=6,
                          original_files=44, ancillary_tables=len(result['ancillary_tables']))
    return result


def markdown(catalog):
    counts = catalog['extraction_verification']['native_category_counts']
    rows = '\n'.join(f'| {name} | {count} |' for name, count in counts.items())
    return f'''# AE-3 original source catalog

Source extraction only. No solver, production module, or upstream MATLAB/shell
script was executed. All 44 original family files match the immutable upstream
manifest. The catalog retains all 636 native export lines, 576 output cells,
102 echoed setup cells, and 113 embedded postprocessor values. This is coverage
evidence, not numerical or historical validation.

| Native output category | Cells across six exports |
| --- | ---: |
{rows}

The six `Straight_20O.fmat_001` through `_006` files pair by basename and speed
sequence with `Straight_20O.asw` and `Roll_rate.sh`. The driver builds six points
at 27.0934, 38.5020, 43.0429, 47.2340, 50.9245, and 59.4556 m/s, then applies `!!F1 1.0`
to every point. The pinned ASWING manual explicitly documents that `!!` applies
a parameter to all current stack points (lines 2192–2204). These are finite
F1=+1 file-control states. The manual permits arbitrary flap units; degree
calibration is supported by the report/postprocessor rather than intrinsically
encoded in the native format. No numeric unit conversion is applied. Their
base rolling coefficient differs from the local flap derivative; neither is
a zero-control result.

Each export gives Mach 0, PG factor 1, rho/rhoSL 1, alpha negative zero, beta 0,
and all body and normalized rates 0. The literal model specifies rhoSL 1.2256,
gravity 9.81, Sref 0.185, Cref 0.15, Bref 1.2192, and moment origin (0, 0, 0). Dynamic
pressure and speed printed intervals agree with that density. The force frame
is explicitly stability axes, x forward and z down: CX=Fx/qS, CY=Fy/qS, CL=-Fz/qS;
Cl=Mx/qSb, Cm=My/qSc, Cn=Mz/qSb. Derivative headings retain their original
u/V, alpha, beta, p, q, r, and dFlap1 labels without an inferred unit conversion.

The exact legacy reconstruction remains qualified: the export title is
`Mowe_temp`, whereas the literal model title is
`Ailereons_Reversal_Straight_wing`; no executable/build or serialized state
proves their identity. The driver has no NODE instruction, and the archived
node arrays are absent. Its `% / 4 23 / P / d` constraint commands are retained
without inventing unseen table defaults. Any new grids and numerical settings
must be declared reconstruction choices.

All six literal models remain in the inventory, including Roll and the five
straight-wing control spans. Duplicate control knots and both raw Weight rows
are preserved. The Weight Mg scale is exactly 0, so both physical weights are
zero without editing the original records. Literal control scales differ:
20O uses 0.0581/-0.0102, 40O uses 0.0686/-0.0107, and 60O/80O/95O use
0.0686/-0.0102; Roll uses zero control slopes. The primary report's prose
0.0581/-0.0107 does not replace any literal model values.

The complete `Post_analysis.m` arrays contain 43 ASWING-labelled locked values,
43 modified ASWING-m locked values, and 27 modified roll values. The locked
counts are 8/8/9/9/9 across 20O/40O/60O/80O/95O; the plots select only 18 rows
from each 43-value set. Every unplotted row, including negative reversal-branch
values, is retained. `Post_analysis.asv` provides duplicate numeric witnesses,
not additional independent target slots, plus a separate seven-value q vector
and literal annotations V_reversal=61.468 and err_V=0.89408. Those annotations
are not independently exported native ASWING scalars.
Native 576 + original 43 + modified 43 + modified roll 27 = 689 unique output
targets before any deliberate mesh expansion. The 102 native setup values,
speed arrays, experimental digitizations and XFOIL outputs are separate
source evidence and do not inflate that denominator.

The embedded arrays are blocked pending independent generating setups. Their
20O speed grid differs from the six native exports, and postprocessing uses
rho 1.292 instead of literal/native 1.2256. The plot's dCl/d(delta_A) label does
not establish equivalence to the native signed dF1 derivative. Modified roll
values lack independently recovered angular units, control/mount setup, and
producer; their speed formulas use experimental CSV pressures, while `b` has
no assignment after `clear all`. The 95O experimental fit uses q80O. These
issues are preserved rather than executed or repaired. No reversal speed is
invented by fitting or interpolating a sign change.

`temp_analysis.sh` creates nine 60O speeds and changes only the current point
with single `!F1 1.0`; it does not supply the native driver's `!!F1` evidence.
`Roll_analysis.sh` prescribes seven nonzero roll rates at 50.9314 m/s for Roll;
it has no retained native export and is not paired to the modified free-roll
arrays. All five CSV tables (including empty cells), four XFOIL polar tables,
airfoil coordinate rows, shell scripts, original model blocks, EPS and PNG
inventory are retained or pinned, with experimental/section-input provenance
distinct from native ASWING output. Swept-wing experimental data have no
paired swept model/export here.

Numeric fields retain original raw lines, tokens, signs of zero, line numbers,
whitespace-column and character positions, and Decimal half-last-place
precision. Unit multipliers, heading identifiers, and syntax numbers remain
in the raw numeric ledger without being labelled output targets. Extraction
verification checks every native and literal-array token position and the
complete category counts. No widened tolerances or fitted inputs are used.

Regenerate with `.venv/bin/python scripts/extract-isae-ae3-reference.py`;
verify the frozen output with the same command plus `--check`.
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--check', action='store_true', help='Check frozen files without writing')
    args = parser.parse_args()
    root = args.root.resolve()
    catalog = build_catalog(root)
    outputs = {CATALOG_PATH: json.dumps(catalog, indent=2, allow_nan=False) + '\n', NOTES_PATH: markdown(catalog)}
    for name, text in outputs.items():
        if args.check:
            require((root / name).read_text() == text, f'Frozen catalog differs: {name}')
        else:
            (root / name).write_text(text)
    print(json.dumps(dict(status='VERIFIED' if args.check else 'EXTRACTED', counts=catalog['counts'],
                          verification=catalog['extraction_verification'], outputs=[pin(root, name) for name in outputs]),
                     sort_keys=True, allow_nan=False))


if __name__ == '__main__':
    main()
