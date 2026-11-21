"""Fetch the pinned primary UIUC tables used by the ISAE P-1 comparison."""
from pathlib import Path
import hashlib
import json
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def main():
    manifest = json.loads((ROOT / 'docs/validation/isae-p1-sources.json').read_text())
    destination = ROOT / '.reference/isae-p1'
    destination.mkdir(parents=True, exist_ok=True)
    for name, entry in manifest['files'].items():
        target = destination / name
        data = target.read_bytes() if target.exists() else urllib.request.urlopen(entry['url'], timeout=60).read()
        assert len(data) == entry['bytes'] and hashlib.sha256(data).hexdigest() == entry['sha256'], name
        if not target.exists():
            target.write_bytes(data)
    print('Verified', len(manifest['files']), 'primary UIUC source files')


if __name__ == '__main__':
    main()
