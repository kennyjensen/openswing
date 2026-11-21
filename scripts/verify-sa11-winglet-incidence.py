"""Check the report/file upper-winglet twist-sign conflict without fitting.

Two serial native AVL / production comparisons at the archived alpha1/speed240
condition. The -4 degree alternative is diagnostic and never replaces sources.
"""
import argparse
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

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from openswing.aero import AnalysisError, FlightCondition, evaluate_aerodynamics
from openswing.asw import Distribution, parse_asw
from openswing.geometry import surface_frame
SPEC=importlib.util.spec_from_file_location('convert',ROOT/'scripts/audit-sa11-avl-conversion.py')
CONVERT=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(CONVERT)
CACHE=ROOT/'reference/isae-validation/f62943df20e9e4d7d9f50e070477b22426b5f865'
FOLDER=next(CACHE.glob('1 - Aerodynamics/SA*/SA - 11 - *'))
SOURCE=ROOT/'examples/isae-sa11-wingtip-up.asw'
BINARY=ROOT/'artifacts/isae/avl-matched-fields-r1-20261108/avl-fields'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
utc=lambda:datetime.now(timezone.utc).isoformat()
read=lambda p:json.loads(p.read_text())
def write(p,x):p.write_text(json.dumps(x,indent=2,allow_nan=False)+'\n')


def model_at(twist):
    model=parse_asw(SOURCE.read_text())
    assert len(model.beams)==3 and not model.diagnostics
    for beam in model.beams[1:]:
        d=beam.distributions['twist'];assert np.all(d.values==4.)
        beam.distributions['twist']=Distribution('twist',d.t.copy(),np.full_like(d.values,twist),d.line)
    return model


def geometry_audit(model):
    rows=[]
    for beam in model.beams[1:]:
        t=float(np.mean(beam.domain)); frame=surface_frame(beam,t);s=frame[:,1]
        across=np.hypot(s[1],s[2]);theta=np.deg2rad(beam.value('twist',t))
        # Independent construction from the literal straight beam tangent.
        c0=np.array([across,-s[0]*s[1]/across,-s[0]*s[2]/across])
        n0=np.array([0.,-s[2]/across,s[1]/across])
        normal=np.sin(theta)*c0+np.cos(theta)*n0
        error=float(np.max(abs(normal-frame[:,2])));assert error<1e-14
        # A horizontal cut through the actual airfoil plane: n dot d=0, dz=0.
        outboard_te_slope=-normal[0]/normal[1]*np.sign(beam.position(t)[1])
        rows.append(dict(beam=beam.index,asw_twist_deg=float(np.rad2deg(theta)),
            trailing_edge_outboard_angle_deg=float(np.rad2deg(np.arctan(outboard_te_slope))),
            normal=normal.tolist(),independent_frame_error=error,
            interpretation='Positive means trailing edge outboard / leading edge inward (toe-in); negative means leading edge outboard (toe-out). This horizontal-cut angle is not the beam-normal input twist.'))
    return rows


def prepare(out):
    assert not out.exists(),out
    parent=read(ROOT/'artifacts/isae/sa11-avl-baseline-r1-20261108/plan.json')
    pins=dict(parent['unchanged_pins'])
    files=[SOURCE,ROOT/'examples/isae-sa11-winglet-sources.json',
        FOLDER/'KC-135A_geometry.svg',FOLDER/'KC-135A_geometry.eps',
        FOLDER/'Aswing_Simulations/Wing_tip_up/wingtip_up_Ma_0_70.txt',
        ROOT/'reference/isae-sa11/NASA-TN-D-8473.pdf',
        ROOT/'reference/aswing-authoritative-20261108/isae-part-1-aerodynamics.pdf']
    manifest=read(CACHE.parent/'manifest.json')
    for path in files:
        if path.is_relative_to(CACHE):assert sha(path)==manifest['files'][str(path.relative_to(CACHE))]['sha256']
        pins[str(path.relative_to(ROOT))]=sha(path)
    assert sha(BINARY)==parent['binary_sha256']
    out.mkdir(parents=True)
    for name,source in [('archived-geometry.png','/tmp/sa11-archived-geometry.png'),('nasa-incidence-p6.png','/tmp/sa11-nasa-incidence-p6.png')]:
        shutil.copyfile(source,out/name)
    rows={str(twist):geometry_audit(model_at(twist)) for twist in [4.,-4.]}
    write(out/'plan.json',dict(observed_utc=utc(),cases=[dict(id='literal_plus4',twist=4.),dict(id='report_minus4',twist=-4.)],
        unchanged_pins=pins,driver_sha256=sha(Path(__file__)),binary_sha256=sha(BINARY),geometry_audit=rows,
        evidence='ISAE KC-135A_geometry.svg labels upper-winglet root/tip twist -4 degrees. NASA TN D-8473 printed p3 defines incidence sign, p4 explicitly says leading edge outboard/toed out4 degrees. Literal ASW upper-winglet twist is +4. Horizontal-plane normal check establishes opposite toe directions; exact4-degree body-axis incidence would require a separate angle conversion.',
        protocol='Two cases, only upper-winglet beam2/3 twist +4 or -4. Native64 one-row vortices on the retained converted grid, PG240/340.21, alpha1, body-x wake. Production uses identical native receivers with stall and local Mach guard active. If rejected, retain converged circulation/field solely as diagnostic; no accepted physical load output is fabricated.',
        limits='Authoritative report geometry versus file conflict, not proof of the archived producing model. The sign-only alternative does not reproduce every NASA dimension/angle and is not a new registered comparison pass.'))
    shutil.copyfile(__file__,out/'driver-used.py')
    print(json.dumps(dict(prepared=True,cases=2,geometry=rows)))


def run(out,index):
    plan=read(out/'plan.json')
    for name,pin in plan['unchanged_pins'].items():assert sha(ROOT/name)==pin,name
    assert sha(Path(__file__))==plan['driver_sha256'] and sha(BINARY)==plan['binary_sha256']
    case=plan['cases'][index];directory=out/case['id'];assert not directory.exists();directory.mkdir()
    model=model_at(case['twist']);base=model_at(4.)
    for original,changed in zip(base.beams,model.beams):
        for key,d in original.distributions.items():
            e=changed.distributions[key];assert np.array_equal(d.t,e.t)
            if original.index==1 or key!='twist':assert np.array_equal(d.values,e.values),(original.index,key)
    write(directory/'input-choice.json',dict(case=case,source_sha256=sha(SOURCE),geometry_audit=geometry_audit(model)))
    text,segments=CONVERT.conversion(model,1);lines=text.splitlines();mach=240/340.21;lines[1]=f'{mach:.17g}'
    (directory/'model.avl').write_text('\n'.join(lines)+'\n')
    commands='LOAD model.avl\nOPER\nO\nA\n\nA A 1\nX\nMRF\nFT total.txt\nFS strips.txt\nFSB body-strips.txt\nFE elements.txt\n\nQUIT\n'
    (directory/'commands.txt').write_text(commands)
    start=time.monotonic();p=subprocess.run([str(BINARY)],input=commands,text=True,capture_output=True,cwd=directory,timeout=30)
    (directory/'stdout.txt').write_text(p.stdout);(directory/'stderr.txt').write_text(p.stderr)
    write(directory/'process.json',dict(observed_utc=utc(),returncode=p.returncode,seconds=time.monotonic()-start));assert p.returncode==0,p.stderr
    f=CONVERT.MATCHED.read_fields(directory/'elements.txt');assert len(f['GAM'])==64
    np.savez(directory/'native-fields.npz',**f)
    meshes,g,errors,settings=CONVERT.mapped_meshes(model,f,segments)
    write(directory/'mesh.json',dict(settings=settings,geometry_errors=errors))
    start=time.monotonic()
    try:
        r=evaluate_aerodynamics(model,FlightCondition(speed=240.,alpha=1.,density=1.2256,mach=None,freeze_influences=True),meshes)
        write(directory/'openswing.json',r)
        gamma=np.array([s['circulation'] for s in r['strips']]);v=np.array([s['relative_velocity'] for s in r['strips']]);cl=np.array([s['cl'] for s in r['strips']])
        status=dict(status='computed',residual=r['residual'],maximum_section_normal_mach=max(s['normal_mach'] for s in r['strips']))
    except AnalysisError as exc:
        assert exc.details and exc.details.get('kind')=='section_normal_mach',str(exc)
        tb=exc.__traceback__
        while tb and tb.tb_frame.f_code.co_name!='evaluate_aerodynamics':tb=tb.tb_next
        assert tb is not None
        local=tb.tb_frame.f_locals;gamma=local['gamma'].copy();v=local['v'].copy();cl=local['cl'].copy()
        status=dict(status='rejected',error=str(exc),details=exc.details,residual=exc.details['circulation_residual'],
                    maximum_section_normal_mach=exc.details['maximum']['normal_mach'])
        write(directory/'openswing-rejected.json',status)
    seconds=time.monotonic()-start
    limits=np.concatenate([np.minimum(m.beam.value('CLmax',m.tm)-cl[sum(len(x.tm) for x in meshes[:i]):sum(len(x.tm) for x in meshes[:i+1])],
        cl[sum(len(x.tm) for x in meshes[:i]):sum(len(x.tm) for x in meshes[:i+1])]-m.beam.value('CLmin',m.tm)) for i,m in enumerate(meshes)])
    np.savez(directory/'diagnostic-state.npz',gamma=gamma,velocity=v,cl=cl,stall_margin=limits)
    labels=CONVERT.MATCHED.NATIVE.labeled(directory/'total.txt')
    native=dict(CL=labels['CLtot'][0],CDi=labels['Trefftz Plane: CLff, CDff, CYff, e'][1],CD_near=labels['CDvis, CDind'][1])
    table=np.loadtxt(FOLDER/'Aswing_Simulations/Wing_tip_up/wingtip_up_Ma_0_70.txt');row=table[table[:,71]==1.];assert row.shape==(1,82)
    reference=dict(CL=float(row[0,77]),CDi=float(row[0,79]),CD=float(row[0,78]))
    report=dict(observed_utc=utc(),case=case,production=status,openswing_seconds=seconds,native=native,reference=reference,
        native_error_percent={k:100*(native[k]/reference[k]-1) for k in ['CL','CDi']},
        maximum_geometry_error=max(errors.values()),native_production_gamma_relative_linf=float(np.max(abs(gamma/240-f['GAM'].ravel()))/np.max(abs(f['GAM']))),
        minimum_stall_margin_widths=float(np.min(limits)/.05),stalled_strips=int(np.sum(limits<0)),
        limits=plan['limits'])
    for name,pin in plan['unchanged_pins'].items():assert sha(ROOT/name)==pin,name
    report['artifact_sha256']={p.name:sha(p) for p in directory.iterdir() if p.is_file()}
    write(directory/'report.json',report)
    print(json.dumps({k:report[k] for k in ['case','native','reference','native_error_percent','minimum_stall_margin_widths','native_production_gamma_relative_linf']}))
    print(json.dumps({k:status[k] for k in ['status','residual','maximum_section_normal_mach']}))


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    q=p.add_mutually_exclusive_group(required=True);q.add_argument('--prepare',action='store_true');q.add_argument('--case',type=int)
    a=p.parse_args()
    if a.prepare:prepare(a.output.resolve())
    else:run(a.output.resolve(),a.case)


if __name__=='__main__':main()
