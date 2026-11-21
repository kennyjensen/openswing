"""Reject incomplete or detached AE-1 evidence when finishing bookkeeping."""
from copy import deepcopy
import json
from pathlib import Path
import pytest

from scripts.finalize_isae_ae1_saved import RAW_FILES, validate_saved

ROOT=Path(__file__).resolve().parents[1]
FOLDER=ROOT/'artifacts/isae/ae1-full-current-20261110/AE-1-a05-row024-m80-frozen'


@pytest.fixture(scope='module')
def saved():
    if not (FOLDER/'raw').exists():pytest.skip('Retained interrupted AE1 evidence is unavailable')
    raw=next((FOLDER/'raw').iterdir())
    job=json.loads((FOLDER/'job.json').read_text())
    return job,{name:json.loads((raw/name).read_text()) for name in RAW_FILES}


def test_complete_physical_evidence_can_be_verified_without_a_solve(saved):
    job,packet=saved
    values,checks=validate_saved(job,packet)
    assert len(values)==6 and len(checks)==29 and all(c['passed'] for c in checks)


@pytest.mark.parametrize('fault',['sensor','fresh_residual','missing_check','request','strip_force','missing_fresh_call'])
def test_detached_or_partial_physical_evidence_is_rejected(saved,fault):
    job,source=saved;packet=deepcopy(source)
    if fault=='sensor':packet['result.json']['sensors'][0]['position_earth'][2]+=.001
    elif fault=='fresh_residual':packet['restored-result.json']['residual']*=2
    elif fault=='missing_check':packet['physical-checks.json'].pop()
    elif fault=='request':packet['request.json']['condition']['density']=1.225
    elif fault=='strip_force':packet['result.json']['strips'][0]['force'][2]+=.001
    else:packet['operations.json']['fresh_residuals']=0
    with pytest.raises(ValueError):validate_saved(job,packet)
