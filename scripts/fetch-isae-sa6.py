"""Fetch the two SHA-pinned public-use NASA reports for SA-6."""
from pathlib import Path
import hashlib,json,urllib.request
ROOT=Path(__file__).resolve().parents[1]

def main():
    manifest=json.loads((ROOT/'docs/validation/isae-sa6-sources.json').read_text())['primary_manifest']
    folder=ROOT/'.reference/isae-sa6';folder.mkdir(parents=True,exist_ok=True)
    for entry in manifest:
        path=folder/f"naca-tr-{entry['report']}.pdf"
        data=path.read_bytes() if path.exists() else urllib.request.urlopen(entry['url'],timeout=60).read()
        assert hashlib.sha256(data).hexdigest()==entry['sha256'],entry['report']
        if not path.exists():path.write_bytes(data)
    (folder/'primary-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print('Verified two primary NASA reports')

if __name__=='__main__':main()
