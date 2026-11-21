"""Independent scalar reference from the retained physical outputs; no solver."""
import gzip
import hashlib
import json
from pathlib import Path
import struct
import time

ROOT = Path(__file__).resolve().parent.parent
BASE = ROOT / 'artifacts/isae/ua2-archive-ui-20261102'
SOURCE = ROOT / 'artifacts/isae/ua2-incidence-periodic-browser-20261101/assessment/production'
rows = []
inputs = {}
began = time.monotonic()
durations = []
for part in range(330):
    start = time.monotonic()
    folder = SOURCE / f'part{part:03}'
    data = (folder / 'trajectory.json.gz').read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    assert digest == json.loads((folder / 'receipt.json').read_text())['output_sha256']['trajectory.json.gz']
    inputs[str(folder.relative_to(ROOT)) + '/trajectory.json.gz'] = digest
    result = json.loads(gzip.decompress(data))
    for snapshot in result['snapshots'][int(part > 0):]:
        rows.append([snapshot['time'], snapshot['CL'], snapshot['frame']['position_earth'][2]])
    durations.append(time.monotonic() - start)
    assert durations[-1] < 30
    if (part + 1) % 64 == 0 or part == 329:
        print(json.dumps(dict(part=part, snapshots=len(rows), seconds=durations[-1])), flush=True)
assert len(rows) == 5281
hashes = {name: hashlib.sha256(b''.join(struct.pack('<d', row[i]) for row in rows)).hexdigest()
          for i, name in enumerate(['time', 'CL', 'frame.position_earth.2'])}
report = dict(passed=True, snapshots=5281, columns=['time', 'CL', 'frame.position_earth.2'], rows=rows,
              float64_little_endian_sha256=hashes, input_sha256=inputs,
              script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              max_segment_seconds=max(durations), wall_seconds=time.monotonic()-began,
              numerical_reexecution=False)
with (BASE / 'reference.json').open('x') as f:
    json.dump(report, f, indent=2)
    f.write('\n')
print(json.dumps(dict(passed=True, snapshots=5281, wall_seconds=report['wall_seconds'])), flush=True)
