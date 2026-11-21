"""Inventory completeness and honest candidate/import states; no physical calls."""
import hashlib
import json
from pathlib import Path, PurePosixPath

import pytest

from scripts import isae_suite_catalog as catalog


SOURCE = b'''Name
Inventory beam
End
Unit
L 1 m
T 1 s
F 1 N
End
Constant
9.81 1.2256 340.21
End
Reference
1 1 2
0 0 0
End
Beam 1 1
Original beam
t y
0 0
2 2
End
'''
SA = '1 - Aerodynamics/SA - Steady Aerodynamics Cases/SA - 1 - Example'
ST = '3 - Structure/CASE - ST1 Example'
P = '2 - Propellers/P - Propeller Cases/P-1 - Component'
UA = '1 - Aerodynamics/UA - Unsteady Cases/UA - 1 - Unknown'
MODEL = SA + '/original.asw'
SUPPLEMENT = '3 - Structure/Mesh_convergence_analysis/original.asw'


@pytest.fixture
def archive(tmp_path, monkeypatch):
    """A small pinned archive preserving the real source metadata schema."""
    entries = {
        MODEL: SOURCE,
        ST + '/original.asw': b'\xef\xbb\xbf' + SOURCE.replace(b'\n', b'\r\n'),
        SUPPLEMENT: SOURCE,
        SA + '/original.sh': b'aswing original.asw\n',
        SA + '/output.txt': b'# Operating point sequence...\n# i t CL\n1 0 1\n',
        P + '/reference.fig': b'MATLAB 5.0 MAT-file, reference contents not decoded',
        UA + '/same-name.txt': b'0 0.1 0.2\n',
        UA + '/unknown.blob': b'\0binary data',
        'README.md': b'Warning: Case number SA-9 has been lost.\n',
    }
    base = tmp_path / '.reference/isae-validation'
    cache = base / catalog.REVISION
    files, tree, directories = {}, [], set()
    for name, data in entries.items():
        path = cache / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        sha1 = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
        files[name] = {'bytes': len(data), 'sha256': catalog.digest(data), 'git_blob_sha1': sha1}
        tree.append({'type': 'blob', 'path': name, 'size': len(data), 'sha': sha1})
        directories.update(str(p) for p in PurePosixPath(name).parents if str(p) != '.')
    tree.extend({'type': 'tree', 'path': p} for p in sorted(directories))
    manifest = {'repository': catalog.REPOSITORY, 'revision': catalog.REVISION, 'files': files}
    metadata = {'manifest.json': manifest,
                'upstream-tree.json': {'sha': catalog.REVISION, 'truncated': False, 'tree': tree}}
    pins = {}
    for name, value in metadata.items():
        data = (json.dumps(value) + '\n').encode()
        (base / name).write_bytes(data)
        pins[name] = catalog.digest(data)
    monkeypatch.setattr(catalog, 'SOURCE_PINS', pins)
    monkeypatch.setattr(catalog, 'EXPECTED_IDS', {'SA-1', 'ST-1', 'P-1', 'UA-1'})
    monkeypatch.setattr(catalog, 'EXPECTED_FILE_COUNT', len(entries))
    monkeypatch.setattr(catalog, 'EXPECTED_MODEL_COUNT', 3)
    return tmp_path, cache, metadata


def test_exhaustive_family_and_supplemental_model_accounting(archive):
    root, _, _ = archive
    result = catalog.build_catalog(root)
    assert result['status'] == 'PASS_INVENTORY_ACCOUNTING'
    assert result['counts']['families'] == 4
    assert result['counts']['models'] == result['counts']['model_hashes_verified'] == 3
    assert result['counts']['family_models'] == 2
    assert result['counts']['supplemental_models'] == 1
    assert result['counts']['parse'] == {'parsed': 3}
    assert all(m['parse']['lossless_bytes'] for m in result['models'])
    assert result['supplemental_models'][0]['path'] == SUPPLEMENT
    all_paths = [f['path'] for c in result['cases'] for f in c['files']]
    all_paths += [f['path'] for f in result['unassigned_files']]
    assert len(all_paths) == len(set(all_paths)) == result['counts']['files']
    assert result['absent_families'][0]['id'] == 'SA-9'
    assert result['absent_families'][0]['counted_as_family'] is False
    assert result == catalog.build_catalog(root)  # resumable planning is deterministic


def test_no_model_does_not_mean_no_reference_and_unknown_is_unpaired(archive):
    root, _, _ = archive
    cases = {c['id']: c for c in catalog.build_catalog(root)['cases']}
    component = cases['P-1']
    assert component['models'] == []
    assert component['reference_candidates'][0]['classification'] == 'matlab_figure_contents_unreviewed'
    assert any(b['code'] == 'NO_LITERAL_MODEL' and b['scope'] == 'model_replay'
               for b in component['blockers'])
    unknown = cases['UA-1']['reference_candidates']
    assert {r['classification'] for r in unknown} == {'unknown_data_candidate', 'unknown_file_candidate'}
    assert all(r['paired'] is False and r['source_values_verified'] is False for r in unknown)
    known = cases['SA-1']['reference_candidates'][0]
    assert known['classification'] == 'aswing_operating_sequence_header'
    assert known['comparison_status'] == 'unpaired'
    assert 'model_path' not in known  # same-name or directory correspondence is no pairing proof


@pytest.mark.parametrize('damage', ['missing', 'same_length_corrupt'])
def test_missing_or_corrupt_original_never_reaches_parser(archive, monkeypatch, damage):
    root, cache, _ = archive
    path = cache / MODEL
    if damage == 'missing':
        path.unlink()
    else:
        path.write_bytes(SOURCE.replace(b'Original beam', b'Corrupt! beam'))
        assert path.stat().st_size == len(SOURCE)
    original_parser = catalog.parse_asw
    parsed = []
    def record_parse(text):
        parsed.append(text)
        return original_parser(text)
    monkeypatch.setattr(catalog, 'parse_asw', record_parse)
    result = catalog.build_catalog(root)
    model = next(m for m in result['models'] if m['path'] == MODEL)
    assert result['status'] == 'FAIL_SOURCE_INTEGRITY'
    assert model['hash_status'] == ('missing' if damage == 'missing' else 'mismatch')
    assert model['parse']['status'] == 'not_attempted'
    assert len(parsed) == 2
    assert result['counts']['models'] == 3  # preserve failed records, never silently drop


def test_parse_failure_is_recorded_not_inventory_or_reference_success(archive, monkeypatch):
    root, _, _ = archive
    def rejected(text):
        raise ValueError('Literal unsupported feature')
    monkeypatch.setattr(catalog, 'parse_asw', rejected)
    result = catalog.build_catalog(root)
    assert result['status'] == 'PASS_INVENTORY_ACCOUNTING'
    assert result['counts']['parse'] == {'rejected': 3}
    assert result['full_suite_validated'] is False
    assert result['models'][0]['parse']['error'] == 'Literal unsupported feature'
    assert any(b['code'] == 'LITERAL_IMPORT_UNRESOLVED' for c in result['cases'] for b in c['blockers'])


def test_identical_bytes_share_only_current_build_parse_results(archive, monkeypatch):
    root, _, _ = archive
    original = catalog.parse_asw
    calls = []
    def tracked(text):
        calls.append(text)
        model = original(text)
        model.diagnostics.append('fixture diagnostic')
        return model
    monkeypatch.setattr(catalog, 'parse_asw', tracked)
    result = catalog.build_catalog(root)
    # Three files, two byte identities. BOM/CRLF input must keep its own exact
    # round-trip check; every file still receives independent hash verification.
    assert len(calls) == 2
    assert result['counts']['model_hashes_verified'] == 3
    assert result['counts']['parse'] == {'parsed': 3}
    records = {m['path']: m for m in result['models']}
    assert records[MODEL]['parse'] == records[SUPPLEMENT]['parse']
    records[MODEL]['parse']['diagnostics'].append('only this record')
    assert records[SUPPLEMENT]['parse']['diagnostics'] == ['fixture diagnostic']

    def changed_parser(text):
        calls.append(text)
        raise ValueError('changed parser result')
    monkeypatch.setattr(catalog, 'parse_asw', changed_parser)
    next_result = catalog.build_catalog(root)
    assert len(calls) == 4  # no cross-build cache, even for unchanged bytes
    assert next_result['counts']['parse'] == {'rejected': 3}
    assert all(m['parse']['error'] == 'changed parser result' for m in next_result['models'])


def test_duplicate_model_integrity_is_checked_before_reusing_parse(archive):
    root, cache, _ = archive
    path = cache / SUPPLEMENT
    path.write_bytes(SOURCE.replace(b'Original beam', b'Corrupt! beam'))
    assert path.stat().st_size == len(SOURCE)
    # MODEL precedes SUPPLEMENT and supplies an otherwise reusable parse result.
    result = catalog.build_catalog(root)
    records = {m['path']: m for m in result['models']}
    assert records[MODEL]['hash_status'] == 'verified'
    assert records[SUPPLEMENT]['hash_status'] == 'mismatch'
    assert records[SUPPLEMENT]['parse']['status'] == 'not_attempted'
    assert result['status'] == 'FAIL_SOURCE_INTEGRITY'


def test_directory_at_file_path_is_still_missing(archive):
    root, cache, _ = archive
    path = cache / MODEL
    path.unlink()
    path.mkdir()
    result = catalog.build_catalog(root)
    model = next(m for m in result['models'] if m['path'] == MODEL)
    assert model['present'] is False and model['actual_bytes'] is None
    assert model['hash_status'] == 'missing' and model['parse']['status'] == 'not_attempted'


def test_historical_parse_claim_does_not_replace_current_diagnostic(archive):
    root, _, _ = archive
    path = root / 'docs/validation/isae-coverage.json'
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({'cases': [{'id': 'SA-1', 'parsed': 0, 'rejected': 99,
                                         'status': 'old_rejection'}]}))
    case = next(c for c in catalog.build_catalog(root)['cases'] if c['id'] == 'SA-1')
    assert case['counts']['parse'] == {'parsed': 1}
    assert case['historical_evidence'][0]['record']['status'] == 'old_rejection'
    assert case['historical_evidence'][0]['scope'] == 'historical_metadata_not_reexecuted'


def test_metadata_corruption_rejected_before_discovery(archive):
    root, _, _ = archive
    path = root / '.reference/isae-validation/upstream-tree.json'
    path.write_text(path.read_text() + ' ')
    with pytest.raises(ValueError, match='metadata hash mismatch'):
        catalog.build_catalog(root)


def test_added_family_cannot_be_silently_omitted(archive, monkeypatch):
    root, _, metadata = archive
    tree = metadata['upstream-tree.json']
    tree['tree'].append({'type': 'tree', 'path': 'new/location/SA - 16 - Added'})
    path = root / '.reference/isae-validation/upstream-tree.json'
    data = json.dumps(tree).encode()
    path.write_bytes(data)
    monkeypatch.setitem(catalog.SOURCE_PINS, 'upstream-tree.json', catalog.digest(data))
    with pytest.raises(ValueError, match=r"extra=\['SA-16'\]"):
        catalog.build_catalog(root)


@pytest.mark.parametrize('header,expected', [
    (b'# Op.Point     Eigenvalue\n1 0 2\n', 'aswing_eigenvalues_header'),
    (b'# Op.Point : 1 Mode: 3\n# Eigenvalue: 0 2\n', 'aswing_eigenvector_header'),
    (b'Calculated polar for XFOIL\n', 'other_solver_xfoil_header'),
    (b'The paper discusses Eigenvalues but is not an ASWING export.\n', 'unknown_data_candidate'),
])
def test_export_headers_distinguish_native_other_solver_and_unknown(header, expected):
    assert catalog.classify_file('same-name.txt', header) == ('reference_candidate', expected)


def test_pinned_original_tree_has_all_41_families_and_one_external_model():
    # Read metadata only; the full 279-model import is a separate catalog run.
    base = Path(__file__).resolve().parents[1] / '.reference/isae-validation'
    if not base.exists():
        pytest.skip('Pinned optional ISAE archive is not installed')
    manifest = json.loads((base / 'manifest.json').read_text())
    tree = json.loads((base / 'upstream-tree.json').read_text())
    cases = catalog.discover_cases(tree)
    assert {c['id'] for c in cases} == catalog.EXPECTED_IDS
    assert len(cases) == 41
    models = [p for p in manifest['files'] if p.endswith('.asw')]
    assert len(models) == 279
    outside = [p for p in models if not any(p.startswith(c['path'] + '/') for c in cases)]
    assert outside == ['3 - Structure/Mesh_convergence_analysis/[0_90]_3s.asw']
