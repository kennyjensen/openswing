"""Fresh source-equation trim and full response on the app's Daedalus mesh.

Small serial stages reuse the checked matrix-assembly driver. Interpolation is
only an initial guess; all steady equations and all dynamic columns are rebuilt.
No native GIF mesh identity, parameter fit, or new convergence limit is claimed.
"""
import argparse
from pathlib import Path
from types import SimpleNamespace
from check_daedalus_load_sensitivity import ROOT, SOURCE, read, write
from daedalus_bounded_job import run
import check_daedalus_source_operator as source
import check_daedalus_structural_resolution as stages

STUDY=ROOT/'artifacts/daedalus-default-mesh-response-20261114'
BASE=SOURCE/'trim-6.7-1/state.json'
PRESET=ROOT/'web/daedalus-mesh.json'


def network(packet):
    from openswing.asw import parse_asw
    from openswing.source_airflow import SourceAirflowNetwork
    from openswing.time_state import read_condition
    model=parse_asw((ROOT/'examples/dae.asw').read_text(),beam_interpolation='drela-segspl-v1')
    launch=packet['launch']
    n=SourceAirflowNetwork(model,read(PRESET),read_condition(launch['condition']),
        launch['gravity'],launch['loads'],operating_constraints=launch['released_constraints'],
        strut_mode=launch['strut_mode'],mesh_recipe='accurate-arc-v2',steady_trim=True)
    assert (n.nn,n.ne,n.ng)==(112,107,86)
    return n


def setup(seed):
    from openswing.equilibrium_state import restore
    packet=read(seed);n=network(packet)
    return n,restore(n,packet)


def dynamic(args):
    import numpy as np
    from openswing.linear_dynamics import _dynamic_base
    from openswing.operating import time_load_constraints
    n,x=setup(args.seed)
    assert max(abs(n.residual(x)))<=1e-9
    zero=np.zeros_like(n.rj)
    return _dynamic_base(n,x,time_load_constraints('free'),'free',
        dict(elastic_motion=(zero,zero,zero,zero),circulation_rate=np.zeros(n.ng)),
        position=(0,0,0),attitude=(0,0,0),velocity=(0,0,0),gravity_magnitude=None)


def initialize(folder,args):
    import numpy as np
    from openswing.equilibrium_state import restore_physical_fields
    packet=read(BASE);n=network(packet)
    old,_=stages.setup(BASE)
    pose=np.zeros_like(n.rj);rotations=np.zeros_like(n.rj)
    force=np.zeros((n.ne,3));moment=force.copy();gamma=np.zeros(n.ng)
    old_cursor=new_cursor=0
    for prior,mesh in zip(old.meshes,n.meshes):
        key=mesh.beam.index;t,ids=n.station_nodes[key];ot,oi=old.station_nodes[key]
        for label,target in [('positions',pose),('rotations',rotations)]:
            values=np.array(packet[label])[oi]
            target[ids]=np.column_stack([np.interp(t,ot,values[:,j]) for j in range(3)])
        old_slice=old.beam_elements[key];new_slice=n.beam_elements[key]
        # Linear element-field transport is explicitly an unaccepted guess.
        for label,target in [('internal_force',force),('internal_moment',moment)]:
            values=np.array(packet[label])[old_slice]
            target[new_slice]=np.column_stack([np.interp(mesh.tm,prior.tm,values[:,j]) for j in range(3)])
        if mesh.beam.lifting:
            values=np.array(packet['circulation'])[old_cursor:old_cursor+len(prior.tm)]
            gamma[new_cursor:new_cursor+len(mesh.tm)]=np.interp(mesh.tm,prior.tm,values)
            old_cursor+=len(prior.tm);new_cursor+=len(mesh.tm)
    assert old_cursor==old.ng and new_cursor==n.ng and n.nc==old.nc
    guess=dict(packet,positions=pose.tolist(),rotations=rotations.tolist(),
        internal_force=force.tolist(),internal_moment=moment.tolist(),circulation=gamma.tolist())
    x=restore_physical_fields(n,guess)
    result=source.save_state(folder,n,x,nodes=n.nn,elements=n.ne,circulation=n.ng,
        qualification='Interpolated initial guess only; full fresh trim and new descriptor are required.')
    assert not result['accepted']
    return result


def response(folder,args):
    import numpy as np
    import scipy.sparse as sp
    from openswing.frequency_response import harmonic_solve
    from openswing.harmonic_structure import ReusableBeamStructure
    assert read(args.matrix/'terminal.json')['returncode']==0
    a=sp.load_npz(args.matrix/'A.npz');m=sp.load_npz(args.matrix/'M.npz')
    with np.load(args.matrix/'maps.npz') as data:b,c=data['B'][:,0],data['C']
    layout=read(STUDY/'mass/layout.json');nn,ne=layout['nodes'],layout['elements']
    assert a.shape==m.shape==(layout['frame']['start']+12,)*2
    for matrix in (a,m):
        for array in (matrix.data,matrix.indices,matrix.indptr):array.flags.writeable=False
    velocity=np.arange(layout['local_velocity']['start'],layout['frame']['start'])
    structure=ReusableBeamStructure(a,m,
        np.r_[np.arange(6*ne),np.arange(6*(nn+ne),layout['circulation']['start'])],
        np.arange(6*(nn+ne)),velocity,velocity)
    rows=[]
    for frequency in args.frequencies:
        z,checks=harmonic_solve(a,m,b,2*np.pi*frequency,_structure=structure)
        out=c@z
        rows.append(dict(frequency_hz=frequency,real=out.real.tolist(),imag=out.imag.tolist(),
            magnitude=abs(out).tolist(),checks=checks))
        np.savez_compressed(folder/f'state-{frequency:.9g}.npz',state=z,output=out)
    return dict(size=a.shape[0],channels=source.CHANNELS,samples=rows,structure=structure.report)


def execute(folder,arguments):
    args=SimpleNamespace(**arguments)
    for key in ('seed','matrix'):
        if getattr(args,key):setattr(args,key,Path(getattr(args,key)))
    args.parts=[Path(p) for p in (args.parts or [])]
    source.imports()
    if args.stage=='init':return initialize(folder,args)
    # Study-local factories only; the production equations are not patched.
    stages.setup=setup;stages.dynamic=dynamic;stages.STUDY=STUDY;source.dynamic=dynamic
    if args.stage in ('trim_geometry','geometry'):return stages.geometry(folder,args)
    if args.stage=='trim_other':return stages.trim_other(folder,args)
    if args.stage=='trim_join':return stages.join_trim(folder,args)
    if args.stage=='trim_rank':return stages.rank_trim(folder,args)
    if args.stage=='correct':return stages.correct(folder,args)
    if args.stage=='geometry_join':return stages.join_geometry(folder,args)
    if args.stage=='response':return response(folder,args)
    return source.staged_linear(folder,args)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage',choices=['init','trim_geometry','trim_other','trim_join','trim_rank',
        'correct','geometry','geometry_join','other','mass','assemble','response'])
    parser.add_argument('--tag',required=True);parser.add_argument('--seed',default=None)
    parser.add_argument('--matrix',default=None);parser.add_argument('--parts',nargs='+')
    parser.add_argument('--start',type=int,default=0);parser.add_argument('--count',type=int,default=96)
    parser.add_argument('--step',type=float,default=1e-5)
    parser.add_argument('--frequencies',type=float,nargs='+',default=[.1,1.15737773741517,1.5])
    args=vars(parser.parse_args());args['speed']=6.7
    if args['stage']!='init' and not args['seed']:parser.error('--seed required')
    inputs=list((ROOT/'openswing').glob('*.py'))+[BASE,PRESET,source.PROJECT,
        ROOT/'examples/dae.asw',ROOT/'docs/validation/ISAE_STATUS.md',
        ROOT/'scripts/check_daedalus_source_operator.py',ROOT/'scripts/check_daedalus_structural_resolution.py',
        ROOT/'reference/aswing-authoritative-20261108/drela-aswing-steady.pdf',
        ROOT/'reference/aswing-authoritative-20261108/drela-aswing-unsteady.pdf',
        ROOT/'docs/validation/aswing-authoritative-sources.json']
    if args['seed']:
        args['seed']=str(Path(args['seed']).resolve());inputs.append(Path(args['seed']))
    for part in (args['parts'] or [])+([args['matrix']] if args['matrix'] else []):
        inputs.extend(Path(part).glob('*.npz'))
        inputs.extend(Path(part)/name for name in ('plan.json','result.json','terminal.json'))
    if args['stage']=='response':inputs.append(STUDY/'mass/layout.json')
    run(STUDY,args['tag'],inputs,execute,args,__file__)


if __name__=='__main__':main()
