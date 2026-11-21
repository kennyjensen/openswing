"""Original AP2 input reconstruction, target completeness and evidence guards."""
from copy import deepcopy
from decimal import Decimal
import hashlib
import json
from pathlib import Path

import pytest

from scripts import isae_suite_ap2 as ap2


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope='module')
def catalog():
    return json.loads((ROOT/ap2.CATALOG).read_text())


@pytest.fixture(scope='module')
def jobs():
    return ap2.plan(ROOT)


def without_engines(raw):
    lines=raw.splitlines(keepends=True)
    positions={i+1 for i,line in enumerate(lines) if b'#  Propeller 1 position' in line or b'# Propeller 2 position' in line}
    return b''.join(line for i,line in enumerate(lines) if i not in positions)


def test_every_native_ratio_and_coefficient_target_is_retained(catalog,jobs):
    assert len(jobs)==237
    assert sum(j['expected_outputs'] for j in jobs)==248
    executable=[j for j in jobs if j['execution_route']=='worker']
    assert len(executable)==234
    assert len({j['coordinate_id'] for j in executable})==117
    assert len({j['source'] for j in executable})==2
    assert {j['nominal'] for j in executable}=={150,300}
    assert sum(o['name']=='CL_CD_ratio' for j in executable for o in j['observations'])==234
    assert sum(o['name'] in ('CL','CD') for j in executable for o in j['observations'])==8
    assert sum(j['expected_outputs'] for j in jobs if j['execution_route']=='unsupported')==6
    for j in executable:
        o=j['observations'][0]
        assert o['tolerance']==0. and o['expected'].hex()==o['expected_hex']
        assert j['condition']['powers']=={'1':330.}


def test_generator_changes_only_source_engine_rows_and_preserves_distinct_drag(catalog):
    endpoints=interiors=0
    for series in catalog['series']:
        original=(ROOT/series['model_path']).read_bytes()
        assert hashlib.sha256(without_engines(original)).hexdigest()==series['non_engine_bytes_sha256']
        for row in series['rows']:
            generated=ap2.reconstruct_source(original,row['engine_tokens'],row['original_endpoint'])
            assert without_engines(generated)==without_engines(original)
            assert hashlib.sha256(generated).hexdigest()==row['generated_source_sha256']
            if row['original_endpoint']:
                endpoints+=1
                assert generated==original
            else:
                interiors+=1
    assert (endpoints,interiors)==(2,115)
    assert [s['cdp'] for s in catalog['series']]==[.0045,.005]


def test_endpoint_native_precision_not_replaced_by_mat_precision(catalog,jobs):
    for series in catalog['series']:
        row=series['rows'][-1]
        pair=row['paired_csv']
        assert row['ratio']==pair['CL']['expected']/pair['CD']['expected']
        for field in pair.values():
            expected=Decimal(field['token'])
            assert field['expected']==float(expected)
            assert field['tolerance']==float(Decimal(5).scaleb(expected.as_tuple().exponent-1))
    endpoint=next(j for j in jobs if j.get('source_row',{}).get('original_endpoint'))
    assert {o['name'] for o in endpoint['observations']}=={'CL','CD','CL_CD_ratio'}


@pytest.mark.parametrize('mutation', ['ratio','precision','engine','power','mesh','observation_count'])
def test_changed_grid_contract_rejected_by_original_sources(jobs,mutation):
    job=deepcopy(jobs[0])
    if mutation=='ratio':job['observations'][0]['expected']+=.01
    elif mutation=='precision':job['observations'][0]['tolerance']=.1
    elif mutation=='engine':job['source_row']['engine_tokens']['positive'][6]='0.0'
    elif mutation=='power':job['condition']['powers']['1']=500.
    elif mutation=='mesh':job['panels']=80
    else:job['expected_outputs']=0
    with pytest.raises(ValueError):ap2.verify_reference_sources(ROOT,job)


def test_unpaired_exports_never_evaluate_a_model(jobs,monkeypatch):
    def forbidden(*args,**kwargs):raise AssertionError('blocked source-only job attempted physics')
    monkeypatch.setattr(ap2,'_execute',forbidden)
    for job in jobs[-3:]:
        result=ap2.run(ROOT,job)
        assert result['status']=='unsupported'
        assert result['physical_calls']==result['production_imports']==0
        assert len(result['reference_checks'])==2
        assert all(c['predicted'] is None and c['passed'] is False for c in result['reference_checks'])
        assert ap2.validate_result_contract(job,result)


@pytest.mark.parametrize('field,value', [('physical_calls',1),('numerical_pass',True),('reference_match',True),('status','computed')])
def test_unpaired_export_cannot_be_promoted(jobs,field,value):
    job=jobs[-1];result=ap2.validate_blocked(ROOT,job)
    result[field]=value
    with pytest.raises(ValueError):ap2.validate_result_contract(job,result)


def test_missing_physical_evidence_cannot_claim_computed(jobs):
    result=dict(status='computed',numerical_pass=True,source_pins_unchanged=True,kernel_pins_unchanged=True,
        operations=dict(cold_solves=1,fresh_residuals=1,retries=0),physical_calls=2,physical_checks=[])
    with pytest.raises(ValueError,match='physical check set'):ap2.validate_result_contract(jobs[0],result)


def test_engine_marker_and_endpoint_tokens_are_checked(catalog):
    series=catalog['series'][0];row=deepcopy(series['rows'][-1]);raw=(ROOT/series['model_path']).read_bytes()
    with pytest.raises(ValueError,match='marker'):
        ap2.reconstruct_source(raw.replace(b'# Propeller 2 position',b'# no marker'),row['engine_tokens'])
    row['engine_tokens']['positive'][6]='1.0'
    with pytest.raises(ValueError,match='endpoint'):
        ap2.reconstruct_source(raw,row['engine_tokens'],True)


def test_independent_wrenches_retain_engine_vertical_moment():
    result=dict(strips=[dict(force=[1.,2.,3.],moment=[4.,5.,6.],position=[.2,.3,.4])],
        engines=[dict(force=[-10.,0.,0.],moment=[0.,0.,0.],position=[-.1,.5,.2]),
                 dict(force=[-10.,0.,0.],moment=[0.,0.,0.],position=[-.1,-.5,.2])])
    out=ap2.reconstruct_wrenches(result,[0.,0.,0.])
    assert out['engine_force']==[-20.,0.,0.]
    assert out['engine_moment']==[0.,-4.,0.]
    values=ap2._values(dict(out,CDi=.01,efficiency=.8),dict(alpha=0.,density=1.2256,speed=50.))
    qs=.5*1.2256*50.**2*.1536
    assert values['CL']==3./qs and values['CD']==1./qs
    assert values['CL_CD_ratio']==3.


def test_mesh_diagnostic_does_not_invent_a_gate(jobs):
    diagnostics=ap2.mesh_diagnostics(jobs,{})
    assert len(diagnostics)==117
    assert all(d['status']=='UNAVAILABLE' and d['passed'] is None and d['acceptance_gate'] is None for d in diagnostics)
