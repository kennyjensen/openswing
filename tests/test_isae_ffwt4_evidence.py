"""Historical-kernel attribution and compressed evidence must fail closed."""
import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('ffwt4_evidence', ROOT/'scripts/isae_ffwt4_evidence.py')
evidence = importlib.util.module_from_spec(spec)
spec.loader.exec_module(evidence)


def archive(tmp_path):
    original = tmp_path/'original/openswing'
    saved = tmp_path/'snapshot/openswing'
    original.mkdir(parents=True)
    saved.mkdir(parents=True)
    entries = []
    for name in ['__init__.py', 'kernel.py']:
        (original/name).write_text('# authenticated source\n')
        (saved/name).write_bytes((original/name).read_bytes())
        entries.append(dict(original=evidence.pin(original/name), archived=str(saved/name)))
    manifest = saved.parent/'manifest.json'
    evidence.write(manifest, dict(files=entries))
    expected = [v['original'] for v in entries]
    return manifest, expected, original, saved


def test_changed_worktree_uses_only_the_exact_archived_kernel(tmp_path):
    manifest, expected, original, saved = archive(tmp_path)
    (original/'kernel.py').write_text('# legitimate later production change\n')
    checked = evidence.KernelArchive(manifest, expected)
    assert checked.verify(expected[1]) == evidence.pin(saved/'kernel.py')
    with pytest.raises(ValueError, match='Conflicting'):
        checked.verify(evidence.pin(original/'kernel.py'))
    (saved/'kernel.py').write_text('# corrupted archive\n')
    with pytest.raises(ValueError, match='Changed archived'):
        checked.verify(expected[1])


@pytest.mark.parametrize('change', ['contents', 'missing', 'extra', 'outside', 'duplicate', 'original_pin'])
def test_incomplete_or_changed_archive_cannot_start_a_solve(tmp_path, change):
    manifest, expected, _, saved = archive(tmp_path)
    data = evidence.read(manifest)
    if change == 'contents':
        (saved/'kernel.py').write_text('# changed\n')
    if change == 'missing':
        (saved/'kernel.py').unlink()
    if change == 'extra':
        (saved/'shadow.py').write_text('# undeclared import\n')
    if change == 'outside':
        data['files'][1]['archived'] = data['files'][1]['original']['path']
    if change == 'duplicate':
        data['files'].append(data['files'][1])
        expected.append(expected[1])
    if change == 'original_pin':
        data['files'][1]['original']['sha256'] = '0'*64
    evidence.write(manifest, data)
    with pytest.raises((ValueError, FileNotFoundError)):
        evidence.KernelArchive(manifest, expected)


def test_ordinary_evidence_cannot_be_replaced_by_an_archive_file(tmp_path):
    manifest, expected, _, _ = archive(tmp_path)
    checked = evidence.KernelArchive(manifest, expected)
    result = tmp_path/'result.json'
    evidence.write(result, dict(moment=1.))
    old = evidence.pin(result)
    evidence.write(result, dict(moment=2.))
    with pytest.raises(ValueError, match='Changed evidence'):
        checked.verify(old)


def test_imported_worktree_kernel_is_rejected(tmp_path, monkeypatch):
    manifest, expected, original, saved = archive(tmp_path)
    checked = evidence.KernelArchive(manifest, expected)
    monkeypatch.setitem(sys.modules, 'openswing', SimpleNamespace(__file__=str(original/'__init__.py')))
    with pytest.raises(ValueError, match='before importing'):
        checked.activate()
    with pytest.raises(ValueError, match='outside the archive'):
        checked.loaded_modules()
    monkeypatch.setitem(sys.modules, 'openswing', SimpleNamespace(__file__=str(saved/'__init__.py')))
    assert checked.loaded_modules() == [dict(module='openswing', path=str(saved/'__init__.py'))]


def test_compression_retains_all_values_and_is_deterministic(tmp_path):
    value = dict(samples=[0., -0., 1e-200, 1e200], nested=dict(text='full record', values=list(range(100))))
    first, second = tmp_path/'a.json.gz', tmp_path/'b.json.gz'
    evidence.write(first, value)
    evidence.write(second, value)
    assert first.read_bytes() == second.read_bytes()
    assert evidence.read(first) == value
    assert '-0.0' in __import__('gzip').decompress(first.read_bytes()).decode()
    before = first.read_bytes()
    with pytest.raises(ValueError):
        evidence.write(first, dict(value=float('nan')))
    assert first.read_bytes() == before
