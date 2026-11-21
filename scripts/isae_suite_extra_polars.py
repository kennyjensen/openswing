"""Additional literal ISAE polar scopes; planning imports no production code.

SA10: five original variants execute, one original attachment failure remains.
SA14: three raw CL polars execute. SA15 force-axis/settings remain explicit
unsupported jobs. SA12 now owns a dedicated ground-aware adapter.
"""
from pathlib import Path
import copy
import base64
import hashlib
import json
import re

try:
    from . import isae_suite_polars as polar
except ImportError:
    import isae_suite_polars as polar

REVISION = polar.REVISION
FAMILIES = (10, 14, 15)
MANIFEST_SHA256 = '813347a3bd9fcbd029a1ec86e0c3141f82422af26f33ebde7c2f732a16bf27f6'
SA10 = ('Louvered', 'TS_60_40_80', 'TS_60_45_30', 'TS_80_60_40', 'wing_alone', 'wing_extension')
OUTPUTS = {
    10: tuple(polar.OUTPUTS), 12: ('CL', 'CD', 'CDi', 'Cm'),
    14: ('CL',), 15: ('CD', 'CY', 'CL', 'Cl', 'Cm', 'Cn', 'efficiency'),
}
HEADERS = {
    12: ('i', 't', 'conv', 'stall', 'alpha', 'CL', 'CD', 'CDi', 'CM'),
    14: ('i', 't', 'conv', 'stall', 'alpha', 'CL'),
    15: ('i', 't', 'alpha_ref', 'CD', 'CY', 'CL', 'Cl', 'Cm', 'Cn', 'span', 'eff.'),
}
BLOCKS = {
    'ORIGINAL_ATTACHMENT_DOMAIN': 'Original Joint stations reference opposite beam2/3 domains; repaired-joint historical model is excluded.',
    'GROUND_ROUTE_NOT_IMPLEMENTED': 'Generic polar route does not forward required ground flag/normal/height and declared Euler pose. Dedicated ground adapter required; no ignored geometry.',
    'FORCE_AXES_AND_SETTINGS_UNRESOLVED': 'Generic output route lacks reviewed CY/Cl/Cn frame mapping; exact auto-loaded .set exists but is undecoded. No partial seven-channel claim.',
}
SOURCE_PAIRING_ID = 'sa7-fore-f745fb40'
DOCUMENTED_SA7_SCOPE = 'sa7-documented'
SOURCE_PAIRING_REVISION = 'f745fb40b308d85a2a99e039665457177686a9bd'
SOURCE_PAIRING_AUDIT = 'artifacts/isae/sa7-drag-source-audit-20261028/history.json'
SOURCE_PAIRING_AUDIT_SHA256 = 'b338f640332e23f3f6187bd686b09f9a10a5586ee3c5225c236ea2c68a8f812d'
SOURCE_PAIRING_MODEL_BLOB = '5dabcd27a836e493cd9fd8f48060cea7c5df21f7'
SOURCE_PAIRING_STEM = 'Tandem_GAW2_L163_G05_Fore_Only'


def _pairing_context(root, pairing_id):
    """Authenticate one reviewed historical trio; no arbitrary path overrides."""
    if pairing_id != SOURCE_PAIRING_ID:
        raise ValueError('Unknown source pairing.')
    root = Path(root).resolve()
    audit_path = root/SOURCE_PAIRING_AUDIT
    audit_pin = polar._pin(audit_path, root)
    if audit_pin['sha256'] != SOURCE_PAIRING_AUDIT_SHA256:
        raise ValueError('Historical source pairing audit changed.')
    audit = json.loads(audit_path.read_bytes())
    reviewed = {item['path']: item for item in audit['source_pins']}
    if len(reviewed) != len(audit['source_pins']):
        raise ValueError('Duplicate historical evidence pins.')
    evidence = {audit_pin['path']: audit_pin}

    def verified(path):
        target = (root/path).resolve()
        if not target.is_relative_to(root):
            raise ValueError('Historical evidence path escapes repository.')
        actual = polar._pin(target, root)
        if actual != reviewed.get(path):
            raise ValueError('Historical source evidence changed: ' + path)
        evidence[path] = actual
        return target

    manifest_path = verified('.reference/isae-validation/manifest.json')
    if evidence['.reference/isae-validation/manifest.json']['sha256'] != MANIFEST_SHA256:
        raise ValueError('Pinned original manifest changed.')
    manifest = json.loads(manifest_path.read_bytes())
    if manifest['revision'] != REVISION:
        raise ValueError('Source revision changed.')
    lineage = next(item for item in audit['bounded_lineage']
                   if item['commit'] == SOURCE_PAIRING_REVISION)
    tree_path = verified(lineage['cached_tree']['path'])
    tree = json.loads(tree_path.read_bytes())
    if tree.get('truncated') is not False:
        raise ValueError('Historical source tree is incomplete.')
    old, current = {}, {}
    for suffix in ('asw', 'sh', 'txt'):
        recovered = audit['recovered_earliest'][suffix]
        old[suffix] = verified(recovered['path'])
        response_path = verified(recovered['raw_blob_response']['path'])
        response = json.loads(response_path.read_bytes())
        raw = old[suffix].read_bytes()
        sha1 = hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
        if (response.get('encoding') != 'base64' or response.get('sha') != sha1
                or recovered['git_blob_sha1'] != sha1 or response.get('size') != len(raw)
                or base64.b64decode(response['content']) != raw):
            raise ValueError('Historical Git blob/content mismatch.')
        entries = [item for item in tree['tree']
                   if Path(item['path']).name == SOURCE_PAIRING_STEM + '.' + suffix]
        if (len(entries) != 1 or entries[0]['type'] != 'blob'
                or entries[0]['sha'] != sha1 or entries[0]['size'] != len(raw)):
            raise ValueError('Historical trio is not bound to the declared commit tree.')
        current[suffix] = verified(audit['current_originals'][suffix]['path'])
        source = manifest['files'][current[suffix].relative_to(
            root/'.reference/isae-validation'/REVISION).as_posix()]
        current_raw = current[suffix].read_bytes()
        if (source['sha256'] != hashlib.sha256(current_raw).hexdigest()
                or source['bytes'] != len(current_raw)):
            raise ValueError('Current source differs from immutable manifest.')
        if suffix != 'asw' and current_raw != raw:
            raise ValueError('Historical driver/table differs from current original.')
    if audit['recovered_earliest']['asw']['git_blob_sha1'] != SOURCE_PAIRING_MODEL_BLOB:
        raise ValueError('Unreviewed historical model.')
    for helper in (Path(__file__).resolve(), root/'scripts/isae_suite_polars.py'):
        item = polar._pin(helper, root)
        evidence[item['path']] = item
    return old, current, evidence, lineage


def plan_source_pairing(root, pairing_id=SOURCE_PAIRING_ID):
    """Opt-in supplemental jobs using recovered bytes, never a new solver."""
    root = Path(root).resolve()
    old, current, evidence, lineage = _pairing_context(root, pairing_id)
    table_path = current['txt'].relative_to(root).as_posix()
    originals = [job for job in polar.plan(root)
                 if job['case_id'] == 'SA-7' and job['table_path'] == table_path]
    if (len(originals) != 58 or {j['row_index'] for j in originals} != set(range(29))
            or {j['settings']['panels'] for j in originals} != {64, 128}):
        raise ValueError('Historical pairing requires all 29 original rows on both meshes.')
    rho, rho_token = polar._rho_sl(old['asw'].read_text())
    historical_path = next(item['path'] for item in lineage['exact_trio_entries']
                           if item['path'].endswith('/' + SOURCE_PAIRING_STEM + '.asw'))
    jobs = []
    for original in originals:
        declaration = original['driver_declarations']
        if (declaration['model_file'] != SOURCE_PAIRING_STEM + '.asw'
                or declaration['output_files'] != [SOURCE_PAIRING_STEM + '.txt']
                or declaration['requested_nodes'] is not None
                or declaration['speed'] != 69.15 or len(declaration['alpha_tokens']) != 29
                or original['settings']['density'] != rho
                or original['settings']['density_token'] != rho_token):
            raise ValueError('Historical source setup differs from reviewed declaration.')
        row = original['reference_row']
        command = declaration['alpha_tokens'][row['row_index']]
        if abs(polar._number(command) - row['fields']['alpha']['value']) > row['fields']['alpha']['tolerance']:
            raise ValueError('Historical driver incidence differs from archived row.')
        job = copy.deepcopy(original)
        job.update(id=original['id'].replace(':row', ':historical-f745fb40:row'),
                   adapter='extra_polars', target_kind='historical_source_polar',
                   execution_route='historical_seven_fields', required_outputs=list(polar.OUTPUTS),
                   comparison_scope='supplemental_historical_source_pairing',
                   complete_family_reproduction=False, unsupported_reason=None, blocker_code=None,
                   exact_driver_alpha_token=command,
                   model_path=old['asw'].relative_to(root).as_posix())
        # Keep the existing table/driver paths and their exact target identity.
        ordered = [job['model_path'], table_path, job['driver_path']]
        job['sources'] = [evidence[path] for path in ordered]
        job['sources'] += [evidence[path] for path in sorted(evidence) if path not in ordered]
        job['source_pairing'] = dict(id=pairing_id,
            repository='https://github.com/rom1isae/ISAE_Aswing_Experimental_Validation',
            revision=SOURCE_PAIRING_REVISION, original_job_id=original['id'],
            current_model_path=original['model_path'], historical_model_path=job['model_path'],
            historical_repository_path=historical_path, model_git_blob_sha1=SOURCE_PAIRING_MODEL_BLOB,
            unchanged_driver_and_table=True, producer_execution_authenticated=False,
            existing_native_targets_reused=True, audit=evidence[SOURCE_PAIRING_AUDIT],
            tree=evidence[lineage['cached_tree']['path']],
            model_blob_api='https://api.github.com/repos/rom1isae/ISAE_Aswing_Experimental_Validation/git/blobs/'
                           + SOURCE_PAIRING_MODEL_BLOB)
        job['qualifications'] += [
            'Explicit supplemental historical-source pairing: the first public import model is used unchanged; the current-file model and its registered jobs are preserved separately.',
            'The historical driver/output bytes are identical to the current originals. All 29 rows and negative Drag/CD signs retain their original precision; these are reused native targets, not additional independent targets.',
            'Commit-tree co-location authenticates the recovered source association, not the executable/build, startup state, historical mesh or actual production of the output table.',
            'The same declared 64/128 interval reconstruction and current solver/gates apply. No original F-toggle initial state or historical circulation K is inferred.',
            'The negative-drag cause remains unresolved. This pairing does not establish complete-family reproduction or justify any sign, reference-area or tolerance correction.',
        ]
        jobs.append(job)
    return jobs


def validate_source_pairing(root, job):
    """Source-only complete canonical contract; True or ValueError."""
    pairing = job.get('source_pairing')
    if not isinstance(pairing, dict) or pairing.get('id') != SOURCE_PAIRING_ID:
        raise ValueError('Missing or unknown historical source pairing.')
    try:
        canonical = next((item for item in plan_source_pairing(root, pairing['id'])
                          if item['id'] == job.get('id')), None)
    except OSError as exc:
        raise ValueError('Historical source evidence is unavailable.') from exc
    if canonical is None or any(job.get(key) != value for key, value in canonical.items()):
        raise ValueError('Historical source pairing job differs from canonical contract.')
    return True


def select_documented_sa7(jobs):
    """Use the authenticated original fore input once, preserving every target.

    Called after both owning adapters have planned their jobs. The literal
    latest-file comparison stays available without this explicit selector.
    Source-pairing jobs keep their full existing canonical execution contract.
    """
    replacements = {j['source_pairing']['original_job_id']: j for j in jobs
                    if j.get('source_pairing', {}).get('id') == SOURCE_PAIRING_ID}
    originals = {j['id']: j for j in jobs if j['id'] in replacements}
    if len(replacements) != 58 or set(originals) != set(replacements):
        raise ValueError('Documented SA-7 scope requires all 58 original and paired fore-wing jobs.')
    for key, paired in replacements.items():
        original = originals[key]
        if (original['case_id'] != 'SA-7' or paired['case_id'] != 'SA-7'
                or paired['source_pairing']['current_model_path'] != original['model_path']
                or any(paired[k] != original[k] for k in
                       ('reference_row', 'settings', 'table_path', 'driver_path', 'expected_outputs'))):
            raise ValueError('Documented SA-7 pairing changed an original target or setup.')
    selected = [j for j in jobs if j['id'] not in replacements]
    family = [j for j in selected if j['case_id'] == 'SA-7']
    if len(family) != 116 or sum(j['expected_outputs'] for j in family) != 812:
        raise ValueError('Documented SA-7 scope must retain exactly 116 jobs and 812 output slots.')
    return selected


def _blocker(case_id, model_path):
    if case_id == 'SA-10' and Path(model_path).stem == 'TS_60_45_30':
        return 'ORIGINAL_ATTACHMENT_DOMAIN'
    if case_id == 'SA-12':
        return 'GROUND_ROUTE_NOT_IMPLEMENTED'
    if case_id == 'SA-15' and Path(model_path).stem == 'JW-1_FW_Only_Body':
        return 'FORCE_AXES_AND_SETTINGS_UNRESOLVED'
    return None


def decode_table(text, family):
    lines = text.splitlines()
    if len(lines) < 4 or 'Operating point sequence' not in lines[1]:
        raise ValueError('Missing original operating-sequence header.')
    header = tuple(lines[2].lstrip('# ').split())
    if family == 10:
        suffix = ('VIAS_ref', 'beta_ref', 'alpha_ref', 'Lift', 'Drag', 'CL', 'CD', 'CDi', 'CM', 'span', 'eff.')
        if header[:4] != ('i', 't', 'conv', 'stall') or header[-len(suffix):] != suffix:
            raise ValueError('Unsupported SA10 wide-table header.')
        columns = {'index': 0, 'time': 1, 'conv': 2, 'stall': 3,
                   'speed': 72, 'beta': 73, 'alpha': 74,
                   **dict(zip(OUTPUTS[10], range(75, 82)))}
        width = 82
    else:
        if header != HEADERS[family]:
            raise ValueError(f'Unsupported SA{family} table header.')
        names = (('index', 'time', 'alpha') if family == 15 else
                 ('index', 'time', 'conv', 'stall', 'alpha')) + OUTPUTS[family]
        columns, width = dict(zip(names, range(len(names)))), len(names)
    rows = []
    for line_number, line in enumerate(lines[3:], 4):
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        tokens = line.split()
        if len(tokens) != width:
            raise ValueError(f'Line {line_number}: expected {width} original columns.')
        # Validate every token, including echoes outside the selected scope.
        decoded = [polar.printed_value(token) for token in tokens]
        fields = {name: decoded[i] for name, i in columns.items()}
        if fields['index']['value'] != len(rows) + 1 or fields['alpha']['value'] is None:
            raise ValueError(f'Line {line_number}: invalid sequence/coordinate.')
        rows.append(dict(row_index=len(rows), line_number=line_number, tokens=tokens, fields=fields))
    if not rows:
        raise ValueError('No archived rows.')
    return rows


def decode_driver(text, expected_output):
    """Reuse bounded driver decoder; allow the reviewed relative SA15 output."""
    if '..' in Path(expected_output).parts or Path(expected_output).is_absolute():
        raise ValueError('Unsafe output path.')
    lines = text.splitlines(keepends=True)
    targets = [i for i, line in enumerate(lines) if line.strip() == expected_output
               and i > 0 and lines[i - 1].strip().lower() == 'w']
    if len(targets) != 1:
        raise ValueError('Driver does not explicitly write the unique reviewed output.')
    replacement = Path(expected_output).name
    # This temporary string only adapts the filename validator. No file edits.
    i = targets[0]
    lines[i] = replacement + ('\n' if lines[i].endswith('\n') else '')
    declaration = polar.decode_driver(''.join(lines))
    if declaration['output_files'] != [replacement]:
        raise ValueError('Additional output writes require a separately reviewed adapter.')
    declaration['output_files'] = [expected_output]
    declaration['scalar_commands'] = [line.strip() for line in text.splitlines()
                                      if re.match(r'^!!?[A-Za-z]', line.strip())]
    return declaration


def _settings(declaration, row, rho, rho_token, count, level):
    return dict(panels=count, mesh_level=level,
                base_panels=declaration['requested_nodes'] or 64,
                mesh_source=polar.NODE_MESH_SOURCE if declaration['requested_nodes'] else
                            polar.FALLBACK_MESH_SOURCE,
                alpha=row['fields']['alpha']['value'], alpha_token=row['fields']['alpha']['token'],
                speed=declaration['speed'], density=rho, density_token=rho_token,
                density_assumption='model Constant rhoSL; sea level assumed',
                mach=0., freeze_influences=False, beta=0., beam_interpolation='natural-v1',
                circulation_method='auto', stall=True, stall_factor=40., stall_width=.05,
                wake_core_ratio=.25, aero_lag=True, body_added_mass_factor=1.)


def _tables(folder, family):
    if family == 10:
        return [(folder/'Aswing_Simulations'/f'{name}.txt',
                 folder/'Aswing_Simulations'/f'{name}.sh', f'{name}.txt') for name in SA10]
    if family == 12:
        return [(folder/'Aswing_Simulations'/f'Rectangular_Wing_{flap}_hc_{height}.txt',
                 folder/'Aswing_Simulations'/f'Rectangular_Wing_{flap}_hc_{height}.sh',
                 f'Rectangular_Wing_{flap}_hc_{height}.txt')
                for flap in ('Flap', 'No_Flap') for height in ('05', '2', 'inf')]
    if family == 14:
        return [(folder/'ASWING_simulations'/f'{name}.txt',
                 folder/'ASWING_simulations'/f'{name}.sh', f'{name}.txt')
                for name in ('WB_polaire_totale', 'WB_polaire_totale_infinite_fuselage', 'W_only_polaire_totale')]
    name = 'JW1_FW_Only_Body_Aswing_simulations/JW1_FW_Only_Body_CL_alpha.txt'
    return [(folder/name, folder/'JW-1_FW_Only_Body.sh', name)]


def sa14_startup_settings(text):
    """Apply the three original driver prefixes to the documented startup menu.

    OPER/K/F is initially true and is never toggled here. OPER/K/M toggles
    fixed PG Mach to speed-derived Mach. Blank lines leave the K submenu;
    '%' followed by A,D selects anchored constraints, not K/F. This is a
    declared default reconstruction, not a recovered historical settings file.
    """
    parts = re.split(r'<<\s*EOF\s*\n', text, maxsplit=1)
    if len(parts) != 2 or '!A' not in parts[1]:
        raise ValueError('Unreviewed SA14 startup script.')
    prefix = [line.strip().lower() for line in parts[1].split('!A', 1)[0].splitlines()]
    wing = ['oper', '!v 70', '%', 'a', 'd', 'k', 'm', '']
    body = ['oper', 'k', 'iter', '10', '', '!v 70', '%', 'a', 'd', 'k', 'm', '']
    commands = [line.strip().lower() for line in parts[1].splitlines()]
    if prefix not in (wing, body) or commands.count('m') != 1 or 'f' in commands:
        raise ValueError('Unreviewed SA14 K/F or K/M command sequence.')
    return dict(freeze_influences=True, mach=None)


def plan(root, *, source_pairings=(), comparison_scopes=()):
    """Default registered scopes, plus only explicitly requested supplements."""
    if (not isinstance(source_pairings, (tuple, list))
            or any(pairing != SOURCE_PAIRING_ID for pairing in source_pairings)
            or len(set(source_pairings)) != len(source_pairings)):
        raise ValueError('Provide unique reviewed source pairing IDs.')
    from scripts import isae_suite_sa15 as sa15
    if (len(set(comparison_scopes)) != len(comparison_scopes)
            or any(scope not in (sa15.SCOPE, DOCUMENTED_SA7_SCOPE) for scope in comparison_scopes)):
        raise ValueError('Provide unique reviewed extra-polar comparison scopes.')
    root = Path(root).resolve()
    cache = root/'.reference/isae-validation'/REVISION
    manifest_path = cache.parent/'manifest.json'
    raw = manifest_path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != MANIFEST_SHA256:
        raise ValueError('Pinned original manifest changed.')
    manifest = json.loads(raw)
    if manifest['revision'] != REVISION:
        raise ValueError('Source revision changed.')
    helper_pins = [polar._pin(Path(__file__).resolve(), root),
                   polar._pin(root/'scripts/isae_suite_polars.py', root)]
    jobs = []
    for family in FAMILIES:
        folders = list((cache/'1 - Aerodynamics/SA - Steady Aerodynamics Cases').glob(f'SA - {family} - *'))
        if len(folders) != 1:
            raise ValueError(f'Missing/ambiguous original SA-{family} folder.')
        for table, driver, output_token in _tables(folders[0], family):
            text = driver.read_text()
            declaration = decode_driver(text, output_token)
            model = driver.parent/declaration['model_file']
            paths = [model, table, driver]
            if model.with_suffix('.set').is_file():
                paths.append(model.with_suffix('.set'))
            for path in paths:
                source = manifest['files'].get(path.relative_to(cache).as_posix())
                if source is None or polar._pin(path, root)['sha256'] != source['sha256']:
                    raise ValueError(f'Original source differs from manifest: {path}')
            rows = decode_table(table.read_text(), family)
            if len(rows) != {10: 27, 12: 85, 14: 60, 15: 13}[family]:
                raise ValueError('Original row accounting changed.')
            tokens = declaration['alpha_tokens']
            if len(tokens) != len(rows):
                raise ValueError('Driver/table row count mismatch; no inferred pairing.')
            rho, rho_token = polar._rho_sl(model.read_text())
            source_pins = [polar._pin(path, root) for path in paths] + helper_pins
            allowed = {'!V', '!A'} if family in (10, 14, 15) else {'!V', '!A', '!RZ'}
            if any(command.split()[0].upper() not in allowed for command in declaration['scalar_commands']):
                raise ValueError('Unreviewed control/power/pose commands; refusing guessed setup.')
            blocker_code = _blocker(f'SA-{family}', str(model))
            unsupported = BLOCKS.get(blocker_code)
            for row, command_token in zip(rows, tokens, strict=True):
                alpha = polar._number(command_token)
                if abs(alpha-row['fields']['alpha']['value']) > row['fields']['alpha']['tolerance']:
                    raise ValueError('Driver incidence differs beyond archived rounding interval.')
                if family == 10 and (row['fields']['speed']['value'] != declaration['speed']
                                      or row['fields']['beta']['value'] != 0):
                    raise ValueError('Wide-table speed/beta differs from reviewed setup.')
                nominal = declaration['requested_nodes'] or 64
                for level, count in enumerate((nominal, 2*nominal)):
                    settings = _settings(declaration, row, rho, rho_token, count, level)
                    # Executable SA10/14 command values equal printed centers;
                    # unsupported SA15 exact commands remain in declarations.
                    qualifications = list(polar.QUALIFICATIONS) + [
                        'This adapter compares only required_outputs; unused generic helper fields have no invented reference targets.',
                        'All archived rows, including repeated alpha12, retain distinct row IDs.',
                        'No whole-family or experimental agreement is established by these selected scopes.',
                    ]
                    if family == 14:
                        settings.update(sa14_startup_settings(text))
                        qualifications.remove(polar.RECONSTRUCTED_INFLUENCE_QUALIFICATION)
                        qualifications.append('Raw archived CL only; no experimental area multiplier or Mach.19 substitution. '
                            'Documented startup reconstruction: K/F remains frozen; the one K/M toggle selects speed-derived PG Mach. '
                            'No original .set is supplied; actual historical startup settings remain unverified.')
                    if family == 15:
                        qualifications.append('Literal units ft/s/lb; speed380 is ft/s. Source says Mach.35 already in section data; .set startup values are not decoded.')
                    sources = list(source_pins)
                    jobs.append(dict(id=f'SA-{family}:{table.stem}:row{row["row_index"]:03d}:n{count}',
                        case_id=f'SA-{family}', adapter='extra_polars', model_path=sources[0]['path'],
                        table_path=sources[1]['path'], driver_path=sources[2]['path'],
                        row_index=row['row_index'], expected_outputs=len(OUTPUTS[family]),
                        required_outputs=list(OUTPUTS[family]), settings=settings, sources=sources,
                        reference_row=row, driver_declarations=declaration,
                        exact_driver_alpha_token=command_token,
                        execution_route='unsupported' if unsupported else ('seven_fields' if family == 10 else 'CL_subset'),
                        unsupported_reason=unsupported, blocker_code=blocker_code, qualifications=qualifications,
                        complete_family_reproduction=False))
    if len(jobs) != 710 or len({j['id'] for j in jobs}) != len(jobs):
        raise ValueError('Incomplete or duplicate additional-family row accounting.')
    requested_pairings = list(source_pairings)
    if DOCUMENTED_SA7_SCOPE in comparison_scopes and SOURCE_PAIRING_ID not in requested_pairings:
        requested_pairings.append(SOURCE_PAIRING_ID)
    for pairing_id in requested_pairings:
        jobs.extend(plan_source_pairing(root, pairing_id))
    if sa15.SCOPE in comparison_scopes:
        jobs.extend(sa15.plan(root))
    if len({j['id'] for j in jobs}) != len(jobs):
        raise ValueError('Duplicate supplemental source pairing IDs.')
    return jobs


def _unsupported(job, reason, stable=True):
    checks = []
    for name in job['required_outputs']:
        ref = job['reference_row']['fields'][name]
        checks.append(dict(name=name, predicted=None, expected=ref['value'], expected_token=ref['token'],
                           abs_error=None, tolerance=ref['tolerance'], passed=False, unavailable_reason=reason))
    return dict(id=job['id'], case_id=job['case_id'], adapter=job['adapter'],
                status='unsupported' if stable else 'source_mismatch', numerical_pass=False,
                reference_match=False, physical_calls=0, sources_unchanged=stable,
                required_outputs=job['required_outputs'], expected_outputs=job['expected_outputs'],
                reference_checks=checks, numerical_checks=[], unsupported_reason=reason,
                blocker_code=job.get('blocker_code'),
                **{key: copy.deepcopy(job[key]) for key in
                   ('source_pairing', 'target_kind', 'comparison_scope') if key in job},
                complete_family_reproduction=False, seconds=0.)


def validate_blocked(root, job):
    """Cheap source-only validation for inline scheduling; never rebuilds plan."""
    code = _blocker(job['case_id'], job['model_path'])
    if (job.get('execution_route') != 'unsupported' or code is None
            or job.get('blocker_code') != code or job.get('unsupported_reason') != BLOCKS[code]
            or job['required_outputs'] != list(OUTPUTS[int(job['case_id'].split('-')[1])])):
        raise ValueError('Blocked-job identity, reason or required output scope changed.')
    try:
        root = Path(root).resolve()
        stable = all(polar._pin(root/s['path'], root) == s for s in job['sources'])
    except OSError:
        stable = False
    return _unsupported(job, BLOCKS[code] if stable else 'Pinned source changed.', stable)


def run(root, job):
    from scripts import isae_suite_sa15 as sa15
    if sa15.identifies(job):
        return sa15.run(root, job)
    root = Path(root).resolve()
    historical = (job.get('case_id') == 'SA-7' or 'source_pairing' in job
                  or job.get('execution_route') == 'historical_seven_fields')
    if historical:
        validate_source_pairing(root, job)
    if job['execution_route'] == 'unsupported':
        return validate_blocked(root, job)
    try:
        stable = all(polar._pin(root/s['path'], root) == s for s in job['sources'])
    except OSError:
        stable = False
    if not stable:
        return _unsupported(job, 'Pinned source changed.', False)
    route = job['execution_route']
    required = job['required_outputs']
    if not ((route == 'seven_fields' and job['case_id'] == 'SA-10' and required == list(polar.OUTPUTS))
            or (historical and route == 'historical_seven_fields' and required == list(polar.OUTPUTS))
            or (route == 'CL_subset' and job['case_id'] == 'SA-14' and required == ['CL'])):
        return _unsupported(job, 'Unreviewed execution route/output scope.')
    # Reject rather than silently discard any newly added physical setting.
    supported = set(_settings({'requested_nodes': None, 'speed': 1},
                             {'fields': {'alpha': {'value': 0, 'token': '0'}}}, 1, '1', 64, 0))
    if set(job['settings']) != supported or job.get('unsupported_reason'):
        return _unsupported(job, 'Settings are outside the reviewed generic physical route.')
    internal = copy.deepcopy(job)
    for name in polar.OUTPUTS:
        if name not in required:
            internal['reference_row']['fields'][name] = dict(value=None, token=None, tolerance=None,
                unavailable_reason='No archived target in this adapter scope; excluded from required outputs.')
    report = polar.run(root, internal)
    report['reference_checks'] = [r for r in report['reference_checks'] if r['name'] in required]
    report['unsupported_outputs'] = [r for r in report['reference_checks'] if 'unavailable_reason' in r]
    report['reference_match'] = bool(report.get('numerical_pass') and
        len(report['reference_checks']) == len(required) and all(r['passed'] for r in report['reference_checks']))
    report.update(required_outputs=required, expected_outputs=len(required), complete_family_reproduction=False,
                  reference_scope='Only required_outputs at original archived rows; historical settings unresolved.',
                  excluded_generic_reference_fields=[name for name in polar.OUTPUTS if name not in required])
    if historical:
        report.update({key: copy.deepcopy(job[key]) for key in
                       ('source_pairing', 'target_kind', 'comparison_scope')})
        report['reference_scope'] = ('Supplemental recovered historical-source pairing of seven unchanged native '
                                     'polar outputs; same original targets reused, historical execution unverified.')
    return report


def validate_result_contract(job, result):
    from scripts import isae_suite_sa15 as sa15
    if sa15.identifies(job):
        return sa15.validate_result_contract(job, result)
    if job.get('case_id') == 'SA-15':
        if (job.get('execution_route') != 'unsupported'
                or job.get('blocker_code') != 'FORCE_AXES_AND_SETTINGS_UNRESOLVED'
                or result.get('status') == 'computed' or result.get('numerical_pass') is True
                or result.get('reference_match') is True
                or any(c.get('predicted') is not None or c.get('passed') is True
                       for c in result.get('reference_checks', []))):
            raise ValueError('Original SA15 historical setup remains blocked; select the explicit declared scope.')
    return True
