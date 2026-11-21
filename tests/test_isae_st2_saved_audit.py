"""The saved-evidence audit must reject corrupted pencils and pass claims."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('st2_saved_audit', ROOT/'scripts/audit-isae-st2-modal.py')
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def save(path, value):
    path.write_text(json.dumps(value, allow_nan=False))


@pytest.fixture
def saved(tmp_path):
    model = tmp_path/'original.asw'; model.write_text('unchanged fixture bytes\n')
    table = tmp_path/'original.e00'
    table.write_text('# Original numerical fixture\n'+''.join(f'1 1.0E-13 {i}.00000\n' for i in range(1, 8)))
    stage = tmp_path/'artifacts'; stage.mkdir()
    a, m, modes = np.zeros((20, 20)), np.eye(20), []
    for k in range(10):
        w = k+1
        a[2*k:2*k+2, 2*k:2*k+2] = [[0., -w], [w, 0.]]
        for sign in (1, -1):
            right = np.zeros(20, dtype=complex); right[2*k:2*k+2] = [1, -sign*1j]
            modes.append(dict(eigenvalue=[0., sign*w],
                right=dict(real=right.real.tolist(), imag=right.imag.tolist()),
                left=dict(real=(right/2).real.tolist(), imag=(right/2).imag.tolist())))
    result = dict(diagnostics=dict(method='full_shift_invert', finite_dimension=None, finite_spectrum=None),
                  matrices=dict(A=a.tolist(), M=m.tolist()), modes=modes)
    save(stage/'result.json', result)
    save(stage/'request.json', dict(source=model.read_text(), condition=None, gravity=[0., 0., -9.81], loads=[],
        modes=dict(frame='fixed', position=[0., 0., 0.], attitude=[0., 0., 0.], count=20,
            shift=[-.01, 0.], method='full_shift_invert', step=1e-5, rank_tolerance=1e-9,
            tolerance=1e-9, matrices=True)))
    save(stage/'restored-residual.json', dict(vector=[0.]*20, maximum_absolute=0.))
    force = [0., 0., -.6787*.55*9.81]
    save(stage/'restored-result.json', dict(applied_force=force, support_force=[-v for v in force],
                                         applied_moment=[0., 0., 0.], support_moment=[0., 0., 0.]))
    comparisons = [dict(name=f'row{i:04d}:{part}', predicted=0. if part == 'real' else float(i),
                        passed=part == 'imaginary') for i in range(1, 8) for part in ('real', 'imaginary')]
    job = dict(id='synthetic', model_path=str(model), table_path=str(table),
        result=dict(artifact_directory=str(stage), process_reaped=True, execution_completed=True,
                    process_exit_code=0, reference_checks=comparisons))
    return tmp_path, stage, job


def test_valid_saved_pencil_keeps_real_reference_mismatches(saved):
    root, _, job = saved
    result = audit.audit_job(job, root)
    assert result['passed']
    assert result['reference_targets'] == 14 and result['reference_matches'] == 7
    assert all(not row['passed'] for row in result['reference_comparisons'] if row['name'].endswith(':real'))


def test_corrupted_full_pencil_is_rejected(saved):
    root, stage, job = saved
    raw = audit.read(stage/'result.json'); raw['matrices']['A'][0][0] = .01
    save(stage/'result.json', raw)
    result = audit.audit_job(job, root)
    assert not result['passed']
    assert any(not row['passed'] and 'full pencil' in row['name'] for row in result['checks'])


def test_invented_printed_precision_pass_is_rejected(saved):
    root, _, job = saved
    job = deepcopy(job); job['result']['reference_checks'][0]['passed'] = True
    result = audit.audit_job(job, root)
    assert not result['passed']
    assert any(not row['passed'] and 'comparison accounting' in row['name'] for row in result['checks'])


def test_raw_residual_cannot_be_hidden_by_retained_maximum(saved):
    root, stage, job = saved
    raw = audit.read(stage/'restored-residual.json'); raw['vector'][0] = 1e-3
    save(stage/'restored-residual.json', raw)
    result = audit.audit_job(job, root)
    assert not result['passed']
    assert {row['name'] for row in result['checks'] if not row['passed']} == {
        'saved raw restored residual', 'raw residual reported maximum'}
