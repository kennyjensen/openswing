"""Compare existing complete AE-2 tangent paths at the failed beta2 seed.

No equilibrium is solved and no production source is changed. Direct geometry
means the existing complete moving-field decomposition, not lagged influences.
"""
import argparse
from datetime import datetime,timezone
from pathlib import Path
import resource
import signal
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.probe_isae_ae2_cold_trace import read,write,pin


def checked(out):
    plan=read(out/'plan.json')
    assert all(pin(p['path'])==p for p in plan['pins'])
    return plan


def prepare(out):
    assert not out.exists()
    from scripts.probe_isae_ae2_incidence import checked as previous_checked
    parent=ROOT/'artifacts/isae/ae2-incidence-trace-20261110';old=previous_checked(parent)
    assert read(parent/'beta01/report.json')['status']=='VERIFIED_WARM_EQUILIBRIUM'
    assert read(parent/'beta02/solve/terminal.json')['process_reaped'] is True
    paths=[Path(__file__),parent/'plan.json',parent/'beta01/report.json',parent/'beta01/result.json',
        parent/'beta02/request.json',parent/'beta02/solve/terminal.json']
    paths += [Path(p['path']) for p in old['pins']]
    write(out/'plan.json',dict(observed_utc=datetime.now(timezone.utc).isoformat(),
        request=str(parent/'beta02/request.json'),pins=[pin(p) for p in sorted(set(paths))],
        methods=['direct','stencil'],primary_votes_added=0,
        maximum_scaled_column_difference=2e-5,maximum_relative_direction_difference=1e-4,
        gate_basis='Same scaled-column gate as test_newton_geometry_composition; direction agreement is separately required.',method=__doc__))


def matrix(out,method):
    resource.setrlimit(resource.RLIMIT_AS,(512*1024**2,)*2)
    resource.setrlimit(resource.RLIMIT_CPU,(15,)*2)
    plan=checked(out);assert method in plan['methods'];folder=out/method;folder.mkdir(exist_ok=False)
    signal.alarm(25)
    import numpy as np
    from scipy.sparse import save_npz
    from scripts.probe_isae_ae2_staged_inverse import network
    from openswing.equilibrium_state import restore
    from openswing.newton_structure import NewtonBeamFactor
    from openswing.steady_continuation import plain
    request=read(plan['request']);n=network(request);x=restore(n,request['initial_state'])
    residual=n.residual(x);before=n.nfev;cpu=time.process_time();wall=time.monotonic()
    j=n.jacobian(x,1.,_sparse=True,_direct_geometry=method=='direct')
    timing=dict(cpu_seconds=time.process_time()-cpu,wall_seconds=time.monotonic()-wall,residual_calls=n.nfev-before)
    factor=NewtonBeamFactor(n,j);direction=factor.solve(-residual)
    linear_error=float(np.max(abs(j@direction+residual)))
    assert linear_error<=1e-10*max(1.,np.max(abs(residual)))
    save_npz(folder/'matrix.npz',j)
    np.savez_compressed(folder/'state.npz',state=x,residual=residual,direction=direction)
    checked(out)
    write(folder/'report.json',plain(dict(status='COMPLETE',method=method,size=n.size,
        timing=timing,linear_error=linear_error,baseline_residual=float(np.max(abs(residual))),
        geometry=getattr(n,'geometry_derivative_diagnostics',None),
        circulation=getattr(n,'circulation_derivative_diagnostics',None),factor=factor.report,
        matrix=pin(folder/'matrix.npz'),state=pin(folder/'state.npz'),primary_votes_added=0)))
    print(plain(dict(method=method,**timing,linear_error=linear_error)),flush=True)


def assess(out):
    resource.setrlimit(resource.RLIMIT_AS,(512*1024**2,)*2)
    resource.setrlimit(resource.RLIMIT_CPU,(15,)*2)
    signal.alarm(25)
    import numpy as np
    from scipy.sparse import load_npz
    plan=checked(out);reports={m:read(out/m/'report.json') for m in plan['methods']}
    for r in reports.values():
        assert r['status']=='COMPLETE' and all(pin(r[k]['path'])==r[k] for k in ('matrix','state'))
    matrices={m:load_npz(out/m/'matrix.npz').toarray() for m in plan['methods']}
    with np.load(out/'direct/state.npz') as f:a={k:f[k].copy() for k in f.files}
    with np.load(out/'stencil/state.npz') as f:b={k:f[k].copy() for k in f.files}
    np.testing.assert_array_equal(a['state'],b['state']);np.testing.assert_array_equal(a['residual'],b['residual'])
    delta=matrices['direct']-matrices['stencil']
    scaled=float(np.max(abs(delta)/(1+abs(matrices['stencil']))))
    relative=float(np.linalg.norm(delta)/np.linalg.norm(matrices['stencil']))
    direction=float(np.linalg.norm(a['direction']-b['direction'])/np.linalg.norm(b['direction']))
    gate=scaled<=plan['maximum_scaled_column_difference'] and direction<=plan['maximum_relative_direction_difference']
    write(out/'assessment.json',dict(status='PASS' if gate else 'FAIL',
        maximum_scaled_column_difference=scaled,relative_matrix_difference=relative,
        relative_direction_difference=direction,reports=reports,primary_votes_added=0))
    assert gate,'Complete tangent paths differ beyond the declared comparison gates.'
    print(dict(status='PASS',scaled=scaled,relative=relative,direction=direction),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['prepare','matrix','assess'])
    p.add_argument('--output',type=Path,required=True);p.add_argument('--method',choices=['direct','stencil']);a=p.parse_args()
    out=a.output.resolve()
    if a.action=='matrix':matrix(out,a.method)
    else:globals()[a.action](out)
