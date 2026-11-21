"""Bounded first variation of coupled response under aerodynamic refinement.

Reuse solved circulation on each fixed-structure aerodynamic grid. Transfer
the complete loads to the original structural equations conservatively, then
solve the full coarse descriptor for their difference. This is the derivative
of an affine interpolation of reduced aerodynamic operators, not a retrimmed
or fully recoupled fine-grid aircraft prediction.
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

from check_daedalus_load_sensitivity import ROOT,SOURCE,LIMITS,read,write,pin,utc
from check_daedalus_aero_resolution import STUDY as RESOLUTION,ACCEPTED,refined_mesh_motion

STUDY=ROOT/'artifacts/daedalus-aero-feedback-20261113'
CAPTURES=['capture-1','capture-2','capture-4']
PRIOR=ROOT/'artifacts/daedalus-load-sensitivity-20261113/reference-dip'


def accepted(folder):
    terminal=read(folder/'terminal.json')
    assert terminal['returncode']==0 and terminal['process_reaped'] and terminal['inputs_unchanged']
    return read(folder/'result.json')


def capture(folder,args):
    import numpy as np
    import scipy.sparse as sp
    from check_daedalus_wing_paper import dynamic
    from check_daedalus_load_sensitivity import groups
    from openswing.aero import evaluate_aerodynamics
    from openswing.frequency_response import harmonic_solve,HarmonicInput

    original=RESOLUTION/ACCEPTED[[1,2,4].index(args.factor)]
    record=accepted(original);saved=np.load(original/'arrays.npz')
    system=dynamic();n=system.network;zero=np.zeros(system.size)
    assert n.ng==82 and system.size==2044 and not n.loads
    frequency=record['frequency_hz'];omega=2*np.pi*frequency
    z=saved['full_state'];zdot=1j*omega*z
    a=sp.load_npz(SOURCE/'assembled-6.7/A.npz');m=sp.load_npz(SOURCE/'assembled-6.7/M.npz')
    maps=np.load(SOURCE/'assembled-6.7/maps.npz')
    solved,checks=harmonic_solve(a,m,maps['B'][:,0],omega)
    np.testing.assert_allclose(z,solved,atol=2e-12,rtol=2e-12)
    forcing,_=HarmonicInput(system,'control.3',0).at_frequency(omega)
    engine_nodes=[n.node(*row[2:4]) for row in n.engines]
    sensor_nodes=[n.node(*row[1:3]) for row in n.model.records.get('sensor',[])]
    gamma=saved['gamma'];response=saved['gamma_response'];rate=1j*omega*response
    keys=[f'beam{mesh.beam.index}' for mesh in n.meshes]+['points_shoulders_engines']
    calls=0;closure=0.;coarse_probes={}

    def sample(part=None,amplitude=0.):
        nonlocal calls,closure
        if part is None:
            state,_,options=system.physical_state(zero,zero,None)
            circulation=gamma;circulation_rate=np.zeros_like(gamma)
        else:
            component=(np.real,np.imag)[part]
            state,_,options=system.physical_state(amplitude*component(z),amplitude*component(zdot),forcing(part,amplitude))
            circulation=gamma+amplitude*component(response)
            circulation_rate=amplitude*component(rate)
        coarse=n.deformed_meshes(state.r,state.Q,n.geometry(state.r,state.Q))
        fine,motion=refined_mesh_motion(n,state,options,args.factor)
        condition,_,_=n.operating.apply(state.x[n.operating_start:],
            condition_override=options['condition_override'],motion_override=options['motion_override'])
        point_positions=n.point_positions(state.r,state.Q)
        engine_positions=[state.r[j]+state.Q[j]@(row[4:7]-n.rj[j]) for row,j in zip(n.engines,engine_nodes)]
        sensor_positions=[state.r[j]+state.Q[j]@(row[3:6]-n.rj[j]) for row,j in zip(n.model.records.get('sensor',[]),sensor_nodes)]
        aero=evaluate_aerodynamics(n.model,condition,fine,circulation,point_positions,
            engine_positions,state.Q[engine_nodes],local_motion=motion,
            circulation_rate=circulation_rate,sensor_positions=sensor_positions)
        calls+=1
        values=[];wrenches=[]

        def add(force,moment):
            global_force=force.sum(axis=0)
            global_moment=(moment+np.cross(state.r-n.model.reference[1],force)).sum(axis=0)
            value=np.zeros(system.size)
            value[6*n.ne:6*n.ne+3*n.nn]=(force/n.F).ravel()
            value[6*n.ne+3*n.nn:6*n.ne+6*n.nn]=(moment/(n.F*n.L)).ravel()
            value[n.operating_start:n.size]=np.r_[global_force/n.F,global_moment/(n.F*n.L)]
            values.append(value);wrenches.append(np.r_[global_force,global_moment])

        for parent,child in zip(coarse,fine):
            strips=[s for s in aero['strips'] if s['beam']==parent.beam.index]
            force=np.array([s['force'] for s in strips]);moment=np.array([s['moment'] for s in strips])
            count=len(parent.tm);q=args.factor if parent.beam.lifting else 1
            assert len(force)==count*q
            # Sum each child's wrench about its parent's aerodynamic receiver.
            # The source endpoint transfer then preserves the original section
            # force/moment convention and every global moment reference.
            f=force.reshape(count,q,3).sum(axis=1)
            arm=child.rm.reshape(count,q,3)-parent.rm[:,None,:]
            c=(moment.reshape(count,q,3)+np.cross(arm,force.reshape(count,q,3))).sum(axis=1)
            nf=np.zeros_like(state.r);nm=np.zeros_like(state.r)
            for ids,ff,mm in n.steady_lifting_wrenches(parent,f,c):
                np.add.at(nf,ids,ff);np.add.at(nm,ids,mm)
            add(nf,nm)
            expected=np.r_[force.sum(axis=0),(moment+np.cross(child.rm-n.model.reference[1],force)).sum(axis=0)]
            np.testing.assert_allclose(wrenches[-1],expected,atol=2e-10,rtol=2e-11)
            closure=max(closure,float(max(abs(wrenches[-1]-expected))))
        nf=np.zeros_like(state.r);nm=np.zeros_like(state.r)

        def point(node,position,force,moment):
            nf[node]+=force;nm[node]+=moment+np.cross(np.array(position)-state.r[node],force)

        for row,position,force in zip(n.weights,point_positions,aero['point_forces']):
            point(n.node(*row[:2]),position,np.array(force),np.zeros(3))
        for entry in aero['body_shoulders']:
            point(n.node(entry['beam'],entry['t']),entry['position'],np.array(entry['force']),np.zeros(3))
        for entry in aero['engines']:
            point(n.node(entry['beam'],entry['t']),entry['position'],np.array(entry['force']),np.array(entry['moment']))
        add(nf,nm)
        values=np.column_stack(values);wrenches=np.column_stack(wrenches)
        expected=np.r_[aero['force'],aero['moment']]
        np.testing.assert_allclose(wrenches.sum(axis=1),expected,atol=2e-10,rtol=2e-11)
        closure=max(closure,float(max(abs(wrenches.sum(axis=1)-expected))))
        if args.factor==1 and part is not None and part not in coarse_probes:
            x=state.x.copy();x[n.gamma_start:n.operating_start]=circulation/n.gamma_scale
            _,data=n.residual(x,detail=True,**dict(options,circulation_rate=circulation_rate))
            reference,_,_=groups(system,data)
            expected=sum(v for k,v in reference.items() if k!='real_mass_gravity_applied' and not k.endswith(':stall'))
            np.testing.assert_allclose(values.sum(axis=1),expected,atol=2e-12,rtol=2e-11)
            coarse_probes[part]=float(max(abs(values.sum(axis=1)-expected)))
        return values,wrenches,aero

    base_values,base_wrenches,base=sample()
    base_residual=float(max(abs(np.array(base['circulation_residual']))))
    assert base_residual<1e-10,base_residual
    stencils=[]
    for width in (1e-3,5e-4):
        value=np.zeros_like(base_values,dtype=complex);wrench=np.zeros_like(base_wrenches,dtype=complex)
        for part in (0,1):
            for offset,weight in ((-2,1),(-1,-8),(1,8),(2,-1)):
                v,w,_=sample(part,width*offset)
                coefficient=(1 if part==0 else 1j)*weight/(12*width)
                value+=coefficient*v;wrench+=coefficient*w
        stencils.append((value,wrench))
    loads,wrenches=stencils[-1]
    load_error=float(np.max(abs(loads-stencils[0][0])))
    wrench_error=float(np.max(abs(wrenches-stencils[0][1])))
    assert load_error<2e-8 and wrench_error<2e-6,(load_error,wrench_error)
    reconstructed=np.vstack((wrenches[:,:-1].T,wrenches.sum(axis=1)))
    np.testing.assert_allclose(reconstructed,saved['loads'],atol=2e-7,rtol=2e-7)
    replay_error=float(np.max(abs(reconstructed-saved['loads'])))
    prior_error=None
    if args.factor==1:
        previous=accepted(PRIOR);arrays=np.load(PRIOR/'arrays.npz')
        names=[row['component'] for row in previous['components']]
        expected=np.column_stack([sum(arrays['component_residuals'][:,i] for i,name in enumerate(names)
            if (name==key or name.startswith(key+':')) and not name.endswith(':stall')) for key in keys])
        np.testing.assert_allclose(loads,expected,atol=2e-8,rtol=2e-7)
        prior_error=float(np.max(abs(loads-expected)))
    np.savez_compressed(folder/'arrays.npz',loads=loads,wrenches=wrenches,state=z,
        base_loads=base_values,base_wrenches=base_wrenches,stencil_difference=loads-stencils[0][0])
    return dict(factor=args.factor,panels=record['panels'],frequency_hz=frequency,groups=keys,
        aero_evaluations=calls,base_circulation_residual=base_residual,
        transfer_wrench_closure=closure,coarse_full_network_probes=coarse_probes,
        load_stencil_error=load_error,wrench_stencil_error=wrench_error,
        previous_refinement_wrench_error=replay_error,coarse_previous_component_residual_error=prior_error,
        full_harmonic_checks=checks,
        qualification='Complete aerodynamic load derivative at prescribed coarse motion with independently solved fine circulation. No structural refinement or retrim.')


def project(folder,args):
    import numpy as np
    import scipy.sparse as sp
    from openswing.frequency_response import harmonic_solve
    records=[accepted(STUDY/tag) for tag in CAPTURES]
    arrays=[np.load(STUDY/tag/'arrays.npz') for tag in CAPTURES]
    reference=records[0];frequency=reference['frequency_hz'];omega=2*np.pi*frequency
    assert all(r['frequency_hz']==frequency and r['groups']==reference['groups'] for r in records)
    z=arrays[0]['state']
    for saved in arrays[1:]:np.testing.assert_array_equal(saved['state'],z)
    a=sp.load_npz(SOURCE/'assembled-6.7/A.npz');m=sp.load_npz(SOURCE/'assembled-6.7/M.npz')
    maps=np.load(SOURCE/'assembled-6.7/maps.npz');baseline=maps['C']@z
    differences=np.concatenate([saved['loads']-arrays[0]['loads'] for saved in arrays[1:]],axis=1)
    assert np.all(differences[1296:1378]==0), 'Fine circulation was eliminated, not mapped to coarse Gamma rows.'
    correction,checks=harmonic_solve(a,m,differences,omega)
    output_changes=maps['C']@correction
    count=len(reference['groups']);rows=[]
    for i,record in enumerate(records[1:]):
        component=output_changes[:,i*count:(i+1)*count];change=component.sum(axis=1)
        combined=baseline+change
        rows.append(dict(panels=record['panels'],factor=record['factor'],
            change_real=change.real.tolist(),change_imag=change.imag.tolist(),
            relative_complex_change_percent=(100*abs(change)/abs(baseline)).tolist(),
            magnitude_first_variation_percent=(100*np.real(change/baseline)).tolist(),
            phase_first_variation_deg=np.rad2deg(np.imag(change/baseline)).tolist(),
            baseline_plus_first_variation_magnitude=abs(combined).tolist(),
            component_output_real=component.real.tolist(),component_output_imag=component.imag.tolist(),
            component_yaw_magnitude_first_variation_percent=(100*np.real(component[0]/baseline[0])).tolist(),
            base_wrench_change=(arrays[i+1]['base_wrenches'].sum(axis=1)-arrays[0]['base_wrenches'].sum(axis=1)).tolist()))
        print('panels',record['panels'],'first_variation_percent',rows[-1]['magnitude_first_variation_percent'],
            'baseline_plus_variation',abs(combined).tolist(),flush=True)
    # A separate total right-hand side checks component grouping and linearity.
    total=np.column_stack([differences[:,i*count:(i+1)*count].sum(axis=1) for i in range(2)])
    independent,total_checks=harmonic_solve(a,m,total,omega)
    summed=np.column_stack([correction[:,i*count:(i+1)*count].sum(axis=1) for i in range(2)])
    np.testing.assert_allclose(independent,summed,atol=2e-11,rtol=2e-9)
    np.savez_compressed(folder/'arrays.npz',load_differences=differences,correction_states=correction,
        output_changes=output_changes,baseline=baseline,total_correction_states=independent)
    return dict(frequency_hz=frequency,channels=['yaw_rate','roll_rate','sideslip','bank'],groups=reference['groups'],
        baseline_real=baseline.real.tolist(),baseline_imag=baseline.imag.tolist(),baseline_magnitude=abs(baseline).tolist(),
        comparisons=rows,component_solve_checks=checks,total_solve_checks=total_checks,
        total_vs_component_state_error=float(np.max(abs(independent-summed))),
        qualifications=[
            'First variation at lambda=0 for an affine interpolation between coarse and refined circulation-eliminated aerodynamic load operators, at a fixed structural base.',
            'The fine aerodynamic mean load differs; an affine offset preserves the original equilibrium. No physical preload, parameter change or production correction is proposed.',
            'The full original descriptor inverse retains structural/free-frame feedback. Higher powers of the changed aerodynamic feedback and structural retrim are not included.',
            'The displayed baseline plus first variation is a diagnostic extrapolation, not a fully recoupled fine-grid Bode solution or native ASWING pass.'])


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage',choices=['capture','project'],default='capture')
    parser.add_argument('--factor',type=int,choices=[1,2,4],default=1)
    parser.add_argument('--tag',required=True);args=parser.parse_args()
    STUDY.mkdir(exist_ok=True);folder=STUDY/args.tag;folder.mkdir(exist_ok=False)
    (folder/'runner.py').write_bytes(Path(__file__).read_bytes())
    inputs=[Path(__file__),ROOT/'scripts/check_daedalus_aero_resolution.py',ROOT/'scripts/check_daedalus_load_sensitivity.py',
        ROOT/'scripts/check_daedalus_wing_paper.py',ROOT/'scripts/check_daedalus_source_operator.py',
        ROOT/'examples/dae.asw',ROOT/'examples/dae-cruise-physical-mesh-project.json',SOURCE/'trim-6.7-1/state.json',
        ROOT/'reference/aswing-authoritative-20261108/drela-aswing-steady.pdf',
        ROOT/'reference/aswing-authoritative-20261108/drela-aswing-unsteady.pdf',ROOT/'docs/validation/aswing-authoritative-sources.json']
    inputs += [SOURCE/'assembled-6.7'/name for name in ('A.npz','M.npz','maps.npz','plan.json','result.json','terminal.json')]
    if args.stage=='capture':
        original=RESOLUTION/ACCEPTED[[1,2,4].index(args.factor)]
        inputs += [original/name for name in ('arrays.npz','result.json','plan.json','terminal.json','runner.py')]
        if args.factor==1:inputs += [PRIOR/name for name in ('arrays.npz','result.json','plan.json','terminal.json','runner.py')]
    else:
        inputs += [STUDY/tag/name for tag in CAPTURES for name in ('arrays.npz','result.json','plan.json','terminal.json','runner.py')]
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
    terminal=dict(observed_utc=utc(),returncode=os.waitstatus_to_exitcode(status),process_reaped=True,timed_out=timed_out,
        cpu_seconds=usage.ru_utime+usage.ru_stime,wall_seconds=time.monotonic()-started,peak_rss_kib=usage.ru_maxrss,
        limits=LIMITS,inputs_unchanged=all(pin(p)==h for p,h in pins.items()))
    write(folder/'terminal.json',terminal);print(json.dumps(terminal),flush=True)
    raise SystemExit(terminal['returncode'] or (0 if terminal['inputs_unchanged'] else 1))


if __name__=='__main__':main()
