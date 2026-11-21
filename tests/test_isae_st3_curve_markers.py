from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from isae_st3_curve_markers import marker_centers


def test_square_uses_center_not_corner_or_outline():
    text='10 20 6 6 re f\nq 1 0 0 -1 0 0 cm\n10 -20 6 -6 re S Q'
    rows=marker_centers(text)
    assert [(r['x'],r['y'],r['kind']) for r in rows]==[(13,23,'square')]


def test_diamond_repeated_move_is_not_an_extra_sample():
    rows=marker_centers('6 20 m 10 25.32 l 14 20 l 10 14.68 l h\n6 20 m f')
    assert len(rows)==1 and rows[0]['x']==10 and rows[0]['y']==20


def test_circle_and_its_outline_do_not_count_twice():
    circle='14 20 m 14 18 12 16 10 16 c 8 16 6 18 6 20 c 6 22 8 24 10 24 c 12 24 14 22 14 20 c f'
    rows=marker_centers(circle+'\nq 1 0 0 -1 0 0 cm\n'+circle.replace(' f',' S Q'))
    assert len(rows)==1 and rows[0]['x']==10 and rows[0]['y']==20


def test_flat_line_keeps_all_marker_samples():
    text='q 1 0 0 -1 0 0 cm 0 -10 m 100 -10 l S Q\n'
    text+='\n'.join(f'{x-3} 7 6 6 re f' for x in (0,25,50,75,100))
    assert [r['x'] for r in marker_centers(text)]==[0,25,50,75,100]


def test_line_clipping_endpoints_are_not_markers():
    assert marker_centers('q 1 0 0 -1 0 0 cm -0.012 -10.023 m 0 -10 l 100 -20 l S Q')==[]
