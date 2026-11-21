"""Retained fresh ST-3 pilot artifacts must support the reported predictions."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil

import pytest

from scripts import isae_suite_st3_mechanics as mechanics

ROOT=Path(__file__).resolve().parents[1]
PILOT=ROOT/'artifacts/isae/st3-mechanics-runner-20261109/pilot'


@pytest.fixture
def saved(tmp_path):
    def load(kind):
        if not (PILOT/'report.json').is_file():
            pytest.skip('Optional fresh ST-3 pilot artifacts unavailable')
        plan=json.loads((PILOT/'plan.json').read_text())
        job=next(j for j in plan['jobs'] if j['target_kind']==kind)
        folder=PILOT/'jobs'/hashlib.sha256(job['id'].encode()).hexdigest()[:20]
        if not (folder/'result.json').is_file():
            pytest.skip('Selected ST-3 pilot job has not completed')
        result=json.loads((folder/'result.json').read_text())
        assert result['status']=='computed'
        original=Path(result['artifact_root'])
        if not original.is_absolute():original=ROOT/original
        stage=original if (original/'adapter-result.json').is_file() else next(original.glob('st3-mechanics-*'))
        target=tmp_path/kind
        shutil.copytree(stage,target)
        result=deepcopy(result);result['artifact_root']=str(target)
        return job,result,target
    return load


@pytest.mark.parametrize('kind',['static','modal'])
def test_complete_fresh_physical_evidence_is_accepted(saved,kind):
    job,result,folder=saved(kind)
    pins=mechanics.verify_artifacts(ROOT,job,result)
    assert pins and all(Path(p['path']).is_relative_to(folder) for p in pins)


@pytest.mark.parametrize('fault',['request_bytes','child_failure','plan_settings','matrix_bytes','missing_shapes'])
def test_incomplete_or_modified_physical_evidence_is_rejected(saved,fault):
    modal=fault in ('matrix_bytes','missing_shapes')
    job,result,folder=saved('modal' if modal else 'static')
    if fault=='request_bytes':
        with (folder/'job-00/request.json').open('a') as f:f.write('\n')
    elif fault=='child_failure':
        (folder/'child-1.json').write_text(json.dumps(dict(returncode=1,terminal=True)))
    elif fault=='plan_settings':
        path=folder/'plan.json';plan=json.loads(path.read_text())
        plan['jobs'][0]['masses_kg']=[0.,0.]
        path.write_text(json.dumps(plan))
    elif fault=='matrix_bytes':
        with (folder/'job-0/A.npz').open('ab') as f:f.write(b'changed')
    else:
        (folder/'job-0/shapes.npz').unlink()
    with pytest.raises((ValueError,FileNotFoundError)):
        mechanics.verify_artifacts(ROOT,job,result)
