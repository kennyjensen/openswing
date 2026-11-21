"""Partition the exact response difference by beam and global balance axis."""
import argparse
from pathlib import Path

from check_daedalus_load_sensitivity import ROOT, read
from daedalus_bounded_job import run
import check_daedalus_response_difference as base

SEEDS = [ROOT/'artifacts/daedalus-regular-mesh-20261114/trim-1/state.json',
         ROOT/'artifacts/daedalus-pitch-balanced-base-20261114/equilibrium-0/state.json']
COARSE_GROUPS = base.row_groups


def beam_groups(layout):
    from openswing.asw import parse_asw
    packets = [read(p) for p in SEEDS]
    assert packets[0]['identity']['stations'] == packets[1]['identity']['stations']
    names = {b.index: b.name for b in parse_asw((ROOT/'examples/dae.asw').read_text(),
                                            beam_interpolation='drela-segspl-v1').beams}
    ne, nn = layout['elements'], layout['nodes']
    rows = [r for r in COARSE_GROUPS(layout) if r[0] not in [
        'beam compatibility', 'nodal force balance', 'nodal moment balance',
        'circulation', 'aircraft force balance', 'aircraft moment balance']]
    cursor = 0
    for key, (stations, nodes) in packets[0]['identity']['stations'].items():
        assert nodes == list(range(nodes[0], nodes[-1]+1))
        name = f'beam {key} {names[int(key)]}'
        count = len(stations)-1
        rows.append((name+' compatibility', 6*cursor, 6*(cursor+count)))
        rows.append((name+' force balance', 6*ne+3*nodes[0], 6*ne+3*(nodes[-1]+1)))
        rows.append((name+' moment balance', 6*ne+3*nn+3*nodes[0], 6*ne+3*nn+3*(nodes[-1]+1)))
        cursor += count
    assert cursor == ne
    start = layout['circulation']['start']
    for beam in layout['circulation']['discretization']['beams']:
        assert beam['representation'] == 'pointwise'
        first = start+beam['coefficient_start']
        rows.append((f"beam {beam['beam']} {names[beam['beam']]} circulation", first, first+beam['unknowns']))
    start = layout['operating']['start']
    rows.extend((f'aircraft {kind} balance {axis}', start+3*k+i, start+3*k+i+1)
                for k, kind in enumerate(['force', 'moment']) for i, axis in enumerate('xyz'))
    return sorted(rows, key=lambda r: r[1])


def execute(folder, arguments):
    base.row_groups = beam_groups
    return base.execute(folder, arguments)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tag', required=True)
    parser.add_argument('--frequency', required=True, type=float)
    args = vars(parser.parse_args())
    inputs = list((ROOT/'openswing').glob('*.py'))+[ROOT/'docs/validation/ISAE_STATUS.md',
        ROOT/'examples/dae.asw', ROOT/'scripts/check_daedalus_response_difference.py',
        ROOT/'docs/validation/aswing-authoritative-sources.json', *SEEDS,
        ROOT/'reference/aswing-authoritative-20261108/drela-aswing-unsteady.pdf']
    for case, report in zip(base.CASES, base.REPORTS):
        inputs.extend(case/'assembled'/name for name in ['A.npz', 'M.npz', 'maps.npz', 'plan.json', 'result.json', 'terminal.json'])
        inputs.extend([case/'mass/layout.json', report/'source-pins.json'])
    run(base.STUDY, args['tag'], inputs, execute, args, __file__)
