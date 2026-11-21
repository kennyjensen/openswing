"""Separate loaded-surface AVL/ASW conventions in small, serial replay jobs.

These are counterfactual operator/force replays, not production changes or
new reference passes. Each endpoint is checked against its saved native or
production result. No native executable or full-aircraft trim is rerun.
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

from check_daedalus_load_sensitivity import ROOT, SOURCE, LIMITS, read, write, pin, utc

PRIOR=ROOT/'artifacts/daedalus-wing-paper-20261113'
STUDY=ROOT/'artifacts/daedalus-avl-conventions-20261113'
STAGES=['native','zero_core','control_point','normal','force_receiver','force_vector','moment_arm']


def tags(beam):
    surface={1:'wing',3:'fin'}[beam]
    return [f'avl-{surface}-base'+('-v3' if beam==1 else '')]+[
        f'avl-{surface}-{axis}-{sign}' for axis in ('roll','yaw') for sign in ('plus','minus')]


def replay(folder,args):
    import numpy as np
    from check_daedalus_wing_paper import dynamic
    from openswing.frozen_influence import lifting_geometry
    from openswing.factored_influence import FactoredInfluence
    from avl_vorvelc_reference import matrix as native_matrix
    system=dynamic();network=system.network;zero=np.zeros(system.size)
    state,_,options=system.physical_state(zero,zero,None)
    residual,data=network.residual(state.x,detail=True,**options)
    assert max(abs(residual))<1e-9
    mesh=next(m for m in data['meshes'] if m.beam.index==args.beam);beam=mesh.beam
    refs=network.model.reference
    np.testing.assert_array_equal(refs[1],refs[3])
    g=lifting_geometry([mesh],np.array([1.,0.,0.]))
    alpha=np.deg2rad(beam.value('alpha',mesh.tm))
    for k,value in data['condition'].controls.items():
        alpha+=value*beam.value(f'dCLdF{k}',mesh.tm)/beam.value('dCLda',mesh.tm)
    normal=np.sin(alpha)[:,None]*mesh.frames[:,:,0]+np.cos(alpha)[:,None]*mesh.frames[:,:,2]
    line=mesh.length[:,None]*mesh.frames[:,:,1]
    location=mesh.rm+((.25-beam.value('Xax',mesh.tm))*beam.value('chord',mesh.tm))[:,None]*mesh.frames[:,:,0]
    results=[];matrices={}
    for tag in tags(args.beam):
        saved=read(PRIOR/tag/'result.json');native=np.load(PRIOR/tag/'native-fields.npz')
        production=read(PRIOR/tag/'openswing.json')
        for key in ('a','b'):
            np.testing.assert_allclose(g[key],native['RV1' if key=='a' else 'RV2'],atol=2e-13,rtol=0.)
        rates=np.zeros(3);rates[{'x':0,'y':1,'z':2}[saved['axis']]]=saved['rate_rad_per_length']
        stages=[]
        for index,label in enumerate(STAGES):
            cp=native['RC'] if index<2 else g['cp']
            norm=native['ENC'] if index<3 else normal
            hv=native['RV'] if index<4 else g['hv']
            dl=native['RV2']-native['RV1'] if index<5 else line
            arm=hv if index<6 else location
            # Keep force application at the original AVL RV while changing
            # just the velocity receiver. The final stage changes that arm.
            if index<6:arm=native['RV']
            if label not in matrices:
                if index==0:
                    icp=native_matrix(cp,g['a'],g['b'],0.)
                    ihv=native_matrix(hv,g['a'],g['b'],0.,exclude_self=True)
                else:
                    icp=FactoredInfluence(cp,g['a'],g['b'],[1.,0.,0.],np.eye(3)).matrix()
                    ihv=FactoredInfluence(hv,g['a'],g['b'],[1.,0.,0.],np.eye(3),
                        exclude_bound=np.eye(len(mesh.tm),dtype=bool)).matrix()
                matrices[label]=(np.einsum('ijk,ik->ij',icp,norm),ihv)
            operator,ihv=matrices[label]
            free=native['VINF']+np.cross(cp-refs[3],rates)
            gamma=np.linalg.solve(operator,-np.sum(free*norm,axis=1))
            induced=np.einsum('ijk,j->ik',ihv,gamma)
            velocity=native['VINF']+np.cross(hv-refs[3],rates)+induced
            force=gamma[:,None]*np.cross(velocity,dl)
            moment=np.cross(arm-refs[1],force)
            wrench=np.r_[force.sum(axis=0),moment.sum(axis=0)]
            stages.append(dict(name=label,wrench=wrench.tolist(),circulation=gamma.tolist(),
                residual=float(max(abs(operator@gamma+np.sum(free*norm,axis=1))))))
            assert stages[-1]['residual']<1e-11
            if index==0:
                np.testing.assert_allclose(gamma,native['GAM'].ravel(),atol=2e-12,rtol=2e-12)
                np.testing.assert_allclose(induced,native['VV'],atol=2e-12,rtol=2e-12)
                np.testing.assert_allclose(wrench,saved['native_circulatory_wrench'],atol=2e-10,rtol=2e-12)
            elif index==len(STAGES)-1:
                expected_gamma=np.array([s['circulation'] for s in production['strips']])
                expected_velocity=np.array([s['relative_velocity'] for s in production['strips']])
                np.testing.assert_allclose(gamma,expected_gamma,atol=2e-12,rtol=2e-12)
                np.testing.assert_allclose(velocity,expected_velocity,atol=2e-12,rtol=2e-12)
                np.testing.assert_allclose(wrench,saved['openswing_circulatory_wrench'],atol=2e-10,rtol=2e-12)
        results.append(dict(tag=tag,axis=saved['axis'],rate=saved['rate_rad_per_length'],stages=stages))
    derivatives=[]
    for axis in ('x','z'):
        plus=next(r for r in results if r['axis']==axis and r['rate']>0)
        minus=next(r for r in results if r['axis']==axis and r['rate']<0)
        ds=(np.array([s['wrench'] for s in plus['stages']])-np.array([s['wrench'] for s in minus['stages']]))/(plus['rate']-minus['rate'])
        derivatives.append(dict(axis=axis,stages=[dict(name=name,wrench_derivative=v.tolist()) for name,v in zip(STAGES,ds)],
            increments=[dict(name=name,delta=(ds[i]-ds[i-1]).tolist(),
                percent_of_native=(100*(ds[i]-ds[i-1])/ds[0]).tolist()) for i,name in enumerate(STAGES) if i],
            final_relative_difference_percent=(100*(ds[-1]-ds[0])/ds[0]).tolist()))
    np.savez_compressed(folder/'geometry.npz',**g,normal=normal,force_vector=line,moment_location=location,
        native_normal=native['ENC'],native_cp=native['RC'],native_hv=native['RV'])
    return dict(beam=args.beam,intervals=len(mesh.tm),derivatives=derivatives,cases=results,
        max_normal_angle_deg=float(np.rad2deg(np.max(np.arccos(np.clip(np.sum(normal*native['ENC'],axis=1),-1,1))))),
        wrench_order=['Fx','Fy','Fz','Mx','My','Mz'],
        qualifications=[
            'Fixed isolated loaded surface at Mach zero and unit speed/density. Original bound endpoints and body-x wake remain fixed.',
            'Native and production endpoints reproduce their saved circulation, velocity and circulatory wrench within unchanged numerical gates.',
            'Stage order is explicit; increments are conditional differences, not a unique additive attribution of interacting conventions.',
            'zero_core also replaces native rounded PI4INV by 1/(4*pi). Receivers change induced and imposed-rate velocity locations together.',
            'Force vector changes from native bound vector to source material span times material interval length. Moment arm then changes to the physical quarter chord.',
            'No production setting, aircraft parameter, Bode result or ISAE count is changed.'])


def project(folder,args):
    """Affine body-rate load correction, preserving the accepted equilibrium.

    Add only the measured isolated, incompressible, steady circulatory load
    derivative difference to free-frame roll/yaw columns. This deliberately
    does not substitute a complete AVL or alternative unsteady operator.
    """
    import numpy as np
    import scipy.sparse as sp
    from check_daedalus_wing_paper import dynamic
    from openswing.frequency_response import harmonic_solve
    system=dynamic();n=system.network;zero=np.zeros(system.size)
    state,_,options=system.physical_state(zero,zero,None)
    residual,data=n.residual(state.x,detail=True,**options)
    assert max(abs(residual))<1e-9
    rho=data['aero']['atmosphere']['density'];speed=data['condition'].speed
    a,m=(sp.load_npz(SOURCE/'assembled-6.7'/name) for name in ('A.npz','M.npz'))
    maps=np.load(SOURCE/'assembled-6.7/maps.npz')
    changes={};checks=[]
    for beam_index,surface in ((1,'wing'),(3,'fin')):
        mesh=next(mesh for mesh in data['meshes'] if mesh.beam.index==beam_index)
        previous=read(STUDY/surface/'result.json')
        correction=sp.lil_matrix(a.shape)
        for axis,label in ((0,'roll'),(2,'yaw')):
            force=[];moment=[]
            for sign in ('plus','minus'):
                native=np.load(PRIOR/f'avl-{surface}-{label}-{sign}/native-fields.npz')
                production=read(PRIOR/f'avl-{surface}-{label}-{sign}/openswing.json')
                rate=1e-4*(1 if sign=='plus' else -1);rates=np.zeros(3);rates[axis]=rate
                nv=native['VINF']+np.cross(native['RV']-n.model.reference[3],rates)+native['VV']
                nf=native['GAM']*np.cross(nv,native['RV2']-native['RV1'])
                nm=np.cross(native['RV']-mesh.rm,nf)
                strips=production['strips'];pg=np.array([s['circulation'] for s in strips])
                pv=np.array([s['relative_velocity'] for s in strips])
                pf=pg[:,None]*np.cross(pv,mesh.frames[:,:,1])*mesh.length[:,None]
                arm=((.25-mesh.beam.value('Xax',mesh.tm))*mesh.beam.value('chord',mesh.tm))[:,None]*mesh.frames[:,:,0]
                pm=np.cross(arm,pf)
                force.append(nf-pf);moment.append(nm-pm)
            df=(force[0]-force[1])/2e-4;dm=(moment[0]-moment[1])/2e-4
            expected=next(d for d in previous['derivatives'] if d['axis']=='xz'[axis//2])['stages']
            wanted=np.array(expected[0]['wrench_derivative'])-np.array(expected[-1]['wrench_derivative'])
            direct=np.r_[df.sum(axis=0),(dm+np.cross(mesh.rm-n.model.reference[1],df)).sum(axis=0)]
            np.testing.assert_allclose(direct,wanted,atol=3e-8,rtol=2e-10)
            # F = rho*U^2*F_unit(omega/U); z_Omega gives omega=W*z.
            df*=rho*speed*system.W;dm*=rho*speed*system.W
            nodal_force=np.zeros_like(data['r']);nodal_moment=np.zeros_like(data['r'])
            for ids,f,q in n.steady_lifting_wrenches(mesh,df,dm):
                np.add.at(nodal_force,ids,f);np.add.at(nodal_moment,ids,q)
            net_force=nodal_force.sum(axis=0)
            net_moment=(nodal_moment+np.cross(data['r']-n.model.reference[1],nodal_force)).sum(axis=0)
            closure=max(abs(np.r_[net_force,net_moment]-direct*rho*speed*system.W))
            assert closure<1e-9,closure
            column=system.frame_start+3+axis
            dz=zero.copy();dz[column]=1e-5
            moved,_,_=system.physical_state(dz,zero,None)
            np.testing.assert_allclose((moved.Omega-state.Omega)/1e-5,np.eye(3)[axis]*system.W,atol=1e-13,rtol=1e-13)
            v=zero.copy()
            v[6*n.ne:6*n.ne+3*n.nn]=(nodal_force/n.F).ravel()
            v[6*n.ne+3*n.nn:6*n.ne+6*n.nn]=(nodal_moment/(n.F*n.L)).ravel()
            v[n.operating_start:n.size]=np.r_[net_force/n.F,net_moment/(n.F*n.L)]
            correction[:,column]=v[:,None]
            checks.append(dict(surface=surface,axis=label,wrench_replay_error=float(max(abs(direct-wanted))),
                transfer_closure=float(closure),column=column,isolated_difference=wanted.tolist()))
        changes[surface]=correction.tocsc()
    outputs=[]
    for label,increment in [('baseline',sp.csc_matrix(a.shape)),('wing',changes['wing']),
                             ('fin',changes['fin']),('both',changes['wing']+changes['fin'])]:
        z,diagnostics=harmonic_solve(a+increment,m,maps['B'][:,0],2*np.pi*args.frequency)
        response=maps['C']@z
        outputs.append(dict(name=label,real=response.real.tolist(),imag=response.imag.tolist(),
            magnitude=abs(response).tolist(),solve_checks=diagnostics))
        print(label,abs(response).tolist(),flush=True)
    for label,delta in changes.items():sp.save_npz(folder/f'A-increment-{label}.npz',delta)
    return dict(frequency_hz=args.frequency,outputs=outputs,checks=checks,
        channels=['yaw_rate','roll_rate','sideslip','bank'],base_residual=float(max(abs(residual))),
        scale=dict(density=rho,speed=speed,angular_rate_scale=system.W),
        qualification='Affine, fixed-base correction of isolated Mach-zero steady circulatory body-rate load derivatives only. It omits the corresponding circulation equations, local elastic motion, mutual influences, PG Mach, lag and apparent-inertia changes. It neither validates a hybrid physical model nor replaces any production result.')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage',choices=['replay','project'],default='replay')
    parser.add_argument('--frequency',type=float,default=1.15737773741517)
    parser.add_argument('--beam',type=int,choices=[1,3],default=1)
    parser.add_argument('--tag',required=True);args=parser.parse_args()
    STUDY.mkdir(exist_ok=True);folder=STUDY/args.tag;folder.mkdir(exist_ok=False)
    (folder/'runner.py').write_bytes(Path(__file__).read_bytes())
    inputs=[Path(__file__),ROOT/'scripts/check_daedalus_wing_paper.py',ROOT/'scripts/check_daedalus_load_sensitivity.py',
        ROOT/'scripts/check_daedalus_source_operator.py',ROOT/'scripts/avl_vorvelc_reference.py',
        ROOT/'examples/dae.asw',ROOT/'examples/dae-cruise-physical-mesh-project.json',SOURCE/'trim-6.7-1/state.json',
        ROOT/'reference/aswing-authoritative-20261108/drela-aswing-steady.pdf',
        ROOT/'docs/validation/aswing-authoritative-sources.json']
    selected=tags(args.beam) if args.stage=='replay' else tags(1)+tags(3)
    inputs += [PRIOR/tag/name for tag in selected for name in ('result.json','native-fields.npz','openswing.json','plan.json','terminal.json')]
    if args.stage=='project':
        inputs += [SOURCE/'assembled-6.7'/name for name in ('A.npz','M.npz','maps.npz','plan.json','result.json','terminal.json')]
        inputs += [STUDY/surface/name for surface in ('wing','fin') for name in ('result.json','plan.json','terminal.json')]
    pins={str(p.resolve()):pin(p) for p in inputs+list((ROOT/'openswing').glob('*.py'))}
    for tag in selected:
        terminal=read(PRIOR/tag/'terminal.json');assert terminal['returncode']==0 and terminal['inputs_unchanged'] and terminal['process_reaped']
        prior=read(PRIOR/tag/'plan.json')['inputs_sha256']
        for name,h in prior.items():
            if '/openswing/' in name or name.endswith('/examples/dae.asw'):assert pins[name]==h,name
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
    terminal=dict(observed_utc=utc(),returncode=os.waitstatus_to_exitcode(status),process_reaped=True,timed_out=timed_out,
        cpu_seconds=usage.ru_utime+usage.ru_stime,wall_seconds=time.monotonic()-started,peak_rss_kib=usage.ru_maxrss,
        limits=LIMITS,inputs_unchanged=all(pin(p)==h for p,h in pins.items()))
    write(folder/'terminal.json',terminal);print(json.dumps(terminal),flush=True)
    raise SystemExit(terminal['returncode'] or (0 if terminal['inputs_unchanged'] else 1))


if __name__=='__main__':main()
