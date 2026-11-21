"""Bounded FW root-map coverage and independent full-residual mode checks."""
import argparse
import json
from pathlib import Path

from check_daedalus_load_sensitivity import ROOT, pin, write
from check_fw_published_20261114 import point, system
from daedalus_bounded_job import run

STUDY = ROOT/'artifacts/fw-modes-20261114'
BASE = ROOT/'artifacts/fw-published-20261114/matrices-32-64'
GROUPS = {'slow': ((-.15, .4), 3),
          'damped': ((-15., .1), 2),
          'low_oscillatory': ((-11.5, 3.7), 1),
          'oscillatory': ((-.1, 17.), 4)}


def verify_base():
    record = json.loads((BASE/'plan.json').read_text())
    for name, expected in record['inputs_sha256'].items():
        assert pin(Path(name)) == expected, name
    terminal = json.loads((BASE/'terminal.json').read_text())
    assert terminal['returncode'] == 0 and terminal['process_reaped']
    assert terminal['inputs_unchanged'] and not terminal['timed_out']


def modes(folder, args):
    import numpy as np
    from openswing.linear_dynamics import eigensystem
    verify_base()
    with np.load(BASE/'pencil.npz') as saved:
        a, m = saved['a'], saved['m']
    meta = json.loads((BASE/'result.json').read_text())
    shift, count = GROUPS[args['group']]
    found, diagnostics = eigensystem(a, m, time_scale=meta['time_scale'], count=count,
                                   shift=shift, method='full_shift_invert')
    error = max(max(row['right_backward_error'], row['left_backward_error']) for row in found)
    assert error < 1e-9
    np.savez_compressed(folder/'modes.npz', right=np.array([v['right'] for v in found]),
                        left=np.array([v['left'] for v in found]),
                        eigenvalues=np.array([complex(*v['eigenvalue']) for v in found]))
    return dict(scope='Local full-pencil roots at 64 ft/s on the current 42-panel FW model.',
        group=args['group'], shift=shift, count=count,
        maximum_pencil_backward_error=error,
        modes=[{k:v for k,v in row.items() if k not in ('right','left')} for row in found],
        diagnostics=diagnostics)


def directions(folder, args):
    import numpy as np
    verify_base()
    seed = json.loads((BASE/'state.json').read_text())
    current, _ = system(dict(speed=64., panels=32), seed)
    base = current.base_report()
    assert base['residual'] < 1e-10 and current.size == 834
    with np.load(BASE/'pencil.npz') as saved:
        a, m = saved['a'], saved['m']
    with np.load(Path(args['modes'])/'modes.npz') as saved:
        vectors, roots = saved['right'], saved['eigenvalues']
    checks, arrays = [], {}
    for index, (v, lam) in enumerate(zip(vectors, roots)):
        v = v/max(abs(v))
        for part in ('real', 'imag'):
            z, zd = getattr(v, part), getattr(lam*v, part)
            if max(np.max(abs(z)), np.max(abs(zd))) < 1e-12:
                continue
            expected = a@z-m@zd
            scale = max(np.max(abs(a@z))+np.max(abs(m@zd)), 1e-14)
            for h in (2e-4, 4e-4):
                values = [current.residual(f*h*z, f*h*zd) for f in (1, -1, 2, -2)]
                direct = (8*(values[0]-values[1])-(values[2]-values[3]))/(12*h)
                difference = float(np.max(abs(direct-expected)))
                relative = float(np.max(abs(direct))/scale)
                arrays[f'{index}-{part}-{h}'] = direct
                checks.append(dict(mode_index=index, eigenvalue=[lam.real,lam.imag],
                    part=part, width=h, scale=float(scale),
                    maximum_absolute_difference=difference,
                    scaled_matrix_difference=difference/scale,
                    scaled_full_mode_residual=relative, accepted=relative < 1e-7))
    np.savez_compressed(folder/'directional-residuals.npz', **arrays)
    return dict(scope='Fourth-order differences of the unmodified full nonlinear residual along each modal trajectory; two fixed widths.',
        base_residual=base['residual'], checks=checks,
        acceptance_threshold=1e-7,
        accepted=sum(row['accepted'] for row in checks), total=len(checks),
        maximum_scaled_residual=max(row['scaled_full_mode_residual'] for row in checks),
        limitation='These directional checks cover the selected eigenvectors, not every state-space direction or Bode input/output derivatives.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['modes','directions'])
    parser.add_argument('--tag', required=True)
    parser.add_argument('--group', choices=list(GROUPS))
    parser.add_argument('--modes')
    args = vars(parser.parse_args())
    inputs = [ROOT/'scripts/check_fw_published_20261114.py', ROOT/'examples/fw.asw',
        ROOT/'docs/validation/fw-reference.json', ROOT/'reference/root_map_fw.pdf',
        ROOT/'docs/validation/aswing-authoritative-references.md',
        ROOT/'docs/validation/aswing-authoritative-sources.json',
        *[BASE/name for name in ('plan.json','terminal.json','result.json','state.json','pencil.npz')],
        *sorted((ROOT/'openswing').glob('*.py'))]
    if args['modes']:
        inputs += [Path(args['modes'])/name for name in ('result.json','modes.npz','terminal.json')]
    run(STUDY, args['tag'], inputs, globals()[args['mode']], args, __file__)
