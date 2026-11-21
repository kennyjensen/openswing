"""Six prescribed same-main-wing mesh controls near CL=.5 at 240m/s."""
import argparse
from copy import deepcopy
import importlib.util
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'scripts/verify_sa11_paper_aligned.py'
spec=importlib.util.spec_from_file_location('aligned_recorder',SOURCE)
driver=importlib.util.module_from_spec(spec);spec.loader.exec_module(driver)
PARENT=ROOT/'artifacts/isae/sa11-same-mainwing-20261108'
UPPER=ROOT/'artifacts/isae/sa11-minimum-spacing-20261108'


def prepare(out):
    driver.bounded();assert not out.exists()
    parent=driver.read(PARENT/'plan.json');analysis=driver.read(PARENT/'analysis.json')
    assert analysis['verified'] and analysis['plan_sha256']==driver.sha(PARENT/'plan.json')
    driver.check(parent['pins']);pins=dict(parent['pins'])
    import numpy as np
    sys.path.insert(0,str(ROOT))
    from openswing.asw import parse_asw
    from openswing.geometry import model_meshes
    from openswing.frozen_influence import lifting_geometry
    cases=[];preflight={};geometries={}
    for configuration,angles in [('wing_alone',(3.,3.25,3.5)),('upper_winglet',(2.5,2.75,3.))]:
        model_path=PARENT/'model.asw' if configuration=='wing_alone' else UPPER/'model.asw'
        original_mesh=driver.read((PARENT if configuration=='wing_alone' else UPPER)/'mesh-import.json')['panels']
        mesh_spec=deepcopy(original_mesh)
        mesh_spec['beams']['1']=dict(count=64,spacing='cosine',min_spacing=.0164659927127284)
        model=parse_asw(model_path.read_text(),beam_interpolation='natural-v1')
        old_meshes=model_meshes(model,original_mesh);meshes=model_meshes(model,mesh_spec)
        assert len(meshes[0].tm)==62
        oldg=lifting_geometry(old_meshes,np.array([1.,0.,0.]))
        g=lifting_geometry(meshes,np.array([1.,0.,0.]))
        if configuration=='upper_winglet':
            assert [len(m.tm) for m in meshes]==[62,16,16]
            for key in g:assert np.array_equal(g[key][62:],oldg[key][32:]),key
            for key in g:assert np.array_equal(g[key][:62],geometries['wing_alone'][key]),key
        geometries[configuration]=g
        preflight[configuration]=[dict(beam=m.beam.index,nodes=[float(m.t0[0]),*map(float,m.t1)],
            intervals=len(m.tm),minimum=float(min(m.length))) for m in meshes]
        for alpha in angles:
            if configuration=='wing_alone':
                prior=next(c for c in parent['cases'] if c['label']=='0_70' and c['alpha']==alpha)
            else:
                prior=next(c for c in driver.read(UPPER/'plan.json')['cases'] if c['label']=='0_70' and c['alpha']==alpha)
                prior=dict(prior,model_path=str(model_path.relative_to(ROOT)),reused_accepted=None)
            case=dict(prior,id=f'{configuration}-main64-m0_70-a{int(4*alpha):02d}',configuration=configuration,
                mesh=mesh_spec,model_path=str(model_path.relative_to(ROOT)))
            cases.append(case)
    for path in (Path(__file__),SOURCE,PARENT/'plan.json',PARENT/'analysis.json',PARENT/'verification-wing_alone.json',
        UPPER/'plan.json',UPPER/'analysis.json',UPPER/'verification.json'):
        pins[str(path.relative_to(ROOT))]=driver.sha(path)
    driver.check(pins);out.mkdir(parents=True)
    (out/'driver-used.py').write_text(Path(__file__).read_text())
    (out/'recorder-used.py').write_text(SOURCE.read_text())
    driver.write(out/'plan.json',dict(observed_utc=driver.utc(),cases=cases,pins=pins,preflight=preflight,
        physical_calls=6,primary_passes_added=0,
        protocol='Shared report-derived main wing, without/with upper winglets. Prescribed240m/s brackets nearCL.5:bare3/3.25/3.5degrees,upper2.5/2.75/3degrees. Change only main explicit32 intervals to cosine64 with same16.466mm minimum, yielding62. Both meshes share identical main nodes. Upper winglet16+16 geometry/receivers remain exactly unchanged. No fitting, winglet refinement or new primary acceptance gate.',
        previous_result='Same-main-wing control50/50valid; baseline6/12 diagnostic matches. AtCL.5 drag benefit overpredicted37.0% at240m/s. Test whether shared main-wing discretization changes that difference.',
        geometry_invariants=dict(main_same_between_models=True,winglet_source_and_receiver_arrays_unchanged=True),
        limits='One BLAS thread;512MiB address space;15CPU/25wall seconds;at most3serialcalls. No background or browser jobs.'))
    driver.signal.alarm(0)
    print(dict(prepared=True,cases=6,counts={k:[b['intervals'] for b in v] for k,v in preflight.items()}))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=('prepare','batch'))
    p.add_argument('--output',type=Path,required=True);p.add_argument('--start',type=int);p.add_argument('--count',type=int,default=3)
    a=p.parse_args()
    if a.action=='prepare':prepare(a.output.resolve())
    else:driver.batch(a.output.resolve(),a.start,a.count)
