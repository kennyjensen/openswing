"""Authenticate and execute the fixed FFWT-4 kernel without rewriting old pins."""
import gzip
import hashlib
import io
import json
from pathlib import Path
import sys


def require(condition, message):
    if not condition:
        raise ValueError(message)


def pin(path):
    path = Path(path)
    if not path.is_absolute() or '..' in path.parts:
        path = path.resolve()
    digest = hashlib.sha256()
    size = 0
    with path.open('rb') as stream:
        while block := stream.read(1024*1024):
            digest.update(block)
            size += len(block)
    return dict(path=str(path), bytes=size, sha256=digest.hexdigest())


def read(path):
    path = Path(path)
    opener = gzip.open if path.suffix == '.gz' else open
    with opener(path, 'rt', encoding='utf-8') as stream:
        return json.load(stream)


def write(path, value):
    path = Path(path)
    temporary = path.with_name(path.name+'.partial')
    with temporary.open('wb') as raw:
        if path.suffix == '.gz':
            binary = gzip.GzipFile(filename='', mode='wb', fileobj=raw, mtime=0, compresslevel=1)
        else:
            binary = raw
        with io.TextIOWrapper(binary, encoding='utf-8') as stream:
            json.dump(value, stream, indent=2, allow_nan=False)
            stream.write('\n')
    temporary.replace(path)


class KernelArchive:
    def __init__(self, manifest, expected):
        self.manifest_pin = pin(manifest)
        self.root = Path(self.manifest_pin['path']).parent
        entries = read(manifest)['files']
        require([v['original'] for v in entries] == expected, 'Archive does not match the original kernel pins')
        self.entries = {v['original']['path']: v for v in entries}
        require(len(self.entries) == len(entries), 'Duplicate archived kernel')
        self.runtime_pins = []
        for value in entries:
            original = value['original']
            target = Path(value['archived'])
            require(target == self.root/'openswing'/Path(original['path']).name,
                    'Archived module is outside the declared package')
            actual = pin(target)
            require((actual['bytes'], actual['sha256']) == (original['bytes'], original['sha256']),
                    'Archived module changed: '+str(target))
            self.runtime_pins.append(actual)
        declared = {v['path'] for v in self.runtime_pins}
        require({str(p) for p in (self.root/'openswing').glob('*.py')} == declared,
                'Undeclared or missing archived module')

    def verify(self, record):
        """Return the authenticated physical pin; only exact old kernels map."""
        entry = self.entries.get(record['path'])
        if entry is None:
            actual = pin(record['path'])
            require(actual == record, 'Changed evidence: '+record['path'])
        else:
            require(record == entry['original'], 'Conflicting original kernel pin')
            actual = pin(entry['archived'])
            require((actual['bytes'], actual['sha256']) == (record['bytes'], record['sha256']),
                    'Changed archived evidence: '+actual['path'])
        return actual

    def activate(self):
        require(not any(k == 'openswing' or k.startswith('openswing.') for k in sys.modules),
                'Activate the archive before importing any solver module')
        sys.path.insert(0, str(self.root))

    def loaded_modules(self):
        declared = {v['path'] for v in self.runtime_pins}
        loaded = []
        for name, module in sys.modules.items():
            if name == 'openswing' or name.startswith('openswing.'):
                path = str(Path(module.__file__).absolute())
                require(path in declared, 'Solver module was loaded outside the archive: '+name)
                loaded.append(dict(module=name, path=path))
        require(loaded, 'No archived solver modules were loaded')
        return sorted(loaded, key=lambda v: v['module'])
