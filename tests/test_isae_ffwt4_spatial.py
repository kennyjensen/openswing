"""Spatial evidence must retain attachments and expose deformation errors."""
import importlib.util
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
spec = importlib.util.spec_from_file_location('ffwt4_spatial', ROOT/'scripts/assess-isae-ffwt4-spatial.py')
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)
# Small synthetic attachment fixture; the tests need no downloaded archive.
STATIONS = [.0069,.017,.0409,.1122,.155,.1978,.2122,.255,.2978,.3145,.328,.3415,.3521,.4243,.4965]
SOURCE = ('Weight\n* 1 1 1 1 1 1 1 1 1 1 1\n' +
          '\n'.join(f'1 {sign*t} 0 0 0 1 0 0 0 0 0 0'
                    for sign in (-1,1) for t in STATIONS for _ in range(2)) + '\nEnd\n')


def state(nominal):
    ts = audit.expected_stations(SOURCE, nominal)
    n = len(ts)
    result = dict(equilibrium_state=dict(
        identity=dict(stations={'1':[ts,list(range(n))]}, nodes=[[0.,t,0.] for t in ts],
                      elements=[[i,i+1] for i in range(n-1)]),
        positions=[[0.,t,.003*t*t] for t in ts], rotations=[[.01*t,0.,0.] for t in ts]),
        sensors=[dict(index=1,load_trace='left',moment_local=[.7,0.,0.])])
    return result


def fields(nominal):
    return audit.mesh_fields(state(nominal), nominal, SOURCE)


def test_independent_mesh_retains_every_attachment_and_nested_station():
    coarse, fine = fields(16), fields(32)
    assert coarse['nodes'] == 47 and fine['nodes'] == 63
    for station in (-.4965,-.4243,-.0069,0.,.0069,.4243,.4965):
        assert any(abs(t-station)<1e-12 for t in fine['stations'])
    comparison = audit.compare(coarse,fine)
    assert comparison['common_nodes'] == 47
    assert comparison['passed'] == comparison['required'] == 3


def test_small_deformation_error_is_not_hidden_by_the_jig_span_or_root_moment():
    coarse, fine = fields(16), fields(32)
    coarse['displacement'][12][2] += 2e-6
    result = audit.compare(coarse,fine)
    assert result['gates']['root_moment']['passed']
    assert not result['gates']['displacement']['passed']
    assert result['gates']['displacement']['fine_scale'] == pytest.approx(.00075)
    assert result['gates']['displacement']['relative_limit'] == .001


def test_rotation_vector_error_at_an_interior_station_is_detected():
    coarse, fine = fields(16), fields(32)
    coarse['rotation_vector'][12][1] += 1e-5
    result = audit.compare(coarse,fine)
    assert result['gates']['root_moment']['passed']
    assert not result['gates']['rotation_vector']['passed']


@pytest.mark.parametrize('fault',['mandatory','jig','trace','nonfinite'])
def test_invalid_saved_mesh_or_sensor_is_rejected(fault):
    result = state(32)
    saved = result['equilibrium_state']
    if fault == 'mandatory':
        i = saved['identity']['stations']['1'][0].index(.4965)
        saved['identity']['stations']['1'][0][i] += 1e-5
    elif fault == 'jig':
        saved['identity']['nodes'][1][0] += 1e-4
    elif fault == 'trace':
        result['sensors'][0]['load_trace'] = 'right'
    else:
        saved['positions'][1][0] = float('nan')
    with pytest.raises(ValueError):
        audit.mesh_fields(result,32,SOURCE)


@pytest.mark.parametrize('fault',['missing','nonfinite_fine_only','skipped_grid'])
def test_incomplete_or_invalid_comparison_cannot_pass(fault):
    coarse, fine = fields(16), fields(32)
    if fault == 'missing':
        fine['stations'].pop(0)
    elif fault == 'nonfinite_fine_only':
        i = next(i for i,t in enumerate(fine['stations']) if all(abs(t-c)>1e-12 for c in coarse['stations']))
        fine['rotation_vector'][i][0] = float('nan')
    else:
        fine['nominal'] = 64
    with pytest.raises(ValueError):
        audit.compare(coarse,fine)
