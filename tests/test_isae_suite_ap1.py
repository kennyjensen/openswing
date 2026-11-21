"""AP1 archive/adapter contracts; no numerical model construction or solves."""
from copy import deepcopy
import builtins
import json
from pathlib import Path
import sys

import pytest

from scripts import isae_suite_ap1 as ap1


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope='module')
def jobs():
    if not (ROOT/'.reference/isae-validation/manifest.json').is_file():
        pytest.skip('Optional original ISAE archive unavailable')
    before = {name for name in sys.modules if name == 'openswing' or name.startswith('openswing.')}
    result = ap1.build_jobs(ROOT)
    assert {name for name in sys.modules if name == 'openswing' or name.startswith('openswing.')} == before
    return result


def selected(jobs, name='AP-1-PROWINA4-header-m150'):
    return next(job for job in jobs if job['id'] == name)


def physical_fixture():
    checks = []
    for name, spec in ap1.PHYSICAL_CHECK_SPECS.items():
        check = dict(name=name,passed=True)
        if spec['metric'] is None:
            check.update(actual=deepcopy(spec.get('expected',{'fixture':'same identity'})),
                         expected=deepcopy(spec.get('expected',{'fixture':'same identity'})))
        else:
            check.update({spec['metric']:0.,'gate':ap1.GATES[spec['gate']]})
            if name.startswith('independent_'):
                check.update(reported=[0.,0.,0.],reconstructed=[0.,0.,0.])
            elif name in ('force_balance','moment_balance'):
                check.update(applied=[0.,0.,0.],support=[0.,0.,0.])
            elif name == 'restored_header_parity':
                check.update(reported={k:0. for k in ap1.HEADER_NAMES},restored={k:0. for k in ap1.HEADER_NAMES},
                             channels={k:0. for k in ap1.HEADER_NAMES})
        checks.append(check)
    return checks


def test_complete_archive_scope_and_only_six_header_routes(jobs):
    assert len(jobs) == len({j['id'] for j in jobs}) == 26
    assert sum(j['expected_outputs'] for j in jobs) == 15470
    executable = [j for j in jobs if j['execution_route'] == 'worker']
    blocked = [j for j in jobs if j['execution_route'] == 'unsupported']
    assert len(executable) == 6 and sum(j['expected_outputs'] for j in executable) == 78
    assert len(blocked) == 20 and sum(j['expected_outputs'] for j in blocked) == 15392
    assert all(j['target_kind'] == 'paired_header' and j['model_path'].endswith('/PROWIM.asw') for j in executable)
    assert all(j['reference_rows'] == [] for j in jobs if j['target_kind'] == 'paired_header')
    unique_rows = {(j['table_path'], r['row_number']) for j in jobs for r in j['reference_rows']}
    assert len(unique_rows) == 1001
    assert all(j['literal_input_modified'] is False and j['complete_family_reproduction'] is False for j in jobs)
    assert all(j['observations'] and not any(o['missing'] for o in j['observations']) for j in jobs)


def test_literal_shared_power_and_reconstructed_mesh_are_explicit(jobs):
    job = selected(jobs)
    assert job['condition']['powers'] == {'1':500.}
    assert job['pairing']['unused_driver_power_W'] == {'2':333.}
    assert job['pairing']['per_engine_power_W'] == [500.,500.]
    assert [e['tokens'][:3] for e in job['pairing']['engine_records']] == [['1','1','1']]*2
    assert job['pairing']['original_node_I'] == 150 and job['nominal'] == 150
    assert selected(jobs, 'AP-1-PROWINA4-header-m300')['nominal'] == 300
    assert job['condition']['mach'] == 0 and job['condition']['density'] == 1.2256
    assert job['condition']['freeze_influences'] is False and job['condition']['wake_core_ratio'] == .25
    assert job['condition']['attitude'] == [0.,0.,0.]
    assert job['settings'] == ap1.POLICY and job['expected_operations'] == dict(cold_solves=1,fresh_residuals=1,retries=0)
    d = selected(jobs, 'AP-1-PROWINA4d-header-m150')
    assert d['pairing']['literal_dCLda'] == [0.,0.] and d['blocker_code'] == 'ZERO_LIFT_SLOPE'
    assert d['condition'] is None and d['settings'] is None


def test_original_header_precision_and_all_thirteen_outputs(jobs):
    job = selected(jobs)
    contract = ap1.reference_contract(job)
    assert list(contract) == list(ap1.HEADER_NAMES)
    assert contract['sum Fy']['expected_token'] == '0.3854E-12'
    assert contract['sum Fy']['expected'] == 3.854e-13
    assert contract['sum Fy']['exact_decimal_tolerance'] == '5E-17'
    assert contract['avg CL']['expected'] == .5518 and contract['avg CL']['tolerance'] == .00005
    assert contract['avg CD']['tolerance'] == .000005
    assert contract['avg Cm']['expected'] == -.1379
    assert contract['Lift']['expected'] == 129.8 and contract['Lift']['tolerance'] == .05
    assert all(field['source_line'] <= 26 for field in contract.values())


@pytest.mark.parametrize('alpha,powers', [(0,[0,-1,0]),(4,[1,0,2]),(10,[1,1,2])])
def test_span_exponents_all_rows_dummy_and_one_sided_duplicates(jobs, alpha, powers):
    job = selected(jobs, f'AP-1-PROWINA{alpha}-span-m150')
    assert job['resultant_exponents'] == powers
    assert len(job['reference_rows']) == 150 and job['expected_outputs'] == 1200
    assert job['reference_rows'][0]['line_number'] == 34
    assert job['reference_rows'][-1]['fields']['cl']['expected'] == 0
    assert job['blocker_code'] == 'SPAN_DISPLAY_UNRESOLVED'
    contract = ap1.reference_contract(job)
    for anchor in (-.3,0.,.3):
        matches = [r for r in job['reference_rows'] if r['fields']['y']['expected'] == anchor]
        assert len(matches) == 2
        assert matches[1]['row_number'] == matches[0]['row_number']+1
    assert contract['row0001:y']['tolerance'] == .0005
    assert contract['row0001:a_flap']['units'] == 'unresolved display units'
    for i, name in enumerate(("Mc'/10", "Ms'/10", 'Fn/10')):
        target = contract['row0001:'+name]
        assert target['power10'] == powers[i]
        assert target['tolerance'] == pytest.approx(target['printed_tolerance']*10**powers[i])


def test_unpaired_fixed_width_row_and_operating_cl_are_retained(jobs):
    span = selected(jobs, 'AP-1-PROWIN-unpaired')
    assert span['model_path'] is None and span['driver_path'] is None
    assert span['expected_outputs'] == 913 and len(span['reference_rows']) == 100
    assert 'f_aero' in span['columns'] and span['resultant_exponents'] == [0,0,1]
    assert any(len(row['raw_line'].split()) != 10 for row in span['reference_rows'])
    assert all(len(row['tokens']) == 10 for row in span['reference_rows'])
    assert ap1._tokens(' 1.00-0.233E-02 +.1 ') == ['1.00','-0.233E-02','+.1']
    op = selected(jobs, 'AP-1-PROWIM-t-unpaired')
    assert op['expected_outputs'] == 1
    assert op['observations'][0]['expected_token'] == '0.557763'
    assert op['observations'][0]['tolerance'] == .0000005
    assert op['model_path'] is None and op['blocker_code'] == 'UNPAIRED_REFERENCE'


def test_aerodynamic_normalization_keeps_total_wrench_separate():
    condition = dict(alpha=0., density=2., speed=10.)
    result = dict(distributed_aero_force=[3.,4.,5.], distributed_aero_moment=[7.,8.,9.],
        force=[-27.,14.,25.], moment=[17.,18.,19.], CDi=.08, efficiency=3.2)
    values = ap1.header_values(result, condition)
    qs = 100*.1536
    assert values['sum Fx'] == -27. and values['sum My'] == 18.
    assert values['Lift'] == 5. and values['avg CL'] == pytest.approx(5/qs)
    assert values['avg CD'] == pytest.approx(3/qs)
    assert values['avg Cm'] == pytest.approx(8/(qs*.24))
    assert values['avg CDi'] == .08 and values['Span Eff'] == 3.2 and values['L/D'] == pytest.approx(5/3)
    rotated = ap1.header_values(result, dict(condition, alpha=90.))
    assert rotated['Lift'] == pytest.approx(-3.) and rotated['avg CD'] == pytest.approx(5/qs)


def test_independent_strip_and_engine_wrenches_apply_each_arm_once():
    snapshot = dict(strips=[dict(position=[1.,3.,0.],force=[2.,0.,5.],moment=[0.,1.,0.])],
        engines=[dict(position=[-1.,1.,2.],force=[-4.,0.,0.],moment=[3.,0.,0.])])
    result = ap1.reconstruct_wrenches(snapshot,[1.,1.,0.])
    assert result['distributed_aero_force'] == [2.,0.,5.]
    assert result['distributed_aero_moment'] == [10.,1.,-4.]
    assert result['engine_force'] == [-4.,0.,0.]
    assert result['engine_moment'] == [3.,-8.,0.]
    assert result['force'] == [-2.,0.,5.]
    assert result['moment'] == [13.,-7.,-4.]


def test_blocked_validation_imports_no_physics_and_retains_every_slot(jobs, monkeypatch):
    original = builtins.__import__
    def no_physics(name, *args, **kwargs):
        if name.split('.')[0] in ('openswing','numpy','scipy'):
            pytest.fail('Blocked AP1 imported numerical/production package: '+name)
        return original(name,*args,**kwargs)
    monkeypatch.setattr(builtins, '__import__', no_physics)
    monkeypatch.setattr(ap1, 'build_jobs', lambda *a:pytest.fail('Blocked validation rebuilt the family'))
    for job in jobs:
        if job['execution_route'] != 'unsupported':
            continue
        result = ap1.run(ROOT, job)
        assert result['status'] == 'unsupported' and result['source_pins_unchanged']
        assert result['operations'] == dict(cold_solves=0,fresh_residuals=0,retries=0)
        assert result['physical_calls'] == result['production_imports'] == 0
        assert not result['reference_match'] and not result['numerical_pass']
        assert len(result['reference_checks']) == job['expected_outputs']
        contract = ap1.reference_contract(job)
        for check in result['reference_checks']:
            assert check['predicted'] is None and check['passed'] is False and check['comparison'] == '<='
            assert all(check[k] == v for k,v in contract[check['name']].items())


@pytest.mark.parametrize('mutation', ['expected','precision','raw_token','coordinate','row_loss','count','route','power','driver','model','mesh'])
def test_tampered_targets_source_pairs_and_settings_are_rejected(jobs, mutation):
    kind = 'header' if mutation in ('power','driver','model','mesh') else 'span'
    job = deepcopy(selected(jobs, f'AP-1-PROWINA4-{kind}-m150'))
    if mutation == 'expected':job['observations'][0]['expected'] += 1
    elif mutation == 'precision':job['observations'][0]['tolerance'] *= 10
    elif mutation == 'raw_token':job['reference_rows'][0]['tokens'][0] = '0.0'
    elif mutation == 'coordinate':job['observations'][0]['coordinate_token'] = '0.0'
    elif mutation == 'row_loss':job['reference_rows'].pop()
    elif mutation == 'count':job['expected_outputs'] -= 1
    elif mutation == 'route':job['execution_route'] = 'worker'
    elif mutation == 'power':job['condition']['powers'] = {'1':500.,'2':333.}
    elif mutation == 'driver':job['driver_path'] = job['driver_path'].replace('PROWIM.sh','PROWIM_d.sh')
    elif mutation == 'model':job['model_path'] = job['model_path'].replace('PROWIM.asw','PROWIMd.asw')
    elif mutation == 'mesh':job['panels'] = 151
    with pytest.raises(ValueError, match='AP1'):
        ap1.verify_reference_sources(ROOT, job)


def test_changed_or_removed_pin_is_not_an_unsupported_success(jobs):
    for remove in (True,False):
        job = deepcopy(selected(jobs,'AP-1-PROWINA4-span-m150'))
        if remove:job['source_pins'].pop()
        else:job['source_pins'][0]['sha256'] = '0'*64
        result = ap1.validate_blocked(ROOT,job)
        assert result['status'] == 'source_mismatch' and not result['source_pins_unchanged']
        assert result['physical_calls'] == 0 and not result['reference_match']


def test_mesh_diagnostic_is_descriptive_and_handles_empty_subset_unrun(jobs):
    job = selected(jobs)
    assert ap1.mesh_diagnostics([], {}) == []
    subset = ap1.mesh_diagnostics([job], {})
    assert subset[0]['status'] == 'UNAVAILABLE' and subset[0]['passed'] is None
    assert len(ap1.mesh_diagnostics(jobs,{})) == 3
    pair = [selected(jobs,f'AP-1-PROWINA4-header-m{n}') for n in (150,300)]
    results = {j['id']:dict(status='computed',reference_checks=ap1._checks(j,{n:float(i+1) for i,n in enumerate(ap1.HEADER_NAMES)})) for j in pair}
    diag = ap1.mesh_diagnostics(pair,results)[0]
    assert diag['status'] == 'COMPARED' and diag['passed'] is None and diag['acceptance_gate'] is None
    assert all(c['abs_change'] == 0 for c in diag['channels'].values())


def test_worker_adapter_preserves_physical_and_reference_results_without_solving(jobs,monkeypatch,tmp_path):
    job = selected(jobs)
    def fake_execute(root, canonical, stage):
        ap1._write(stage/'operations.json',dict(cold_solves=1,fresh_residuals=1,retries=0))
        # Deliberately preserve an archived discrepancy despite physical success.
        return {o['name']:o['expected']+1 for o in canonical['observations']}, physical_fixture()
    monkeypatch.setattr(ap1,'_execute',fake_execute)
    monkeypatch.setattr(ap1.tempfile,'mkdtemp',lambda **kwargs:str(tmp_path))
    result = ap1.run(ROOT,job)
    assert result['status'] == 'computed' and result['numerical_pass'] and not result['reference_match']
    assert result['operations'] == job['expected_operations'] and result['physical_calls'] == 2
    assert result['source_pins_unchanged'] and result['kernel_pins_unchanged']
    assert all(not c['passed'] for c in result['reference_checks'])
    assert (tmp_path/'adapter-result.json').exists()


@pytest.mark.parametrize('mutation',['missing','duplicate','gate','false_pass','vectors','balance','restored','expectation'])
def test_physical_evidence_requires_complete_set_and_recomputed_metrics(jobs,mutation):
    job = selected(jobs)
    checks = physical_fixture()
    assert ap1.validate_physical_checks(job,checks)
    by_name = {c['name']:c for c in checks}
    if mutation == 'missing':checks.pop()
    elif mutation == 'duplicate':checks[-1] = deepcopy(checks[0])
    elif mutation == 'gate':by_name['fresh_full_residual']['gate'] *= 10
    elif mutation == 'false_pass':by_name['fresh_full_residual']['maximum'] = 1.
    elif mutation == 'vectors':by_name['independent_force']['reconstructed'][0] = 1.
    elif mutation == 'balance':by_name['force_balance']['applied'][0] = 1.
    elif mutation == 'restored':by_name['restored_header_parity']['restored']['Lift'] = 1.
    elif mutation == 'expectation':by_name['one_restored_residual'].update(actual=0,expected=0)
    with pytest.raises(ValueError,match='AP1'):
        ap1.validate_physical_checks(job,checks)
