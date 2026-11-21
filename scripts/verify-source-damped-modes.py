#!/usr/bin/env python3
"""Complete source-grid Kelvin--Voigt spectrum, including rigid relaxation.

The dual axial/torsional beam has eight elastic coordinates (16 quadratic
roots) and 16 rigid-strain relaxation coordinates. None is filtered out.
"""
import hashlib
import json
from pathlib import Path
import sys
import time

import numpy as np
from scipy.optimize import linear_sum_assignment

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from openswing.bridge import dispatch


def main():
    output = Path(sys.argv[1])
    output.mkdir(exist_ok=False)
    source_path = ROOT/'examples/source-vacuum-damped-check.asw'
    request = dict(action='modes', mode='modes', source=source_path.read_text(),
        panels=dict(default=4, beams={'1': dict(count=4, spacing='uniform')}), condition=None,
        numerics=dict(beam_interpolation='drela-segspl-v1', structural_operator='drela-fixed-vacuum-v1'),
        modes=dict(frame='fixed', vacuum=True, count=32, shift=[-.01, 0.], method='dense', step=1e-5,
                   rank_tolerance=1e-9, matrices=True, position=[0., 0., 0.], attitude=[0., 0., 0.], gravity_magnitude=0.))
    def write(name, value):
        (output/name).write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')
    pins = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((ROOT/'openswing').glob('*.py'))}
    omega = np.r_[4*np.sqrt(800/2)*np.tan((2*np.arange(1, 5)-1)*np.pi/16),
                  4*np.sqrt(80/.1)*np.tan((2*np.arange(1, 5)-1)*np.pi/16)]
    tau = .002
    expected = np.r_[np.concatenate([np.roots([1, tau*w*w, w*w]) for w in omega]), np.full(16, -1/tau)]
    write('request.json', request)
    write('plan.json', dict(kernel_pins=pins, source_file=str(source_path.relative_to(ROOT)),
        source_sha256=hashlib.sha256(source_path.read_bytes()).hexdigest(), expected_finite_dimension=32,
        expected_relaxation_multiplicity=16, expected_roots=[[float(z.real), float(z.imag)] for z in expected],
        eigenvalue_relative_gate=3e-8, pencil_backward_gate=1e-8, base_residual_gate=1e-9,
        scope='Complete synthetic discrete spectrum; not archived ASWING agreement.'))
    start = time.monotonic()
    result = dispatch(request)
    elapsed = time.monotonic()-start
    write('result.json', result)
    actual = np.array([complex(*m['eigenvalue']) for m in result['modes']])
    assert result['diagnostics']['finite_dimension'] == len(actual) == len(expected) == 32
    error = abs(expected[:, None]-actual[None, :])/np.maximum(1., abs(expected[:, None]))
    rows, cols = linear_sum_assignment(error)
    assert max(error[rows, cols]) < 3e-8
    assert sum(m['constitutive_relaxation'] for m in result['modes']) == 16
    assert max(actual.real) < 0
    assert result['diagnostics']['base_residual'] < 1e-9
    backward = max(max(m['right_backward_error'], m['left_backward_error']) for m in result['modes'])
    assert backward < 1e-8
    assert result['base']['structure']['strain_source'] == 'source_discrete_damped_constitutive'
    assert result['base']['sensors'][0]['strain_axes_body'] is None
    report = dict(status='PASS', seconds=elapsed, finite_dimension=32, relaxation_multiplicity=16,
        maximum_relative_eigenvalue_error=float(max(error[rows, cols])), maximum_pencil_backward_error=backward,
        base_residual=result['diagnostics']['base_residual'], source_pins=pins,
        eigenvalue_matching=[dict(expected=[float(expected[r].real), float(expected[r].imag)],
            actual=[float(actual[c].real), float(actual[c].imag)], relative_error=float(error[r, c]))
            for r, c in zip(rows, cols)], reference_scope='Independent synthetic spectrum only.')
    write('report.json', report)
    print(json.dumps({k: v for k, v in report.items() if k not in ('source_pins', 'eigenvalue_matching')}), flush=True)


if __name__ == '__main__':
    main()
