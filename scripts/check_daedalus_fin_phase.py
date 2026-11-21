"""Bounded current-state apparent-load replay and saved motion/physics split."""
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

STUDY=ROOT/'artifacts/daedalus-fin-phase-20261113'
MOTION=ROOT/'artifacts/daedalus-motion-loads-20261113'
GROUPS=['control','frame','fin_translation','fin_rotation','fin_deformation','beam1','beam2','beam4','beam5']
FREQUENCY=1.15737773741517


def analyze(folder,args):
    import numpy as np
    from check_daedalus_wing_paper import dynamic
    from openswing.local_rate_tangent import RateFields
    from fin_apparent_reference import evaluate,PARTS
    system=dynamic();n=system.network;zero=np.zeros(system.size);omega=2*np.pi*FREQUENCY
    state,_,options=system.physical_state(zero,zero,None)
    # The base rate is zero, so ordinary evaluation may skip the axis induced
    # field. Capture its complete base value explicitly for the rate derivative.
    fields=RateFields();old=n.iteration_fields;n.iteration_fields=fields;n.aero_key=None
    try:residual,base=n.residual(state.x,detail=True,**options)
    finally:n.iteration_fields=old;n.aero_key=None
    assert max(abs(residual))<1e-9
    assert max(abs(system.Omega0))<1e-12
    for key in ('rates','acceleration','angular_acceleration'):assert max(abs(getattr(base['motion'],key)))<1e-10
    mesh,=[m for m in base['meshes'] if m.beam.index==3]
    surface_beams=[m for m in base['meshes'] if m.beam.lifting]
    start=sum(len(m.tm) for m in surface_beams[:surface_beams.index(mesh)])
    sl=n.beam_elements[3];strips=base['aero']['strips'][sl];beam=mesh.beam
    fixture=dict(a=n.a[sl],b=n.b[sl],fraction=n.fractions[3],node_frames=system.Q0,
        node_positions=system.r0,positions=mesh.rm,frames=mesh.frames,chord=beam.value('chord',mesh.tm),
        xax=beam.value('Xax',mesh.tm),length=np.array([s['length'] for s in strips]),
        density=np.array(base['aero']['atmosphere']['density']),axis_air_velocity=fields.incident['axis'][start:start+len(mesh.tm)],
        base_frame_velocity=system.U0,moment_reference=np.array(n.model.reference[1]))
    np.savez_compressed(folder/'fixture.npz',**fixture)
    states=[];expected_forces=[];expected_moments=[];expected_wrenches=[];calculated=[];aero_split=[]
    sources=GROUPS+['full'];paths={name:MOTION/(name if name!='full' else 'full-v2') for name in sources}
    for name,path in paths.items():
        saved=np.load(path/'arrays.npz');metadata=read(path/'result.json');z=saved['state'];states.append(z)
        local_velocity,local_rates=z[system.velocity_start:system.frame_start].reshape(2,n.nn,3)
        frame_velocity=system.V*z[system.frame_start:system.frame_start+3]
        frame_rates=system.W*z[system.frame_start+3:system.frame_start+6]
        result=evaluate(fixture,system.V*local_velocity,system.W*local_rates,frame_velocity,frame_rates,omega)
        index=metadata['keys'].index('beam3:apparent');load=saved['component_residuals'][:,index]
        expected_forces.append(n.F*load[6*n.ne:6*n.ne+3*n.nn].reshape(n.nn,3))
        expected_moments.append(n.F*n.L*load[6*n.ne+3*n.nn:6*(n.ne+n.nn)].reshape(n.nn,3))
        expected_wrenches.append(saved['wrenches'][:,index]);calculated.append(result)
        aero_split.append(saved['wrenches'][:,[metadata['keys'].index('beam3:'+kind) for kind in ('lift','rate_lift','profile','pitch','apparent')]])
    states=np.column_stack(states)
    actual_force=np.array([r['nodal_force'].sum(axis=0) for r in calculated]);expected_force=np.array(expected_forces)
    actual_moment=np.array([r['nodal_moment'].sum(axis=0) for r in calculated]);expected_moment=np.array(expected_moments)
    wrench_parts=np.array([r['wrench'] for r in calculated]);expected_wrench=np.array(expected_wrenches)
    errors=dict(nodal_force=float(np.max(abs(actual_force-expected_force))),nodal_moment=float(np.max(abs(actual_moment-expected_moment))),
        global_wrench=float(np.max(abs(wrench_parts.sum(axis=1)-expected_wrench))))
    assert max(errors.values())<2e-6,errors
    sum_error=float(np.max(abs(wrench_parts[:-1].sum(axis=0)-wrench_parts[-1])));assert sum_error<2e-10,sum_error
    # Independent frame kinematics: a_origin=Udot+Omega cross U, alpha=Omegadot.
    # The operating acceleration slots are NOT used in the reference above.
    frame_errors=[]
    z=states[:,-1]
    for function in (np.real,np.imag):
        d=function(z);h=1e-4;values=[]
        for sign in (-1,1):
            state,_,options=system.physical_state(sign*h*d,sign*h*function(1j*omega*z),None)
            _,motion,_=n.operating.apply(state.x[n.operating_start:],condition_override=options['condition_override'],motion_override=options['motion_override'])
            values.append(np.r_[motion.at(np.zeros(3),n.model.reference[2]),motion.angular_acceleration])
        expected=function(np.r_[1j*omega*system.V*z[system.frame_start:system.frame_start+3]+
            np.cross(system.W*z[system.frame_start+3:system.frame_start+6],system.U0),
            1j*omega*system.W*z[system.frame_start+3:system.frame_start+6]])
        frame_errors.append(float(max(abs((values[1]-values[0])/(2*h)-expected))))
    assert max(frame_errors)<2e-8,frame_errors
    np.savez_compressed(folder/'arrays.npz',states=states,expected_force=expected_force,expected_moment=expected_moment,
        expected_wrench=expected_wrench,reference_force=actual_force,reference_moment=actual_moment,
        wrench_parts=wrench_parts,aero_split=np.array(aero_split),
        local_rates=np.array([r['local_rate'] for r in calculated]),local_velocities=np.array([r['local_velocity'] for r in calculated]))
    def record(value):return dict(real=value.real.tolist(),imag=value.imag.tolist())
    result=dict(frequency_hz=FREQUENCY,groups=sources,apparent_parts=PARTS,comparison_errors=errors,
        superposition_error=sum_error,frame_acceleration_reconstruction_errors=frame_errors,
        apparent_wrench_parts=record(wrench_parts),aero_components=['lift','rate_lift','profile','pitch','apparent'],
        aerodynamic_wrenches_by_motion=record(np.array(aero_split)),
        qualification='Independent stationary-base section-rate/acceleration and Eqs43-44 replay. Loaded geometry, material values, base fluid velocity, response coordinates and the declared symmetric load transfer are inputs. This does not independently validate circulation, solve aircraft dynamics, or identify native settings.')
    print(json.dumps(dict(comparison_errors=errors,superposition_error=sum_error,frame_errors=frame_errors)),flush=True)
    return result


def report(folder,args):
    import csv
    import re
    import numpy as np
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    source=STUDY/'replay';result=read(source/'result.json');data=np.load(source/'arrays.npz')
    parts=data['wrench_parts'];loads=data['aero_split']
    np.testing.assert_allclose(parts.sum(axis=1),data['expected_wrench'],atol=2e-6,rtol=0)
    np.testing.assert_allclose(parts[:-1].sum(axis=0),parts[-1],atol=2e-10,rtol=0)
    palette=re.findall(r"'([^']+)'",(ROOT/'web/plot-colors.js').read_text().split('export const plotColors = Object.freeze([')[1].split(']);')[0])
    plt.rcParams.update({'figure.facecolor':'#111827','axes.facecolor':'#111827','text.color':'white',
        'axes.labelcolor':'white','xtick.color':'white','ytick.color':'white','axes.edgecolor':'#9ca3af','font.size':9})
    fig,axes=plt.subplots(1,2,figsize=(12,5.5),layout='constrained')
    selected=[1,2,3,4,9];labels=['Frame motion','Root translation','Root rotation','Fin deformation','Total']
    terms=[0,1,2,3,4,5];term_labels=['Rotation rate','Frame velocity derivative','Frame convective term',
        'Frame angular acceleration','Elastic translation acceleration','Elastic rotation acceleration']
    for ax,values,names,title in [(axes[0],parts[selected,:,1].sum(axis=1),labels,'Apparent side force by motion'),
                                 (axes[1],parts[-1,terms,1],term_labels,'Apparent side force by equation term')]:
        y=np.arange(len(names));ax.barh(y-.18,values.real,.36,color=palette[0],label='Real')
        ax.barh(y+.18,values.imag,.36,color=palette[1],label='Imaginary')
        ax.set_yticks(y,names);ax.invert_yaxis();ax.axvline(0,color='white',alpha=.5,lw=.7)
        ax.set_xlabel('Fin body-y force [lb per native F3]');ax.set_title(title)
        ax.grid(axis='x',alpha=.15);ax.set_axisbelow(True);ax.legend(facecolor='#111827',labelcolor='white')
    fig.suptitle('Daedalus fin loads at 1.157378 Hz\nIndependent apparent-load replay; supplied coupled motion and mean airflow')
    fig.savefig(folder/'fin-phase.png',dpi=150);fig.savefig(folder/'fin-phase.svg');plt.close(fig)
    with (folder/'loads.csv').open('x') as stream:
        writer=csv.writer(stream);writer.writerow(['motion','decomposition','term','component','real','imag','unit_per_F3'])
        for g,name in enumerate(result['groups']):
            for decomposition,names,values in [('apparent_equation',result['apparent_parts'],parts[g]),
                                              ('aerodynamic_load',result['aero_components'],loads[g].T)]:
                for term,value in zip(names,values):
                    for j,axis in enumerate(['Fx','Fy','Fz','Mx','My','Mz']):
                        writer.writerow([name,decomposition,term,axis,value[j].real,value[j].imag,'lb' if j<3 else 'lb ft'])
    return dict(frequency_hz=result['frequency_hz'],comparison_errors=result['comparison_errors'],
        frame_acceleration_reconstruction_errors=result['frame_acceleration_reconstruction_errors'],
        superposition_error=result['superposition_error'],source='replay',qualification=result['qualification'])


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('stage',choices=['analyze','report'])
    parser.add_argument('--tag',required=True);args=parser.parse_args()
    STUDY.mkdir(exist_ok=True);folder=STUDY/args.tag;folder.mkdir(exist_ok=False)
    (folder/'runner.py').write_bytes(Path(__file__).read_bytes())
    inputs=[Path(__file__),ROOT/'scripts/fin_apparent_reference.py',ROOT/'scripts/check_daedalus_wing_paper.py',
        ROOT/'scripts/check_daedalus_source_operator.py',ROOT/'scripts/check_daedalus_load_sensitivity.py',
        ROOT/'examples/dae.asw',ROOT/'examples/dae-cruise-physical-mesh-project.json',SOURCE/'trim-6.7-1/state.json',
        ROOT/'docs/validation/aswing-authoritative-sources.json',ROOT/'reference/aswing-authoritative-20261108/drela-aswing-unsteady.pdf',
        ROOT/'reference/daedalus-provenance-20261113/receipt.json']
    inputs += [MOTION/tag/name for tag in GROUPS+['full-v2'] for name in ('arrays.npz','result.json','terminal.json')]
    if args.stage=='report':inputs += [STUDY/'replay'/name for name in ('arrays.npz','result.json','terminal.json')]+[ROOT/'web/plot-colors.js']
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
