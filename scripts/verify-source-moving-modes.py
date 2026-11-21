#!/usr/bin/env python3
"""Free-frame two-mass spring: independent analytic pole and full pencil.

The exact selected pole follows k=EA/L and omega²=k(1/m_root+1/m_tip).
Massless internal stations and physical frame zero/Jordan chains remain in
the unreduced pencil. This checks one nonzero pole, not a finite census.
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
    source = ROOT/'examples/source-moving-vacuum-check.asw'
    omega = np.sqrt(100*(1/2+1/3))
    request = dict(action='modes', mode='modes', source=source.read_text(),
        panels=dict(default=4, beams={'1': dict(count=4, spacing='uniform')}), condition=None,
        numerics=dict(beam_interpolation='drela-segspl-v1', structural_operator='drela-moving-vacuum-v1'),
        modes=dict(frame='free', vacuum=True, count=1, shift=[-.1, float(omega)],
            method='full_shift_invert', step=1e-5, rank_tolerance=1e-9, matrices=True,
            position=[1., 2., 3.], attitude=[12., -7., 24.], gravity_magnitude=0.,
            velocity=[7., -2., .5], motion=dict(rates=[0., 0., 0.],
                acceleration=[0., 0., 0.], angular_acceleration=[0., 0., 0.])))
    write = lambda name, value: (output/name).write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')
    pins = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((ROOT/'openswing').glob('*.py'))}
    write('request.json', request)
    write('plan.json', dict(kernel_pins=pins, source_file=source.relative_to(ROOT).as_posix(),
        source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(), expected_finite_dimension=None,
        expected_returned_count=1, expected_structural_nodes=5, expected_structural_elements=4,
        frequency_relative_gate=2e-8, pencil_backward_gate=1e-8, base_residual_gate=1e-9,
        expected_angular_frequency=float(omega),
        scope='Synthetic free-frame two-mass oscillator; selected positive pole only. Not archived ASWING agreement.',
        browser_case=dict(case_name='Free frame, two-mass spring, one positive pole',
            project_name='Moving-frame vacuum verification', solution_name='Free axial mode',
            plot_quantity='nodes.displacement.1', solve_timeout_ms=120000, total_timeout_ms=300000)))
    start = time.monotonic()
    result = dispatch(request)
    elapsed = time.monotonic()-start
    write('result.json', result)
    assert len(result['modes']) == 1
    mode = result['modes'][0]
    np.testing.assert_allclose(mode['eigenvalue'], [0., omega], rtol=2e-8, atol=1e-9)
    assert result['diagnostics']['finite_dimension'] is None
    assert result['diagnostics']['base_residual'] < 1e-9
    assert result['base']['residual'] < 1e-9
    for key in ('force_balance', 'moment_balance', 'support_force', 'support_moment'):
        np.testing.assert_allclose(result['base'][key], 0., atol=1e-9, rtol=0.)
    assert result['base']['equilibrium_state']['identity']['structural_operator'] == request['numerics']['structural_operator']
    # Independent saved-array arithmetic, without the production eigensolver.
    A, M = (np.array(result['matrices'][key]) for key in ('A', 'M'))
    pole = complex(*mode['eigenvalue'])
    backward = {}
    for side in ('right', 'left'):
        v = np.array(mode[side]['real'])+1j*np.array(mode[side]['imag'])
        a, m, lam = (A, M, pole) if side == 'right' else (A.T, M.T, pole.conjugate())
        err = np.linalg.norm(a@v-lam*(m@v))/((np.linalg.norm(A)+abs(pole)*np.linalg.norm(M))*np.linalg.norm(v))
        assert err < 1e-8
        backward[side] = float(err)
    for name, digest in pins.items():
        assert hashlib.sha256((ROOT/'openswing'/name).read_bytes()).hexdigest() == digest
    report = dict(status='PASS_NATIVE_SOURCE_MOVING_VACUUM', seconds=elapsed,
        expected_angular_frequency=float(omega), eigenvalue=mode['eigenvalue'],
        relative_frequency_error=float(abs(mode['eigenvalue'][1]/omega-1)),
        independent_original_pencil_backward_errors=backward,
        base_residual=result['diagnostics']['base_residual'], full_dimension=len(A),
        returned_count=1, finite_dimension=None, kernel_pins=pins,
        reference_scope='Independent synthetic mechanics, not historical ASWING parity.')
    write('report.json', report)
    print(json.dumps({k:v for k,v in report.items() if k != 'kernel_pins'}), flush=True)


if __name__ == '__main__':
    main()
