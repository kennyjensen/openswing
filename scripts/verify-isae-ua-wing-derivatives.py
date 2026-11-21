"""Bound central-difference uncertainty in the UA-2 matrix reference."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import time

import numpy as np

from isae_ua_wing_reference import assemble, harmonic

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'artifacts/isae/ua2-time-20261101'


def complex_response(rows):
    return np.array([complex(r['CL_real'],r['CL_imag']) for r in rows])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--panels',type=int,choices=(20,40),required=True)
    args = parser.parse_args()
    output = BASE/f'derivative-refinement-n{args.panels}.json'
    if output.exists():
        parser.error('Preserve completed evidence')
    first = json.loads((BASE/f'reference-n{args.panels}.json').read_text())
    previous = json.loads((ROOT/f'artifacts/isae/ua-time-20261101/wing-ar10-n{args.panels}.json').read_text())
    started = time.monotonic()
    step = first['settings']['derivative_step']
    references = [first,assemble(args.panels,step=step/2),assemble(args.panels,step=step/4)]
    for r in references:
        assert r['numerical_passed']
    responses = [complex_response(harmonic(r)) for r in references]
    coarse,half,fine = responses
    delta1,delta2 = np.abs(coarse-half),np.abs(half-fine)
    ratio = float(np.max(delta2)/np.max(delta1))
    extrapolated = (4*fine-half)/3
    relative_uncertainty = float(np.max(np.abs(coarse-extrapolated))/np.max(np.abs(extrapolated)))
    difference = np.abs(coarse-complex_response(previous['production']['response']))
    # The older reference uses the same dimensional difference step at V30,
    # hence a smaller nondimensional perturbation than the present V10 data.
    # Use the independently measured truncation bound, with a rounding floor,
    # rather than expecting exact equality between the finite differences.
    bound = 2*delta1+1e-12
    passed = ratio < .35 and relative_uncertainty < 1e-7 and bool(np.all(difference <= bound))
    result = dict(panels=args.panels,derivative_steps=[step,step/2,step/4],
        refinement_ratio=ratio,relative_CL_uncertainty=relative_uncertainty,
        maximum_previous_harmonic_difference=float(np.max(difference)),
        previous_difference=difference.tolist(),measured_consistency_bound=bound.tolist(),
        passed=passed,gate='Difference-refinement ratio <.35; relative CL correction <1e-7; prior harmonic difference inside 2*coarse-half difference +1e-12.',
        matrices_replaced=False,production_changed=False,
        references=references,seconds=time.monotonic()-started,
        script_sha256=sha256(Path(__file__).read_bytes()).hexdigest())
    output.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps({k:result[k] for k in ('panels','refinement_ratio','relative_CL_uncertainty','maximum_previous_harmonic_difference','passed','seconds')}))
    if not passed:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
