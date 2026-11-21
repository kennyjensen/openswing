"""Independent beam-frequency and 2D lag checks of the unsteady residual.

This verification-only descriptor pencil has no general mode selection, flight
states, controls, root tracking, or flutter solver. It is not a product API.
"""
import hashlib
import json
from pathlib import Path
import platform
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
import scipy
from scipy.linalg import eig
from openswing.asw import parse_asw
from openswing.aero import FlightCondition,evaluate_aerodynamics
from openswing.network import StaticNetwork


def beam_mode(panels,damping):
    source=f'''Name
Uniform cantilever residual verification
End
Unit
L 1 m
T 1 s
F 1 N
End
Constant
9.80665 1.225 340.294
End
Reference
2 1 2
End
Ground
1 0 0
End
Beam 1
Euler Bernoulli beam
t y EIcc mg tdeps
0 0 100 19.6133 {damping}
2 2 100 19.6133 {damping}
End
'''
    net=StaticNetwork(parse_asw(source),panels,None,[0,0,0],[])
    x=np.zeros(net.size);z=np.zeros((net.nn,3));nk=6*net.nn
    def residual(state,velocity,acceleration):
        v=velocity.reshape(net.nn,6);a=acceleration.reshape(net.nn,6)
        return net.residual(state,elastic_motion=(net.L*v[:,:3],v[:,3:],net.L*a[:,:3],a[:,3:]))
    zero=np.zeros(nk);h=1e-5
    k=np.empty((net.size,net.size));c=np.empty((net.size,nk));mass=np.empty_like(c)
    for i in range(net.size):
        step=np.zeros(net.size);step[i]=h
        k[:,i]=(residual(x+step,zero,zero)-residual(x-step,zero,zero))/(2*h)
    for i in range(nk):
        step=np.zeros(nk);step[i]=h
        c[:,i]=(residual(x,step,zero)-residual(x,-step,zero))/(2*h)
        mass[:,i]=(residual(x,zero,step)-residual(x,zero,-step))/(2*h)
    # R=K x+C v+B vdot and xkin_dot-v=0, retaining rigid constraints.
    n=net.size+nk;A=np.zeros((n,n));E=np.zeros((n,n))
    A[:net.size,:net.size]=k;A[:net.size,net.size:]=c
    A[net.size:,net.size:]=-np.eye(nk)
    E[:net.size,net.size:]=mass;E[net.size:,:nk]=np.eye(nk)
    values,vectors=eig(-A,E)
    selected=np.flatnonzero(np.isfinite(values)&(values.imag>1e-4))
    index=min(selected,key=lambda i:abs(values[i]));value=values[index];vector=vectors[:,index]
    eigen_residual=float(np.linalg.norm((A+value*E)@vector)/((np.linalg.norm(A)+abs(value)*np.linalg.norm(E))*np.linalg.norm(vector)))
    omega=1.875104068711961**2*np.sqrt(100/(2*2**4))
    expected=-.5*damping*omega**2+1j*omega*np.sqrt(1-(damping*omega/2)**2)
    assert eigen_residual<1e-12
    return dict(panels=panels,damping_time=damping,
                root=[float(value.real),float(value.imag)],analytic_root=[float(expected.real),float(expected.imag)],
                relative_root_error=float(abs(value-expected)/abs(expected)),eigenpair_residual=eigen_residual)


def lag_cases():
    text=Path('examples/rectangular.asw').read_text()
    text=text[:text.index('t dCLdF1')]+'End\n'
    text=text.replace('6 0 6 0','100000 0 100000 0').replace('6 .008','100000 .008').replace('.008','0')
    condition=FlightCondition(alpha=0,mach=0,stall=False)
    net=StaticNetwork(parse_asw(text),4,condition,[0,0,0],[])
    eps=1e-4;one=np.ones(net.ng);zero=np.zeros(net.ng)
    a=evaluate_aerodynamics(net.model,condition,net.meshes,eps*one,circulation_rate=zero)
    b=evaluate_aerodynamics(net.model,condition,net.meshes,zero,circulation_rate=eps*one)
    ar=np.mean(a['circulation_residual'])/eps;br=np.mean(b['circulation_residual'])/eps
    lf=a['force'][2]/eps;lr=b['force'][2]/eps
    out=[]
    for k in [.001,.01,.1,1.,10.,100.]:
        omega=2*condition.speed*k
        value=ar/(ar+1j*omega*br)*(lf+1j*omega*lr)/lf
        expected=(1+2j*k)/(1+4j*k)
        error=float(abs(value-expected))
        assert error<2e-5
        out.append(dict(reduced_frequency=k,lift_transfer=[float(value.real),float(value.imag)],
            analytic_transfer=[float(expected.real),float(expected.imag)],absolute_error=error))
    return out


if __name__=='__main__':
    cases=[]
    for damping in [0.,.02]:
        subset=[]
        for panels in [4,8,16]:
            case=beam_mode(panels,damping);cases.append(case);subset.append(case)
            print(json.dumps(case),flush=True)
        assert subset[-1]['relative_root_error']<.005
        assert subset[-1]['relative_root_error']<.3*subset[-2]['relative_root_error']
    sources=[Path('scripts/verify-unsteady.py'),*sorted(Path('openswing').glob('*.py'))]
    report=dict(description='Verification of an instantaneous unsteady residual, not a time integrator or general eigenmode/flutter implementation.',
        versions=dict(python=platform.python_version(),numpy=np.__version__,scipy=scipy.__version__),
        source_sha256={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},
        beam_modes=cases,circulation_lag=lag_cases(),
        limitations=['Linear straight uniform clamped beam only; no general aeroelastic mode validation.',
            'Empirical lag is the published rational approximation, not exact Theodorsen response.',
            'No ASWING executable or experimental comparison.'])
    Path('docs/validation/unsteady-residual.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
