"""Run the bounded independent section-transfer sweep on an explicit kernel."""
import argparse
import hashlib
import json
import os
import platform
import sys
import time
from pathlib import Path
import numpy as np
import scipy
from durrant_section_transfer import compute,independent_checks
from durrant_unloaded_native import load_kernel

ROOT=Path(__file__).resolve().parents[1]


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kernel-root',type=Path,required=True)
    parser.add_argument('--plan',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists():raise ValueError('Use a fresh section result path.')
    plan=json.loads(args.plan.read_text())
    if set(plan)-{'schema','description','cases'} or plan.get('schema')!=1 or not 1<=len(plan['cases'])<=32:
        raise ValueError('Expected bounded section plan schema1 with1–32 cases.')
    kernel_root,_=load_kernel(args.kernel_root)
    files=[Path(__file__),ROOT/'scripts/durrant_section_transfer.py',ROOT/'scripts/durrant_unloaded_native.py',
           *sorted((kernel_root/'openswing').glob('*.py'))]
    fingerprints={str(path):sha(path) for path in files}
    begin=time.monotonic()
    out=dict(status='running',started=time.time(),command=sys.argv,plan=plan,plan_sha256=sha(args.plan),
        source_sha256=fingerprints,versions=dict(python=platform.python_version(),numpy=np.__version__,scipy=scipy.__version__),
        independent_checks=independent_checks(),cases=[],
        limitations=['Prescribed unloaded section loads, not beam assembly or loaded flutter.',
            'ASWING empirical lag, not exact Theodorsen or experimental aerodynamics.',
            'WASM/browser replay of this consolidated verifier is recorded separately when completed.'])
    def save():
        temporary=args.output.with_suffix('.part')
        with temporary.open('w') as stream:
            stream.write(json.dumps(out,indent=2,allow_nan=False)+'\n');stream.flush();os.fsync(stream.fileno())
        temporary.replace(args.output)
    save()
    try:
        for spec in plan['cases']:
            if fingerprints!={str(path):sha(path) for path in files}:raise ValueError('Sources changed during the section sweep.')
            case=compute(kernel_root,spec);out['cases'].append(case);save()
            print(spec,'computed',flush=True)
        checks={key:max(max(sample[key].values()) for case in out['cases'] for sample in case['samples'])
                for key in ['finite_comparison','tangent_step_change']}
        checks['maximum_circulation_error']=max(sample['circulation_max_scaled_difference'] for case in out['cases'] for sample in case['samples'])
        checks['maximum_harmonic_residual']=max(sample['normalized_harmonic_residual'] for case in out['cases'] for sample in case['samples'])
        bounds=dict(finite_comparison=1e-7,tangent_step_change=1e-6,maximum_circulation_error=1e-7,maximum_harmonic_residual=1e-10)
        large=[case for case in out['cases'] if case['aspect_ratio']==200000.]
        if large:
            checks['large_span_infinite_comparison']=max(max(sample['infinite_comparison'].values()) for case in large for sample in case['samples'])
            bounds['large_span_infinite_comparison']=1e-4
        if fingerprints!={str(path):sha(path) for path in files}:raise ValueError('Sources changed during the section sweep.')
        out.update(checks=checks,bounds=bounds,status='passed' if all(checks[k]<=v for k,v in bounds.items()) else 'failed')
    except Exception as exc:
        out.update(status='failed',error=repr(exc));raise
    finally:
        out.update(ended=time.time(),elapsed_s=time.monotonic()-begin);save()
    print(json.dumps(dict(status=out['status'],checks=checks),indent=2),flush=True)
    if out['status']!='passed':raise SystemExit(1)


if __name__=='__main__':main()
