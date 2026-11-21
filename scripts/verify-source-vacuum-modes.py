#!/usr/bin/env python3
"""Bounded native source-modal example; independent scalar finite-grid roots.

The beam has axial and torsional compliance only. All four frequencies in
each family follow the clamped/free endpoint-average difference operator:
omega_j = 2*n/L * sqrt(stiffness/density) * tan((2*j-1)*pi/(4*n)).
No ASWING archived frequency or fitted parameter enters this check.
"""
import hashlib
import json
from pathlib import Path
import sys
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from openswing.bridge import dispatch


def main():
    output = Path(sys.argv[1])
    output.mkdir(exist_ok=False)
    request = dict(action='modes', mode='modes', source=(ROOT/'examples/source-vacuum-check.asw').read_text(),
        panels=dict(default=4, beams={'1': dict(count=4, spacing='uniform')}), condition=None,
        numerics=dict(beam_interpolation='drela-segspl-v1', structural_operator='drela-fixed-vacuum-v1'),
        modes=dict(frame='fixed', vacuum=True, count=16, shift=[-.01, 0.], method='dense', step=1e-5, rank_tolerance=1e-9,
                   matrices=True, position=[0., 0., 0.], attitude=[0., 0., 0.], gravity_magnitude=0.))
    write = lambda name, value: (output/name).write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')
    write('request.json', request)
    pins = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((ROOT/'openswing').glob('*.py'))}
    write('plan.json', dict(kernel_pins=pins, expected_finite_dimension=16,
        frequency_relative_gate=2e-8, pencil_backward_gate=1e-8, base_residual_gate=1e-9,
        scope='Synthetic discrete oracle; not archived ASWING agreement.'))
    start = time.monotonic()
    result = dispatch(request)
    elapsed = time.monotonic()-start
    write('result.json', result)
    values = np.array([complex(*m['eigenvalue']) for m in result['modes']])
    expected = np.sort(np.r_[4*np.sqrt(800/2)*np.tan((2*np.arange(1, 5)-1)*np.pi/16),
                                4*np.sqrt(80/.1)*np.tan((2*np.arange(1, 5)-1)*np.pi/16)])
    actual = np.sort(values.imag[values.imag > 1e-6])
    assert result['diagnostics']['finite_dimension'] == len(values) == 16
    np.testing.assert_allclose(actual, expected, rtol=2e-8, atol=1e-9)
    assert max(abs(values.real)) < 1e-8
    assert result['diagnostics']['base_residual'] < 1e-9
    backward = max(max(m['right_backward_error'], m['left_backward_error']) for m in result['modes'])
    assert backward < 1e-8
    assert result['base']['equilibrium_state']['identity']['structural_operator'] == request['numerics']['structural_operator']
    assert result['base']['structure']['strain_source'] == 'source_discrete_constitutive'
    report = dict(status='PASS', seconds=elapsed, finite_dimension=16,
        angular_frequencies=actual.tolist(), expected_angular_frequencies=expected.tolist(),
        maximum_relative_frequency_error=float(max(abs(actual/expected-1))),
        maximum_pencil_backward_error=backward, base_residual=result['diagnostics']['base_residual'],
        source_pins=pins, reference_scope='Independent synthetic finite-grid oracle only.')
    write('report.json', report)
    print(json.dumps(report), flush=True)


if __name__ == '__main__':
    main()
