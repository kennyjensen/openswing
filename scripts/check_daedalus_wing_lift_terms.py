"""Bounded product-rule decomposition of the current wing lift tangent.

The accepted full aircraft response is supplied. Differential force-law terms
are accounting components, not independently adjustable physical parameters.
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

STUDY=ROOT/'artifacts/daedalus-wing-lift-terms-20261113'
SAVED=ROOT/'artifacts/daedalus-load-sensitivity-20261113'
CASES={'slow':(.2,'slow-animation'),'one':(1.,'one-hertz'),'dip':(1.15737773741517,'reference-dip')}
TERMS=['circulation','air_velocity','span_direction','strip_length','load_position']


def analyze(folder,args):
    import numpy as np
    import scipy.sparse as sp
    from check_daedalus_wing_paper import dynamic
    from check_daedalus_load_sensitivity import groups
    from openswing.frequency_response import HarmonicInput,harmonic_solve
    from openswing.harmonic_structure import ReusableBeamStructure
    system=dynamic();n=system.network;frequency,tag=CASES[args.case];omega=2*np.pi*frequency
    previous=np.load(SAVED/tag/'arrays.npz');z=previous['state'];rate=1j*omega*z
    forcing,_=HarmonicInput(system,'control.3',0).at_frequency(omega)
    sl=n.beam_elements[1];lo,hi=n.a[sl],n.b[sl]

    def sample(q,dq,input_force):
        state,_,options=system.physical_state(q,dq,input_force)
        residual,data=n.residual(state.x,detail=True,**options)
        mesh,=[m for m in data['meshes'] if m.beam.index==1]
        strips=data['aero']['strips'][sl];beam=mesh.beam
        get=lambda name:np.array([s[name] for s in strips])
        quarter=((.25-beam.value('Xax',mesh.tm))*beam.value('chord',mesh.tm))[:,None]*mesh.frames[:,:,0]
        values,wrenches,_=groups(system,data)
        primitives=dict(gamma=get('circulation'),velocity=get('relative_velocity'),span=mesh.frames[:,:,1],
            length=get('length'),arm=quarter+mesh.rm-(mesh.r0+mesh.r1)/2,positions=data['r'])
        return primitives,values['beam1:lift'],wrenches['beam1:lift'],data['aero']['atmosphere']['density'],float(max(abs(residual)))

    zero=np.zeros(system.size);base,_,_,rho,error=sample(zero,zero,None);assert error<1e-9
    stencils=[]
    for step in (1e-3,5e-4):
        derivative={key:np.zeros_like(value,dtype=complex) for key,value in base.items()}
        load=np.zeros(system.size,complex);wrench=np.zeros(6,complex)
        for part,function in enumerate((np.real,np.imag)):
            for offset,weight in [(-2,1),(-1,-8),(1,8),(2,-1)]:
                h=step*offset;p,v,w,density,_=sample(h*function(z),h*function(rate),forcing(part,h))
                assert density==rho
                factor=weight/(12*step)*(1 if part==0 else 1j)
                for key in derivative:derivative[key]+=factor*p[key]
                load+=factor*v;wrench+=factor*w
        stencils.append((derivative,load,wrench))
    d,target,target_wrench=stencils[-1]
    step_errors={key:float(np.max(abs(d[key]-stencils[0][0][key]))) for key in d}
    assert max(step_errors.values())<2e-6,step_errors
    f0=rho*(base['gamma']*base['length'])[:,None]*np.cross(base['velocity'],base['span'])
    force=np.array([
        rho*(d['gamma']*base['length'])[:,None]*np.cross(base['velocity'],base['span']),
        rho*(base['gamma']*base['length'])[:,None]*np.cross(d['velocity'],base['span']),
        rho*(base['gamma']*base['length'])[:,None]*np.cross(base['velocity'],d['span']),
        rho*(base['gamma']*d['length'])[:,None]*np.cross(base['velocity'],base['span']),
        np.zeros_like(f0,dtype=complex)])
    couple=np.cross(base['arm'][None,:,:],force);couple[-1]+=np.cross(d['arm'],f0)
    nf=np.zeros((len(TERMS),n.nn,3),complex);nm=np.zeros_like(nf);nf0=np.zeros((n.nn,3))
    for ids in (lo,hi):
        np.add.at(nf0,ids,f0/2)
        for j in range(len(TERMS)):
            np.add.at(nf[j],ids,force[j]/2);np.add.at(nm[j],ids,couple[j]/2)
    global_force=nf.sum(axis=1)
    global_moment=(nm+np.cross((base['positions']-n.model.reference[1])[None,:,:],nf)).sum(axis=1)
    global_moment[-1]+=np.cross(d['positions'],nf0).sum(axis=0)
    wrenches=np.concatenate([global_force,global_moment],axis=1).T
    residuals=np.zeros((system.size,len(TERMS)),complex)
    residuals[6*n.ne:6*n.ne+3*n.nn]=nf.reshape(len(TERMS),-1).T/n.F
    residuals[6*n.ne+3*n.nn:6*(n.ne+n.nn)]=nm.reshape(len(TERMS),-1).T/(n.F*n.L)
    residuals[n.operating_start:n.size]=wrenches/np.array([n.F]*3+[n.F*n.L]*3)[:,None]
    saved_result=read(SAVED/tag/'result.json');keys=[c['component'] for c in saved_result['components']]
    index=keys.index('beam1:lift')
    errors=dict(load=float(max(abs(residuals.sum(axis=1)-target))),wrench=float(max(abs(wrenches.sum(axis=1)-target_wrench))),
        saved_load=float(max(abs(target-previous['component_residuals'][:,index]))),
        saved_wrench=float(max(abs(target_wrench-previous['wrenches'][:,index]))))
    assert errors['load']<2e-8 and errors['wrench']<2e-6,errors
    assert errors['saved_load']<2e-8 and errors['saved_wrench']<2e-6,errors
    matrix=SOURCE/'assembled-6.7';a,m=(sp.load_npz(matrix/name) for name in ('A.npz','M.npz'))
    for pencil in (a,m):
        for value in (pencil.data,pencil.indices,pencil.indptr):value.flags.writeable=False
    maps=np.load(matrix/'maps.npz');k=1j*omega*m-a
    assert max(abs(k@z-maps['B'][:,0]))<2e-10
    structure=ReusableBeamStructure(a,m,np.r_[np.arange(618),np.arange(1266,1296)],np.arange(1266),np.arange(1384,2032),np.arange(1384,2032))
    dz,checks=harmonic_solve(a,m,residuals,omega,_structure=structure)
    output=maps['C']@z;sensitivities=maps['C']@dz
    errors['saved_sensitivity']=float(max(abs(sensitivities.sum(axis=1)-previous['output_derivatives'][:,index])))
    assert errors['saved_sensitivity']<2e-8,errors
    np.savez_compressed(folder/'arrays.npz',state=z,residuals=residuals,wrenches=wrenches,force_terms=force,
        node_force=nf,node_moment=nm,output=output,output_derivatives=sensitivities,
        target_load=target,target_wrench=target_wrench,**{'base_'+key:value for key,value in base.items()},
        **{'derivative_'+key:value for key,value in d.items()})
    rows=[dict(term=name,wrench_real=wrenches[:,j].real.tolist(),wrench_imag=wrenches[:,j].imag.tolist(),
        output_derivative_real=sensitivities[:,j].real.tolist(),output_derivative_imag=sensitivities[:,j].imag.tolist(),
        log_magnitude_sensitivity=np.real(sensitivities[:,j]/output).tolist()) for j,name in enumerate(TERMS)]
    result=dict(frequency_hz=frequency,terms=rows,channels=saved_result['channels'],errors=errors,step_errors=step_errors,
        output_magnitude=abs(output).tolist(),solve_checks=checks,nonlinear_evaluations=17,
        qualification='Product-rule accounting of Eq34 and conservative nodal/global moment transfer along the supplied full coupled response. Sensitivities multiply only the named differential contribution while holding the equilibrium fixed. They are not new Bode predictions, independent physical parameters, native ASWING validation, or a fit.')
    print(json.dumps(dict(frequency_hz=frequency,errors=errors,terms=[dict(term=r['term'],yaw_sensitivity=r['log_magnitude_sensitivity'][0]) for r in rows])),flush=True)
    return result


def split(folder,args):
    import numpy as np
    import scipy.sparse as sp
    from check_daedalus_wing_paper import dynamic
    from openswing.local_motion import NetworkMotion
    from openswing.frequency_response import harmonic_solve
    from openswing.harmonic_structure import ReusableBeamStructure
    system=dynamic();n=system.network;frequency,_=CASES[args.case];omega=2*np.pi*frequency
    saved=np.load(STUDY/args.case/'arrays.npz');z=saved['state']
    base={key[5:]:saved[key] for key in saved.files if key.startswith('base_')}
    sl=n.beam_elements[1];lo,hi=n.a[sl],n.b[sl]
    zero=np.zeros(system.size);state,_,options=system.physical_state(zero,zero,None)
    residual,data=n.residual(state.x,detail=True,**options);assert max(abs(residual))<1e-9
    strips=data['aero']['strips'][sl];points=np.array([s['velocity_position'] for s in strips])
    rho=data['aero']['atmosphere']['density']
    np.testing.assert_allclose(base['positions'],data['r'],atol=1e-13,rtol=0)
    assert max(abs(system.Omega0))<1e-12
    u,w=z[system.velocity_start:system.frame_start].reshape(2,n.nn,3)
    frame=-(system.V*z[system.frame_start:system.frame_start+3]+np.cross(system.W*z[system.frame_start+3:system.frame_start+6],points))
    local=np.zeros_like(points,dtype=complex)
    for part,function in enumerate((np.real,np.imag)):
        motion=NetworkMotion(n,system.r0,system.Q0,system.V*function(u),system.W*function(w),np.zeros_like(system.r0),np.zeros_like(system.r0))
        local-=(1 if part==0 else 1j)*motion.sample(1,n.fractions[1])[0].velocity_at(points)
    flow=saved['derivative_velocity']-frame-local
    velocities=np.array([frame,local,flow]);terms=['frame_air_velocity','elastic_air_velocity','induced_air_velocity']
    expected_load=saved['residuals'][:,TERMS.index('air_velocity')]
    expected_sensitivity=saved['output_derivatives'][:,TERMS.index('air_velocity')]
    if args.stage=='elastic':
        root=n.node(1,0.)
        translation=np.broadcast_to(-system.V*u[root],points.shape)
        rotation=-np.cross(system.W*w[root],points-system.r0[root])
        velocities=np.array([translation,rotation,local-translation-rotation])
        terms=['root_translation','root_rotation','deformation_relative_to_root']
        previous=np.load(STUDY/(args.case+'-split')/'arrays.npz')
        expected_load=previous['residuals'][:,1];expected_sensitivity=previous['output_derivatives'][:,1]
    force=rho*(base['gamma']*base['length'])[None,:,None]*np.cross(velocities,base['span'][None,:,:])
    couple=np.cross(base['arm'][None,:,:],force)
    nf=np.zeros((3,n.nn,3),complex);nm=np.zeros_like(nf)
    for ids in (lo,hi):
        for j in range(3):np.add.at(nf[j],ids,force[j]/2);np.add.at(nm[j],ids,couple[j]/2)
    wrench=np.concatenate([nf.sum(axis=1),(nm+np.cross((base['positions']-n.model.reference[1])[None,:,:],nf)).sum(axis=1)],axis=1).T
    loads=np.zeros((system.size,3),complex)
    loads[6*n.ne:6*n.ne+3*n.nn]=nf.reshape(3,-1).T/n.F
    loads[6*n.ne+3*n.nn:6*(n.ne+n.nn)]=nm.reshape(3,-1).T/(n.F*n.L)
    loads[n.operating_start:n.size]=wrench/np.array([n.F]*3+[n.F*n.L]*3)[:,None]
    error=float(max(abs(loads.sum(axis=1)-expected_load)))
    assert error<2e-12,error
    a,m=(sp.load_npz(SOURCE/'assembled-6.7'/name) for name in ('A.npz','M.npz'))
    for pencil in (a,m):
        for value in (pencil.data,pencil.indices,pencil.indptr):value.flags.writeable=False
    maps=np.load(SOURCE/'assembled-6.7/maps.npz')
    structure=ReusableBeamStructure(a,m,np.r_[np.arange(618),np.arange(1266,1296)],np.arange(1266),np.arange(1384,2032),np.arange(1384,2032))
    dz,checks=harmonic_solve(a,m,loads,omega,_structure=structure);dy=maps['C']@dz;output=maps['C']@z
    sensitivity_error=float(max(abs(dy.sum(axis=1)-expected_sensitivity)))
    assert sensitivity_error<2e-10,sensitivity_error
    np.savez_compressed(folder/'arrays.npz',velocity_terms=velocities,force_terms=force,residuals=loads,
        wrenches=wrench,output_derivatives=dy,output=output,positions=points)
    rows=[dict(term=name,wrench_real=wrench[:,j].real.tolist(),wrench_imag=wrench[:,j].imag.tolist(),
        log_magnitude_sensitivity=np.real(dy[:,j]/output).tolist()) for j,name in enumerate(terms)]
    result=dict(frequency_hz=frequency,terms=rows,load_sum_error=error,sensitivity_sum_error=sensitivity_error,solve_checks=checks,
        qualification='Further accounting of the fixed-equilibrium velocity term. Frame and elastic kinematic velocities use Eq30-31; induced is the remainder and includes circulation, changing vortex geometry, body flow and propeller flow. No independently modified aircraft or causal split within that induced remainder is claimed.')
    if args.stage=='elastic':result['qualification']='Wing elastic-velocity contribution partitioned into rigid transport from beam 1:t0 and remaining deformation. Only the velocity-dependent part of ordinary circulation lift is partitioned; this does not delete complete wing-motion aerodynamic feedback or change the aircraft.'
    print(json.dumps(dict(frequency_hz=frequency,load_sum_error=error,sensitivity_sum_error=sensitivity_error,terms=rows)),flush=True)
    return result


elastic=split


def report(folder,args):
    import csv
    import re
    import numpy as np
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    cases=['slow','dip'];labels=['0.2 Hz','1.157 Hz']
    samples=[read(STUDY/tag/'result.json') for tag in cases]
    splits=[read(STUDY/(tag+'-split')/'result.json') for tag in cases]
    elastic_parts=[read(STUDY/(tag+'-elastic')/'result.json') for tag in cases]
    palette=re.findall(r"'([^']+)'",(ROOT/'web/plot-colors.js').read_text().split('export const plotColors = Object.freeze([')[1].split(']);')[0])
    plt.rcParams.update({'figure.facecolor':'#111827','axes.facecolor':'#111827','text.color':'white',
        'axes.labelcolor':'white','xtick.color':'white','ytick.color':'white','axes.edgecolor':'#9ca3af','font.size':9})
    fig,axes=plt.subplots(1,3,figsize=(16,5.3),layout='constrained')
    for ax,records,names,title in [(axes[0],samples,['Circulation','Air velocity','Span direction','Strip length','Load position'],'Wing lift product-rule terms'),
                                 (axes[1],splits,['Frame motion','Wing elastic motion','Induced flow'],'Air-velocity term split'),
                                 (axes[2],elastic_parts,['Root translation','Root rotation','Wing deformation'],'Wing elastic-velocity term split')]:
        y=np.arange(len(names))
        for j,(sample,label) in enumerate(zip(records,labels)):
            values=[r['log_magnitude_sensitivity'][0] for r in sample['terms']]
            ax.barh(y+(j-.5)*.36,values,.36,color=palette[j],label=label)
        ax.set_yticks(y,names);ax.invert_yaxis();ax.axvline(0,color='white',alpha=.5,lw=.7)
        ax.set_xlabel('Yaw magnitude change [%]\nfor +1% differential-term multiplier')
        ax.set_title(title);ax.grid(axis='x',alpha=.15);ax.set_axisbelow(True)
        ax.legend(facecolor='#111827',labelcolor='white')
    fig.suptitle('Daedalus: which part of the wing lift tangent affects yaw?\nLocal sensitivities at the accepted equilibrium; no physical force law rescaled')
    fig.savefig(folder/'wing-lift-terms.png',dpi=150);fig.savefig(folder/'wing-lift-terms.svg');plt.close(fig)
    with (folder/'terms.csv').open('x') as stream:
        writer=csv.writer(stream);writer.writerow(['frequency_hz','decomposition','term','yaw_log_magnitude_sensitivity','body_z_moment_real_lbft_per_F3','body_z_moment_imag_lbft_per_F3'])
        for decomposition,records in [('lift_product_rule',samples),('air_velocity',splits),('elastic_velocity',elastic_parts)]:
            for sample in records:
                for row in sample['terms']:writer.writerow([sample['frequency_hz'],decomposition,row['term'],row['log_magnitude_sensitivity'][0],row['wrench_real'][5],row['wrench_imag'][5]])
    return dict(cases=cases,samples=samples,splits=splits,elastic_parts=elastic_parts,qualification=samples[0]['qualification'])


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--case',choices=list(CASES))
    parser.add_argument('--stage',choices=['analyze','split','elastic','report'],default='analyze')
    parser.add_argument('--tag',required=True);args=parser.parse_args()
    if args.stage!='report' and args.case is None:parser.error('--case is required')
    STUDY.mkdir(exist_ok=True);folder=STUDY/args.tag;folder.mkdir(exist_ok=False)
    (folder/'runner.py').write_bytes(Path(__file__).read_bytes())
    inputs=[Path(__file__),ROOT/'scripts/check_daedalus_wing_paper.py',ROOT/'scripts/check_daedalus_source_operator.py',
        ROOT/'scripts/check_daedalus_load_sensitivity.py',ROOT/'examples/dae.asw',ROOT/'examples/dae-cruise-physical-mesh-project.json',
        SOURCE/'trim-6.7-1/state.json',ROOT/'reference/aswing-authoritative-20261108/drela-aswing-unsteady.pdf']
    if args.case is not None:inputs += [SAVED/CASES[args.case][1]/name for name in ('arrays.npz','result.json','terminal.json')]
    if args.stage in ('split','elastic'):inputs += [STUDY/args.case/name for name in ('arrays.npz','result.json','terminal.json')]
    if args.stage=='elastic':inputs += [STUDY/(args.case+'-split')/name for name in ('arrays.npz','result.json','terminal.json')]
    if args.stage=='report':inputs += [STUDY/tag/name for tag in ('slow','dip','slow-split','dip-split','slow-elastic','dip-elastic') for name in ('arrays.npz','result.json','terminal.json')]+[ROOT/'web/plot-colors.js']
    inputs += [SOURCE/'assembled-6.7'/name for name in ('A.npz','M.npz','maps.npz')]
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
