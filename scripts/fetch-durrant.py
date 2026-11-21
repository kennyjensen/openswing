"""Fetch the pinned, author-deposited Durrant thesis; never execute downloaded data."""
import hashlib
import json
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]


def main():
    reference = json.loads((ROOT/'docs/validation/durrant-reference.json').read_text())
    spec = reference['source']['file']
    target = ROOT/'.reference/durrant/thesis.pdf'
    if target.exists():
        data = target.read_bytes()
    else:
        request = Request(spec['url'], headers={'User-Agent': 'OpenSwing reference research'})
        with urlopen(request, timeout=60) as response:
            data = response.read()
    if len(data) != spec['bytes'] or hashlib.sha256(data).hexdigest() != spec['sha256']:
        raise ValueError('Durrant thesis size or SHA-256 mismatch; do not replace the reference silently.')
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix('.pdf.part')
        temporary.write_bytes(data)
        temporary.replace(target)
    print(f'Verified {target.relative_to(ROOT)} ({len(data)} bytes)')


if __name__ == '__main__':
    main()
