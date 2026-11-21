"""One bounded source-modal column job with independent beam-column oracles.

This synthetic cantilever is not an original ISAE model or native ASWING target.
Euler's Pcr=pi²EI/(4L²); a massless beam with tip mass has exactly one dynamic
bending coordinate. For a dead compressive load P, q=sqrt(P/EI), a=qL,
k=P*q*cos(a)/(sin(a)-qL*cos(a)) and lambda²=-k/m.
Box integration of the published first-order beam equations replaces a by
2*n*atan(q*L/(2*n)); Pcr,n=EI*(2*n/L*tan(pi/(4*n)))². No production matrix or
solver output enters either reference. All node displacements are also checked.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import resource
import sys
import time
import traceback

ROOT=Path(__file__).resolve().parents[1]
L=2.; EI=100.; MASS=1.
PCR=math.pi**2*EI/(4*L**2)
GATES=dict(pole_scaled=2e-6,shape_absolute=2e-7,base_residual=1e-9,
           backward=1e-8,balance=1e-7,straight_base=1e-8)


def critical(count=None):
    return PCR if count is None else EI*(2*count/L*math.tan(math.pi/(4*count)))**2


def stiffness(load,count=None):
    if load==0:
        return 3*EI/L**3/(1 if count is None else 1-1/(4*count**2))
    q=math.sqrt(load/EI)
    angle=q*L if count is None else 2*count*math.atan(q*L/(2*count))
    return load*q*math.cos(angle)/(math.sin(angle)-q*L*math.cos(angle))


def shape(load,count):
    values=[]
    for j in range(count+1):
        s=L*j/count
        if load==0:
            value=(L*s*s/2-s**3/6-(L/count)**2*s/12)/(L**3/3-L*(L/count)**2/12)
        else:
            q=math.sqrt(load/EI);step=2*math.atan(q*L/(2*count));a=count*step;b=j*step
            value=(math.sin(a)*(1-math.cos(b))+math.cos(a)*(math.sin(b)-q*s))/(math.sin(a)-q*L*math.cos(a))
        values.append(value)
    return values


def run(args):
    out=Path(args.output);out.mkdir(parents=True,exist_ok=False)
    write=lambda name,v:(out/name).write_text(json.dumps(v,indent=2,allow_nan=False)+'\n')
    pins={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
          for p in [*sorted((ROOT/'openswing').glob('*.py')),Path(__file__),ROOT/'examples/euler-column.asw',
                    ROOT/'.reference/asw_theory.pdf',ROOT/'.reference/asw_uns_theory.pdf']}
    load=args.ratio*(critical(args.intervals) if args.grid_critical else PCR)
    reference=dict(load=load,continuum_critical=PCR,grid_critical=critical(args.intervals),
                   continuum_stiffness=stiffness(load),grid_stiffness=stiffness(load,args.intervals),
                   normalized_displacement=shape(load,args.intervals))
    request=dict(action='modes',mode='modes',source=(ROOT/'examples/euler-column.asw').read_text(),
        condition=None,strut_mode='bilateral',
        panels=dict(default=args.intervals,beams={'1':dict(count=args.intervals,spacing='uniform')}),
        numerics=dict(beam_interpolation='drela-segspl-v1',structural_operator='drela-fixed-vacuum-v1'),
        modes=dict(frame='fixed',vacuum=True,count=2,shift=[-.02,0.],method=args.method,
                   step=1e-5,rank_tolerance=1e-9,matrices=True,
                   position=[0.,0.,0.],attitude=[-90.,0.,0.],gravity_magnitude=load))
    write('plan.json',dict(scope='Independent synthetic Euler-column supplement; not native ASWING validation.',
        source_pins=pins,gates=GATES,reference=reference,arguments=vars(args),
        expected_cold_solves=1,expected_fresh_residuals=1,child_address_space_bytes=512*1024**2))
    write('request.json',request)
    resource.setrlimit(resource.RLIMIT_AS,(512*1024**2,512*1024**2))
    start=time.monotonic();report=dict(status='RUNNING',goal_complete=False)
    try:
        import numpy as np
        sys.path.insert(0,str(ROOT))
        from openswing.bridge import dispatch
        from openswing.asw import parse_asw
        from openswing.source_dynamics import SourceDynamicNetwork
        from openswing.equilibrium_state import warm_start_recipe,restore
        from openswing.network import network_snapshot
        print(f'BEGIN column n={args.intervals} P/Pcr={load/PCR:.9g}',flush=True)
        result=dispatch(request);write('result.json',result)
        base=result['base'];saved=base['equilibrium_state']
        model=parse_asw(request['source'],beam_interpolation='drela-segspl-v1')
        net=SourceDynamicNetwork(model,request['panels'],None,base['gravity_body'],[],
            mesh_recipe=warm_start_recipe(model,request['panels'],saved))
        state=restore(net,saved);assert net.nfev==0
        zero=np.zeros_like(net.rj)
        residual,data=net.residual(state,detail=True,elastic_motion=(zero,zero,zero,zero),
                                  circulation_rate=np.zeros(net.circulation_basis.panels))
        assert net.nfev==1
        fresh=network_snapshot(net,residual,data);write('fresh-base.json',fresh)
        write('fresh-residual.json',residual.tolist())
        assert len(result['modes'])==2
        target=complex(-reference['grid_stiffness']/MASS)**.5
        actual=np.array([complex(*m['eigenvalue']) for m in result['modes']])
        expected=np.array([target,-target])
        from scipy.optimize import linear_sum_assignment
        i,j=linear_sum_assignment(abs(actual[:,None]-expected[None,:]))
        pole_error=float(np.max(abs(actual[i]-expected[j])/np.maximum(1.,abs(expected[j]))))
        backward=max(max(m['right_backward_error'],m['left_backward_error']) for m in result['modes'])
        assert result['converged'] and base['converged'] and fresh['converged']
        checks=dict(pole_scaled=pole_error,base_residual=float(np.max(abs(residual))),backward=backward,
            balance=max(np.linalg.norm(fresh['force_balance']),np.linalg.norm(fresh['moment_balance'])),
            straight_base=max(np.linalg.norm(np.asarray(node['position'])-[0.,L*k/args.intervals,0.])
                              for k,node in enumerate(fresh['nodes'])))
        shapes=[]
        for mode in result['modes']:
            nodes=mode['output']['nodes']
            displacement=np.array([np.asarray(node['displacement']['real'])+1j*np.asarray(node['displacement']['imag']) for node in nodes])
            normalized=displacement[:,2]/displacement[-1,2]
            shapes.append(float(np.max(abs(normalized-reference['normalized_displacement']))))
        checks['shape_absolute']=max(shapes)
        for name,value in checks.items():assert value<=GATES[name],(name,value,GATES[name])
        unstable=reference['grid_stiffness']<0
        assert any(mode['stability']=='unstable' for mode in result['modes'])==unstable
        assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==v for p,v in pins.items())
        report.update(status='PASS',checks=checks,reference=reference,poles=[m['eigenvalue'] for m in result['modes']],
            classifications=[m['stability'] for m in result['modes']],finite_dimension=result['diagnostics'].get('finite_dimension'),
            physical_checks_pass=True,source_pins_unchanged=True)
    except BaseException as error:
        report.update(status='FAILURE_RETAINED',error=repr(error),traceback=traceback.format_exc())
        raise
    finally:
        report.update(seconds=time.monotonic()-start,peak_RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        write('report.json',report)
        print(json.dumps({k:v for k,v in report.items() if k not in ('reference','traceback')}),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output');parser.add_argument('--intervals',type=int,required=True)
    parser.add_argument('--ratio',type=float,required=True);parser.add_argument('--grid-critical',action='store_true')
    parser.add_argument('--method',choices=('dense','full_shift_invert'),default='full_shift_invert')
    run(parser.parse_args())
