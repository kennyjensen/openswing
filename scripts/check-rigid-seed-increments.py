"""Retain seeded rigid solves for an independent packaged-WASM replay."""
import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/'tests'))
from openswing.bridge import dispatch
from test_rigid_circulation_initialization import setup

parser=argparse.ArgumentParser()
parser.add_argument('--output',required=True)
args=parser.parse_args()
witness=json.loads((ROOT/'tests/fixtures/rigid-subnormal-seed.json').read_text())
requests=[dict(witness['request'],initial_circulation=witness['seed'])]
for modes,powered in ((4,False),(0,True),(4,True)):
    model,condition,meshes,basis=setup(modes,alpha=7.,powered=powered)
    requests.append(dict(action='solve',mode='rigid',source=model.dumps(),panels=12,
        condition=asdict(condition),circulation_method='direct',
        initial_circulation=basis.decode(np.full(basis.size,1e-18)).tolist()))
for alpha in (0.,1e-12,1e-18):
    requests.append(dict(witness['request'],condition=dict(witness['request']['condition'],alpha=alpha),
                         initial_circulation=[1.]*len(witness['seed'])))
cases=[]
for request in requests:
    result=dispatch(request)
    assert result['converged'] and result['residual']<1e-10
    initialization=result['circulation_solver']['initialization']
    assert initialization['seed_attempt']['accepted'] and not initialization['cold_fallback']
    assert initialization['initial_circulation']==request['initial_circulation']
    cases.append(dict(request=request,result=result))
report=dict(cases=cases,module_hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'openswing').glob('*.py')})
Path(args.output).write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
print('Seven direct seeds converge, including engine/Fourier and zero/tiny nonzero lift.')
