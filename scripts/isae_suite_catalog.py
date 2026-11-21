"""Account for the complete pinned ISAE source archive, without running a case.

Native export headers identify candidates, never a model/output/settings pair.
Historical report claims are retained separately from fresh literal import checks.
The only production operation here is parse_asw; no mesh or physical evaluation.
"""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
from stat import S_ISREG
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from openswing.asw import parse_asw

REVISION = 'f62943df20e9e4d7d9f50e070477b22426b5f865'
REPOSITORY = 'https://github.com/rom1isae/ISAE_Aswing_Experimental_Validation'
SOURCE_PINS = {
    'manifest.json': '813347a3bd9fcbd029a1ec86e0c3141f82422af26f33ebde7c2f732a16bf27f6',
    'upstream-tree.json': '693857318410e4459ff49fb81d669aeee4e9d7a05e81e7bc8a1aa67b75d35c2b',
}
EXPECTED_IDS = frozenset(
    [f'SA-{n}' for n in range(1, 16) if n != 9]
    + [f'{prefix}-{n}' for prefix, end in [('UA', 2), ('AP', 2), ('P', 5),
                                         ('ST', 6), ('AE', 7), ('FFWT', 5)]
    for n in range(1, end + 1)])
# Test fixtures replace these pinned-source expectations, not the parser.
EXPECTED_FILE_COUNT = 2539
EXPECTED_MODEL_COUNT = 279
FAMILY = re.compile(r'^(?:CASE\s*-\s*)?(SA|UA|AP|P|ST|AE|FFWT)[\s-]*(\d+)(?:\D|$)')
DRIVERS = {'.sh': 'shell_driver_candidate', '.m': 'matlab_analysis_or_generation',
           '.py': 'python_analysis_or_generation'}
GRAPHICS = {'.fig', '.png', '.svg', '.eps', '.ps'}
TABLES = {'.txt', '.csv', '.dat', '.mat', '.xlsx', '.xlsx#', '.ods', '.t',
          '.temp', '.txttheta', '.e00', '.rom', '.f1', '.f06', '.bl'}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def pin(path, root):
    data = path.read_bytes()
    return {'path': str(path.relative_to(root)), 'bytes': len(data), 'sha256': digest(data)}


def discover_cases(tree):
    """Discover top-level family directories, rejecting ambiguous duplicate IDs.

    Matching is not restricted to today's expected IDs or hardcoded path depths:
    an added family must appear in the accounting, then fail the revision check.
    Nested folders under a recognized family belong to that family.
    """
    found = []
    for row in sorted(tree['tree'], key=lambda r: (len(PurePosixPath(r['path']).parts), r['path'])):
        if row['type'] != 'tree':
            continue
        path = row['path']
        if any(path.startswith(c['path'] + '/') for c in found):
            continue
        match = FAMILY.match(PurePosixPath(path).name)
        if match:
            case_id = f'{match[1]}-{int(match[2])}'
            if any(c['id'] == case_id for c in found):
                raise ValueError(f'Duplicate family identifier: {case_id}')
            found.append({'id': case_id, 'path': path, 'name': PurePosixPath(path).name})
    return sorted(found, key=lambda c: c['path'])


def _sources(root):
    base = root / '.reference/isae-validation'
    loaded = {}
    for name, expected in SOURCE_PINS.items():
        data = (base / name).read_bytes()
        if digest(data) != expected:
            raise ValueError(f'Pinned source metadata hash mismatch: {name}')
        loaded[name] = json.loads(data)
    manifest, tree = loaded['manifest.json'], loaded['upstream-tree.json']
    if (manifest['revision'] != REVISION or tree['sha'] != REVISION
            or manifest['repository'] != REPOSITORY or tree.get('truncated') is not False):
        raise ValueError('Source revision/repository mismatch or truncated upstream tree')
    blobs = {r['path']: r for r in tree['tree'] if r['type'] == 'blob'}
    if set(blobs) != set(manifest['files']):
        raise ValueError('Manifest and tree do not enumerate identical source files')
    for name, record in manifest['files'].items():
        rel = PurePosixPath(name)
        if rel.is_absolute() or '..' in rel.parts:
            raise ValueError(f'Unsafe source path: {name}')
        row = blobs[name]
        if record['bytes'] != row['size'] or record['git_blob_sha1'] != row['sha']:
            raise ValueError(f'Manifest/tree length or Git object mismatch: {name}')
    if len(blobs) != EXPECTED_FILE_COUNT:
        raise ValueError(f'Pinned file count mismatch: {len(blobs)}')
    return base / REVISION, manifest, tree


def _file_record(cache, name, spec):
    path = cache / name
    try:
        info = path.stat()
    except OSError:
        info = None
    present = info is not None and S_ISREG(info.st_mode)
    actual_bytes = info.st_size if present else None
    return {'path': name, 'sha256': spec['sha256'], 'bytes': spec['bytes'],
            'present': present, 'actual_bytes': actual_bytes,
            'availability': 'missing' if not present else
                            ('size_mismatch' if actual_bytes != spec['bytes'] else 'present'),
            'hash_status': 'not_checked'}


def _model_record(cache, record, spec, parsed_contents=None):
    result = dict(record)
    result['parse'] = {'status': 'not_attempted', 'policy': 'natural-v1'}
    if not record['present']:
        result['hash_status'] = 'missing'
        return result
    data = (cache / record['path']).read_bytes()
    actual_sha = digest(data)
    blob = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
    result.update(actual_sha256=actual_sha, actual_git_blob_sha1=blob)
    if (actual_sha != spec['sha256'] or len(data) != spec['bytes']
            or blob != spec['git_blob_sha1']):
        result['hash_status'] = 'mismatch'
        return result
    result['hash_status'] = 'verified'
    # Only reuse current-invocation parsing after this individual file passes
    # both original hashes and its length check. Raw-byte identity preserves
    # BOM/newline differences. No persisted parse cache or retained model object.
    if parsed_contents is not None and actual_sha in parsed_contents:
        result['parse'] = deepcopy(parsed_contents[actual_sha])
        return result
    try:
        # Decode without newline conversion and restore a possible UTF-8 BOM
        # when checking the exact source bytes, not just equal Python strings.
        literal = data.decode('utf-8-sig')
        model = parse_asw(literal)
        dumped = model.dumps()
        restored = (b'\xef\xbb\xbf' if data.startswith(b'\xef\xbb\xbf') else b'') + dumped.encode('utf-8')
        result['parse'].update(status='parsed' if restored == data else 'roundtrip_mismatch',
                               lossless_bytes=restored == data,
                               diagnostics=model.diagnostics, beams=len(model.beams))
    except Exception as exc:
        result['parse'].update(status='rejected', error_type=type(exc).__name__, error=str(exc))
    if parsed_contents is not None:
        parsed_contents[actual_sha] = deepcopy(result['parse'])
    return result


def classify_file(name, header):
    """Return a source role and conservative candidate type from actual headers."""
    suffix = PurePosixPath(name).suffix.lower()
    if suffix == '.asw':
        return 'model', 'literal_asw'
    if suffix in DRIVERS:
        return 'driver', DRIVERS[suffix]
    if suffix in {'.set', '.asv', '.bdf'}:
        return 'setup', {'.set': 'aswing_settings_candidate', '.asv': 'model_backup_candidate',
                         '.bdf': 'other_solver_input_candidate'}[suffix]
    text = header.decode('utf-8', errors='replace')
    # Prefer more specific modal exports over their embedded Eigenvalue label.
    if 'Control variable influence-matrix' in text and 'Eigenvalue:' in text:
        return 'reference_candidate', 'aswing_reduced_order_header'
    if re.search(r'#\s*Op\.Point\s*:\s*\d+\s+Mode\s*:', text):
        return 'reference_candidate', 'aswing_eigenvector_header'
    if re.search(r'#\s*Operating point sequence', text):
        return 'reference_candidate', 'aswing_operating_sequence_header'
    if re.search(r'#\s*Op\.Point\s+Eigenvalue', text):
        return 'reference_candidate', 'aswing_eigenvalues_header'
    if 'Mass and Inertia tensors in body axes' in text:
        return 'reference_candidate', 'aswing_force_matrix_header'
    if re.search(r'Op\.Point\s*:\s*\d+', text) and re.search(r'(Surface|Body)\s+Beam', text):
        return 'reference_candidate', 'aswing_span_dump_header'
    if suffix == '.fig':
        return 'reference_candidate', 'matlab_figure_contents_unreviewed'
    if suffix in GRAPHICS:
        return 'reference_candidate', 'plot_contents_unreviewed'
    if suffix == '.pdf':
        return 'reference_candidate', 'document_contents_unreviewed'
    if suffix in TABLES or suffix.startswith(('.evec', '.fmat')):
        if re.search(r'\bXFOIL\b', text, re.I):
            kind = 'other_solver_xfoil_header'
        elif re.search(r'\bNASTRAN\b', text, re.I):
            kind = 'other_solver_nastran_header'
        else:
            kind = 'unknown_data_candidate'
        return 'reference_candidate', kind
    if PurePosixPath(name).name == '.DS_Store':
        return 'ancillary', 'filesystem_metadata'
    if suffix in {'.md', '.pdf_tex'}:
        return 'documentation', 'text_document'
    # Unrecognized extensions and extensionless files remain visible candidates.
    return 'reference_candidate', 'unknown_file_candidate'


def _historical(root, case_id):
    records = []
    for filename in ['isae-suite-inventory.json', 'isae-coverage.json']:
        path = root / 'docs/validation' / filename
        if path.is_file():
            data = json.loads(path.read_text())
            for row in data.get('cases', []):
                if row.get('id') == case_id:
                    records.append({'source': pin(path, root), 'record': row,
                                    'scope': 'historical_metadata_not_reexecuted'})
    path = root / 'docs/validation/isae-aswing-reference-status.md'
    if path.is_file():
        rows = [{'line': i, 'text': line} for i, line in enumerate(path.read_text().splitlines(), 1)
                if line.startswith('| ') and re.search(r'(?<![A-Z0-9-])' + re.escape(case_id) + r'(?![0-9])', line)]
        if rows:
            records.append({'source': pin(path, root), 'rows': rows,
                            'scope': 'published_claim_not_reexecuted'})
    return records


def _blockers(case):
    blockers = []
    def add(code, scope, detail, paths=None):
        item = {'code': code, 'scope': scope, 'detail': detail}
        if paths:
            item['paths'] = paths
        blockers.append(item)
    if not case['models']:
        add('NO_LITERAL_MODEL', 'model_replay',
            'No original .asw in this family; component/data comparisons may still be possible.')
    for status in ['missing', 'mismatch']:
        paths = [m['path'] for m in case['models'] if m['hash_status'] == status]
        if paths:
            add('MODEL_' + status.upper(), 'model_replay', 'Original model integrity check failed.', paths)
    rejected = [m['path'] for m in case['models'] if m['parse']['status'] != 'parsed'
                and m['hash_status'] == 'verified']
    if rejected:
        add('LITERAL_IMPORT_UNRESOLVED', 'affected_models',
            'See each model diagnostic; other variants in this family may import.', rejected)
    missing = [f['path'] for f in case['files'] if f['availability'] != 'present']
    if missing:
        add('SOURCE_FILE_UNAVAILABLE_OR_WRONG_SIZE', 'source_integrity',
            'Original files are missing or differ in length.', missing)
    if not any(r['classification'].startswith('aswing_') for r in case['reference_candidates']):
        add('NO_NATIVE_EXPORT_HEADER_IDENTIFIED', 'reference_decoding',
            'This header scan proves no absence of archived values in figures, tables or documents.')
    add('PAIRINGS_NOT_ESTABLISHED_BY_CATALOG', 'inventory_only',
        'Model/driver/output/operating-settings pairings need an explicit comparison adapter; names are not proof.')
    return blockers


def build_catalog(root):
    root = Path(root).resolve()
    cache, manifest, tree = _sources(root)
    cases = discover_cases(tree)
    ids = {c['id'] for c in cases}
    if ids != EXPECTED_IDS:
        raise ValueError(f'Family accounting mismatch: missing={sorted(EXPECTED_IDS-ids)}, extra={sorted(ids-EXPECTED_IDS)}')
    models, files = [], []
    parsed_contents = {}
    for name, spec in sorted(manifest['files'].items()):
        record = _file_record(cache, name, spec)
        header = b''
        if record['present'] and PurePosixPath(name).suffix.lower() not in {'.asw', *DRIVERS}:
            with (cache / name).open('rb') as stream:
                header = stream.read(8192)
        role, classification = classify_file(name, header)
        record.update(role=role, classification=classification)
        if role == 'model':
            record = _model_record(cache, record, spec, parsed_contents)
            models.append(record)
        elif role == 'reference_candidate':
            record.update(paired=False, comparison_status='unpaired',
                          header_probe_bytes=len(header), header_probe_sha256=digest(header),
                          classification_basis='first_8192_bytes_and_file_format_only',
                          source_values_verified=False)
        files.append(record)
    if len(models) != EXPECTED_MODEL_COUNT:
        raise ValueError(f'Model accounting mismatch: {len(models)}')
    assigned = set()
    for case in cases:
        members = [f for f in files if f['path'].startswith(case['path'] + '/')]
        assigned.update(f['path'] for f in members)
        case.update(files=members,
                    models=[f for f in members if f['role'] == 'model'],
                    reference_candidates=[f for f in members if f['role'] == 'reference_candidate'],
                    drivers=[f for f in members if f['role'] == 'driver'],
                    setup_candidates=[f for f in members if f['role'] == 'setup'],
                    historical_evidence=_historical(root, case['id']),
                    comparison_status='not_executed_by_inventory')
        case['counts'] = {'files': len(members), 'models': len(case['models']),
                          'drivers': len(case['drivers']), 'reference_candidates': len(case['reference_candidates']),
                          'native_header_candidates': sum(f['classification'].startswith('aswing_') for f in case['reference_candidates']),
                          'parse': dict(Counter(m['parse']['status'] for m in case['models']))}
        case['blockers'] = _blockers(case)
    unassigned = [f for f in files if f['path'] not in assigned]
    bad_integrity = [m for m in models if m['hash_status'] != 'verified']
    unavailable = [f for f in files if f['availability'] != 'present']
    readme = cache / 'README.md'
    absent = []
    if 'SA-9' not in ids:
        lines = readme.read_text().splitlines() if readme.is_file() else []
        evidence = [{'line': i, 'text': line} for i, line in enumerate(lines, 1) if 'SA-9' in line]
        absent.append({'id': 'SA-9', 'status': 'absent_from_pinned_tree',
                       'counted_as_family': False, 'source_path': 'README.md', 'evidence': evidence})
    return {
        'schema_version': 1, 'repository': REPOSITORY, 'revision': REVISION,
        'scope': 'Complete source inventory and fresh default-policy literal parsing; no solves or reference comparisons.',
        'status': 'FAIL_SOURCE_INTEGRITY' if bad_integrity or unavailable else 'PASS_INVENTORY_ACCOUNTING',
        'acceptance_target': 'Archived tested ASWING outputs; experimental agreement is optional.',
        'full_suite_validated': False, 'physical_solves': 0,
        'sources': [pin(cache.parent / name, root) for name in SOURCE_PINS],
        'kernel_modules': {p.name: digest(p.read_bytes()) for p in sorted((root / 'openswing').glob('*.py'))},
        'counts': {'families': len(cases), 'files': len(files), 'models': len(models),
                   'family_models': sum(len(c['models']) for c in cases),
                   'supplemental_models': sum(f['role'] == 'model' for f in unassigned),
                   'model_hashes_verified': len(models) - len(bad_integrity),
                   'parse': dict(Counter(m['parse']['status'] for m in models)),
                   'unavailable_files': len(unavailable), 'unassigned_files': len(unassigned)},
        'verification_limits': ['All original .asw bytes checked against SHA256, Git blob SHA1 and length.',
                                'Other files checked for presence/length; header probes do not verify full file hashes.',
                                'Import success is not solver support or reference agreement.',
                                'Reference candidates remain unpaired; all historical evidence is unexecuted here.'],
        'absent_families': absent, 'cases': cases, 'models': models,
        'supplemental_models': [f for f in unassigned if f['role'] == 'model'],
        'unassigned_files': unassigned,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    # Legacy scientific reports are inputs, never destinations for this catalog.
    protected = {args.root.resolve() / 'docs/validation' / n for n in
                 ['isae-suite-inventory.json', 'isae-coverage.json']}
    if args.output.resolve() in protected:
        parser.error('Refusing to overwrite a legacy inventory or coverage report')
    result = build_catalog(args.root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    print(json.dumps({'status': result['status'], **result['counts']}))
    return 0 if result['status'] == 'PASS_INVENTORY_ACCOUNTING' else 1


if __name__ == '__main__':
    raise SystemExit(main())
