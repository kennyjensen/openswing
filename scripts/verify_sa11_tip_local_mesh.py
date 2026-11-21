"""Six SA-11 controls changing only the outer two original main-wing intervals."""
import argparse
from copy import deepcopy
import importlib.util
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT/'scripts/verify_sa11_paper_aligned.py'
spec = importlib.util.spec_from_file_location('aligned_recorder',SOURCE)
driver = importlib.util.module_from_spec(spec); spec.loader.exec_module(driver)
BASE = ROOT/'artifacts/isae/sa11-same-mainwing-20261108'
FINE = ROOT/'artifacts/isae/sa11-same-mainwing-mesh-20261108'
UPPER = ROOT/'artifacts/isae/sa11-minimum-spacing-20261108'
AUDIT = ROOT/'artifacts/isae/sa11-winglet-interactions-20261108'


def prepare(out):
    driver.bounded(); assert not out.exists()
    analysis = driver.read(AUDIT/'analysis.json'); assert analysis['verified']
    pins = dict(analysis['pins']); driver.check(pins)
    prior = driver.read(FINE/'plan.json')
    original = driver.read(BASE/'mesh-import.json')['panels']['beams']['1']['nodes']
    finer = prior['preflight']['wing_alone'][0]['nodes']
    left,right = original[2],original[-3]
    # Keep the complete original interior. Substitute the already prescribed
    # fine-grid nodes only outside the second original node from either tip.
    nodes = [t for t in finer if t<left]+original[2:-2]+[t for t in finer if t>right]
    assert len(nodes)-1 == 46
    import numpy as np
    sys.path.insert(0,str(ROOT))
    from openswing.asw import parse_asw
    from openswing.geometry import model_meshes
    from openswing.frozen_influence import lifting_geometry
    cases=[]; preflight={}; geometries={}; invariants={}
    for config in ('wing_alone','upper_winglet'):
        seed=next(c for c in prior['cases'] if c['configuration']==config)
        model=parse_asw((ROOT/seed['model_path']).read_text(),beam_interpolation='natural-v1')
        oldspec=driver.read((BASE if config=='wing_alone' else UPPER)/'mesh-import.json')['panels']
        mesh=deepcopy(oldspec);mesh['beams']['1']=dict(nodes=nodes)
        old=model_meshes(model,oldspec);new=model_meshes(model,mesh)
        assert len(new[0].tm)==46
        assert min(new[0].length)>=.0164659927127284-1e-12
        oldg=lifting_geometry(old,np.array([1.,0.,0.]));g=lifting_geometry(new,np.array([1.,0.,0.]))
        keep=(new[0].t0>=left-1e-12)&(new[0].t1<=right+1e-12)
        assert sum(keep)==28
        errors={key:float(np.max(abs(g[key][:46][keep]-oldg[key][:32][2:-2]))) for key in ('a','b','hv','cp','rm','chord','ds')}
        assert max(errors.values())<2e-12,errors
        if config=='upper_winglet':
            for key in g:
                assert np.array_equal(g[key][46:],oldg[key][32:]),key
                assert np.array_equal(g[key][:46],geometries['wing_alone'][key]),key
        geometries[config]=g
        invariants[config]=dict(interior_intervals_retained=28,maximum_interior_geometry_errors=errors)
        preflight[config]=[dict(beam=m.beam.index,nodes=[float(m.t0[0]),*map(float,m.t1)],
                               intervals=len(m.tm),minimum=float(min(m.length))) for m in new]
        for oldcase in prior['cases']:
            if oldcase['configuration']==config:
                cases.append(dict(oldcase,id=f"{config}-tip-local-m0_70-a{int(4*oldcase['alpha']):02d}",mesh=mesh))
    for path in (Path(__file__),SOURCE,FINE/'plan.json',AUDIT/'analysis.json'):
        pins[str(path.relative_to(ROOT))]=driver.sha(path)
    driver.check(pins);out.mkdir(parents=True)
    (out/'driver-used.py').write_text(Path(__file__).read_text())
    (out/'recorder-used.py').write_text(SOURCE.read_text())
    driver.write(out/'plan.json',dict(observed_utc=driver.utc(),pins=pins,cases=cases,preflight=preflight,
        geometry_invariants=invariants,cutoff_parameters=[left,right],main_nodes=nodes,physical_calls=6,primary_passes_added=0,
        protocol='240m/s,bare3/3.25/3.5degrees,upper2.5/2.75/3degrees. Replace only outer two original main32 intervals per side with nodes from the pre-existing main62 grid; retain all28 interior intervals, winglets16each, source model and frozen influences. Result46main intervals, same16.466mm minimum. Not a new production mesh or primary acceptance gate.',
        coordinate_note='Main ASW parameter t equals projected span coordinate y in metres. The exploratory audit bin0.125 is a span-coordinate distance, not beam arc length. Cutoff at abs(t)~1.0413 replaces the outer0.2013m projected span on either side.',
        previous_goal_turn='Progress: nine saved-state audits locate most mesh-dependent drag change in finite-origin main/winglet interactions at the outer main wing. This local-only mesh trial tests that attribution with a new coupled circulation solution.',
        limits='One BLAS thread,512MiB address space,15CPU/25wall seconds,at most3serialcalls. No browser/background jobs.'))
    driver.write(out/'mesh-import.json',dict(panels=next(c['mesh'] for c in cases if c['configuration']=='upper_winglet')))
    driver.signal.alarm(0)
    print(dict(prepared=True,cases=len(cases),main_intervals=46,retained_interior=28,cutoff=[left,right],invariants=invariants))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=('prepare','batch'))
    p.add_argument('--output',type=Path,required=True);p.add_argument('--start',type=int);p.add_argument('--count',type=int,default=3)
    a=p.parse_args()
    if a.action=='prepare':prepare(a.output.resolve())
    else:driver.batch(a.output.resolve(),a.start,a.count)
