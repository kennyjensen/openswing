"""The runnable app and source builds do not depend on optional raw evidence."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import runpy
from zipfile import ZipFile


SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'


def run(root, script, *args):
    subprocess.run([sys.executable, str(root / 'scripts' / script), *args], cwd=root, check=True, capture_output=True)


def fixture(root):
    for directory in ('scripts', 'openswing', 'tests/fixtures', 'docs/validation/nested', 'public'):
        (root / directory).mkdir(parents=True, exist_ok=True)
    for name in ('distribution.py', 'package-source.py', 'package-local.py'):
        shutil.copyfile(SCRIPTS / name, root / 'scripts' / name)
    (root / 'openswing/__init__.py').write_text('value = 17\n')
    (root / 'README.md').write_text('Source instructions\n')
    (root / 'docs/validation/summary.json').write_text('{"status":"partial"}\n')
    archives = {}
    for name in ('docs/validation/one.zip', 'docs/validation/nested/two.zip', 'tests/fixtures/required.zip'):
        path = root / name
        with ZipFile(path, 'w') as archive:
            archive.writestr('values.txt', name)
        archives[name] = path.read_bytes()
    return archives


def test_separate_archives_preserve_sources_runtime_and_all_raw_bytes(tmp_path):
    raw = fixture(tmp_path)
    run(tmp_path, 'package-source.py', '--include-validation')
    metadata = json.loads((tmp_path / 'public/distribution.json').read_text())
    assert metadata['validation']['archives'] == metadata['validation']['catalog_archives'] == 2
    catalog = json.loads((tmp_path / 'docs/validation/archive-index.json').read_text())['archives']
    with ZipFile(tmp_path / 'public/openswing-source.zip') as source, ZipFile(tmp_path / 'public/openswing-validation.zip') as evidence:
        assert source.read('openswing/openswing/__init__.py') == b'value = 17\n'
        assert source.read('openswing/tests/fixtures/required.zip') == raw['tests/fixtures/required.zip']
        assert source.read('openswing/docs/validation/summary.json') == b'{"status":"partial"}\n'
        for name in catalog:
            assert 'openswing/' + name not in source.namelist()
            assert evidence.read('openswing/' + name) == raw[name] == (tmp_path / name).read_bytes()
            assert catalog[name] == dict(bytes=len(raw[name]), sha256=hashlib.sha256(raw[name]).hexdigest())
    for item in ('source', 'validation'):
        data = (tmp_path / 'public' / metadata[item]['file']).read_bytes()
        assert metadata[item]['sha256'] == hashlib.sha256(data).hexdigest()
        assert metadata[item]['bytes'] == len(data)
    before = {p.name: p.read_bytes() for p in (tmp_path / 'public').iterdir()}
    run(tmp_path, 'package-source.py', '--include-validation')
    assert before == {p.name: p.read_bytes() for p in (tmp_path / 'public').iterdir()}
    shutil.copytree(tmp_path / 'public', tmp_path / 'dist')
    (tmp_path / 'dist/runtime').mkdir()
    (tmp_path / 'dist/index.html').write_text('<p>Local app</p>')
    (tmp_path / 'dist/runtime/python_stdlib.zip').write_bytes(b'required runtime archive')
    run(tmp_path, 'package-local.py')
    first = (tmp_path / 'dist/openswing-local.zip').read_bytes()
    with ZipFile(tmp_path / 'dist/openswing-local.zip') as local:
        assert 'openswing-validation.zip' not in local.namelist()
        assert local.read('runtime/python_stdlib.zip') == b'required runtime archive'
        assert local.read('openswing-source.zip') == before['openswing-source.zip']
        local_metadata = json.loads(local.read('distribution.json'))
        assert local_metadata == dict(metadata, kind='local', validation=None)
        assert json.loads((tmp_path / 'dist/distribution.json').read_text()) == metadata
    run(tmp_path, 'package-local.py')
    assert first == (tmp_path / 'dist/openswing-local.zip').read_bytes()


def test_source_only_rebuild_keeps_missing_catalog_and_reports_partial_availability(tmp_path):
    raw = fixture(tmp_path)
    run(tmp_path, 'package-source.py', '--include-validation')
    catalog = (tmp_path / 'docs/validation/archive-index.json').read_bytes()
    with ZipFile(tmp_path / 'public/openswing-source.zip') as source:
        source.extractall(tmp_path / 'extracted')
    checkout = tmp_path / 'extracted/openswing'
    (checkout / 'public').mkdir()
    (checkout / 'public/openswing-validation.zip').write_bytes(b'obsolete generated download')
    run(checkout, 'package-source.py', '--include-validation')
    assert json.loads((checkout / 'public/distribution.json').read_text())['validation'] is None
    assert not (checkout / 'public/openswing-validation.zip').exists()
    assert (checkout / 'docs/validation/archive-index.json').read_bytes() == catalog
    name = 'docs/validation/one.zip'
    (checkout / name).write_bytes(raw[name])
    run(checkout, 'package-source.py', '--include-validation')
    metadata = json.loads((checkout / 'public/distribution.json').read_text())
    assert metadata['validation']['archives'] == 1 and metadata['validation']['catalog_archives'] == 2
    assert (checkout / 'docs/validation/archive-index.json').read_bytes() == catalog
    with ZipFile(checkout / 'public/openswing-validation.zip') as evidence:
        assert evidence.read('openswing/' + name) == raw[name]
        assert 'openswing/docs/validation/nested/two.zip' not in evidence.namelist()


def test_normal_build_never_reads_optional_archives_and_removes_stale_download(tmp_path, monkeypatch):
    raw = fixture(tmp_path)
    run(tmp_path, 'package-source.py', '--include-validation')
    catalog = (tmp_path / 'docs/validation/archive-index.json').read_bytes()
    protected = {(tmp_path / name).resolve() for name in raw if name.startswith('docs/validation/')}
    original_open = Path.open

    def protected_open(path, *args, **kwargs):
        assert path.resolve() not in protected, 'Normal build must not read or rewrite raw validation bytes'
        return original_open(path, *args, **kwargs)

    monkeypatch.chdir(tmp_path)
    monkeypatch.syspath_prepend(str(SCRIPTS))
    script = runpy.run_path(str(SCRIPTS / 'package-source.py'))
    with monkeypatch.context() as guarded:
        guarded.setattr(Path, 'open', protected_open)
        script['build_source']()

    assert not (tmp_path / 'public/openswing-validation.zip').exists()
    assert json.loads((tmp_path / 'public/distribution.json').read_text())['validation'] is None
    assert (tmp_path / 'docs/validation/archive-index.json').read_bytes() == catalog
    for name, contents in raw.items():
        assert (tmp_path / name).read_bytes() == contents
    with ZipFile(tmp_path / 'public/openswing-source.zip') as source:
        assert source.read('openswing/tests/fixtures/required.zip') == raw['tests/fixtures/required.zip']
        assert source.read('openswing/openswing/__init__.py') == b'value = 17\n'
        assert source.read('openswing/docs/validation/summary.json') == b'{"status":"partial"}\n'
        assert all('openswing/' + name not in source.namelist() for name in raw if name.startswith('docs/validation/'))
    # A later explicit build recovers the optional download from unchanged inputs.
    run(tmp_path, 'package-source.py', '--include-validation')
    assert json.loads((tmp_path / 'public/distribution.json').read_text())['validation']['archives'] == 2
