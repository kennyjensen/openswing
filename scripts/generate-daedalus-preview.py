"""Generate the display-only jig geometry used before the browser solver loads."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from openswing.asw import parse_asw
from openswing.geometry import attachment_geometry, geometry_summary


def rounded(value):
    if isinstance(value, float):
        return round(value, 6)
    if isinstance(value, list):
        return [rounded(item) for item in value]
    if isinstance(value, dict):
        return {key: rounded(item) for key, item in value.items()}
    return value


source = ROOT / 'examples/dae.asw'
model = parse_asw(source.read_text())
mesh = json.loads((ROOT / 'web/daedalus-mesh.json').read_text())
beams = geometry_summary(model, panels=mesh)
for beam in beams:
    # The startup viewer always uses streamwise chords.
    if 'streamwise_quads' in beam:
        del beam['quads']
preview = rounded(dict(name=model.name, beams=beams, attachments=attachment_geometry(model)))
output = json.dumps(preview, separators=(',', ':'), allow_nan=False) + '\n'
destination = ROOT / 'web/daedalus-preview.json'
if sys.argv[1:] == ['--check']:
    if destination.read_text() != output:
        raise SystemExit('Daedalus startup preview is stale.')
else:
    destination.write_text(output)
