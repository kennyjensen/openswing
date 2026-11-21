"""Small serial independent replay of current Daedalus wing real inertia."""
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

STUDY=ROOT/'artifacts/daedalus-wing-inertia-20261113'
SAVED=ROOT/'artifacts/daedalus-load-sensitivity-20261113'
MOUNT=ROOT/'artifacts/daedalus-wing-mount-20261113'
CASES={'slow':(.2,'slow-animation'),'dip':(1.15737773741517,'reference-dip')}


def analyze(folder,args):
    import numpy as np
    from check_daedalus_wing_paper import dynamic
    from check_daedalus_load_sensitivity import groups
    from wing_inertia_reference import evaluate,PARTS
    system=dynamic();n=system.network;frequency,tag=CASES[args.case];omega=2*np.pi*frequency
    previous=np.load(SAVED/tag/'arrays.npz');z=previous['state']
    names=[entry['component'] for entry in read(SAVED/tag/'result.json')['components']]
    index=names.index('real_mass_gravity_applied');zero=np.zeros(system.size)
    state,_,options=system.physical_state(zero,zero,None)
    residual,base=n.residual(state.x,detail=True,**options)
    assert max(abs(residual))<1e-9
    assert max(abs(system.Omega0))<1e-12 and max(abs(system.Udot0))<1e-10
    assert max(abs(system.Omegadot0))<1e-12
    assert not n.loads and not n.gravity_override
    assert all(int(row[0])!=1 for row in n.weights)
    mesh,=[m for m in n.meshes if m.beam.index==1];beam=mesh.beam;sl=n.beam_elements[1]
    assert not np.any(n.offa[sl]) and not np.any(n.offb[sl])
    samples={key:[] for key in ('a','b','node','frames','ds','weight_density','cg_local',
                                'icc_weight_density','inn_weight_density')}
    # Sample the input property tables directly; do not read the production
    # source_mass_samples/source_rotary_samples or call inertial_wrench.
    for prefix in ('','D'):
        for t,side,node,frame in [(mesh.t0,'right',n.a[sl],system.Q0[n.a[sl]]@n.R0a[sl]),
                                  (mesh.t1,'left',n.b[sl],system.Q0[n.b[sl]]@n.R0b[sl])]:
            values=dict(a=n.a[sl],b=n.b[sl],node=node,frames=frame,ds=mesh.length,
                weight_density=beam.value(prefix+'mg',t,side=side),
                cg_local=np.column_stack([beam.value(prefix+'Ccg',t,side=side),np.zeros(len(t)),
                                          beam.value(prefix+'Ncg',t,side=side)]),
                icc_weight_density=beam.value(prefix+'mgcc',t,side=side),
                inn_weight_density=beam.value(prefix+'mgnn',t,side=side))
            for key,value in values.items():samples[key].append(value)
    fixture={key:np.concatenate(value) for key,value in samples.items()}
    root=n.node(1,0.);boom=n.node(4,0.);_,nodes=n.station_nodes[1]
    fixture.update(node_positions=system.r0,gravity=base['gravity'],base_velocity=system.U0,
                   g_constant=np.array(n.model.constants[0]),moment_reference=system.r0[boom])
    dr=n.L*z[:6*n.nn].reshape(n.nn,6)[:,:3];theta=z[:6*n.nn].reshape(n.nn,6)[:,3:]
    u,w=z[system.velocity_start:system.frame_start].reshape(2,n.nn,3)
    u=system.V*u;w=system.W*w
    U=system.V*z[system.frame_start:system.frame_start+3]
    W=system.W*z[system.frame_start+3:system.frame_start+6]
    kinematic_errors=dict(translation=float(np.max(abs(1j*omega*dr-u))),
                          rotation=float(np.max(abs(1j*omega*theta-w))))
    assert max(kinematic_errors.values())<2e-9,kinematic_errors
    actual=evaluate(fixture,dr,theta,u,w,U,W,omega,dr[boom])
    fr=(6*n.ne+3*nodes[:,None]+np.arange(3)).ravel()
    mr=(6*n.ne+3*n.nn+3*nodes[:,None]+np.arange(3)).ravel()
    expected_force=n.F*previous['component_residuals'][fr,index].reshape(-1,3)
    expected_moment=n.F*n.L*previous['component_residuals'][mr,index].reshape(-1,3)
    base_loads,_,_=groups(system,base);v0=base_loads['real_mass_gravity_applied']
    f0=n.F*v0[fr].reshape(-1,3);m0=n.F*n.L*v0[mr].reshape(-1,3)
    expected_wrench=np.r_[expected_force.sum(axis=0),(expected_moment+
        np.cross(system.r0[nodes]-system.r0[boom],expected_force)+np.cross(dr[nodes]-dr[boom],f0)).sum(axis=0)]
    errors=dict(base_force=float(np.max(abs(actual['base_force'][nodes]-f0))),
        base_moment=float(np.max(abs(actual['base_moment'][nodes]-m0))),
        nodal_force=float(np.max(abs(actual['nodal_force'].sum(axis=0)[nodes]-expected_force))),
        nodal_moment=float(np.max(abs(actual['nodal_moment'].sum(axis=0)[nodes]-expected_moment))),
        moving_reference_wrench=float(np.max(abs(actual['wrenches'].sum(axis=0)-expected_wrench))))
    assert max(errors.values())<2e-6,errors
    # Verify the independent gravity orientation and origin acceleration against
    # the actual state mapping, without using those values in the reconstruction.
    gravity_errors=[];acceleration_errors=[]
    for part in (np.real,np.imag):
        values=[]
        for sign in (-1,1):
            h=sign*1e-4
            state,_,options=system.physical_state(h*part(z),h*part(1j*omega*z),None)
            _,motion,_=n.operating.apply(state.x[n.operating_start:],
                condition_override=options['condition_override'],motion_override=options['motion_override'])
            values.append((options['gravity_override'],motion.at(np.zeros(3),n.model.reference[2])))
        gravity_errors.append(float(max(abs((values[1][0]-values[0][0])/2e-4-part(actual['gravity_derivative'])))))
        acceleration_errors.append(float(max(abs((values[1][1]-values[0][1])/2e-4-part(1j*omega*U+np.cross(W,system.U0))))))
    assert max(gravity_errors+acceleration_errors)<2e-8
    # Partition the supplied elastic motion into rigid root translation/rotation
    # and deformation relative to it. The moving reference is a separate term.
    zz=np.zeros_like(dr);z3=np.zeros(3,complex)
    root_dr=np.broadcast_to(dr[root],dr.shape);root_u=np.broadcast_to(u[root],u.shape)
    rigid_theta=np.broadcast_to(theta[root],theta.shape);rigid_w=np.broadcast_to(w[root],w.shape)
    rigid_dr=np.cross(theta[root],system.r0-system.r0[root]);rigid_u=np.cross(w[root],system.r0-system.r0[root])
    motions=[('aircraft_frame',zz,zz,zz,zz,U,W,z3),
        ('wing_root_translation',root_dr,zz,root_u,zz,z3,z3,z3),
        ('wing_root_rotation',rigid_dr,rigid_theta,rigid_u,rigid_w,z3,z3,z3),
        ('wing_relative_deformation',dr-root_dr-rigid_dr,theta-rigid_theta,u-root_u-rigid_u,w-rigid_w,z3,z3,z3),
        ('moving_boom_reference',zz,zz,zz,zz,z3,z3,dr[boom])]
    motion_wrenches=np.array([evaluate(fixture,d,t,v,wv,fv,fw,omega,ref)['wrenches']
                             for _,d,t,v,wv,fv,fw,ref in motions])
    superposition_error=float(np.max(abs(motion_wrenches.sum(axis=0)-actual['wrenches'])))
    assert superposition_error<2e-10
    np.savez_compressed(folder/'fixture.npz',**fixture)
    np.savez_compressed(folder/'arrays.npz',state=z,displacement=dr,rotation=theta,velocity=u,rates=w,
        frame_velocity=U,frame_rates=W,reference_displacement=dr[boom],nodes=nodes,
        expected_force=expected_force,expected_moment=expected_moment,expected_wrench=expected_wrench,
        reference_force=actual['nodal_force'],reference_moment=actual['nodal_moment'],
        wrenches=actual['wrenches'],motion_wrenches=motion_wrenches,
        base_force=actual['base_force'],base_moment=actual['base_moment'])
    def record(value):return dict(real=value.real.tolist(),imag=value.imag.tolist())
    result=dict(frequency_hz=frequency,terms=PARTS,motions=[row[0] for row in motions],
        comparison_errors=errors,kinematic_errors=kinematic_errors,gravity_mapping_errors=gravity_errors,
        origin_acceleration_errors=acceleration_errors,superposition_error=superposition_error,
        wing_weight_lb=float(actual['mass'].sum()*n.model.constants[0]),
        wrenches=record(actual['wrenches']),motion_wrenches=record(motion_wrenches.sum(axis=1)),
        expected_wrench=record(expected_wrench),
        qualification='Independent stationary-base real-inertia/gravity equation replay. Input sampling, supplied loaded geometry and harmonic state, endpoint product averaging and symmetric transfer are declared inputs/conventions. This does not validate historical ASWING quadrature, the complete Bode solution or unknown reference settings.')
    print(json.dumps(result),flush=True);return result


def report(folder,args):
    import csv
    import re
    import numpy as np
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    results=[read(STUDY/case/'result.json') for case in CASES]
    arrays=[np.load(STUDY/case/'arrays.npz') for case in CASES]
    palette=re.findall(r"'([^']+)'",(ROOT/'web/plot-colors.js').read_text().split('export const plotColors = Object.freeze([')[1].split(']);')[0])
    plt.rcParams.update({'figure.facecolor':'#111827','axes.facecolor':'#111827','text.color':'white',
        'axes.labelcolor':'white','xtick.color':'white','ytick.color':'white','axes.edgecolor':'#9ca3af','font.size':9})
    fig,axes=plt.subplots(1,2,figsize=(12,6),layout='constrained')
    term_labels=['Frame velocity derivative','Frame convective acceleration','Frame angular acceleration',
        'Elastic translation acceleration','Elastic rotation acceleration','Section rotary inertia',
        'Finite-segment rotary inertia','Gravity orientation','Gravity CG-arm motion','Gravity reference-arm motion']
    for ax,result,data in zip(axes,results,arrays):
        np.testing.assert_allclose(data['wrenches'].sum(axis=0),data['expected_wrench'],atol=2e-6,rtol=0)
        np.testing.assert_allclose(data['motion_wrenches'].sum(axis=0),data['wrenches'],atol=2e-10,rtol=0)
        values=data['wrenches'][:,5];y=np.arange(len(values))
        ax.barh(y-.18,values.real,.36,color=palette[0],label='Real')
        ax.barh(y+.18,values.imag,.36,color=palette[1],label='Imaginary')
        ax.set_yticks(y,term_labels);ax.invert_yaxis();ax.axvline(0,color='white',alpha=.5,lw=.7)
        ax.set_title(f"{result['frequency_hz']:.6g} Hz");ax.set_xlabel('Wing body-z moment [lb ft per native F3]')
        ax.grid(axis='x',alpha=.15);ax.set_axisbelow(True);ax.legend(facecolor='#111827',labelcolor='white')
    fig.suptitle('Daedalus wing real inertia and gravity\nIndependent replay about the moving boom attachment; supplied coupled response')
    fig.savefig(folder/'wing-inertia.png',dpi=150);fig.savefig(folder/'wing-inertia.svg');plt.close(fig)
    with (folder/'wrenches.csv').open('x') as stream:
        writer=csv.writer(stream);writer.writerow(['frequency_hz','decomposition','term','axis','real','imag','unit_per_F3'])
        for result,data in zip(results,arrays):
            for decomposition,names,values in [('equation',result['terms'],data['wrenches']),
                                               ('motion',result['motions'],data['motion_wrenches'].sum(axis=1))]:
                for name,value in zip(names,values):
                    for j,axis in enumerate(['Fx','Fy','Fz','Mx','My','Mz']):
                        writer.writerow([result['frequency_hz'],decomposition,name,axis,value[j].real,value[j].imag,'lb' if j<3 else 'lb ft'])
    return dict(cases=results,qualification=results[0]['qualification'])


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('stage',choices=['analyze','report'])
    parser.add_argument('--case',choices=list(CASES));parser.add_argument('--tag',required=True);args=parser.parse_args()
    if args.stage=='analyze' and args.case is None:parser.error('--case is required')
    STUDY.mkdir(exist_ok=True);folder=STUDY/args.tag;folder.mkdir(exist_ok=False)
    (folder/'runner.py').write_bytes(Path(__file__).read_bytes())
    inputs=[Path(__file__),ROOT/'scripts/wing_inertia_reference.py',ROOT/'scripts/check_daedalus_wing_paper.py',
        ROOT/'scripts/check_daedalus_source_operator.py',ROOT/'scripts/check_daedalus_load_sensitivity.py',
        ROOT/'examples/dae.asw',ROOT/'examples/dae-cruise-physical-mesh-project.json',SOURCE/'trim-6.7-1/state.json',
        ROOT/'docs/validation/aswing-authoritative-sources.json',ROOT/'docs/validation/ISAE_STATUS.md',
        ROOT/'reference/aswing-authoritative-20261108/drela-aswing-unsteady.pdf',
        ROOT/'reference/aswing-authoritative-20261108/drela-aswing-steady.pdf']
    if args.stage=='analyze':inputs += [SAVED/CASES[args.case][1]/name for name in ('arrays.npz','result.json','terminal.json')]
    else:inputs += [STUDY/case/name for case in CASES for name in ('arrays.npz','result.json','terminal.json')]+[ROOT/'web/plot-colors.js']
    pins={str(p):pin(p) for p in inputs+list((ROOT/'openswing').glob('*.py'))}
    write(folder/'plan.json',dict(observed_utc=utc(),arguments=vars(args),limits=LIMITS,inputs_sha256=pins,
        allocator_environment={key:os.environ.get(key) for key in ('MALLOC_MMAP_THRESHOLD_','MALLOC_TRIM_THRESHOLD_')}))
    started=time.monotonic();sys.stdout.flush();pid=os.fork()
    if pid==0:
        code=0
        for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[key]='1'
        resource.setrlimit(resource.RLIMIT_AS,(LIMITS['address_space_bytes'],)*2);resource.setrlimit(resource.RLIMIT_CPU,(LIMITS['cpu_seconds'],)*2)
        sys.path.insert(0,str(ROOT))
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
