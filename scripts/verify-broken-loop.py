"""Source-keyed scalar broken-loop checks against independent mechanical models."""
import hashlib,json,platform,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'tests')]
import numpy as np
import scipy
from openswing.bridge import dispatch
from test_broken_loop import oscillator_request,compare_oscillator,scaled_request

files=[Path(__file__),ROOT/'tests/test_broken_loop.py',ROOT/'tests/test_feedback.py',ROOT/'tests/test_custom_feedback.py',
       ROOT/'examples/instrumented-oscillator.asw',*sorted((ROOT/'openswing').glob('*.py'))]
provenance=dict(versions=dict(python=platform.python_version(),numpy=np.__version__,scipy=scipy.__version__),
    source_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files})
cache=ROOT/'.reference/broken-loop-verification.json'
saved=json.loads(cache.read_text()) if cache.exists() else {}
cases=saved.get('cases',{}) if saved.get('provenance')==provenance else {}
for name,kind,request,time_scale in [(k,k,oscillator_request(k),1.) for k in ('none','pd','pi','acceleration','lag','cross')]+[
        ('lag_fine','lag',oscillator_request('lag',step=3e-6),1.),('time_units','lag',scaled_request(),2.)]:
    if name in cases:print('Resumed '+name,flush=True);continue
    if name=='pd':request['frequency']['inputs'][0]='power.01'
    result=dispatch(request)
    error=compare_oscillator(result,kind,time_scale)
    comparison=dict(maximum_broken_loop_error=error,physical_time_per_input_unit=time_scale,
        maximum_full_pencil_backward_error=max(max(s['diagnostics']['backward_errors']) for s in result['samples']),
        transformed_samples=sum(r['broken_loop']['available'] for s in result['samples'] for r in s['responses']),
        unavailable_samples=sum(not r['broken_loop']['available'] for s in result['samples'] for r in s['responses']))
    cases[name]=dict(request=request,result=result,comparison=comparison)
    tmp=cache.with_suffix('.tmp');tmp.write_text(json.dumps(dict(provenance=provenance,cases=cases),allow_nan=False));tmp.replace(cache)
    print(name+': '+json.dumps(comparison),flush=True)
assert len(cases)==8
record=dict(**provenance,cases=cases,definition='1-u/x with x the response matching u in identical physical units; all other command increments zero.',
    limitations=['Documented scalar display only; not a unique multivariable return-ratio matrix or a stability-margin certificate.',
        'Small nonzero responses are retained and can produce sensitive, very large ratios. Exact zero and reciprocal overflow are gaps.',
        'Independent component verification; not ASWING executable, aircraft or experimental validation.'])
path=ROOT/'docs/validation/broken-loop.json';path.write_text(json.dumps(record,allow_nan=False)+'\n')
print(f'Wrote {path.relative_to(ROOT)}: {len(cases)} cases, {len(provenance["source_sha256"])} hashes, {path.stat().st_size} bytes',flush=True)
