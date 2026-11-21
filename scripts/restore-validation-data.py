#!/usr/bin/env python3
"""Restore byte-identical validation records from optional chunked gzip transport.

Install as scripts/restore-validation-data.py and run before source packaging.
No transport manifest means a normal source download: leave every file alone.
"""
import argparse
import gzip
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import tempfile


FORMAT = 'openswing-validation-source-transport'
PART_LIMIT = 512 * 1024
SHA = re.compile(r'[0-9a-f]{64}\Z')
PART = re.compile(r'data-[0-9]{4,}\.part-[0-9]{5,}\Z')
EXACT_EXTRA_PATHS = {
    'docs/STATUS.md',
    'tests/fixtures/hinge-history/history/owned-v2-release-400-0.35-0.02-order2.json',
}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def digest_file(path):
    total = 0
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            total += len(block)
            digest.update(block)
    return {'bytes': total, 'sha256': digest.hexdigest()}


def check_pin(record, *, part=False):
    require(type(record.get('bytes')) is int and record['bytes'] >= 0, 'Invalid byte count')
    require(isinstance(record.get('sha256'), str) and SHA.fullmatch(record['sha256']), 'Invalid SHA-256')
    if part:
        require(0 < record['bytes'] <= PART_LIMIT, 'Transport part exceeds 512 KiB or is empty')


def relative_record_path(name):
    require(isinstance(name, str) and '\\' not in name and ':' not in name and
            all(ord(c) >= 32 for c in name), 'Invalid record path')
    parts = name.split('/')
    require(all(p not in ('', '.', '..', '.source-data') for p in parts) and
            ((len(parts) >= 3 and parts[:2] == ['docs', 'validation']) or name in EXACT_EXTRA_PATHS),
            'Record must be below docs/validation or one of two exact additional paths')
    require(not PurePosixPath(name).is_absolute() and not name.lower().endswith('.zip'),
            'Raw ZIP archives are not source records')
    return parts


def safe_target(root, parts):
    target = root.joinpath(*parts)
    current = root
    for part in parts:
        current = current / part
        require(not current.is_symlink(), f'Symlink path forbidden: {current}')
    require(target.resolve().is_relative_to(root), f'Path escapes root: {target}')
    if target.exists():
        require(target.is_file(), f'Target is not a regular file: {target}')
    return target


class VerifiedChunks(io.RawIOBase):
    def __init__(self, folder, parts, expected):
        super().__init__()
        self.folder, self.parts, self.expected = folder, parts, expected
        self.index = 0
        self.stream = None
        self.part_hash = None
        self.part_bytes = 0
        self.total_hash = hashlib.sha256()
        self.total_bytes = 0
        self.complete = False

    def readable(self):
        return True

    def readinto(self, buffer):
        if self.complete:
            return 0
        if self.stream is None:
            if self.index == len(self.parts):
                require({'bytes': self.total_bytes, 'sha256': self.total_hash.hexdigest()} == self.expected,
                        'Combined gzip stream checksum mismatch')
                self.complete = True
                return 0
            item = self.parts[self.index]
            path = self.folder / item['name']
            require(path.is_file() and not path.is_symlink(), f'Missing or unsafe part: {path}')
            require(path.stat().st_size == item['bytes'], f'Part size mismatch: {path}')
            self.stream = path.open('rb')
            self.part_hash = hashlib.sha256()
            self.part_bytes = 0
        count = self.stream.readinto(buffer)
        if count:
            data = memoryview(buffer)[:count]
            self.part_hash.update(data)
            self.total_hash.update(data)
            self.part_bytes += count
            self.total_bytes += count
            return count
        item = self.parts[self.index]
        self.stream.close()
        self.stream = None
        require({'bytes': self.part_bytes, 'sha256': self.part_hash.hexdigest()} ==
                {k: item[k] for k in ('bytes', 'sha256')}, f'Part checksum mismatch: {item["name"]}')
        self.index += 1
        return self.readinto(buffer)

    def close(self):
        if self.stream is not None:
            self.stream.close()
        super().close()


def restore(root):
    root = Path(root).resolve()
    folder = root / 'docs/validation/.source-data'
    manifest_path = folder / 'manifest.json'
    for parent in (root / 'docs', root / 'docs/validation', folder):
        require(not parent.is_symlink(), f'Symlink transport folder: {parent}')
    if not manifest_path.exists():
        return {'status': 'NO_TRANSPORT_MANIFEST', 'restored': 0, 'already_correct': 0, 'files': []}
    require(manifest_path.is_file() and not manifest_path.is_symlink(), 'Unsafe manifest')
    manifest = json.loads(manifest_path.read_text())
    require(manifest.get('format') == FORMAT and manifest.get('version') == 1 and
            manifest.get('compression') == 'gzip' and manifest.get('part_bytes_limit') == PART_LIMIT,
            'Unsupported transport manifest')
    entries = manifest.get('files')
    require(isinstance(entries, list), 'Manifest files must be a list')
    records, names, part_names = [], set(), set()
    for entry in entries:
        check_pin(entry)
        name = entry.get('path')
        parts = relative_record_path(name)
        require(name not in names, f'Duplicate destination: {name}')
        names.add(name)
        check_pin(entry.get('gzip', {}))
        chunks = entry.get('parts')
        require(isinstance(chunks, list) and chunks, 'Missing transport parts')
        for part in chunks:
            check_pin(part, part=True)
            name_part = part.get('name')
            require(isinstance(name_part, str) and PART.fullmatch(name_part), 'Unsafe transport part name')
            require(name_part not in part_names, f'Duplicate part: {name_part}')
            part_names.add(name_part)
        require(sum(p['bytes'] for p in chunks) == entry['gzip']['bytes'], 'Compressed byte count mismatch')
        records.append((entry, safe_target(root, parts)))
    result = {'status': 'PASS_RESTORED_VALIDATION_DATA', 'restored': 0, 'already_correct': 0, 'files': []}
    for entry, target in records:
        original_pin = {k: entry[k] for k in ('bytes', 'sha256')}
        if target.is_file() and digest_file(target) == original_pin:
            result['already_correct'] += 1
            result['files'].append({'path': entry['path'], 'status': 'ALREADY_CORRECT'})
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(prefix='.' + target.name + '.', suffix='.restore-tmp',
                                             dir=target.parent, delete=False) as output:
                temporary = Path(output.name)
                digest = hashlib.sha256()
                total = 0
                with VerifiedChunks(folder, entry['parts'], entry['gzip']) as chunks:
                    with io.BufferedReader(chunks) as buffered:
                        with gzip.GzipFile(fileobj=buffered, mode='rb') as decoded:
                            for block in iter(lambda: decoded.read(1024 * 1024), b''):
                                total += len(block)
                                require(total <= entry['bytes'], f'Decompressed size exceeds manifest: {target}')
                                digest.update(block)
                                output.write(block)
                        require(not buffered.read(1), 'Unconsumed compressed data')
                        require(chunks.complete, 'Transport checksum incomplete')
                require({'bytes': total, 'sha256': digest.hexdigest()} == original_pin,
                        f'Restored original checksum mismatch: {target}')
                output.flush()
                os.fsync(output.fileno())
            os.chmod(temporary, 0o644)
            os.replace(temporary, target)
            temporary = None
            result['restored'] += 1
            result['files'].append({'path': entry['path'], 'status': 'RESTORED', **original_pin})
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    result = restore(args.root)
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
