"""Package the built static application for a Python-only local launch."""
from pathlib import Path
import json
from distribution import package

root = Path('dist')
if not (root / 'index.html').is_file():
    raise SystemExit('Build the app before packaging it.')
destination = root / 'openswing-local.zip'
instructions = '''OpenSwing local browser application

Extract this entire ZIP into a folder. Open a terminal in that folder and run:

    python3 -m http.server 8000 --bind 127.0.0.1

On Windows you can use: py -m http.server 8000 --bind 127.0.0.1

Open http://127.0.0.1:8000 in your browser. Stop the server with Ctrl+C.
Do not open index.html directly: the browser must load the worker and WASM
runtime through HTTP. No npm install, pip install or internet connection is
needed for this prebuilt bundle. All numerical work runs inside your browser;
Python's server only serves these static files.

The included openswing-source.zip contains the MIT-licensed source and full
build instructions, tests and validation summaries. Optional raw experiment
archives are a separate download; see VALIDATION-ARCHIVES.txt inside the source
ZIP. Development is ongoing; see its requirements ledger for remaining ASWING
functionality and validation limits.
'''

metadata = json.loads((root / 'distribution.json').read_text())
if metadata.get('format') != 'openswing-distribution' or metadata.get('version') != 1:
    raise SystemExit('Build the distribution metadata before packaging the app.')
metadata.update(kind='local', validation=None)
excluded = {destination, root / 'openswing-validation.zip', root / 'distribution.json'}
files = [(p.relative_to(root).as_posix(), p) for p in root.rglob('*')
         if p.is_file() and p not in excluded and '.openai' not in p.parts]
package(destination, files, {'README-local.txt': instructions.encode(),
        'distribution.json': (json.dumps(metadata, sort_keys=True, indent=2) + '\n').encode()})
print(f'Packaged {destination} ({destination.stat().st_size/1048576:.1f} MiB)')
