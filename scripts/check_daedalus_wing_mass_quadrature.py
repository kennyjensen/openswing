"""Bounded saved-motion check of endpoint versus continuous wing mass loads."""
import argparse
import json
import os
from pathlib import Path
import resource
import signal
import sys
import time
import traceback

from check_daedalus_load_sensitivity import ROOT,LIMITS,read,write,pin,utc

STUDY=ROOT/'artifacts/daedalus-wing-inertia-20261113'


def run(folder,args):
    import numpy as np
    from wing_inertia_reference import evaluate
    from wing_mass_integral_reference import integrate
    def record(value):return dict(real=value.real.tolist(),imag=value.imag.tolist())
    # Analytic straight uniform beam: both frame and elastic rigid rotations
    # must recover m L^2/12, rather than an endpoint-lumped m L^2/4 or twice it.
    fixture=dict(a=np.array([0]*4),b=np.array([1]*4),node=np.array([0,1,0,1]),
        frames=np.repeat(np.eye(3)[None],4,axis=0),ds=np.array([4.]*4),
        weight_density=np.array([2.,2.,0.,0.]),cg_local=np.zeros((4,3)),
        icc_weight_density=np.zeros(4),inn_weight_density=np.zeros(4),g_constant=np.array(1.),
        node_positions=np.array([[0.,-2.,0.],[0.,2.,0.]]),gravity=np.zeros(3),
        base_velocity=np.zeros(3),moment_reference=np.zeros(3))
    omega=3.;rate=np.array([1.,0.,2.]);zz=np.zeros((2,3));z3=np.zeros(3)
    controls=[]
    for frame in (True,False):
        velocity=zz if frame else np.cross(rate,fixture['node_positions'])
        rates=zz if frame else np.broadcast_to(rate,zz.shape)
        motion=dict(displacement=velocity/(1j*omega),rotation=rates/(1j*omega),
            velocity=velocity,rates=rates,frame_velocity=z3,frame_rates=rate if frame else z3,
            reference_displacement=z3)
        integrated,_=integrate(fixture,motion,omega,4)
        endpoint=evaluate(fixture,motion['displacement'],motion['rotation'],velocity,rates,z3,
                          motion['frame_rates'],omega,z3)['wrenches'].sum(axis=0)
        analytic=np.r_[z3,-1j*omega*(8*4**2/12)*rate]
        errors=dict(integral=float(max(abs(integrated.sum(axis=0)-analytic))),
                    endpoint=float(max(abs(endpoint-analytic))))
        assert max(errors.values())<1e-10
        controls.append(dict(motion='frame_rotation' if frame else 'elastic_rigid_rotation',errors=errors))
    cases=[];saved={}
    for case in ('slow','dip'):
        data=dict(np.load(STUDY/case/'fixture.npz'));motion=dict(np.load(STUDY/case/'arrays.npz'))
        meta=read(STUDY/case/'result.json');omega=2*np.pi*meta['frequency_hz']
        low,mass=integrate(data,motion,omega,4);high,highmass=integrate(data,motion,omega,8)
        error=float(np.max(abs(high-low)));assert error<2e-10,error
        np.testing.assert_allclose(mass,highmass,atol=1e-12,rtol=1e-12)
        np.testing.assert_allclose(mass*float(data['g_constant']),meta['wing_weight_lb'],atol=2e-12,rtol=1e-12)
        original=motion['wrenches'].sum(axis=0);continuous=high.sum(axis=0);difference=continuous-original
        cases.append(dict(case=case,frequency_hz=meta['frequency_hz'],quadrature_error=error,
            original=record(original),continuous=record(continuous),difference=record(difference),
            yaw_moment_complex_difference_percent=float(100*abs(difference[5])/abs(original[5])),
            roll_moment_complex_difference_percent=float(100*abs(difference[3])/abs(original[3]))))
        saved[case+'_integral_parts']=high;saved[case+'_endpoint_parts']=motion['wrenches']
    np.savez_compressed(folder/'arrays.npz',**saved)
    result=dict(controls=controls,cases=cases,
        qualification='Prescribed harmonic motion, linear endpoint property/centerline interpolation and geodesic frame interpolation. The direct distributed moment integral includes finite-span inertia geometrically, with no second Eq80 correction. These are conditional wrench differences, not changes to the coupled Bode response or new native validation passes.')
    print(json.dumps(result),flush=True);return result


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--tag',required=True);args=parser.parse_args()
    folder=STUDY/args.tag;folder.mkdir(exist_ok=False);(folder/'runner.py').write_bytes(Path(__file__).read_bytes())
    inputs=[Path(__file__),ROOT/'scripts/wing_mass_integral_reference.py',ROOT/'scripts/wing_inertia_reference.py',
        ROOT/'scripts/fin_apparent_reference.py',ROOT/'scripts/check_daedalus_load_sensitivity.py',ROOT/'docs/validation/ISAE_STATUS.md']
    inputs += [STUDY/case/name for case in ('slow','dip') for name in ('fixture.npz','arrays.npz','result.json','terminal.json')]
    pins={str(p):pin(p) for p in inputs}
    write(folder/'plan.json',dict(observed_utc=utc(),limits=LIMITS,inputs_sha256=pins,
        allocator_environment={key:os.environ.get(key) for key in ('MALLOC_MMAP_THRESHOLD_','MALLOC_TRIM_THRESHOLD_')}))
    started=time.monotonic();sys.stdout.flush();pid=os.fork()
    if pid==0:
        code=0
        for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[key]='1'
        resource.setrlimit(resource.RLIMIT_AS,(LIMITS['address_space_bytes'],)*2);resource.setrlimit(resource.RLIMIT_CPU,(LIMITS['cpu_seconds'],)*2)
        with (folder/'stdout.log').open('x') as out,(folder/'stderr.log').open('x') as err:
            os.dup2(out.fileno(),1);os.dup2(err.fileno(),2)
            try:write(folder/'result.json',run(folder,args))
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
