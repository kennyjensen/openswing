"""Small serial SA-11 checks of twist sign, documented wake option and mesh.

Only diagnostic inputs change. Original models, production and guards stay fixed.
"""
import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('incidence', ROOT/'scripts/verify-sa11-winglet-incidence.py')
INC = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(INC)
PARENT = ROOT/'artifacts/isae/sa11-winglet-polar-20261108'
read = lambda p: json.loads(p.read_text())
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
utc = lambda: datetime.now(timezone.utc).isoformat()
write = INC.write


def prepare(out):
    assert not out.exists(), out
    parent = read(PARENT/'plan.json')
    pins = dict(parent['unchanged_pins'])
    geometries = {1:'artifacts/isae/sa11-winglet-incidence-20261108/literal_plus4/native-fields.npz',
                  2:'artifacts/isae/sa11-avl-conversion-20261108/isae-sa11-wingtip-up-r2/native-fields.npz'}
    for file in ['reference/aswing_doc.txt','reference/aswing-authoritative-20261108/drela-aswing-steady.pdf',*geometries.values()]:
        pins[file] = sha(ROOT/file)
    cases = []
    for group, (alpha, twist) in enumerate([(1.,4.),(1.,-4.),(5.,4.),(5.,-4.)]):
        variant = 'literal_plus4' if twist == 4 else 'report_minus4'
        for refinement in (1,2):
            for frozen in (True,False):
                case = dict(id=f'g{group}-r{refinement}-'+('frozen' if frozen else 'current'),
                    group=group, alpha=alpha, twist=twist, refinement=refinement, frozen=frozen)
                if refinement == 1 and frozen:
                    path = (ROOT/'artifacts/isae/sa11-winglet-incidence-20261108'/variant/'report.json'
                            if alpha == 1 else PARENT/f'row20-{variant}'/'report.json')
                    case.update(reused_report=str(path.relative_to(ROOT)),reused_sha256=sha(path))
                cases.append(case)
    for name,pin in pins.items(): assert sha(ROOT/name)==pin,name
    out.mkdir(parents=True)
    write(out/'plan.json',dict(observed_utc=utc(),cases=cases,geometry_files=geometries,unchanged_pins=pins,
        driver_sha256=sha(Path(__file__)),previous_goal_turn='progress: twist-sign finding confirmed across21 archived angles, with independent native field agreement',
        protocol='Speed240, density1.2256, alpha1 or5, +/-4 upper twist, native64/128 span meshes, frozen or current-wind influences. Four frozen64 states reused unchanged; twelve production calls new. No native AVL current-wind comparison is implied.',
        rationale='ASW guide F explicitly recommends current-wind influences for nearby wake/surface interactions. Earlier tests were literal+4 at30m/s; the report-minus4 at archived speed needs its own check.',
        limits='An alternative source input and diagnostic mesh do not authenticate the archived producing configuration. All original references and counts remain. Stall and local Mach guard retained.'))
    shutil.copyfile(__file__,out/'driver-used.py')
    print(json.dumps(dict(prepared=True,retained_cases=16,new_calls=12)))


def check(plan):
    for name,pin in plan['unchanged_pins'].items():assert sha(ROOT/name)==pin,name
    assert sha(Path(__file__))==plan['driver_sha256']


def run(out,case,plan):
    directory=out/case['id'];assert not directory.exists();directory.mkdir()
    model=INC.model_at(case['twist'])
    _,segments=INC.CONVERT.conversion(model,case['refinement'])
    with np.load(ROOT/plan['geometry_files'][str(case['refinement'])]) as archive:
        fields={name:archive[name].copy() for name in archive.files}
    meshes,_,errors,settings=INC.CONVERT.mapped_meshes(model,fields,segments)
    condition=INC.FlightCondition(speed=240.,alpha=case['alpha'],density=1.2256,mach=None,freeze_influences=case['frozen'])
    e,_,_=condition.vectors();wind=np.array([1.,0.,0.]) if case['frozen'] else e
    geometry=INC.CONVERT.lifting_geometry(meshes,wind)
    tangent=np.concatenate([m.frames[...,1] for m in meshes])
    write(directory/'setup.json',dict(condition=asdict(condition),settings=settings,frozen_geometry_error=errors))
    gamma=velocity=cl=None;start=time.monotonic()
    try:
        result=INC.evaluate_aerodynamics(model,condition,meshes)
        write(directory/'openswing.json',result)
        gamma=np.array([s['circulation'] for s in result['strips']])
        velocity=np.array([s['relative_velocity'] for s in result['strips']])
        cl=np.array([s['cl'] for s in result['strips']])
        maximum=result['lifting_airflow']['maximum']
        state=dict(status='computed',residual=result['residual'],maximum_section_normal_mach=maximum['normal_mach'],maximum=maximum)
        values={key:result[key] for key in ('CL','CD','CDi','Cm','efficiency')}
    except INC.AnalysisError as exc:
        state=dict(status='rejected',error=str(exc),details=exc.details);values=None
        if exc.details and exc.details.get('kind')=='section_normal_mach':
            tb=exc.__traceback__
            while tb and tb.tb_frame.f_code.co_name!='evaluate_aerodynamics':tb=tb.tb_next
            assert tb is not None
            local=tb.tb_frame.f_locals
            gamma,velocity,cl=[local[key].copy() for key in ('gamma','v','cl')]
            state.update(residual=exc.details['circulation_residual'],maximum_section_normal_mach=exc.details['maximum']['normal_mach'],maximum=exc.details['maximum'])
        write(directory/'openswing-rejected.json',state)
    seconds=time.monotonic()-start
    diagnostic={}
    if gamma is not None:
        margins=[];offset=0
        for m in meshes:
            end=offset+len(m.tm)
            margins.extend(np.minimum(m.beam.value('CLmax',m.tm)-cl[offset:end],cl[offset:end]-m.beam.value('CLmin',m.tm)))
            offset=end
        margins=np.array(margins)
        np.savez(directory/'state.npz',gamma=gamma,velocity=velocity,cl=cl,stall_margin=margins,
                 tangent=tangent,wind=wind,**geometry)
        vp=velocity-np.sum(velocity*tangent,axis=1)[:,None]*tangent
        mach=float(np.linalg.norm(vp,axis=1).max()/340.21)
        assert abs(mach-state['maximum_section_normal_mach'])<1e-12
        diagnostic=dict(minimum_stall_margin_widths=float(margins.min()/.05),stalled_strips=int(np.sum(margins<0)))
    table=np.loadtxt(INC.FOLDER/'Aswing_Simulations/Wing_tip_up/wingtip_up_Ma_0_70.txt')
    row=table[table[:,71]==case['alpha']];assert row.shape==(1,82)
    reference={key:float(row[0,i]) for key,i in [('CL',77),('CD',78),('CDi',79),('Cm',80),('efficiency',81)]}
    report=dict(observed_utc=utc(),case=case,production=state,seconds=seconds,panels=sum(len(m.tm) for m in meshes),
        values=values,reference=reference,error_percent=None if values is None else {key:100*(values[key]/reference[key]-1) for key in values},**diagnostic)
    report['artifact_sha256']={p.name:sha(p) for p in directory.iterdir() if p.is_file()}
    write(directory/'report.json',report)
    print(json.dumps(dict(case=case,status=state['status'],maximum_mach=state.get('maximum_section_normal_mach'),
        maximum=state.get('maximum'),error_percent=report['error_percent'],**diagnostic)),flush=True)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    g=p.add_mutually_exclusive_group(required=True);g.add_argument('--prepare',action='store_true');g.add_argument('--group',type=int)
    a=p.parse_args();out=a.output.resolve()
    if a.prepare:prepare(out);return
    plan=read(out/'plan.json');check(plan)
    cases=[c for c in plan['cases'] if c['group']==a.group];assert len(cases)==4
    for case in cases:
        if 'reused_report' in case:assert sha(ROOT/case['reused_report'])==case['reused_sha256']
        else:run(out,case,plan)
    check(plan)


if __name__=='__main__':main()
