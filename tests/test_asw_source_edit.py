"""Comment placement and exact model values across local property edits."""
from pathlib import Path
from difflib import SequenceMatcher
import json
import re

import numpy as np
import pytest

from openswing.asw import AswError, parse_asw
from openswing.asw_edit import edit_distribution


SPRING = Path('examples/instrumented-oscillator.asw').read_text()
TABLE = 't y EA tdeps\n0 0 1000 .02\n2 2 1000 .02'
ANNOTATED = ('  t y EA tdeps  ! beam properties\n'
             '# root station\n'
             '  0 0 1000 .02  ! root stiffness\n'
             '\n% tip station\n'
             '  2 2 1000 .02  # tip stiffness')


def comments(source, *, positions=False):
    result = []
    for i, line in enumerate(source.splitlines()):
        match = re.search(r'[!#%].*', line)
        if match:
            result.append((i, match.group()) if positions else match.group())
    return result


def inserted_line(before, after):
    old, new = before.splitlines(keepends=True), after.splitlines(keepends=True)
    changes = [op for op in SequenceMatcher(a=old, b=new, autojunk=False).get_opcodes() if op[0] != 'equal']
    assert len(changes) == 1
    kind, a, b, c, d = changes[0]
    assert kind == 'insert' and a == b and d-c == 1
    return new[c]


@pytest.mark.parametrize('newline', ['\n', '\r\n'])
@pytest.mark.parametrize('descending', [False, True])
@pytest.mark.parametrize('policy', ['natural-v1', 'drela-segspl-v1'])
def test_shared_station_insertion_adds_one_line_and_interpolates_every_column(newline, descending, policy):
    rows = ['  0 0 2 .1 1000 .02 ! root', '  1 .3 1.5 .2 1200 .04 # middle', '  2 2 1 .1 1000 .02 % tip']
    if descending:
        rows.reverse()
    table = 't y chord Ccg EA tdeps ! geometry and properties\n'+ '\n'.join(rows)
    source = SPRING.replace(TABLE, table).replace('\n', newline).rstrip('\r\n')
    model = parse_asw(source, beam_interpolation=policy)
    edited = edit_distribution(model, 1, 'chord', points=[[0, 2], [.5, 1.75], [1, 1.5], [2, 1]])
    row = inserted_line(source, edited.dumps())
    assert row.endswith(newline) and not re.search(r'[!#%]', row)
    assert comments(edited.dumps()) == comments(source)
    assert ('! root'+newline+row if not descending else row+'  0 0 2 .1 1000 .02 ! root') in edited.dumps()
    for name, original in model.beams[0].distributions.items():
        result = edited.beams[0].distributions[name]
        np.testing.assert_array_equal(result.t, [0, .5, 1, 2])
        np.testing.assert_array_equal(np.delete(result.values, 1), original.values)
        value = 1.75 if name == 'chord' else original.evaluate(.5)
        assert result.values[1] == value
    assert model.dumps() == source


@pytest.mark.parametrize('station', [-1, 1, 3])
def test_shared_insertion_preserves_changing_scaling_and_station_annotations(station):
    table = ('t y EA tdeps ! shared\n'
             '* 2 3 100 4 ! multipliers\n'
             '+ 0 1 5 0 % offsets\n'
             '# root station\n'
             '0,0,10,.02 # root\n'
             '* 2 3 ! short scaling resets unprovided columns\n'
             '+ 0 1 # short offsets reset unprovided columns\n'
             '! tip station\n'
             '1,2,2000,.02 ! tip')
    source = SPRING.replace(TABLE, table)
    model = parse_asw(source)
    d = model.beams[0].distributions['EA']
    points = sorted([[*pair] for pair in zip(d.t, d.values)]+[[station, float(d.evaluate(station))]])
    edited = edit_distribution(model, 1, 'EA', points=points)
    row = inserted_line(source, edited.dumps())
    assert comments(edited.dumps()) == comments(source)
    assert '* 2 3 100 4 ! multipliers' in edited.dumps()
    if station == -1:
        assert row+'# root station\n0,0,10,.02' in edited.dumps()
    elif station == 1:
        assert '0,0,10,.02 # root\n'+row+'* 2 3 ! short' in edited.dumps()
    else:
        assert '1,2,2000,.02 ! tip\n'+row in edited.dumps()
    for name, original in model.beams[0].distributions.items():
        result = edited.beams[0].distributions[name]
        np.testing.assert_array_equal(result.t, sorted([0, 2, station]))
        i = int(np.searchsorted(result.t, station))
        np.testing.assert_array_equal(np.delete(result.values, i), original.values)
        assert result.values[i] == pytest.approx(original.evaluate(station), rel=2e-15, abs=0)


def test_shared_insertion_negative_station_scale_and_zero_value_scale():
    table = ('t y EA tdeps\n* -2 1 100 0\n+ 0 0 5 .02\n'
             '-1 2 10 999 ! tip\n0 0 10 999 ! root')
    source = SPRING.replace(TABLE, table)
    edited = edit_distribution(parse_asw(source), 1, 'EA', points=[[0, 1005], [1, 1205], [2, 1005]])
    row = inserted_line(source, edited.dumps())
    assert '-1 2 10 999 ! tip\n'+row+'0 0 10 999 ! root' in edited.dumps()
    assert row.split()[:3] == ['-0.5', '1', '12']
    for name, values in dict(y=[0, 1, 2], EA=[1005, 1205, 1005], tdeps=[.02, .02, .02]).items():
        np.testing.assert_array_equal(edited.beams[0].distributions[name].values, values)


def test_drela_chord_insertion_is_a_single_shared_row_through_editor_bridge():
    from openswing.bridge import dispatch
    source = Path('examples/dae.asw').read_text()
    model = parse_asw(source)
    beam = next(b for b in model.beams if b.lifting)
    chord = beam.distributions['chord']
    points = np.column_stack((chord.t, chord.values))
    station, value = (points[0]+points[1])/2
    points = np.insert(points, 1, [station, value], axis=0)
    response = dispatch(dict(action='edit_distribution', source=source, beam=beam.index,
                             name='chord', edit=dict(points=points.tolist())))
    saved = response['source']
    inserted_line(source, saved)
    np.testing.assert_array_equal(response['distribution']['points'], points)
    assert '   t     chord     y      Ccg\n' in saved
    assert comments(saved) == comments(source)
    for name in ['y', 'Ccg']:
        report = dispatch(dict(action='distribution', source=saved, beam=beam.index, name=name))
        np.testing.assert_array_equal(np.asarray(report['points'])[:, 0], points[:, 0])
        assert report['points'][1][1] == beam.distributions[name].evaluate(station)
    restored = dispatch(dict(action='edit_distribution', source=saved, beam=beam.index,
                             name='chord', edit=dict(points=np.delete(points, 1, axis=0).tolist(), delete_station=1)))
    assert restored['source'] == source
    # Independent property tables remain independent; subsequent value edits
    # also retain the shared table and do not move any notes.
    out = parse_asw(saved)
    for name, d in beam.distributions.items():
        if name not in ('chord', 'y', 'Ccg'):
            np.testing.assert_array_equal(out.beams[0].distributions[name].t, d.t)
            np.testing.assert_array_equal(out.beams[0].distributions[name].values, d.values)
    points[1, 1] *= 1.01
    changed = edit_distribution(out, beam.index, 'chord', points=points)
    assert '   t     chord     y      Ccg\n' in changed.dumps()
    assert comments(changed.dumps(), positions=True) == comments(saved, positions=True)
    assert model.dumps() == source


@pytest.mark.parametrize('index', [0, 1, 2])
@pytest.mark.parametrize('descending', [False, True])
@pytest.mark.parametrize('policy', ['natural-v1', 'drela-segspl-v1'])
def test_shared_station_deletion_preserves_remaining_rows_comments_and_scaling(index, descending, policy):
    rows = ['  2 0 .75 .1', '  1 1 .5 .2 ! middle station', '  0 2 .25 .3']
    removed = rows[index]
    if descending:
        rows.reverse()
    table = ('t y chord Ccg\n* -2 3 2 4\n+ 4 1 .5 .1\n'+ '\n'.join(rows)+
             '\nt EA tdeps\n0 1000 .02\n2 1000 .02')
    newline = '\r\n' if descending else '\n'
    # Keep both sensors on the middle station so either endpoint may be removed.
    source = SPRING.replace(TABLE, table).replace('1 1 0 0 0 .2', '1 1 2 0 0 .2').replace('\n', newline).rstrip('\r\n')
    model = parse_asw(source, beam_interpolation=policy)
    d = model.beams[0].distributions['chord']
    points = np.delete(np.column_stack((d.t, d.values)), index, axis=0)
    edited = edit_distribution(model, 1, 'chord', points=points, delete_station=index)
    note = ' '*removed.index('!')+'! middle station'+newline if '!' in removed else ''
    assert edited.dumps() == source.replace(removed+newline, note)
    assert comments(edited.dumps()) == comments(source)
    for name, original in model.beams[0].distributions.items():
        result = edited.beams[0].distributions[name]
        shared = name in ('y', 'chord', 'Ccg')
        np.testing.assert_array_equal(result.t, np.delete(original.t, index) if shared else original.t)
        np.testing.assert_array_equal(result.values, np.delete(original.values, index) if shared else original.values)
    # The old points alone also identify deletion when the station is unique.
    assert edit_distribution(model, 1, 'chord', points=points).dumps() == edited.dumps()
    assert model.dumps() == source


@pytest.mark.parametrize('index', [1, 2])
@pytest.mark.parametrize('descending', [False, True])
def test_shared_station_deletion_distinguishes_identical_chord_rows(index, descending):
    rows = ['0 0 1 0', '1 1 1 .1', '1 1 1 .2', '2 2 1 .3']
    removed = rows[index]
    if descending:
        rows.reverse()
    table = 't y chord Ccg\n'+'\n'.join(rows)+'\nt EA tdeps\n0 1000 .02\n2 1000 .02'
    source = SPRING.replace(TABLE, table)
    model = parse_asw(source)
    points = [[0, 1], [1, 1], [2, 1]]
    edited = edit_distribution(model, 1, 'chord', points=points, delete_station=index)
    assert edited.dumps() == source.replace(removed+'\n', '')
    np.testing.assert_array_equal(edited.beams[0].distributions['Ccg'].values, [0, .2 if index == 1 else .1, .3])
    with pytest.raises(AswError, match='which doubled station'):
        edit_distribution(model, 1, 'chord', points=points)
    assert model.dumps() == source


def test_shared_station_deletion_rejects_invalid_rows_and_invalid_companion_grid():
    source = SPRING.replace(TABLE, 't y EA tdeps\n0 0 0 .02\n1 1 0 .02\n2 2 0 .02')
    model = parse_asw(source)
    for index in [-1, 3, True, .5]:
        with pytest.raises(AswError):
            edit_distribution(model, 1, 'EA', points=[[0, 0], [2, 0]], delete_station=index)
    with pytest.raises(AswError, match='other rows unchanged'):
        edit_distribution(model, 1, 'EA', points=[[0, 0], [2, 100]], delete_station=1)
    with pytest.raises(AswError, match='exactly the selected row'):
        edit_distribution(model, 1, 'EA', delete_station=1)
    two = edit_distribution(model, 1, 'EA', points=[[0, 0], [2, 0]], delete_station=1)
    # A lone zero EA value is legal, but y/tdeps cannot have just one knot.
    with pytest.raises(AswError, match='at least two stations'):
        edit_distribution(two, 1, 'EA', points=[[0, 0]], delete_station=1)
    assert model.dumps() == source
    assert len(two.beams[0].distributions['y'].t) == 2


@pytest.mark.parametrize('index', range(8))
def test_actual_daedalus_plus_requests_update_source_and_pass_mesh_inspection(index):
    from openswing.bridge import dispatch
    requests = json.loads(Path('tests/fixtures/dae-station-insert-requests.json').read_text())['requests']
    source = Path('examples/dae.asw').read_text()
    numerics = dict(beam_interpolation='drela-segspl-v1', structural_operator='drela-moving-airflow-v1')
    request = dict(requests[index], source=source, numerics=numerics)
    result = dispatch(request)
    inserted_line(source, result['source'])
    np.testing.assert_array_equal(result['distribution']['points'], request['edit']['points'])
    model = dispatch(dict(action='inspect', source=result['source'], numerics=numerics,
                          panels=json.loads(Path('web/daedalus-mesh.json').read_text())))
    assert model['name'] == 'Daedalus HPA'
    original = parse_asw(source).beams[0].distributions['chord']
    points = np.asarray(request['edit']['points'])
    added = int(np.flatnonzero(~np.isin(points[:, 0], original.t))[0])
    restored = dispatch(dict(action='edit_distribution', source=result['source'], beam=1,
                             name='chord', numerics=numerics,
                             edit=dict(points=np.delete(points, added, axis=0).tolist(), delete_station=added)))
    assert restored['source'] == source


@pytest.mark.parametrize('newline', ['\n', '\r\n'])
@pytest.mark.parametrize('policy', ['natural-v1', 'drela-segspl-v1'])
def test_value_edit_changes_only_the_selected_numeric_token(newline, policy):
    source = SPRING.replace(TABLE, ANNOTATED).replace('\n', newline).rstrip('\r\n')
    model = parse_asw(source, beam_interpolation=policy)
    edited = edit_distribution(model, 1, 'EA', points=[[0, 1000], [2, 1250]])
    assert edited.dumps() == source.replace('2 2 1000 .02', '2 2 1250 .02')
    assert model.dumps() == source
    again = edit_distribution(edited, 1, 'EA', points=[[0, 1100], [2, 1250]])
    assert again.dumps() == edited.dumps().replace('0 0 1000 .02', '0 0 1100 .02')
    assert again.beam_interpolation == policy
    assert comments(again.dumps(), positions=True) == comments(source, positions=True)


def test_scaled_shared_table_keeps_notes_and_other_columns_exact():
    table = (' t y EA tdeps ! columns\n'
             '* 2 3 100 4 ! multipliers\n'
             '+ 0 1 5 0 % offsets\n'
             '0,0,10,.02 # root\n'
             '* 2 3 ! short scaling resets unprovided columns\n'
             '+ 0 1 # short offsets reset unprovided columns\n'
             '1,2,2000,.02 ! tip')
    source = SPRING.replace(TABLE, table)
    model = parse_asw(source)
    edited = edit_distribution(model, 1, 'EA', multiplier=2)
    np.testing.assert_array_equal(edited.beams[0].distributions['EA'].values, [2010, 4000])
    for name in ['y', 'tdeps']:
        np.testing.assert_array_equal(edited.beams[0].distributions[name].t, model.beams[0].distributions[name].t)
        np.testing.assert_array_equal(edited.beams[0].distributions[name].values, model.beams[0].distributions[name].values)
    assert comments(edited.dumps(), positions=True) == comments(source, positions=True)
    assert '0,0,2010,.02 # root' in edited.dumps()
    assert '* 2 3 ! short scaling resets unprovided columns' in edited.dumps()


def test_new_station_grid_splits_only_edited_column_next_to_original_table():
    source = SPRING.replace(TABLE, ANNOTATED)
    model = parse_asw(source)
    edited = edit_distribution(model, 1, 'EA', points=[[0, 1000], [1, 1500], [2, 2000]])
    saved = edited.dumps()
    assert saved[:saved.index('Beam 1')] == source[:source.index('Beam 1')]
    assert saved[saved.index('! Default body-aligned'):] == source[source.index('! Default body-aligned'):]
    assert comments(saved) == comments(source)
    assert saved.index('# root station') < saved.index('# tip stiffness') < saved.index('t EA\n') < saved.index('! Default body-aligned')
    for name in ['y', 'tdeps']:
        before, after = model.beams[0].distributions[name], edited.beams[0].distributions[name]
        np.testing.assert_array_equal(before.t, after.t)
        np.testing.assert_array_equal(before.values, after.values)
    np.testing.assert_array_equal(edited.beams[0].distributions['EA'].t, [0, 1, 2])
    assert 'Comments retained' not in saved


def test_single_property_insertion_and_deletion_keep_annotations_with_rows():
    table = ('t y tdeps\n0 0 .02\n2 2 .02\n'
             't EA ! axial stiffness\n'
             '* 2 100 ! scaled values\n'
             '# root station\n'
             '0 10 ! root\n'
             '# middle station\n'
             '.5 12.5 ! middle\n'
             '1 10 ! tip')
    source = SPRING.replace(TABLE, table)
    inserted = edit_distribution(parse_asw(source), 1, 'EA', points=[[0, 1000], [.5, 1100], [1, 1250], [2, 1000]])
    saved = inserted.dumps()
    assert '0 1000 ! root\n0.5 1100\n# middle station\n' in saved
    assert comments(saved) == comments(source)
    deleted = edit_distribution(inserted, 1, 'EA', points=[[0, 1000], [.5, 1100], [2, 1000]])
    assert re.search(r'# middle station\n[ \t]*! middle\n', deleted.dumps())
    before_note = next(line for line in saved.splitlines() if line.endswith('! middle'))
    after_note = next(line for line in deleted.dumps().splitlines() if line.endswith('! middle'))
    assert after_note.index('!') == before_note.index('!')
    assert comments(deleted.dumps()) == comments(source)
    np.testing.assert_array_equal(deleted.beams[0].distributions['EA'].values, [1000, 1100, 1000])
    prepended = edit_distribution(deleted, 1, 'EA', points=[[-1, 900], [0, 1000], [.5, 1100], [2, 1000]])
    assert '-1 900\n# root station\n0 1000 ! root' in prepended.dumps()
    assert comments(prepended.dumps()) == comments(source)


def test_descending_table_retains_its_order_and_inline_notes():
    source = SPRING.replace(TABLE, 't y tdeps\n0 0 .02\n2 2 .02\nt EA\n2 1000 ! tip\n0 1000 ! root')
    changed = edit_distribution(parse_asw(source), 1, 'EA', points=[[0, 900], [1, 950], [2, 1000]])
    assert '2 1000 ! tip\n1 950\n0  900 ! root' in changed.dumps()
    assert comments(changed.dumps()) == comments(source)


def test_adding_and_removing_tables_never_collect_or_discard_comments():
    source = SPRING.replace(TABLE, ANNOTATED)
    model = parse_asw(source)
    added = edit_distribution(model, 1, 'dCLdF12', points=[[0, .2], [2, .3]])
    assert comments(added.dumps()) == comments(source)
    removed = edit_distribution(added, 1, 'EA', remove=True)
    assert comments(removed.dumps()) == comments(source)
    # Comments on a single-property header and its deleted data stay in place.
    source2 = source.replace(ANNOTATED, 't y tdeps\n0 0 .02\n2 2 .02\nt EA ! stiffness\n0 1000 ! root\n2 1000 ! tip')
    removed2 = edit_distribution(parse_asw(source2), 1, 'EA', remove=True)
    assert re.search(r'! stiffness\n[ \t]*! root\n[ \t]*! tip\nEnd', removed2.dumps())
    assert comments(removed2.dumps()) == comments(source2)


@pytest.mark.parametrize('example', ['dae', 'usa', 'fw'])
def test_drela_example_value_edits_keep_every_comment_on_its_line(example):
    from openswing.bridge import dispatch
    source = Path('examples', example+'.asw').read_text()
    model = parse_asw(source)
    beam = next(b for b in model.beams if b.lifting)
    d = beam.distributions['chord']
    points = np.column_stack((d.t, d.values))
    points[0, 1] *= 1.01
    result = dispatch(dict(action='edit_distribution', source=source, beam=beam.index,
                           name='chord', edit=dict(points=points.tolist())))
    saved = result['source']
    assert comments(saved, positions=True) == comments(source, positions=True)
    assert 'Comments retained' not in saved
    np.testing.assert_array_equal(result['distribution']['points'], points)
    assert edit_distribution(parse_asw(saved), beam.index, 'chord', points=points).dumps() == saved
