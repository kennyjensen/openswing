"""Original ST4 modal exports, with explicit unsupported archive entries.

Planning and blocked validation use only the standard library. Executable jobs
reuse the existing local Arnoldi verifier and its three declared meshes. No
archive, source model, production equation, helper or historical report changes.
"""
import ast
import csv
from copy import deepcopy
from decimal import Decimal
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import re
import tempfile
import time
import traceback
import xml.etree.ElementTree as ET
import zipfile

REVISION = 'f62943df20e9e4d7d9f50e070477b22426b5f865'
MANIFEST_SHA256 = '813347a3bd9fcbd029a1ec86e0c3141f82422af26f33ebde7c2f732a16bf27f6'
FAMILY = '3 - Structure/CASE - ST4 Concentrated weight'
HELPERS = ('verify-isae-st4-arnoldi.py', 'verify-isae-st4-source-modes.py')
GRIDS = (16, 32, 64)
POLICY = dict(beam_interpolation='drela-segspl-v1', structural_operator='drela-fixed-vacuum-v1')
VARIANTS = {'Weight7a': ('7a_b17', 6), 'Weight7c': ('7c_b21', 6),
            'Weight7d': ('7d_b48', 7), 'Weight7e': ('7e_b48', 6), 'Weight7f': ('7f_b48', 6)}
BLOCKS = {
    'MISSING_BEAM_END': 'Original W0M.asw has no closing Beam End. Current literal import rejects it; no repaired model is substituted.',
    'MISSING_EXACT_W0_PAIR': 'Retained driver invokes missing W0.asw and writes W0_vaccum.txt, not retained W0_eig_vaccum.txt. Exact model/output pairing is unresolved.',
    'COUPLED_MODAL_PROTOCOL_UNREVIEWED': 'These are air-flow operating-point eigenvalues, not the initial vacuum export. Source-aero modal setup and operating-point/branch pairing have no reviewed adapter; no vacuum substitution.',
    'NO_PAIRED_EXPORT': 'No direct modal export is paired with this original model. Aggregate ASWING summary cells remain unverified candidates; no mass position or property substitution is inferred.',
    'AGGREGATE_PAIRING_UNRESOLVED': 'Mixed experiment/ASWING summary has no exact generating-model/settings provenance per cell, and contains missing/zero/NC values and inconsistent rows. Only ASWING-labelled cells are inventoried; no branch or literal-model pairing is inferred.',
}
LIMITS = [
    'Original inputs and raw targets are unchanged. Experiments and fitted properties are excluded.',
    'Initial MODE sequence precedes OPER, selects anchored defaults, toggles F and requests16 near(-.1,300). Initial toggle state and startup sidecars are unavailable.',
    'Fixed vacuum, zero gravity/pose, and uniform16/32/64 are the existing declared comparison setup; historical mesh/gravity/initial settings are not proved.',
    'Compare ascending positive frequencies within the selected16 roots in original archive order. This is not a complete census or a certified global-lowest-root assignment.',
    'Tiny vacuum real components are retained as numerical residues, not fitted damping targets. All original rows, including the seventh Weight7d root, remain required.',
    'Three-grid mesh sensitivity uses the existing0.1% finer-denominator gate; printed precision and mesh agreement remain separate from numerical validity.',
    'No selected job establishes whole-family reproduction.',
]


def _pin(path):
    path = Path(path).resolve(); raw = path.read_bytes()
    return dict(path=str(path), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def _require(ok, message):
    if not ok:
        raise ValueError(message)


def _write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')


def decode_table(text, vacuum):
    lines = text.splitlines()
    _require(len(lines) >= 4 and lines[2].split() == ['#', 'Op.Point', 'Eigenvalue'], 'Unreviewed modal table header.')
    rows = []
    for line_number, line in enumerate(lines, 1):
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        tokens = line.split()
        _require(len(tokens) == 3 and tokens[0].isdigit(), 'Unreviewed original modal row.')
        values = [Decimal(x) for x in tokens[1:]]
        _require(all(x.is_finite() for x in values), 'Nonfinite original root.')
        halves = [Decimal(5)*Decimal(10)**(x.as_tuple().exponent-1) for x in values]
        rows.append(dict(line=line_number, raw_tokens=tokens, operating_point=int(tokens[0]),
            eigenvalue=list(map(float, values)), frequency_Hz=float(values[1])/(2*math.pi),
            half_printed_units=list(map(float, halves)), exact_decimal_values=list(map(str, values)),
            exact_decimal_half_units=list(map(str, halves))))
    _require(bool(rows), 'Empty original modal table.')
    if vacuum:
        _require(all(r['operating_point'] == 1 and r['eigenvalue'][1] > 0 for r in rows), 'Invalid vacuum ordinals.')
        _require(all(a['eigenvalue'][1] < b['eigenvalue'][1] for a,b in zip(rows, rows[1:])),
                 'Preserve original ascending ordinals; no target sorting.')
    return rows


def decode_driver(text):
    lines = [line.strip() for line in text.splitlines()]
    match = re.fullmatch(r'.*/aswing ([A-Za-z0-9_]+) <<EOF', lines[1])
    _require(match is not None, 'Unreviewed original ASWING invocation.')
    expected = ['mode', '%', 'a', 'd', 'f', 'n', '16', '-0.1 300', 'w', 'vaccum.txt', 'O']
    _require(lines[2:13] == expected, 'Initial vacuum command sequence changed.')
    _require(lines[18] == 'oper', 'Vacuum export must precede operating sweep.')
    _require(sum(x == 'vaccum.txt' for x in lines) == 1 and lines.count('eig.txt') == 1,
             'Ambiguous output writes.')
    return dict(model=match[1]+'.asw', vacuum_write_line=12, vacuum_sequence=lines[2:13],
                airflow_write_line=lines.index('eig.txt')+1,
                airflow_speed_commands=[x for x in lines if x.startswith('!V ')],
                mesh_command=None, startup_settings='unknown')


def _point_station(text):
    # A deliberately narrow source decoder, not another ASW parser. Exact
    # immutable fixtures all have two weights at one station and the same beam.
    lines = [x.strip() for x in text.splitlines() if x.strip() and not x.lstrip().startswith('#')]
    i = lines.index('Weight'); scale, left, right = [lines[i+k].split() for k in (1,2,3)]
    _require(scale == ['*','0.0254','1.0','1.','0.0254','9.81'] and left[0] == right[0] == '1', 'Unknown weight scaling.')
    _require(left[1] == right[1], 'Distinct point anchors need a new count derivation.')
    _require(lines.count('Beam 1') == 1 and lines[-1].lower() == 'end', 'Unsupported literal beam scope/end.')
    _require('0.0001' in text and '1.2192' in text, 'Original domain changed.')
    return Decimal(left[1])*Decimal(scale[1])


def _request(source, count):
    return dict(action='modes', mode='modes', source=source,
        panels=dict(default=count, beams={'1':dict(count=count, spacing='uniform')}),
        condition=None, numerics=deepcopy(POLICY),
        modes=dict(frame='fixed', vacuum=True, count=16, shift=[-.1,300.], method='full_shift_invert',
            step=1e-5, rank_tolerance=1e-9, matrices=True, position=[0.,0.,0.],
            attitude=[0.,0.,0.], gravity_magnitude=0.))


def _aggregate(path):
    """Retain ASWING-labelled summary cells; never turn their labels into pairs."""
    if path.suffix == '.csv':
        rows = list(csv.reader(path.read_text().splitlines(), delimiter=';'))
        cells = {i+1:{j:token for j,token in enumerate(row)} for i,row in enumerate(rows)}
    else:
        ns = {'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
        with zipfile.ZipFile(path) as archive:
            shared = ET.fromstring(archive.read('xl/sharedStrings.xml'))
            strings = [''.join(node.itertext()) for node in shared]
            sheet = ET.fromstring(archive.read('xl/worksheets/sheet1.xml'))
        cells = {}
        for row in sheet.findall('.//s:sheetData/s:row',ns):
            values = {}
            for cell in row.findall('s:c',ns):
                column = re.match(r'[A-Z]+',cell.attrib['r'])[0]; index = 0
                for char in column:index=index*26+ord(char)-64
                value = cell.find('s:v',ns); token = '' if value is None else value.text or ''
                if cell.attrib.get('t') == 's' and token:token=strings[int(token)]
                values[index-1] = token
            cells[int(row.attrib['r'])] = values
    header = cells[1]
    columns = {index:token.strip() for index,token in header.items() if token.strip().lower().endswith('_asw')}
    _require(set(columns.values()) == {'Vf_Asw','fb1_Asw','fb2_Asw','ft_Asw','ff_Asw'}, 'Aggregate ASWING headers changed.')
    targets = []
    for line,row in sorted(cells.items()):
        weight = row.get(0,'').strip().upper()
        if weight not in ('0','7A','7B','7C','7D','7E','7F'):
            continue
        for column,name in columns.items():
            token=row.get(column,'');value=None;tolerance=None
            try:
                number=Decimal(token.strip().replace(',','.'))
                if number.is_finite():
                    value=float(number);tolerance=float(Decimal(5)*Decimal(10)**(number.as_tuple().exponent-1))
            except Exception:
                pass
            targets.append(dict(name=f'row{line}:{name}',source_line=line,column_1based=column+1,
                weight_label=weight,position_token=row.get(1,''),raw_token=token,expected=value,tolerance=tolerance,
                units='m/s' if name == 'Vf_Asw' else 'Hz',
                precision_scope='Stored cell token only; spreadsheet storage precision is not a recovered ASWING print format.'))
    _require(bool(targets), 'No aggregate ASWING candidates.')
    return targets


def _specialized_source(root, name, row_count):
    """Only generalize ordinal count; every existing algebra/gate stays intact."""
    text = (root/'scripts'/HELPERS[0]).read_text()
    tree = ast.parse(text)
    node = next(x for x in tree.body if isinstance(x, ast.FunctionDef) and x.name == name)
    source = ast.get_source_segment(text, node)
    replacements = ({'len(positive) >= 6':f'len(positive) >= {row_count}',
                     'len(positive) < 6':f'len(positive) < {row_count}',
                     'positive[:6]':f'positive[:{row_count}]',
                     'per_component_total=6':f'per_component_total={row_count}'} if name == 'verify' else
                    {"len(cr['reference_comparison']) == len(fr['reference_comparison']) == 6":
                     f"len(cr['reference_comparison']) == len(fr['reference_comparison']) == {row_count}"})
    for before, after in replacements.items():
        _require(source.count(before) == 1, 'Reviewed helper anchor changed: '+before)
        source = source.replace(before, after)
    # Diagnostics must name the complete actual target count as well.
    source = source.replace('six ', f'{row_count} ')
    compile(source, '<st4-modal-count-specialization>', 'exec')
    return source


def _helper(root, row_count):
    path = root/'scripts'/HELPERS[0]
    spec = importlib.util.spec_from_file_location('_isae_suite_original_modes', path)
    helper = importlib.util.module_from_spec(spec); spec.loader.exec_module(helper)
    helper.ORDINAL_SCOPE = (f'First {row_count} ascending positive frequencies within the sixteen selected roots, '
                            f'compared to all {row_count} archived ordinals; not certified globally lowest modes.')
    for name in ('verify', 'compare_pair'):
        exec(compile(_specialized_source(root, name, row_count), str(path), 'exec'), helper.__dict__)
    return helper


def plan(root):
    root = Path(root).resolve(); cache = root/'.reference/isae-validation'/REVISION
    folder = cache/FAMILY; manifest_path = cache.parent/'manifest.json'
    _require(_pin(manifest_path)['sha256'] == MANIFEST_SHA256, 'Original manifest changed.')
    manifest = json.loads(manifest_path.read_text())
    _require(manifest['revision'] == REVISION, 'Original revision changed.')
    def original(path):
        pin = _pin(path); expected = manifest['files'][path.relative_to(cache).as_posix()]
        _require(all(pin[k] == expected[k] for k in ('bytes','sha256')), 'Original source changed: '+str(path))
        return pin
    common = [_pin(Path(__file__)), *[_pin(root/'scripts'/name) for name in HELPERS],
              _pin(manifest_path), _pin(root/'.reference/aswing_doc.txt'), _pin(root/'.reference/version_notes.txt')]
    kernels = [_pin(p) for p in sorted((root/'openswing').glob('*.py'))]
    jobs = []; paired_models = set(); seen_tables = set()
    for directory in [folder/'Simulation_files', *[folder/'Simulation_files'/name for name in VARIANTS]]:
        driver = directory/'Flutter_analysis.sh'; declaration = decode_driver(driver.read_text())
        model = directory/declaration['model']; paired_models.add(model)
        for vacuum in (True, False):
            table = directory/('vaccum.txt' if vacuum else 'eig.txt'); seen_tables.add(table)
            rows = decode_table(table.read_text(), vacuum)
            executable = vacuum and directory.name in VARIANTS
            if executable:
                expected_model, expected_rows = VARIANTS[directory.name]
                _require(model.stem == expected_model and len(rows) == expected_rows, 'Variant/row mapping changed.')
                point = _point_station(model.read_text())
            elif vacuum:
                _require(model.name == 'W0M.asw' and len(rows) == 7 and model.read_text().strip().endswith('#'),
                         'W0M missing-End blocker changed.')
            block = None if executable else 'MISSING_BEAM_END' if vacuum else 'COUPLED_MODAL_PROTOCOL_UNREVIEWED'
            inputs = [original(p) for p in (model,driver,table)] + common
            counts = GRIDS if executable else ()
            record = dict(id=f'ST-4:{directory.name}:{table.stem}', case_id='ST-4', adapter='modes',
                execution_route='local_vacuum' if executable else 'unsupported', blocker_code=block,
                unsupported_reason=BLOCKS.get(block), model_path=str(model), table_path=str(table), driver_path=str(driver),
                reference_rows=rows, required_components=['imaginary'] if vacuum else ['real','imaginary'],
                expected_outputs=len(rows)*(len(GRIDS) if executable else 1)*(1 if vacuum else 2),
                grid_counts=list(counts), expected_operations=dict(cold_bridge_calls=len(counts), additional_equilibrium_solves=0, retries=0),
                settings=dict(policy=deepcopy(POLICY), frame='fixed', vacuum=True, gravity_magnitude=0.,
                    method='full_shift_invert', selected_count=16, shift=[-.1,300.]) if executable else None,
                driver_declarations=declaration, source_pins=inputs, kernel_pins=kernels if executable else [],
                suggested_cap_seconds=180 if executable else 10, complete_family_reproduction=False,
                qualifications=LIMITS, reference_scope='Original ASWING eigenvalue exports; no experimental target.')
            if executable:
                record['grids'] = []
                for count in counts:
                    fraction = (point-Decimal('.0001'))/(Decimal('1.2192')-Decimal('.0001'))
                    extra = int(0 < fraction < 1 and fraction*count != int(fraction*count))
                    record['grids'].append(dict(count=count, expected_elements=count+extra,
                                                request=_request(model.read_text(), count)))
                record['verifier_sources'] = {name:_specialized_source(root,name,len(rows)) for name in ('verify','compare_pair')}
                record['mesh_gate'] = dict(required_pair=[32,64], other_pair=[16,32], relative_gate=.001)
            jobs.append(record)
    table = folder/'W0_eig_vaccum.txt'; seen_tables.add(table)
    rows = decode_table(table.read_text(), True); _require(len(rows) == 6, 'Root W0 table changed.')
    driver = folder/'vaccum.sh'; _require('aswing W0 <<EOF' in driver.read_text() and '\nW0_vaccum.txt\n' in driver.read_text()
                                        and not (folder/'W0.asw').exists(), 'Missing W0 pairing blocker changed.')
    jobs.append(dict(id='ST-4:W0-unpaired:vacuum',case_id='ST-4',adapter='modes',execution_route='unsupported',
        blocker_code='MISSING_EXACT_W0_PAIR',unsupported_reason=BLOCKS['MISSING_EXACT_W0_PAIR'],
        table_path=str(table),model_path=None,driver_path=str(driver),reference_rows=rows,
        required_components=['imaginary'],expected_outputs=6,source_pins=[original(table),original(driver)]+common,
        kernel_pins=[],expected_operations=dict(cold_bridge_calls=0),complete_family_reproduction=False,qualifications=LIMITS))
    for model in sorted(folder.rglob('*.asw')):
        if model in paired_models:
            continue
        jobs.append(dict(id='ST-4:unpaired-model:'+model.relative_to(folder).as_posix(),case_id='ST-4',adapter='modes',
            execution_route='unsupported',blocker_code='NO_PAIRED_EXPORT',unsupported_reason=BLOCKS['NO_PAIRED_EXPORT'],
            model_path=str(model),table_path=None,reference_rows=[],required_components=[],expected_outputs=0,
            source_pins=[original(model)]+common,kernel_pins=[],expected_operations=dict(cold_bridge_calls=0),
            complete_family_reproduction=False,qualifications=LIMITS))
    for name in ('Eigen_data_save.csv','Modal_analysis.xlsx'):
        path=folder/name;targets=_aggregate(path)
        jobs.append(dict(id='ST-4:aggregate:'+name,case_id='ST-4',adapter='modes',execution_route='unsupported',
            blocker_code='AGGREGATE_PAIRING_UNRESOLVED',unsupported_reason=BLOCKS['AGGREGATE_PAIRING_UNRESOLVED'],
            model_path=None,table_path=str(path),reference_rows=[],required_components=[],aggregate_targets=targets,
            expected_outputs=len(targets),source_pins=[original(path)]+common,kernel_pins=[],
            expected_operations=dict(cold_bridge_calls=0),complete_family_reproduction=False,qualifications=LIMITS))
    actual = {p for p in folder.rglob('*.txt') if 'Op.Point' in p.read_text()[:250]}
    _require(actual == seen_tables and len(actual) == 13, 'An original modal export is unaccounted.')
    _require(len(jobs) == 42 and len(paired_models) == 6 and len(list(folder.rglob('*.asw'))) == 33,
             'Original model/job accounting changed.')
    _require(sum(j['expected_outputs'] for j in jobs if 'aggregate_targets' not in j) == 3454,
             'Required native modal scalar accounting changed.')
    return jobs


def _stable(job):
    try:
        return all(_pin(p['path']) == p for p in job['source_pins']+job.get('kernel_pins',[]))
    except OSError:
        return False


def _reference_checks(job, packets=None, reason=None):
    if 'aggregate_targets' in job:
        return [dict(row,predicted=None,passed=False,abs_error=None,comparison='<=',
                     unavailable_reason=reason or job['unsupported_reason']) for row in job['aggregate_targets']]
    packets = packets or {}; checks = []
    for count in job.get('grid_counts') or [None]:
        compared = {r['ordinal']:r for r in packets.get(count,{}).get('reference_comparison',[])}
        for ordinal, row in enumerate(job['reference_rows'],1):
            actual = compared.get(ordinal)
            for component in job['required_components']:
                k = 0 if component == 'real' else 1
                expected, tolerance = row['eigenvalue'][k], row['half_printed_units'][k]
                predicted = actual['actual_eigenvalue'][k] if actual else None
                check = dict(name=f'n{count}:row{ordinal:04d}:{component}',predicted=predicted,expected=expected,
                    expected_token=row['raw_tokens'][k+1],tolerance=tolerance,comparison='<=',
                    abs_error=None if predicted is None else abs(predicted-expected),
                    passed=predicted is not None and abs(predicted-expected)<=tolerance,
                    source_line=row['line'],operating_point=row['operating_point'],units='1/s')
                if actual:
                    check['exact_decimal_passed'] = actual['printed_precision']['real' if k == 0 else 'imaginary']
                else:
                    check['unavailable_reason'] = reason or 'Required solve/comparison did not complete.'
                checks.append(check)
    return checks


def validate_blocked(root, job):
    _require(job.get('execution_route') == 'unsupported' and job.get('blocker_code') in BLOCKS
             and job.get('unsupported_reason') == BLOCKS[job['blocker_code']], 'Blocked-job reason changed.')
    stable = _stable(job)
    checks = _reference_checks(job, reason=job['unsupported_reason'] if stable else 'Pinned source changed.')
    _require(len(checks) == job['expected_outputs'], 'Blocked output accounting changed.')
    return dict(id=job['id'],case_id='ST-4',adapter='modes',status='unsupported' if stable else 'source_mismatch',
        numerical_pass=False,reference_match=False,reference_checks=checks,physical_calls=0,
        blocker_code=job['blocker_code'],unsupported_reason=job['unsupported_reason'],source_pins_unchanged=stable,
        complete_family_reproduction=False)


def _dispatch(request, progress):
    from openswing.bridge import dispatch
    return dispatch(request, progress=progress)


def run(root, job):
    root = Path(root).resolve()
    if job['execution_route'] == 'unsupported':
        return validate_blocked(root,job)
    _require(job['execution_route'] == 'local_vacuum' and job['grid_counts'] == list(GRIDS), 'Unreviewed modal route/grids.')
    stage = Path(tempfile.mkdtemp(prefix='openswing-isae-suite-modes-')); _write(stage/'job.json',job)
    helper = _helper(root,len(job['reference_rows'])); packets = {}; errors = []; calls = 0; mesh = []
    try:
        _require(_stable(job), 'Pinned input changed before execution.')
        for grid in job['grids']:
            count = grid['count']; out = stage/f'n{count}'; out.mkdir()
            source = Path(job['model_path']).read_text(); request = grid['request']
            _require(request == _request(source,count), 'Prepared modal setup changed.')
            plan = dict(kernel_pins={Path(p['path']).name:p['sha256'] for p in job['kernel_pins']},pins=job['source_pins'],
                nominal_intervals=count,expected_elements=grid['expected_elements'],reference_rows=job['reference_rows'],
                policy=POLICY,method=helper.METHOD,ordinal_scope=helper.ORDINAL_SCOPE)
            _write(out/'request.json',request);_write(out/'plan.json',plan)
            report = dict(checks=[],numerical_status='NOT_RUN',reference_status='NOT_ESTABLISHED');packets[count]=report
            start = time.monotonic()
            def progress(*values):
                with (out/'progress.jsonl').open('a') as stream:
                    stream.write(json.dumps(dict(seconds=time.monotonic()-start,progress=values),default=str)+'\n')
            try:
                calls += 1; result = _dispatch(request,progress);_write(out/'result.json',result)
                helper.verify(result,plan,report)
                report['checks'].append(dict(name='frozen input pins retained',passed=_stable(job)))
                precision = _reference_checks(dict(job,grid_counts=[count]),{count:report})
                report['checks'].append(dict(name='binary and exact decimal precision accounting consistent',
                    passed=all(c['passed'] == c['exact_decimal_passed'] for c in precision)))
                passed = bool(report['checks']) and all(c['passed'] for c in report['checks'])
                report['numerical_status'] = 'PASS' if passed else 'FAIL'
                _require(passed,'Modal numerical check failed; stop before another grid.')
            except Exception as exc:
                report['numerical_status']='FAIL';report['error']=dict(type=type(exc).__name__,message=str(exc),traceback=traceback.format_exc())
                raise
            finally:
                report['seconds']=time.monotonic()-start;_write(out/'report.json',report)
        for coarse,fine in zip(GRIDS,GRIDS[1:]):
            output=stage/f'mesh-{coarse}-{fine}';output.mkdir()
            mesh.append(helper.compare_pair(stage/f'n{coarse}',stage/f'n{fine}',output))
    except Exception as exc:
        errors.append(dict(type=type(exc).__name__,message=str(exc),traceback=traceback.format_exc()))
    checks = _reference_checks(job,packets);stable = _stable(job)
    numerical = not errors and stable and len(packets)==3 and all(r['numerical_status']=='PASS' for r in packets.values())
    result = dict(id=job['id'],case_id='ST-4',adapter='modes',status='computed' if numerical else 'numerical_failure',
        numerical_pass=numerical,reference_match=numerical and all(c['passed'] for c in checks),reference_checks=checks,
        physical_calls=calls,additional_equilibrium_solves=0,retries=0,errors=errors,source_pins_unchanged=stable,
        numerical_reports=packets,mesh_reports=mesh,mesh_gates_pass=bool(mesh) and mesh[-1]['numerical_status']=='PASS',
        complete_family_reproduction=False,reference_status='NOT_ESTABLISHED',qualifications=job['qualifications'],
        artifact_directory=str(stage),artifact_files=[_pin(p) for p in sorted(stage.rglob('*')) if p.is_file()])
    _write(stage/'adapter-result.json',result)
    return result
