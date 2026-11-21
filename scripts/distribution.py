"""Deterministic, bounded-memory distribution files and content checksums."""
import hashlib
import os
from pathlib import Path
from shutil import copyfileobj
import tempfile
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED, ZIP_STORED


def checksum(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def entry(name, size=0):
    info = ZipInfo(name, (2026, 1, 1, 0, 0, 0))
    info.compress_type = ZIP_STORED if Path(name).suffix in ('.zip', '.whl') else ZIP_DEFLATED
    info.external_attr = 0o100644 << 16
    info.file_size = size
    return info


def package(destination, files, extra=None):
    """Replace the finished archive atomically; never buffer large members."""
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=destination.name + '.', suffix='.tmp', dir=destination.parent)
    os.close(descriptor)
    try:
        with ZipFile(temporary, 'w', ZIP_DEFLATED) as archive:
            for name, path in sorted(files):
                path = Path(path)
                with path.open('rb') as source, archive.open(entry(name, path.stat().st_size), 'w', force_zip64=True) as target:
                    copyfileobj(source, target, length=1024 * 1024)
            for name, data in sorted((extra or {}).items()):
                archive.writestr(entry(name), data)
        os.replace(temporary, destination)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def description(path):
    path = Path(path)
    return dict(file=path.name, bytes=path.stat().st_size, sha256=checksum(path))
