"""Independent physical directional probes of the saved AE-2 stalled trial."""
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
    parent=ROOT/'artifacts/isae/ae2-stalled-saved-20261110'
    old=base.checked(parent)
    for phase in old['phases']:base.receipt(parent,phase)
    paths=[Path(p['path']) for p in old['pins']]+[Path(__file__),parent/'plan.json',parent/'assessment.json']
    for phase in old['phases']:
        paths += [parent/phase/f for f in ('terminal.json','sources-verified.json')]
    for phase in ('capture','direct','stencil','probe'):paths.append(parent/phase/'report.json')
    write(out/'plan.json',dict(observed_utc=datetime.now(timezone.utc).isoformat(),method=__doc__,
        parent=str(parent),pins=[pin(p) for p in sorted(set(paths))],limits=base.LIMITS,
        phases=['directional'],steps=[1e-3,1e-4,1e-5,1e-6],primary_votes_added=0))


def directional(out,plan):
    import numpy as np
    from scipy.sparse import load_npz
    parent=Path(plan['parent']);n,x,r=base.trial(parent)
    fields=read(parent/'capture/fields.json')
    ranges=[('compatibility',0,6*n.ne),('force',6*n.ne,6*n.ne+3*n.nn),
        ('moment',6*n.ne+3*n.nn,6*n.ne+6*n.nn),('constraints',6*(n.ne+n.nn),n.gamma_start),
        ('circulation',n.gamma_start,n.operating_start)]
    records=[]
    for method in ('direct','stencil'):
        report=read(parent/method/'report.json')
        assert all(pin(report[k]['path'])==report[k] for k in ('matrix','direction','trial','capture','request'))
        jac=load_npz(parent/method/'matrix.npz')
        with np.load(parent/method/'direction.npz') as data:d=data['direction'].copy()
        predicted=jac@d;probes=[]
        for h in plan['steps']:
            actual=(n.residual(x+h*d)-n.residual(x-h*d))/(2*h)
            delta=actual-predicted
            probes.append(dict(step=h,relative_l2_error=float(np.linalg.norm(delta)/np.linalg.norm(predicted)),
                scaled_max_error=float(np.max(abs(delta))/np.max(abs(predicted)))))
        full=n.residual(x+d);curvature=full-(r+predicted);total=float(curvature@curvature)
        blocks={name:dict(maximum=float(np.max(abs(curvature[first:stop]))),
            squared_fraction=float(curvature[first:stop]@curvature[first:stop]/total)) for name,first,stop in ranges}
        controls=[]
        for row in sorted(set(t['controlling_row'] for t in read(parent/'probe/report.json')['trials'] if 'controlling_row' in t)):
            entry=dict(row=row,block=next(name for name,first,stop in ranges if first<=row<stop))
            if n.gamma_start<=row<n.operating_start:
                strip=fields['strips'][row-n.gamma_start]
                entry.update(beam=strip['beam'],t=strip['t'],cl=strip['cl'],outside_reported_cl_limits=strip['stalled'])
            controls.append(entry)
        records.append(dict(method=method,linear_defect=float(np.max(abs(predicted+r))),
            direction_norm=float(np.linalg.norm(d)),probes=probes,full_step_curvature=blocks,controlling_rows=controls))
        del jac
    write(out/'assessment.json',dict(status='COMPLETE_DIRECTIONAL_DIAGNOSTIC',records=records,
        baseline_residual=float(np.max(abs(r))),fresh_residual_calls=n.nfev,primary_votes_added=0,accepted_state=False,
        qualifications=['These probes diagnose a nonconverged trial; they do not validate an equilibrium or a reference point.',
            'Centered directional probes are independent physical residual evaluations; no tangent is used in evaluating them.',
            'A directional check does not establish every Jacobian column or prove a fold/unique branch.']))
    print(records,flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['prepare','launch'])
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.action=='prepare':prepare(a.output.resolve())
    else:
        base.directional=directional
        base.launch(a.output.resolve(),'directional')
