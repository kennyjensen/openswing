"""Fetch the pinned ISAE validation suite into the unshipped reference cache.

All regular files are checked against the Git tree. Downloaded scripts are
reference material only; this program never executes them.
"""
from pathlib import Path, PurePosixPath
from urllib.request import Request, urlopen
import hashlib
import json
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = 'rom1isae/ISAE_Aswing_Experimental_Validation'
REVISION = 'f62943df20e9e4d7d9f50e070477b22426b5f865'
CACHE = ROOT / '.reference/isae-validation' / REVISION


def download(url):
    return urlopen(Request(url, headers={'User-Agent': 'OpenSwing-validation'}), timeout=60)


def checked(data, record):
    digest = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
    if len(data) != record['size'] or digest != record['sha']:
        raise ValueError('Reference content mismatch: ' + record['path'])
    return dict(bytes=len(data), git_blob_sha1=digest, sha256=hashlib.sha256(data).hexdigest())


def main():
    CACHE.mkdir(parents=True, exist_ok=True)
    tree_path = CACHE.parent / 'upstream-tree.json'
    if tree_path.exists():
        tree = json.loads(tree_path.read_text())
    else:
        with download(f'https://api.github.com/repos/{REPOSITORY}/git/trees/{REVISION}?recursive=1') as response:
            tree = json.load(response)
        tree_path.write_text(json.dumps(tree, indent=2) + '\n')
    if tree['sha'] != REVISION or tree.get('truncated'):
        raise ValueError('Incomplete or different reference Git tree')
    records = {row['path']: row for row in tree['tree'] if row['type'] == 'blob'}
    for name in records:
        path = PurePosixPath(name)
        if path.is_absolute() or '..' in path.parts:
            raise ValueError('Unsafe reference path')
    if not all((CACHE / name).is_file() for name in records):
        url = f'https://codeload.github.com/{REPOSITORY}/tar.gz/{REVISION}'
        with tempfile.TemporaryFile() as temporary:
            with download(url) as response:
                while chunk := response.read(1024 * 1024):
                    temporary.write(chunk)
            temporary.seek(0)
            with tarfile.open(fileobj=temporary, mode='r:gz') as archive:
                for member in archive:
                    if not member.isfile():
                        continue
                    name = '/'.join(PurePosixPath(member.name).parts[1:])
                    if name not in records:
                        raise ValueError('Unexpected reference archive member: ' + name)
                    data = archive.extractfile(member).read()
                    checked(data, records[name])
                    destination = CACHE / name
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    destination.write_bytes(data)
    files = {name: checked((CACHE / name).read_bytes(), row) for name, row in records.items()}
    manifest = dict(repository='https://github.com/' + REPOSITORY, revision=REVISION, files=files)
    (CACHE.parent / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(f'Verified {len(files)} files at {REVISION}', flush=True)


if __name__ == '__main__':
    main()
