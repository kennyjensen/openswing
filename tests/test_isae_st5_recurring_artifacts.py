"""Fresh ST-5 physical artifacts and provenance survive independent import."""
from copy import deepcopy
import importlib.util
from pathlib import Path
import sys

import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import isae_suite_st5_mechanics as adapter
PILOT=ROOT/'artifacts/isae/st5-recurring-20261110/pilot'


@pytest.fixture(scope='module')
def original():
    plan=adapter.read(PILOT/'plan.json');report=adapter.read(PILOT/'report.json')
    job=plan['jobs'][0];row=report['jobs'][0]
    result=adapter.read(Path(row['result']['artifact_root']).parent/'result.json')
    folder=next(Path(result['artifact_root']).glob('st5-mechanics-*'))
    return job,result,folder


def test_five_fresh_physical_states_and_residual_fields_are_importable(original):
    job,result,_=original
    files=adapter.verify_artifacts(ROOT,job,result)
    assert sum(Path(p['path']).name=='fresh-fields.npz' for p in files)==5
    assert result['solver_calls']==5 and len(result['mesh_checks'])==14


@pytest.mark.parametrize('fault',['residual','missing_fields','receipt','audit','plan','report','manifest'])
def test_changed_or_missing_saved_evidence_is_rejected(original,tmp_path,fault):
    job,result,source=original;result=deepcopy(result);result['artifact_root']=str(tmp_path)
    for p in source.rglob('*'):
        dest=tmp_path/p.relative_to(source)
        if p.is_dir():dest.mkdir(exist_ok=True)
        else:dest.symlink_to(p.resolve())
    names=dict(residual='run-4/level4/fresh-fields.npz',missing_fields='run-0/level0/fresh-fields.npz',
        receipt='run-2/execution.json',audit='audit.json',plan='run-1/plan.json',
        report='run-0/level0/comparison.json',manifest='artifacts.json')
    path=tmp_path/names[fault]
    if fault in ('residual','missing_fields'):
        path.unlink()
        if fault=='residual':path.write_bytes(b'corrupt')
    else:
        data=adapter.read(path);path.unlink()
        if fault=='receipt':data['returncode']=-9
        elif fault=='audit':data['passed']=False
        elif fault=='plan':data['meshes'][0]['panels']['default']=32
        elif fault=='report':data['rows'][0]['values'][1]+=1
        else:data=[r for r in data if r['path']!='run-0/level0/fresh-fields.npz']
        adapter.save(path,data)
    with pytest.raises((ValueError,FileNotFoundError)):
        adapter.verify_artifacts(ROOT,job,result)


def summary_module():
    spec=importlib.util.spec_from_file_location('st5_artifact_summary',ROOT/'scripts/summarize-isae-suite.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


@pytest.mark.parametrize('fault',['missing_opt_in','missing_helper','changed_source'])
def test_importer_requires_scope_and_source_provenance(tmp_path,fault):
    plan=adapter.read(PILOT/'plan.json');report=adapter.read(PILOT/'report.json')
    if fault=='missing_opt_in':
        plan['execution_policy']['comparison_scopes']=[];report['execution_policy']=deepcopy(plan['execution_policy'])
    elif fault=='missing_helper':
        plan['code_sha256'].pop('scripts/isae_st5_recurring_worker.py');report['code_sha256']=deepcopy(plan['code_sha256'])
    else:
        plan['jobs'][0]['source_pins'][0]['bytes']+=1
        report['jobs'][0]['source_pins']=deepcopy(plan['jobs'][0]['source_pins'])
    for name,data in [('plan',plan),('report',report),('catalog',plan['catalog'])]:adapter.save(tmp_path/(name+'.json'),data)
    with pytest.raises(ValueError):summary_module().load_runs([tmp_path])
