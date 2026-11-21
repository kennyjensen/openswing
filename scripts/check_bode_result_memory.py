"""Bounded serialization probes; repeated samples are not new physics solves."""
import argparse
import json
from pathlib import Path
import sys
from types import SimpleNamespace

from check_daedalus_load_sensitivity import ROOT, SOURCE, write
from daedalus_bounded_job import run

STUDY = ROOT / 'artifacts/bode-result-memory-20261114'
SEED = SOURCE / 'trim-6.7-1/state.json'
VECTOR = ROOT / 'artifacts/daedalus-wing-peak-mass-20261114/dip/arrays.npz'
FREQUENCY = 1.15737773741517


def inventory(value):
    seen = set()
    counts = {}

    def visit(v):
        if id(v) in seen:
            return 0
        seen.add(id(v))
        name = type(v).__name__
        counts[name] = counts.get(name, 0) + 1
        size = sys.getsizeof(v)
        if isinstance(v, dict):
            size += sum(visit(k) + visit(x) for k, x in v.items())
        elif isinstance(v, (list, tuple)):
            size += sum(visit(x) for x in v)
        return size

    return dict(python_owned_bytes=visit(value), unique_objects=counts)


def capture(folder, args):
    import numpy as np
    from check_daedalus_structural_resolution import dynamic
    from openswing.frequency_response import HarmonicInput
    from openswing.linear_dynamics import output_perturbation, complex_data

    system = dynamic(SimpleNamespace(seed=SEED))
    assert system.size == 2044
    with np.load(VECTOR) as arrays:
        vector = arrays['original_state']
    omega = 2 * np.pi * FREQUENCY
    forcing, _ = HarmonicInput(system, 'control.3', 0).at_frequency(omega)
    output = output_perturbation(system, vector, 1j * omega * vector, forcing=forcing)
    response = dict(input='control.3', converged=True, state=complex_data(vector),
                    state_rate=complex_data(1j * omega * vector), output=output)
    text = json.dumps(response, allow_nan=False)
    (folder / 'response.json').write_text(text)
    groups = {k: dict(json_bytes=len(json.dumps(v, allow_nan=False).encode()), **inventory(v))
              for k, v in output.items()}
    size = len(text.encode())
    return dict(scope='One full output recovery from a previously checked harmonic state; no new harmonic solve.',
                frequency_hz=FREQUENCY, states=system.size, nodes=system.network.nn,
                elements=system.network.ne, response_json_bytes=size,
                response_inventory=inventory(response), output_groups=groups,
                projected_response_json_bytes={f'41_points_{n}_inputs':41*n*size for n in (1, 5)},
                projection_note='Storage-size extrapolation only; excludes base, headers, matrices, serialization temporaries and browser copies.')


def serialize(folder, args):
    import hashlib
    import resource
    import time
    response = json.loads((STUDY/'capture/response.json').read_text())
    # A transport stress fixture, not 41 newly computed frequencies. Sharing
    # this response isolates encoder allocations from persistent grid storage.
    result = dict(analysis='frequency_response', samples=[
        dict(omega=float(k+1), responses=[response]) for k in range(41)])
    before = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    start = time.monotonic()
    if args['encoder'] == 'old':
        def envelope(value):
            text = json.dumps(value, allow_nan=False)
            return '{"result":' + text + '}'
        packet = envelope(result).encode('utf-8')
    else:
        from openswing.worker_transport import WorkerReply
        reply = WorkerReply(dict(result=result))
        digest_parts = hashlib.sha256()
        byte_count = 0
        try:
            for index in range(reply.part_count):
                packet = reply.next_part()
                raw = packet._data
                digest_parts.update(raw)
                byte_count += len(raw)
                restored = json.loads(raw.tobytes())
                if index == 0:
                    assert restored == dict(result=dict(analysis='frequency_response', samples=[]), sample_count=41)
                else:
                    assert restored == dict(sample=result['samples'][index-1])
                del raw, packet, restored
        finally:
            reply.close()
    elapsed = time.monotonic() - start
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    digest = hashlib.sha256(packet).hexdigest() if args['encoder']=='old' else digest_parts.hexdigest()
    size = len(packet) if args['encoder']=='old' else byte_count
    return dict(scope='41-point, one-input serialization fixture repeating one saved full response; no frequency solves.',
                encoder=args['encoder'], bytes=size, sha256=digest,
                elapsed_seconds=elapsed, before_peak_rss_kib=before,
                after_peak_rss_kib=peak, incremental_peak_rss_kib=peak-before,
                persistent_responses_shared=True, exact_sample_checks=41 if args['encoder']!='old' else None,
                limitation='Measures encoder overhead in native Python, not full grid storage or browser peak memory.')


def checks(folder, args):
    import pytest
    reports = []
    class Results:
        def pytest_runtest_logreport(self, report):
            if report.when == 'call' or report.failed:
                reports.append(dict(test=report.nodeid, outcome=report.outcome))
    tests = ['tests/test_worker_transport.py', 'tests/test_worker_boundary.py', 'tests/test_time_result_storage.py']
    if args.get('ownership'):
        tests += ['tests/test_frequency_sweep.py::test_refinement_retains_samples_and_exact_frozen_pencil_with_owned_inputs',
                  'tests/test_frequency_sweep.py::test_failed_batch_is_transactional_and_can_be_retried',
                  'tests/test_frequency_sweep.py::test_json_boundary_rejects_changed_source_settings_expired_and_discarded_sessions']
    code = pytest.main(['-q', *tests], plugins=[Results()])
    assert code == 0, f'pytest exit {code}'
    return dict(exit_code=int(code), reports=reports)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['capture', 'serialize', 'checks'])
    parser.add_argument('--tag', required=True)
    parser.add_argument('--encoder', choices=['old','streamed'], default='old')
    parser.add_argument('--ownership', action='store_true')
    args = vars(parser.parse_args())
    import check_daedalus_source_operator as source
    inputs = [SEED, VECTOR, source.PROJECT,
              ROOT/'scripts/check_daedalus_structural_resolution.py',
              ROOT/'scripts/check_daedalus_source_operator.py',
              ROOT/'docs/validation/aswing-authoritative-references.md',
              ROOT/'docs/validation/aswing-authoritative-sources.json',
              *sorted((ROOT/'openswing').glob('*.py'))]
    if args['mode'] == 'serialize':
        inputs.append(STUDY/'capture/response.json')
    if args['mode'] == 'checks':
        inputs.extend(ROOT/name for name in ['tests/test_worker_transport.py', 'tests/test_worker_boundary.py',
                      'tests/test_time_result_storage.py', 'tests/data/daedalus-frame-response.json', 'tests/test_frequency_sweep.py'])
    run(STUDY, args['tag'], inputs, globals()[args['mode']], args, __file__)
