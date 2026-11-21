"""Locate the shared AE-2 directional derivative defect by physical state block."""
import argparse
from datetime import datetime,timezone
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts import probe_isae_ae2_stalled_tangent as base
from scripts.probe_isae_ae2_cold_trace import read,write,pin


def prepare(out):
    assert not out.exists()
    parent=ROOT/'artifacts/isae/ae2-stalled-saved-20261110';old=base.checked(parent)
    direction=ROOT/'artifacts/isae/ae2-stalled-direction-20261110';base.checked(direction)
    base.receipt(direction,'directional')
    paths=[Path(p['path']) for p in old['pins']]+[Path(__file__),parent/'plan.json',parent/'assessment.json',
        direction/'plan.json',direction/'assessment.json',direction/'directional/terminal.json',
        direction/'directional/sources-verified.json']
    for phase in ('capture','stencil'):
        base.receipt(parent,phase)
        paths += [parent/phase/f for f in ('terminal.json','sources-verified.json','report.json')]
    write(out/'plan.json',dict(observed_utc=datetime.now(timezone.utc).isoformat(),method=__doc__,
        parent=str(parent),pins=[pin(p) for p in sorted(set(paths))],limits=base.LIMITS,
        phases=['blocks'],steps=[1e-4,1e-5,1e-6],primary_votes_added=0))


def blocks(out,plan):
    import numpy as np
    from scipy.sparse import load_npz
    parent=Path(plan['parent']);n,x,r=base.trial(parent)
    report=read(parent/'stencil/report.json')
    assert all(pin(report[k]['path'])==report[k] for k in ('matrix','direction','trial','capture','request'))
    jac=load_npz(parent/'stencil/matrix.npz')
    with np.load(parent/'stencil/direction.npz') as data:d=data['direction'].copy()
    columns=[('geometry',0,6*n.nn),('internal_wrenches',6*n.nn,6*(n.nn+n.ne)),
        ('reactions',6*(n.nn+n.ne),n.gamma_start),('circulation',n.gamma_start,n.operating_start)]
    rows=[('compatibility',0,6*n.ne),('force',6*n.ne,6*n.ne+3*n.nn),
        ('moment',6*n.ne+3*n.nn,6*n.ne+6*n.nn),('constraints',6*(n.ne+n.nn),n.gamma_start),
        ('circulation',n.gamma_start,n.operating_start)]
    result=[];arrays={}
    for name,first,stop in columns:
        local=np.zeros_like(d);local[first:stop]=d[first:stop];predicted=jac@local
        for h in plan['steps']:
            actual=(n.residual(x+h*local)-n.residual(x-h*local))/(2*h);delta=actual-predicted
            result.append(dict(columns=name,step=h,column_direction_norm=float(np.linalg.norm(local)),
                predicted_derivative_norm=float(np.linalg.norm(predicted)),defect_norm=float(np.linalg.norm(delta)),
                relative_to_full_newton_derivative=float(np.linalg.norm(delta)/np.linalg.norm(r)),
                maximum_defect=float(np.max(abs(delta))),maximum_row=int(np.argmax(abs(delta))),
                row_blocks={kind:float(np.linalg.norm(delta[a:b])) for kind,a,b in rows}))
            if h==1e-5:
                arrays[name+'_actual']=actual;arrays[name+'_predicted']=predicted;arrays[name+'_defect']=delta
    np.savez_compressed(out/'blocks/arrays.npz',**arrays)
    write(out/'assessment.json',dict(status='COMPLETE_BLOCK_DIAGNOSTIC',records=result,
        arrays=pin(out/'blocks/arrays.npz'),baseline_derivative_norm=float(np.linalg.norm(r)),
        physical_residual_calls=n.nfev,primary_votes_added=0,accepted_state=False))
    print(result,flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['prepare','launch'])
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.action=='prepare':prepare(a.output.resolve())
    else:
        base.blocks=blocks
        base.launch(a.output.resolve(),'blocks')
