"""Run deflection continuation with list/array-safe condition checks.

Preserve the first failed diagnostic and its pinned source. That run stopped
at the sensor helper's Python list check before any Newton matrix was built.
"""
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import probe_isae_ae2_deflection_branch as branch
from scripts.probe_isae_ae2_cold_trace import read, write, pin


def sensor_y(n, x):
    import numpy as np
    assert n.operating.count == 0 and np.max(np.abs(n.condition.attitude)) == 0
    assert np.max(np.abs(n.condition.position_earth)) == 0
    row, = n.model.records['sensor']
    node = n.node(*row[1:3])
    beam = next(b for b in n.model.beams if b.index == int(row[1]))
    r, q, *_ = n.unpack(x)
    return float((r[node] + q[node] @ (row[3:6]-beam.position(row[2])))[1])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare', 'launch'])
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--seed', type=Path)
    parser.add_argument('--target', type=float)
    parser.add_argument('--phase', choices=['solve', 'tangent', 'verify'])
    args = parser.parse_args()
    out = args.output.resolve()
    branch.sensor_y = sensor_y
    if args.action == 'prepare':
        branch.prepare(out, args.seed.resolve(), args.target)
        plan = read(out / 'plan.json')
        failed = ROOT / 'artifacts/isae/ae2-deflection-0202-20261110'
        plan['pins'] += [pin(p) for p in [Path(__file__), failed / 'plan.json',
            failed / 'solve/terminal.json', failed / 'solve/stderr.log', failed / 'solve/sources-verified.json']]
        plan['qualifications'].append(__doc__)
        write(out / 'plan.json', plan)
    else:
        branch.base.solve = branch.solve
        branch.base.tangent = branch.tangent
        branch.base.verify = branch.verify
        branch.base.launch(out, args.phase)
