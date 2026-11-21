"""Independent Biot-Savart quadrature of SA-12 physical and image vortices."""
from pathlib import Path
import hashlib, importlib.util, json, sys
import numpy as np
from scipy.integrate import quad, quad_vec

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'scripts'))
from openswing.asw import parse_asw
from openswing.geometry import model_meshes
spec=importlib.util.spec_from_file_location('sa12',ROOT/'scripts/verify-isae-sa12.py')
sa12=importlib.util.module_from_spec(spec);spec.loader.exec_module(sa12)
D=ROOT/'docs/validation'


def quadrature(target,a,b,direction,gamma,exclude=None):
    selected=np.arange(len(gamma))!=exclude if exclude is not None else np.ones(len(gamma),dtype=bool)
    delta=b-a
    def integrand(f):
        r=target-a[selected]-f*delta[selected]
        return gamma[selected,None]*np.cross(delta[selected],r)/np.linalg.norm(r,axis=1)[:,None]**3/(4*np.pi)
    bound,error=quad_vec(integrand,0.,1.,epsabs=1e-10,epsrel=1e-11,limit=2000)
    total=bound.sum(axis=0);wake_error=0.
    for k in range(len(gamma)):
        for node,sign in [(b[k],1.),(a[k],-1.)]:
            r=target-node;along=float(r@direction);h=float(np.linalg.norm(r-along*direction));assert h>0
            value,err=quad(np.cos,np.arctan2(-along,h),np.pi/2,epsabs=1e-12,epsrel=1e-12)
            coefficient=sign*gamma[k]*np.cross(direction,r)/(4*np.pi*h*h)
            total+=coefficient*value;wake_error+=np.linalg.norm(coefficient)*err
    return total,float(error+wake_error)


def main():
    sources=json.loads((D/'isae-sa12-sources.json').read_text())
    sample=json.loads((D/'isae-sa12-wasm-native.json').read_text());p=sample['provenance']
    assert p['modules']=={f.name:sa12.sha(f) for f in (ROOT/'openswing').glob('*.py')}
    assert p['source_report_sha256']==sa12.sha(D/'isae-sa12-sources.json')
    folder=ROOT/'.reference/isae-sa12-runs'/hashlib.sha256(json.dumps(p,sort_keys=True).encode()).hexdigest()
    assert json.loads((folder/'identity.json').read_text())==p
    rows=[]
    for case in sources['models']:
        model=parse_asw(case['source']);mesh,=model_meshes(model,100)
        assert np.allclose(mesh.r0[:,[0,2]],0) and np.allclose(mesh.r1[:,[0,2]],0)
        assert np.all(model.beams[0].value('Xax',mesh.tm)==.25)
        for label in ['05','2']:
            for pose in ['level_freestream','zero_attitude']:
                request=sa12.specification(case,label,100,5.,pose=pose)
                path=folder/(sa12.key(request)+'.json');row=json.loads(path.read_text());assert row['status']=='computed'
                r=row['result'];profiles=r['profiles'];gamma=np.array([v['circulation'] for v in profiles])
                assert np.allclose([v['t'] for v in profiles],mesh.tm)
                theta=np.deg2rad(5. if pose=='level_freestream' else 0.)
                normal=np.array([-np.sin(theta),0.,np.cos(theta)]);height=request['height']
                # Explicit reflection in n.r+h=0; no production image helper.
                reflect=lambda x:x-2*(x@normal+height)[...,None]*normal
                direction=np.array([np.cos(np.deg2rad(5.)),0.,np.sin(np.deg2rad(5.))])
                image_direction=direction-2*(direction@normal)*normal
                a,b=mesh.r0,mesh.r1;ia,ib=reflect(a),reflect(b)
                checks=[]
                for index in [0,25,49]:
                    point=np.array(profiles[index]['position'])
                    assert np.max(abs(point-mesh.rm[index]))<1e-12
                    real,er=quadrature(point,a,b,direction,gamma,index)
                    image,ei=quadrature(point,ia,ib,image_direction,-gamma)
                    velocity=35.76*direction+real+image
                    actual=np.array(profiles[index]['relative_velocity'])
                    difference=float(np.max(abs(velocity-actual)));assert difference<2e-8,(request,index,difference)
                    checks.append(dict(receiver_index=index,position=point.tolist(),production_velocity=actual.tolist(),
                        independent_velocity=velocity.tolist(),physical_induced_velocity=real.tolist(),
                        image_induced_velocity=image.tolist(),maximum_component_error=difference,estimated_quadrature_error=er+ei))
                boundary=[]
                for x,y in [(-.2,-.3),(.1,.1),(.3,.4)]:
                    point=np.array([x,y,0.]);point-=normal*(point@normal+height)
                    real,er=quadrature(point,a,b,direction,gamma)
                    image,ei=quadrature(point,ia,ib,image_direction,-gamma)
                    leakage=float((real+image)@normal);assert abs(leakage)<2e-8
                    boundary.append(dict(point=point.tolist(),induced_normal_velocity=leakage,
                        freestream_normal_velocity=float(35.76*direction@normal),estimated_quadrature_error=er+ei))
                rows.append(dict(specification=request,cache_sha256=sa12.sha(path),checks=checks,boundary_checks=boundary,
                    circulation=gamma.tolist(),source_a=a.tolist(),source_b=b.tolist()))
                print(case['name'],label,pose,'PASS',flush=True)
    assert len(rows)==8
    out=dict(status='PASS_INDEPENDENT_VELOCITY_CHECK_NOT_EXPERIMENTAL_VALIDATION',rows=rows,
        modules=p['modules'],source_report_sha256=p['source_report_sha256'],script_sha256=sa12.sha(Path(__file__)),
        compute_script_sha256=p['script_sha256'],maximum_velocity_difference=max(c['maximum_component_error'] for r in rows for c in r['checks']),
        maximum_induced_boundary_normal_speed=max(abs(c['induced_normal_velocity']) for r in rows for c in r['boundary_checks']),
        method='Numerical finite-segment and semi-infinite-ray Biot-Savart integrals, independent explicit reflection and negative image circulation, zero PG and same-surface zero core.',
        limitations=['Geometry and circulation come from the production mesh and converged state; this is not an independent circulation solution.',
            'Checks verify 24 force-point velocities and 24 image-boundary points. They do not validate flap section properties, pose reconstruction or measured force agreement.',
            'Only the board-parallel setup has zero total normal speed at a stationary ground board. In the zero-pitch diagnostic, images cancel induced normal velocity but the prescribed freestream has a normal component.'])
    (D/'isae-sa12-velocity.json').write_text(json.dumps(out,indent=2)+'\n')


if __name__=='__main__':main()
