"""Lifting-line refinement at fixed loaded structural fields and motion.

Subdivide each original lifting interval in whole-beam Glauert angle. Preserve
the original structural displacement/rotation/motion interpolants and its
integrated interval measure. Solve only steady and harmonic circulation;
this is not a retrimmed or refined full-aircraft Bode prediction.
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

STUDY=ROOT/'artifacts/daedalus-aero-resolution-20261113'
ACCEPTED=['dip-1-v4','dip-2-v2','dip-4']


def refined_mesh_motion(n,state,options,factor):
    """Sample unchanged structural fields on a refined lifting-line grid."""
    import numpy as np
    from openswing.geometry import PanelMesh,surface_frame
    from openswing.local_motion import NetworkMotion,LocalMotion
    original=n.deformed_meshes(state.r,state.Q,n.geometry(state.r,state.Q))
    motion=NetworkMotion(n,state.r,state.Q,*options['elastic_motion'])
    if factor==1:return original,motion
    meshes=[];surface_fields=[]
    for old,jig in zip(original,n.meshes):
        beam=old.beam
        if not beam.lifting:meshes.append(old);continue
        count=len(old.tm);q=factor
        theta=jig.theta[:-1,None]+(jig.theta[1:]-jig.theta[:-1])[:,None]*np.arange(q+1)[None,:]/q
        total=float(sum(jig.length));s=total*(1+np.cos(theta))/2
        origin=np.r_[0.,np.cumsum(jig.length)[:-1]]
        fraction=(s-origin[:,None])/jig.length[:,None]
        fraction[:,0]=0.;fraction[:,-1]=1.
        sample_s=total*(1+np.cos((theta[:,:-1]+theta[:,1:])/2))/2
        midpoint=(sample_s-origin[:,None])/jig.length[:,None]
        ts=jig.t0[:,None]+fraction*(jig.t1-jig.t0)[:,None]
        tm=jig.t0[:,None]+midpoint*(jig.t1-jig.t0)[:,None]
        # This adapter is deliberately restricted to the literal file's
        # straight, linearly parameterized undeformed beam segments.
        np.testing.assert_allclose(beam.position(ts.ravel()).reshape(count,q+1,3),
            jig.r0[:,None,:]+fraction[:,:,None]*(jig.r1-jig.r0)[:,None,:],atol=2e-10,rtol=2e-12)
        edge,rotation,_=motion.sample(beam.index,fraction)
        field,midrotation,_=motion.sample(beam.index,midpoint)
        frames=midrotation.reshape(-1,3,3)@surface_frame(beam,tm.ravel())
        endframes=rotation.reshape(-1,3,3)@surface_frame(beam,ts.ravel())
        endframes=endframes.reshape(count,q+1,3,3)
        length=old.length[:,None]*np.diff(fraction,axis=1)
        np.testing.assert_allclose(length.sum(axis=1),old.length,atol=1e-13,rtol=1e-13)
        meshes.append(PanelMesh(beam,ts[:,:-1].ravel(),ts[:,1:].ravel(),tm.ravel(),
            edge.origin[:,:-1].reshape(-1,3),edge.origin[:,1:].reshape(-1,3),field.origin.reshape(-1,3),
            frames,length.ravel(),endframes[:,:-1].reshape(-1,3,3),endframes[:,1:].reshape(-1,3,3),
            ((ts[:,:-1]+ts[:,1:])/2).ravel(),np.r_[theta[:,:-1].ravel(),theta[-1,-1]],old.mesh_recipe))
        surface_fields.append(LocalMotion(*(getattr(field,key).reshape(-1,3) for key in LocalMotion.__dataclass_fields__)))
    # Other receivers remain on the original structural discretization.
    refined_motion=SimpleNamespace(surface=lambda:LocalMotion.concatenate(surface_fields),
        point=motion.point,body=motion.body,station=motion.station)
    return meshes,refined_motion


def analyze(folder,args):
    import numpy as np
    import scipy.sparse as sp
    from check_daedalus_wing_paper import dynamic
    from openswing.aero import evaluate_aerodynamics
    from openswing.geometry import PanelMesh,surface_frame
    from openswing.local_motion import NetworkMotion,LocalMotion
    from openswing.structured_static import IterationFields
    from openswing.circulation_tangent import FlowDerivative,surface_derivatives
    from openswing.frequency_response import harmonic_solve,HarmonicInput
    system=dynamic();n=system.network;zero=np.zeros(system.size)
    omega=2*np.pi*args.frequency
    matrix=SOURCE/'assembled-6.7';a=sp.load_npz(matrix/'A.npz');m=sp.load_npz(matrix/'M.npz')
    maps=np.load(matrix/'maps.npz')
    z,harmonic_checks=harmonic_solve(a,m,maps['B'][:,0],omega);zdot=1j*omega*z
    forcing,_=HarmonicInput(system,'control.3',0).at_frequency(omega)
    initial,_,base_options=system.physical_state(zero,zero,None)
    residual,base_data=n.residual(initial.x,detail=True,**base_options)
    assert max(abs(residual))<1e-9
    engine_nodes=[n.node(*row[2:4]) for row in n.engines]
    sensor_nodes=[n.node(*row[1:3]) for row in n.model.records.get('sensor',[])]
    calls=0;coarse_probes={}

    def mesh_motion(state,options):
        return refined_mesh_motion(n,state,options,args.factor)

    def evaluate(gamma,gamma_dot=None,*,part=None,amplitude=0.,capture=False):
        nonlocal calls
        if part is None:state,_,options=system.physical_state(zero,zero,None)
        else:
            component=(np.real,np.imag)[part]
            state,_,options=system.physical_state(amplitude*component(z),amplitude*component(zdot),forcing(part,amplitude))
        meshes,motion=mesh_motion(state,options)
        condition,_,_=n.operating.apply(state.x[n.operating_start:],
            condition_override=options['condition_override'],motion_override=options['motion_override'])
        fields=IterationFields() if capture else None
        if fields is not None:fields.capture_circulation=True
        engine_positions=[state.r[j]+state.Q[j]@(row[4:7]-n.rj[j]) for row,j in zip(n.engines,engine_nodes)]
        sensor_positions=[state.r[j]+state.Q[j]@(row[3:6]-n.rj[j]) for row,j in zip(n.model.records.get('sensor',[]),sensor_nodes)]
        result=evaluate_aerodynamics(n.model,condition,meshes,gamma,
            n.point_positions(state.r,state.Q),engine_positions,state.Q[engine_nodes],
            local_motion=motion,circulation_rate=gamma_dot,_iteration_fields=fields,
            sensor_positions=sensor_positions)
        calls+=1
        if args.factor==1 and part is not None and part not in coarse_probes:
            # Exercise the full network path at exactly the same supplied
            # Gamma/Gamma-dot, including its acceleration operating slots.
            x=state.x.copy();x[n.gamma_start:n.operating_start]=gamma/n.gamma_scale
            check_options=dict(options,circulation_rate=np.zeros_like(gamma) if gamma_dot is None else gamma_dot)
            _,checked=n.residual(x,detail=True,**check_options)
            errors={}
            for key in ('force','moment','circulation_residual'):
                expected=checked['aero'][key]
                np.testing.assert_allclose(result[key],expected,atol=2e-8,rtol=2e-10)
                errors[key]=float(np.max(abs(np.array(result[key])-expected)))
            coarse_probes[part]=errors
        return np.asarray(result['circulation_residual']),result,fields,meshes

    gamma=np.repeat(initial.gamma,args.factor)
    history=[]
    for iteration in range(8):
        r,base,fields,meshes=evaluate(gamma,capture=True)
        history.append(float(max(abs(r))))
        print('circulation',iteration,len(gamma),history[-1],flush=True)
        if iteration==0 and args.factor==1:
            np.testing.assert_allclose(base['force'],base_data['aero']['force'],atol=2e-8,rtol=2e-10)
            np.testing.assert_allclose(base['moment'],base_data['aero']['moment'],atol=2e-8,rtol=2e-10)
        data=fields.circulation_aero
        flow=FlowDerivative(SimpleNamespace(gamma_scale=1.,ng=len(gamma),size=len(gamma)),fields,data)
        _,_,jac=surface_derivatives(data,flow,residual_only=True)
        if history[-1]<1e-10:break
        increment=np.linalg.solve(jac,-r)
        for power in range(8):
            candidate=gamma+increment/2**power
            trial,*_=evaluate(candidate)
            if max(abs(trial))<history[-1]:gamma=candidate;break
        else:raise RuntimeError('Refined circulation line search failed')
    else:raise RuntimeError('Refined circulation did not converge')
    if args.factor==1:
        np.testing.assert_allclose(gamma,initial.gamma,atol=2e-8,rtol=2e-10)
    speed=np.asarray([s['normal_speed'] for s in base['strips'] if s['lifting']])
    lag=-2/(np.pi*speed*data['condition'].speed)
    assert data['condition'].aero_lag
    # Check the analytic Gamma block and explicit Gamma-dot block against
    # fresh physical residual probes before solving the harmonic subsystem.
    direction=np.sin(np.arange(len(gamma))+.3);step=1e-4
    plus,*_=evaluate(gamma+step*direction);minus,*_=evaluate(gamma-step*direction)
    jac_error=float(max(abs((plus-minus)/(2*step)-jac@direction)))
    plus,*_=evaluate(gamma,step*direction);minus,*_=evaluate(gamma,-step*direction)
    lag_error=float(max(abs((plus-minus)/(2*step)-lag*direction)))
    assert max(jac_error,lag_error)<2e-8,(jac_error,lag_error)

    shape=[]
    for width in (1e-3,5e-4):
        rhs=np.zeros(len(gamma),complex)
        for part in (0,1):
            for offset,weight in ((-2,1),(-1,-8),(1,8),(2,-1)):
                value,*_=evaluate(gamma,part=part,amplitude=offset*width)
                rhs+=(1 if part==0 else 1j)*weight/(12*width)*value
        shape.append(rhs)
    shape_error=float(max(abs(shape[0]-shape[1])));assert shape_error<2e-8,shape_error
    operator=jac+1j*omega*np.diag(lag)
    response=np.linalg.solve(operator,-shape[-1])
    response_error=float(max(abs(operator@response+shape[-1])));assert response_error<1e-10,response_error
    coarse_error=None
    if args.factor==1:
        expected=z[n.gamma_start:n.operating_start]*n.gamma_scale
        coarse_error=float(max(abs(response-expected))/max(abs(expected)))
        assert coarse_error<2e-6,coarse_error
    responses=[]
    for width in (1e-3,5e-4):
        value=np.zeros((len(meshes)+1,6),complex)
        for part in (0,1):
            component=(np.real,np.imag)[part]
            for offset,weight in ((-2,1),(-1,-8),(1,8),(2,-1)):
                amplitude=offset*width
                _,result,_,moving=evaluate(gamma+amplitude*component(response),amplitude*component(1j*omega*response),part=part,amplitude=amplitude)
                block=[]
                for mesh in moving:
                    strips=[s for s in result['strips'] if s['beam']==mesh.beam.index]
                    force=np.array([s['force'] for s in strips]);moment=np.array([s['moment'] for s in strips])
                    block.append(np.r_[force.sum(axis=0),(moment+np.cross(mesh.rm-n.model.reference[1],force)).sum(axis=0)])
                block.append(np.r_[result['force'],result['moment']])
                value+=(1 if part==0 else 1j)*weight/(12*width)*np.array(block)
        responses.append(value)
    load_error=float(max(abs(responses[0]-responses[1]).ravel()));assert load_error<2e-6,load_error
    np.savez_compressed(folder/'arrays.npz',gamma=gamma,gamma_response=response,jacobian=jac,lag_diagonal=lag,
        shape_rhs=shape[-1],loads=responses[-1],full_state=z)
    return dict(factor=args.factor,frequency_hz=args.frequency,panels=len(gamma),aero_evaluations=calls,
        steady_circulation_residuals=history,base_force=base['force'],base_moment=base['moment'],
        base_change_from_original_force=(np.array(base['force'])-base_data['aero']['force']).tolist(),
        base_change_from_original_moment=(np.array(base['moment'])-base_data['aero']['moment']).tolist(),
        jacobian_probe_error=jac_error,lag_probe_error=lag_error,shape_stencil_error=shape_error,
        harmonic_circulation_residual=response_error,coarse_response_relative_error=coarse_error,load_stencil_error=load_error,
        coarse_full_network_probes=coarse_probes,
        wrench_groups=[f'beam{mesh.beam.index}' for mesh in meshes]+['total_aerodynamic'],
        wrench_real=responses[-1].real.tolist(),wrench_imag=responses[-1].imag.tolist(),wrench_magnitude=abs(responses[-1]).tolist(),
        full_harmonic_checks=harmonic_checks,
        qualifications=[
            'Original loaded structural geometry, interpolation and actual rudder-response motion are prescribed. The aerodynamic base is re-solved; no structural retrim or new coupled Bode response is claimed.',
            'Lifting intervals are subdivided uniformly in whole-beam Glauert angle. The original current interval measure is partitioned, and documented spacing-dependent cross-surface cores change with aerodynamic refinement.',
            'All original material properties, body mesh, point/engine attachments, local motion, controls, lag, profile drag, stall and propeller feedback are retained.',
            'Factor one must recover the saved full-aircraft circulation response. Derivative steps and physical residual gates are unchanged across refinements.'])


def report(folder,args):
    import re
    import numpy as np
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    records=[read(STUDY/tag/'result.json') for tag in ACCEPTED]
    for tag,record in zip(ACCEPTED,records):
        terminal=read(STUDY/tag/'terminal.json')
        assert terminal['returncode']==0 and terminal['process_reaped'] and terminal['inputs_unchanged']
        assert record['frequency_hz']==records[0]['frequency_hz']
    previous=read(ROOT/'artifacts/daedalus-load-sensitivity-20261113/reference-dip/result.json')
    coarse=records[0];prior_error=0.
    for beam in range(1,6):
        rows=[row for row in previous['components'] if row['component'].startswith(f'beam{beam}:')]
        expected=np.sum([np.array(row['wrench_real'])+1j*np.array(row['wrench_imag']) for row in rows],axis=0)
        index=coarse['wrench_groups'].index(f'beam{beam}')
        actual=np.array(coarse['wrench_real'][index])+1j*np.array(coarse['wrench_imag'][index])
        np.testing.assert_allclose(actual,expected,atol=2e-7,rtol=2e-7)
        prior_error=max(prior_error,float(max(abs(actual-expected))))
    rows=[]
    for group,component in [('beam1',3),('beam1',5),('beam3',3),('beam3',5),('total_aerodynamic',5)]:
        values=np.array([complex(r['wrench_real'][r['wrench_groups'].index(group)][component],
                                 r['wrench_imag'][r['wrench_groups'].index(group)][component]) for r in records])
        rows.append(dict(group=group,component=['Fx','Fy','Fz','Mx','My','Mz'][component],
            magnitude=abs(values).tolist(),phase_deg=np.rad2deg(np.angle(values)).tolist(),
            successive_complex_change_percent=(100*abs(np.diff(values))/abs(values[1:])).tolist()))
    panels=[r['panels'] for r in records]
    fig,axes=plt.subplots(1,2,figsize=(10,4),layout='constrained')
    palette_source=(ROOT/'web/plot-colors.js').read_text()
    palette=re.findall(r'#[0-9a-fA-F]{6}',palette_source.split('surfaceColors = Object.freeze([')[1].split(']);')[0])
    for group,label,color in [('beam1','Wing',palette[0]),('beam3','Fin',palette[2])]:
        row=next(row for row in rows if row['group']==group and row['component']=='Mz')
        axes[0].plot(panels,row['magnitude'],'o-',label=label,color=color)
        axes[1].plot(panels,row['phase_deg'],'o-',label=label,color=color)
    for axis in axes:
        axis.set_xscale('log',base=2);axis.set_xticks(panels,[str(p) for p in panels]);axis.set_facecolor('#111827');axis.grid(color='white',alpha=.2)
        axis.set_xlabel('Total lifting panels');axis.legend(facecolor='#111827',labelcolor='white')
    axes[0].set_ylabel('Yaw-moment magnitude [lb ft / F3]')
    axes[1].set_ylabel('Yaw-moment phase [degrees]')
    fig.suptitle(f'Aerodynamic resolution at {records[0]["frequency_hz"]:.6f} Hz\nPrescribed loaded structure and motion; not a new aircraft Bode solution')
    fig.savefig(folder/'resolution.png',dpi=150);fig.savefig(folder/'resolution.svg');plt.close(fig)
    return dict(frequency_hz=records[0]['frequency_hz'],panels=panels,comparisons=rows,
        coarse_prior_full_load_error=prior_error,
        jobs={tag:read(STUDY/tag/'terminal.json') for tag in ACCEPTED},
        qualification='Conditional aerodynamic resolution check at fixed structural fields. No coupled response, original reference pass or production change follows from this plot.')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage',choices=['analyze','report'],default='analyze')
    parser.add_argument('--factor',type=int,choices=[1,2,4],default=1)
    parser.add_argument('--frequency',type=float,default=1.15737773741517)
    parser.add_argument('--tag',required=True);args=parser.parse_args()
    STUDY.mkdir(exist_ok=True);folder=STUDY/args.tag;folder.mkdir(exist_ok=False)
    (folder/'runner.py').write_bytes(Path(__file__).read_bytes())
    inputs=[Path(__file__),ROOT/'scripts/check_daedalus_wing_paper.py',ROOT/'scripts/check_daedalus_load_sensitivity.py',
        ROOT/'scripts/check_daedalus_source_operator.py',ROOT/'examples/dae.asw',ROOT/'examples/dae-cruise-physical-mesh-project.json',
        SOURCE/'trim-6.7-1/state.json',ROOT/'reference/aswing-authoritative-20261108/drela-aswing-steady.pdf',
        ROOT/'reference/aswing-authoritative-20261108/drela-aswing-unsteady.pdf',ROOT/'docs/validation/aswing-authoritative-sources.json']
    inputs += [SOURCE/'assembled-6.7'/name for name in ('A.npz','M.npz','maps.npz','plan.json','result.json','terminal.json')]
    if args.stage=='report':
        inputs += [STUDY/tag/name for tag in ACCEPTED for name in ('plan.json','result.json','terminal.json','runner.py','arrays.npz')]
        inputs += [ROOT/'artifacts/daedalus-load-sensitivity-20261113/reference-dip/result.json']
        inputs += [ROOT/'web/plot-colors.js']
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
