"""Validate continuation history separately from an accepted terminal BDF step."""
import math
from hashlib import sha256
import json


def validate_checkpoint(raw, *, final, expected_end):
    samples = raw['snapshots']
    assert len(samples) >= 3
    sample, previous, previous2 = samples[-1], samples[-2], samples[-3]
    saved = sample['restart']
    accepted = saved['accepted_method']
    assert sample['time'] == saved['state']['time'] == expected_end
    assert sample['order'] == accepted['effective_order'] == 2
    assert accepted['kind'] == 'bdf'
    assert accepted['scheme'] == 'drela-euler-bdf-v1'
    assert accepted['endpoint']['state'] == saved['state']
    assert accepted['previous'] == previous['restart']['state']
    assert accepted['previous2'] == previous2['restart']['state']
    assert accepted['previous']['time'] == previous['time']
    assert accepted['previous2']['time'] == previous2['time']
    assert accepted['end_time'] == expected_end
    step = expected_end - previous['time']
    prior_step = previous['time'] - previous2['time']
    assert step > 0 and prior_step > 0
    assert accepted['step'] == sample['step'] == step
    ratio = step/prior_step
    coefficients = [(1+2*ratio)/(step*(1+ratio)), -(1+ratio)/step,
                    ratio*ratio/(step*(1+ratio))]
    assert len(accepted['coefficients']) == 3
    assert all(math.isclose(a, b, rel_tol=1e-12, abs_tol=1e-12)
               for a, b in zip(accepted['coefficients'], coefficients))
    if final:
        # The accepted step reaches the table from the left. A later resume
        # must first complete the cutoff's right state and restart BDF1.
        assert raw['forcing']['end_time'] == expected_end
        assert raw['forcing']['breaks'] == [expected_end]
        assert sample['forcing_side'] == saved['forcing_side'] == accepted['endpoint_side'] == 'left'
        assert saved['older'] is None
    else:
        assert expected_end < raw['forcing']['end_time']
        assert expected_end not in raw['forcing']['breaks']
        assert sample['forcing_side'] == saved['forcing_side'] == accepted['endpoint_side'] == 'right'
        assert saved['older'] == previous['restart']['state']
    return dict(accepted_order=2, accepted_history_verified=True,
                terminal_cutoff=bool(final), continuation_history_cleared=bool(final))


def digest(path):
    result = sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            result.update(block)
    return result.hexdigest()


def assessment_sources(base, root):
    """Bind the corrected assessment without replacing the failed producer."""
    manifest_path = base/'assessment.json'
    execution_path = base/'assessment-execution.json'
    manifest = json.loads(manifest_path.read_text())
    execution = json.loads(execution_path.read_text())
    assert execution['exit_code'] == 0
    assert execution['report_sha256'] == digest(manifest_path)
    assert manifest['passed'] and not manifest['numerical_reexecution']
    assert manifest['original_producer_exit_code'] == 1
    assert manifest['original_successful_requests'] == 329
    assert manifest['reassessed_request'] == 329
    assert manifest['original_plan_sha256'] == digest(base/'plan.json')
    completion = json.loads((base/'production-complete.json').read_text())
    assert completion['kind'] == 'retained-result-assessment'
    assert completion['computed_jobs'] == 330 and completion['physical_steps'] == 5280
    assert completion['original_producer_exit_code'] == 1
    assert all(digest(root/name) == value for name, value in manifest['source_sha256'].items())
    # The final combine rechecks all input bytes. Chunk readers check the raw
    # files and receipts they consume, avoiding a second whole-history scan.
    pins = {**manifest['source_sha256'], **manifest['input_sha256']}
    for path in (manifest_path, execution_path, base/'production-complete.json'):
        pins[str(path.relative_to(root))] = digest(path)
    return pins
