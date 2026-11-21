"""Full-window gates must expose transient and local deformation errors."""
import copy
import importlib.util
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
spec = importlib.util.spec_from_file_location('ffwt4_fields', ROOT/'scripts/assess-isae-ffwt4-field-refinement.py')
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def history(divisor, stations, mutate=None, baseline=.7):
    for tick in range(199*divisor+1):
        time = float(tick*audit.DT/divisor)
        frame = dict(tick=tick, time=time, moment=baseline+.4*time/2.9651,
                     displacement=[[0., 0., .003*(1+time)*s*s] for s in stations],
                     rotation_vector=[[.01*(1+time)*s, 0., 0.] for s in stations])
        if mutate:
            mutate(frame)
        yield frame


def compare(kind='temporal', coarse_mutate=None, fine_mutate=None, baseline=.7):
    coarse_stations = [-.5, 0., .5]
    fine_stations = coarse_stations if kind == 'temporal' else [-.5, -.25, 0., .25, .5]
    divisors = [2, 4] if kind == 'temporal' else [2, 2]
    return audit.compare_frames(history(divisors[0], coarse_stations, coarse_mutate, baseline),
        history(divisors[1], fine_stations, fine_mutate, baseline), kind=kind,
        nominals=[32, 32] if kind == 'temporal' else [16, 32], divisors=divisors,
        coarse_stations=coarse_stations, fine_stations=fine_stations)


@pytest.mark.parametrize('kind', ['spatial', 'temporal'])
def test_exact_continuous_fields_match_at_all_shared_coordinates(kind):
    result = compare(kind)
    assert result['passed'] == result['required'] == 4
    assert result['common_times'] == 399 and result['common_nodes'] == 3
    assert all(g['relative_limit'] == .001 for g in result['gates'].values())


def test_large_steady_moment_cannot_hide_increment_error_between_native_ticks():
    def perturb(frame):
        if frame['tick'] == 3:
            frame['moment'] += .0005
    gates = compare(coarse_mutate=perturb, baseline=1000.)['gates']
    assert gates['root_moment']['passed']
    assert not gates['gust_increment']['passed']
    assert gates['gust_increment']['worst_coarser_tick'] == 3
    assert gates['gust_increment']['fine_scale'] == pytest.approx(.4)
    assert gates['gust_increment']['maximum_percent_of_scale'] == pytest.approx(.125)


@pytest.mark.parametrize('field,delta', [('displacement', 1e-5), ('rotation_vector', 1e-4)])
def test_local_vector_error_is_not_hidden_by_span_or_the_root_sensor(field, delta):
    def perturb(frame):
        if frame['tick'] == 3:
            frame[field][1][1] += delta
    gates = compare('spatial', coarse_mutate=perturb)['gates']
    assert gates['root_moment']['passed'] and gates['gust_increment']['passed']
    assert not gates[field]['passed']
    assert gates[field]['worst_station'] == 0.
    assert gates[field]['maximum_absolute_difference'] == pytest.approx(delta)
    if field == 'displacement':
        assert gates[field]['fine_scale'] == pytest.approx(.003*(1+2.9651)*.25)


@pytest.mark.parametrize('fault', ['nan', 'overflow', 'large_rotation', 'missing_node', 'shifted_time', 'repeated_tick'])
def test_invalid_fine_only_time_cannot_be_skipped(fault):
    def perturb(frame):
        if frame['tick'] != 1:
            return
        if fault == 'nan':
            frame['displacement'][1][2] = float('nan')
        elif fault == 'overflow':
            frame['displacement'][1][2] = 1e300
        elif fault == 'large_rotation':
            frame['rotation_vector'][1][2] = .2
        elif fault == 'missing_node':
            frame['displacement'].pop()
        elif fault == 'shifted_time':
            frame['time'] += 1e-4
        else:
            frame['tick'] = 0
    with pytest.raises(ValueError):
        compare(fine_mutate=perturb)


@pytest.mark.parametrize('side', ['coarser', 'finer'])
def test_incomplete_tail_cannot_pass_full_window(side):
    stations = [-.5, 0., .5]
    coarser, finer = list(history(2, stations)), list(history(4, stations))
    (coarser if side == 'coarser' else finer).pop()
    with pytest.raises(ValueError, match='Incomplete'):
        audit.compare_frames(coarser, finer, kind='temporal', nominals=[32, 32], divisors=[2, 4],
                             coarse_stations=stations, fine_stations=stations)


@pytest.mark.parametrize('kind,nominals,divisors,c,f', [
    ('spatial', [16, 64], [2, 2], [-.5, 0., .5], [-.5, 0., .5]),
    ('spatial', [16, 32], [2, 4], [-.5, 0., .5], [-.5, 0., .5]),
    ('spatial', [16, 32], [2, 2], [-.5, 0., .5], [-.5, .1, .5]),
    ('temporal', [16, 32], [2, 4], [-.5, 0., .5], [-.5, 0., .5]),
    ('temporal', [16, 16], [2, 8], [-.5, 0., .5], [-.5, 0., .5]),
    ('temporal', [16, 16], [2, 4], [-.5, 0., .5], [-.5, 0., 0., .5]),
])
def test_mixed_changes_skipped_grids_and_unmatched_stations_are_rejected(kind, nominals, divisors, c, f):
    with pytest.raises(ValueError):
        audit.pairing(kind, nominals, divisors, c, f)


def test_no_transient_has_no_relative_increment_accuracy_verdict():
    def constant(frame):
        frame['moment'] = .7
    with pytest.raises(ValueError, match='Zero scale'):
        compare(coarse_mutate=constant, fine_mutate=constant)


def test_partial_assessment_is_rejected_before_loading_any_files():
    with pytest.raises(ValueError, match='Complete histories'):
        audit.history_contract(dict(status='HISTORY_ASSESSED', complete=False))


def extraction_fixture(tmp_path, changed_boundary=False):
    masses = [.0069, .017, .0409, .1122, .155, .1978, .2122, .255, .2978, .3145, .328, .3415, .3521, .4243, .4965]
    source = ('Weight\n* 1 1 1 1 1 1 1 1 1 1 1\n' + '\n'.join(
        f'1 {sign*t} 0 0 0 1 0 0 0 0 0 0' for sign in (-1, 1) for t in masses for _ in range(2))+'\nEnd\n')
    stations = audit.spatial.expected_stations(source, 16)
    nodes = [[0., t, 0.] for t in stations]
    identity = dict(stations={'1': [stations, list(range(len(nodes)))]}, nodes=nodes,
                    elements=[[i, i+1] for i in range(len(nodes)-1)])
    frames = list(history(2, stations))[:3]
    dt = float(audit.DT/2)
    snapshots = []
    for frame in frames:
        tick = frame['tick']
        method = dict(scheme='drela-euler-bdf-v1', effective_order=1 if tick == 1 else 2,
                      coefficients=[1/dt, -1/dt, 0.] if tick == 1 else [1.5/dt, -2/dt, .5/dt])
        network = dict(positions=[[p[j]+v[j] for j in range(3)] for p, v in zip(nodes, frame['displacement'])],
                       rotations=frame['rotation_vector'])
        snapshots.append(dict(time=frame['time'], converged=True, residual=1e-12,
            sensors=[dict(index=1, load_trace='left', moment_local=[frame['moment'], 0., 0.])],
            restart=dict(state=dict(network=network), accepted_method=method)))
    def save(name, value):
        path = tmp_path/name
        path.write_text(json.dumps(value))
        return dict(path=str(path))
    initial = dict(equilibrium_state=dict(identity=identity, **snapshots[0]['restart']['state']['network']),
                   sensors=snapshots[0]['sensors'])
    plans = [dict(start_step=0, end_step=1, initial_request=save('request.json', dict(source=source)),
                  initial_result=save('initial.json', initial)), dict(start_step=1, end_step=2)]
    reports = []
    for i in range(2):
        pair = copy.deepcopy(snapshots[i:i+2])
        if i == 1 and changed_boundary:
            pair[0]['restart']['state']['network']['positions'][1][2] += 1e-5
        raw = dict(restart_context=dict(identity=identity), snapshots=pair, accepted_steps=1,
                   rejected_steps=0, converged=True)
        reports.append(dict(result=save(f'segment{i}.json', raw)))
    data = dict(nominal=16, divisor=2, required_steps=2,
                samples={str(f['tick']): dict(time=f['time'], moment=f['moment']) for f in frames})
    return data, plans, reports


def test_extraction_removes_jig_and_deduplicates_only_identical_continuation_fields(tmp_path):
    data, plans, reports = extraction_fixture(tmp_path)
    result = audit.extract(data, plans, reports, tmp_path/'fields.jsonl')
    frames = list(audit.frames(result['file']['path']))
    assert len(frames) == result['frames'] == 3
    assert result['continuation_boundaries'] == 1
    assert frames[0]['displacement'][0] == pytest.approx([0., 0., .00075])


def test_changed_continuation_field_cannot_hide_behind_matching_sensor(tmp_path):
    data, plans, reports = extraction_fixture(tmp_path, changed_boundary=True)
    with pytest.raises(ValueError, match='shared nodal state'):
        audit.extract(data, plans, reports, tmp_path/'fields.jsonl')
