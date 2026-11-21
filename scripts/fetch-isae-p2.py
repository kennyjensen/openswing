"""Fetch and verify the four pinned UIUC forward-flow CP tables for ISAE P-2."""
from pathlib import Path
import hashlib
import json
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def main():
    manifest = json.loads((ROOT/'docs/validation/isae-p2-sources.json').read_text())
    destination = ROOT/'.reference/isae-p2'
    destination.mkdir(parents=True, exist_ok=True)
    for name, entry in manifest['files'].items():
        target = destination/name
        data = target.read_bytes() if target.exists() else urllib.request.urlopen(entry['url'], timeout=30).read()
        if len(data) != entry['bytes'] or hashlib.sha256(data).hexdigest() != entry['sha256']:
            raise ValueError('Primary P-2 table changed: '+name)
        if not target.exists():
            target.write_bytes(data)
    print('Verified four primary P-2 power tables; static rows use fetch-isae-p1.py.')


if __name__ == '__main__':
    main()
