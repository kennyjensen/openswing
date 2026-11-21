"""Single-case Euler-column check with bounded, streaming output.

Example: .venv/bin/python scripts/check-euler-column.py /tmp/column-check \
    --intervals 32 --ratio .5
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
helper_path=ROOT/'scripts/run-column-buckling-streamed.py'
spec=importlib.util.spec_from_file_location('_streamed_column',helper_path)
helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('output');parser.add_argument('--intervals',type=int,required=True)
parser.add_argument('--ratio',type=float,required=True);parser.add_argument('--grid-critical',action='store_true')
parser.add_argument('--method',choices=('dense','full_shift_invert'),default='full_shift_invert')
args=parser.parse_args()
source=helper.transformed()
namespace={'__name__':'_column_check','__file__':str(helper.VERIFIER)}
exec(compile(source,str(helper.VERIFIER),'exec'),namespace)
try:
    namespace['run'](args)
finally:
    folder=Path(args.output)
    if folder.is_dir():
        pins={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
              for p in [Path(__file__),helper_path,helper.VERIFIER]}
        with (folder/'streaming-writer.json').open('w') as stream:
            json.dump(dict(source_pins=pins,executed_verifier_sha256=hashlib.sha256(source.encode()).hexdigest(),
                change='Only json.dump replaces json.dumps plus write_text; full matrices and all physical checks retained.'),stream,indent=2)
            stream.write('\n')
