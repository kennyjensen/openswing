"""Real mounted JSON boundary: observation must not change the solved result."""
import json
import pytest
from openswing.bridge import run_json


SOURCE = '''Name
Mounted progress verification
End
Unit
L 1 m
T 1 s
F 1 N
End
Constant
9.80665 1.225 340.294
End
Reference
2 1 2
0 0 0
End
Ground
1 0 0
End
Beam 1
Finite-stiffness lifting beam
t x y z chord Xax EIcc EInn GJ EA GKc GKn
0 0 0 0 .5 .25 10000 10000 10000 100000 100000 100000
2 0 2 0 .5 .25 10000 10000 10000 100000 100000 100000
t dCLda Cdf
0 6.283185307179586 .008
2 6.283185307179586 .008
End
'''


def request():
    return json.dumps(dict(action='solve', mode='mounted', source=SOURCE, panels=4,
        gravity=[0,0,0], condition=dict(speed=10,alpha=5,mach=0)))


def test_mounted_progress_reports_real_columns_and_loads_without_changing_any_output(tmp_path):
    plain = run_json(request())
    events = []
    observed = run_json(request(), progress=lambda *event:events.append(event))
    (tmp_path/'request.json').write_text(request())
    (tmp_path/'without-progress.json').write_text(plain)
    (tmp_path/'with-progress.json').write_text(observed)
    (tmp_path/'progress-events.json').write_text(json.dumps(events,indent=2))
    # Includes all numerical fields, metadata and residual evaluation count.
    assert observed == plain
    result = json.loads(observed)
    assert result['analysis'] == 'mounted_static'
    assert result['residual'] < 1e-8
    assert result['max_displacement'] > 0
    assert max(abs(x) for x in result['force_balance']) < 1e-7
    assert max(abs(x) for x in result['moment_balance']) < 1e-7
    assert events[0] == ('static_load',0.,1.)
    loads = [value for stage,value,total in events if stage == 'static_load']
    assert loads[-1] == 1.
    assert any(0 < value < 1 for value in loads)
    assert all(0 <= value <= 1 for value in loads)
    stages = [stage for stage, _, _ in events]
    startup = ('static_initial_airflow', 'static_circulation_residual',
               'static_circulation_loads', 'static_rank_assembly', 'static_tangent', 'static_rank')
    positions = [stages.index(stage) for stage in startup]
    assert positions == sorted(positions)
    tangents = []
    for stage,done,total in events:
        if stage == 'static_load':
            assert total == 1
        if stage != 'static_tangent':
            continue
        assert isinstance(done,int) and isinstance(total,int) and total > 0
        if done == 0:
            tangents.append([])
        assert tangents
        tangents[-1].append((done,total))
    assert len(tangents) >= 2  # Initial rank tangent plus loaded continuation.
    for tangent in tangents:
        assert tangent[0][0] == 0
        assert tangent[-1][0] == tangent[-1][1]
        assert len({total for _,total in tangent}) == 1
        assert all(a[0] < b[0] for a,b in zip(tangent,tangent[1:]))


def test_progress_callback_failure_propagates_before_any_solve_is_reported_complete():
    events = []
    def stop(stage, current, total):
        events.append((stage,current,total))
        if stage == 'static_tangent':
            raise RuntimeError('caller stopped observation')
    with pytest.raises(RuntimeError, match='caller stopped observation'):
        run_json(request(), progress=stop)
    assert events[0] == ('static_load',0.,1.)
    assert events[-1][0:2] == ('static_tangent',0)
    assert not any(stage == 'static_load' and value == 1 for stage,value,_ in events)


def test_cache_limit_reports_progress_warning_and_keeps_converged_result(monkeypatch):
    from openswing import frozen_influence
    monkeypatch.setattr(frozen_influence, '_CACHE_BYTES', 512)
    events = []
    result = json.loads(run_json(request(), progress=lambda *event: events.append(event)))
    assert result['converged']
    assert result['residual'] < 1e-8
    assert result['frozen_influence_cache_warning']['largest_uncached_map_bytes'] > 512
    assert [event for event in events if event[0] == 'static_cache_pressure'] == [
        ('static_cache_pressure', 512, 0)]
