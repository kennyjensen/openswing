"""Test the existing fourth-order geometry partial at the AE-2 failed trial.

This changes only the diagnostic Jacobian assembly option. Physical equations,
inputs and acceptance gates are unchanged; no state is accepted by this probe.
"""
import argparse
from datetime import datetime,timezone
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts import probe_isae_ae2_stalled_tangent as base
from scripts.probe_isae_ae2_cold_trace import read,write,pin


def prepare(out):
    assert not out.exists()
    parent=ROOT/'artifacts/isae/ae2-stalled-saved-20261110';old=base.checked(parent)
    block=ROOT/'artifacts/isae/ae2-stalled-blocks-20261110';base.checked(block);base.receipt(block,'blocks')
    paths=[Path(p['path']) for p in old['pins']]+[Path(__file__),parent/'plan.json',parent/'assessment.json',
        block/'plan.json',block/'assessment.json',block/'blocks/terminal.json',block/'blocks/sources-verified.json']
    for phase in ('capture','direct','stencil','probe'):
        base.receipt(parent,phase);paths += [parent/phase/f for f in ('report.json','terminal.json','sources-verified.json')]
    write(out/'plan.json',dict(observed_utc=datetime.now(timezone.utc).isoformat(),method=__doc__,
        parent=str(parent),pins=[pin(p) for p in sorted(set(paths))],limits=base.LIMITS,
        phases=['centered','verify'],geometry_difference_order=4,geometry_difference_step=1e-6,
        directional_steps=[1e-3,1e-4,1e-5,1e-6],maximum_directional_relative_error=1e-4,
        trial_powers=list(range(13)),primary_votes_added=0))


def centered(out,plan):
    import numpy as np
    from scipy.sparse import save_npz
    from openswing import geometry_tangent
    from openswing.newton_structure import NewtonBeamFactor
    from openswing.steady_continuation import plain
    n,x,r=base.trial(Path(plan['parent']));native=geometry_tangent.geometry_columns
    def precise(*args,**kwargs):
        kwargs['difference_order']=plan['geometry_difference_order']
        kwargs['step']=plan['geometry_difference_step']
        return native(*args,**kwargs)
    before=time.monotonic();cpu=time.process_time();calls=n.nfev
    geometry_tangent.geometry_columns=precise
    try:jac=n.jacobian(x,1.,_sparse=True,_direct_geometry=True)
    finally:geometry_tangent.geometry_columns=native
    timing=dict(wall_seconds=time.monotonic()-before,cpu_seconds=time.process_time()-cpu,residual_calls=n.nfev-calls)
    diagnostics=n.geometry_derivative_diagnostics
    assert diagnostics['difference_order']==4 and diagnostics['direct_geometry_columns']==6*n.nn
    factor=NewtonBeamFactor(n,jac);direction=factor.solve(-r)
    defect=float(np.max(abs(jac@direction+r)));assert defect<=1e-10
    save_npz(out/'centered/matrix.npz',jac);np.savez_compressed(out/'centered/direction.npz',direction=direction)
    write(out/'centered/report.json',plain(dict(status='COMPLETE',timing=timing,geometry=diagnostics,
        linear_defect=defect,matrix=pin(out/'centered/matrix.npz'),direction=pin(out/'centered/direction.npz'),
        trial=pin(Path(plan['parent'])/'capture/trial.npz'),primary_votes_added=0)))
    print(dict(status='COMPLETE',**timing,linear_defect=defect),flush=True)


def verify(out,plan):
    import numpy as np
    from scipy.sparse import load_npz
    base.receipt(out,'centered');report=read(out/'centered/report.json')
    assert all(pin(report[k]['path'])==report[k] for k in ('matrix','direction','trial'))
    n,x,r=base.trial(Path(plan['parent']));jac=load_npz(out/'centered/matrix.npz')
    with np.load(out/'centered/direction.npz') as data:d=data['direction'].copy()
    predicted=jac@d;probes=[];trials=[];error=float(np.max(abs(r)))
    for h in plan['directional_steps']:
        actual=(n.residual(x+h*d)-n.residual(x-h*d))/(2*h)
        probes.append(dict(step=h,relative_l2_error=float(np.linalg.norm(actual-predicted)/np.linalg.norm(predicted)),
            scaled_max_error=float(np.max(abs(actual-predicted))/np.max(abs(predicted)))))
    for power in plan['trial_powers']:
        scale=2.**-power;value=n.residual(x+scale*d);norm=float(np.max(abs(value)))
        trials.append(dict(power=power,scale=scale,error=norm,ratio=norm/error,
            accepted_by_merit=bool(norm<error*(1-1e-4*scale) or norm<=1e-12),original_search=power<=8))
    gate=all(p['relative_l2_error']<=plan['maximum_directional_relative_error'] for p in probes[-2:])
    write(out/'assessment.json',dict(status='DIRECTIONAL_GATE_PASS' if gate else 'DIRECTIONAL_GATE_FAIL',
        probes=probes,trials=trials,direction_norm=float(np.linalg.norm(d)),baseline_error=error,
        matrix_report=report,accepted_state=False,primary_votes_added=0))
    print(dict(gate=gate,probes=probes,accepted_powers=[r['power'] for r in trials if r['accepted_by_merit']]),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['prepare','launch'])
    p.add_argument('--output',type=Path,required=True);p.add_argument('--phase',choices=['centered','verify']);a=p.parse_args()
    if a.action=='prepare':prepare(a.output.resolve())
    else:
        base.centered=centered;base.verify=verify
        base.launch(a.output.resolve(),a.phase)
