"""Bounded full-state load accounting and fixed-equilibrium sensitivities.

No aircraft parameter is fitted or changed. Multipliers refer to an affine
diagnostic that preserves the accepted residual at the base state, not to a
retrimmed modified aircraft. Every response uses the complete descriptor.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import resource
import signal
import sys
import time
import traceback
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'artifacts/daedalus-source-20261113'
STUDY=ROOT/'artifacts/daedalus-load-sensitivity-20261113'
LIMITS=dict(address_space_bytes=512*1024**2,cpu_seconds=15,wall_seconds=25)

def read(p):return json.loads(Path(p).read_text())
def write(p,value):
    with Path(p).open('x') as f:json.dump(value,f,indent=2,allow_nan=False);f.write('\n')
def pin(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def utc():return datetime.now(timezone.utc).isoformat()


def groups(system,data):
    """Partition exactly transferred external wrenches and stall residuals."""
    import numpy as np
    from openswing.aero import _stall_leakage
    n=system.network;r=data['r'];aero=data['aero'];rho=aero['atmosphere']['density']
    values={};wrenches={};node_values={};stall=[]
    def add(key,force,moment):
        global_force=force.sum(axis=0)
        global_moment=(moment+np.cross(r-n.model.reference[1],force)).sum(axis=0)
        v=np.zeros(system.size)
        v[6*n.ne:6*n.ne+3*n.nn]=(force/n.F).ravel()
        v[6*n.ne+3*n.nn:6*n.ne+6*n.nn]=(moment/(n.F*n.L)).ravel()
        v[n.operating_start:n.size]=np.r_[global_force/n.F,global_moment/(n.F*n.L)]
        values[key]=v;wrenches[key]=np.r_[global_force,global_moment]
        node_values[key]=(force,moment)
    def transfer(key,mesh,force,moment):
        nf=np.zeros_like(r);nm=np.zeros_like(r)
        for ids,f,m in n.steady_lifting_wrenches(mesh,force,moment):
            np.add.at(nf,ids,f);np.add.at(nm,ids,m)
        add(key,nf,nm)
    flow_cursor=0
    for mesh in data['meshes']:
        beam=mesh.beam;sl=n.beam_elements[beam.index];strips=aero['strips'][sl]
        assert all(s['beam']==beam.index for s in strips)
        force=np.array([s['force'] for s in strips]);moment=np.array([s['moment'] for s in strips])
        prefix=f'beam{beam.index}'
        if not beam.lifting:
            transfer(prefix+':body',mesh,force,moment);continue
        get=lambda name:np.array([s[name] for s in strips])
        velocity=get('relative_velocity');span=mesh.frames[:,:,1];chord_axis=mesh.frames[:,:,0]
        cl=get('cl');chord=beam.value('chord',mesh.tm);length=get('length')
        lift=rho*get('circulation')[:,None]*np.cross(velocity,span)*length[:,None]
        rate=get('circulation_rate_force');apparent=get('apparent_force')
        profile=force-lift-rate-apparent
        quarter=((.25-beam.value('Xax',mesh.tm))*chord)[:,None]*chord_axis
        profile_arm=(mesh.r0+mesh.r1)/2-mesh.rm
        pitch=moment-get('apparent_moment')-np.cross(quarter,lift+rate)-np.cross(profile_arm,profile)
        for label,f,m in [('lift',lift,np.cross(quarter,lift)),('rate_lift',rate,np.cross(quarter,rate)),
                          ('profile',profile,np.cross(profile_arm,profile)),
                          ('pitch',np.zeros_like(force),pitch),('apparent',apparent,get('apparent_moment'))]:
            transfer(prefix+':'+label,mesh,f,m)
        leakage,derivative=_stall_leakage(cl,beam.value('CLmin',mesh.tm),beam.value('CLmax',mesh.tm),data['condition'].stall_width)
        contribution=np.zeros(system.size)
        contribution[n.gamma_start+flow_cursor:n.gamma_start+flow_cursor+len(mesh.tm)]=(
            -get('normal_speed')/beam.value('dCLda',mesh.tm)*data['condition'].stall_factor*leakage/data['condition'].speed)
        values[prefix+':stall']=contribution;wrenches[prefix+':stall']=np.zeros(6)
        stall.append(dict(beam=beam.index,cl_min=float(min(cl)),cl_max=float(max(cl)),
            max_scaled_leakage_slope=float(max(data['condition'].stall_factor*derivative))))
        flow_cursor+=len(mesh.tm)
    assert flow_cursor==n.ng
    nf=np.zeros_like(r);nm=np.zeros_like(r)
    def point(node,position,force,moment):
        nf[node]+=force;nm[node]+=moment+np.cross(np.array(position)-r[node],force)
    positions=n.point_positions(r,data['Q'])
    for row,position,force in zip(n.weights,positions,aero['point_forces']):
        point(n.node(*row[:2]),position,np.array(force),np.zeros(3))
    for entry in aero['body_shoulders']:
        point(n.node(entry['beam'],entry['t']),entry['position'],np.array(entry['force']),np.zeros(3))
    for engine in aero['engines']:
        point(n.node(engine['beam'],engine['t']),engine['position'],np.array(engine['force']),np.array(engine['moment']))
    add('points_shoulders_engines',nf,nm)
    af=sum(v[0] for v in node_values.values());am=sum(v[1] for v in node_values.values())
    actual=np.r_[aero['force'],aero['moment']]
    reconstructed=sum(wrenches.values())
    np.testing.assert_allclose(reconstructed,actual,atol=2e-10,rtol=2e-11)
    add('real_mass_gravity_applied',data['force']-af,data['moment']-am)
    np.testing.assert_allclose(sum(v[0] for v in node_values.values()),data['force'],atol=2e-12,rtol=2e-12)
    np.testing.assert_allclose(sum(v[1] for v in node_values.values()),data['moment'],atol=2e-12,rtol=2e-12)
    return values,wrenches,dict(aerodynamic_wrench_closure=float(max(abs(reconstructed-actual))),stall=stall)


def analyze(folder,args):
    import numpy as np
    import scipy.sparse as sp
    import check_daedalus_source_operator as source
    from openswing.frequency_response import harmonic_solve,HarmonicInput
    from openswing.harmonic_structure import ReusableBeamStructure
    source.imports()
    setup=SimpleNamespace(speed=6.7,seed=SOURCE/'trim-6.7-1/state.json',frozen=False,no_lag=False,no_plume=False,fourier=0)
    system=source.dynamic(setup);n=system.network
    assert n.ng==82 and system.size==2044 and not n.loads
    assert [c.quantity for c in n.operating.constraints]==['force.'+a for a in 'xyz']+['moment.'+a for a in 'xyz']
    matrix=SOURCE/'assembled-6.7';a,m=(sp.load_npz(matrix/name) for name in ('A.npz','M.npz'))
    for pencil in (a,m):
        for array in (pencil.data,pencil.indices,pencil.indptr):array.flags.writeable=False
    structure=ReusableBeamStructure(a,m,np.r_[np.arange(618),np.arange(1266,1296)],np.arange(1266),np.arange(1384,2032),np.arange(1384,2032))
    maps=np.load(matrix/'maps.npz');omega=2*np.pi*args.frequency
    z,checks=harmonic_solve(a,m,maps['B'][:,0],omega,_structure=structure);rate=1j*omega*z
    forcing,_=HarmonicInput(system,'control.3',0).at_frequency(omega)
    def sample(v,dv,input_forcing):
        state,_,options=system.physical_state(v,dv,input_forcing)
        residual,data=n.residual(state.x,detail=True,**options)
        values,wrenches,diagnostics=groups(system,data)
        return values,wrenches,diagnostics,float(max(abs(residual)))
    base=sample(np.zeros(system.size),np.zeros(system.size),None)
    assert base[3]<1e-9
    keys=list(base[0]);stencils=[]
    for step in (args.step,args.step/2):
        tangent=np.zeros((system.size,len(keys)),complex);wrench=np.zeros((6,len(keys)),complex);capture=[]
        for component,part in enumerate((np.real,np.imag)):
            for offset,weight in [(-2,1),(-1,-8),(1,8),(2,-1)]:
                value=step*offset
                values,wrenches,diagnostics,residual=sample(value*part(z),value*part(rate),forcing(component,value))
                factor=weight/(12*step)*(1 if component==0 else 1j)
                tangent+=factor*np.column_stack([values[k] for k in keys]);wrench+=factor*np.column_stack([wrenches[k] for k in keys])
                capture.append(dict(component=component,offset=offset,diagnostics=diagnostics,residual=residual))
        stencils.append(dict(step=step,loads=tangent,wrench=wrench,capture=capture))
    delta=stencils[1]['loads'];moments=stencils[1]['wrench']
    error=float(np.max(abs(delta-stencils[0]['loads'])))
    assert error<2e-8,error
    # Complete incremental net force/moment closes for the actual harmonic
    # solution; stall is a separate circulation-equation term, not a load.
    balance=moments.sum(axis=1)
    assert max(abs(balance))<2e-6,balance
    dz,sensitivity_checks=harmonic_solve(a,m,delta,omega,_structure=structure)
    outputs=maps['C']@z;derivatives=maps['C']@dz
    np.savez_compressed(folder/'arrays.npz',state=z,component_residuals=delta,wrenches=moments,
        sensitivity_states=dz,output=outputs,output_derivatives=derivatives,
        stencil_load_difference=delta-stencils[0]['loads'])
    rows=[]
    for i,key in enumerate(keys):
        d=derivatives[:,i]
        row=dict(component=key,wrench_real=moments[:,i].real.tolist(),wrench_imag=moments[:,i].imag.tolist(),
            output_derivative_real=d.real.tolist(),output_derivative_imag=d.imag.tolist(),
            log_magnitude_sensitivity=np.real(d/outputs).tolist(),phase_sensitivity_degrees=np.imag(d/outputs).tolist())
        # Store phase derivative with correct radians-to-degrees conversion.
        row['phase_sensitivity_degrees']=(np.imag(d/outputs)*180/np.pi).tolist()
        rows.append(row)
    print('frequency',args.frequency,'outputs',abs(outputs).tolist(),'stencil_error',error,'balance',max(abs(balance)),flush=True)
    for row in sorted(rows,key=lambda v:abs(v['log_magnitude_sensitivity'][0]),reverse=True)[:10]:
        print(row['component'],row['log_magnitude_sensitivity'],flush=True)
    return dict(frequency_hz=args.frequency,channels=source.CHANNELS,
        output_real=outputs.real.tolist(),output_imag=outputs.imag.tolist(),output_magnitude=abs(outputs).tolist(),
        components=rows,base_diagnostics=base[2],base_residual=base[3],
        max_stencil_difference=error,total_wrench_real=balance.real.tolist(),total_wrench_imag=balance.imag.tolist(),
        solve_checks=checks,sensitivity_solve_checks=sensitivity_checks,
        stencils=[dict(step=s['step'],capture=s['capture']) for s in stencils],
        qualification='Exact first variation of an affine component multiplier at fixed accepted equilibrium. It is not a retrimmed parameter change or a proposed physical correction.')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tag',required=True);parser.add_argument('--frequency',type=float,required=True)
    parser.add_argument('--step',type=float,default=1e-3);args=parser.parse_args()
    STUDY.mkdir(exist_ok=True);folder=STUDY/args.tag;folder.mkdir(exist_ok=False)
    (folder/'runner.py').write_bytes(Path(__file__).read_bytes())
    inputs=[Path(__file__),ROOT/'scripts/check_daedalus_source_operator.py',ROOT/'examples/dae.asw',
        ROOT/'examples/dae-cruise-physical-mesh-project.json',SOURCE/'trim-6.7-1/state.json']
    inputs += [SOURCE/'assembled-6.7'/name for name in ('A.npz','M.npz','maps.npz','plan.json','result.json','terminal.json')]
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
            try:write(folder/'result.json',analyze(folder,args))
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
