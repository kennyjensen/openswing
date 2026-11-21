"""Bounded UA-1 linear-solve diagnostics; never changes production modules.

The default run records the actual structured Newton solves. Experimental
refinement/dense modes use the same matrices and physical residual, and are
explicitly diagnostic rather than a passing physical validation case.
"""
import argparse
import gzip
import json
from pathlib import Path
import sys
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from isae_ua1_stall_browser import digest, pins, read, write
from isae_ua_artifacts import write_trajectory

BASE = ROOT/'artifacts/isae/ua-time-conditioning-20261102'
PREVIOUS = ROOT/'artifacts/isae/ua-time-position-20261102'


def run(mode):
    from scipy.linalg import solve
    from openswing.bridge import dispatch
    import openswing.structured_time as structured
    folder = BASE/mode
    folder.mkdir(parents=True, exist_ok=False)
    request_path = PREVIOUS/'requested/request.json'
    request = read(request_path)
    inputs = [request_path, PREVIOUS/'requested/trajectory.json.gz',
              PREVIOUS/'browser/requested.json.gz']
    write(folder/'plan.json', dict(mode=mode, diagnostic_only=True,
        source_sha256=pins([Path(__file__).resolve(), *sorted((ROOT/'openswing').glob('*.py'))]),
        input_sha256=pins(inputs), equations_changed=False,
        physical_tolerance=request['time']['tolerance'],
        physical_steps=8, runtime_agreement_limit=2e-8))
    original = structured.Factorization.solve
    rows = []
    arrays = {}

    def measured(self, rhs):
        result = original(self, rhs)
        perm = self.permutation
        matrix = self.matrix.toarray()
        b = rhs[perm]
        x = result[perm]
        initial = x.copy()
        if mode in ('refined', 'refined-double'):
            # Fixed three corrections to the identical linearized equations.
            # This diagnostic uses extended accumulation only to determine
            # whether roundoff in the linear solve can explain the forces.
            for _ in range(3):
                dtype = np.longdouble if mode == 'refined' else float
                defect = np.asarray(b.astype(dtype)-matrix.astype(dtype)@x.astype(dtype), dtype=float)
                physical = np.empty_like(defect); physical[perm] = defect
                x += original(self, physical)[perm]
            result[perm] = x
        elif mode == 'dense':
            x = solve(matrix, b)
            result[perm] = x
        elif mode == 'equilibrated':
            scaled = matrix.copy()
            right = b.copy()
            column_scale = np.ones(len(b))
            for _ in range(6):
                row = np.maximum(np.max(abs(scaled), axis=1), np.finfo(float).tiny)
                scaled /= row[:, None]; right /= row
                column = np.maximum(np.max(abs(scaled), axis=0), np.finfo(float).tiny)
                scaled /= column[None, :]; column_scale /= column
            x = column_scale*solve(scaled, right)
            result[perm] = x
        defect = np.asarray(matrix.astype(np.longdouble)@x.astype(np.longdouble)-b.astype(np.longdouble), dtype=float)
        denominator = abs(matrix)@abs(x)+abs(b)
        backward = np.divide(abs(defect), denominator, out=np.zeros_like(b), where=denominator!=0)
        index = len(rows)
        arrays.update({f'matrix_{index}':matrix, f'rhs_{index}':b, f'solution_{index}':x,
                       f'permutation_{index}':perm})
        rows.append(dict(index=index, size=len(rhs), max_rhs=float(max(abs(b))),
            max_correction=float(max(abs(x))), changed_correction=float(max(abs(x-initial))),
            max_linear_residual=float(max(abs(defect))),
            componentwise_backward_error=float(max(backward))))
        return result

    structured.Factorization.solve = measured
    start = time.monotonic()
    try:
        raw = dispatch(request)
    finally:
        structured.Factorization.solve = original
    seconds = time.monotonic()-start
    write_trajectory(folder/'trajectory.json.gz', raw)
    np.savez_compressed(folder/'linear-solves.npz', **arrays)
    reference = {}
    for name, path in [('python', inputs[1]), ('browser', inputs[2])]:
        with gzip.open(path, 'rt') as stream:
            expected = json.load(stream)
        assert len(expected['snapshots']) == len(raw['snapshots']) == 9
        errors = []
        for actual, other in zip(raw['snapshots'][1:], expected['snapshots'][1:]):
            assert abs(actual['time']-other['time']) < 1e-12
            errors.append(float(max(abs(np.array(actual['force'])-other['force']))/(.5*1.225*10**2*200000)))
        reference[name] = max(errors)
    report = dict(mode=mode, diagnostic_only=True, seconds=seconds,
        accepted_steps=raw['accepted_steps'], rejected_steps=raw['rejected_steps'],
        new_step_residual=max(s['residual'] for s in raw['snapshots'][1:]),
        force_difference=reference, linear_solves=rows,
        max_local_z_acceleration=max(abs(v[2]) for s in raw['snapshots'][1:] for v in s['local_acceleration']))
    write(folder/'report.json', report)
    print(json.dumps({k:v for k,v in report.items() if k!='linear_solves'}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['original', 'refined', 'refined-double', 'dense', 'equilibrated'])
    run(parser.parse_args().mode)
