"""Reproducible physical field references and immutable solved-state surveys."""
import hashlib,json,platform,sys
from copy import deepcopy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import numpy as np
import scipy
from scipy.integrate import quad_vec
from openswing.asw import parse_asw
from openswing.aero import FlightCondition
from openswing.bridge import dispatch
from openswing.geometry import model_meshes
from openswing.network import solve_static
from openswing.ground import body_to_earth
from openswing.flow_survey import plane_grid
from openswing.time_integration import solve_time
from openswing.time_state import checkpoint

BODY='''Name
Flow survey verification
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
4 1 4
End
Ground
1 0 0
End
Beam 1
Body
{rows}
End
'''

def request(source,condition=None,plane=None,**options):
    args=dict(plane=plane or dict(origin=[0,0,1],u=[-2,6],v=[-5,5],counts=[21,17]),**options)
    if condition is not None:args['condition']=condition
    return dict(action='flow_survey',source=source,panels=8,survey=args)


def reference(component,values,indices=None,tolerance=1e-9,description=''):
    return dict(component=component,values=np.asarray(values).tolist(),indices=indices,tolerance=tolerance,description=description)


def make_cases():
    cases=[]
    wing=(ROOT/'examples/rectangular.asw').read_text();m=parse_asw(wing);mesh=model_meshes(m,8)[0]
    gamma=np.linspace(.2,.7,len(mesh.tm));req=request(wing,dict(speed=13,alpha=0,mach=0,stall=False),circulation=gamma.tolist())
    points,_=plane_grid(req['survey']['plane']);indices=[0,19,65,170,356];expected=[]
    for point in points[indices]:
        value=np.zeros(3)
        for g,a,b,length,chord in zip(gamma,mesh.r0,mesh.r1,mesh.length,mesh.beam.value('chord',mesh.tm)):
            core=max(chord/4,length)
            def line(start,d,end):
                def integrand(t):
                    r=point-start-t*d
                    return np.cross(d,r)/(r@r+core**2)**1.5/(4*np.pi)
                return quad_vec(integrand,0,end,epsabs=1e-12)[0]
            value+=g*(line(a,b-a,1)+line(b,np.array([1.,0,0]),np.inf)-line(a,np.array([1.,0,0]),np.inf))
        expected.append(value)
    cases.append(dict(name='horseshoe_integrals',request=req,references=[reference('lifting',expected,indices,2e-11,'Adaptive integration of regularized bound and semi-infinite vortex segments.')]))
    source=BODY.format(rows='t x radius\n0 -2 .1\n2 0 .35\n4 2 .1');m=parse_asw(source);beam=m.beams[0]
    req=request(source,dict(speed=13,alpha=17,mach=0),plane=dict(origin=[0,0,.15],u=[-3,3],v=[-2,2],counts=[21,17]));req['panels']=20
    points,_=plane_grid(req['survey']['plane']);indices=[0,45,99,225,356];e=FlightCondition(**req['survey']['condition']).vectors()[0];expected=[]
    for point in points[indices]:
        def integrand(t):
            radius=float(beam.value('radius',t));rd=float(beam.value('radius',t,derivative=1));r=point-beam.position(t);r2=r@r;den=r2+(radius/2)**2
            sigma=2*np.pi*radius*rd*e[0];nu=2*np.pi*radius**2*(e-[e[0],0,0])
            return 13/(4*np.pi)*(sigma*r/den**1.5+(nu*r2-3*(nu@r)*r)/den**2.5)
        expected.append(quad_vec(integrand,0,4,epsabs=1e-12)[0])
    cases.append(dict(name='body_integrals',request=req,references=[reference('volume',expected,indices,3e-9,'Adaptive integration of the distributed regularized body sources and doublets.')]))
    source=BODY.format(rows='t x radius\n0 0 0\n4 4 0')+'Weight\n1 0 .1 -.2 .3 0 .2 .5\nEnd\n'
    req=request(source,dict(speed=13,alpha=0,mach=.4,ground_effect=1,position_earth=[0,0,2]),plane=dict(origin=[0,0,-2],u=[-3,5],v=[-3,3],counts=[21,17]))
    points,_=plane_grid(req['survey']['plane']);pg=np.diag([1/np.sqrt(1-.4**2),1,1]);core=max(np.sqrt(.2/np.pi),np.cbrt(.5/np.pi));nu=.5*pg@np.array([1,0,0]);expected=np.zeros_like(points)
    for position in ([.1,-.2,.3],[.1,-.2,-4.3]):
        r=(points-position)@pg.T;r2=np.sum(r*r,axis=1);den=r2+core**2
        expected+=(.2*r/den[:,None]**1.5+(nu*r2[:,None]-3*(r@nu)[:,None]*r)/den[:,None]**2.5)@pg*13/(4*np.pi)
    cases.append(dict(name='point_pg_ground',request=req,references=[reference('volume',expected,tolerance=2e-12,description='Direct point source/doublet tensor with PG chain rule and its reflected solid-ground image.')]))
    source=BODY.format(rows='t x radius\n0 0 0\n4 4 0')
    c=dict(speed=11,alpha=13,beta=-7,mach=0,rates=[.2,-.3,.4],attitude=[23,17,-31],position_earth=[2,3,5],gust=dict(type='expression',components=['.1*y','-.2*x','.3*z+.4*t']),time=.7)
    req=request(source,c,plane=dict(origin=[1,2,3],normal=[1,2,3],direction=[2,-1,1],u=[-2,3],v=[-1,2],counts=[21,17]),coordinates='earth')
    points,_=plane_grid(req['survey']['plane']);R=body_to_earth(c['attitude']);body=(points-c['position_earth'])@R;gust=np.column_stack([.1*points[:,1],-.2*points[:,0],.3*points[:,2]+.28]);velocity=(11*FlightCondition(**c).vectors()[0]-np.cross(c['rates'],body))@R.T+gust
    cases.append(dict(name='oblique_earth_gust',request=req,references=[reference('gust',gust,tolerance=2e-12,description='Direct affine Earth field at t=0.7.'),reference('relative',velocity,tolerance=2e-12,description='Rigid frame velocity subtracted in Earth axes.')]))
    source+='Engine\n1 0 1 0 0 0 0 -1 0 0 1 .03 .8 150 0\nEnd\n'
    req=request(source,dict(speed=25,alpha=0,mach=0,powers={1:100}),plane=dict(normal=[0,1,0],direction=[1,0,0],u=[-1,10],v=[-1.4,1.4],counts=[41,25]))
    points,_=plane_grid(req['survey']['plane']);rho=1.225;dv=np.sqrt(25**2+2*100/(rho*np.pi*.8**2))-25;contracted=.8*np.sqrt((25+dv/2)/(25+dv));expected=[]
    # Compute shape integrals numerically instead of using jet_profile's polynomial coefficients.
    for point in points:
        x,y,z=point;rad=np.hypot(y,z);inner=max(0,contracted-.11*dv/(25+dv)*max(x,0));outer=contracted+.11*dv/(25+dv/2)*max(x,0)
        if x<=0 or rad>=outer:expected.append([0,0,0]);continue
        def shape(r):return (1-np.clip((r-inner)/(outer-inner),0,1)**1.5)**2
        ints=quad_vec(lambda r:np.array([r*shape(r),r*shape(r)**2,r*r*shape(r),r*r*shape(r)**2]),0,outer,points=[inner] if inner>0 else None,epsabs=1e-12)[0]
        I1,I2,J1,J2=2*np.pi*rho*ints;center=200/(25*I1+np.sqrt((25*I1)**2+400*I2));swirl=-3/(25*J1+center*J2)
        expected.append(shape(rad)*np.array([center,swirl*z/rad if rad else 0,-swirl*y/rad if rad else 0]))
    cases.append(dict(name='momentum_jet',request=req,references=[reference('jet',expected,tolerance=2e-9,description='Jet amplitudes from independent numerical polar momentum integrals, with 100 N thrust and 3 N m torque.')]))
    source=(ROOT/'examples/flexible.asw').read_text()+'\nSensor\n1 1 4 .6 4 .8\nEnd\n';m=parse_asw(source)
    base=solve_static(m,FlightCondition(speed=20,alpha=5,mach=0),4,gravity=[0,0,0]);assert base['max_displacement']>.001
    sensors=base['sensors'];req=dict(action='flow_survey',source=source,survey=dict(positions=[s['position_body'] for s in sensors],equilibrium_state=base['equilibrium_state']))
    expected=[np.asarray(s['axes_body'])@s['air_velocity_sensor'] for s in sensors]
    cases.append(dict(name='deformed_sensor',request=req,references=[reference('relative',expected,tolerance=2e-8,description='Cross-path check against the full-airflow sensor on the deformed pylon.')]))
    source=(ROOT/'examples/instrumented-oscillator.asw').read_text();m=parse_asw(source)
    controller=dict(commands={'RY[2]':2},outputs=[dict(actuator='E1',expression="-100*integral('RY[2]')")])
    base=solve_static(m,FlightCondition(speed=10,alpha=0,mach=0),4,gravity=[0,0,0],controller=controller,operating_constraints=[dict(variable='command.RY[2]',quantity='force.y',target=5)])
    req=request(source,equilibrium_state=base['equilibrium_state']);cases.append(dict(name='controller_trim',request=req,references=[],expected_power=5))
    c=FlightCondition(speed=10,alpha=0,mach=0,gust=dict(type='expression',components=['0','0','.1*sin(3*t)']))
    trajectory=solve_time(m,c,4,duration=.04,dt=.02,gravity=[0,0,0],forcing='time E1\n0 0\n.02 2\n.02 5\n.04 5')
    snap=trajectory['snapshots'][1];req=request(source,checkpoint=checkpoint(trajectory,1));points,_=plane_grid(req['survey']['plane'])
    cases.append(dict(name='time_event_side',request=req,references=[reference('gust',np.broadcast_to([0,0,.1*np.sin(.06)],points.shape),tolerance=2e-12,description='Time phase at the saved forcing knot; restore its incoming event side.')],expected_power=snap['forcing_values']['E1']))
    return cases


def verify(case,out):
    count=0;maximum=0.
    for ref in case['references']:
        actual=np.asarray(out['velocity'][ref['component']]);actual=actual if ref['indices'] is None else actual[ref['indices']]
        expected=np.asarray(ref['values']);error=float(np.max(abs(actual-expected)/np.maximum(1.,abs(expected))));count+=expected.size;maximum=max(maximum,error)
        assert error<ref['tolerance'],(case['name'],ref['description'],error,ref['tolerance'])
    v={k:np.asarray(a) for k,a in out['velocity'].items()}
    for key,parts in [('relative',['kinematic','air']),('air',['gust','induced']),('induced',['lifting','volume','jet'])]:np.testing.assert_allclose(v[key],sum(v[k] for k in parts),rtol=2e-13,atol=2e-13)
    if out['plane']:
        axes=np.array([out['plane'][key] for key in ('direction','transverse','normal')]);np.testing.assert_allclose(axes@axes.T,np.eye(3),atol=1e-14)
        for key,value in v.items():np.testing.assert_allclose(out['plane_velocity'][key],value@axes.T,rtol=2e-13,atol=2e-13)
    if case['name']=='body_integrals':assert any(out['inside_body']) and not all(out['inside_body'])
    if 'expected_power' in case:assert abs(float(out['condition']['powers'].get(1,out['condition']['powers'].get('1')))-case['expected_power'])<1e-8
    if out['saved_state_residual'] is not None:assert out['saved_state_residual']<1e-7
    json.dumps(out,allow_nan=False)
    return dict(reference_values_checked=count,maximum_scaled_reference_error=maximum,samples=len(out['position']),masked_samples=len(out['valid'])-sum(out['valid']))


def main():
    cases=make_cases()
    for case in cases:
        before=deepcopy(case['request']);case['result']=dispatch(case['request']);assert case['request']==before
        case['checks']=verify(case,case['result']);print(case['name'],case['checks'],flush=True)
    files=sorted((ROOT/'openswing').glob('*.py'))+[Path(__file__),ROOT/'examples/rectangular.asw',ROOT/'examples/flexible.asw',ROOT/'examples/instrumented-oscillator.asw']
    out=dict(description='External velocity surveys: independent field integrals, coordinate kinematics, immutable deformed/controller/time states. Sensor replay is a cross-path check, not an independent physics reference.',python=platform.python_version(),numpy=np.__version__,scipy=scipy.__version__,source_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files},cases=cases)
    (ROOT/'docs/validation/flow-survey.json').write_text(json.dumps(out,indent=2)+'\n');print('All native flow survey cases passed.',flush=True)

if __name__=='__main__':main()
