"""Check the independently verified static threshold through the public modal API."""
import argparse
import hashlib
import json
from pathlib import Path
import resource
import sys
import time
import traceback

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
def write(p,x):Path(p).write_text(json.dumps(x,indent=2,allow_nan=False)+'\n')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def run(args):
    out=Path(args.output);out.mkdir(parents=True,exist_ok=False)
    static=Path(args.static_case);target=json.loads((static/'report.json').read_text())
    setup=json.loads((static/'plan.json').read_text());count=setup['arguments']['intervals']
    assert target['status']=='PASS_DISCRETE_STATIC_CHECK'
    for p,h in setup['pins'].items():assert sha(ROOT/p)==h,p
    gravity=target['gravity']*args.ratio
    pins={str(p.relative_to(ROOT)):sha(p) for p in [*sorted((ROOT/'openswing').glob('*.py')),
        Path(__file__),ROOT/'examples/self-weight-column.asw']}
    static_pins={str(static/p):sha(static/p) for p in ('report.json','plan.json','critical-mode.npz')}
    request=dict(action='modes',mode='modes',source=(ROOT/'examples/self-weight-column.asw').read_text(),condition=None,
        panels=dict(default=count,beams={'1':dict(count=count,spacing='uniform')}),
        numerics=dict(beam_interpolation='drela-segspl-v1',structural_operator='drela-fixed-vacuum-v1'),
        modes=dict(frame='fixed',vacuum=True,count=4,shift=[-.02,0.],method='full_shift_invert',
            step=1e-5,rank_tolerance=1e-9,matrices=False,
            position=[0.,0.,0.],attitude=[-90.,0.,0.],gravity_magnitude=gravity))
    gates=dict(base=1e-9,preload=1e-10,straight=1e-8,backward=1e-8,critical_shape=.001)
    write(out/'request.json',request)
    write(out/'plan.json',dict(pins=pins,static_pins=static_pins,gates=gates,
        load=gravity,discrete_critical_load=target['gravity'],load_units='gravity m/s^2',
        native_ASWING_validation=False,scope=__doc__))
    began=time.monotonic();report=dict(status='RUNNING',native_ASWING_validation=False,goal_complete=False)
    try:
        import numpy as np
        from scipy.sparse import save_npz,load_npz,csc_matrix
        from scipy.sparse.linalg import norm
        import openswing.linear_dynamics as dynamics
        from openswing.bridge import dispatch
        from openswing.asw import parse_asw
        from openswing.source_dynamics import SourceDynamicNetwork
        from openswing.equilibrium_state import restore,warm_start_recipe
        from openswing.network import network_snapshot
        original=dynamics.linearize;captured=[]
        def retain(system,*a,**kw):
            assert not captured
            aa,mm=original(system,*a,**kw)
            save_npz(out/'A.npz',csc_matrix(aa));save_npz(out/'M.npz',csc_matrix(mm));captured.append(True)
            return aa,mm
        dynamics.linearize=retain
        try:result=dispatch(request)
        finally:dynamics.linearize=original
        write(out/'result.json',result)
        assert result['converged'] and result['base']['converged'] and len(result['modes'])==4
        model=parse_asw(request['source'],beam_interpolation='drela-segspl-v1')
        saved=result['base']['equilibrium_state']
        n=SourceDynamicNetwork(model,request['panels'],None,result['base']['gravity_body'],[],
            mesh_recipe=warm_start_recipe(model,request['panels'],saved))
        state=restore(n,saved);assert n.nfev==0
        residual,data=n.residual(state,detail=True)
        write(out/'fresh-base.json',network_snapshot(n,residual,data))
        force=data['source_discrete']['force_local'];expected=np.zeros_like(force)
        expected[:,1]=-gravity*(1-(n.rj[n.a,1]+n.rj[n.b,1])/2)
        checks=dict(base=float(np.max(abs(residual))),straight=float(np.max(abs(data['r']-n.rj))),
            preload=float(np.max(abs(force-expected)))/gravity,backward=0.,critical_shape=0.)
        aa,mm=load_npz(out/'A.npz'),load_npz(out/'M.npz')
        for mode in result['modes']:
            pole=complex(*mode['eigenvalue'])
            for side in ('left','right'):
                v=np.asarray(mode[side]['real'])+1j*np.asarray(mode[side]['imag'])
                a,m=(aa.T,mm.T) if side=='left' else (aa,mm)
                value=pole.conjugate() if side=='left' else pole
                error=float(np.max(abs(a@v-value*(m@v)))/((norm(a,np.inf)+abs(value)*norm(m,np.inf))*np.max(abs(v))))
                checks['backward']=max(checks['backward'],error)
        near=sorted(result['modes'],key=lambda m:abs(complex(*m['eigenvalue'])))[:2]
        reference=np.load(static/'critical-mode.npz')['physical_shape']
        for mode in near:
            nodes=mode['output']['nodes']
            shape=np.array([np.r_[np.asarray(x['displacement']['real'])+1j*np.asarray(x['displacement']['imag']),
                np.asarray(x['rotation']['real'])+1j*np.asarray(x['rotation']['imag'])] for x in nodes])
            shape/=shape[-1,2]
            checks['critical_shape']=max(checks['critical_shape'],float(np.max(abs(shape-reference))/np.max(abs(reference))))
        poles=[complex(*m['eigenvalue']) for m in near]
        if args.ratio<1:
            assert all(abs(z.real)<1e-7 and abs(z.imag)>1e-5 for z in poles)
            assert not any(m['stability']=='unstable' for m in result['modes'])
        else:
            assert all(abs(z.imag)<1e-7 for z in poles) and min(z.real for z in poles)<0<max(z.real for z in poles)
            assert sum(m['stability']=='unstable' for m in result['modes'])==1
        for k,v in checks.items():assert v<=gates[k],(k,v,gates[k])
        assert all(sha(ROOT/p)==h for p,h in pins.items())
        assert all(sha(p)==h for p,h in static_pins.items())
        report.update(status='PASS_DISCRETE_ANALYTICAL_CHECK',checks=checks,gravity=gravity,
            near_critical_poles=[m['eigenvalue'] for m in near],independent_pencil_checks=8,
            higher_mode_frequency_validation=False)
    except BaseException as error:
        report.update(status='FAILURE_RETAINED',error=repr(error),traceback=traceback.format_exc());raise
    finally:
        report.update(seconds=time.monotonic()-began,peak_RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        write(out/'report.json',report);print(json.dumps({k:v for k,v in report.items() if k!='traceback'}),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('output');p.add_argument('static_case')
    p.add_argument('--ratio',type=float,choices=[.9999,1.0001],required=True)
    run(p.parse_args())
