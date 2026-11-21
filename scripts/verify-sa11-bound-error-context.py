"""Replay one rejected SA-11 receiver through the current diagnostic observer.

One influence row is evaluated at saved circulation; no equilibrium solve,
geometry repair, acceptance override or new reference comparison is made.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from openswing.airflow_diagnostics import local_vortex_breakdown, breakdown_message
from openswing.factored_influence import FactoredInfluence

SOURCE = ROOT/'artifacts/isae/sa11-winglet-current-wind-20261108/g3-r2-current'
OUT = ROOT/'artifacts/isae/sa11-shared-bound-corner-20261108/error-context.json'
sha = lambda p:hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    assert not OUT.exists()
    report = json.loads((SOURCE/'report.json').read_text())
    for name,expected in report['artifact_sha256'].items(): assert sha(SOURCE/name)==expected
    with np.load(SOURCE/'state.npz') as data:
        f={k:data[k].copy() for k in data.files}
    normal=f['velocity']-np.sum(f['velocity']*f['tangent'],axis=1)[:,None]*f['tangent']
    i=int(np.argmax(np.linalg.norm(normal,axis=1)));n=len(f['gamma'])
    original=report['production']['details']['vortex_breakdown']
    assert np.array_equal(f['hv'][i],np.array(original['influence_receiver']))
    assert n==128 and np.all(f['physical']==1)
    order=np.r_[i,np.flatnonzero(np.arange(n)!=i)]
    # The retained native conversion has64 main,32 right,32 left strips.
    beams=np.r_[np.full(64,1),np.full(32,2),np.full(32,3)]
    p=dict(physical=f['physical'][order],beam=beams[order],t=f['rm'][order,1])
    g={key:f[key][order] for key in ('a','b','physical')};g['hv']=f['hv'][i:i+1]
    wind=f['wind'];pg=np.eye(3)+(1/np.sqrt(1-(240/340.21)**2)-1)*np.outer(wind,wind)
    exclude=np.zeros((1,n),dtype=bool);exclude[0,0]=True
    operator=FactoredInfluence(g['hv'],g['a'],g['b'],wind,pg,exclude_bound=exclude)
    gamma=f['gamma'][order]
    incident=np.array(original['incident_velocity']);jet=np.array(original['jet_velocity'])
    total=incident+jet+operator.apply(gamma)[0]
    error=float(np.max(abs(total-f['velocity'][i])))
    assert error<1e-8
    diagnostic=local_vortex_breakdown(operator,0,gamma,p,g,wind,
        np.maximum(.25*f['chord'][order],f['ds'][order]),incident,jet,total)
    main=diagnostic['bound_sources'][0]
    assert main['beam']==original['bound_sources'][0]['beam']
    assert abs(main['strip_t']-original['bound_sources'][0]['strip_t'])<1e-14
    np.testing.assert_allclose(main['velocity'],original['bound_sources'][0]['velocity'],rtol=1e-12,atol=1e-9)
    assert main['shared_bound_endpoint'] is not None
    explanation=breakdown_message(diagnostic)
    assert 'Distance to its physical bound segment=' in explanation
    assert 'Shared bound endpoint' in explanation
    unchanged_prefix=report['production']['error'].split(' Largest bound-vortex contribution:')[0]
    result=dict(observed_utc=datetime.now(timezone.utc).isoformat(),source=str(SOURCE.relative_to(ROOT)),
        source_report_sha256=sha(SOURCE/'report.json'),source_state_sha256=sha(SOURCE/'state.npz'),
        observer_sha256=sha(ROOT/'openswing/airflow_diagnostics.py'),driver_sha256=sha(Path(__file__)),
        source_to_reordered_panel_index=order.tolist(),diagnostic=diagnostic,
        maximum_velocity_difference_m_s=error,original_exception=report['production']['error'],
        updated_exception=unchanged_prefix+explanation,new_equilibrium_calls=0,
        note='Saved rejected state remains rejected; two sections are beyond local stall limits in this fine current-wind alpha5 diagnostic. No post-stall repair or reference rescore. The replay only verifies source context at its existing worst receiver.')
    OUT.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps(dict(error=error,source=main,updated_exception=result['updated_exception'])))


if __name__=='__main__':main()
