"""Three count-preserving material-node redistributions; no fitted parameters."""
import argparse
import importlib.util
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'scripts/verify-sa11-extension-mesh-limit.py'
spec=importlib.util.spec_from_file_location('mesh_limit_driver',SOURCE)
driver=importlib.util.module_from_spec(spec);spec.loader.exec_module(driver)
PARENT=ROOT/'artifacts/isae/sa11-extension-mesh-limit-20261108'
PAIRS=ROOT/'artifacts/isae/sa11-extension-drag-pairs-20261108'


def prepare(out):
    driver.bounded();assert not out.exists()
    parent=driver.read(PARENT/'plan.json');pair_plan=driver.read(PAIRS/'plan.json')
    driver.check(pair_plan['pins'])
    analysis=driver.read(PAIRS/'analysis.json');transitions=driver.read(PAIRS/'spacing-transitions.json')
    assert analysis['verified'] and transitions['verified']
    assert transitions['analysis_sha256']==driver.sha(PAIRS/'analysis.json')
    import numpy as np
    sys.path.insert(0,str(ROOT))
    from openswing.asw import parse_asw
    from openswing.geometry import model_meshes
    from openswing.discretization import requirements
    from openswing.arc_length import material_arc
    pins=dict(pair_plan['pins']);cases=[]
    for case in parent['cases']:
        if case['control']['settings']['speed']!=240 or case['control']['settings']['alpha']!=3:continue
        model= parse_asw((ROOT/case['control']['case']['original_job']['model_path']).read_text(),beam_interpolation='natural-v1')
        old,=model_meshes(model,case['mesh']);arc=material_arc(old.beam)
        required=np.unique([r['t'] for r in requirements(model,mesh_recipe=old.mesh_recipe)[old.beam.index]])
        old_nodes=np.r_[old.t0[0],old.t1];nodes=[];segments=[]
        for left,right in zip(required[:-1],required[1:]):
            selection=(old.t0>=left)&(old.t1<=right)
            count=int(sum(selection));assert count>0
            s0,s1=map(float,arc.at(np.array([left,right])))
            assert (s1-s0)/count>=driver.MINIMUM-1e-12
            values=np.asarray(arc.inverse(np.linspace(s0,s1,count+1)))
            values[0],values[-1]=left,right
            nodes.extend(values[:-1].tolist())
            segments.append(dict(left=float(left),right=float(right),intervals=count,uniform_length=(s1-s0)/count))
        nodes.append(float(required[-1]))
        n=case['requested_intervals'];mesh_spec=dict(default=n,beams={'1':dict(nodes=nodes)})
        mesh,=model_meshes(model,mesh_spec)
        assert len(mesh.tm)==len(old.tm) and min(mesh.length)>=driver.MINIMUM-1e-12
        assert np.array_equal(np.r_[mesh.t0[0],mesh.t1],nodes)
        new=dict(case,id=case['id']+'-redistributed',mesh=mesh_spec,
            preflight=dict(actual_intervals=len(mesh.tm),minimum_interval=float(min(mesh.length)),
                maximum_interval=float(max(mesh.length)),nodes=nodes),
            redistribution=dict(original_mesh=case['mesh'],mandatory_segments=segments,
                maximum_adjacent_width_ratio=float(max(np.maximum(mesh.length[:-1]/mesh.length[1:],mesh.length[1:]/mesh.length[:-1])))))
        cases.append(new)
        folder=PARENT/case['id']
        for path in folder.iterdir():
            if path.is_file():pins[str(path.relative_to(ROOT))]=driver.sha(path)
    assert len(cases)==3
    for path in (Path(__file__),SOURCE,PARENT/'plan.json',PAIRS/'plan.json',PAIRS/'analysis.json',PAIRS/'spacing-transitions.json'):
        pins[str(path.relative_to(ROOT))]=driver.sha(path)
    driver.check(pins)
    out.mkdir(parents=True);(out/'driver-used.py').write_text(Path(__file__).read_text())
    (out/'solver-recorder-used.py').write_text(SOURCE.read_text())
    driver.write(out/'plan.json',dict(observed_utc=driver.utc(),cases=cases,pins=pins,
        source_basis='Saved pair audit:80--86% of latest drag changes arise from adjacent finite-origin wake terms. Exact straight pair identity and candidate-node inspection support testing abrupt width transitions.',
        protocol='All three existing160/172/178-interval extension meshes at240m/s,alpha3. Preserve count in every mandatory-station span,all mandatory stations,minimum16.466mm,original file,settings and equations. Redistribute nodes uniformly in material arc within each mandatory span. No choice based on target error. Explicit nodes are diagnostic alternatives,not a change to production meshing or primary comparison.',
        stability='Use the preceding1% successive-change diagnostic forCL,CD,CDi,Cm across both refinements;not an added5% reference gate. Preserve every rejected result.',
        minimum_spacing=driver.MINIMUM,physical_calls=3,primary_passes_added=0))
    driver.signal.alarm(0)
    print([{key:case['preflight'][key] for key in ('actual_intervals','minimum_interval','maximum_interval')} for case in cases],flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('action',choices=('prepare','run'));parser.add_argument('--index',type=int)
    args=parser.parse_args()
    if args.action=='prepare':prepare(args.output.resolve())
    else:driver.run(args.output.resolve(),args.index)
