"""Successful large-angle progress and bounded injected repeated failures."""
from pathlib import Path
import json
import numpy as np
import pytest
from openswing.aero import AnalysisError
from openswing.equilibrium_state import capture
from test_hinge_chart_state import network


@pytest.mark.parametrize('angle',[720,-720])
def test_hinge_cold_two_turn_path_exceeds_128_accepted_levels_and_matches_law(angle,tmp_path):
    from openswing.structured_static import equilibrate
    n=network(angle);x,steps=equilibrate(n)
    rows=n.continuation_diagnostics;accepted=[r for r in rows if r['accepted']]
    assert steps==len(accepted)>128
    assert max(abs(n.residual(x)))<=1e-12
    state=capture(n,x)
    actual=state['hinge_charts'][0]['angle_rad']
    assert actual==pytest.approx(np.deg2rad(angle),abs=2e-12)
    # Source law is q[deg]=M[Nm]. Analytic outer-tip position is independent.
    theta=np.deg2rad(angle);r,q,force,moment,*_=n.unpack(x)
    np.testing.assert_allclose(r[-1],[0,2+2*np.cos(theta),2*np.sin(theta)],atol=2e-12)
    c,s=np.cos(theta),np.sin(theta)
    np.testing.assert_allclose(q[-1],[[1,0,0],[0,c,-s],[0,s,c]],atol=2e-12)
    maximum=max(row['accepted_load_rotation_increment_rad'] for row in accepted)
    assert maximum<=np.deg2rad(5)*(1+1e-12)
    (tmp_path/f'cold-{angle:+d}-budget.json').write_text(json.dumps(dict(angle_deg=angle,accepted_levels=steps,
        rejected_attempts=len(rows)-steps,residual=float(max(abs(n.residual(x)))),chart_angle_rad=actual,
        max_load_rotation_increment_rad=maximum,continuation=rows),indent=2)+'\n')


def test_hinge_repeated_failed_attempt_budget_survives_successes_and_rolls_back(monkeypatch,tmp_path):
    import openswing.structured_static as module
    n=network(720);original_factor=module.BlockFactorization;original_dense=module.DenseNewtonFactor
    control=dict(attempt=0,reject=False)
    def progress(phase,value,total):
        if phase=='static_load' and value:
            control['attempt']+=1;control['reject']=control['attempt']%2==0
    def factor(*args,**kwargs):
        if control['reject']:raise ValueError('injected factorization failure')
        return original_factor(*args,**kwargs)
    def dense(*args,**kwargs):
        if control['reject']:raise ValueError('injected full solve failure')
        return original_dense(*args,**kwargs)
    monkeypatch.setattr(module,'BlockFactorization',factor);monkeypatch.setattr(module,'DenseNewtonFactor',dense)
    with pytest.raises(AnalysisError,match='128 rejected load attempts'):
        module.equilibrate(n,progress=progress)
    rows=n.continuation_diagnostics;bad=[r for r in rows if not r['accepted']]
    assert len(bad)==128 and any(r['accepted'] for r in rows)
    assert bad[-1]['rejected_attempts']==128
    for row in bad:assert row['starting_charts']==row['restored_charts']
    assert [c['angle_chart'] for c in n.constraints if c['type']==3]==bad[-1]['restored_charts']
    (tmp_path/'repeated-failure-budget.json').write_text(json.dumps(dict(injected_failure=True,
        physical_validation_claim=False,accepted_levels=sum(r['accepted'] for r in rows),
        rejected_attempts=len(bad),continuation=rows),indent=2)+'\n')
