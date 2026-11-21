"""Saved fresh ST4 pilot evidence must survive report import without alteration."""
from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import isae_suite_st4_mechanics as adapter


@pytest.fixture(scope='module')
def original():
    run = ROOT/'artifacts/isae/st4-recurring-20261109/paper'
    plan = adapter.read(run/'plan.json'); report = adapter.read(run/'report.json')
    job = plan['jobs'][0]
    row = next(j for j in report['jobs'] if j['id'] == job['id'])
    result = adapter.read(Path(row['result']['artifact_root']).parent/'result.json')
    # The worker's original strict result, before the report's5% policy view.
    folder = next(Path(result['artifact_root']).glob('st4-mechanics-*'))
    return job, result, folder


def test_fresh_saved_matrices_and_requests_are_importable(original):
    job,result,_ = original
    files = adapter.verify_artifacts(ROOT, job, result)
    assert len(files) == 18
    assert sum(Path(p['path']).name in ('A.npz','M.npz') for p in files) == 4


@pytest.mark.parametrize('fault', ['request','matrix','missing_vector','receipt','audit','plan','report'])
def test_modified_physical_artifacts_rejected(original, tmp_path, fault):
    job,result,source = original
    result = deepcopy(result); result['artifact_root'] = str(tmp_path)
    # Link untouched large files; only unlink-and-replace the selected fault.
    for file in source.rglob('*'):
        dest = tmp_path/file.relative_to(source)
        if file.is_dir(): dest.mkdir(exist_ok=True)
        else: dest.symlink_to(file.resolve())
    names = dict(request='job-00/request.json', matrix='job-00/A.npz', missing_vector='job-00/result.json',
                 receipt='child-0.json', audit='evidence.json', plan='plan.json', report='job-00/report.json')
    path = tmp_path/names[fault]
    if fault in ('matrix','missing_vector'):
        path.unlink()
        if fault == 'matrix': path.write_bytes(b'corrupt')
    else:
        data = json.loads(path.read_text()); path.unlink()
        if fault == 'request': data['modes']['gravity_magnitude'] = 9.81
        elif fault == 'receipt': data['returncode'] = -9
        elif fault == 'audit': data['mesh_checks'][0]['relative_change'] = 0.
        elif fault == 'plan': data['jobs'][0]['panels'] = 32
        else: data['positive_frequencies_Hz'][0] *= 2
        adapter.save(path, data)
    with pytest.raises((ValueError, FileNotFoundError)):
        adapter.verify_artifacts(ROOT, job, result)
