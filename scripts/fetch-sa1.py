"""Fetch pinned SA-1 inputs and published data into the unshipped reference cache.

No downloaded script is executed. Existing files must match the recorded bytes.
"""
import hashlib
import json
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]


def checked_bytes(name, spec, data):
    if len(data) != spec['bytes'] or hashlib.sha256(data).hexdigest() != spec['sha256']:
        raise ValueError(f'{name}: reference size or SHA-256 mismatch')
    blob = b'blob ' + str(len(data)).encode() + b'\0' + data
    if hashlib.sha1(blob).hexdigest() != spec['git_blob_sha1']:
        raise ValueError(f'{name}: Git blob mismatch')
    return data


def main():
    manifest = json.loads((ROOT/'docs/validation/sa1-sources.json').read_text())
    target = ROOT/'.reference/isae-sa1'
    target.mkdir(parents=True, exist_ok=True)
    for name, spec in manifest['files'].items():
        if Path(name).name != name:
            raise ValueError('Reference names must be basenames')
        path = target/name
        if path.exists():
            checked_bytes(name, spec, path.read_bytes())
            print(f'Verified {name}', flush=True)
        else:
            with urlopen(spec['url'], timeout=60) as response:
                data = checked_bytes(name, spec, response.read())
            temporary = path.with_suffix(path.suffix+'.part')
            temporary.write_bytes(data)
            temporary.replace(path)
            print(f'Fetched and verified {name}', flush=True)


if __name__ == '__main__':
    main()
