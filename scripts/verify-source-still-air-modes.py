#!/usr/bin/env python3
"""Compare the complete normal-shear/torsional source-grid still-air spectrum."""
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
    source_path = ROOT/'examples/source-still-air-check.asw'
    density = 1.225
    policy = dict(beam_interpolation='drela-segspl-v1', structural_operator='drela-fixed-still-air-v1')
    request = dict(action='modes', mode='modes', source=source_path.read_text(),
        panels=dict(default=4, beams={'1': dict(count=4, spacing='uniform')}), condition=None,
        numerics=policy,
        modes=dict(frame='fixed', vacuum=False, quiescent_density=density, count=16,
                   shift=[-.01, 0.], method='dense', step=1e-5, rank_tolerance=1e-9,
                   matrices=True, position=[0., 0., 0.], attitude=[0., 0., 0.], gravity_magnitude=0.))
    def write(name, value):
        (output/name).write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')
    pins = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((ROOT/'openswing').glob('*.py'))}
    mu = density*np.pi/4
    angle = np.tan((2*np.arange(1, 5)-1)*np.pi/16)
    omega = np.r_[4*np.sqrt(800/(2+mu))*angle, 4*np.sqrt(80/(.1+mu/32))*angle]
    expected = np.r_[1j*omega, -1j*omega]
    write('request.json', request)
    write('plan.json', dict(kernel_pins=pins, source_file=str(source_path.relative_to(ROOT)),
        source_sha256=hashlib.sha256(source_path.read_bytes()).hexdigest(), expected_finite_dimension=16,
        expected_relaxation_multiplicity=0, expected_roots=[[float(z.real), float(z.imag)] for z in expected],
        eigenvalue_relative_gate=3e-8, pencil_backward_gate=1e-8, base_residual_gate=1e-9,
        scope='Complete synthetic discrete still-air spectrum; not archived ASWING agreement.'))
    start = time.monotonic()
    result = dispatch(request)
    elapsed = time.monotonic()-start
    write('result.json', result)
    actual = np.array([complex(*m['eigenvalue']) for m in result['modes']])
    assert result['diagnostics']['finite_dimension'] == len(actual) == len(expected) == 16
    error = abs(expected[:, None]-actual[None, :])/np.maximum(1., abs(expected[:, None]))
    rows, cols = linear_sum_assignment(error)
    assert max(error[rows, cols]) < 3e-8
    assert not any(m['constitutive_relaxation'] for m in result['modes'])
    assert result['diagnostics']['base_residual'] < 1e-9
    backward = max(max(m['right_backward_error'], m['left_backward_error']) for m in result['modes'])
    assert backward < 1e-8
    assert result['vacuum'] is False and result['rom_output_catalog'] == []
    for data in (result, result['base']):
        assert data['structural_operator'] == policy['structural_operator']
        assert data['fluid']['kind'] == 'quiescent' and data['fluid']['density'] == density
        assert data['fluid']['apparent_properties']['spatial_matrix'] is None
    state = result['base']['equilibrium_state']
    assert state['identity']['quiescent_density'] == state['launch']['quiescent_density'] == density
    report = dict(status='PASS', seconds=elapsed, finite_dimension=16, relaxation_multiplicity=0,
        maximum_relative_eigenvalue_error=float(max(error[rows, cols])), maximum_pencil_backward_error=backward,
        base_residual=result['diagnostics']['base_residual'], source_pins=pins,
        eigenvalue_matching=[dict(expected=[float(expected[r].real), float(expected[r].imag)],
            actual=[float(actual[c].real), float(actual[c].imag)], relative_error=float(error[r, c]))
            for r, c in zip(rows, cols)], reference_scope='Independent synthetic spectrum only.')
    write('report.json', report)
    print(json.dumps({k: v for k, v in report.items() if k not in ('source_pins', 'eigenvalue_matching')}), flush=True)


if __name__ == '__main__':
    main()
