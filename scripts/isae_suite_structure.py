"""Original static snapshots using the existing full-row verifiers.

Planning imports only stdlib helpers. Each job retains all three declared grids,
one cold solve and one fresh restoration per grid, every original output row,
and the existing numerical/mesh/printed-precision rules. Recovery mathematics
is reused from the reviewed verifiers, never reconstructed in this adapter.
"""
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import re
import sys
import tempfile
import traceback
import zipfile


TARGET_MARKER = '/__isae_suite_structure_target__/target.json'
CASES = ('st3-m15_0', 'st5-20lb_80_20', 'st5-20lb_90_10', 'st5-30lb_90_10',
         'st5-30lb_80_20')
ROLLER_CASES = tuple('st5-roller-'+s for s in ('20lb_80_20', '20lb_90_10', '30lb_80_20', '30lb_90_10'))
FORWARD_CASES = tuple('st5-forward-'+s for s in ('cosine_20lb', 'cosine_30lb', 'elliptical_20lb', 'elliptical_30lb'))
ELLIPTICAL_CASES = tuple('st5-elliptical-'+s for s in ('20lb_80_20', '20lb_90_10', '30lb_80_20', '30lb_90_10'))
CASES += ROLLER_CASES + FORWARD_CASES + ELLIPTICAL_CASES
REVISION = 'f62943df20e9e4d7d9f50e070477b22426b5f865'
MANIFEST_SHA256 = '813347a3bd9fcbd029a1ec86e0c3141f82422af26f33ebde7c2f732a16bf27f6'
ST5_RELATIVE = Path('3 - Structure/CASE - ST5 Joined Wing/Rigid_Joint')
ST5_ORIGINAL = 'JW_1_30lb_80_20'


def _read(path):
    return json.loads(Path(path).read_text())


def _pin(path):
    path = Path(path).resolve()
    raw = path.read_bytes()
    return dict(path=str(path), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def _require(ok, message):
    if not ok:
        raise ValueError(message)


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def decode_st5_original(root):
    """Decode all 28 original columns; retain source diagnostics even if failed.

    The existing stdlib decoder supplies per-file exponents, literal geometry,
    sided roots and shell arithmetic. A diagnostic mismatch is evidence, not a
    reason to alter the original token, its precision or the model.
    """
    root = Path(root).resolve()
    manifest_path = root/'.reference/isae-validation/manifest.json'
    _require(_pin(manifest_path)['sha256'] == MANIFEST_SHA256, 'ST5 archive manifest changed.')
    manifest = _read(manifest_path)
    _require(manifest['revision'] == REVISION, 'ST5 archive revision changed.')
    base = root/'.reference/isae-validation'/REVISION/ST5_RELATIVE
    helper_path = root/'scripts/extract-isae-st5-load-cases.py'
    helper = _load(helper_path, '_suite_st5_original_decoder')
    names = ([ST5_ORIGINAL+suffix for suffix in ('.asw', '.sh', '.txt', '.mat')]
             + [helper.BASELINE+suffix for suffix in ('.asw', '.sh', '.txt')]
             + ['JW_1_30lb_90_10.txt'])
    original_pins = []
    for name in names:
        actual = _pin(base/name)
        expected = manifest['files'][str(ST5_RELATIVE/name)]
        _require(all(actual[key] == expected[key] for key in ('bytes', 'sha256')),
                 'Original ST5 input/export changed: '+name)
        original_pins.append(actual)
    units_path = root/'docs/validation/isae-st5-reference-target.json'
    old = _read(units_path)
    columns = [dict(index0=i, index1=i+1, name=name, physical_unit=old['columns'][i]['physical_unit'],
        location='coordinate' if i == 0 else 'nodal derived shell' if i in (19, 20) else
        'following interval; final dummy' if i >= 21 else 'nodal') for i, name in enumerate(helper.NAMES)]
    target = helper.build_case(base, ST5_ORIGINAL,
                              helper.observations(base/(helper.BASELINE+'.txt')), columns)
    _require([b['row_count'] for b in target['beams']] == [44, 36]
             and len(columns) == 28, 'Original ST5 full table is incomplete.')
    echo = helper.observations(base/'JW_1_30lb_90_10.txt')
    same_echo = all([r['raw_tokens'][j] for r in beam['rows']] ==
                    [r['raw_tokens'][j] for r in reference['rows']]
                    for beam, reference in zip(target['beams'], echo) for j in (21, 23))
    _require(same_echo, 'ST5 endpoint-value display evidence changed.')
    target['input_echo_evidence'] = dict(reference=original_pins[-1], columns=['chord', 'cm'],
        matched_original_tokens=160, rule='Endpoint-value average inherited from the reviewed load-case verifier; identical original echo tokens, not recovered exporter source.')
    target['decoder_dependencies'] = [_pin(manifest_path), _pin(helper_path), _pin(units_path)] + original_pins
    target['uncertainties'] = [
        'The original has two retained failed source arithmetic diagnostics; FAIL_RETAINED is not a source-audit pass. Neither failure changes the replay targets or numerical gates.',
        'Forward root f_reac differs from literal signed weight outside its original half-last-place. Its exporter law remains unsupported; retain the scalar-weight diagnostic separately.',
        'Rear row12 tau does not overlap the propagated original printing interval. Keep its exact original target and strict precision, without a fitted correction.',
        'Interior unrounded historical stations are unavailable. Use printed centers and exact literal anchors, retaining both. This does not prove historical node-array equivalence.',
        'Positive forward joint prints2.000999 versus literal2.001. Preserve both; never enlarge output intervals or overwrite the original coordinate.',
        'Duplicate rows retain incoming/outgoing traces and zero-width display intervals; no historical zero-length computational element is inferred.',
        'Selective force/moment/strain/stress scaling uses each beam/file exponents and independent geometry, body-origin root balance and shell evidence. All-zero channels do not establish nonzero-rate scaling.',
        'eps/tau remain nodal including the last rear row. Final seven display columns use following-interval/final-dummy conventions.',
        'chord/Cm use the reviewed endpoint-value average, supported by160 identical original echo tokens in30lb90/10. f_reac remains an unresolved display diagnostic.',
        'Global traction sums use the body origin; Xmom is a coefficient reference. Tiny printed residual components are not loads to fit.',
        'drela-segspl-v1 and drela-steady-section-v1 are explicit current policies. The original binary, startup settings and unrounded mesh are unavailable.',
        'Literal forward/rear Dmg multipliers are-24/-6 and rear mg is1.1699. Preserve these original values despite the inconsistent90/10 model comment.',
    ]
    target['proposed_comparison'] = dict(
        policy=dict(beam_interpolation='drela-segspl-v1', structural_operator='drela-steady-section-v1'),
        structural_indices0=helper.STRUCTURAL, structural_values=1120,
        conditional_zero_indices0=helper.CONDITIONAL, conditional_zero_values=800,
        input_echo_indices0=[21, 23], input_echo_values=160,
        scalar_weight_display_index0=25, scalar_weight_values=80,
        coordinate_index0=0, coordinate_values=80, all_exported_tokens=2240,
        reference_gate='Original half-last-place intervals per column/beam; no tolerance relaxation or fitted data.',
        unsupported_fields={'f_reac': 'Exporter law unresolved; scalar signed-weight values are diagnostics, not validated reaction-force outputs.'},
        global_scope='Retain original headers; root force and moment balance uses body origin. No-flow conditional zeros do not establish aerodynamic validation.')
    return target


def decode_st5_variant(root, case):
    """Decode original roller, forward-only and elliptical-load snapshots."""
    root = Path(root).resolve()
    _require(case in ROLLER_CASES + FORWARD_CASES + ELLIPTICAL_CASES, 'Unknown structural variant.')
    manifest_path = root/'.reference/isae-validation/manifest.json'
    _require(_pin(manifest_path)['sha256'] == MANIFEST_SHA256, 'ST5 archive manifest changed.')
    manifest = _read(manifest_path)
    _require(manifest['revision'] == REVISION, 'ST5 archive revision changed.')
    units_path = root/'docs/validation/isae-st5-reference-target.json'
    names = ['verify-isae-st5-roller.py', 'verify-isae-st5-forward.py',
             'extract-isae-st5-load-cases.py', 'assess-isae-st5-roller.py']
    extra_dependencies = []
    if case in ELLIPTICAL_CASES:
        helper = _load(root/'scripts'/names[2], '_suite_elliptical_decoder')
        joint_helper = _load(root/'scripts'/names[0], '_suite_elliptical_joints')
        base = root/'.reference/isae-validation'/REVISION/ST5_RELATIVE.parent/'Elliptical_Loading'
        original = 'JW_1_'+case.removeprefix('st5-elliptical-')
        # Verify the selected original and the literal within-folder baseline.
        for name in dict.fromkeys((original, helper.BASELINE)):
            for suffix in ('.asw', '.sh', '.txt', '.mat'):
                path = base/(name+suffix)
                actual = _pin(path)
                expected = manifest['files'][str(path.relative_to(root/'.reference/isae-validation'/REVISION))]
                _require(all(actual[k] == expected[k] for k in ('bytes','sha256')), 'Original elliptical ST5 source changed: '+str(path))
                extra_dependencies.append(actual)
        units = _read(units_path)['columns']
        columns = [dict(index0=i, name=n, physical_unit=units[i]['physical_unit']) for i,n in enumerate(helper.NAMES)]
        changes = set() if original == helper.BASELINE else {(1,'Dmg'),(2,'Dmg')}
        target = helper.build_case(base, original, helper.observations(base/(helper.BASELINE+'.txt')),
                                   columns, expected_load_changes=changes)
        _require([b['row_count'] for b in target['beams']] == [44,36], 'Elliptical ST5 table layout changed.')
        joints = joint_helper.joint_rows((base/(original+'.asw')).read_text())
        _require(joints == [[1.,2.,2.001,2.001],[1.,2.,-2.001,-2.001]], 'Elliptical ST5 rigid joints changed.')
        _require('Aswing_R_5_92/bin/aswing' in target['driver_lines'][0], 'Elliptical ST5 driver changed.')
        header = '\n'.join(target['header_lines'])
        for label in ('Velocity','Alpha','Beta','Heading','Elev.','Bank','Ux','Uy','Uz','Wx','Wy','Wz',
                      'Udotx','Udoty','Udotz','Wdotx','Wdoty','Wdotz'):
            value = re.search(r'(?<!\w)'+re.escape(label)+r'\s*:\s*([-+\d.Ee]+)', header)
            _require(value is not None and float(value.group(1)) == 0., 'Nonzero elliptical ST5 motion/flow: '+label)
        target['joint_rows'] = joints
        target['source_decoder_diagnostics'] = target['checks']
        target['uncertainties'] = [
            'Exact original models, 25-point elliptical load tables and rear mg multiplier1.1699 are retained; no filename-based normalization.',
            'Original source arithmetic discrepancies are retained in checks/status and never repair a target or widen its printed interval.',
            'The within-folder20lb80/20 baseline is identical to itself; other elliptical snapshots change only the two Dmg multipliers.',
            'No original unrounded node arrays or startup settings are available. Printed centers and exact literal anchors define prospective three-grid comparisons.',
            'Selective export scaling has independent root-balance, geometry and shell evidence; historical exporter source is unavailable.',
            'All80rows/27outputs are required:14structural,10conditional zero,2input echo,1unresolved f_reac per row.',
            'Chord/Cm endpoint-value averaging is an inherited conditional display hypothesis; f_reac remains unresolved.',
            'Default type0 joints match translation and rotation. A small equilibrium residual does not establish archived agreement.']
    elif case in ROLLER_CASES:
        helper = _load(root/'scripts'/names[0], '_suite_roller_decoder')
        decoder = _load(root/'scripts'/names[2], '_suite_variant_rows')
        units = _read(units_path)['columns']
        columns = [dict(index0=i, name=n, physical_unit=units[i]['physical_unit']) for i,n in enumerate(decoder.NAMES)]
        target = helper.target_for(case.removeprefix('st5-roller-'), decoder, columns, manifest)
    else:
        helper = _load(root/'scripts'/names[1], '_suite_forward_decoder')
        target = helper.target_for(case.removeprefix('st5-forward-'), manifest)
    dependencies = [_pin(p) for p in [manifest_path, units_path, root/'.reference/aswing_doc.txt',
                                     *[root/'scripts'/name for name in names]]]
    dependencies += target.get('byte_identical_duplicates', [])
    dependencies += extra_dependencies
    return target, dependencies


def _target(root, case):
    if case in ROLLER_CASES + FORWARD_CASES + ELLIPTICAL_CASES:
        target, dependencies = decode_st5_variant(root, case)
        output = next(p for p in target['source_pins'] if p['path'].endswith('.txt'))
        raw = json.dumps(target, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
        return target, dependencies, dict(output, decoder='st5-variant-text-v1',
                                         decoded_sha256=hashlib.sha256(raw).hexdigest())
    if case == 'st5-30lb_80_20':
        target = decode_st5_original(root)
        output = next(p for p in target['source_pins'] if p['path'].endswith('.txt'))
        raw = json.dumps(target, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
        origin = dict(output, decoder='st5-original-text-v1', decoded_sha256=hashlib.sha256(raw).hexdigest())
        return target, target['decoder_dependencies'], origin
    if case in CASES[:2]:
        family = case[:3]
        path = root/f'docs/validation/isae-{family}-reference-target.json'
        raw = path.read_bytes()
        return json.loads(raw), [_pin(path)], dict(path=str(path), sha256=hashlib.sha256(raw).hexdigest())
    audit_path = root/'docs/validation/isae-st5-load-cases-source-audit.json'
    audit = _read(audit_path)
    _require(audit['checks_passed'] == audit['checks_total'], 'Additional ST5 source audit failed.')
    basename = 'JW_1_'+case[4:]+'-target.json'
    expected = next(p for p in audit['targets'] if Path(p['path']).name == basename)
    archive = root/'docs/validation/isae-st5-load-cases-20261026-evidence.zip'
    member = 'source-audit/'+basename
    with zipfile.ZipFile(archive) as stream:
        raw = stream.read(member)
    _require(len(raw) == expected['bytes'] and hashlib.sha256(raw).hexdigest() == expected['sha256'],
             'Published additional ST5 target changed.')
    return json.loads(raw), [_pin(audit_path), _pin(archive)], dict(archive=str(archive), member=member,
        bytes=len(raw), sha256=expected['sha256'])


def _source(root, case):
    if case in ELLIPTICAL_CASES:
        return root/'.reference/isae-validation'/REVISION/ST5_RELATIVE.parent/'Elliptical_Loading'/('JW_1_'+case.removeprefix('st5-elliptical-')+'.asw')
    if case in ROLLER_CASES:
        return root/'.reference/isae-validation'/REVISION/ST5_RELATIVE.parent/'Link_Joint'/('JW_1_'+case.removeprefix('st5-roller-')+'.asw')
    if case in FORWARD_CASES:
        kind, load = case.removeprefix('st5-forward-').split('_')
        folder = 'Rigid_Joint' if kind == 'cosine' else 'Elliptical_Loading'
        return root/'.reference/isae-validation'/REVISION/ST5_RELATIVE.parent/folder/('JW_1_FW_'+load+'.asw')
    if case == 'st5-30lb_80_20':
        return root/'.reference/isae-validation'/REVISION/ST5_RELATIVE/(ST5_ORIGINAL+'.asw')
    return root/('examples/isae-st3-static-m15_0.asw' if case.startswith('st3')
                 else 'examples/isae-st5-static-'+case[4:]+'.asw')


def _generated(root, case):
    if case in ROLLER_CASES + FORWARD_CASES:
        helper = _load(root/('scripts/verify-isae-st5-roller.py' if case in ROLLER_CASES
                            else 'scripts/verify-isae-st5-forward.py'), '_suite_static_variant')
        if case in ROLLER_CASES:
            generator = _load(root/'scripts/verify-isae-st5-load-cases.py', '_suite_roller_generator')
            text, patches, diff = helper.generated(_source(root, case), Path(TARGET_MARKER), generator)
            before, after = 'cold_solves=1, fresh_residuals=1,', 'cold_solves=len(records), fresh_residuals=len(records),'
            _require(text.count(before) == 1, 'Roller operation count anchor changed.')
            text = text.replace(before, after)
            patches.append(dict(label='all executed grids counted', before=before, after=after))
        else:
            text, patches = helper.generated(_source(root, case), Path(TARGET_MARKER))
            diff = ''
        before = 'all_fine_mesh_gates_pass=None,'
        after = "all_fine_mesh_gates_pass=all(v['passes'] for v in changes[-1]['measures'].values()) if changes else None,"
        _require(text.count(before) == 1, 'Variant mesh summary anchor changed.')
        text = text.replace(before, after)
        patches.append(dict(label='summarize three-grid refinement', before=before, after=after))
    elif case in CASES[:2]:
        helper = _load(root/'scripts/verify-source-discrete-integration.py', '_suite_static_source')
        text, patches, diff = helper.generate(case[:3])
        old_scope = helper.metadata(case[:3])['output_scope']
        new_scope = ('Current production source constitutive interval/endpoint recovery is available. '
                     'This verifier retains its conservative one-sided archived endpoint comparisons; '
                     'no historical-exporter equivalence follows.')
        _require(text.count(repr(old_scope)) == 1, 'Current reporting source anchor changed.')
        text = text.replace(repr(old_scope), repr(new_scope))
        patches.append(dict(label='current recovery reporting only', before=old_scope, after=new_scope))
    else:
        helper = _load(root/'scripts/verify-isae-st5-load-cases.py', '_suite_static_loads')
        text, patches, diff = helper.generate(_source(root, case), Path(TARGET_MARKER))
    # This is only an execution guard; every recovery expression and gate stays
    # byte-for-byte as generated by the existing reviewed helper.
    if case in CASES[:2]:
        anchor = "        write(out/'comparison.json', packet)"
        _require(text.count(anchor) == 1, 'Physical-stop source anchor changed.')
        replacement = anchor+"\n        assert passed, 'Physical gate failed; retain state and stop before refinement.'"
        text = text.replace(anchor, replacement)
        patches.append(dict(label='stop after physical failure', before=anchor, after=replacement))
    compile(text, '<isae-suite-structure-generated>', 'exec')
    return text, patches, diff


def _meshes(target, st3):
    # These are the exact public prepare() node recipes, with no physics or fit.
    if st3:
        nodes = {'1': sorted({r['physical_values'][0] for r in target['rows']} | {.6*.558})}
    else:
        nodes = {str(b['beam']): sorted({r['printed_t'] if r['exact_anchor_t'] is None
                 else r['exact_anchor_t'] for r in b['rows']}) for b in target['beams']}
    meshes = []
    for level in range(3):
        counts = {key: len(values)-1 for key, values in nodes.items()}
        meshes.append(dict(level=level, intervals_by_beam=counts,
            panels={'default': max(counts.values()), 'beams': {key: {'nodes': values} for key, values in nodes.items()}}))
        nodes = {key: sorted(values+[(a+b)/2 for a, b in zip(values[:-1], values[1:])])
                 for key, values in nodes.items()}
    expected = [44, 88, 176] if st3 else [38, 76, 152] if len(target['beams']) == 1 else [70, 140, 280]
    _require([sum(m['intervals_by_beam'].values()) for m in meshes] == expected, 'Original grid recipe changed.')
    return meshes


def plan(root, *, snapshots=None):
    """Seventeen snapshots; planning itself has no production import or solve."""
    root = Path(root).resolve()
    snapshots = CASES if snapshots is None else tuple(snapshots)
    _require(len(set(snapshots)) == len(snapshots) and all(s in CASES for s in snapshots), 'Unknown structural snapshot scope.')
    if not snapshots:
        return []
    # A plan records one source/kernel snapshot. Reuse content hashes only
    # inside this invocation; every new plan and worker revalidation reads the
    # files again. Return copies so a caller cannot alter another job's pins.
    pinned = {}

    def pin_once(path):
        key = str(path)
        if key not in pinned:
            value = _pin(path)
            pinned[key] = value
            pinned[value['path']] = value
        return dict(pinned[key])

    common = [Path(__file__), root/'scripts/verify-source-discrete-integration.py',
        root/'scripts/verify-isae-st3-archived-output.py', root/'scripts/isae_st3_static_reference.py',
        root/'scripts/verify-isae-st5-archived-output.py', root/'scripts/verify-isae-st5-load-cases.py']
    common_paths = {pin_once(p)['path'] for p in common}
    kernel_pins = [pin_once(p) for p in sorted((root/'openswing').glob('*.py'))]
    jobs = []
    for case in snapshots:
        st3 = case.startswith('st3')
        target, dependencies, target_origin = _target(root, case)
        source = _source(root, case)
        raw_sources = target['files' if st3 else 'source_pins']
        source_pin = pin_once(source)
        _require(source_pin['sha256'] == raw_sources[0]['sha256'], 'Packaged model differs from literal original.')
        for item in raw_sources:
            actual = pin_once(item['path'])
            _require(actual['sha256'] == item['sha256'] and actual['bytes'] == item['bytes'], 'Original input/export changed.')
        generated, patches, _ = _generated(root, case)
        rows, columns = (45, 8) if st3 else (sum(b['row_count'] for b in target['beams']), 27)
        policy = dict(beam_interpolation='drela-segspl-v1', structural_operator=
            'drela-steady-zero-offset-v1' if case in CASES[:2] else 'drela-steady-section-v1')
        paths = common_paths | {source_pin['path']}
        source_pins = [pin_once(path) for path in sorted(paths)] + dependencies
        source_pins += [pin_once(p['path']) for p in raw_sources]
        source_pins = list({p['path']: p for p in source_pins}.values())
        jobs.append(dict(id=case.upper()+'-static-three-grids', case_id='ST-3' if st3 else 'ST-5',
            adapter='structure', snapshot=case, expected_outputs=3*rows*columns,
            rows_per_grid=rows, outputs_per_row=columns, grids=_meshes(target, st3),
            settings=policy, source=str(source), source_pins=source_pins,
            kernel_pins=[dict(p) for p in kernel_pins],
            target_origin=target_origin, generated_template_sha256=hashlib.sha256(generated.encode()).hexdigest(),
            wrapper_patches=patches, expected_operations=dict(cold_solves=3, fresh_residuals=3),
            suggested_cap_seconds=120, reference_scope='All printed output fields at all original rows on each declared grid; not a complete family.',
            field_groups=(dict(structural_per_grid=270, conditional_zero_per_grid=90) if st3 else
                dict(structural_per_grid=rows*14, conditional_zero_per_grid=rows*10, input_echo_per_grid=rows*2, unresolved_display_per_grid=rows)),
            qualifications=[
                'Exact original source is unchanged; no experiment or fitted parameters enter this replay.',
                'Strict printed half-last-place gates remain unchanged. Coordinates use known exact anchors and otherwise printed centers.',
                'Duplicate rows retain incoming/outgoing traces; no historical zero-length computational element is inferred.',
                'Three nested grids test sensitivity; historical unrounded nodes and startup/settings remain unknown.',
                'ST3 shared-coordinate rounding witnesses remain a separate historical diagnostic; this job does not substitute fitted coordinates.',
                'ST5 20lb80/20 retains the original midpoint chord/Cm display diagnostic. The other ST5 snapshots use the separately supported endpoint-value-average display, including160 matching original echo tokens for30lb80/20.',
                'ST5 f_reac scalar-weight diagnostic is unresolved. Conditional zero channels are reporting conventions, not aerodynamic predictions.',
                'Printed reference, numerical validity and fine-grid sensitivity are reported separately.']))
    return jobs


def _write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')


def run(root, job):
    """Execute existing full verifiers; keep all raw artifacts on any failure."""
    root = Path(root).resolve()
    matches = [row for row in plan(root, snapshots=(job.get('snapshot'),)) if row['id'] == job.get('id')]
    _require(len(matches) == 1, 'Unknown structural job.')
    canonical = matches[0]
    for key, value in canonical.items():
        _require(job.get(key) == value, 'Prepared structural job changed: '+key)
    case, st3 = canonical['snapshot'], canonical['case_id'] == 'ST-3'
    stage = Path(tempfile.mkdtemp(prefix='openswing-isae-suite-'+case+'-'))
    text, patches, diff = _generated(root, case)
    target, _, _ = _target(root, case)
    if TARGET_MARKER in text:
        target_path = stage/'target.json'
        _write(target_path, target)
        _require(text.count(TARGET_MARKER) == 1, 'Generated target path is ambiguous.')
        text = text.replace(TARGET_MARKER, str(target_path))
    verifier = stage/'verifier.py'
    verifier.write_text(text)
    _write(stage/'adapter-job.json', canonical)
    _write(stage/'patches.json', patches)
    (stage/'wrapper.diff').write_text(diff)
    sys.path.insert(0, str(root/'scripts'))
    module = _load(verifier, '_suite_structure_verifier')
    error = None
    with (stage/'run.log').open('w') as log, contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
        try:
            module.prepare(stage)
            actual_plan = _read(stage/'plan.json')
            _require([m['panels'] for m in actual_plan['meshes']] ==
                     [m['panels'] for m in canonical['grids']], 'Verifier grid differs from registered grid.')
            module.run(stage)
        except Exception as exc:
            error = dict(type=type(exc).__name__, message=str(exc), traceback=traceback.format_exc())
    packets, checks = [], []
    for grid in canonical['grids']:
        folder = stage/(f"n{sum(grid['intervals_by_beam'].values())}" if st3 else f"level{grid['level']}")
        path = folder/'comparison.json'
        if not path.is_file():
            continue
        packet = _read(path)
        _require(len(packet['rows']) == canonical['rows_per_grid'], 'Verifier returned an incomplete row table.')
        packets.append(packet)
        names = module.COLUMNS if st3 else [c['name'] for c in target['columns']][1:]
        for index, row in enumerate(packet['rows']):
            for column, name in enumerate(names, 0 if st3 else 1):
                predicted, expected, tolerance = (row[k][column] for k in ('values', 'expected', 'half_last_place'))
                checks.append(dict(name=f"grid{grid['level']}:row{index:03d}:{name}",
                    predicted=predicted, expected=expected, tolerance=tolerance,
                    abs_error=abs(predicted-expected), comparison='<=', passed=abs(predicted-expected) <= tolerance,
                    source_line=row['source_line'], t_printed=row['t_printed'], t_evaluated=row['t_evaluated'],
                    trace=row.get('trace', row.get('side'))))
    summary = _read(stage/'summary.json') if (stage/'summary.json').is_file() else None
    stable = all(_pin(p['path']) == p for p in canonical['source_pins']+canonical['kernel_pins'])
    numerical = bool(error is None and summary and summary['all_numerical_gates_pass'] and stable
                     and len(checks) == canonical['expected_outputs'])
    result = dict(id=canonical['id'], case_id=canonical['case_id'], adapter='structure',
        status='computed' if numerical else 'numerical_failure', numerical_pass=numerical,
        reference_match=numerical and all(c['passed'] for c in checks), reference_checks=checks,
        mesh_gates_pass=summary['all_fine_mesh_gates_pass'] if summary else None,
        summary=summary, error=error, source_pins_unchanged=stable,
        artifact_directory=str(stage), artifact_files=[_pin(p) for p in sorted(stage.rglob('*')) if p.is_file()],
        completed_grid_count=len(packets), expected_operations=canonical['expected_operations'],
        qualifications=canonical['qualifications'], reference_scope=canonical['reference_scope'])
    _write(stage/'adapter-result.json', result)
    return result
