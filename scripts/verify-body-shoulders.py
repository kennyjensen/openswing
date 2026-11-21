"""Body-radius jumps: independent weak integrals, mechanics and runtime replay."""
import hashlib,json,platform,sys
from copy import deepcopy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import numpy as np
import scipy
from scipy.integrate import quad_vec
from openswing.asw import parse_asw
from openswing.bridge import dispatch
from openswing.time_state import checkpoint,resume_time
from openswing.flow_survey import survey


def step_source(left=.1,right=.3,width=0,scale=1):
    a,b=2-width/2,2+width/2
    radii=f'0 {left}\n2 {left}\n2 {right}\n4 {right}' if not width else f'0 {left}\n{a} {left}\n{a} {left}\n{b} {right}\n{b} {right}\n4 {right}'
    return f'''Name
Original body shoulder verification
End
Unit
L 1 {'cm' if scale==100 else 'm'}
T 1 s
F 1 N
End
Constant
{9.80665*scale} {1.225/scale**4} {340.294*scale}
End
Reference
{4*scale**2} {scale} {4*scale}
End
Ground
1 0 0
End
Beam 1
Stepped body
 t x
0 0
4 {4*scale}
 t radius
{radii}
 t Cdf Cdp
0 0 0
4 0 0
End
'''


def specifications():
    source=(ROOT/'examples/stepped-body.asw').read_text();out=[]
    for name,scale in [('step_pg',1),('centimeter',100)]:
        out.append(dict(name=name,kind='rigid',source=step_source(.1*scale,.3*scale,scale=scale),scale=scale,
            condition=dict(speed=17*scale,alpha=13,beta=-7,mach=.35),panels=16,
            segments=[[0,2*scale,.1*scale,.1*scale],[2*scale,4*scale,.3*scale,.3*scale]],jumps=[[2*scale,.1*scale,.3*scale]]))
    for name,kind in [('closed','rigid'),('ground','rigid'),('elastic','mounted'),('derivative','mounted'),('time','time')]:
        c=dict(speed=17,alpha=11,mach=0)
        if name=='ground':c=dict(speed=13,alpha=0,mach=.3,ground_effect=1,position_earth=[0,0,2])
        if name=='elastic':c=dict(speed=5,alpha=1,mach=0)
        if name=='time':c=dict(speed=10,alpha=0,mach=0,gust=dict(type='expression',components=['0','0','.2*sin(3*t)']))
        text=source if name!='elastic' else source.replace(' t Cdf Cdp',' t EIcc EInn GJ EA\n0 10000 10000 10000 10000000\n4 10000 10000 10000 10000000\n t Cdf Cdp')
        out.append(dict(name=name,kind=kind,source=text,scale=1,condition=c,panels=4 if kind!='rigid' else 16,
            segments=[[0,1,0,0],[1,3,.2,.2],[3,4,0,0]],jumps=[[1,0,.2],[3,.2,0]]))
    out.append(dict(name='smooth_limit',kind='smooth',source=step_source(),scale=1,condition=dict(speed=17,alpha=13,beta=-7,mach=.35),panels=16,
        segments=[[0,2,.1,.1],[2,4,.3,.3]],jumps=[[2,.1,.3]]))
    return out


def axes(spec):
    c=spec['condition'];alpha,beta=np.deg2rad([c.get('alpha',5),c.get('beta',0)])
    e=np.array([np.cos(alpha)*np.cos(beta),-np.sin(beta),np.sin(alpha)*np.cos(beta)])
    pg=np.eye(3)+(1/np.sqrt(1-c['mach']**2)-1)*np.outer(e,e);xi=pg@e;length=np.linalg.norm(pg[:,0]);ell=pg[:,0]/length
    return e,pg,xi,ell,length


def reference_field(spec,points,images_only=False):
    """Adaptive physical-axis/area integration; never call the kernel's source functions."""
    points=np.asarray(points,dtype=float);e,pg,xi,ell,length=axes(spec);result=np.zeros_like(points)
    sides=[] if images_only else [(0,1)]
    flag=spec['condition'].get('ground_effect',0)
    if flag:sides.append((-2*spec['condition']['position_earth'][2],flag))
    for z,sign in sides:
        reflection=pg@np.diag([1,1,-1])@np.linalg.inv(pg) if z else np.eye(3)
        for lo,hi,ra,rb in spec['segments']:
            if ra==rb==0:continue
            def integrand(x):
                radius=ra+(rb-ra)*(x-lo)/(hi-lo);r=(points-[x,0,z])@pg.T;r2=np.sum(r*r,axis=1);den=r2+(radius/2)**2
                sigma=2*np.pi*radius*(rb-ra)/(hi-lo)*(xi@ell)
                nu=reflection@(2*np.pi*radius**2*(xi-(xi@ell)*ell)*length)
                return sign*(sigma*r/den[:,None]**1.5+(nu*r2[:,None]-3*(r@nu)[:,None]*r)/den[:,None]**2.5)@pg/(4*np.pi)
            result+=quad_vec(integrand,lo,hi,epsabs=1e-12)[0]
        for x,ra,rb in spec['jumps']:
            r=(points-[x,0,z])@pg.T;r2=np.sum(r*r,axis=1)
            result+=sign*quad_vec(lambda area:((xi@ell)*r/(r2[:,None]+area/(4*np.pi))**1.5)@pg/(4*np.pi),np.pi*ra*ra,np.pi*rb*rb,epsabs=1e-12)[0]
    return result*spec['condition']['speed']


def expected_loads(spec,time=0):
    e,*_=axes(spec);speed=spec['condition']['speed'];rho=1.225/spec['scale']**4
    jumps=spec['jumps']
    points=np.array([[j[0],0,0] for j in jumps]);velocity=np.broadcast_to(speed*e,points.shape).copy()
    if spec['condition'].get('ground_effect'):velocity+=reference_field(spec,points,images_only=True)
    if spec['name']=='time':velocity[:,2]+=.2*np.sin(3*time)
    normal=velocity.copy();normal[:,0]=0
    force=np.array([rho*v*n*np.pi*(b*b-a*a) for v,n,(_,a,b) in zip(velocity[:,0],normal,jumps)])
    return force,np.r_[force.sum(axis=0),np.cross(points,force).sum(axis=0)]


def compute(spec):
    request=dict(action='time' if spec['kind']=='time' else 'solve',mode=spec['kind'] if spec['kind'] in ('mounted','rigid') else 'rigid',source=spec['source'],condition=spec['condition'],panels=spec['panels'],gravity=[0,0,0])
    if spec['name']=='derivative':request['derivatives']=dict(parameters=['alpha'],step=1e-5)
    if spec['kind']=='time':request['time']=dict(duration=.04,dt=.02)
    before=deepcopy(request);out=dispatch(request);assert before==request
    model=parse_asw(spec['source']);scale=spec['scale'];points=np.array([[-1,.5,.7],[1.5,.6,.4],[2.2,.5,.3],[5,-.8,.6]])*scale
    saved={};extra={}
    if spec['kind']=='mounted':saved['equilibrium_state']=out['equilibrium_state']
    elif spec['kind']=='time':
        saved['checkpoint']=checkpoint(out,1);extra['resumed']=resume_time(model,saved['checkpoint'],duration=.02)
    else:saved['condition']=spec['condition'];saved['panels']=spec['panels']
    before=deepcopy(saved)
    field=survey(model,positions=points,**saved)
    plane=survey(model,plane=dict(origin=[0,0,.25*scale],u=[-scale,5*scale],v=[-scale,scale],counts=[31,15]),**saved)
    assert before==saved
    if spec['panels']==4 and spec['name']!='elastic':
        # These bodies stay rigid. Refine only the regular line-doublet
        # quadrature to distinguish its spatial error from the exact jump term.
        extra['field_mesh_refinement']=[dict(panels=n,field=survey(model,positions=points,
            condition=spec['condition'],panels=n)) for n in (8,16)]
    if spec['kind']=='smooth':
        results=[]
        for width in (.2,.1,.05,.025):
            text=step_source(width=width);a,b=2-width/2,2+width/2;m=parse_asw(text)
            value=dispatch(dict(request,source=text));v=survey(m,positions=points,condition=spec['condition'],panels=spec['panels'])
            results.append(dict(width=width,result=value,field=v))
        extra['refinement']=results
    return dict(request=request,result=out,field=field,plane=plane,**extra)


def physical(case):
    out=case['result'];snapshots=out['snapshots'] if out.get('analysis')=='time_response' else [out]
    if 'resumed' in case:snapshots+=case['resumed']['snapshots']
    values=[]
    for snap in snapshots:
        values.extend(snap['force']+snap['moment'])
        for shoulder in snap['body_shoulders']:values.extend(shoulder['position']+shoulder['force'])
        for node in snap.get('nodes',[]):values.extend(node['position'])
    values.extend(np.asarray(case['field']['velocity']['volume']).ravel())
    values.extend(np.asarray(case['plane']['velocity']['volume']).ravel())
    if 'derivatives' in out:values.extend(np.asarray(out['derivatives']['matrices']['distributed_aero_wrench']).ravel())
    for r in case.get('refinement',[]):values.extend(r['result']['force']+r['result']['moment']);values.extend(np.asarray(r['field']['velocity']['volume']).ravel())
    for r in case.get('field_mesh_refinement',[]):values.extend(np.asarray(r['field']['velocity']['volume']).ravel())
    return np.asarray(values)


def verify(spec,case):
    maximum=0.;count=0
    def close(actual,expected,tol=3e-8):
        nonlocal maximum,count
        a,b=np.asarray(actual),np.asarray(expected);error=float(np.max(abs(a-b)/np.maximum(1.,abs(b))));count+=a.size;maximum=max(maximum,error)
        assert error<tol,(spec['name'],error,tol,a,b)
    out=case['result'];snapshots=out['snapshots'] if spec['kind']=='time' else [out]
    if spec['name']!='elastic':
        for snap in snapshots:
            force,wrench=expected_loads(spec,snap.get('time',0));close(np.r_[snap['force'],snap['moment']],wrench)
            close([s['force'] for s in snap['body_shoulders']],force)
            if 'support_moment' in snap:close(snap['support_moment'],-wrench[3:])
        close(case['field']['velocity']['volume'],reference_field(spec,case['field']['position_body']),5e-7 if spec['panels']==4 else 2e-9)
    field_errors=[]
    if case.get('field_mesh_refinement'):
        reference=reference_field(spec,case['field']['position_body'])
        fields=[case['field']]+[row['field'] for row in case['field_mesh_refinement']]
        field_errors=[float(np.max(abs(np.asarray(f['velocity']['volume'])-reference))) for f in fields]
        close(fields[-1]['velocity']['volume'],reference,2e-9)
        for a,b in zip(field_errors,field_errors[1:]):
            if a>1e-10:assert b<a*.2,(spec['name'],field_errors)
    if spec['name']=='elastic':
        force=out['body_shoulders'];tip=next(n for n in out['nodes'] if n['t']==4)['position'][2]
        expected=sum(s['force'][2]*s['t']**2*(12-s['t'])/(6*10000) for s in force)
        grid=sorted(n['t'] for n in out['nodes']);error=-sum((b-a)**3*sum(s['force'][2] for s in force if s['t']>(a+b)/2) for a,b in zip(grid,grid[1:]))/(12*10000)
        close(tip,expected+error,5e-10)
        close(out['force_balance'],[0,0,0],2e-8);close(out['moment_balance'],[0,0,0],2e-8)
    if spec['name']=='derivative':close(np.array(out['derivatives']['matrices']['distributed_aero_wrench'])[:,0],[0,0,0,0,1.225*2*np.pi*.2**2*17**2*np.cos(2*np.deg2rad(11)),0],2e-8)
    if spec['kind']=='time':
        last=case['resumed']['snapshots'][-1];_,wrench=expected_loads(spec,last['time']);close(last['force']+last['moment'],wrench)
        close(last['support_moment'],-wrench[3:])
    refinement=[]
    for row in case.get('refinement',[]):
        width=row['width'];a,b=2-width/2,2+width/2
        smooth=dict(spec,segments=[[0,a,.1,.1],[a,b,.1,.3],[b,4,.3,.3]],jumps=[])
        close(row['field']['velocity']['volume'],reference_field(smooth,row['field']['position_body']),2e-9)
        force,wrench=expected_loads(spec);centroid=2+width*(.3-.1)/(6*(.3+.1));close(row['result']['force'],force[0]);close(row['result']['moment'],np.cross([centroid,0,0],force[0]))
        assert not row['result']['body_shoulders'];refinement.append(float(np.linalg.norm(np.asarray(row['field']['velocity']['volume'])-case['field']['velocity']['volume'])))
    if refinement:assert all(b<a*.65 for a,b in zip(refinement,refinement[1:])),refinement
    json.dumps(case,allow_nan=False)
    return dict(reference_values_checked=count,maximum_scaled_reference_error=maximum,
        smooth_field_errors=refinement,field_mesh_errors=field_errors)


def main():
    files=sorted((ROOT/'openswing').glob('*.py'))+[Path(__file__),ROOT/'examples/stepped-body.asw']
    hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files};cache=ROOT/'.reference/body-shoulders'/hashlib.sha256(json.dumps(hashes,sort_keys=True).encode()).hexdigest();cache.mkdir(parents=True,exist_ok=True)
    cases=[]
    for spec in specifications():
        path=cache/(spec['name']+'.json');result=json.loads(path.read_text()) if path.exists() else compute(spec);checks=verify(spec,result)
        path.write_text(json.dumps(result,allow_nan=False));cases.append(dict(specification=spec,result=result,checks=checks));print(spec['name'],checks,flush=True)
    (ROOT/'docs/validation/body-shoulders.json').write_text(json.dumps(dict(description='Concentric radius jumps as weak limits of the published slender-body source and force equations; not a resolved blunt-step/separation model.',source_sha256=hashes,python=platform.python_version(),numpy=np.__version__,scipy=scipy.__version__,cases=cases),indent=2)+'\n')
    print('All native body-shoulder cases passed.',flush=True)
if __name__=='__main__':main()
