"""Publish the saved sensor-average diagnostic without starting a solver."""
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import json
import shutil

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT/'artifacts/daedalus-sensor-average-20261114/bode-report'
OUTPUT = ROOT/'public/validation/daedalus-sensor-average'


def main():
    terminal = json.loads((SOURCE/'terminal.json').read_text())
    assert terminal['returncode'] == 0 and terminal['process_reaped'] and terminal['inputs_unchanged']
    for name, digest in json.loads((SOURCE/'plan.json').read_text())['inputs_sha256'].items():
        assert sha256(Path(name).read_bytes()).hexdigest() == digest, name
    OUTPUT.mkdir(parents=True, exist_ok=True)
    files = ['index.html', 'bode.svg', 'bode.png', 'bode.csv', 'sensor-locations.json', 'result.json']
    for name in files:
        shutil.copyfile(SOURCE/name, OUTPUT/name)
    receipt = dict(published_utc=datetime.now(timezone.utc).isoformat(),
                   source=str(SOURCE.relative_to(ROOT)), source_observed_utc=terminal['observed_utc'],
                   generator=str(Path(__file__).relative_to(ROOT)),
                   files_sha256={name: sha256((OUTPUT/name).read_bytes()).hexdigest() for name in files})
    (OUTPUT/'publication.json').write_text(json.dumps(receipt, indent=2)+'\n')
    print(f'Published sensor-average Bode to {OUTPUT}')


if __name__ == '__main__':
    main()
