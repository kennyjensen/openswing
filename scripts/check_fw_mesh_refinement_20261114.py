"""Serial current-mesh FW refinement with explicitly unconverged seed transfer.

Interpolation only initializes a new native mesh. Every reported equilibrium
and dynamic matrix is recomputed using the unmodified production equations.
"""
import argparse
from copy import deepcopy
import json
from pathlib import Path

from check_daedalus_load_sensitivity import ROOT,write
from check_fw_published_20261114 import constraints
from check_fw_current_mesh_20261114 import trim,matrices,modes
from check_fw_current_directions_20261114 import directions
from daedalus_bounded_job import run

STUDY=ROOT/'artifacts/fw-mesh-refinement-20261114'


def transfer(folder,args):
    import numpy as np
    from openswing.asw import parse_asw
    from openswing.network import StaticNetwork
    from openswing.time_state import read_condition
    from openswing.equilibrium_state import capture,restore
    from openswing.discretization import CURRENT_MESH_RECIPE,requirements
    source=Path(args['seed'])
    saved=json.loads(source.read_text())
    meta=json.loads((source.parent/'result.json').read_text())
    assert meta['residual']<1e-10 and meta['mesh_recipe']==CURRENT_MESH_RECIPE
    assert saved['identity']['mesh_recipe']==CURRENT_MESH_RECIPE
    model=parse_asw((ROOT/'examples/fw.asw').read_text())
    condition=read_condition(saved['launch']['condition'])
    assert condition.speed==args['speed']==38.
    assert len(model.beams)==1 and model.beams[0].lifting
    old=StaticNetwork(model,saved['launch']['panels'],condition,None,(),operating_constraints=constraints())
    new=StaticNetwork(model,args['panels'],condition,None,(),operating_constraints=constraints())
    old_state=restore(old,saved)
    assert not old.hinges and not new.hinges
    assert old.ng==old.ne and new.ng==new.ne
    assert old.nc==new.nc==6 and len(old.constraints)==len(new.constraints)==1
    assert old.constraints[0]['kind']==new.constraints[0]['kind']=='ground'
    np.testing.assert_allclose(old.rj[old.constraints[0]['a']],new.rj[new.constraints[0]['a']],atol=0,rtol=0)
    assert np.max(np.linalg.norm(saved['rotations'],axis=1))<np.pi/2
    old_t,old_ids=old.station_nodes[1];new_t,new_ids=new.station_nodes[1]
    assert np.array_equal(old_ids,np.arange(old.nn)) and np.array_equal(new_ids,np.arange(new.nn))
    def interpolate(x,y,target):
        y=np.asarray(y)
        if y.ndim==1:return np.interp(target,x,y)
        return np.column_stack([np.interp(target,x,y[:,j]) for j in range(y.shape[1])])
    guess=capture(new,np.zeros(new.size))
    guess['positions']=(new.rj+interpolate(old_t,np.asarray(saved['positions'])-old.rj,new_t)).tolist()
    guess['rotations']=interpolate(old_t,saved['rotations'],new_t).tolist()
    # Do not blend element fields across mandatory property/control breaks or
    # the center point weight. These are initial estimates, not new quadrature.
    breaks=sorted({row['t'] for row in requirements(model,(),mesh_recipe=CURRENT_MESH_RECIPE)[1]})
    old_mid,new_mid=old.meshes[0].tm,new.meshes[0].tm
    for key in ('internal_force','internal_moment','circulation'):
        values=np.asarray(saved[key]);mapped=np.empty((new.ne,)+values.shape[1:])
        assigned=np.zeros(new.ne,dtype=bool)
        for a,b in zip(breaks,breaks[1:]):
            src=(old_mid>a)&(old_mid<b);dst=(new_mid>a)&(new_mid<b)
            if np.any(dst):
                assert np.any(src)
                mapped[dst]=interpolate(old_mid[src],values[src],new_mid[dst]);assigned[dst]=True
        assert np.all(assigned)
        guess[key]=mapped.tolist()
    guess['reactions']=deepcopy(saved['reactions'])
    guess['operating_values']=deepcopy(saved['operating_values'])
    guess['residual']=None
    guess['diagnostic_seed']=dict(kind='unconverged-current-mesh-transfer',source=str(source),
        method='Piecewise linear physical-field interpolation; full nonlinear correction required.')
    guess['limitations'].append('Unconverged initial guess only; not a validated equilibrium or mode result.')
    z=np.zeros_like(new.rj)
    actual=restore(new,guess)
    residual=float(np.max(abs(new.residual(actual,elastic_motion=(z,z,z,z),circulation_rate=np.zeros(new.ne)))))
    write(folder/'guess.json',guess)
    return dict(scope='Initialization only, not an accepted equilibrium.',source=str(source),
        speed_ft_s=condition.speed,source_panels=old.ne,target_panels=new.ne,
        requested_target_count=args['panels'],mesh_recipe=CURRENT_MESH_RECIPE,
        initial_residual=residual,physical_properties_changed=False,full_correction_required=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('mode',choices=['transfer','trim','matrices','modes','directions'])
    parser.add_argument('--tag',required=True)
    parser.add_argument('--panels',type=int,default=48)
    parser.add_argument('--speed',type=float,default=38.)
    parser.add_argument('--seed')
    parser.add_argument('--pencil')
    parser.add_argument('--modes')
    parser.add_argument('--group',default=None)
    parser.add_argument('--shift',type=float,nargs=2,default=[-7.,1.65])
    parser.add_argument('--count',type=int,default=1)
    args=vars(parser.parse_args())
    inputs=[ROOT/'scripts/check_fw_published_20261114.py',ROOT/'scripts/check_fw_current_mesh_20261114.py',
        ROOT/'scripts/check_fw_current_directions_20261114.py',ROOT/'examples/fw.asw',
        ROOT/'docs/validation/fw-reference.json',ROOT/'reference/root_map_fw.pdf',
        ROOT/'docs/validation/aswing-authoritative-references.md',ROOT/'docs/validation/aswing-authoritative-sources.json',
        *sorted((ROOT/'openswing').glob('*.py'))]
    if args['seed']:
        seed=Path(args['seed']);inputs += [seed,seed.parent/'result.json']
    if args['pencil']:
        matrix=Path(args['pencil']).parent;inputs += [matrix/n for n in ('pencil.npz','result.json','state.json','terminal.json')]
    if args['modes']:
        mode=Path(args['modes']);inputs += [mode/n for n in ('modes.npz','result.json','terminal.json')]
    run(STUDY,args['tag'],inputs,globals()[args['mode']],args,__file__)
