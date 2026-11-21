"""Bounded, serial FFWT-4 timing with exact full-output parity to saved evidence."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
REFERENCE = ROOT/'artifacts/isae/ffwt4-profile-20261106/base-gust'
ARCHIVE = ROOT/'.reference/solver-snapshots/ffwt4-before-operator-cache-20261106'


def read(path):
    with path.open() as stream:
        return json.load(stream)


def pin(path):
    data = path.read_bytes()
    return dict(path=str(path), bytes=len(data), sha256=hashlib.sha256(data).hexdigest())


def content_hash(value):
    # Includes every output field and preserves float representation/signed
    # zero. Only dictionary order and JSON whitespace are disregarded.
    data = json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    return hashlib.sha256(data).hexdigest()


def write(path, value):
    with path.open('w') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--implementation', choices=['baseline', 'current'], required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    folder = args.output_dir.resolve()
    folder.mkdir(parents=True, exist_ok=False)
    archive = read(ARCHIVE/'manifest.json')
    reference_plan = read(REFERENCE/'plan.json')
    reference_report = read(REFERENCE/'report.json')
    assert [entry['original'] for entry in archive['files']] == reference_plan['kernel_pins']
    current, changed = [], []
    for entry in archive['files']:
        original, saved = entry['original'], pin(Path(entry['archived']))
        assert (saved['bytes'], saved['sha256']) == (original['bytes'], original['sha256'])
        actual = pin(Path(original['path']))
        current.append(actual)
        if actual != original:
            changed.append(str(Path(original['path']).relative_to(ROOT)))
    assert changed == ['openswing/tangent_influences.py'], changed
    inputs = reference_plan['source_pins'] + [reference_report['request'], reference_report['result']]
    inputs += [pin(ARCHIVE/'manifest.json'), pin(REFERENCE/'plan.json'), pin(REFERENCE/'report.json'), pin(Path(__file__))]
    for entry in inputs:
        assert pin(Path(entry['path'])) == entry
    request = read(REFERENCE/'request.json')
    reference = read(REFERENCE/'result.json')
    expected = content_hash(reference)
    del reference
    write(folder/'plan.json', dict(implementation=args.implementation, inputs=inputs,
        current_kernels=current, archived_kernels=archive['files'], changed=changed,
        full_output_reference_sha256=expected, timed_region='dispatch only, imports excluded',
        native_pass_count_change=0))

    # Select the archived class before any solver module imports it. The rest
    # of the kernel is authenticated as byte-identical in both runs.
    import openswing.tangent_influences as tangent
    if args.implementation == 'baseline':
        specification = importlib.util.spec_from_file_location('openswing._timing_baseline',
            ARCHIVE/'openswing/tangent_influences.py')
        baseline = importlib.util.module_from_spec(specification)
        specification.loader.exec_module(baseline)
        tangent.TangentInfluences = baseline.TangentInfluences
    from openswing.factored_influence import FactoredInfluence
    from openswing.bridge import dispatch
    constructor, query = FactoredInfluence.__init__, tangent.TangentInfluences.factored_vortex
    counts = dict(operators_built=0, tangent_queries=0)

    def counted_constructor(self, *a, **kw):
        counts['operators_built'] += 1
        constructor(self, *a, **kw)

    def counted_query(self, *a, **kw):
        counts['tangent_queries'] += 1
        return query(self, *a, **kw)

    FactoredInfluence.__init__ = counted_constructor
    tangent.TangentInfluences.factored_vortex = counted_query
    started = time.perf_counter()
    try:
        result = dispatch(request)
    finally:
        seconds = time.perf_counter()-started
        FactoredInfluence.__init__ = constructor
        tangent.TangentInfluences.factored_vortex = query
    actual = content_hash(result)
    assert actual == expected, 'Full result differs from the authenticated pre-change trajectory.'
    assert result['converged'] and result['accepted_steps'] == 4 and result['rejected_steps'] == 0
    maximum_residual = max(snapshot['residual'] for snapshot in result['snapshots'])
    assert maximum_residual <= 1e-8
    for entry in inputs + current:
        assert pin(Path(entry['path'])) == entry
    report = dict(status='PASS', implementation=args.implementation, seconds=seconds,
        counts=counts, accepted_steps=4, rejected_steps=0, maximum_residual=maximum_residual,
        full_output_sha256=actual, full_output_exactly_equal=True,
        jacobian_builds=result['jacobian_builds'], newton_iterations=result['newton_iterations'],
        native_pass_count_change=0, source_pins_unchanged=True, kernel_pins_unchanged=True)
    write(folder/'report.json', report)
    print(json.dumps(report), flush=True)


if __name__ == '__main__':
    main()
