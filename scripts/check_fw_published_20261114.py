"""Small serial checks against the published FW root map, not a native Bode oracle."""
import argparse
import json
from pathlib import Path
import sys

from daedalus_bounded_job import run
from check_daedalus_load_sensitivity import ROOT, write

STUDY = ROOT/'artifacts/fw-published-20261114'
REFERENCE = ROOT/'docs/validation/fw-reference.json'
HISTORICAL = ROOT/'docs/validation/flying-wing.json'


def point(speed):
    reference = json.loads(REFERENCE.read_text())
    return next(p for p in reference['points'] if p['speed_ft_s'] == speed)


def constraints():
    from openswing.operating import OperatingConstraint
    return [OperatingConstraint('alpha', 'force.z'),
            OperatingConstraint('attitude.elevation', 'force.x'),
            OperatingConstraint('control.2', 'moment.y')]


def system(args, seed=None):
    from openswing.asw import parse_asw
    from openswing.aero import FlightCondition
    from openswing.linear_dynamics import make_system
    reference = point(args['speed'])
    condition = FlightCondition(speed=args['speed'], alpha=reference['alpha_deg'],
        controls={2: reference['control_2_deg']}, attitude=[0., reference['elevation_deg'], 0.],
        freeze_influences=True)
    model = parse_asw((ROOT/'examples/fw.asw').read_text())
    return make_system(model, condition, args['panels'], frame='free',
        operating_constraints=constraints(), tolerance=1e-10, initial_state=seed,
        structured_base=True)


def trim(folder, args):
    from dataclasses import asdict
    reference = point(args['speed'])
    seed = None
    if not args['cold']:
        history = json.loads(HISTORICAL.read_text())
        old = next(c for c in history['cases'] if c['requested_panels'] == args['panels']
                   and c['speed_ft_s'] == args['speed'] and c['difference_step'] == 1e-5)
        seed = old['base']['equilibrium_state']
    current, steps = system(args, seed)
    base = current.base_report()
    write(folder/'state.json', current.equilibrium_state)
    write(folder/'base.json', base)
    values = base['operating_values']
    actual = dict(alpha_deg=values['alpha'], elevation_deg=values['attitude.elevation'],
        control_2_deg=values['control.2'], CL=base['CL'], CD=base['CD'])
    assert base['converged'] and base['residual'] < 1e-10
    return dict(scope='Current browser-default midpoint/natural equations and frozen influences; published FW point with inferred steady-glide trim.',
        published_point=reference['point'], speed_ft_s=args['speed'],
        requested_panels=args['panels'], structural_nodes=base['structural_nodes'],
        lifting_panels=base['lifting_panels'], descriptor_size=current.size,
        condition=asdict(current.condition), initial_state='historical physical fields, corrected with current equations' if seed else 'cold',
        residual=base['residual'], iterations=steps, kinematically_steady=base['modal_base']['kinematically_steady'],
        actual=actual, reference={key:reference[key] for key in actual},
        difference={key:actual[key]-reference[key] for key in actual},
        reference_bff_per_s=reference['bff_root_per_s'],
        limitation='No current eigenvalue or transfer-function comparison yet; original mesh and executable settings remain unspecified.')


def matrices(folder, args):
    import numpy as np
    from openswing.linear_dynamics import linearize
    seed = json.loads(Path(args['seed']).read_text())
    current, _ = system(args, seed)
    base = current.base_report()
    assert base['residual'] < 1e-10
    a, m = linearize(current, step=1e-5, sparse=True)
    np.savez_compressed(folder/'pencil.npz', a=a.toarray(), m=m.toarray())
    write(folder/'state.json', current.equilibrium_state)
    return dict(dimension=current.size, time_scale=current.W, residual=base['residual'],
                method='Current full residual linearization with sparse assembly; no modal reduction.',
                seed=args['seed'], step=1e-5, a_nonzero=a.nnz, m_nonzero=m.nnz)


def roots(folder, args):
    import numpy as np
    from openswing.linear_dynamics import eigensystem
    pencil = Path(args['pencil'])
    meta = json.loads((pencil.parent/'result.json').read_text())
    with np.load(pencil) as saved:
        a, m = saved['a'], saved['m']
    reference = point(args['speed'])
    modes, diagnostics = eigensystem(a, m, time_scale=meta['time_scale'], count=4,
        shift=(-.1,17.), method='full_shift_invert')
    candidates = [mode for mode in modes if mode['eigenvalue'][0]>-3 and 15<mode['eigenvalue'][1]<24]
    assert len(candidates) == 1
    actual = candidates[0]
    error = max(max(mode['right_backward_error'],mode['left_backward_error']) for mode in modes)
    assert error < 1e-9
    np.savez_compressed(folder/'mode.npz', right=actual['right'], left=actual['left'])
    return dict(scope='Local BFF-root search on the current midpoint/natural equations; not a complete spectrum or native Bode comparison.',
        dimension=len(a), maximum_pencil_backward_error=error,
        speed_ft_s=args['speed'], requested_panels=args['panels'],
        current_bff_per_s=actual['eigenvalue'], reference_bff_per_s=reference['bff_root_per_s'],
        difference_per_s=(np.asarray(actual['eigenvalue'])-reference['bff_root_per_s']).tolist(),
        current_frequency_hz=actual['eigenvalue'][1]/(2*np.pi),
        reference_frequency_hz=reference['bff_root_per_s'][1]/(2*np.pi),
        modes=[{k:v for k,v in mode.items() if k not in ('right','left')} for mode in modes],
        diagnostics=diagnostics)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['trim','matrices','roots'])
    parser.add_argument('--tag', required=True)
    parser.add_argument('--panels', type=int, choices=[8,16,32], default=8)
    parser.add_argument('--speed', type=float, default=64.)
    parser.add_argument('--cold', action='store_true')
    parser.add_argument('--seed')
    parser.add_argument('--pencil')
    args = vars(parser.parse_args())
    inputs = [REFERENCE, HISTORICAL, ROOT/'examples/fw.asw', ROOT/'reference/root_map_fw.pdf',
              ROOT/'docs/validation/aswing-authoritative-references.md',
              ROOT/'docs/validation/aswing-authoritative-sources.json',
              *sorted((ROOT/'openswing').glob('*.py'))]
    if args['seed']:
        inputs.append(Path(args['seed']))
    if args['pencil']:
        inputs.extend([Path(args['pencil']),Path(args['pencil']).parent/'result.json'])
    run(STUDY, args['tag'], inputs, globals()[args['mode']], args, __file__)
