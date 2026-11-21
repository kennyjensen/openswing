"""Restore publisher-deposited metadata used in the SA-10 source audit."""
from pathlib import Path
import hashlib, json, urllib.request

ROOT = Path(__file__).resolve().parents[1]
report = json.loads((ROOT / 'docs/validation/isae-sa10-sources.json').read_text())
primary = report['primary']
target = ROOT / '.reference/isae-sa10/crossref.json'
target.parent.mkdir(parents=True, exist_ok=True)
sha = lambda b: hashlib.sha256(b).hexdigest()
if target.exists() and sha(target.read_bytes()) == primary['metadata_sha256']:
    print('Verified cached SA-10 metadata')
else:
    request = urllib.request.Request(primary['metadata_url'], headers={'User-Agent': 'OpenSwing-source-audit/1.0'})
    with urllib.request.urlopen(request, timeout=60) as response:
        data = response.read()
    if sha(data) != primary['metadata_sha256']:
        candidate = target.with_name('crossref-current-unverified.json'); candidate.write_bytes(data)
        raise SystemExit('Crossref metadata changed. Candidate retained for explicit source review; pinned audit not overwritten.')
    target.write_bytes(data)
    print('Downloaded and verified SA-10 metadata')
