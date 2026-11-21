"""Track the coupled ST-1 modal branches and check a smaller spectral survey."""
import argparse
from pathlib import Path
import resource
import time

import verify_st1_modal_mechanics as main

common=main.common
ROOT=main.ROOT
BASE=ROOT/'artifacts/isae/st1-modal-mechanics-20261109'
JOBS=[dict(name='unloaded',gravity=0.,nominal=40),dict(name='quarter-gravity',gravity=2.4525,nominal=40),
      dict(name='half-gravity',gravity=4.905,nominal=40),dict(name='fine-count12',gravity=9.81,nominal=80)]


def prepare(out):
    prior=common.read(BASE/'plan.json');common.authenticate(prior['pins']);pins=dict(prior['pins'])
    for path in (Path(__file__),BASE/'plan.json',BASE/'job-2/request.json',BASE/'job-2/result.json',BASE/'job-2/report.json',BASE/'job-3/terminal.json'):
        pins[path.relative_to(ROOT).as_posix()]=common.sha(path)
    common.write(out/'plan.json',dict(observed_utc=common.utc(),pins=pins,jobs=JOBS,count=12,
        source_request='artifacts/isae/st1-modal-mechanics-20261109/job-2/request.json',
        protocol='Same coupled blade and source vacuum operator. Three lower-gravity equilibria diagnose branch identity; '
                 'no altered-gravity state receives a native comparison vote. Nominal80 count12 retains all named targets '
                 'while omitting unneeded high modes from the timed-out count16 survey. Full-pencil residual gate unchanged.',
        limits=dict(blas_threads=1,address_space_mib=512,cpu_seconds=15,wall_seconds=25)))


def run(out,index):
    plan=common.read(out/'plan.json');common.authenticate(plan['pins']);job=plan['jobs'][index]
    folder=out/f'job-{index}';folder.mkdir()
    request=common.read(ROOT/plan['source_request']);request['modes']['count']=12
    request['gravity']=[0.,0.,-job['gravity']]
    request['panels']['default']=request['panels']['beams']['1']['count']=job['nominal']
    common.write(folder/'request.json',request)
    import numpy as np
    from scipy.sparse import save_npz
    from openswing.bridge import dispatch
    from openswing import linear_dynamics as dynamics
    original=dynamics.linearize;captured=[]
    def capture(system,*args,**kwargs):
        start=time.monotonic();a,m=original(system,*args,**kwargs)
        captured.append((system,a,m));print('linearization completed',time.monotonic()-start,flush=True);return a,m
    dynamics.linearize=capture;started=time.monotonic()
    try:result=dispatch(request)
    finally:dynamics.linearize=original
    seconds=time.monotonic()-started;common.write(folder/'result.json',result)
    assert len(captured)==1;system,a,m=captured[0]
    save_npz(folder/'A.npz',a);save_npz(folder/'M.npz',m)
    base=result['base'];assert result['converged'] and base['converged'] and base['residual']<1e-8
    residual=float(np.max(abs(system.residual(np.zeros(system.size),np.zeros(system.size)))))
    assert residual<1e-8 and system.network.ng==0 and len(base['nodes'])==job['nominal']+1
    assert result['frame_mode']=='fixed' and result['vacuum'] and base['gravity_body']==request['gravity']
    audits=[]
    for mode in result['modes']:
        lam=complex(*mode['eigenvalue']);values=[]
        for side in ('right','left'):
            v=np.asarray(mode[side]['real'])+1j*np.asarray(mode[side]['imag'])
            av,mv=(a@v,m@v) if side=='right' else (v.conjugate()@a,v.conjugate()@m)
            error=float(np.linalg.norm(av-lam*mv)/(np.linalg.norm(av)+abs(lam)*np.linalg.norm(mv)))
            assert error<1e-8;values.append(error)
        audits.append(dict(index=mode['index'],right=values[0],left=values[1]))
    classified=[main.shape_activity(mode,base,main.CASES['coupled']) for mode in result['modes'] if mode['eigenvalue'][1]>1e-6]
    common.authenticate(plan['pins'])
    common.write(folder/'report.json',dict(observed_utc=common.utc(),job=job,seconds=seconds,base_residual=residual,
        peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,pencil_audits=audits,classified=classified,
        plan_sha256=common.sha(out/'plan.json'),artifacts={p.name:common.sha(p) for p in folder.iterdir() if p.is_file()}))
    print(dict(job=job,seconds=seconds,classified=classified),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=('prepare','run'))
    p.add_argument('--output',type=Path,required=True);p.add_argument('--index',type=int)
    args=p.parse_args();common.bounded()
    if args.action=='prepare':args.output.mkdir();prepare(args.output.resolve())
    else:run(args.output.resolve(),args.index)
