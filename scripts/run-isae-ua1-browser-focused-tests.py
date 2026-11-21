"""Run remaining focused regression checks in small serial subprocesses."""
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import time
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'artifacts/isae/ua1-incidence-periodic-browser-20261102-r1'
env = dict(os.environ, OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1', MKL_NUM_THREADS='1', PYTHONDONTWRITEBYTECODE='1')
jobs = [
    ('cutoff', ['tests/test_isae_ua2_browser_cutoff.py']),
    ('endpoint', ['tests/test_time_endpoint_roundoff.py']),
    ('forcing-setup', ['tests/test_forcing.py', '-k', 'natural_cubic or doubled_times or bad_or_unimplemented or acceleration_history_cannot']),
]
for name in [
    'prescribed_acceleration_ramp_converges_to_exact_cubic_translation',
    'step_impulse_is_not_applied_before_jump_and_bdf_restarts',
    'flap_history_reaches_actual_section_pitching_loads',
    'time_varying_proportional_thrust_accelerates_free_rigid_mass',
    'angular_acceleration_table_integrates_in_degrees_with_second_order_rotation',
    'flap_ramp_time_domain_lift_converges_to_the_analytic_empirical_lag',
]:
    jobs.append((name, ['tests/test_forcing.py::test_' + name]))

receipts = []
for name, selection in jobs:
    receipt_path = BASE / f'focused-{name}-execution.json'
    assert not receipt_path.exists(), receipt_path
    junit = BASE / f'focused-{name}-tests.xml'
    log = BASE / f'focused-{name}-tests.log'
    command = ['timeout', '60s', 'nice', '-n', '10', str(ROOT / '.venv/bin/python'), '-m', 'pytest', '-q', *selection, '--junitxml=' + str(junit)]
    start = time.monotonic()
    with log.open('x') as output:
        result = subprocess.run(command, cwd=ROOT, env=env, stdout=output, stderr=subprocess.STDOUT)
    receipt = dict(name=name, command=command, exit_code=result.returncode, wall_seconds=time.monotonic()-start, log_sha256=sha256(log.read_bytes()).hexdigest())
    if junit.exists():
        cases = ET.parse(junit).getroot().findall('.//testcase')
        failed = sum(case.find('failure') is not None or case.find('error') is not None for case in cases)
        skipped = sum(case.find('skipped') is not None for case in cases)
        receipt.update(passed_tests=len(cases)-failed-skipped, failed_tests=failed, skipped_tests=skipped, junit_sha256=sha256(junit.read_bytes()).hexdigest())
    receipt_path.write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt), flush=True)
    assert result.returncode == 0 and receipt.get('failed_tests') == 0, 'Preserve failed receipt and stop'
    receipts.append(receipt)

previous = json.loads((BASE / 'focused-periodic-tests-execution.json').read_text())
assert previous['exit_code'] == 0
total = previous['passed_tests'] + sum(r['passed_tests'] for r in receipts)
summary = dict(exit_code=0, passed_tests=total, jobs=len(receipts)+1, serial=True, timeout_seconds_per_job=60, prior_combined_attempt_exit_code=124, receipts=receipts, periodic=previous)
(BASE / 'focused-tests-results.json').write_text(json.dumps(summary, indent=2) + '\n')
print(json.dumps(dict(passed_tests=total, completed_jobs=len(receipts)+1)), flush=True)
