"""Read saved SA1 states; independent scalar Biot-Savart, no solve/import."""
from pathlib import Path
import hashlib,json,math

ROOT=Path(__file__).resolve().parents[3]
FOLDER=ROOT/'artifacts/isae/sa1-basis-diagnostic-20261027'
def wpair(y,a,b,d):
    u,v=y-a,y-b
    if u==0 or v==0:raise ValueError('Receiver on a trailing filament')
    if d==0:return (1/v-1/u)/(4*math.pi)
    return ((1+math.hypot(d,v)/d)/v-(1+math.hypot(d,u)/d)/u)/(4*math.pi)
def leakage(cl):
    def softplus(z):return max(z,0)+math.log1p(math.exp(-abs(z)))
    return .05*(softplus((cl-1.2)/.05)-softplus((-1.2-cl)/.05))
def pin(path):
    raw=path.read_bytes();return dict(path=str(path.relative_to(ROOT)),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
rows=[]
for path in sorted(FOLDER.glob('row*.json')):
    packet=json.loads(path.read_text());j=packet['job'];r=packet['result'];condition=j['condition']
    assert condition['mach']==condition['beta']==0 and condition['freeze_influences'] is False
    assert condition['stall_factor']==40 and condition['stall_width']==.05
    n=j['panels'];strips=r['strips'];nodes=[x['t'] for x in r['mesh_discretization']['beams'][0]['nodes']]
    assert len(nodes)==n+1 and len(strips)==n and nodes[0]==-2.95 and nodes[-1]==2.95
    U,rho,S,c,a0=47.9,1.2256,5.9,1.,6.2832
    assert condition['speed']==U and condition['density']==rho
    alpha=math.radians(condition['alpha']);sa,ca=math.sin(alpha),math.cos(alpha)
    e=[ca,0.,sa];ell=[-sa,0.,ca];gamma=[x['circulation'] for x in strips]
    force=[];moment=[];residual=[];wakes=[];profile=[];lift=[]
    velocity_error=[];cl_error=[];strip_force_error=[];strip_moment_error=[];geometry_error=[]
    for i,s in enumerate(strips):
        y=s['t'];ds=nodes[i+1]-nodes[i]
        wh=math.fsum(g*wpair(y,a,b,0.) for g,a,b in zip(gamma,nodes,nodes[1:]))
        wc=math.fsum(g*wpair(y,a,b,c*a0/(4*math.pi)) for g,a,b in zip(gamma,nodes,nodes[1:]))
        speed=math.hypot(U,wh);cl=2*gamma[i]/(c*speed);vn=U*sa+wc*ca
        residual.append((vn-speed/a0*40*leakage(cl))/U)
        velocity=[U*e[k]+wh*ell[k] for k in range(3)]
        fl=[rho*gamma[i]*(U*ell[k]-wh*e[k])*ds for k in range(3)]
        scale=rho*c*(.5*(.00352562+.00771413)*speed+2*vn*vn/speed)*ds
        fp=[scale*v for v in velocity]
        f=[a+b for a,b in zip(fl,fp)]
        my=-.25*fl[2]
        force.append(f);moment.append([y*f[2],my,-y*f[0]]);profile.append(fp);lift.append(fl);wakes.append(wh)
        velocity_error.extend(abs(a-b) for a,b in zip(velocity,s['relative_velocity']))
        cl_error.append(abs(cl-s['cl']))
        strip_force_error.extend(abs(a-b) for a,b in zip(f,s['force']))
        strip_moment_error.append(abs(my-s['moment'][1]))
        geometry_error.extend(abs(a-b) for a,b in zip(s['velocity_position'],[.25*ca,y,.25*sa]))
        geometry_error.append(abs(ds-s['length']))
    def total(values):return [math.fsum(v[k] for v in values) for k in range(3)]
    f,m,fp,fl=map(total,[force,moment,profile,lift]);qS=.5*rho*U*U*S
    def dot(a,b):return math.fsum(x*y for x,y in zip(a,b))
    cli=2*math.fsum(g*(b-a) for g,a,b in zip(gamma,nodes,nodes[1:]))/(U*S)
    cdi=-2*math.fsum(g*w*(b-a) for g,w,a,b in zip(gamma,wakes,nodes,nodes[1:]))/(U*U*S)
    predicted=dict(CL=dot(f,ell)/qS,CD=dot(f,e)/qS,CDi=cdi,CDi_near=cdi,CLi=cli,CDp=dot(fp,e)/qS,
        Cm=m[1]/qS,efficiency=cli*cli/(math.pi*5.9*cdi))
    predicted_residual=residual
    modes=condition['circulation_modes'].get('1',0)
    if modes:
        theta=[x['theta'] for x in r['mesh_discretization']['beams'][0]['nodes']]
        predicted_residual=[2/math.pi*math.fsum(v*math.sin(k*(a+b)/2)*(a-b) for v,a,b in zip(residual,theta,theta[1:])) for k in range(1,modes+1)]
    rows.append(dict(source=pin(path),panels=n,modes=modes,alpha=condition['alpha'],
        values={k:dict(oracle=v,retained=r[k],absolute_difference=abs(v-r[k])) for k,v in predicted.items()},
        maximum_absolute_differences=dict(velocity=max(velocity_error),section_cl=max(cl_error),strip_force=max(strip_force_error),
            strip_moment=max(strip_moment_error),geometry=max(geometry_error),
            local_residual=max(abs(a-b) for a,b in zip(residual,r['circulation_local_residual'])),
            projected_residual=max(abs(a-b) for a,b in zip(predicted_residual,r['circulation_residual'])),
            integrated_force=max(abs(a-b) for a,b in zip(f,r['force'])),integrated_moment=max(abs(a-b) for a,b in zip(m,r['moment'])))))
out=dict(scope='SA1 saved circulation replay through independently derived scalar Biot-Savart. No solve, matrix assembly or production/numerical import.',
    formula='w(d)=[(1+hypot(d,y-b)/d)/(y-b)-(1+hypot(d,y-a)/d)/(y-a)]/(4*pi); w(0)=[1/(y-b)-1/(y-a)]/(4*pi)',
    cases=rows)
Path(__file__).with_suffix('.json').write_text(json.dumps(out,indent=2)+'\n')
for row in rows:print(row['source']['path'].split('/')[-1],row['maximum_absolute_differences'])
