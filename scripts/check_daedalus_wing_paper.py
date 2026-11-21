"""Small serial diagnostics tied to Drela's 1989 Daedalus wing paper.

The paper describes ASWING 3.x and is not an authenticated setup for the
later rudder Bode PDF. Keep its physical model distinct from literal dae.asw.
"""
import argparse
import json
import os
from pathlib import Path
import resource
import signal
import sys
import time
import traceback
from types import SimpleNamespace

from check_daedalus_load_sensitivity import ROOT,SOURCE,LIMITS,read,write,pin,utc

STUDY=ROOT/'artifacts/daedalus-wing-paper-20261113'
PAPER=ROOT/'reference/st4-node-placement-20261109/drela-1989-wing-loads.pdf'
AVL=ROOT/'artifacts/isae/avl-matched-fields-r1-20261108/avl-fields'


def avl_tags():
    return ['avl-wing-base-v3','avl-fin-base']+[
        f'avl-{surface}-{rate}-{sign}' for surface in ('wing','fin')
        for rate in ('roll','yaw','yaw-half') for sign in ('plus','minus')]


def dynamic():
    import check_daedalus_source_operator as source
    source.imports()
    return source.dynamic(SimpleNamespace(speed=6.7,seed=SOURCE/'trim-6.7-1/state.json',
        frozen=False,no_lag=False,no_plume=False,fourier=0))


def inspect(folder,args):
    import numpy as np
    import pymupdf
    from openswing.geometry import surface_frame
    with pymupdf.open(PAPER) as pdf:
        for page in (3,4,8,9):
            pdf[page-1].get_pixmap(matrix=pymupdf.Matrix(1.5,1.5)).save(str(folder/f'paper-page-{page}.png'))
    system=dynamic();n=system.network
    zero=np.zeros(system.size);state,_,options=system.physical_state(zero,zero,None)
    residual,data=n.residual(state.x,detail=True,**options)
    r,Q,N,M,reactions,gamma=n.unpack(state.x)
    t,ids=n.station_nodes[1];sl=n.beam_elements[1];beam=next(b for b in n.model.beams if b.index==1)
    frame=Q[ids]@surface_frame(beam,t)
    chord=frame[:,:,0]
    # There are two distributed records per beam, followed by point records.
    # Use their tags; zipping this list to the meshes silently drops masses.
    records=data['masses'];g=float(n.model.constants[0])
    weights=[dict(beam=mesh.beam.index,weight_lb=float(sum(np.sum(e['mass'])*g for e in records if e['beam']==mesh.beam.index))) for mesh in n.meshes]
    point_weight=float(sum(np.sum(e['mass'])*g for e in records if e['point'] is not None))
    total_weight=sum(w['weight_lb'] for w in weights)+point_weight
    np.testing.assert_allclose(total_weight,sum(np.sum(e['mass'])*g for e in records),atol=1e-10,rtol=1e-12)
    np.testing.assert_allclose(total_weight,np.linalg.norm(data['force'].sum(axis=0)-data['aero']['force']),atol=1e-8,rtol=1e-10)
    result=dict(residual_max=float(max(abs(residual))),weight_lb=sum(w['weight_lb'] for w in weights)+point_weight,
        beam_weights_lb=weights,point_weight_lb=point_weight,condition=data['condition'].__dict__,
        wing=dict(stations=t.tolist(),positions_ft=r[ids].tolist(),
            displacement_ft=(r[ids]-n.rj[ids]).tolist(),
            chord_elevation_deg=np.rad2deg(np.arctan2(chord[:,2],chord[:,0])).tolist(),
            elastic_chord_elevation_deg=np.rad2deg(np.arctan2(chord[:,2],chord[:,0])-
                np.arctan2(surface_frame(beam,t)[:,2,0],surface_frame(beam,t)[:,0,0])).tolist(),
            element_stations=n.meshes[0].tm.tolist(),forces_lb=N[sl].tolist(),moments_lbft=M[sl].tolist(),
            strips=data['aero']['strips'][sl]),
        joint_records=[list(row) for row in n.model.records['joint']],reactions=data['reactions'],struts=data['struts'])
    # Conditions contain tuples and integer-keyed maps, all JSON-compatible.
    print('weight_lb',result['weight_lb'],'wing_tip_displacements_ft',result['wing']['displacement_ft'][0],result['wing']['displacement_ft'][-1],flush=True)
    return result


def release(folder,args):
    """Replace only the wing-root roll compatibility row at fixed equilibrium.

    The new harmonic row sets incremental roll couple to zero. The old static
    couple is retained as a constant preload, explicitly reported. This is an
    affine boundary-condition diagnostic, not a retrimmed hinged aircraft.
    """
    import numpy as np
    import scipy.sparse as sp
    from openswing.frequency_response import harmonic_solve
    system=dynamic();n=system.network;zero=np.zeros(system.size)
    candidates=[c for c in n.constraints if c['kind']=='joint' and c['a']==n.node(4,0) and c['b']==n.node(1,0)]
    assert len(candidates)==1;c=candidates[0];assert c['type']==0
    reaction_start=6*(n.nn+n.ne);row=reaction_start+c['sl'].start+3
    def couple(z):
        state,_,_=system.physical_state(z,zero,None)
        _,Q,_,_,reactions,_=n.unpack(state.x)
        v=reactions[c['sl']]
        return float(Q[c['a'],:,0]@v[3:])
    gradient=np.zeros(system.size);indices=list(range(6*c['a']+3,6*c['a']+6))+list(range(row,row+3))
    for j in indices:
        d=zero.copy();d[j]=1e-5
        gradient[j]=(8*(couple(d)-couple(-d))-(couple(2*d)-couple(-2*d)))/(12e-5)
    direction=np.random.default_rng(8963).normal(size=system.size);step=1e-5
    fd=(couple(step*direction)-couple(-step*direction))/(2*step)
    assert abs(fd-gradient@direction)<1e-8
    a=sp.load_npz(SOURCE/'assembled-6.7/A.npz');m=sp.load_npz(SOURCE/'assembled-6.7/M.npz')
    changed=a.tolil();changed[row,:]=gradient;changed=changed.tocsc()
    assert m.getrow(row).nnz==0
    maps=np.load(SOURCE/'assembled-6.7/maps.npz');assert maps['B'][row,0]==0
    samples=[]
    for frequency in (.1,.2,1.,1.15737773741517,1.5,2.):
        entries={}
        for label,matrix in (('literal_rigid',a),('incremental_roll_release',changed)):
            z,checks=harmonic_solve(matrix,m,maps['B'][:,0],2*np.pi*frequency)
            output=maps['C']@z
            entries[label]=dict(real=output.real.tolist(),imag=output.imag.tolist(),magnitude=abs(output).tolist(),checks=checks,
                joint_roll_couple_magnitude_lbft=float(abs(gradient@z)*n.F*n.L))
        samples.append(dict(frequency_hz=frequency,**entries));print(samples[-1],flush=True)
    sp.save_npz(folder/'A-incremental-roll-release.npz',changed)
    return dict(row=row,gradient_nonzeros={str(j):gradient[j] for j in indices},
        static_roll_couple_lbft=couple(zero)*n.F*n.L,directional_gradient_error=float(abs(fd-gradient@direction)),
        samples=samples,channels=['yaw_rate','roll_rate','sideslip','bank'],qualifications=[
            'Paper p4 describes a roll pin; literal public dae.asw omits KJtype and therefore specifies a rigid joint.',
            'This releases only incremental roll couple, holding accepted geometry and the reported static couple as preload.',
            'No retrim, nonlinear hinged response, historical setup identification or production model change is claimed.'])


def compare(folder,args):
    import numpy as np
    from PIL import Image
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    saved=read(STUDY/'static-and-pages-v3/result.json');wing=saved['wing']
    rgb=np.array(Image.open(STUDY/'static-and-pages-v3/paper-page-9.png').convert('RGB'))
    # Manual axis calibration on the retained 1.5x render: force plots span
    # -b/2..b/2 at x=133..775. Do not fit scale to the computed deflection.
    xmin,xmax=133.,775.;center=(xmin+xmax)/2;scale=(xmax-xmin)/112.
    dark=np.mean(rgb,axis=2)<105;points=[]
    for x in range(140,766):
        hits=np.flatnonzero(dark[770:840,x])+770
        if not len(hits):continue
        run=hits[hits<=hits[0]+2]
        points.append([x,float(np.mean(run))])
    points=np.array(points);root_y=float(np.mean(points[abs(points[:,0]-center)<=4,1]))
    t=np.array(wing['stations']);r=np.array(wing['positions_ft']);root=int(np.argmin(abs(t)))
    projection=np.c_[center+scale*r[:,1],root_y-scale*(r[:,2]-r[root,2])]
    error=np.interp(points[:,0],projection[:,0],projection[:,1])-points[:,1]
    moments=np.array(wing['moments_lbft']);mid=np.array(wing['element_stations'])
    strips=wing['strips'];cl=np.array([s['cl'] for s in strips])
    fig,axes=plt.subplots(1,2,figsize=(12,6),layout='constrained')
    ax=axes[0];ax.imshow(rgb);ax.plot(center+scale*mid,363.-.4*abs(moments[:,0]),color='#7b2cbf',label='Current bending moment')
    ax.plot(center+scale*mid,747.-80.*cl,color='#009e73',label='Current section CL')
    ax.set_xlim(70,850);ax.set_ylim(755,175);ax.legend(loc='center left');ax.set_title('Figure 8: literal current model over paper')
    ax=axes[1];ax.plot((points[:,0]-center)/(xmax-xmin),(root_y-points[:,1])/(xmax-xmin),color='black',label='Paper raster')
    ax.plot(r[:,1]/112,(r[:,2]-r[root,2])/112,color='#7b2cbf',label='Current beam axis')
    ax.set_xlabel('Projected spanwise coordinate / nominal span');ax.set_ylabel('Height above root / nominal span');ax.grid(alpha=.2);ax.legend();ax.set_title('Wing shape: no deflection scale fitted')
    fig.suptitle(f'Steady-wing comparison, not a matched-input validation\nPaper: 22 ft/s, 240 lb; current literal model: 21.9816 ft/s, {saved["weight_lb"]:.4f} lb')
    fig.savefig(folder/'paper-comparison.png',dpi=150);fig.savefig(folder/'paper-comparison.svg');plt.close(fig)
    result=dict(calibration=dict(render_scale=1.5,span_x_pixels=[xmin,xmax],root_y_px=root_y,
            moment_zero_y_px=363,moment_pixels_per_lbft=.4,cl_zero_y_px=747,cl_pixels_per_unit=80),
        paper_profile_pixels=points.tolist(),projected_current_profile_pixels=projection.tolist(),
        mean_profile_error_px=float(np.mean(error)),rms_profile_error_px=float(np.sqrt(np.mean(error**2))),max_profile_error_px=float(max(abs(error))),
        current_root_Mx_lbft=float(np.mean(abs(moments[np.argsort(abs(mid))[:2],0]))),
        current_max_element_Mx_lbft=float(max(abs(moments[:,0]))),current_max_cl=float(max(cl)),
        current_tip_rise_ft=(r[[0,-1],2]-r[root,2]).tolist(),
        qualifications=[
            'Manual axes on a scanned figure; no authoritative digital ordinate values or original input deck.',
            'Wing sketch assumed to share horizontal scale and equal vertical scale with the force plot. Its root height only sets the vertical origin.',
            'Raster includes chord edges and line thickness; current beam axis is not exactly the drawn outline.',
            'The current literal model has different gross weight and root-joint conditions; no numerical pass is assigned.',
            'Element-center Mx is shown without reconstructing sided endpoint jumps; compare smooth trends, not peak convergence.'])
    print({k:v for k,v in result.items() if k not in ('paper_profile_pixels','projected_current_profile_pixels','qualifications')},flush=True)
    return result


def avl(folder,args):
    """Rigid loaded-surface rate audit; no trim or full-aircraft response."""
    import importlib.util
    import subprocess
    from dataclasses import replace
    import numpy as np
    from openswing.aero import FlightCondition,evaluate_aerodynamics
    from openswing.frozen_influence import lifting_geometry
    from openswing.factored_influence import FactoredInfluence
    from avl_vorvelc_reference import matrix as native_core_matrix
    spec=importlib.util.spec_from_file_location('matched_fields',ROOT/'scripts/verify-avl-matched-fields.py')
    matched=importlib.util.module_from_spec(spec);spec.loader.exec_module(matched)
    system=dynamic();n=system.network;zero=np.zeros(system.size)
    state,_,options=system.physical_state(zero,zero,None)
    residual,data=n.residual(state.x,detail=True,**options);assert max(abs(residual))<1e-9
    mesh=next(m for m in data['meshes'] if m.beam.index==args.beam);beam=mesh.beam
    model=replace(n.model,beams=[beam],records={})
    g=lifting_geometry([mesh],np.array([1.,0.,0.]))
    stations=np.r_[mesh.t0,mesh.t1[-1]]
    frames=np.concatenate([mesh.frame0,mesh.frame1[-1:]])
    quarters=np.concatenate([g['a'],g['b'][-1:]])
    assert len(stations)==len(mesh.tm)+1
    refs=model.reference
    lines=['Daedalus loaded isolated surface rate audit','0','0 0 0',
        ' '.join(map(str,refs[0])),' '.join(map(str,refs[1])),'0',
        'SURFACE',f'Loaded beam {args.beam}','1 0','COMPONENT','1']
    for t,frame,quarter in zip(stations,frames,quarters):
        c,s,norm=frame.T;across=np.linalg.norm(np.cross([1.,0.,0.],s))
        chord=beam.value('chord',t)/across
        alpha=np.deg2rad(beam.value('alpha',t))
        for k,value in data['condition'].controls.items():alpha+=value*beam.value(f'dCLdF{k}',t)/beam.value('dCLda',t)
        normal=np.sin(alpha)*c+np.cos(alpha)*norm
        n0=np.cross([1.,0.,0.],s)/across
        incidence=np.rad2deg(np.arctan2(normal[0],normal@n0))
        leading=quarter-[.25*chord,0.,0.]
        lines+=['SECTION',' '.join(f'{v:.17g}' for v in (*leading,chord,incidence))+' 1 0',
                'CLAF',f'{beam.value("dCLda",t)/(2*np.pi):.17g}']
    (folder/'model.avl').write_text('\n'.join(lines)+'\n')
    alpha,beta=data['condition'].alpha,data['condition'].beta
    rates=np.zeros(3);axis={'x':0,'y':1,'z':2}[args.axis];rates[axis]=args.rate
    scale=refs[0,1] if axis==1 else refs[0,2]
    command={'x':'R','y':'P','z':'Y'}[args.axis]
    commands=f'LOAD model.avl\nOPER\nO\nA\nR\n\nA A {alpha:.17g}\nB B {beta:.17g}\n{command} {command} {args.rate*scale/2:.17g}\nX\nMRF\nFT total.txt\nFS strips.txt\nFSB body-strips.txt\nFE elements.txt\n\nQUIT\n'
    (folder/'commands.txt').write_text(commands)
    started=time.monotonic()
    process=subprocess.run([str(AVL)],input=commands,text=True,capture_output=True,cwd=folder,timeout=8)
    (folder/'native-stdout.txt').write_text(process.stdout);(folder/'native-stderr.txt').write_text(process.stderr)
    write(folder/'native-terminal.json',dict(returncode=process.returncode,process_reaped=True,wall_seconds=time.monotonic()-started))
    assert process.returncode==0,process.stderr
    f=matched.read_fields(folder/'elements.txt');assert len(f['GAM'])==len(mesh.tm)
    np.savez_compressed(folder/'native-fields.npz',**f)
    # A uniform gust holds the incident velocity at the accepted alpha/beta
    # while leaving the influence wake on body x, as in this native AVL run.
    wind=data['condition'].vectors()[0]
    condition=FlightCondition(speed=1.,alpha=0.,beta=0.,mach=0.,density=1.,
        rates=tuple(rates),stall=False,freeze_influences=False,
        controls=data['condition'].controls,gust=dict(type='uniform',velocity=(wind-[1.,0.,0.]).tolist()))
    result=evaluate_aerodynamics(model,condition,[mesh]);write(folder/'openswing.json',result)
    np.testing.assert_allclose(f['VINF'],np.broadcast_to(wind,f['VINF'].shape),atol=2e-13,rtol=2e-13)
    gamma=f['GAM'].ravel();native_velocity=f['VINF']+np.cross(f['RV']-refs[1],rates)+f['VV']
    force=gamma[:,None]*np.cross(native_velocity,f['RV2']-f['RV1'])
    moment=np.cross(f['RV']-refs[1],force)
    labels=matched.NATIVE.labeled(folder/'total.txt')
    labels={name:value for key,values in labels.items() for name,value in zip(key.removeprefix('Trefftz Plane: ').split(', '),values)}
    coefficient=np.r_[force.sum(axis=0)*2/refs[0,0],moment.sum(axis=0)*2/refs[0,0]/refs[0,[2,1,2]]]
    expected=np.array([labels[k] for k in ('CXtot','CYtot','CZtot','Cltot','Cmtot','Cntot')])
    np.testing.assert_allclose(coefficient,expected,atol=1e-11,rtol=1e-10)
    # Native coordinates/normals isolate the vortex/rate arithmetic from
    # conversion and material-frame conventions. No native value is fitted.
    kernel_factor=4*np.pi*.079577472
    cp=FactoredInfluence(f['RC'],f['RV1'],f['RV2'],[1.,0.,0.],np.eye(3))
    hv=FactoredInfluence(f['RV'],f['RV1'],f['RV2'],[1.,0.,0.],np.eye(3),exclude_bound=np.eye(len(gamma),dtype=bool))
    normal_matrix=np.einsum('ijk,ik->ij',cp.matrix(),f['ENC'])
    free=f['VINF']+np.cross(f['RC']-refs[1],rates)
    checked_gamma=np.linalg.solve(normal_matrix,-np.sum(free*f['ENC'],axis=1))/kernel_factor
    zero_core_gamma_difference=float(max(abs(checked_gamma-gamma))/max(abs(gamma)))
    zero_core_field_difference=float(np.max(abs(kernel_factor*hv.apply(gamma)-f['VV'])))
    # AVL VSRF/VORVELC uses a quartic core of 0.0001 strip width even on
    # the same component. ASWING's same-beam core is zero. Replay each
    # law separately, as in the existing curved SA-11 conversion audit.
    core_cp=native_core_matrix(f['RC'],f['RV1'],f['RV2'],0.)
    core_hv=native_core_matrix(f['RV'],f['RV1'],f['RV2'],0.,exclude_self=True)
    core_gamma=np.linalg.solve(np.einsum('ijk,ik->ij',core_cp,f['ENC']),-np.sum(free*f['ENC'],axis=1))
    gamma_error=float(max(abs(core_gamma-gamma))/max(abs(gamma)))
    field_error=float(np.max(abs(np.einsum('ijk,j->ik',core_hv,gamma)-f['VV'])))
    assert gamma_error<1e-6 and field_error<1e-6,(gamma_error,field_error)
    strips=result['strips'];pgamma=np.array([s['circulation'] for s in strips]);velocity=np.array([s['relative_velocity'] for s in strips])
    pforce=pgamma[:,None]*np.cross(velocity,mesh.frames[:,:,1])*mesh.length[:,None]
    physical_arm=((.25-beam.value('Xax',mesh.tm))*beam.value('chord',mesh.tm))[:,None]*mesh.frames[:,:,0]
    pmoment=np.cross(mesh.rm+physical_arm-refs[1],pforce)
    output=dict(beam=args.beam,axis=args.axis,rate_rad_per_length=args.rate,alpha_deg=alpha,beta_deg=beta,
        intervals=len(mesh.tm),native_circulatory_wrench=np.r_[force.sum(axis=0),moment.sum(axis=0)].tolist(),
        openswing_circulatory_wrench=np.r_[pforce.sum(axis=0),pmoment.sum(axis=0)].tolist(),
        native_force_reconstruction_error=float(max(abs(coefficient-expected))),
        matched_coordinate_relative_gamma_error=gamma_error,matched_coordinate_max_field_error=field_error,
        native_zero_core_relative_gamma_difference=zero_core_gamma_difference,
        native_zero_core_max_field_difference=zero_core_field_difference,
        direct_relative_gamma_error=float(max(abs(pgamma-gamma))/max(abs(gamma))),
        geometry_max_errors={k:float(np.max(abs(g[k]-f[v]))) for k,v in [('a','RV1'),('b','RV2'),('hv','RV'),('cp','RC')]},
        qualifications=[
            'Isolated rigid loaded surface, Mach zero, speed and density one, fixed body-x wake; no body, engines, other surfaces or structural response.',
            'Production retains source mesh/material frames; native uses standard streamwise-chord AVL SECTION interpolation. Differences are measured, not assumed absent.',
            'Compare circulation and circulation-related wrench only; native AVL does not include ASWING apparent inertia or circulation-rate lift.',
            'Matched-coordinate field audit uses native exported receivers/normals, rounded PI4INV and quartic same-component core. The distinct ASW zero-core field difference is retained; production predictions are not rescaled.'])
    print(json.dumps(output),flush=True);return output


def avl_summary(folder,args):
    cases={tag:read(STUDY/tag/'result.json') for tag in avl_tags()}
    terminals=[read(STUDY/tag/'terminal.json') for tag in avl_tags()]
    for tag,terminal in zip(avl_tags(),terminals):
        assert terminal['returncode']==0 and terminal['process_reaped'] and terminal['inputs_unchanged']
        native=read(STUDY/tag/'native-terminal.json')
        assert native['returncode']==0 and native['process_reaped']
        plan=read(STUDY/tag/'plan.json')
        assert pin(STUDY/tag/'runner.py')==plan['inputs_sha256'][str(Path(__file__).resolve())]
        # Old runners remain immutable. All native and production physics
        # inputs must still match the versions used for every numerical job.
        for name,h in plan['inputs_sha256'].items():
            if '/openswing/' in name or name in (str(AVL),str(ROOT/'scripts/avl_vorvelc_reference.py')):
                assert pin(name)==h,name
    derivatives=[]
    for surface in ('wing','fin'):
        for axis in ('roll','yaw'):
            def pair(label):
                p=cases[f'avl-{surface}-{label}-plus'];m=cases[f'avl-{surface}-{label}-minus']
                step=p['rate_rad_per_length']-m['rate_rad_per_length']
                return {solver:[(a-b)/step for a,b in zip(p[f'{solver}_circulatory_wrench'],m[f'{solver}_circulatory_wrench'])]
                        for solver in ('native','openswing')}
            values=pair(axis);native=values['native'];production=values['openswing']
            entry=dict(surface=surface,axis=axis,step_rad_per_length=1e-4,**values,
                relative_difference_percent=[100*(p-n)/n if n else None for p,n in zip(production,native)])
            if axis=='yaw':
                fine=pair('yaw-half');entry['half_step']=fine
                entry['half_step_change_percent']={solver:[100*(a-b)/a if a else None for a,b in zip(fine[solver],values[solver])]
                                                   for solver in values}
                entry['half_step_max_scaled_change']={solver:max(abs(a-b) for a,b in zip(fine[solver],values[solver]))/max(map(abs,fine[solver])) for solver in values}
                assert max(entry['half_step_max_scaled_change'].values())<1e-5
            derivatives.append(entry)
    return dict(cases=cases,derivatives=derivatives,wrench_order=['Fx','Fy','Fz','Mx','My','Mz'],
        checks={key:max(c[key] for c in cases.values()) for key in (
            'native_force_reconstruction_error','matched_coordinate_relative_gamma_error',
            'matched_coordinate_max_field_error','native_zero_core_max_field_difference')},
        resources=dict(jobs=len(cases),max_cpu_seconds=max(t['cpu_seconds'] for t in terminals),
            max_wall_seconds=max(t['wall_seconds'] for t in terminals),max_peak_rss_kib=max(t['peak_rss_kib'] for t in terminals)),
        qualifications=[
            'Fixed, isolated loaded surfaces at zero Mach, unit speed/density and body-x wake; no full-aircraft dynamics or operating-point identification.',
            'Source endpoints match; receiver positions, section normals and bound-line versus beam-length force conventions remain distinct.',
            'Yaw rate perturbation is checked at half step. Small cross-axis components can have large relative differences; every wrench component is retained.',
            'These are numerical diagnostics, not Bode reference passes or ISAE completion increments.'])


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage',choices=['inspect','release','compare','avl','avl_summary']);parser.add_argument('--tag',required=True)
    parser.add_argument('--beam',type=int,choices=[1,3],default=1)
    parser.add_argument('--axis',choices=['x','y','z'],default='x');parser.add_argument('--rate',type=float,default=0.)
    args=parser.parse_args();STUDY.mkdir(exist_ok=True);folder=STUDY/args.tag;folder.mkdir(exist_ok=False)
    (folder/'runner.py').write_bytes(Path(__file__).read_bytes())
    inputs=[Path(__file__),ROOT/'scripts/check_daedalus_load_sensitivity.py',ROOT/'scripts/check_daedalus_source_operator.py',
        ROOT/'examples/dae.asw',ROOT/'examples/dae-cruise-physical-mesh-project.json',SOURCE/'trim-6.7-1/state.json',PAPER,
        ROOT/'reference/aswing_doc.txt',ROOT/'docs/validation/isae-st4-node-placement-sources-20261109.json']
    inputs += [SOURCE/'assembled-6.7'/name for name in ('A.npz','M.npz','maps.npz','plan.json','result.json','terminal.json')]
    if args.stage=='compare':inputs += [STUDY/'static-and-pages-v3/result.json',STUDY/'static-and-pages-v3/paper-page-9.png']
    if args.stage=='avl':inputs += [AVL,ROOT/'scripts/verify-avl-matched-fields.py',ROOT/'scripts/verify-avl-native-controls.py',
        ROOT/'scripts/avl_vorvelc_reference.py',ROOT/'reference/avl-native-20261108/source/AVL3.52rel09032025/src/aic.f']
    if args.stage=='avl_summary':inputs += [STUDY/tag/name for tag in avl_tags()
        for name in ('plan.json','result.json','terminal.json','native-terminal.json','runner.py')]
    pins={str(p.resolve()):pin(p) for p in inputs+list((ROOT/'openswing').glob('*.py'))}
    write(folder/'plan.json',dict(observed_utc=utc(),arguments=vars(args),inputs_sha256=pins,limits=LIMITS))
    started=time.monotonic();sys.stdout.flush();pid=os.fork()
    if pid==0:
        code=0
        for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[key]='1'
        resource.setrlimit(resource.RLIMIT_AS,(LIMITS['address_space_bytes'],)*2)
        resource.setrlimit(resource.RLIMIT_CPU,(LIMITS['cpu_seconds'],)*2);sys.path.insert(0,str(ROOT))
        with (folder/'stdout.log').open('x') as out,(folder/'stderr.log').open('x') as err:
            os.dup2(out.fileno(),1);os.dup2(err.fileno(),2)
            try:write(folder/'result.json',globals()[args.stage](folder,args))
            except BaseException:traceback.print_exc();code=1
            sys.stdout.flush();sys.stderr.flush()
        os._exit(code)
    reaped=0;timed_out=False
    try:
        while not reaped:
            reaped,status,usage=os.wait4(pid,os.WNOHANG)
            if reaped:break
            if time.monotonic()-started>LIMITS['wall_seconds']:
                timed_out=True;os.kill(pid,signal.SIGKILL);reaped,status,usage=os.wait4(pid,0);break
            time.sleep(.05)
    finally:
        if not reaped:os.kill(pid,signal.SIGKILL);reaped,status,usage=os.wait4(pid,0)
    receipt=dict(observed_utc=utc(),returncode=os.waitstatus_to_exitcode(status),process_reaped=True,timed_out=timed_out,
        cpu_seconds=usage.ru_utime+usage.ru_stime,wall_seconds=time.monotonic()-started,peak_rss_kib=usage.ru_maxrss,
        limits=LIMITS,inputs_unchanged=all(pin(p)==h for p,h in pins.items()))
    write(folder/'terminal.json',receipt);print(json.dumps(receipt),flush=True)
    raise SystemExit(receipt['returncode'] or (0 if receipt['inputs_unchanged'] else 1))


if __name__=='__main__':main()
