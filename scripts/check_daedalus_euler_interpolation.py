"""Conditional absolute-Euler interior frames with consistent time derivatives.

No production algorithm is changed. The published nodal charts and Glauert
fractions define a possible interpolant, not an authenticated ASWING choice.
Diagnostic checkpoints carry an extra identity key rejected by production.
"""
import argparse
from pathlib import Path
from check_daedalus_load_sensitivity import ROOT,SOURCE,read
from daedalus_bounded_job import run

STUDY=ROOT/'artifacts/daedalus-euler-interpolation-20261114'
BASE=SOURCE/'trim-6.7-1/state.json'
TAG='absolute-euler-linear-interior-v1'
DIP=1.15737773741517


def frame(q,body):
    import numpy as np
    from check_daedalus_rate_interpolation import euler_frame
    q=np.asarray(q)
    return euler_frame(q.reshape(-1,3),body).reshape(q.shape[:-1]+(3,3))


def field(Ra,Rb,wa,wb,aa,ab,fraction,body):
    """R, spatial omega and its body-coordinate derivative at fixed fraction."""
    import numpy as np
    from openswing.source_discrete import angles_from_frame,angle_matrix,_increments
    from openswing.source_dynamics import angle_matrix_rate
    qa,qb=angles_from_frame(Ra,body),angles_from_frame(Rb,body)
    f=np.asarray(fraction)[...,None];mid=qa+f*_increments(qa,qb);R=frame(mid,body)
    if not any(np.any(v) for v in (wa,wb,aa,ab)):
        return R,np.zeros(R.shape[:-1]),np.zeros(R.shape[:-1])
    ka,kb=angle_matrix(qa,body),angle_matrix(qb,body)
    A,B=Ra@ka,Rb@kb
    da=np.linalg.solve(A,wa[...,None])[...,0];db=np.linalg.solve(B,wb[...,None])[...,0]
    def mv(m,v):return np.einsum('...ij,...j->...i',m,v)
    # d(R K qdot)/dt = R(K qddot + Kdot qdot): the omitted term
    # omega cross (R K qdot) = omega cross omega vanishes identically.
    dda=np.linalg.solve(A,(aa-mv(Ra@angle_matrix_rate(qa,da,body),da))[...,None])[...,0]
    ddb=np.linalg.solve(B,(ab-mv(Rb@angle_matrix_rate(qb,db,body),db))[...,None])[...,0]
    dm=da+f*(db-da);ddm=dda+f*(ddb-dda);km=angle_matrix(mid,body)
    return R,mv(R@km,dm),mv(R,mv(km,ddm)+mv(angle_matrix_rate(mid,dm,body),dm))


class EulerInterpolation:
    """Scoped hooks only on explicitly tagged source-airflow networks."""
    def __enter__(self):
        import numpy as np
        import openswing.equilibrium_state as equilibrium
        from openswing.network import StaticNetwork
        from openswing.local_motion import NetworkMotion
        from openswing.source_discrete import angles_from_frame,_increments
        self.old_mesh=StaticNetwork.deformed_meshes;self.old_sample=NetworkMotion.sample;self.old_identity=equilibrium.identity
        old_mesh,old_sample,old_identity=self.old_mesh,self.old_sample,self.old_identity
        def meshes(n,r,Q,geometry):
            result=old_mesh(n,r,Q,geometry)
            if getattr(n,'diagnostic_interior',None)!=TAG:return result
            for mesh in result:
                sl=n.beam_elements[mesh.beam.index];f=n.fractions[mesh.beam.index];body=not mesh.beam.lifting
                qa=angles_from_frame(geometry[2][sl],body);qb=angles_from_frame(geometry[3][sl],body)
                mesh.frames=frame(qa+f[:,None]*_increments(qa,qb),body)
            return result
        def sample(motion,beam,fraction,*,material=False):
            value,rotation,kd=old_sample(motion,beam,fraction,material=material)
            n=motion.network
            if material or getattr(n,'diagnostic_interior',None)!=TAG:return value,rotation,kd
            assert n.source_airflow and not np.any(n.damping_times)
            sl=n.beam_elements[beam];body=not next(m.beam.lifting for m in n.meshes if m.beam.index==beam)
            f=np.broadcast_to(fraction,(len(motion.pa[sl]),)+np.shape(fraction)[1:])
            def shaped(v):
                v=v[sl]
                return v[:,None] if f.ndim==2 else v
            Ra,Rb=map(shaped,(motion.ra,motion.rb))
            wa,wb,aa,ab=map(shaped,(motion.rates[n.a],motion.rates[n.b],motion.rate_derivative[n.a],motion.rate_derivative[n.b]))
            absolute,value.rates,value.rate_derivative=field(Ra,Rb,wa,wb,aa,ab,f,body)
            zero=np.zeros_like(wa)
            jig,_,_=field(shaped(n.R0a),shaped(n.R0b),zero,zero,zero,zero,f,body)
            # Nonmaterial callers in this source policy consume only LocalMotion.
            # The third return is not a geodesic arc derivative for this method.
            return value,absolute@jig.swapaxes(-1,-2),None
        def identity(n):
            result=old_identity(n)
            if getattr(n,'diagnostic_interior',None)==TAG:result['diagnostic_interior']=TAG
            return result
        StaticNetwork.deformed_meshes=meshes;NetworkMotion.sample=sample;equilibrium.identity=identity
        return self
    def __exit__(self,*exc):
        import openswing.equilibrium_state as equilibrium
        from openswing.network import StaticNetwork
        from openswing.local_motion import NetworkMotion
        StaticNetwork.deformed_meshes=self.old_mesh;NetworkMotion.sample=self.old_sample;equilibrium.identity=self.old_identity


def setup(seed=None):
    import numpy as np
    import check_daedalus_source_operator as source
    from openswing.asw import parse_asw
    from openswing.source_airflow import SourceAirflowNetwork
    from openswing.equilibrium_state import restore,restore_physical_fields,identity
    from openswing.time_state import read_condition
    original=read(BASE);packet=original if seed is None else read(seed);launch=packet['launch']
    config=read(source.PROJECT)['cases'][0]['configuration']
    model=parse_asw(config['source'],beam_interpolation='drela-segspl-v1')
    panels=dict(default=16,beams={k:dict(nodes=v[0]) for k,v in original['identity']['stations'].items()})
    n=SourceAirflowNetwork(model,panels,read_condition(launch['condition']),launch['gravity'],launch['loads'],
        operating_constraints=launch['released_constraints'],strut_mode=launch['strut_mode'],mesh_recipe='physical-breaks-v1',steady_trim=True)
    n.diagnostic_interior=TAG
    assert (n.nn,n.ne,n.ng)==(108,103,82) and not np.any(n.damping_times)
    current=identity(n);assert current.pop('diagnostic_interior')==TAG
    assert current==original['identity']
    if seed is not None:assert packet['identity']['diagnostic_interior']==TAG
    return n,restore_physical_fields(n,packet) if seed is None else restore(n,packet)


def kinematics(folder,args):
    import numpy as np
    from openswing.source_discrete import angle_matrix
    from openswing.source_dynamics import angle_matrix_rate
    checks=[];records={}
    def vee(m):return np.stack([m[...,2,1]-m[...,1,2],m[...,0,2]-m[...,2,0],m[...,1,0]-m[...,0,1]],axis=-1)/2
    f=np.array([0.,.17,.5,.83,1.])
    for body in (False,True):
        qa=np.array([.31,.18,-.22]);qb=np.array([.52,-.14,.16])
        va=np.array([.6,-.3,.2]);vb=np.array([-.2,.4,.8])
        aa=np.array([.07,-.16,.31]);ab=np.array([-.13,.22,-.12])
        def rotations(t):
            a=qa+t*va+t*t/2*aa;b=qb+t*vb+t*t/2*ab
            return frame(a,body),frame(b,body),frame(a+f[:,None]*(b-a),body)
        Ra,Rb,R=rotations(0)
        wa=Ra@angle_matrix(qa,body)@va;wb=Rb@angle_matrix(qb,body)@vb
        ada=Ra@(angle_matrix(qa,body)@aa+angle_matrix_rate(qa,va,body)@va)
        adb=Rb@(angle_matrix(qb,body)@ab+angle_matrix_rate(qb,vb,body)@vb)
        actual,w,accel=field(Ra,Rb,wa,wb,ada,adb,f,body)
        np.testing.assert_allclose(actual,R,atol=2e-15,rtol=0)
        np.testing.assert_allclose(w[[0,-1]],[wa,wb],atol=2e-14,rtol=0)
        np.testing.assert_allclose(accel[[0,-1]],[ada,adb],atol=2e-14,rtol=0)
        for h in (.0004,.0008):
            sample=[rotations(t) for t in (-2*h,-h,0.,h,2*h)]
            node_errors=[]
            for index,expected_rate,expected_accel in [(0,wa,ada),(1,wb,adb),(2,w,accel)]:
                rm2,rm1,r0,rp1,rp2=[row[index] for row in sample]
                d=(rm2-8*rm1+8*rp1-rp2)/(12*h)
                dd=(-rp2+16*rp1-30*r0+16*rm1-rm2)/(12*h*h)
                spin=d@np.swapaxes(r0,-1,-2)
                omega=vee(spin);alpha=vee(dd@np.swapaxes(r0,-1,-2)-spin@spin)
                error=float(max(abs(omega-expected_rate).ravel()));error2=float(max(abs(alpha-expected_accel).ravel()))
                assert error<2e-10 and error2<3e-7,(body,h,index,error,error2)
                node_errors.append(dict(location=['first_node','second_node','interior'][index],rate_error=error,acceleration_error=error2))
                records[f'{body}-{h}-{index}-rate']=omega
                records[f'{body}-{h}-{index}-acceleration']=alpha
            checks.append(dict(body=body,width=h,checks=node_errors))
        # Exercise the multidimensional fractions used by body quadrature.
        shaped=field(Ra[None,None],Rb[None,None],wa[None,None],wb[None,None],ada[None,None],adb[None,None],f[None,:],body)
        for x,y in zip(shaped,(R,w,accel)):np.testing.assert_allclose(x[0],y,atol=2e-14,rtol=0)
    np.savez_compressed(folder/'arrays.npz',**records)
    return dict(checks=checks,endpoint_checks=True,quadrature_shape_checks=True,
        qualification='Independent time differences of explicit rotation trajectories validate endpoint and interior angular velocities/accelerations at two widths. No aircraft solve or native interpolation claim.')


def trim(folder,args):
    import check_daedalus_wing_peak_mass as driver
    driver.setup=setup
    with EulerInterpolation():result=driver.trim(folder,args)
    result['qualification']='Physical trim with conditional Euler interior orientation; no residual offset. Original tangent used only as an accelerator; distinct diagnostic checkpoint identity.'
    return result


def response(folder,args):
    import check_daedalus_wing_peak_mass as driver
    driver.setup=setup;driver.STUDY=STUDY
    with EulerInterpolation():result=driver.retrim_step(folder,args)
    result['qualification']='Full 2044-state response of physically retrimmed Euler-interpolation diagnostic with consistent angular rates and accelerations. Original descriptor is only a preconditioner, not a rank certificate.'
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage',choices=['kinematics','trim','response']);parser.add_argument('--tag',required=True)
    parser.add_argument('--seed');parser.add_argument('--source');parser.add_argument('--frequency',type=float,default=DIP)
    parser.add_argument('--width',type=float,default=.002);parser.add_argument('--state',choices=['state','next_state'],default='next_state')
    parser.add_argument('--iterations',type=int,choices=[1,2],default=2)
    args=vars(parser.parse_args())
    inputs=[ROOT/name for name in ('examples/dae.asw','examples/dae-cruise-physical-mesh-project.json','docs/validation/ISAE_STATUS.md',
        'docs/validation/aswing-authoritative-sources.json','reference/aswing-authoritative-20261108/drela-aswing-steady.pdf',
        'reference/aswing-authoritative-20261108/drela-aswing-unsteady.pdf')]
    inputs+=list((ROOT/'openswing').glob('*.py'))
    inputs += [ROOT/'scripts'/name for name in ('check_daedalus_rate_interpolation.py','check_daedalus_wing_peak_mass.py',
        'check_daedalus_measured_mass.py','check_daedalus_mesh_zeros.py','check_daedalus_mesh_residual.py',
        'check_daedalus_structural_resolution.py','check_daedalus_source_operator.py')]
    inputs += [BASE,SOURCE/'mass-6.7/layout.json',SOURCE/'trim-6.7-1/trim-tangent.npz']
    folders=[SOURCE/'assembled-6.7']
    if args['seed']:inputs += [Path(args['seed']).resolve()]
    if args['source']:folders += [STUDY/args['source']]
    for folder in folders:inputs += [p for p in folder.iterdir() if p.suffix in ('.json','.npz')]
    run(STUDY,args['tag'],inputs,globals()[args['stage']],args,__file__)


if __name__=='__main__':main()
