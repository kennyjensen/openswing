"""Independent scalar planar-vortex reference for the frozen jig influences.

This diagnostic uses closed-form x/y vortex integrals, no production vortex
routine or circulation solver. It retains the source section normals at the
prescribed fold and the documented smooth stall-leakage equation.
"""
import argparse,hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import numpy as np
from scipy.special import expit
from openswing.asw import parse_asw
from openswing.aero import FlightCondition
from openswing.network import exp

def read(p):return json.loads(Path(p).read_text())
def pin(p):
    p=Path(p).resolve();b=p.read_bytes();return dict(path=str(p),bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
def planar_columns(x,y,a,b):
    """Unit Gamma, bound a→b along +y, wake +x at b and −x at a."""
    x=np.asarray(x)[:,None];y=np.asarray(y)[:,None]
    da,db=np.asarray(a)[None,:]-y,np.asarray(b)[None,:]-y
    ra,rb=np.hypot(x,da),np.hypot(x,db)
    bound=-(db/rb-da/ra)/(4*np.pi*x)
    wake=(-(1+x/rb)/db+(1+x/ra)/da)/(4*np.pi)
    return bound+wake

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--study',type=Path,required=True)
    p.add_argument('--nodes',type=int,required=True);p.add_argument('--sampling',choices=('logical','physical'),default='logical')
    p.add_argument('--refinement',choices=('material','glauert'),default='material')
    p.add_argument('--plan-name',default='reference-plan-v3.json')
    args=p.parse_args();plan=read(args.study/args.plan_name)
    for item in plan['inputs']:assert pin(item['path'])==item
    old=read(plan['pose_plan']['path']);request=read(old['request']['path'])
    model=parse_asw(request['source'],beam_interpolation=request['numerics']['beam_interpolation'])
    condition=FlightCondition(**request['condition']);free=condition.speed*condition.vectors()[0]
    assert condition.mach==0 and not np.any(condition.rates) and not condition.controls
    assert not model.records.get('engine') and condition.gust is None
    assert len(model.beams)==3 and all(beam.lifting and beam.physical_index==1 for beam in model.beams)
    nodes=args.nodes;recipe=old['meshes'][str(107 if args.refinement=='glauert' else min(nodes,419))]
    beam_nodes={k:np.array(v['nodes']) for k,v in recipe['beams'].items()}
    if args.refinement=='glauert':beam_nodes={k:v[::2] for k,v in beam_nodes.items()}
    count=sum(len(v) for v in beam_nodes.values())
    while count<nodes:
        refined={}
        for k,v in beam_nodes.items():
            if args.refinement=='glauert':
                lo,hi=v[0],v[-1];theta=np.arccos(np.clip(1-2*(v-lo)/(hi-lo),-1,1))
                inserted=lo+(hi-lo)*(1-np.cos(.5*(theta[:-1]+theta[1:])))/2
            else:inserted=(v[:-1]+v[1:])/2
            refined[k]=np.sort(np.r_[v,inserted])
        beam_nodes=refined
        count=sum(len(v) for v in beam_nodes.values())
    assert count==nodes
    normals=[];spans=[];chords=[];slopes=[];low=[];high=[];a=[];b=[];middle=[];locations=[];quarter=[];beams=[]
    rotations={beam.index:np.eye(3) for beam in model.beams};anchors={}
    for h in old['hinges']:
        rotations[h['other_beam']]=exp(np.array(h['axis_jig'])*np.deg2rad(h['angle_deg']))
        anchors[h['other_beam']]=np.array([0,h['t'],0])
    for beam in model.beams:
        ends=beam_nodes[str(beam.index)];lo,hi=beam.domain
        np.testing.assert_allclose(beam.position(ends),np.stack([np.zeros_like(ends),ends,np.zeros_like(ends)],axis=1),atol=1e-15,rtol=0)
        glo,ghi=(lo,hi) if args.sampling=='logical' else (-.5,.5)
        theta=np.arccos(np.clip(1-2*(ends-glo)/(ghi-glo),-1,1))
        t=glo+(ghi-glo)*(1-np.cos(.5*(theta[:-1]+theta[1:])))/2
        q=rotations[beam.index];span=q[:,1];c=q[:,0];normal=q[:,2]
        assert np.all(beam.value('twist',t)==0) and np.all(beam.value('alpha',t)==0)
        chord=beam.value('chord',t);slope=beam.value('dCLda',t);xax=beam.value('Xax',t)
        assert np.all(chord==.078) and np.all(xax==.5)
        jig=np.stack([np.zeros_like(t),t,np.zeros_like(t)],axis=1)
        anchor=anchors.get(beam.index,np.zeros(3));r=anchor+(jig-anchor)@q.T
        a.extend(ends[:-1]);b.extend(ends[1:]);middle.extend(t);locations.extend(r);quarter.extend(r+(.25-xax)[:,None]*chord[:,None]*c)
        normals.extend(np.broadcast_to(normal,(len(t),3)));spans.extend(np.broadcast_to(span,(len(t),3)))
        chords.extend(chord);slopes.extend(slope);low.extend(beam.value('CLmin',t));high.extend(beam.value('CLmax',t));beams.extend([beam.index]*len(t))
    a,b,t,chord,slope,lower,upper,normal,span,quarter=map(np.array,(a,b,middle,chords,slopes,low,high,normals,spans,quarter))
    count=len(t);x=chord*slope/(4*np.pi)
    cp=planar_columns(x,t,a,b)
    hv=(1/(t[:,None]-b[None,:])-1/(t[:,None]-a[None,:]))/(4*np.pi)
    matrix=normal[:,2,None]*cp;rhs=normal@free
    gamma=np.linalg.solve(matrix,-rhs)
    # Independent equation-204 evaluation and exact scalar-flow derivative.
    for iteration in range(10):
        velocity=np.broadcast_to(free,(count,3)).copy();velocity[:,2]+=hv@gamma
        vp=velocity-(np.sum(velocity*span,axis=1)[:,None])*span
        speed=np.linalg.norm(vp,axis=1);cl=2*gamma/(chord*speed)
        width=condition.stall_width
        leak=width*(np.logaddexp(0,(cl-upper)/width)-np.logaddexp(0,(lower-cl)/width))
        strength=condition.stall_factor/slope if condition.stall else np.zeros_like(slope)
        residual=(matrix@gamma+rhs-strength*speed*leak)/condition.speed
        error=float(np.max(abs(residual)))
        if error<=1e-12:break
        ds=vp[:,2,None]/speed[:,None]*hv
        dcl=2/(chord*speed)[:,None]*(np.eye(count)-gamma[:,None]/speed[:,None]*ds)
        df=expit((cl-upper)/width)+expit((lower-cl)/width)
        derivative=(matrix-strength[:,None]*(leak[:,None]*ds+speed[:,None]*df[:,None]*dcl))/condition.speed
        gamma+=np.linalg.solve(derivative,-residual)
    assert error<=1e-12
    force=condition.density*gamma[:,None]*np.cross(velocity,span)*(b-a)[:,None]
    free_force=condition.density*gamma[:,None]*np.cross(free,span)*(b-a)[:,None]
    moment=np.cross(quarter,force);fm=np.cross(quarter,free_force)
    mask=(np.array(beams)==3)|((np.array(beams)==1)&(t<0))
    result=dict(nodes=nodes,cells=count,sampling=args.sampling,refinement=args.refinement,physical_residual=error,
        beam_nodes={k:v.tolist() for k,v in beam_nodes.items()},
        negative_half_lift_moment=moment[mask].sum(axis=0).tolist(),negative_half_free_moment=fm[mask].sum(axis=0).tolist(),
        circulation=gamma.tolist(),t=t.tolist(),a=a.tolist(),b=b.tolist(),beams=beams,
        nonlinear_corrections=iteration,maximum_leakage=float(np.max(abs(leak))),native_passes_added=0,
        qualification='Independent planar frozen-influence diagnostic, prescribed constant folds. Physical sampling is a counterfactual quadrature control, not a production change or authenticated native convention.')
    if nodes<=419 and args.sampling=='logical' and args.refinement=='material':
        saved=read(plan['archive_results'][str(nodes)]['path']);expected=np.array([v['circulation'] for v in saved['strips']])
        expected_t=np.array([v['t'] for v in saved['strips']])
        result['maximum_station_error']=float(np.max(abs(t-expected_t)))
        result['maximum_gamma_scaled_error']=float(np.max(abs(gamma-expected)/(1+abs(expected))))
        result['maximum_hv_velocity_error']=float(np.max(abs(velocity-np.array([v['relative_velocity'] for v in saved['strips']]))))
        assert result['maximum_station_error']<1e-14 and result['maximum_gamma_scaled_error']<1e-10
    suffix='-glauert-refinement' if args.refinement=='glauert' else ''
    output=args.study/f'reference-{args.sampling}-{nodes}{suffix}.json'
    with output.open('x') as f:json.dump(result,f,indent=2,allow_nan=False);f.write('\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('circulation','t','a','b','beams','beam_nodes')}),flush=True)
if __name__=='__main__':main()
