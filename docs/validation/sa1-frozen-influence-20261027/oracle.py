"""Replay saved frozen SA1 fields. Standard library only; never solves Gamma."""
import argparse
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
U, RHO, S, CHORD, A0 = 47.9, 1.2256, 5.9, 1., 6.2832
CD0, WIDTH, KS = .00352562 + .00771413, .05, 40.
MODEL_SHA = '4c7a55235973171749afac41741e11792fc5b4fbf9e072aaee3bc57c6fc658bd'


def pin(path):
    path = Path(path).resolve()
    data = path.read_bytes()
    try:
        name = str(path.relative_to(ROOT))
    except ValueError:
        name = str(path)
    return dict(path=name, bytes=len(data), sha256=hashlib.sha256(data).hexdigest())


def wpair(y, a, b, d):
    """Body-z velocity per Gamma, span segment a..b, fixed +x trailing rays."""
    u, v = y-a, y-b
    if u == 0 or v == 0:
        raise ValueError('Receiver lies on a trailing filament.')
    if d == 0:
        return (1/v-1/u)/(4*math.pi)
    return ((1+math.hypot(d,v)/d)/v-(1+math.hypot(d,u)/d)/u)/(4*math.pi)


def stall(cl):
    def softplus(z):
        return max(z,0)+math.log1p(math.exp(-abs(z)))
    return WIDTH*(softplus((cl-1.2)/WIDTH)-softplus((-1.2-cl)/WIDTH))


def dot(a, b):
    return math.fsum(x*y for x,y in zip(a,b))


def total(vectors):
    return [math.fsum(v[k] for v in vectors) for k in range(3)]


def calculate(nodes, samples, gamma, alpha):
    """Scalar line integration and local source force laws at retained Gamma."""
    if len(nodes) != len(gamma)+1 or len(samples) != len(gamma):
        raise ValueError('Need N+1 endpoints and N samples/circulations.')
    if not all(math.isfinite(v) for v in [*nodes,*samples,*gamma,alpha]):
        raise ValueError('Finite saved fields are required.')
    if any(b<=a or not a<y<b for a,b,y in zip(nodes,nodes[1:],samples)):
        raise ValueError('Ordered intervals and strictly interior receivers are required.')
    angle = math.radians(alpha); sa, ca = math.sin(angle), math.cos(angle)
    e, lift_axis = [ca,0.,sa], [-sa,0.,ca]
    qs = .5*RHO*U*U*S
    strips = []
    for i,(a,b,y,g) in enumerate(zip(nodes,nodes[1:],samples,gamma)):
        ds=b-a
        wh=math.fsum(q*wpair(y,aa,bb,0.) for q,aa,bb in zip(gamma,nodes,nodes[1:]))
        wc=math.fsum(q*wpair(y,aa,bb,CHORD*A0/(4*math.pi)) for q,aa,bb in zip(gamma,nodes,nodes[1:]))
        velocity=[U*ca,0.,U*sa+wh]
        speed=math.hypot(velocity[0],velocity[2])
        if speed == 0:
            raise ValueError('Section speed is zero.')
        cl=2*g/(CHORD*speed)
        tangency=U*sa+wc
        residual=(tangency-speed/A0*KS*stall(cl))/U
        fl=[-RHO*g*velocity[2]*ds,0.,RHO*g*velocity[0]*ds]
        profile_factor=RHO*CHORD*(.5*CD0*speed+2*tangency*tangency/speed)*ds
        fp=[profile_factor*v for v in velocity]
        force=[x+z for x,z in zip(fl,fp)]
        section_moment=[0.,-.25*CHORD*fl[2],0.]
        moment=[y*force[2],section_moment[1],-y*force[0]]
        strips.append(dict(y=y,length=ds,Gamma=g,velocity=velocity,speed=speed,cl=cl,
            hv=[.25,y,0.],cp=[.25+CHORD*A0/(4*math.pi),y,0.],
            w_hv=wh,w_cp=wc,tangency=tangency,residual=residual,
            lift_force=fl,profile_force=fp,force=force,
            section_moment=section_moment,moment=moment,
            trefftz_velocity=[0.,0.,2*wh],trefftz_drag=-RHO*g*wh*ds))
    force=total([s['force'] for s in strips]); moment=total([s['moment'] for s in strips])
    profile=total([s['profile_force'] for s in strips]); lift=total([s['lift_force'] for s in strips])
    G=math.fsum(g*(b-a) for g,a,b in zip(gamma,nodes,nodes[1:]))
    cli0=2*G/(U*S)
    cdi0=math.fsum(s['trefftz_drag'] for s in strips)/qs
    values=dict(CL=dot(force,lift_axis)/qs,CD=dot(force,e)/qs,Cm=moment[1]/(qs*CHORD),
        CLi=cli0,CDi=cdi0,CDi_near=dot(lift,e)/qs,CDp=dot(profile,e)/qs,
        efficiency=cli0*cli0/(math.pi*(5.9**2/S)*cdi0) if cdi0>0 else None)
    identities=dict(near_circulation_CL=dot(lift,lift_axis)/qs,
        near_circulation_CL_from_fixed_wake=cli0-sa*cdi0,
        near_circulation_CD_from_fixed_wake=ca*cdi0,
        Cm_from_fixed_wake=-.25*ca*cli0,
        fixed_wake_transverse_force=[0.,0.,RHO*U*G],
        fixed_wake_transverse_force_projected_on_actual_lift_axis=ca*cli0)
    return dict(strips=strips,force=force,moment=moment,profile_force=profile,lift_force=lift,
        values=values,identities=identities,actual_wind=e,actual_lift_axis=lift_axis,
        influence_wind=[1.,0.,0.],influence_lift_axis=[0.,0.,1.])


def max_difference(pairs):
    return max((abs(a-b) for a,b in pairs),default=0.)


def replay(path):
    packet=json.loads(Path(path).read_text()); job=packet['job']; result=packet['result']
    condition=job['condition']
    if not (condition['freeze_influences'] is True and condition['mach']==0 and condition['beta']==0
            and condition['speed']==U and condition['density']==RHO and condition['stall'] is True
            and condition['stall_factor']==KS and condition['stall_width']==WIDTH):
        raise ValueError('Saved case is outside the declared frozen/Mach0/literal-SA1 scope.')
    if any(condition.get('circulation_modes',{}).values()):
        raise ValueError('This replay is limited to pointwise circulation.')
    for key in ('rates','acceleration','angular_acceleration'):
        if any(condition.get(key,[0.,0.,0.])):
            raise ValueError('Motion is outside the stationary replay scope.')
    if condition.get('controls') or condition.get('powers') or condition.get('gust'):
        raise ValueError('Controls, engines and gusts are outside this replay scope.')
    if condition.get('ground_effect',0):
        raise ValueError('Ground images are outside this replay scope.')
    model_pin=pin(ROOT/job['model_path'])
    if model_pin['sha256'] != MODEL_SHA:
        raise ValueError('Literal SA1 model hash differs.')
    if result['aerodynamic_influences']['frozen'] is not True:
        raise ValueError('Raw result is not marked as frozen influences.')
    mesh=result['mesh_discretization']['beams']
    if len(mesh)!=1:
        raise ValueError('Expected the single mirrored SA1 wing.')
    raw=result['strips']; nodes=[n['t'] for n in mesh[0]['nodes']]
    if nodes[0] != -2.95 or nodes[-1] != 2.95 or len(raw)!=job['panels']:
        raise ValueError('Unexpected source geometry or requested interval count.')
    calc=calculate(nodes,[s['t'] for s in raw],[s['circulation'] for s in raw],condition['alpha'])
    derived=calc['strips']; trefftz=result['trefftz']
    if not trefftz['available']:
        raise ValueError('The saved Trefftz diagnostic is unavailable.')
    for name in ('velocity_body','strip_induced_drag'):
        if len(trefftz[name]) != len(raw):
            raise ValueError('Saved Trefftz field count differs from strip count.')
    errors={}
    for name, raw_name in [('velocity','relative_velocity'),('hv','velocity_position'),('force','force'),('section_moment','moment')]:
        errors[name]=max_difference((a,b) for d,r in zip(derived,raw) for a,b in zip(d[name],r[raw_name]))
    for name,raw_name in [('length','length'),('cl','cl'),('speed','normal_speed')]:
        errors[name]=max_difference((d[name],r[raw_name]) for d,r in zip(derived,raw))
    for name in ('force','moment'):
        errors['integrated_'+name]=max_difference(zip(calc[name],result[name]))
    for name in ('circulation_local_residual','circulation_residual'):
        if len(result[name]) != len(derived):
            raise ValueError('Pointwise residual count differs.')
        errors[name]=max_difference((d['residual'],v) for d,v in zip(derived,result[name]))
    errors['trefftz_velocity']=max_difference((a,b) for d,v in zip(derived,trefftz['velocity_body']) for a,b in zip(d['trefftz_velocity'],v))
    errors['trefftz_strip_drag']=max_difference((d['trefftz_drag'],v) for d,v in zip(derived,trefftz['strip_induced_drag']))
    errors['trefftz_transverse_force']=max_difference(zip(calc['identities']['fixed_wake_transverse_force'],trefftz['force_transverse_body']))
    comparisons={k:dict(oracle=v,retained=result[k],absolute_difference=abs(v-result[k]) if v is not None and result[k] is not None else None)
                 for k,v in calc['values'].items()}
    return dict(source=pin(path),model=model_pin,job=job,actual_wind=calc['actual_wind'],
        influence_wind=calc['influence_wind'],values=comparisons,maximum_absolute_differences=errors,
        independent_identities=calc['identities'],
        maximum_absolute_local_residual=max(abs(s['residual']) for s in derived),
        scope='Saved Gamma replay; no independent solve, historical-setting identification or reference-acceptance decision.')


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path,nargs='+',required=True,help='Saved {job,result} packets; all provided files retained.')
    parser.add_argument('--output',type=Path,required=True,help='New receipt file; refuses an existing file.')
    args=parser.parse_args(argv)
    if args.output.exists():
        parser.error('Output already exists; frozen receipts are never overwritten.')
    cases=[replay(path) for path in args.input]
    record=dict(status='SAVED_FIELD_REPLAY_COMPLETE',new_solves=0,production_imports=0,
        script=pin(__file__),cases=cases,
        qualifications=[
            'Actual freestream and force-projection axes retain alpha; the fixed influence wake and coefficient geometry use alpha=beta=0.',
            'The replay verifies the zero-angle fixed-wake Trefftz diagnostic. The primary K/F description does not explicitly state how historical exported Trefftz axes are handled; this is not recovered ASWING exporter evidence.',
            'Native reference checks in input packets are not used or reclassified. Local law replay does not identify historical Gamma or discrete force-transfer rules.'])
    with args.output.open('x') as stream:
        json.dump(record,stream,indent=2,allow_nan=False);stream.write('\n')
    print(json.dumps(dict(output=str(args.output),cases=len(cases),new_solves=0)))


if __name__=='__main__':
    main()
