"""Explicitly regenerate one native fixture from a selected kernel snapshot.

Historical generation used the frozen kernel plus its pre-shell-fix asw.py;
see PROVENANCE.json. This script never runs as part of the WASM test.
"""
from pathlib import Path
import argparse
import hashlib
import inspect
import json
import sys

parser = argparse.ArgumentParser()
parser.add_argument('--kernel-parent', type=Path, required=True)
parser.add_argument('--recipe', choices=['legacy', 'current'], required=True)
args = parser.parse_args()
parent = args.kernel_parent.resolve()
sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
producer_modules = {p.name: sha(p) for p in sorted((parent/'openswing').glob('*.py'))}
generator_sha256 = sha(__file__)
sys.path.insert(0, str(parent))

import numpy as np
import scipy
from openswing.asw import parse_asw
from openswing.equilibrium_state import capture
from openswing.network import StaticNetwork
from openswing.time_initialization import launch_time
from openswing.time_state import checkpoint, restore_checkpoint

folder = Path(__file__).resolve().parent
source = (folder/'curved-shell.asw').read_text()
model = parse_asw(source)
assert not model.diagnostics
loads = [dict(beam=1, t=1.1, force=[0., 0., 0.])]
recipe = 'all-breaks-v0' if args.recipe == 'legacy' else 'physical-breaks-v1'
options = {}
if 'mesh_recipe' in inspect.signature(StaticNetwork).parameters:
    options['mesh_recipe'] = recipe
else:
    assert args.recipe == 'legacy', 'Unversioned kernel is only the historical producer.'
n = StaticNetwork(model, 4, None, [0, 0, 0], loads, **options)
x = np.zeros(n.size)
residual = float(np.max(abs(n.residual(x))))
assert residual < 1e-12
saved = capture(n, x, residual=residual)
assert (saved['identity'].get('mesh_recipe') == 'physical-breaks-v1') == (args.recipe == 'current')
assert (.43 in n.meshes[0].t0) == (args.recipe == 'legacy')
cases = {}
for name, order in [('bdf2', 2), ('radau', 5)]:
    out = launch_time(model, saved, duration=.02, dt=.01, order=order,
                      forcing='time Ay\n0 .2\n.03 .2', tolerance=1e-9)
    assert out['accepted_steps'] == 2 and out['rejected_steps'] == 0
    packet = checkpoint(out)
    restored = restore_checkpoint(model, packet)
    assert restored[7]['acceptance_validation']['discrete_replayed']
    np.testing.assert_allclose(packet['state']['velocity_origin_body'], [0, .004, 0], rtol=0, atol=2e-10)
    cases[name] = dict(checkpoint=packet, native_validation=restored[7]['acceptance_validation'],
                       native_full_residual=restored[6])

fields = ('t0', 't1', 'tm', 'ts', 'r0', 'r1', 'rm', 'frames', 'length', 'theta')
assert producer_modules == {p.name: sha(p) for p in sorted((parent/'openswing').glob('*.py'))}
assert generator_sha256 == sha(__file__)
report = dict(recipe=recipe, producer_kind='native frozen historical source' if not options else 'native explicit recipe',
    source_sha256=sha(folder/'curved-shell.asw'), generator_sha256=generator_sha256,
    producer_modules=producer_modules,
    versions=dict(python=sys.version, numpy=np.__version__, scipy=scipy.__version__),
    panels=4, loads=loads, equilibrium=saved, native_equilibrium_residual=residual,
    mesh={key: getattr(n.meshes[0], key).tolist() for key in fields}, cases=cases)
output = folder/(args.recipe+'.json')
output.write_text(json.dumps(report, separators=(',', ':'), allow_nan=False)+'\n')
print(json.dumps(dict(file=str(output), bytes=output.stat().st_size, sha256=sha(output),
                      native_residuals={k:v['native_full_residual'] for k,v in cases.items()})), flush=True)
