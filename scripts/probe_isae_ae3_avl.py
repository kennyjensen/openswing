"""Actual rigid AE-3 control-normal comparison with native AVL, one job at a time.

Keep native bound-vector loads, ASW beam-vector loads and section moments
distinct. No solver replacement or native-ASWING validation votes.
"""
from dataclasses import replace
from datetime import datetime,timezone
import importlib.util
import json
import os
from pathlib import Path
import resource
import signal
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'artifacts/isae/ae3-native-avl-20261111'
BASE=ROOT/'artifacts/isae/ae3-control-setup-20261111'
NATIVE=ROOT/'artifacts/isae/avl-matched-fields-r1-20261108'
BUILD=ROOT/'artifacts/isae/avl-native-build-20261108'
sys.path.insert(0,str(ROOT))
from scripts.probe_isae_ae2_cold_trace import read,write,pin,THREADS
LIMITS=dict(address_space_bytes=512*1024**2,cpu_seconds=15,wall_seconds=25)


def load_module(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def checked():
    plan=read(OUT/'plan.json')
    assert all(pin(p['path'])==p for p in plan['pins'])
    return plan


def prepare():
    assert not OUT.exists()
    baseline=read(BASE/'plan.json')
    assert all(pin(p['path'])==p for p in baseline['pins'])
    native=read(NATIVE/'plan.json');build=read(BUILD/'plan.json')
    paths={p['path'] for p in baseline['pins']}
    paths.update(str(p) for p in (Path(__file__),BASE/'plan.json',BASE/'assessment.json',
        NATIVE/'plan.json',NATIVE/'build.json',NATIVE/'avl-fields',NATIVE/'aoutmrf.f',
        BUILD/'plan.json',BUILD/'verification.json',BUILD/'avl',
        ROOT/'scripts/verify-avl-matched-fields.py',ROOT/'scripts/verify-avl-native-controls.py',
        ROOT/'scripts/avl_vorvelc_reference.py',
        ROOT/'reference/avl-native-20261108/avl3.52.tgz',
        ROOT/'reference/avl-native-20261108/source/AVL3.52rel09032025/avl_doc-AVL350-04242025.txt'))
    assert pin(NATIVE/'avl-fields')['sha256']==read(NATIVE/'build.json')['binary_sha256']
    assert pin(BUILD/'avl')['sha256']==native['original_binary_sha256']
    assert pin(ROOT/'reference/avl-native-20261108/avl3.52.tgz')['sha256']==build['upstream']['archive_sha256']
    assert (NATIVE/'aoutmrf.f').read_text().replace(native['patch'],'')==(BUILD/'source/src/aoutmrf.f').read_text()
    for path,sha in build['source_build_pins'].items():
        p=BUILD/'source'/path;assert pin(p)['sha256']==sha;paths.add(str(p))
    for path,sha in native['native_objects'].items():
        p=BUILD/'objects'/path;assert pin(p)['sha256']==sha;paths.add(str(p))
    cases=[]
    for previous in baseline['cases']:
        if previous['variant']!='rigid' or previous['job']['native_operating_point']!=1:continue
        folder=BASE/'cases'/previous['name']
        for name in ('result.json','fresh-result.json','report.json','terminal.json'):paths.add(str(folder/name))
        assert read(folder/'terminal.json')['returncode']==0
        cases.append(dict(name='m'+str(previous['job']['nominal']),job=previous['job'],
            baseline=str(folder),source=previous['job']['source']))
    assert len(cases)==2
    OUT.mkdir(parents=True)
    write(OUT/'plan.json',dict(observed_utc=datetime.now(timezone.utc).isoformat(),
        previous_goal_turn='progress: ten source/control diagnostics rule out frozen influences and show a low-speed rigid response discrepancy',
        cases=cases,pins=[pin(p) for p in sorted(paths)],limits=LIMITS,
        gates=dict(geometry=3e-12,native_force_reconstruction=3e-12,native_operator_relative=1e-7,physical_residual=1e-8),
        native_binary=str(NATIVE/'avl-fields'),native_source_files=len(build['source_build_pins']),
        primary_votes_added=0,
        setup='Literal Straight_20O, F1=+1, alpha=beta=Mach=0, 27.0934 m/s in OpenSwing; unit-normalized native AVL. One chord row, CLAF=dCLda/(2*pi), streamwise chord=normal chord/|x cross beam tangent|. Encode control as the projected section-normal incidence, not a physical hinged flap. Original reference area/chord/span .185/.15/1.2192 and origin0.',
        discretization='Original nominal80/160 ASW node arrays, including control/root breaks. Four same-component AVL surfaces; one span interval per consecutive ASW node pair. Export and measure actual native receivers. A separate ASW calculation at native receiver stations isolates sampling differences.',
        conventions='Native geometric Cl is +Mx/qSb; ASW stability Cl at alpha0 is -Mx/qSb. AVL omits the ASW intrinsic section Cm. Keep native bound-vector forces distinct from ASW beam-vector forces and quarter-chord arm.',
        restrictions=['All model and production sources unchanged.',
            'No new ASWING pass, fitted input, mesh gate relaxation or physical hinged-flap equivalence claim.',
            'Preserve original generated ASW receiver results alongside matched-native receiver diagnostics.',
            'Native AVL numerical objects unchanged; existing output-only instrumentation is reused.']))
    print(json.dumps(dict(cases=[c['name'] for c in cases],pins=len(paths),native_source_files=len(build['source_build_pins']))))


def worker(name):
    import numpy as np
    from openswing.asw import parse_asw
    from openswing.aero import FlightCondition,evaluate_aerodynamics
    from openswing.geometry import surface_frame
    from openswing.source_coupled import SourceCoupledNetwork
    from openswing.frozen_influence import lifting_geometry
    from scripts.avl_vorvelc_reference import matrix as native_matrix
    fields_helper=load_module('native_ae3_fields',ROOT/'scripts/verify-avl-matched-fields.py')
    plan=checked();case=next(c for c in plan['cases'] if c['name']==name);job=case['job'];folder=OUT/'cases'/name
    assert all(os.environ.get(k)=='1' for k in THREADS)
    source=Path(case['source']).read_text();model=parse_asw(source,beam_interpolation=job['settings']['beam_interpolation'])
    assert not model.diagnostics and len(model.beams)==1
    beam=model.beams[0];c=dict(job['condition'])
    for key in ('controls','powers','circulation_modes'):c[key]={int(k):v for k,v in c[key].items()}
    condition=FlightCondition(**c);net=SourceCoupledNetwork(model,job['panels'],condition,job['gravity'])
    assert net.ne==job['expected_elements'] and len(net.meshes)==1
    mesh=net.meshes[0];nodes=net.station_nodes[1][0]
    assert nodes.tolist()==read(Path(case['baseline'])/'report.json')['checked_properties']['stations']
    cuts=[-.6096,-.8*.6096,0.,.8*.6096,.6096]
    lines=['AE3 literal rigid equivalent control normals','0','0 0 0','0.185 0.15 1.2192','0 0 0','0']
    sections=[];interval_incidence=[]
    for band,(left,right) in enumerate(zip(cuts[:-1],cuts[1:])):
        selected=nodes[(nodes>=left)&(nodes<=right)]
        assert selected[0]==left and selected[-1]==right
        lines+=['SURFACE',f'AE3 band {band}','1 0','COMPONENT',str(beam.physical_index)]
        theta=float(beam.value('dCLdF1',(left+right)/2)/beam.value('dCLda',(left+right)/2))
        for i,t in enumerate(selected):
            side='left' if i==len(selected)-1 else 'right'
            frame=surface_frame(beam,t,side);across=float(np.linalg.norm(np.cross([1.,0.,0.],frame[:,1])))
            chord=float(beam.value('chord',t,side=side))/across
            le=beam.position(t,side=side)-[float(beam.value('Xax',t,side=side))*chord,0.,0.]
            incidence=float(np.arctan(across*np.tan(theta)))
            claf=float(beam.value('dCLda',t,side=side)/(2*np.pi))
            lines+=['SECTION',' '.join(f'{v:.17g}' for v in (*le,chord,np.degrees(incidence)))+' 1 0','CLAF',f'{claf:.17g}']
            sections.append(dict(band=band,t=float(t),side=side,le=le.tolist(),normal_chord=float(beam.value('chord',t,side=side)),streamwise_chord=chord,incidence_radians=incidence,claf=claf))
            if i<len(selected)-1:interval_incidence.append(incidence)
    (folder/'model.avl').write_text('\n'.join(lines)+'\n')
    write(folder/'conversion.json',dict(sections=sections,original_nodes=nodes.tolist(),original_sample_stations=mesh.tm.tolist(),section_incidence=interval_incidence))
    commands='LOAD model.avl\nOPER\nO\nA\n\nA A 0\nX\nMRF\nFT total.txt\nFE elements.txt\n\nQUIT\n'
    (folder/'commands.txt').write_text(commands)
    start=time.monotonic()
    proc=subprocess.run([plan['native_binary']],input=commands,text=True,capture_output=True,cwd=folder,timeout=10)
    (folder/'native-stdout.txt').write_text(proc.stdout);(folder/'native-stderr.txt').write_text(proc.stderr)
    write(folder/'native-process.json',dict(returncode=proc.returncode,process_reaped=True,wall_seconds=time.monotonic()-start))
    assert proc.returncode==0,proc.stderr
    f=fields_helper.read_fields(folder/'elements.txt');labels=fields_helper.NATIVE.labeled(folder/'total.txt')
    assert f['GAM'].shape==(net.ne,1) and 'Geometric' in (folder/'total.txt').read_text()
    assert labels['# vortices']==[net.ne] and labels['# strips']==[net.ne]
    assert labels['Alpha, pb/2V, p\'b/2V'][0]==0. and labels['Mach, rb/2V, r\'b/2V'][0]==0.
    assert np.max(abs(f['VINF']-[1.,0.,0.]))<1e-14
    np.savez(folder/'native-fields.npz',**f)
    checks=[]
    def check(key,value,gate):checks.append(dict(name=key,metric=float(value),gate=gate,passed=bool(np.isfinite(value) and value<=gate)))
    original_geometry=lifting_geometry([mesh],np.array([1.,0.,0.]))
    for key,native_key in [('a','RV1'),('b','RV2')]:check('native_'+key+'_endpoints',np.max(abs(original_geometry[key]-f[native_key])),3e-12)
    assert np.all(f['RV'][:,1]>mesh.t0) and np.all(f['RV'][:,1]<mesh.t1)
    matched=replace(mesh,tm=f['RV'][:,1].copy(),rm=beam.position(f['RV'][:,1]),frames=surface_frame(beam,f['RV'][:,1]))
    g=lifting_geometry([matched],np.array([1.,0.,0.]))
    for key,native_key in [('a','RV1'),('b','RV2'),('hv','RV'),('cp','RC')]:check('matched_'+key,np.max(abs(g[key]-f[native_key])),3e-12)
    angles=np.array(interval_incidence)
    e_chord=np.column_stack((np.cos(angles),np.zeros(net.ne),-np.sin(angles)))
    bound=f['RV2']-f['RV1'];predicted_normal=np.cross(e_chord,bound)
    predicted_normal/=np.linalg.norm(predicted_normal,axis=1)[:,None]
    check('native_normal_from_input',np.max(abs(predicted_normal-f['ENC'])),3e-12)
    gamma=f['GAM'].ravel();velocity=f['VINF']+f['VV']
    normalized_force=2*gamma[:,None]*np.cross(velocity,bound)/.185
    normalized_moment=np.cross(f['RV'],normalized_force).sum(axis=0)/[1.2192,.15,1.2192]
    native_force=np.array([labels[k][0] for k in ('CXtot, Cltot, Cl\'tot','CYtot, Cmtot','CZtot, Cntot, Cn\'tot')])
    native_moment=np.array([labels[k][1] for k in ('CXtot, Cltot, Cl\'tot','CYtot, Cmtot','CZtot, Cntot, Cn\'tot')])
    check('native_force_reconstruction',np.max(abs(normalized_force.sum(axis=0)-native_force)),3e-12)
    check('native_moment_reconstruction',np.max(abs(normalized_moment-native_moment)),3e-12)
    cp=native_matrix(f['RC'],f['RV1'],f['RV2'],0.)
    hv=native_matrix(f['RV'],f['RV1'],f['RV2'],0.,exclude_self=True)
    aic=np.einsum('ijk,ik->ij',cp,f['ENC']);rhs=-np.sum(f['VINF']*f['ENC'],axis=1)
    linear=np.linalg.solve(aic,rhs)
    check('native_gamma_operator_reproduction',np.max(abs(linear-gamma))/np.max(abs(gamma)),1e-7)
    check('native_field_operator_reproduction',np.max(abs(np.einsum('ijk,j->ik',hv,gamma)-f['VV'])),1e-7)
    alpha=beam.value('dCLdF1',matched.tm)/beam.value('dCLda',matched.tm)
    asw_normal=np.sin(alpha)[:,None]*matched.frames[:,:,0]+np.cos(alpha)[:,None]*matched.frames[:,:,2]
    alternate_aic=np.einsum('ijk,ik->ij',cp,asw_normal)
    alternate=np.linalg.solve(alternate_aic,-np.sum(f['VINF']*asw_normal,axis=1))
    result=evaluate_aerodynamics(model,condition,[matched])
    write(folder/'openswing-native-receivers.json',result)
    produced=np.array([s['circulation'] for s in result['strips']])/condition.speed
    fresh=evaluate_aerodynamics(model,condition,[matched],circulation=produced*condition.speed)
    write(folder/'openswing-fresh.json',fresh)
    check('fresh_circulation_residual',fresh['residual'],1e-8)
    check('fresh_force_parity',np.max(abs(np.array(fresh['force'])-result['force']))/max(1.,np.linalg.norm(result['force'])),2e-10)
    baseline=read(Path(case['baseline'])/'result.json')
    def components(packet,m):
        gam=np.array([s['circulation'] for s in packet['strips']])/condition.speed
        vel=np.array([s['relative_velocity'] for s in packet['strips']])/condition.speed
        force=2*gam[:,None]*np.cross(vel,m.frames[:,:,1]*m.length[:,None])/.185
        quarter=m.rm+((.25-beam.value('Xax',m.tm))*beam.value('chord',m.tm))[:,None]*m.frames[:,:,0]
        vortex=-float(np.cross(quarter,force).sum(axis=0)[0])/1.2192
        total=-packet['distributed_aero_moment'][0]/(.5*condition.density*condition.speed**2*.185*1.2192)
        return dict(Cl_total=total,Cl_circulation_force=vortex,Cl_other=total-vortex,
            circulation=gam.tolist(),force_coefficient=force.sum(axis=0).tolist())
    current=components(result,matched);original=components(baseline,mesh)
    native_Cl=-float(native_moment[0]);native_bound_native_gamma=-float(normalized_moment[0])
    mapped_native_force=2*gamma[:,None]*np.cross(velocity,matched.frames[:,:,1]*matched.length[:,None])/.185
    quarter=matched.rm+((.25-beam.value('Xax',matched.tm))*beam.value('chord',matched.tm))[:,None]*matched.frames[:,:,0]
    native_on_asw_arm=-float(np.cross(quarter,mapped_native_force).sum(axis=0)[0])/1.2192
    report=dict(name=name,numerical_pass=all(c['passed'] for c in checks),checks=checks,
        native_Cl_stability=native_Cl,native_bound_reconstructed_Cl=native_bound_native_gamma,
        native_fields_on_asw_force_arm_Cl=native_on_asw_arm,
        original=original,matched_receivers=current,
        native_vs_matched_circulation_relative_linf=float(np.max(abs(produced-gamma))/np.max(abs(gamma))),
        normals_only_circulation_relative_linf=float(np.max(abs(alternate-gamma))/np.max(abs(gamma))),
        native_vs_original_circulation_relative_linf=float(np.max(abs(np.array(original['circulation'])-gamma))/np.max(abs(gamma))),
        native_receiver_shift_max=float(np.max(abs(original_geometry['hv']-f['RV']))),
        control_normal_component_difference=float(np.max(abs(asw_normal-f['ENC']))),
        native_vs_original_Cl_percent=100*abs(original['Cl_total']/native_Cl-1),
        native_vs_matched_vortex_Cl_percent=100*abs(current['Cl_circulation_force']/native_Cl-1),
        native_vs_asw_arm_vortex_Cl_percent=100*abs(current['Cl_circulation_force']/native_on_asw_arm-1),
        stalled_strips=sum(s['stalled'] for s in result['strips']),primary_votes_added=0,
        scope=plan['conventions'])
    write(folder/'report.json',report);checked()
    assert report['numerical_pass'],checks
    print(json.dumps({k:report[k] for k in ('name','numerical_pass','native_Cl_stability','original','native_vs_matched_circulation_relative_linf','native_vs_original_Cl_percent','native_receiver_shift_max')}),flush=True)


def launch(name):
    plan=checked();case=next(c for c in plan['cases'] if c['name']==name)
    folder=OUT/'cases'/name;folder.mkdir(parents=True,exist_ok=False)
    write(folder/'started.json',dict(case=case,plan=pin(OUT/'plan.json'),observed_utc=datetime.now(timezone.utc).isoformat()))
    def caps():
        resource.setrlimit(resource.RLIMIT_AS,(LIMITS['address_space_bytes'],)*2)
        resource.setrlimit(resource.RLIMIT_CPU,(LIMITS['cpu_seconds'],)*2)
    start=time.monotonic();pid=0;timeout=False
    with (folder/'stdout.log').open('x') as out,(folder/'stderr.log').open('x') as err:
        child=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'worker',name],cwd=ROOT,
            env={**os.environ,**THREADS},preexec_fn=caps,stdout=out,stderr=err,start_new_session=True)
        try:
            while not pid:
                pid,status,usage=os.wait4(child.pid,os.WNOHANG)
                if pid:break
                if time.monotonic()-start>LIMITS['wall_seconds']:
                    timeout=True;os.killpg(child.pid,signal.SIGKILL);pid,status,usage=os.wait4(child.pid,0);break
                time.sleep(.05)
        finally:
            if not pid:os.killpg(child.pid,signal.SIGKILL);pid,status,usage=os.wait4(child.pid,0)
            child.returncode=os.waitstatus_to_exitcode(status)
    terminal=dict(returncode=child.returncode,process_reaped=True,supervisor_timeout=timeout,
        cpu_seconds=usage.ru_utime+usage.ru_stime,wall_seconds=time.monotonic()-start,
        peak_rss_kib=usage.ru_maxrss,limits=LIMITS,observed_utc=datetime.now(timezone.utc).isoformat())
    write(folder/'terminal.json',terminal);checked()
    write(folder/'sources-verified.json',dict(all_pins_checked=True,plan=pin(OUT/'plan.json')))
    print(json.dumps(dict(name=name,**terminal)),flush=True)
    if child.returncode:sys.exit(1)
    report=read(folder/'report.json')
    print(json.dumps({k:report[k] for k in ('name','native_Cl_stability','native_vs_matched_circulation_relative_linf','native_vs_original_Cl_percent','native_receiver_shift_max')}),flush=True)


if __name__=='__main__':
    if sys.argv[1]=='prepare':prepare()
    elif sys.argv[1]=='launch':launch(sys.argv[2])
    elif sys.argv[1]=='worker':worker(sys.argv[2])
    else:raise ValueError(sys.argv[1])
