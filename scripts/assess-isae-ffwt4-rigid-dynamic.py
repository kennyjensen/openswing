"""Audit saved dynamic pencils through full inverse blocks at held-out s values."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import numpy as np
from isae_ffwt4_evidence import pin, read, require, write
from isae_ffwt4_rigid_extension_v2 import fixture


def inverse_block(A, M, n, s, extended):
    """Read physical compliance directly from the FULL descriptor inverse.

    Unlike the producer's two-stage Schur complement, this eliminates nothing
    explicitly. Canonical row/column blocks come from the production layout.
    """
    cols = np.r_[np.arange(6*5), 6*n.nn+np.arange(6*4), 6*(n.nn+n.ne)+np.arange(6)]
    rows = np.r_[np.arange(6*4), 6*n.ne+np.arange(3*5),
                 6*n.ne+3*n.nn+np.arange(3*5), 6*(n.ne+n.nn)+np.arange(6)]
    require(len(cols) == len(rows) == 60, 'Wrong retained layout')
    if not extended:
        require(np.array_equal(cols, np.arange(n.size)) and np.array_equal(rows, np.arange(n.size)),
                'Unexpected condensed ordering')
    # Retained physical state is five poses, four internal wrenches, one
    # support wrench. Retained equations are four compatibility conditions,
    # five force/moment balances, one clamp condition.
    physical_state = np.r_[np.tile([n.L]*3+[1.]*3, 5),
        np.tile([n.F]*3+[n.F*n.L]*3, 5)]
    physical_rhs = np.r_[np.tile([n.L]*3+[1.]*3, 4),
        np.full(15, n.F), np.full(15, n.F*n.L), [n.L]*3+[1.]*3]
    full_inverse = np.linalg.inv(A-s*M)
    return physical_state[:, None]*full_inverse[np.ix_(cols, rows)]/physical_rhs[None, :]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--root', required=True, type=Path)
    ap.add_argument('--output', required=True, type=Path)
    args = ap.parse_args(); require(not args.output.exists(), 'Preserve earlier evidence')
    terminals, pins = {}, [pin(__file__)]
    for path in sorted(args.root.glob('terminal-*.json')):
        receipt = read(path); pins.append(pin(path))
        for row in receipt.get('attempts', [receipt]):
            require(row['exit_code'] == 0, 'Unexpected failed process')
            command = row['command']
            if '--output-dir' in command:
                folder = Path(command[command.index('--output-dir')+1]).resolve()
                require(str(folder) not in terminals, 'Duplicate terminal receipt')
                terminals[str(folder)] = row
    expected = [(chart, end, True, step) for chart in ('body', 'surface')
        for end in ('lower', 'upper') for step in (1e-5, 3e-6)]
    expected += [(chart, 'lower', False, 1e-5) for chart in ('body', 'surface')]
    require(len(terminals) == len(expected) == 10, 'Incomplete comparison scope')
    reports, fields, heldout = [], {}, []
    for chart, end, moving, step in expected:
        tag = f'{chart}-{end}-{"moving" if moving else "stationary"}-h{"1e5" if step == 1e-5 else "3e6"}'
        folder = (args.root/tag).resolve()
        require(str(folder) in terminals, 'Missing actual terminal')
        report, plan = read(folder/'report.json'), read(folder/'plan.json')
        require(report['status'] == 'CONTINUOUS_DYNAMIC_PENCILS_VERIFIED', 'Failed physical comparison')
        require((plan['chart'], plan['end'], plan['moving_frame'], plan['difference_step']) ==
                (chart, end, moving, step), 'Wrong case settings')
        for p in [*plan['kernel_pins'], *plan['helper_pins'], plan['source_check'], report['plan'], report['arrays']]:
            require(pin(p['path']) == p, 'Changed evidence: '+p['path']); pins.append(p)
        pins.append(pin(folder/'report.json'))
        arrays = np.load(report['arrays']['path'], allow_pickle=False)
        pair = [fixture(extended=e, upper=end == 'upper', lifting=chart == 'surface', moving=moving)
                for e in (True, False)]
        for s in (.5j, -2+3j, 20j):
            a = inverse_block(arrays['extended_A'], arrays['extended_M'], pair[0].network, s, True)
            b = inverse_block(arrays['pylon_A'], arrays['pylon_M'], pair[1].network, s, False)
            error = float(np.max(abs(a-b)/(1+abs(b))))
            require(error <= 2e-7, 'Held-out full-inverse comparison failed')
            heldout.append(dict(case=tag, s=[s.real, s.imag], maximum_scaled_error=error))
        for label in ('extended', 'pylon'):
            fields[(chart, end, moving, step, label)] = arrays[label+'_coefficients'].copy()
        arrays.close()
        reports.append(dict(case=tag, report=pin(folder/'report.json'),
            coefficient_pair_errors=report['coefficient_pair_errors'], oracle_checks=report['oracle_checks'],
            frequency_checks=report['frequency_checks'], negative_controls=report['negative_controls']))
    stencils = []
    for chart in ('body', 'surface'):
        for end in ('lower', 'upper'):
            for label in ('extended', 'pylon'):
                a, b = (fields[(chart, end, True, h, label)] for h in (1e-5, 3e-6))
                errors = [float(np.max(abs(x-y)/(1+abs(y)))) for x, y in zip(a, b)]
                require(max(errors) <= 2e-7, 'Finite-difference step consistency failed')
                stencils.append(dict(chart=chart, end=end, representation=label, coefficient_errors=errors))
    tests = args.root/'oracle-tests.xml'; suite = ET.parse(tests).getroot().find('testsuite')
    require(int(suite.attrib['tests']) == len(suite.findall('testcase')) == 24
        and all(int(suite.attrib[k]) == 0 for k in ('failures', 'errors', 'skipped')), 'Oracle tests did not pass')
    pins.extend([pin(tests), pin(ROOT/'tests/test_rigid_point_dynamic_oracle.py')])
    output = dict(status='CONTINUOUS_RIGID_ATTACHMENT_DYNAMICS_ASSESSED', observed_at=datetime.now(timezone.utc).isoformat(),
        cases=reports, comparison_jobs=10, production_linearizations=20, oracle_tests_passed=24,
        held_out_full_inverse_checks=heldout, difference_step_checks=stencils,
        maximum_coefficient_pair_error=max(max(r['coefficient_pair_errors']) for r in reports),
        maximum_spatial_mass_error=max(o['spatial_mass_error'] for r in reports for o in r['oracle_checks']),
        maximum_velocity_error=max(o['velocity_error'] for r in reports for o in r['oracle_checks']),
        maximum_full_inverse_error=max(r['maximum_scaled_error'] for r in heldout),
        pins=list({p['path']: p for p in pins}.values()), new_time_steps=0, native_predictions_added=0,
        production_attachment_rule_changed=False, native_attachment_semantics_established=False,
        qualifications=['Both material charts and both retained beam ends; four-interval retained and auxiliary beams.',
            'Frozen continuous-time linearization at fully converged, zero-local-rate equilibria.',
            'Full point inertia and spin, nonparallel frame rates and accelerations; no point or distributed airflow.',
            'Velocity variables are eliminated in both models before comparing reduced mechanical polynomials.',
            'No general nonlinear 3D trajectory, finite-BDF identity, browser execution or native input interpretation is established.'])
    write(args.output, output)
    print(json.dumps({k: output[k] for k in ('status', 'comparison_jobs', 'oracle_tests_passed', 'maximum_coefficient_pair_error',
        'maximum_spatial_mass_error', 'maximum_velocity_error', 'maximum_full_inverse_error')}), flush=True)


if __name__ == '__main__':
    main()
