"""Original elastic rotor-mount reference, separate from the numerical kernel.

The four-state mechanics and azimuthal blade integration below do not call the
production engine, inertia, beam or eigenvalue routines. The full ASW model is
then evaluated through the same public bridge as the browser.
"""
import hashlib,json,platform,sys,time
from pathlib import Path
ROOT=Path(__file__).absolute().parents[1];sys.path.insert(0,str(ROOT))
import numpy as np
import scipy
from scipy.linalg import eigvals
from scipy.optimize import linear_sum_assignment
from scipy.spatial.transform import Rotation
from openswing.asw import parse_asw,Distribution
from openswing.bridge import dispatch

RHO,RADIUS,OMEGA,DESIGN_SPEED,BLADES,CHORD,CLA=1.225,.5,180.,10.,3,.06,5.8
INERTIA,SPIN,EI,LENGTH=.2,-1.8,5.,1.
J=np.array([[0.,-1.],[1.,0.]])


def radial_integrals():
    nodes,weights=np.polynomial.legendre.leggauss(100)
    radius=(nodes+1)*RADIUS/2;dr=weights*RADIUS/2
    phi=np.arctan2(DESIGN_SPEED,OMEGA*radius)
    return np.array([[BLADES*CHORD/RADIUS**2*np.sum(f(phi)*(radius/RADIUS)**j*dr)
        for f in (np.sin,np.cos)] for j in range(4)])


def reference(spec,continuum=False):
    """Exact linear mechanics of two rotations, including discrete beam error.

    Eliminate the pin reaction using the midpoint beam's flexibility integrals:
    B = sum(h*(L-x_mid)^2); k = EI/(L - L^4/(4B)). For a uniform mesh this is
    EI/L*(4N^2-1)/(N^2-1), converging to the Euler-Bernoulli 4EI/L.
    """
    n=spec.get('panels',4);k=4*EI/LENGTH if continuum else EI/LENGTH*(4*n*n-1)/(n*n-1)
    sc=radial_integrals();sign=spec.get('spin_sign',1);h=SPIN*sign if spec.get('spin',True) else 0.
    active=spec.get('engine_type',2)==2
    a=sign*RHO*RADIUS**3/4*CLA*sc[1,1] if active else 0.
    d=RHO*RADIUS**4/4*CLA*sc[3,1]*OMEGA*RADIUS if active else 0.
    speed=spec.get('speed',10.);c=a*speed**2
    stiffness=k*np.eye(2)-c*J;damping=d*np.eye(2)-h*J
    matrix=np.block([[np.zeros((2,2)),np.eye(2)],[-stiffness/INERTIA,-damping/INERTIA]])
    critical_frequency=(SPIN+np.sqrt(SPIN**2+4*INERTIA*k))/(2*INERTIA)
    critical_speed=np.sqrt(d*critical_frequency/abs(a)) if active and spec.get('spin',True) else None
    return dict(k=k,spin=h,circulatory=c,damping=d,stiffness=stiffness,damping_matrix=damping,
        A=matrix,roots=eigvals(matrix),critical_speed=critical_speed,critical_frequency=critical_frequency)


def blade_derivatives(spin=1):
    """Differentiate direct blade-force quadrature at zero section lift.

    This independent check is at the 10 m/s design inflow only. The ASW source
    freezes its radial inflow-angle integrals during subsequent speed sweeps.
    """
    nodes,weights=np.polynomial.legendre.leggauss(100)
    radius=(nodes+1)*RADIUS/2;dr=weights*RADIUS/2
    phi=np.arctan2(DESIGN_SPEED,OMEGA*radius);psi=np.arange(256)*2*np.pi/256
    er=np.stack([np.zeros_like(psi),np.cos(psi),np.sin(psi)],axis=-1)
    ex=np.array([1.,0.,0.]);et=-spin*np.cross(ex,er)
    arm=radius[:,None,None]*er[None,:,:]
    baseline=DESIGN_SPEED*ex-OMEGA*radius[:,None,None]*et[None,:,:]
    def wrench(v,w):
        velocity=baseline+v-np.cross(w,arm)
        axial=velocity[...,0];tangent=-np.sum(velocity*et[None,:,:],axis=-1)
        angle=np.arctan2(axial,tangent);cl=CLA*(phi[:,None]-angle)
        force=(.5*RHO*(axial**2+tangent**2)*cl*CHORD*dr[:,None])[...,None]*(
            -np.cos(angle)[...,None]*ex-np.sin(angle)[...,None]*et[None,:,:])
        return np.r_[force.sum(axis=(0,1)),np.cross(arm,force).sum(axis=(0,1))]*BLADES/len(psi)
    columns=[];step=1e-4
    for axis in (1,2):
        v=np.eye(3)[axis]*step
        columns.append((wrench(v,np.zeros(3))-wrench(-v,np.zeros(3)))/(2*step))
    for axis in (1,2):
        w=np.eye(3)[axis]*step
        columns.append((wrench(np.zeros(3),w)-wrench(np.zeros(3),-w))/(2*step))
    return np.array(columns).T


def configuration(spec):
    model=parse_asw((ROOT/'examples/whirl-flutter.asw').read_text())
    sign=spec.get('spin_sign',1);scale=spec.get('time_unit',1.)
    q=Rotation.from_rotvec(spec.get('rotation',[0.,0.,0.])).as_matrix()
    model.reference[1]=q@model.reference[1]  # moments about the fixed rotor pin
    model.units.declarations['T']=(scale,'s')
    model.constants*=np.array([scale**2,1/scale**2,scale])
    for name,values in zip(('x','y','z'),q[:,0]):
        model.beams[0].distributions[name]=Distribution(name,[0.,1.],[0.,values],0)
    row=model.records['weight'][0];row[2:5]=q@row[2:5]
    row[8:11]=q@row[8:11]*(sign*scale if spec.get('spin',True) else 0.)
    inertia=q@np.diag(row[11:14])@q.T
    row[11:17]=[*np.diag(inertia),-inertia[0,1],-inertia[0,2],-inertia[1,2]]
    for i,row in enumerate(model.records['engine']):
        row[4:7]=q@row[4:7];row[7:10]=q@row[7:10]
        if i==0:row[1]=spec.get('engine_type',2);row[13]*=sign*scale
    for row in model.records['sensor']:row[3:6]=q@row[3:6]
    e=q[:,0];speed=spec.get('speed',10.)*scale
    condition=dict(speed=speed,alpha=float(np.degrees(np.arctan2(e[2],e[0]))),beta=float(-np.degrees(np.arcsin(e[1]))),density=RHO/scale**2,mach=0)
    n=spec.get('panels',4)
    return dict(source=model.dumps(),panels=dict(default=n,beams={'1':dict(count=n,spacing='uniform')}),
        gravity=[0,0,0],condition=condition)


def specifications():
    out=[dict(name='stable_mesh4',panels=4,speed=10.,frequency=True),
         dict(name='stable_mesh8',panels=8,speed=10.),
         dict(name='stable_mesh16',panels=16,speed=10.),
         dict(name='unstable',speed=14.,frequency=True),
         dict(name='reverse_spin',speed=10.,spin_sign=-1,frequency=True),
         dict(name='no_intrinsic_spin',speed=10.,spin=False),
         dict(name='without_p_factor',speed=10.,engine_type=1),
         dict(name='rotated',speed=10.,rotation=[.31,-.24,.17],frequency=True),
         dict(name='time_unit',speed=10.,time_unit=.1,frequency=True),
         dict(name='tangent_step',speed=10.,step=1e-6),
         dict(name='flutter_boundary',speed=10.,stability=True)]
    return [dict(s,request=configuration(s)) for s in out]


def compute(spec):
    options=dict(frame='fixed',count=4,step=spec.get('step',1e-5))
    if spec.get('stability'):
        return dict(stability=dispatch(dict(spec['request'],action='stability',modes=options,
            stability=dict(parameter='speed',values=[10.,14.],refine=True,parameter_rtol=1e-5,growth_tolerance=1e-7,max_iterations=20))))
    out=dict(modes=dispatch(dict(spec['request'],action='modes',modes=options)))
    if spec.get('frequency'):
        scale=spec.get('time_unit',1.)
        out['frequency']=dispatch(dict(spec['request'],action='frequency',frequency=dict(frame='fixed',
            frequencies=(np.array([0.,5.,6.5,10.,16.,25.])*scale).tolist(),inputs=['power.2','power.3'],step=options['step'])))
    return out


def as_complex(value):return np.asarray(value['real'])+1j*np.asarray(value['imag'])


def verify(spec,result):
    checks=0;maximum=0.;mode_equation=0.
    def close(a,b,tolerance=2e-6):
        nonlocal checks,maximum
        a,b=np.asarray(a),np.asarray(b);error=float(np.max(abs(a-b)/np.maximum(1.,abs(b))))
        checks+=a.size*(2 if np.iscomplexobj(a) or np.iscomplexobj(b) else 1);maximum=max(maximum,error)
        assert error<tolerance,(spec['name'],a,b,error)
    ref=reference(spec);scale=spec.get('time_unit',1.)
    rotation=Rotation.from_rotvec(spec.get('rotation',[0.,0.,0.])).as_matrix()
    if 'stability' in result:
        out=result['stability'];assert out['converged'] and out['tracking_complete'] and out['spectrum_complete']
        assert len(out['boundaries'])==1,out['boundaries'];b=out['boundaries'][0]
        assert b['status']=='resolved',b
        close(b['value'],ref['critical_speed'],2e-5)
        close(abs(complex(*b['eigenvalue']).imag),ref['critical_frequency'],2e-5)
        for p in out['points']:
            if not p.get('result'):continue
            actual=np.array([complex(*m['eigenvalue']) for m in p['result']['modes']])
            expected=reference(dict(spec,speed=p['value']))['roots']
            i,j=linear_sum_assignment(abs(actual[:,None]-expected[None,:]));close(actual[i],expected[j])
        return dict(independent_scalar_checks=checks,maximum_scaled_error=maximum,critical_speed=b['value'],critical_frequency=abs(complex(*b['eigenvalue']).imag),reference_speed=ref['critical_speed'],reference_frequency=ref['critical_frequency'])
    out=result['modes'];assert out['converged'] and out['diagnostics']['finite_dimension']==4
    assert out['diagnostics']['base_residual']<1e-8
    actual=np.array([complex(*m['eigenvalue'])/scale for m in out['modes']])
    i,j=linear_sum_assignment(abs(actual[:,None]-ref['roots'][None,:]));close(actual[i],ref['roots'][j])
    assert len(actual)==4
    for mode in out['modes']:
        lam=complex(*mode['eigenvalue'])/scale
        tip=mode['output']['nodes'][-1];theta=rotation.T@as_complex(tip['rotation'])
        norm=np.linalg.norm(theta);assert norm>1e-10
        close(theta[0]/norm,0.,1e-7);close(as_complex(tip['displacement'])/norm,np.zeros(3),1e-7)
        residual=((INERTIA*lam*lam+ref['damping']*lam+ref['k'])*np.eye(2)+(-ref['spin']*lam-ref['circulatory'])*J)@theta[1:]
        ratio=float(np.linalg.norm(residual)/(norm*max(ref['k'],abs(INERTIA*lam*lam))))
        mode_equation=max(mode_equation,ratio);assert ratio<2e-6,(spec['name'],ratio)
    if 'frequency' in result:
        for p in result['frequency']['samples']:
            w=p['omega']/scale
            matrix=(ref['k']-INERTIA*w*w+1j*ref['damping']*w)*np.eye(2)+(-1j*ref['spin']*w-ref['circulatory'])*J
            transfer=np.linalg.inv(matrix)
            for index,r in enumerate(p['responses']):
                theta=as_complex(r['output']['nodes'][-1]['rotation']);expected=rotation@np.r_[0.,transfer[:,index]]
                close(theta,expected,2e-7)
                aero=ref['circulatory']*J@transfer[:,index]-1j*w*ref['damping']*transfer[:,index]
                moment=rotation@np.r_[0.,np.eye(2)[:,index]+aero]
                close(as_complex(r['output']['global']['engine_moment']),moment,2e-7)
    continuum=reference(spec,True)['roots'];i,j=linear_sum_assignment(abs(actual[:,None]-continuum[None,:]))
    error=float(np.max(abs(actual[i]-continuum[j])/np.maximum(1.,abs(continuum[j]))))
    return dict(independent_scalar_checks=checks,maximum_scaled_error=maximum,maximum_mode_equation_residual=mode_equation,continuum_root_relative_error=error)


def physical(result):
    values=[]
    if 'stability' in result:
        # Adaptive refinement points may differ slightly between platforms;
        # each is checked independently against its own physical speed above.
        for p in result['stability']['points'][:2]:
            values.append(p['value'])
            if p.get('result'):values.extend(np.array(sorted([m['eigenvalue'] for m in p['result']['modes']],key=lambda v:(abs(v[1]),v[1]))).ravel())
        for b in result['stability']['boundaries']:values.extend([b['value'],*b['eigenvalue']])
    else:
        # Eigenvector phase/normalization may differ by platform. Compare invariant
        # poles here; the independent modal equation checks the physical shapes.
        values.extend(np.array(sorted([m['eigenvalue'] for m in result['modes']['modes']],key=lambda v:(abs(v[1]),v[1]))).ravel())
        if 'frequency' in result:
            for p in result['frequency']['samples']:
                for r in p['responses']:
                    for v in [r['output']['nodes'][-1]['rotation'],r['output']['global']['engine_moment']]:values.extend(v['real']);values.extend(v['imag'])
    return np.array(values)


def main():
    paths=sorted((ROOT/'openswing').glob('*.py'))+[Path(__file__).absolute(),ROOT/'examples/whirl-flutter.asw']
    hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    key=hashlib.sha256(json.dumps(hashes,sort_keys=True).encode()).hexdigest();cache=ROOT/'.reference/whirl'/key;cache.mkdir(parents=True,exist_ok=True)
    blade=[]
    for spin in (1,-1):
        direct=blade_derivatives(spin);s=dict(spin_sign=spin);ref=reference(s)
        expected=np.c_[ref['circulatory']/DESIGN_SPEED*np.eye(2),-ref['damping']*np.eye(2)]
        error=float(np.max(abs(direct[4:6]-expected)));assert error<2e-8
        blade.append(dict(spin_sign=spin,maximum_moment_derivative_error=error,derivatives=direct.tolist()))
    cases=[]
    for spec in specifications():
        path=cache/(spec['name']+'.json');started=time.monotonic()
        if path.exists():result=json.loads(path.read_text())
        else:
            result=compute(spec);path.write_text(json.dumps(result,allow_nan=False))
        checks=verify(spec,result);cases.append(dict(specification=spec,result=result,checks=checks));print(spec['name'],checks,'seconds',time.monotonic()-started,flush=True)
    errors=[cases[i]['checks']['continuum_root_relative_error'] for i in range(3)]
    assert errors[1]<.27*errors[0] and errors[2]<.27*errors[1],errors
    report=dict(description='Original two-axis elastic rotor mount. Independent beam flexibility, gyroscopic mechanics, direct blade-force quadrature, coupled modes, forced response and frozen-coefficient whirl boundary. No ASWING executable or measured-rotor comparison is claimed.',source_sha256=hashes,python=platform.python_version(),numpy=np.__version__,scipy=scipy.__version__,blade_integration=blade,cases=cases)
    (ROOT/'docs/validation/whirl.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print('completed',len(cases),'cases;',sum(c['checks']['independent_scalar_checks'] for c in cases),'scalar checks;',len(hashes),'source hashes',flush=True)


if __name__=='__main__':main()
