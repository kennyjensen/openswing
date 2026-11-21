"""FW checks that require the fresh browser mesh recipe, never a legacy seed."""
import argparse
from dataclasses import asdict
import json
from pathlib import Path

from check_daedalus_load_sensitivity import ROOT, write
from check_fw_published_20261114 import point, system, constraints
from daedalus_bounded_job import run

STUDY = ROOT/'artifacts/fw-current-mesh-20261114'
OLD = ROOT/'artifacts/fw-published-20261114/matrices-32-64/state.json'
GROUPS = {'slow': ((-.15,.4),3), 'damped': ((-15.,.1),2),
          'low_oscillatory': ((-11.5,3.7),1), 'oscillatory': ((-.1,17.),4)}


def layout(folder,args):
    from openswing.asw import parse_asw
    from openswing.aero import FlightCondition
    from openswing.network import StaticNetwork
    from openswing.equilibrium_state import identity,recipe_from_identity
    from openswing.discretization import CURRENT_MESH_RECIPE
    reference = point(args['speed'])
    condition = FlightCondition(speed=args['speed'],alpha=reference['alpha_deg'],
        controls={2:reference['control_2_deg']},attitude=[0.,reference['elevation_deg'],0.],freeze_influences=True)
    n = StaticNetwork(parse_asw((ROOT/'examples/fw.asw').read_text()),args['panels'],condition,None,(),
                      operating_constraints=constraints())
    current = identity(n)
    old = json.loads(OLD.read_text())['identity']
    assert current['mesh_recipe'] == CURRENT_MESH_RECIPE
    write(folder/'identity.json',current)
    return dict(current_recipe=CURRENT_MESH_RECIPE,previous_recipe=recipe_from_identity(old),
        requested_panels=args['panels'],current_nodes=n.nn,current_elements=n.ne,
        previous_nodes=len(old['nodes']),previous_elements=len(old['elements']),
        current_stations=current['stations'],previous_stations=old['stations'],
        conclusion='Previous warm-start comparisons used current equations with a preserved legacy mesh, not the fresh browser mesh.')


def checked_system(args):
    from openswing.discretization import CURRENT_MESH_RECIPE
    seed = None if args['seed'] is None else json.loads(Path(args['seed']).read_text())
    if seed is not None:
        assert seed['identity'].get('mesh_recipe') == CURRENT_MESH_RECIPE
    current, steps = system(args,seed)
    assert current.equilibrium_state['identity']['mesh_recipe'] == CURRENT_MESH_RECIPE
    base = current.base_report()
    assert base['converged'] and base['residual'] < 1e-10
    return current,base,steps


def trim(folder,args):
    current,base,steps = checked_system(args)
    reference = point(args['speed'])
    write(folder/'state.json',current.equilibrium_state)
    write(folder/'base.json',base)
    v = base['operating_values']
    actual = dict(alpha_deg=v['alpha'],elevation_deg=v['attitude.elevation'],
                  control_2_deg=v['control.2'],CL=base['CL'],CD=base['CD'])
    return dict(scope='Current equations and accurate-arc-v2 fresh mesh; inferred free-glide trim.',
        speed_ft_s=args['speed'],requested_panels=args['panels'],
        seed=args['seed'],continuation_steps=steps,residual=base['residual'],
        equilibrium_initialization=base.get('equilibrium_initialization'),
        structural_nodes=base['structural_nodes'],lifting_panels=base['lifting_panels'],
        descriptor_size=current.size,condition=asdict(current.condition),
        mesh_recipe=current.equilibrium_state['identity']['mesh_recipe'],
        actual=actual,reference={k:reference[k] for k in actual},
        difference={k:actual[k]-reference[k] for k in actual},
        kinematically_steady=base['modal_base']['kinematically_steady'])


def matrices(folder,args):
    import numpy as np
    from openswing.linear_dynamics import linearize
    current,base,_ = checked_system(args)
    a,m = linearize(current,step=1e-5,sparse=True)
    np.savez_compressed(folder/'pencil.npz',a=a.toarray(),m=m.toarray())
    write(folder/'state.json',current.equilibrium_state)
    return dict(dimension=current.size,time_scale=current.W,residual=base['residual'],
        speed_ft_s=args['speed'],requested_panels=args['panels'],
        mesh_recipe=current.equilibrium_state['identity']['mesh_recipe'],step=1e-5,
        a_nonzero=a.nnz,m_nonzero=m.nnz)


def modes(folder,args):
    import numpy as np
    from openswing.linear_dynamics import eigensystem
    from openswing.discretization import CURRENT_MESH_RECIPE
    pencil = Path(args['pencil'])
    meta = json.loads((pencil.parent/'result.json').read_text())
    assert meta['mesh_recipe'] == CURRENT_MESH_RECIPE
    with np.load(pencil) as saved:a,m = saved['a'],saved['m']
    shift,count = (args['shift'],args['count']) if args.get('shift') is not None else GROUPS[args['group']]
    found,diagnostics = eigensystem(a,m,time_scale=meta['time_scale'],count=count,
        shift=shift,method='full_shift_invert')
    error = max(max(r['right_backward_error'],r['left_backward_error']) for r in found)
    assert error < 1e-9
    np.savez_compressed(folder/'modes.npz',right=np.array([r['right'] for r in found]),
        left=np.array([r['left'] for r in found]),
        eigenvalues=np.array([complex(*r['eigenvalue']) for r in found]))
    return dict(scope='Full-pencil root search on the current fresh mesh.',
        speed_ft_s=meta['speed_ft_s'],dimension=len(a),mesh_recipe=meta['mesh_recipe'],
        group=args['group'],shift=shift,count=count,maximum_pencil_backward_error=error,
        modes=[{k:v for k,v in row.items() if k not in ('right','left')} for row in found],
        diagnostics=diagnostics)


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('mode',choices=['layout','trim','matrices','modes'])
    parser.add_argument('--tag',required=True)
    parser.add_argument('--panels',type=int,default=32)
    parser.add_argument('--speed',type=float,default=64.)
    parser.add_argument('--seed')
    parser.add_argument('--pencil')
    parser.add_argument('--group',choices=list(GROUPS))
    parser.add_argument('--shift',type=float,nargs=2)
    parser.add_argument('--count',type=int,default=1)
    args=vars(parser.parse_args())
    inputs=[ROOT/'scripts/check_fw_published_20261114.py',OLD,
        ROOT/'examples/fw.asw',ROOT/'reference/root_map_fw.pdf',
        ROOT/'docs/validation/fw-reference.json',ROOT/'docs/validation/aswing-authoritative-references.md',
        ROOT/'docs/validation/aswing-authoritative-sources.json',*sorted((ROOT/'openswing').glob('*.py'))]
    if args['seed']:inputs.append(Path(args['seed']))
    if args['pencil']:inputs += [Path(args['pencil']),Path(args['pencil']).parent/'result.json']
    run(STUDY,args['tag'],inputs,globals()[args['mode']],args,__file__)
