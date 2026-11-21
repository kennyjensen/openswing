"""Fetch pinned public settings/operating-point inputs into an excluded reference directory."""
import hashlib
import json
from pathlib import Path
from urllib.request import urlopen
ROOT=Path(__file__).resolve().parents[1]
def check(name,spec,data):
    assert len(data)==spec['bytes'],name
    assert hashlib.sha256(data).hexdigest()==spec['sha256'],name
    assert hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()==spec['git_blob_sha1'],name
    return data
if __name__=='__main__':
    manifest=json.loads((ROOT/'docs/validation/legacy-settings-sources.json').read_text())
    target=ROOT/'.reference/legacy-settings-research';target.mkdir(parents=True,exist_ok=True)
    for name,spec in manifest['files'].items():
        if Path(name).name!=name:raise ValueError('Reference names must be basenames.')
        file=target/name
        if file.exists():check(name,spec,file.read_bytes())
        else:
            with urlopen(spec['url'],timeout=60) as response:data=check(name,spec,response.read())
            temporary=file.with_suffix('.part');temporary.write_bytes(data);temporary.replace(file)
        print('Verified',name)
