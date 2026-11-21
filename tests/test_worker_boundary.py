"""The browser receives rejected-state evidence without accepting its loads."""
import json
from pathlib import Path
import pytest
from openswing.aero import AnalysisError
from openswing.bridge import run_json, run_worker_json


def test_sa11_rejection_survives_worker_json_without_changing_native_errors():
    # The UI's explicitly labeled, corrected-Joint example, not an ISAE pass.
    source = Path('examples/isae-sa11-wingtip-up.asw').read_text()
    request = json.dumps(dict(action='solve', source=source, panels=12,
        condition=dict(speed=240, alpha=1, mach=240/340.21, freeze_influences=True)))
    with pytest.raises(AnalysisError, match='Local section-normal Mach') as caught:
        run_json(request)
    reply = json.loads(run_worker_json(request))
    assert set(reply) == {'error', 'details'}
    assert reply['error'] == str(caught.value)
    assert reply['details'] == caught.value.details
    d = reply['details']
    assert d['maximum']['normal_mach'] >= 1
    assert d['circulation_residual'] < 1e-8
    assert d['vortex_breakdown']['axes'] == 'body'
    assert d['vortex_breakdown']['influence_geometry'] == 'frozen jig'
    sections=d['rejected_sections']
    assert len(sections)>1  # Both winglet roots must reach the browser.
    assert all(s['normal_mach']>=1 for s in sections)
    assert sections[0]['normal_mach']==d['maximum']['normal_mach']
    assert sections[0]['position']==d['maximum']['position']
    assert len({s['panel_index'] for s in sections})==len(sections)
    assert all(s['position']==s['influence_position'] for s in sections)  # Rigid frozen jig.
    forces=d['surface_force_diagnostic']
    assert forces['available'] and not forces['pitching_moment_available']
    assert len(forces['beams'])==3
    assert forces['rejected_strips']==len(sections)
    assert forces['normalization']['coefficients_available']
    assert forces['terms']['sum']['CL']>0 and forces['terms']['sum']['CD']>0
    assert 'equilibrium_state' not in reply and 'result' not in reply


def test_worker_success_keeps_native_result_and_unexpected_errors_still_raise():
    request = json.dumps(dict(action='solve', panels=4,
        source=Path('examples/rectangular.asw').read_text(), condition=dict(alpha=2, mach=0)))
    assert json.loads(run_worker_json(request)) == dict(result=json.loads(run_json(request)))
    with pytest.raises(json.JSONDecodeError):
        run_worker_json('{invalid')
