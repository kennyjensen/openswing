"""Regular Daedalus mesh and fresh trim, in bounded serial stages."""
import argparse
from pathlib import Path
from types import SimpleNamespace
from check_daedalus_load_sensitivity import ROOT,read,write
from daedalus_bounded_job import run
import check_daedalus_default_mesh_response as previous

STUDY=ROOT/'artifacts/daedalus-regular-mesh-20261114'
BASE=ROOT/'artifacts/daedalus-default-mesh-response-20261114/trim-1/state.json'
PRESET=ROOT/'web/daedalus-mesh.json'
source=previous.source
stages=previous.stages


def network(packet,panels=None):
    from openswing.asw import parse_asw
    from openswing.source_airflow import SourceAirflowNetwork
    from openswing.time_state import read_condition
    model=parse_asw((ROOT/'examples/dae.asw').read_text(),beam_interpolation='drela-segspl-v1')
    launch=packet['launch']
    return SourceAirflowNetwork(model,read(PRESET) if panels is None else panels,
        read_condition(launch['condition']),launch['gravity'],launch['loads'],
        operating_constraints=launch['released_constraints'],strut_mode=launch['strut_mode'],
        mesh_recipe='accurate-arc-v2',steady_trim=True)


def setup(seed):
    from openswing.equilibrium_state import restore
    packet=read(seed);n=network(packet)
    return n,restore(n,packet)


def old_setup(seed):
    from openswing.equilibrium_state import restore
    packet=read(seed);n=network(packet,packet['launch']['panels'])
    return n,restore(n,packet)


def tests(folder,args):
    import pytest
    result=pytest.main(['-q','-p','no:cacheprovider','tests/test_regular_spacing.py',
        'tests/test_minimum_horseshoe_spacing.py'])
    assert result==0
    return dict(pytest_exit=int(result))


def mesh(folder,args):
    import numpy as np
    from openswing.discretization import report,requirements
    from openswing.geometry import geometry_summary
    rows=[]
    for name,panels in [('previous',read(BASE)['launch']['panels']),('regular',read(PRESET))]:
        n=network(read(BASE),panels);required=requirements(n.model)
        geometry=geometry_summary(n.model,meshes=n.meshes)
        write(folder/f'{name}-geometry.json',geometry)
        write(folder/f'{name}-nodes.json',report(n.model,n.meshes,panels))
        for m in n.meshes:
            assert {r['t'] for r in required[m.beam.index]}<=set(np.r_[m.t0,m.t1[-1]])
            rows.append(dict(mesh=name,beam=m.beam.index,name=m.beam.name,intervals=len(m.tm),
                minimum=float(min(m.length)),maximum=float(max(m.length))))
    return dict(rows=rows,nodes=n.nn,elements=n.ne,circulation=n.ng,all_required_stations=True)


def audit(folder,args):
    import numpy as np
    n,x=setup(args.seed);error=float(max(abs(n.residual(x))));assert error<1e-9
    system=previous.dynamic(args);zero=np.zeros(system.size);base=system.base_report()
    dynamic_error=float(max(abs(system.residual(zero,zero))))
    assert dynamic_error<1e-9 and base['modal_base']['kinematically_steady']
    assert abs(base['earth_state']['flight_path'])<1e-7
    return dict(residual=error,dynamic_residual=dynamic_error,nodes=n.nn,elements=n.ne,
        circulation=n.ng,dynamic_states=system.size,condition=read(args.seed)['launch']['condition'],
        flight_path=base['earth_state']['flight_path'],
        weight_lb=float(base['mass_properties']['mass']*np.linalg.norm(base['gravity_body'])))


def execute(folder,arguments):
    args=SimpleNamespace(**arguments);args.seed=Path(args.seed) if args.seed else None
    args.matrix=Path(args.matrix) if args.matrix else None;args.parts=[Path(p) for p in args.parts or []]
    source.imports();previous.network=network;previous.BASE=BASE;previous.STUDY=STUDY
    if args.stage=='init':
        stages.setup=old_setup
        return previous.initialize(folder,args)
    previous.setup=setup;stages.setup=setup;stages.dynamic=previous.dynamic
    if args.stage in ('mesh','tests','audit'):return globals()[args.stage](folder,args)
    return {'trim_geometry':stages.geometry,'trim_other':stages.trim_other,
        'trim_join':stages.join_trim,'trim_rank':stages.rank_trim,'correct':stages.correct}[args.stage](folder,args)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage',choices=['mesh','tests','init','trim_geometry','trim_other','trim_join','trim_rank','correct','audit'])
    parser.add_argument('--tag',required=True);parser.add_argument('--seed');parser.add_argument('--matrix')
    parser.add_argument('--parts',nargs='+');parser.add_argument('--start',type=int,default=0)
    parser.add_argument('--count',type=int,default=96);parser.add_argument('--step',type=float,default=1e-5)
    args=vars(parser.parse_args());args['speed']=6.7
    for key in ('seed','matrix'):
        if args[key]:args[key]=str(Path(args[key]).resolve())
    inputs=list((ROOT/'openswing').glob('*.py'))+[BASE,PRESET,ROOT/'examples/dae.asw',
        ROOT/'tests/test_regular_spacing.py',ROOT/'tests/test_minimum_horseshoe_spacing.py',
        ROOT/'scripts/check_daedalus_default_mesh_response.py',
        ROOT/'scripts/check_daedalus_source_operator.py',ROOT/'scripts/check_daedalus_structural_resolution.py',
        ROOT/'docs/validation/aswing-authoritative-sources.json',ROOT/'docs/validation/ISAE_STATUS.md']
    if args['seed']:inputs.append(Path(args['seed']))
    for part in (args['parts'] or [])+([args['matrix']] if args['matrix'] else []):
        inputs.extend(p for p in Path(part).iterdir() if p.suffix in ('.npz','.json'))
    run(STUDY,args['tag'],inputs,execute,args,__file__)
