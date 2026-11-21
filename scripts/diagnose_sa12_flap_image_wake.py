"""Bounded historical-image hypothesis checks, never a production correction.

One replay control and four predeclared flapped points. Reflecting only image
origins is deliberately nonphysical for a tilted wake; report its wall defect
alongside every coefficient comparison. Original sources/defaults stay intact.
"""
import argparse
import math
from pathlib import Path
import resource
import sys
import time

import verify_sa12_current_pilot as io

ROOT = Path(__file__).resolve().parents[1]
PRIOR = ROOT / 'artifacts/isae/sa12-flap-pose-20261109'


def prepare(out):
    io.bounded()
    prior = io.read(PRIOR / 'plan.json')
    io.authenticate(prior['pins'])
    pins = dict(prior['pins'])
    for p in (Path(__file__), PRIOR/'plan.json', PRIOR/'analysis.json',
              ROOT/'artifacts/isae/sa12-avl-ground-r2-20261109/analysis.json'):
        pins[str(p.relative_to(ROOT))] = io.sha(p)
    baselines = [c for c in prior['cases'] if c['setup'] == 'wind_parallel_current']
    assert len(baselines) == 4
    control, = [c for c in baselines if c['job']['height_label']=='05' and c['settings']['alpha']==2.]
    cases = []
    for c, reflected in [(control,True), *((c,False) for c in baselines)]:
        folder = PRIOR/c['id']
        report = io.read(folder/'report.json')
        assert report['result_sha256'] == io.sha(folder/'result.json')
        assert report['numerical_pass']
        for name in ('result.json','report.json','verification.json'):
            pins[str((folder/name).relative_to(ROOT))] = io.sha(folder/name)
        cases.append(dict(id=c['id'].replace('-baseline','')+('-replay' if reflected else '-shared-wake'),
            job=c['job'], baseline=str((folder/'result.json').relative_to(ROOT)),
            pitch=c['settings']['alpha'] if reflected else 0., reflect_wake=reflected))
    assert not out.exists()
    out.mkdir(parents=True)
    io.write(out/'plan.json',dict(observed_utc=io.utc(),cases=cases,pins=pins,
        protocol='Independent nonlinear tangency/forces on original models. First replay current/pitch-alpha physical baseline at h/c0.5,alpha2. Then four fixed zero-pitch,current-influence diagnostics reflecting endpoints but not image rays. Same four flap points as paired study; no tuning. Report induced wall-normal defect; never count alternative as physical validity or primary pass.',
        source_basis='Drela steady sections4.2,4.5,4.6; Jan PartI p20-21 and38/Fig23. Full reflected paths cancel induced ground-normal velocity. Archived K/F startup and Euler attitude unavailable.',
        diagnostic_equilibrium_calls=5,production_calls=0,primary_passes_added=0,
        prior_goal_turn='Progress: native AVL ground controls verified and stale ground test repaired.',
        limits='One serial foreground solve per invocation,one BLAS thread,512MiB,15CPU/25wall seconds.'))
    (out/'driver-used.py').write_text(Path(__file__).read_text())
    io.signal.alarm(0)
    print('Prepared one physical replay control and four nonphysical historical-approximation diagnostics.')


def run(out,index):
    io.bounded()
    start=time.monotonic()
    plan=io.read(out/'plan.json');io.authenticate(plan['pins'])
    case=plan['cases'][index];folder=out/case['id']
    assert not folder.exists()
    import numpy as np
    sys.path.insert(0,str(ROOT))
    from openswing.asw import parse_asw
    from openswing.geometry import model_meshes
    from openswing.frozen_influence import lifting_geometry
    from avl_vorvelc_reference import matrix
    job=case['job'];s=job['settings']
    model=parse_asw((ROOT/job['model_path']).read_text(),beam_interpolation=s['beam_interpolation'])
    assert not model.diagnostics and len(model.beams)==1
    meshes=model_meshes(model,s['panels'])
    sample=lambda key:np.concatenate([m.beam.value(key,m.tm) for m in meshes])
    assert np.all(sample('Cdp')==0) and np.all(sample('Cm')==0)
    span=np.concatenate([m.frames[...,1] for m in meshes])
    incidence=np.deg2rad(sample('alpha'))
    normal=(np.sin(incidence)[:,None]*np.concatenate([m.frames[...,0] for m in meshes])
            +np.cos(incidence)[:,None]*np.concatenate([m.frames[...,2] for m in meshes]))
    alpha=math.radians(s['alpha']);pitch=math.radians(case['pitch'])
    wind=np.array([math.cos(alpha),0.,math.sin(alpha)])
    lift=np.array([-math.sin(alpha),0.,math.cos(alpha)])
    ground=np.array([-math.sin(pitch),0.,math.cos(pitch)])
    height=s['position_earth'][2]
    reflect=lambda p:p-2*(p@ground+height)[...,None]*ground
    reflected_direction=wind-2*(wind@ground)*ground
    image_direction=reflected_direction if case['reflect_wake'] else wind
    g=lifting_geometry(meshes,wind)

    def operator(points,a,b,direction,exclude=False):
        rotation=np.array([direction,[0.,1.,0.],np.cross(direction,[0.,1.,0.])])
        return matrix(points@rotation.T,a@rotation.T,b@rotation.T,0.,
                      exclude_self=exclude,core_fraction=0.)@rotation/(4*math.pi*.079577472)

    def field(points,exclude=False):
        return (operator(points,g['a'],g['b'],wind,exclude)
                -operator(points,reflect(g['a']),reflect(g['b']),image_direction))

    hv=field(g['hv'],True);cp=field(g['cp'])
    cp_normal=np.einsum('ijq,iq->ij',cp,normal)
    speed,rho,width=s['speed'],s['density'],s['stall_width']
    flight=speed*wind;strength=s['stall_factor']/sample('dCLda')

    def equations(gamma):
        v=flight+np.einsum('ijq,j->iq',hv,gamma)
        perp=v-np.sum(v*span,axis=1)[:,None]*span
        vp=np.linalg.norm(perp,axis=1)
        cl=2*gamma/(g['chord']*vp)
        upper=(cl-sample('CLmax'))/width;lower=(sample('CLmin')-cl)/width
        f=width*(np.logaddexp(0,upper)-np.logaddexp(0,lower))
        fp=np.exp(-np.logaddexp(0,-upper))+np.exp(-np.logaddexp(0,-lower))
        residual=normal@flight+cp_normal@gamma-vp*strength*f
        dvp=np.einsum('iq,ijq->ij',perp/vp[:,None],hv)
        jac=cp_normal-(strength*(f-fp*cl))[:,None]*dvp
        jac-=np.diag(strength*fp*2/g['chord'])
        return residual,jac,v,perp,vp,cl

    gamma=np.linalg.solve(cp_normal,-normal@flight)
    for iteration in range(20):
        residual,jac,*_=equations(gamma)
        if max(abs(residual))/speed<1e-12:break
        step=np.linalg.solve(jac,-residual)
        for backtrack in range(20):
            trial=gamma+step*.5**backtrack
            if max(abs(equations(trial)[0]))<max(abs(residual)):
                gamma=trial;break
        else:raise AssertionError('Diagnostic Newton line search failed')
    residual,jac,v,perp,vp,cl=equations(gamma)
    assert max(abs(residual))/speed<1e-10
    probe=np.cos(np.arange(len(gamma)))
    finite=(equations(gamma+1e-5*probe)[0]-equations(gamma-1e-5*probe)[0])/2e-5
    derivative_error=float(max(abs(finite-jac@probe))/max(abs(jac@probe)))
    assert derivative_error<1e-7
    tangent=normal@flight+cp_normal@gamma
    vortex=rho*gamma[:,None]*np.cross(v,span)*g['ds'][:,None]
    friction=.5*rho*np.linalg.norm(v,axis=1)[:,None]*v*(g['chord']*sample('Cdf')*g['ds'])[:,None]
    stall=2*rho*perp/vp[:,None]*(tangent**2*g['chord']*g['ds'])[:,None]
    forces=vortex+friction+stall
    total=np.array([math.fsum(forces[:,i]) for i in range(3)])
    qs=.5*rho*speed**2*model.reference[0,0]
    # A formal common-wake trace exists in these variants. This calculation
    # does not make the endpoint-only ground image physically valid.
    assert max(abs(image_direction-wind))<1e-12
    wake=np.zeros_like(g['hv'])
    for points,sign in ((g['b'],1),(g['a'],-1),(reflect(g['b']),-1),(reflect(g['a']),1)):
        r=g['hv'][:,None,:]-points[None,:,:]
        r-=(r@wind)[...,None]*wind
        wake+=sign*np.einsum('ijq,j->iq',np.cross(wind,r)/np.sum(r*r,axis=2)[...,None],gamma)/(2*math.pi)
    cdi=-.5*rho*math.fsum(gamma*np.sum(wake*np.cross(wind,g['b']-g['a']),axis=1))/qs
    values=dict(CL=float(total@lift/qs),CD=float(total@wind/qs),CDi=float(cdi),Cm=0.)
    along=np.array([math.cos(pitch),0.,math.sin(pitch)])
    board=np.array([x*along+[0.,y,0.]-height*ground for x in (-.5,0.,.5) for y in (-.5,0.,.5)])
    boundary=float(max(abs(np.einsum('ijq,j->iq',field(board),gamma)@ground)))
    baseline=io.read(ROOT/case['baseline'])
    replay=None
    if case['reflect_wake']:
        replay=dict(gamma=float(max(abs(gamma-np.array([r['circulation'] for r in baseline['strips']])))),
                    coefficients=max(abs(values[k]-baseline[k]) for k in values))
        assert replay['gamma']<2e-10 and replay['coefficients']<2e-12 and boundary<1e-10,replay
    comparisons=[]
    for name,value in values.items():
        ref=job['reference_row']['fields'][name];expected=ref['value']
        tolerance=ref['tolerance'] if abs(expected)<=1e-8 else max(ref['tolerance'],.05*abs(expected))
        comparisons.append(dict(name=name,actual=value,expected=expected,tolerance=tolerance,
            error_percent=None if abs(expected)<=1e-8 else 100*(value-expected)/abs(expected),
            within_numeric_gate=abs(value-expected)<=tolerance))
    result=dict(observed_utc=io.utc(),case=case['id'],values=values,comparisons=comparisons,
        equation_residual=float(max(abs(residual))/speed),jacobian_error=derivative_error,
        baseline_replay=replay,induced_ground_normal_speed=boundary,
        freestream_ground_normal_speed=float(flight@ground),
        physical_ground_image=case['reflect_wake'],
        minimum_stall_margin_widths=float(min(np.minimum(sample('CLmax')-cl,cl-sample('CLmin'))/width)),
        drag_parts={k:float(math.fsum(f@wind)/qs) for k,f in [('circulation',vortex),('friction',friction),('stall',stall)]},
        diagnostic_equilibrium_calls=1,production_calls=0,primary_passes_added=0,
        seconds=time.monotonic()-start,peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        plan_sha256=io.sha(out/'plan.json'))
    folder.mkdir()
    np.savez(folder/'state.npz',gamma=gamma,velocity=v,force=forces,ground_points=board,
             a=g['a'],b=g['b'],hv=g['hv'],cp=g['cp'],normal=normal)
    result['state_sha256']=io.sha(folder/'state.npz')
    io.write(folder/'result.json',result)
    io.signal.alarm(0)
    print({k:v for k,v in result.items() if k!='comparisons'})


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('prepare','run'))
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--index',type=int)
    args=parser.parse_args()
    if args.action=='prepare':prepare(args.output.resolve())
    else:run(args.output.resolve(),args.index)
