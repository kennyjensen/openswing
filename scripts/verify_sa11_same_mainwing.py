"""Remove winglets while preserving the exact verified SA-11 main wing.

This is a separately labelled geometry-only control, not a replacement for
the archived bare-wing model. The existing bounded recorder performs solves.
"""
from copy import deepcopy
import argparse
import importlib.util
from pathlib import Path
import re
import sys

ROOT=Path(__file__).resolve().parents[1]
RECORDER=ROOT/'scripts/verify_sa11_paper_aligned.py'
module=importlib.util.spec_from_file_location('aligned_recorder',RECORDER)
driver=importlib.util.module_from_spec(module);module.loader.exec_module(driver)
UPPER=ROOT/'artifacts/isae/sa11-minimum-spacing-20261108'
ALIGNED=ROOT/'artifacts/isae/sa11-paper-aligned-20261108'
PAPER=ROOT/'artifacts/isae/sa11-paper-suite-aligned-20261108'


def prepare(out):
    driver.bounded();assert not out.exists()
    parent=driver.read(UPPER/'plan.json')
    driver.check(parent['pins'])
    pins=dict(parent['pins'])
    for name,digest in parent['generated_pins'].items():
        assert driver.sha(UPPER/name)==digest
        pins[str((UPPER/name).relative_to(ROOT))]=digest
    paper=driver.read(PAPER/'analysis.json')
    proof=driver.read(PAPER/'verification.json')
    assert proof['verified'] and proof['analysis_sha256']==driver.sha(PAPER/'analysis.json')
    for item in driver.read(ROOT/'docs/validation/aswing-authoritative-sources.json')['files']:
        if item['id'] in ('isae-part-1','drela-steady'):
            for key,digestkey in [('local_pdf','sha256'),('local_text','text_sha256')]:
                assert driver.sha(ROOT/item[key])==item[digestkey]
                pins[item[key]]=item[digestkey]
    source=(UPPER/'model.asw').read_text()
    lines=source.splitlines(keepends=True);removed=[];remove_indices=set()
    for index,line in enumerate(lines):
        if not (re.match(r'^Joint\s*$',line.strip()) or re.match(r'^Beam\s+[23](?:\s|$)',line)):
            continue
        end=next(j for j in range(index+1,len(lines)) if lines[j].strip()=='End')
        removed.append(dict(start_line=index+1,end_line=end+1,text=''.join(lines[index:end+1])))
        remove_indices.update(range(index,end+1))
    assert len(removed)==3
    retained=''.join(line for i,line in enumerate(lines) if i not in remove_indices)
    header='# SA-11 geometry-only control: upper-winglet model with only Joint and Beam2/3 blocks removed.\n# Main-wing tables, references and explicit32-node-interval mesh are unchanged; not the archived baseline input.\n'
    control=header+retained
    beam1=lambda text:re.search(r'^Beam[ \t]+1[ \t]+1[ \t]*\r?\n.*?^End[ \t]*\r?$',text,re.M|re.S).group(0)
    assert beam1(control)==beam1(source)
    sys.path.insert(0,str(ROOT))
    import numpy as np
    from openswing.asw import parse_asw
    from openswing.geometry import model_meshes
    from openswing.frozen_influence import lifting_geometry
    parent_model=parse_asw(source,beam_interpolation='natural-v1')
    model=parse_asw(control,beam_interpolation='natural-v1')
    assert len(model.beams)==1 and model.beams[0].index==1 and not model.diagnostics
    assert np.array_equal(model.reference,parent_model.reference)
    parent_mesh_spec=driver.read(UPPER/'mesh-import.json')['panels']
    mesh_spec=dict(default=parent_mesh_spec['default'],beams={'1':deepcopy(parent_mesh_spec['beams']['1'])})
    parent_meshes=model_meshes(parent_model,parent_mesh_spec)
    mesh,=model_meshes(model,mesh_spec)
    assert len(mesh.tm)==32
    for field in ('t0','t1','tm','ts','theta','r0','r1','rm','frames','length'):
        assert np.array_equal(getattr(mesh,field),getattr(parent_meshes[0],field)),field
    g=lifting_geometry([mesh],np.array([1.,0.,0.]))
    parent_g=lifting_geometry(parent_meshes,np.array([1.,0.,0.]))
    for field in g:assert np.array_equal(g[field],parent_g[field][:32]),field
    section_keys=('dCLda','Cdf','Cdp','alpha','Cm','CLmin','CLmax')
    for field in section_keys:
        assert np.array_equal(mesh.beam.value(field,mesh.tm),parent_meshes[0].beam.value(field,mesh.tm)),field
    before=driver.read(ALIGNED/'plan.json')
    cases=[]
    for label,speed in [('0_70',240.),('0_80',272.)]:
        baseline=next(c for c in before['cases'] if c['configuration']=='wing_alone' and c['label']==label)
        path=ROOT/baseline['table']
        pins[baseline['table']]=driver.sha(path)
        rows=[line.split() for line in path.read_text().splitlines() if len(line.split())==82 and line.split()[0].isdigit()]
        assert len(rows)==41
        for i in range(25):
            tokens=rows[i];alpha=i/4
            assert float(tokens[71])==alpha and float(tokens[69])==speed
            cases.append(dict(id=f'mainwing-control-m{label}-a{i:02d}',configuration='wing_alone',
                model_variant='upper-winglet model with winglets removed',label=label,row=i,alpha=alpha,
                model_path=str((out/'model.asw').relative_to(ROOT)),mesh=mesh_spec,
                condition=dict(parent['cases'][0]['condition'],alpha=alpha,speed=speed,mach=speed/340.21),
                table=baseline['table'],tokens=tokens,
                reference={k:float(tokens[c]) for k,c in driver.FIELDS.items()},reused_accepted=None))
    assert len(cases)==50
    upper_controls=[]
    for curve in paper['curves']:
        if curve['configuration']!='upper_winglet':continue
        for point in curve['points']:
            assert point['valid']
            path=ROOT/point['source'];report=driver.read(path)
            for name,digest in report['artifacts'].items():
                assert driver.sha(path.parent/name)==digest
                pins[str((path.parent/name).relative_to(ROOT))]=digest
            pins[str(path.relative_to(ROOT))]=driver.sha(path)
            upper_controls.append(dict(label=curve['label'],alpha=point['alpha'],report=point['source'],
                accepted=str((path.parent/'accepted.json').relative_to(ROOT))))
    assert len(upper_controls)==43
    for path in (Path(__file__),RECORDER,ROOT/'scripts/check_sa11_paper_aligned.py',UPPER/'plan.json',
        UPPER/'verification.json',PAPER/'analysis.json',PAPER/'verification.json',ALIGNED/'plan.json',
        ROOT/'docs/validation/aswing-authoritative-sources.json',ROOT/'reference/aswing_doc.txt'):
        pins[str(path.relative_to(ROOT))]=driver.sha(path)
    driver.check(pins)
    out.mkdir(parents=True)
    (out/'model.asw').write_text(control)
    driver.write(out/'mesh-import.json',dict(format='openswing-mesh',version=1,panels=mesh_spec))
    (out/'driver-used.py').write_text(Path(__file__).read_text())
    (out/'recorder-used.py').write_text(RECORDER.read_text())
    for name in ('model.asw','mesh-import.json','driver-used.py','recorder-used.py'):
        pins[str((out/name).relative_to(ROOT))]=driver.sha(out/name)
    preflight={'wing_alone':[dict(beam=1,nodes=[float(mesh.t0[0]),*map(float,mesh.t1)],intervals=32,
        minimum=float(min(mesh.length)))]}
    driver.write(out/'plan.json',dict(observed_utc=driver.utc(),cases=cases,pins=pins,preflight=preflight,
        upper_controls=upper_controls,removed_source_blocks=removed,added_comment=header,
        parent_model=str((UPPER/'model.asw').relative_to(ROOT)),
        geometry_identity=dict(main_beam_text_identical=True,all_reference_rows_identical=True,
            mesh_arrays_identical=True,source_endpoints_receivers_frames_identical=True,
            all_sampled_section_fields_identical=True,actual_mainwing_intervals=32),
        previous_goal_turn='Progress:89 new aligned solves plus4saved states verified; upper-winglet bracket adds1pass to unchanged48target suite. Baseline source changes main-wing lift/drag data, so next action isolates wingtip geometry with exact common main wing.',
        protocol='Remove only Joint andBeam2/3 blocks from the verified report-derived upper-winglet model, plus descriptive comments. Retain every main-wing table, explicit32-interval mesh and all references. Frozen influences, true-speed PG, same density and stall/core settings. Fifty states0..6degrees quarter-step at240/272m/s, declared before solves; all rejections retained. Reuse43verified upper-winglet states. No fitted parameters or production changes.',
        comparison='Compare baseline CL at1/3/5degrees and CD atCL0.3/0.5/0.7 to the archived bare-wing curve as a disclosed alternative. Compare upper-minus-control CL and equal-lift CD, including main-wing and winglet force decomposition. Do not replace or add to primary21/48 or original1060/9184.',
        source_basis='Jan PartI p35,Fig22 p39 andAppendixD; Drela steady load laws and documented frozen-influence option. Same physical aircraft with wingtip-device removal motivates a shared main-wing control; historical generating parameters remain unverified.',
        physical_calls=50,reused_states=0,primary_passes_added=0,
        limits='One BLAS thread;512MiB address space;15CPU/25wall seconds;at most3serialcalls per foreground invocation. No browser,Vite,build or background jobs.'))
    driver.signal.alarm(0)
    print(dict(prepared=True,physical_calls=50,reused_upper_states=43,intervals=32,identical_main_geometry=True))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('prepare','batch'));parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--start',type=int);parser.add_argument('--count',type=int,default=3)
    args=parser.parse_args()
    if args.action=='prepare':prepare(args.output.resolve())
    else:driver.batch(args.output.resolve(),args.start,args.count)
