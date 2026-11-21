"""Ground declaration, all-row accounting and physical forwarding regressions."""
import copy
import math
from pathlib import Path
import sys

import pytest

from scripts import isae_suite_sa12 as sa12

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope='module')
def jobs():
    if not (ROOT/'.reference/isae-validation/manifest.json').exists():
        pytest.skip('Optional pinned original archive unavailable')
    before = {name for name in sys.modules if name.startswith('openswing')}
    result = sa12.plan(ROOT)
    assert {name for name in sys.modules if name.startswith('openswing')} == before
    return result


def test_all_six_tables_every_row_and_both_grids(jobs):
    assert len(jobs) == len({j['id'] for j in jobs}) == 1020
    assert sum(j['expected_outputs'] for j in jobs) == 4080
    assert len({j['table_path'] for j in jobs}) == 6
    for table in {j['table_path'] for j in jobs}:
        selected = [j for j in jobs if j['table_path'] == table]
        assert len(selected) == 170
        for n in (100, 200):
            rows = [j for j in selected if j['settings']['panels'] == n]
            assert [j['row_index'] for j in rows] == list(range(85))
            assert {j['settings']['alpha'] for j in rows} == {
                -6+i/4 for i in range(89)} - {11.25, 11.5, 11.75, 12.}
    assert all(j['required_outputs'] == ['CL', 'CD', 'CDi', 'Cm'] for j in jobs)
    assert all(not j['complete_family_reproduction'] for j in jobs)


def test_ground_and_missing_pose_are_distinct(jobs):
    for job in jobs:
        s, d = job['settings'], job['driver_declarations']
        assert s['ground_effect'] == 1  # Also the nominal infinite-height case.
        assert s['ground_normal'] == [0., 0., 1.]
        assert s['position_earth'] == [0., 0., sa12.HEIGHTS[job['height_label']]]
        assert s['attitude'] == [0., s['alpha'], 0.]
        assert d['euler_pose_recorded'] is False
        assert d['requested_nodes'] == 100 and d['node_count_token'] == '100'
        assert 'declared_panels' not in d and 'panel_token' not in d
        assert s['base_panels'] == 100 and s['panels'] == 100 * 2 ** s['mesh_level']
        assert 'interval-count reconstruction' in s['mesh_source']
        assert 'historical node array and circulation K unknown' in s['mesh_source']
        assert sa12.polar.NODE_I_QUALIFICATION in job['qualifications']
        assert 'historical Euler pose absent' in s['pose_assumption']
        assert d['anchored_defaults_selected'] == (job['flap'] != 'No_Flap' or job['height_label'] != 'inf')
        assert s['speed'] == 35.76 and s['density'] == 1.2256
        assert s['mach'] == 0. and s['freeze_influences'] is False
        assert job['archived_stall_flag'] == job['reference_row']['fields']['stall']['value']


def test_all_raw_precision_intervals_retained(jobs):
    for job in jobs:
        fields = job['reference_row']['fields']
        checks = sa12.reference_checks({k:fields[k]['value'] for k in sa12.OUTPUTS}, job['reference_row'])
        assert all(c['passed'] for c in checks)
        for c in checks:
            assert c['expected_token'] == fields[c['name']]['token']
            assert c['tolerance'] == sa12.polar.printed_value(c['expected_token'])['tolerance']
    assert min(j['reference_row']['fields']['Cm']['tolerance'] for j in jobs) < 1e-10


def fake_result(model, condition, panels):
    import numpy as np
    a = math.radians(condition.alpha)
    qS = .5*condition.density*condition.speed**2*model.reference[0, 0]
    force = np.array([qS*(.2*math.cos(a)-.8*math.sin(a)), .05*qS,
                      qS*(.2*math.sin(a)+.8*math.cos(a))])
    c, b = model.reference[0, 1:3]
    moment = qS*np.array([-.03*b, -.07*c, -.09*b])
    return dict(converged=True, residual=1e-12, panels=panels, CL=.8, CD=.2, CY=.05,
        Cm=-.07, Cl=.03, Cn=.09, CDi=.12, CDi_near=.15, CDp=.05,
        CDbody=0., CDam=0., CDeng=0., CDrate=0., force=force, moment=moment,
        strips=[dict(force=force.tolist(), moment=moment.tolist(), position=model.reference[1].tolist())],
        trefftz={'available': True}, ground_plane=dict(flag=1, normal_body=[-math.sin(a), 0., math.cos(a)],
        normal_earth=[0., 0., 1.], offset=condition.position_earth[2],
        position_earth=list(condition.position_earth), attitude=list(condition.attitude),
        minimum_clearance=min(condition.position_earth[2]+.25*.254*math.sin(a),
                              condition.position_earth[2]-.75*.254*math.sin(a))))


def test_worker_forwards_ground_and_uses_raw_far_field_drag(jobs, monkeypatch):
    from openswing import aero
    job = next(j for j in jobs if j['settings']['alpha'] == 5. and j['height_label'] == 'inf')
    calls = []
    def solve(model, condition, *, panels, circulation_method):
        calls.append(condition)
        for key in sa12.CONDITION_FIELDS:
            assert getattr(condition, key) == job['settings'][key]
        assert panels == 100 and circulation_method == 'auto'
        return fake_result(model, condition, panels)
    monkeypatch.setattr(aero, 'solve_rigid', solve)
    result = sa12.run(ROOT, job)
    assert len(calls) == result['physical_calls'] == 1
    assert result['status'] == 'computed', result
    assert all(c['passed'] for c in result['numerical_checks'])
    assert result['result']['predicted']['CD'] == .2
    assert result['result']['predicted']['CDi'] == .12
    assert result['result']['CDi_near'] == .15
    assert not result['reference_match']


@pytest.mark.parametrize('fault', ['flag', 'normal_body', 'offset', 'attitude', 'clearance', 'wrong_clearance', 'Cm', 'CDi', 'convergence'])
def test_independent_ground_and_wrench_failures_cannot_pass(jobs, monkeypatch, fault):
    from openswing import aero
    job = next(j for j in jobs if j['settings']['alpha'] == 5.)
    def solve(model, condition, *, panels, **_):
        result = fake_result(model, condition, panels)
        if fault == 'flag': result['ground_plane']['flag'] = 0
        elif fault == 'normal_body': result['ground_plane']['normal_body'] = [0., 0., 1.]
        elif fault == 'offset': result['ground_plane']['offset'] += .01
        elif fault == 'attitude': result['ground_plane']['attitude'] = [0., 0., 0.]
        elif fault == 'clearance': result['ground_plane']['minimum_clearance'] = -.01
        elif fault == 'wrong_clearance': result['ground_plane']['minimum_clearance'] += .01
        elif fault == 'Cm': result['Cm'] += .01
        elif fault == 'CDi': result['CDi'] = None
        elif fault == 'convergence': result['converged'] = False
        return result
    monkeypatch.setattr(aero, 'solve_rigid', solve)
    result = sa12.run(ROOT, job)
    assert result['status'] == 'numerical_failure', result
    assert not result['numerical_pass'] and not result['reference_match']
    assert len(result['reference_checks']) == 4


@pytest.mark.parametrize('field', ['ground_effect', 'ground_normal', 'attitude', 'position_earth', 'mach', 'extra_unknown'])
def test_changed_or_extra_settings_fail_before_any_solve(jobs, monkeypatch, field):
    from openswing import aero
    job = copy.deepcopy(jobs[0])
    job['settings'][field] = 'changed'
    monkeypatch.setattr(aero, 'solve_rigid', lambda *a, **k:pytest.fail('Changed physical setup reached solver'))
    result = sa12.run(ROOT, job)
    assert result['status'] == 'error' and result['physical_calls'] == 0
    assert 'declared literal plan' in result['error']
    assert len(result['reference_checks']) == 4


def test_new_sidecar_requires_review_even_for_previously_validated_job(jobs, monkeypatch):
    job = jobs[0]
    sa12._validate_job(ROOT, job)
    original = Path.exists
    sidecar = (ROOT/job['model_path']).with_suffix('.set')
    monkeypatch.setattr(Path, 'exists', lambda path:True if path == sidecar else original(path))
    result = sa12.run(ROOT, job)
    assert result['physical_calls'] == 0 and 'sidecar' in result['error']


@pytest.mark.parametrize('replacement', ['-1\n0 0 1', '1\n1 0 0', '0\n0 0 1'])
def test_unreviewed_ground_driver_declaration_rejected(jobs, replacement):
    job = jobs[0]
    text = (ROOT/job['driver_path']).read_text().replace('1\n0 0 1', replacement)
    with pytest.raises(ValueError, match='ground flag/normal'):
        sa12.decode_driver(text, Path(job['table_path']).name)
