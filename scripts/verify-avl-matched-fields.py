"""Serial one-row native AVL / OpenSwing geometry and field comparison.

Only the copied native output routine is extended. Native numerical objects,
the original binary, production Python, and registered ISAE scopes stay fixed.
Use prepare, build, and one case per invocation. Never overwrite an outcome.
"""
import argparse
from dataclasses import asdict, replace
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from openswing.aero import FlightCondition, evaluate_aerodynamics
from openswing.asw import parse_asw
from openswing.factored_influence import FactoredInfluence
from openswing.frozen_influence import lifting_geometry
from openswing.geometry import model_meshes, surface_frame

BUILD = ROOT/'artifacts/isae/avl-native-build-20261108'
BASE = ROOT/'artifacts/isae/avl-native-controls-20261108'
SPEC = importlib.util.spec_from_file_location('native_controls', ROOT/'scripts/verify-avl-native-controls.py')
NATIVE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(NATIVE)
FIELDS = ('RV1', 'RV2', 'RV', 'RC', 'ENC', 'ENV', 'VV', 'VINF')


def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def utc(): return datetime.now(timezone.utc).isoformat()
def write(p, value): p.write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')


def unchanged(plan):
    for name, pin in plan['unchanged_pins'].items():
        assert sha(ROOT/name) == pin, name
    for name, pin in plan['native_objects'].items():
        assert sha(BUILD/'objects'/name) == pin, name
    assert sha(BUILD/'avl') == plan['original_binary_sha256']


def prepare(out, parent=None):
    assert not out.exists(), out
    previous = json.loads((BASE/'plan.json').read_text())
    out.mkdir(parents=True)
    original = BUILD/'source/src/aoutmrf.f'
    anchor = "     &        '| I, X, Y, Z, DX, Slope, dCp'\n"
    source = original.read_text()
    assert source.count(anchor) == 1
    extra = 'C---- Read-only diagnostic export; no solver state assignments.\n'
    for field in FIELDS:
        value = f'({field}(K,I),K=1,3)' if field != 'VINF' else '(VINF(K),K=1,3)'
        extra += "            WRITE(LUN,'(A,1X,I6,3(1X,ES25.16))')\n"
        extra += f"     &        'DIAG_{field}',I,{value}\n"
    extra += "            WRITE(LUN,'(A,1X,I6,1X,ES25.16)')\n     &        'DIAG_GAM',I,GAM(I)\n"
    patched = source.replace(anchor, anchor+extra)
    assert patched.replace(extra, '') == source
    (out/'aoutmrf.f').write_text(patched)
    cases = []
    for geometry in ('rectangle', 'winglets'):
        for ns in (16, 32, 64):
            cases.append(dict(id=f'{geometry}-c1-s{ns}', geometry=geometry,
                nchord=1, nspan=ns, alpha=5., sweep=0., legs=False))
    if parent is not None:
        cases=[dict(id=f'swept-c1-s{ns}',geometry='swept',nchord=1,nspan=ns,
                    alpha=5.,sweep=30.,legs=False) for ns in (16,32,64)]
    for case in cases:
        parsed=parse_asw(asw_source(case))
        assert len(parsed.beams)==(3 if case['geometry']=='winglets' else 1)
    plan = dict(observed_utc=utc(), previous_turn='progress: report/source audit distinguishes original 5.96 reference curves from ISAE modifications',
        cases=cases, original_binary_sha256=sha(BUILD/'avl'),
        original_output_source_sha256=sha(original), patched_output_source_sha256=sha(out/'aoutmrf.f'),
        patch=extra, unchanged_pins=previous['unchanged_pins'],
        native_objects={p.name:sha(p) for p in sorted((BUILD/'objects').glob('*.o'))},
        driver_sha256=sha(Path(__file__)), native_driver_sha256=sha(ROOT/'scripts/verify-avl-native-controls.py'),
        protocol='One native console solve and one production Python solve per case. Export endpoints, bound/control receiver positions, normals, induced bound velocity and circulation. Match exact native nodes and receivers with explicit diagnostic meshes. Compare generated ASWING receivers separately. Mach=0, no stall, no viscosity, speed=1, frozen body-x influences. Native tiny fourth-power core is retained; OpenSwing same-physical core is zero.',
        force_convention='Both use induced velocity at the stored bound receiver, not necessarily the arithmetic midpoint printed by FE. Native source still determines all outputs.',
        limits='One-row diagnostic; not a native ASWING result, not the offset/forked SA-11 geometry, not a new ISAE pass.')
    if parent is not None:
        old_plan=json.loads((parent/'plan.json').read_text());unchanged(old_plan)
        old_build=json.loads((parent/'build.json').read_text())
        assert old_build['status']=='built'
        assert sha(parent/'avl-fields')==old_build['binary_sha256']
        assert old_plan['patched_output_source_sha256']==plan['patched_output_source_sha256']
        shutil.copyfile(parent/'avl-fields',out/'avl-fields')
        (out/'avl-fields').chmod(0o755)
        plan['parent_plan']=str((parent/'plan.json').relative_to(ROOT))
        plan['parent_plan_sha256']=sha(parent/'plan.json')
        plan['swept_geometry']='30-degree straight oblique quarter-chord axis; normal chord cos(30 degrees) gives native streamwise chord 1, identical 3/4-control offset and strip area. No fitted parameter.'
        write(out/'build.json',dict(observed_utc=utc(),status='built',binary_sha256=sha(out/'avl-fields'),
            reused_build=str((parent/'build.json').relative_to(ROOT)),reused_build_sha256=sha(parent/'build.json')))
    unchanged(plan)
    write(out/'plan.json', plan)
    shutil.copyfile(__file__, out/'driver-used.py')
    print(json.dumps(dict(status='prepared',cases=len(cases))))


def build(out):
    plan=json.loads((out/'plan.json').read_text());unchanged(plan)
    assert not (out/'build.json').exists()
    assert sha(out/'aoutmrf.f')==plan['patched_output_source_sha256']
    flags=json.loads((BUILD/'plan.json').read_text())
    command=['gfortran',*flags['fortran_flags'],*flags['double_flags'],
             '-I'+str(BUILD/'source/src'),'-I'+str(BUILD/'objects'),'-J'+str(out),
             '-c',str(out/'aoutmrf.f'),'-o',str(out/'aoutmrf.o')]
    records=[]
    for step in ('compile','link'):
        if step=='link':
            command=json.loads((BUILD/'link.json').read_text())['command']
            command=[str(out/'avl-fields') if s==str(BUILD/'avl') else
                     str(out/'aoutmrf.o') if s==str(BUILD/'objects/aoutmrf.o') else s for s in command]
        start=time.monotonic()
        p=subprocess.run(command,capture_output=True,text=True,timeout=35,cwd=out)
        records.append(dict(step=step,command=command,returncode=p.returncode,
            seconds=time.monotonic()-start,stdout=p.stdout,stderr=p.stderr))
        write(out/'build.json',dict(observed_utc=utc(),records=records,status='running' if p.returncode==0 else 'failed'))
        assert p.returncode==0,p.stderr
    unchanged(plan)
    write(out/'build.json',dict(observed_utc=utc(),records=records,status='built',binary_sha256=sha(out/'avl-fields')))
    print(json.dumps(dict(status='built',seconds=sum(r['seconds'] for r in records))))


def read_fields(path):
    rows={name:[] for name in (*FIELDS,'GAM')}
    for line in path.read_text().splitlines():
        if not line.startswith('DIAG_'):continue
        fields=line.split();name=fields[0].removeprefix('DIAG_')
        assert int(fields[1])==len(rows[name])+1
        rows[name].append([float(x) for x in fields[2:]])
    return {k:np.array(v) for k,v in rows.items()}


def asw_source(c):
    parts=[((.25,-5.,0.),(.25,5.,0.))]
    if c['geometry']=='winglets':
        parts=[((.25,-5.,1.),(.25,-5.,0.)),*parts,((.25,5.,0.),(.25,5.,1.))]
    slope=np.tan(np.deg2rad(c['sweep']))
    chord=np.cos(np.deg2rad(c['sweep']))
    parts=[(tuple((.25+slope*a[1],a[1],a[2])),tuple((.25+slope*b[1],b[1],b[2]))) for a,b in parts]
    source='Name\nMatched one-row AVL diagnostic\nEnd\nUnit\nL 1 m\nT 1 s\nF 1 N\nEnd\nConstant\n9.80665 1.225 340.294\nEnd\nReference\n10 1 10\n.25 0 0\nEnd\n'
    for i,(a,b) in enumerate(parts,1):
        source+=f'Beam {i} 1\nPart {i}\nt x y z chord Xax dCLda Cdf Cdp Cm\n'
        length=float(np.linalg.norm(np.array(b)-a))
        # ASWING reflects nonnegative-only beam tables. A centered parameter
        # domain describes precisely this entire segment, without reflection.
        for t,r in ((-length/2,a),(length/2,b)):
            source+=f'{t:.17g} '+' '.join(f'{x:.17g}' for x in r)+f' {chord:.17g} .25 {2*np.pi:.17g} 0 0 0\n'
        source+='End\n'
    return source


def match_mesh(model,c,f):
    counts=[c['nspan']//4,c['nspan'],c['nspan']//4] if c['geometry']=='winglets' else [c['nspan']]
    settings={};samples={};i=0
    for beam,count in zip(model.beams,counts,strict=True):
        a,b=beam.position(np.array(beam.domain));direction=(b-a)/np.linalg.norm(b-a)
        nodes=np.r_[f['RV1'][i:i+count]@direction,f['RV2'][i+count-1]@direction]-a@direction+beam.domain[0]
        nodes[0],nodes[-1]=beam.domain
        settings[str(beam.index)]=dict(nodes=nodes.tolist())
        samples[beam.index]=(f['RV'][i:i+count]-a)@direction+beam.domain[0]
        i+=count
    generated=model_meshes(model,dict(default=16,beams=settings))
    meshes=[replace(m,tm=samples[m.beam.index],rm=m.beam.position(samples[m.beam.index]),
                    frames=surface_frame(m.beam,samples[m.beam.index])) for m in generated]
    g=lifting_geometry(meshes,np.array([1.,0.,0.]))
    before=lifting_geometry(generated,np.array([1.,0.,0.]))
    errors={k:float(np.max(abs(g[k]-f[n]))) for k,n in [('a','RV1'),('b','RV2'),('hv','RV'),('cp','RC')]}
    errors['normals']=float(np.max(abs(np.concatenate([m.frames[...,2] for m in meshes])-f['ENC'])))
    errors['generated_receiver_difference']=float(np.max(abs(before['hv']-f['RV'])))
    errors['native_printed_midpoint_vs_force_receiver']=float(np.max(abs((f['RV1']+f['RV2'])/2-f['RV'])))
    assert max(errors[k] for k in ('a','b','hv','cp','normals'))<2e-12,errors
    return meshes,g,errors,settings


def run(out,index):
    plan=json.loads((out/'plan.json').read_text());unchanged(plan)
    assert sha(Path(__file__))==plan['driver_sha256']
    assert sha(ROOT/'scripts/verify-avl-native-controls.py')==plan['native_driver_sha256']
    build_info=json.loads((out/'build.json').read_text());binary=out/'avl-fields'
    assert build_info['status']=='built' and sha(binary)==build_info['binary_sha256']
    c=plan['cases'][index];directory=out/c['id'];assert not directory.exists();directory.mkdir()
    (directory/'model.avl').write_text(NATIVE.model(c))
    commands=f"LOAD model.avl\nOPER\nO\nA\n\nA A {c['alpha']}\nX\nMRF\nFT total.txt\nFS strips.txt\nFSB body-strips.txt\nFE elements.txt\n\nQUIT\n"
    (directory/'commands.txt').write_text(commands)
    start=time.monotonic();p=subprocess.run([str(binary)],input=commands,text=True,capture_output=True,cwd=directory,timeout=30)
    (directory/'stdout.txt').write_text(p.stdout);(directory/'stderr.txt').write_text(p.stderr)
    native_seconds=time.monotonic()-start
    write(directory/'process.json',dict(observed_utc=utc(),returncode=p.returncode,seconds=native_seconds,binary_sha256=sha(binary)))
    assert p.returncode==0,p.stderr
    native=NATIVE.parse(directory,c);f=read_fields(directory/'elements.txt')
    np.savez(directory/'native-fields.npz',**f)
    duplicate={}
    if (BASE/c['id']).exists():
        for name in ('total.txt','strips.txt','body-strips.txt'):
            duplicate[name]=sha(directory/name)==sha(BASE/c['id']/name)
        assert all(duplicate.values()),duplicate
    source=asw_source(c);(directory/'model.asw').write_text(source)
    model=parse_asw(source);meshes,g,geometry,settings=match_mesh(model,c,f)
    cond=FlightCondition(speed=1.,alpha=c['alpha'],mach=0.,density=1.225,stall=False,freeze_influences=True)
    write(directory/'setup.json',dict(condition=asdict(cond),explicit_mesh=settings,geometry_checks=geometry))
    start=time.monotonic();r=evaluate_aerodynamics(model,cond,meshes)
    python_seconds=time.monotonic()-start
    write(directory/'openswing.json',r)
    gamma=np.array([s['circulation'] for s in r['strips']]);ngamma=f['GAM'].ravel()
    velocity=np.array([s['relative_velocity'] for s in r['strips']])
    cp=FactoredInfluence(f['RC'],f['RV1'],f['RV2'],[1.,0.,0.],np.eye(3))
    hv=FactoredInfluence(f['RV'],f['RV1'],f['RV2'],[1.,0.,0.],np.eye(3),exclude_bound=np.eye(len(gamma),dtype=bool))
    field=hv.apply(ngamma)
    cp_residual=np.sum((cp.apply(ngamma)+f['VINF'])*f['ENC'],axis=1)
    vector=f['RV2']-f['RV1'];force=2*ngamma[:,None]*np.cross(f['VINF']+f['VV'],vector)/10
    moment=np.sum(np.cross(f['RV']-[.25,0,0],force),axis=0)/[10,1,10]
    coefficients=native['coefficients'];native_force=np.array([coefficients[k] for k in ('CXtot','CYtot','CZtot')])
    native_moment=np.array([coefficients[k] for k in ('Cltot','Cmtot','Cntot')])
    force_error=float(np.max(abs(force.sum(axis=0)-native_force)))
    moment_error=float(np.max(abs(moment-native_moment)))
    assert max(force_error,moment_error)<1e-12,(force_error,moment_error)
    values={k:dict(openswing=r[k],native=coefficients[n],relative_percent=100*(r[k]/coefficients[n]-1) if abs(coefficients[n])>1e-12 else None)
            for k,n in [('CL','CLtot'),('CD','CDind'),('CDi','CDff'),('Cm','Cmtot')]}
    comparison=dict(observed_utc=utc(),case=c,native_seconds=native_seconds,openswing_seconds=python_seconds,
        geometry=geometry,native_original_output_identical=duplicate,coefficients=values,
        max_gamma_difference=float(np.max(abs(gamma-ngamma))),
        relative_gamma_linf=float(np.max(abs(gamma-ngamma))/np.max(abs(ngamma))),
        max_native_gamma_python_cp_residual=float(np.max(abs(cp_residual))),
        max_native_gamma_induced_velocity_difference=float(np.max(abs(field-f['VV']))),
        max_solved_velocity_difference=float(np.max(abs(velocity-f['VV']-f['VINF']))),
        native_force_reconstruction_error=force_error,native_moment_reconstruction_error=moment_error,
        native_max_bound_speed=float(np.max(np.linalg.norm(f['VINF']+f['VV'],axis=1))),
        openswing_max_bound_speed=float(np.max(np.linalg.norm(velocity,axis=1))),
        source_limit='Native tiny fourth-power core and literal PI/DTR rounding differ from production zero-core/double-precision constants. All outputs retained; no production patch or reference rescore.')
    unchanged(plan)
    comparison['artifacts']={p.name:sha(p) for p in sorted(directory.iterdir()) if p.is_file()}
    write(directory/'comparison.json',comparison)
    print(json.dumps({k:comparison[k] for k in ('case','coefficients','relative_gamma_linf','max_native_gamma_python_cp_residual','max_native_gamma_induced_velocity_difference','native_max_bound_speed')}))


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    g=p.add_mutually_exclusive_group(required=True);g.add_argument('--prepare',action='store_true');g.add_argument('--build',action='store_true');g.add_argument('--case',type=int);g.add_argument('--swept-from',type=Path)
    a=p.parse_args();out=a.output.resolve()
    if a.prepare:prepare(out)
    elif a.swept_from:prepare(out,a.swept_from.resolve())
    elif a.build:build(out)
    else:run(out,a.case)


if __name__=='__main__':main()
