"""Serial native AVL controls of SA-12's current-influence ground operator.

Compare a common inviscid, unstalled problem in wind axes. Native runs and
production comparisons are separate bounded invocations; no native rebuild.
"""
import argparse
import math
from pathlib import Path
import resource
import subprocess
import sys
import time

import verify_sa12_current_pilot as io

ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT / 'artifacts/isae/avl-matched-fields-r1-20261108'
BUILD = ROOT / 'artifacts/isae/avl-native-build-20261108'
FIELDS = ('RV1','RV2','RV','RC','ENC','VV','VINF','GAM')
POINTS = [('No_Flap','05',8.),('Flap','05',-5.),('Flap','05',2.),('Flap','inf',5.)]


def prepare(out):
    io.bounded()
    baseline = io.read(ROOT / 'artifacts/isae/sa12-current-pilot-20261108/plan.json')
    io.authenticate(baseline['pins'])
    build = io.read(NATIVE / 'build.json')
    binary = NATIVE / 'avl-fields'
    assert build['status'] == 'built' and io.sha(binary) == build['binary_sha256']
    pins = dict(baseline['pins'])
    for path in [Path(__file__), binary, NATIVE/'build.json', NATIVE/'aoutmrf.f', BUILD/'verification.json',
                 *(BUILD/'source/src'/name for name in ('aic.f','amake.f','sgutil.f','aero.f','atpforc.f'))]:
        pins[str(path.relative_to(ROOT))] = io.sha(path)
    jobs = io.adapter.plan(ROOT)
    cases = []
    assert not out.exists()
    out.mkdir(parents=True)
    for flap,height,alpha in POINTS:
        job, = [j for j in jobs if j['flap']==flap and j['height_label']==height
                and j['settings']['alpha']==alpha and j['settings']['panels']==100]
        slope, incidence = (6.,0.) if flap=='No_Flap' else (7.44,12.5)
        case = dict(id=f'{flap}-h{height}-a{alpha:g}',job=job,slope=slope,incidence=incidence)
        folder = out / case['id']
        folder.mkdir()
        # Uniform one-row chord spacing makes CP-QC = .5*CLAF*c exactly.
        # Cosine chord spacing uses a nonlinear CLAF rule and is not equivalent.
        lines = [case['id'],'0.',f"0 1 {-job['settings']['position_earth'][2]:.17g}",
            '.3871 .254 1.524','0 0 0','0','SURFACE','SA12 wind-frame lifting line',
            '1 0.0','COMPONENT','1']
        for y in (-.762,.762):
            lines += ['SECTION',f'-.0635 {y:.17g} 0 .254 {incidence+alpha:.17g}' + (' 100 1.0' if y<0 else ''),
                      'CLAF',f'{slope/(2*math.pi):.17g}']
        (folder/'model.avl').write_text('\n'.join(lines)+'\n')
        commands='LOAD model.avl\nOPER\nO\nA\n\nA A 0\nX\nMRF\nFT total.txt\nFE elements.txt\n\nQUIT\n'
        (folder/'commands.txt').write_text(commands)
        for path in (folder/'model.avl',folder/'commands.txt'):
            pins[str(path.relative_to(ROOT))] = io.sha(path)
        cases.append(case)
    io.write(out/'plan.json',dict(observed_utc=io.utc(),cases=cases,pins=pins,
        native_binary=str(binary.relative_to(ROOT)),native_calls=4,production_calls=4,primary_passes_added=0,
        protocol='Original SA12 straight span/chord/section incidence/slope and reference dimensions. Rotate current-wind geometry and ground plane into wind axes for native fixed-x AVL. One uniform chord row,100 cosine span intervals,CLAF=dCLda/(2pi),AINC=section-alpha+flight-alpha,AVL alpha0,Zsym=-height. Compare exact exported native geometry/receivers with production diagnostic meshes. Both Mach0,speed1,stall off,zero profile drag. These are common-physics controls,not raw ISAE passes.',
        limits='One BLAS thread,512MiB,15CPU/25wall seconds. Native and Python solves in separate invocations. Reuse immutable instrumented native binary; no build or browser jobs.',
        previous_turn='Progress: eight flap production/replay states showed frozen setup is not a general correction.'))
    (out/'driver-used.py').write_text(Path(__file__).read_text())
    io.signal.alarm(0)
    print('Prepared four native ground controls and four separate production comparisons.')


def selected(out,index):
    plan=io.read(out/'plan.json');io.authenticate(plan['pins'])
    case=plan['cases'][index]
    return plan,case,out/case['id']


def native(out,index):
    io.bounded()
    plan,case,folder=selected(out,index)
    assert not (folder/'native.json').exists() and 'numpy' not in sys.modules
    commands=(folder/'commands.txt').read_text()
    start=time.monotonic()
    process=subprocess.run([str(ROOT/plan['native_binary'])],input=commands,text=True,capture_output=True,cwd=folder,timeout=20)
    (folder/'stdout.txt').write_text(process.stdout);(folder/'stderr.txt').write_text(process.stderr)
    receipt=dict(observed_utc=io.utc(),returncode=process.returncode,seconds=time.monotonic()-start,
        child_peak_rss_kib=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,
        plan_sha256=io.sha(out/'plan.json'),artifacts={p.name:io.sha(p) for p in folder.iterdir() if p.is_file()})
    io.write(folder/'native.json',receipt)
    assert process.returncode==0,process.stderr
    assert (folder/'total.txt').exists() and (folder/'elements.txt').exists()
    io.signal.alarm(0);print(receipt | {'artifacts':len(receipt['artifacts'])})


def compare(out,index):
    io.bounded()
    start=time.monotonic()
    plan,case,folder=selected(out,index)
    assert not (folder/'comparison.json').exists()
    native_receipt=io.read(folder/'native.json')
    assert native_receipt['returncode']==0 and native_receipt['plan_sha256']==io.sha(out/'plan.json')
    for name,digest in native_receipt['artifacts'].items():assert io.sha(folder/name)==digest
    import numpy as np
    sys.path.insert(0,str(ROOT))
    from openswing.asw import parse_asw
    from openswing.asw_edit import edit_distribution
    from openswing.geometry import PanelMesh,surface_frame
    from openswing.frozen_influence import lifting_geometry
    from openswing.aero import FlightCondition,evaluate_aerodynamics
    fields={name:[] for name in FIELDS}
    for line in (folder/'elements.txt').read_text().splitlines():
        if not line.startswith('DIAG_'):continue
        tokens=line.split();name=tokens[0][5:]
        if name not in fields:continue
        assert int(tokens[1])==len(fields[name])+1
        fields[name].append([float(x) for x in tokens[2:]])
    f={k:np.array(v) for k,v in fields.items()}
    assert f['GAM'].shape==(100,1)
    coefficients={}
    for line in (folder/'total.txt').read_text().splitlines():
        if '|' not in line:continue
        left,right=line.split('|',1)
        try:values=[float(x) for x in left.split()]
        except ValueError:continue
        names=right.strip().removeprefix('Trefftz Plane: ').split(', ')
        coefficients.update(zip(names,values))
    assert coefficients['Alpha']==0 and coefficients['# vortices']==100
    job=case['job'];s=job['settings']
    original=parse_asw((ROOT/job['model_path']).read_text(),beam_interpolation=s['beam_interpolation'])
    assert len(original.beams)==1 and not original.diagnostics
    model=edit_distribution(original,1,'Cdf',multiplier=0.)
    beam=model.beams[0]
    assert np.all(beam.value('dCLda',[-.762,0,.762])==case['slope'])
    assert np.all(beam.value('alpha',[-.762,0,.762])==case['incidence'])
    assert np.all(beam.value('Cdp',[-.762,0,.762])==0)
    (folder/'inviscid-control.asw').write_text(model.dumps())
    alpha=math.radians(s['alpha']);wind=np.array([math.cos(alpha),0.,math.sin(alpha)])
    lift=np.array([-math.sin(alpha),0.,math.cos(alpha)])
    rotation=np.array([wind,[0.,1.,0.],lift])
    nodes=np.r_[f['RV1'][:,1],f['RV2'][-1,1]]
    assert np.all(np.diff(nodes)>0) and max(abs(nodes[[0,-1]]-beam.domain))<2e-12
    # Native cosine spacing leaves its center at about -3e-11 m. Preserve
    # that exact native lattice instead of inserting ASW's attachment node0.
    # This is a rigid aerodynamic comparison, not a structural mesh.
    tm=f['RV'][:,1]
    matched=PanelMesh(beam,nodes[:-1],nodes[1:],tm,
        beam.position(nodes[:-1]),beam.position(nodes[1:]),beam.position(tm),
        surface_frame(beam,tm),np.diff(nodes),ts=.5*(nodes[:-1]+nodes[1:]),
        theta=np.arccos(np.clip(nodes/.762,-1,1)))
    g=lifting_geometry([matched],wind)
    geometry={key:float(np.max(abs(g[key]@rotation.T-f[name]))) for key,name in
              [('a','RV1'),('b','RV2'),('hv','RV'),('cp','RC')]}
    incidence=math.radians(case['incidence'])
    normal=math.sin(incidence)*matched.frames[...,0]+math.cos(incidence)*matched.frames[...,2]
    geometry['normal']=float(np.max(abs(normal@rotation.T-f['ENC'])))
    assert max(geometry.values())<2e-12,geometry
    condition=FlightCondition(speed=1.,alpha=s['alpha'],density=s['density'],mach=0.,
        stall=False,freeze_influences=False,ground_effect=1,position_earth=s['position_earth'],attitude=s['attitude'])
    result=evaluate_aerodynamics(model,condition,[matched])
    assert result['converged'] and result['residual']<1e-8
    gamma=np.array([r['circulation'] for r in result['strips']])
    velocity=np.array([r['relative_velocity'] for r in result['strips']])@rotation.T
    ngamma=f['GAM'].ravel();native_v=f['VV']+f['VINF']
    k=4*math.pi*.079577472
    qs=.5*s['density']*model.reference[0,0]
    force=np.asarray(result['force'])@rotation.T/qs
    native_force=np.array([coefficients[key] for key in ('CXtot','CYtot','CZtot')])
    rebuilt=2*np.sum(ngamma[:,None]*np.cross(native_v,f['RV2']-f['RV1']),axis=0)/model.reference[0,0]
    checks=dict(native_force_reconstruction=float(max(abs(rebuilt-native_force))),
        corrected_gamma_relative=float(max(abs(gamma-k*ngamma))/max(abs(gamma))),
        velocity_absolute=float(np.max(abs(velocity-native_v))),
        corrected_force_absolute=float(max(abs(force-k*native_force))),
        corrected_CDi_absolute=abs(result['CDi']-k*k*coefficients['CDff']))
    assert checks['native_force_reconstruction']<2e-12,checks
    assert checks['corrected_gamma_relative']<2e-9 and checks['velocity_absolute']<2e-9,checks
    assert checks['corrected_force_absolute']<2e-10 and checks['corrected_CDi_absolute']<2e-10,checks
    values={key:dict(openswing=float(result[key]),avl=coefficients[name],
                    error_percent=100*(result[key]/coefficients[name]-1))
            for key,name in [('CL','CLtot'),('CD','CDind'),('CDi','CDff')]}
    np.savez(folder/'matched-fields.npz',gamma=gamma,velocity=velocity,**{f'native_{key}':value for key,value in f.items()})
    report=dict(observed_utc=io.utc(),case=case['id'],verified=True,geometry=geometry,checks=checks,values=values,
        source_derived_AVL_kernel_factor=k,production_calls=1,primary_passes_added=0,
        seconds=time.monotonic()-start,peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        plan_sha256=io.sha(out/'plan.json'),native_receipt_sha256=io.sha(folder/'native.json'),
        artifacts={p.name:io.sha(p) for p in (folder/'inviscid-control.asw',folder/'matched-fields.npz')})
    io.write(folder/'comparison.json',report)
    io.signal.alarm(0);print(report)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('prepare','native','compare'))
    parser.add_argument('--output',type=Path,required=True);parser.add_argument('--index',type=int)
    args=parser.parse_args()
    if args.action=='prepare':prepare(args.output.resolve())
    elif args.action=='native':native(args.output.resolve(),args.index)
    else:compare(args.output.resolve(),args.index)
