"""Source-only ST2 worker contracts; fixtures are not physical modal results."""
from copy import deepcopy
import importlib.util
import json
import math
from pathlib import Path
import subprocess
import sys

import pytest

ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location('st2_modal_contract_helper',ROOT/'scripts/isae_suite_st2_modal.py')
helper=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(helper)


@pytest.fixture(scope='module')
def jobs():
    from scripts.isae_suite_st2 import plan
    return [j for j in plan(ROOT) if j['execution_route']=='worker']


@pytest.fixture
def job(jobs):
    return deepcopy(jobs[0])


def physical_fixture(job, values=None):
    """Fully bound synthetic evidence, without a model import or matrix assembly.

    Optional values maps row0001:real / :imaginary through row0007. It changes
    both positive and conjugate roots, then rebuilds all root-derived evidence.
    """
    positives=[[1e-13*(i+1),float(i+1)] for i in range(10)]
    if values is not None:
        positives[:7]=[[values[f'row{i:04d}:real'],values[f'row{i:04d}:imaginary']] for i in range(1,8)]
        top=max(x[1] for x in positives[:7])
        positives[7:]=[[1e-13*(i+1),top+100.*(i-6)] for i in range(7,10)]
    roots=[]
    for i in [3,1,8,0,9,2,5,4,7,6]:
        a,b=positives[i];roots.extend([[a,-b],[a,b]])
    evidence=helper.spectrum_evidence(roots)
    dimension=18*job['expected_nodes'];expected=helper._expectations(job,dimension)
    identity=dict(model_sha256=job['literal_model_sha256'],structural_operator=job['settings']['structural_operator'],
        beam_interpolation='drela-segspl-v1',circulation_count=0,nodes=[[0.,0.,0.]]*job['expected_nodes'],
        elements=[[0,1]]*job['expected_elements'])
    if job['density'] is not None:identity['quiescent_density']=job['density']
    position=[-.005,.2,0.];force=[job['expected_real_mass']*g for g in job['gravity']];moment=helper._cross(position,force)
    fields=dict(positions=[0.,0.,0.],rotations=[1.,0.,0.,0.,1.,0.,0.,0.,1.],applied_force=force,
        applied_moment=moment,support_force=[-x for x in force],support_moment=[-x for x in moment],sensor_positions=[0.,0.,.55])
    checks=[]
    for name,spec in helper.PHYSICAL_CHECK_SPECS.items():
        kind=spec['kind']
        if kind=='exact':
            value=identity if name=='same_operator_identity' else deepcopy(expected[name])
            checks.append(dict(name=name,actual=value,expected=deepcopy(value),passed=True));continue
        if kind=='spectrum':
            checks.append(dict(name=name,evidence=deepcopy(evidence),passed=True));continue
        row=dict(name=name,metric=0.,gate=spec.get('fixed_gate',helper.GATES.get(spec.get('gate'))),passed=True)
        if kind=='maximum':row['values']=[0.]
        elif kind=='balance':
            applied=force if name=='force_balance' else moment
            row.update(applied=applied,support=[-x for x in applied])
        elif kind=='clamp':
            v=job['root_position'] if name.endswith('position') else [1.,0.,0.,0.,1.,0.,0.,0.,1.]
            row.update(reported=list(v),expected=list(v))
        elif kind=='mass':
            row.update(endpoint_masses=[job['expected_real_mass']],reconstructed=job['expected_real_mass'],
                reported=job['expected_real_mass'],expected=job['expected_real_mass'])
        elif kind=='gravity':
            row.update(samples=[dict(mass=job['expected_real_mass'],position=position)],reconstructed_force=force,
                reconstructed_moment=moment,reported_force=force,reported_moment=moment)
        elif kind=='parity':
            row.update(reported=deepcopy(fields),restored=deepcopy(fields),channels={k:0. for k in fields})
        elif kind=='pencil':
            entries=[]
            for i,root in enumerate(roots):
                denominator=1.+abs(complex(*root))
                entries.append(dict(index=i,eigenvalue=root,residual_norm=1e-16,vector_norm=1.,A_norm=1.,M_norm=1.,
                    denominator=denominator,backward_error=1e-16/denominator,reported_backward_error=0.))
            row.update(entries=entries,metric=max(e['backward_error'] for e in entries))
        elif kind=='pairing':row['entries']=[dict(index=i,value=[1.,0.],error=0.,normalized=True) for i in range(20)]
        elif kind=='neutral':row.update(eigenvalues=roots,metric=max(abs(a)/max(1.,abs(b)) for a,b in roots))
        checks.append(row)
    byname={x['name']:x for x in checks}
    evidence['pencil_checks']=dict(right=deepcopy(byname['modal_right_pencil']['entries']),
        left=deepcopy(byname['modal_left_pencil']['entries']),mass_pairing=deepcopy(byname['modal_mass_pairing']['entries']))
    evidence['mass_pairing_matrix']=dict(real=[[float(i==j) for j in range(20)] for i in range(20)],
        imag=[[0.]*20 for _ in range(20)],scope='Synthetic diagonal normalization only; not solved.')
    return checks,evidence,evidence['values']


def computed_fixture(job, values=None):
    from scripts import isae_suite_st2
    physical,evidence,values=physical_fixture(job,values)
    checks=isae_suite_st2._reference_checks(job,values)
    return dict(id=job['id'],case_id='ST-2',adapter='st2',status='computed',numerical_pass=True,
        reference_match=all(c['passed'] for c in checks),reference_checks=checks,physical_checks=physical,
        modal_evidence=evidence,operations=deepcopy(helper.OPERATIONS),physical_calls=2,
        source_pins_unchanged=True,kernel_pins_unchanged=True,complete_family_reproduction=False,
        historical_settings_recovered=False,error=None)


def test_import_has_no_production_or_array_dependency():
    code='''import builtins,importlib.util
real=builtins.__import__
def guard(name,*args,**kwargs):
    assert not name.startswith(('openswing','numpy','scipy')),name
    return real(name,*args,**kwargs)
builtins.__import__=guard
spec=importlib.util.spec_from_file_location('check_helper','scripts/isae_suite_st2_modal.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
assert len(module.REQUIRED_PHYSICAL_CHECKS)==35
'''
    subprocess.run([sys.executable,'-c',code],cwd=ROOT,check=True,capture_output=True,text=True)


def test_eight_predeclared_jobs_share_immutable_contract(jobs):
    assert len(jobs)==8
    assert {(j['nominal'],j['medium']) for j in jobs}=={(40,'vacuum'),(40,'still_air'),(80,'vacuum'),(80,'still_air')}
    assert sum(j['expected_outputs'] for j in jobs)==112
    for j in jobs:
        assert helper._job_contract(j)==j['settings']
        checks,evidence,values=physical_fixture(j)
        assert helper.validate_physical_checks(j,checks)
        assert helper.validate_modal_evidence(j,evidence)==values


def test_ordinal_selection_uses_imaginary_order_not_return_order_or_targets(job):
    checks,evidence,values=physical_fixture(job)
    assert evidence['selected_indices']==[7,3,11,1,15,13,19]
    assert [values[f'row{i:04d}:imaginary'] for i in range(1,8)]==list(range(1,8))
    assert values['row0001:real']==1e-13
    assert len(evidence['eigenvalues'])==20 and len(evidence['positive_indices'])==10
    assert len({w['candidates'][0]['index'] for w in evidence['conjugate_witnesses']})==7
    assert helper.validate_modal_evidence(job,evidence)==values


@pytest.mark.parametrize('fault',['order','selected','values','conjugate','zero_snap','duplicate'])
def test_root_evidence_tampering_is_rejected(job,fault):
    _,evidence,_=physical_fixture(job)
    if fault=='order':evidence['positive_indices'].reverse()
    elif fault=='selected':evidence['selected_indices'][0]=evidence['selected_indices'][-1]
    elif fault=='values':evidence['values']['row0001:real']=0.
    elif fault=='conjugate':evidence['conjugate_witnesses'][0]['candidates'][0]['absolute_error']=1.
    elif fault=='zero_snap':evidence['eigenvalues'][0][0]=0.
    else:evidence['eigenvalues'][0]=evidence['eigenvalues'][1]
    with pytest.raises(ValueError):helper.validate_modal_evidence(job,evidence)


@pytest.mark.parametrize('fault',['missing_positive','missing_witness','duplicate_root'])
def test_incomplete_or_ambiguous_local_spectrum_cannot_pass(job,fault):
    _,old,_=physical_fixture(job);roots=deepcopy(old['eigenvalues'])
    if fault=='missing_positive':
        for i in old['positive_indices'][6:]:roots[i][1]=0.
    elif fault=='missing_witness':roots[old['conjugate_witnesses'][0]['candidates'][0]['index']][1]-=.5
    else:roots[-1]=list(roots[0])
    evidence=helper.spectrum_evidence(roots)
    with pytest.raises(ValueError):helper.validate_modal_evidence(job,evidence)


@pytest.mark.parametrize('fault',['missing','duplicate','unknown','gate','protocol','dimension','mass','gravity','balance',
    'pencil_norm','pencil_error','pairing','neutral','restore_counter','metric_nan','physical_boolean'])
def test_physical_contract_recomputes_saved_evidence(job,fault):
    checks,_,_=physical_fixture(job);rows={r['name']:r for r in checks}
    if fault=='missing':checks.pop()
    elif fault=='duplicate':checks[-1]=deepcopy(checks[0])
    elif fault=='unknown':checks[-1]['name']='unknown'
    elif fault=='gate':rows['fresh_full_residual']['gate']=1.
    elif fault=='protocol':job['modal_protocol']['count']=16
    elif fault=='dimension':rows['full_matrix_shape']['expected']['A'][0]+=1
    elif fault=='mass':rows['independent_real_mass']['reconstructed']+=.1
    elif fault=='gravity':rows['independent_gravity_wrench']['samples'][0]['position'][0]+=.1
    elif fault=='balance':rows['force_balance']['applied']=[0.,0.,-1.]
    elif fault=='pencil_norm':rows['modal_right_pencil']['entries'][0]['denominator']*=2.
    elif fault=='pencil_error':rows['modal_left_pencil']['entries'][0]['residual_norm']=1.
    elif fault=='pairing':rows['modal_mass_pairing']['entries'][0]['value']=[2.,0.]
    elif fault=='neutral':rows['modal_neutrality']['eigenvalues'][0][0]=1.
    elif fault=='restore_counter':rows['restore_without_evaluation']['actual']=1
    elif fault=='metric_nan':rows['base_residual']['metric']=math.nan
    else:rows['fresh_full_residual']['passed']=False
    with pytest.raises(ValueError):helper.validate_physical_checks(job,checks)


def test_validly_recorded_physical_failure_is_not_promoted(job):
    checks,_,_=physical_fixture(job)
    row=next(r for r in checks if r['name']=='base_residual')
    row.update(values=[1e-5],metric=1e-5,passed=False)
    assert helper.validate_physical_checks(job,checks) is False


def test_fixture_propagates_optional_complex_components(job):
    values={f'row{i:04d}:{part}':float(i*100) if part=='imaginary' else -i*1e-12
        for i in range(1,8) for part in ['real','imaginary']}
    checks,evidence,actual=physical_fixture(job,values)
    assert actual==values
    assert helper.validate_modal_evidence(job,evidence)==values
    assert helper.validate_physical_checks(job,checks)


def test_computed_fixture_binds_all_original_components_to_adapter(job):
    from scripts import isae_suite_st2
    values={name:cell['expected'] for name,cell in isae_suite_st2.reference_contract(job).items()}
    result=computed_fixture(job,values)
    assert isae_suite_st2.validate_result_contract(job,result)
    assert result['reference_match'] is True
    assert len(result['reference_checks'])==14
    assert all(check['passed'] for check in result['reference_checks'])
