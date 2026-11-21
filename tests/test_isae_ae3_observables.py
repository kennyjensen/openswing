"""Native export conventions and independently checked auxiliary evidence."""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import isae_suite_ae3 as adapter


def test_nonzero_normalized_rates_use_body_and_base_stability_axes():
    from scripts.isae_ae3_observables import normalized_rates
    values=normalized_rates(SimpleNamespace(speed=10,alpha=90,rates=[2.,3.,5.]),chord=2,span=4)
    assert values==pytest.approx(dict(body_Wx_b_2V=.4,body_Wy_c_2V=.3,body_Wz_b_2V=1.,
        stability_p_b_2V=-1.,stability_q_c_2V=.3,stability_r_b_2V=.4),abs=1e-15)


def test_zero_real_mass_and_rectangular_surface_apparent_integrals():
    import numpy as np
    from scripts.isae_ae3_observables import mass_outputs
    # Prescribed physical panels isolate tensor reporting from the parser and
    # mesher, both independently checked by the native-case worker.
    beam=SimpleNamespace(index=1,lifting=True,
        value=lambda key,t:np.full_like(np.asarray(t,dtype=float),{'chord':2.,'Xax':.5}.get(key,0.)))
    model=SimpleNamespace(beams=[beam])
    mesh=SimpleNamespace(beam=beam,tm=np.array([-.5,.5]),rm=np.array([[0.,-.5,0.],[0.,.5,0.]]),
        length=np.ones(2),frames=np.tile(np.eye(3),(2,1,1)))
    network=SimpleNamespace(model=model,station_nodes={1:(np.array([-1.,0.,1.]),)},
        condition=SimpleNamespace(body_added_mass_factor=1.))
    record=dict(mass=np.zeros(2),inertia=np.zeros((2,3,3)),spin=np.zeros((2,3)))
    data=dict(masses=[record],meshes=[mesh],aero=dict(atmosphere=dict(density=1.)))
    values,report=mass_outputs(network,data)
    assert len(values)==42 and report['physical_real_centroid'] is None
    # Two midpoint panels, c=2, ds=1: each normal apparent mass is pi.
    assert values['apparent_mass_zz']==pytest.approx(2*np.pi)
    assert values['apparent_mass_xx']==values['apparent_mass_yy']==0.
    assert values['apparent_inertia_origin_xx']==pytest.approx(np.pi/2)
    assert values['apparent_inertia_origin_yy']==pytest.approx(np.pi/4)
    assert values['apparent_inertia_origin_zz']==0.
    assert all(values[k]==0 for k in values if k.startswith(('real_','mass_centroid','center_of_mass','jig_center')))
    record['mass'][0]=1.
    with pytest.raises(ValueError,match='zero physical'):mass_outputs(network,data)


@pytest.fixture(scope='module')
def auxiliary_jobs():
    root=Path(__file__).resolve().parents[1]
    return {j['target_kind']:j for j in adapter.plan(root) if j.get('native_operating_point')==1
            and j['target_kind']!='native_coefficients'}


def report_fixture(job):
    """Synthetic tensor/response evidence; never counted as a physical solve."""
    derivative=job['target_kind']=='native_derivatives';g=adapter.OBSERVABLE_GATES
    gates={name:g['operator_parity'] for name in ('base_operator_parity','base_output_parity',
        'off_state_operator_parity_0','off_state_operator_parity_1')}
    gates.update(base_residual=g['base_residual'],apparent_mass_acceleration_recovery=g['mass_recovery'])
    if derivative:
        gates.update(reciprocal_condition_gate=1.,analytic_control_partial=g['input_refinement'])
        gates.update({f'full_tangent_direction_{i}':g['directional_tangent'] for i in range(2)})
        gates.update({group+'_'+p:g[group] for group in ('input_refinement','linear_residual','output_refinement')
                      for p in adapter.OBSERVABLE_PARAMETERS})
    matrix=[[v if i==j else 0. for j in range(6)] for i,v in enumerate((0.,0.,2.,3.,5.,0.))]
    values={f'{prefix}_{a}':0. for prefix in ('mass_centroid','center_of_mass','jig_center_of_mass') for a in 'xyz'}
    values.update({'real_mass_'+a:0. for a in ('xx','yy','zz')})
    for a,v in zip(('xx','xy','xz','yy','yz','zz'),(0.,0.,0.,0.,0.,2.)):values['apparent_mass_'+a]=v
    for about in ('origin','centroid'):
        for a,v in zip(('xx','xy','xz','yy','yz','zz'),(3.,0.,0.,5.,0.,0.)):
            values[f'real_inertia_{about}_{a}']=0.;values[f'apparent_inertia_{about}_{a}']=v
    values.update({k:0. for k in ('body_Wx_b_2V','body_Wy_c_2V','body_Wz_b_2V',
        'stability_p_b_2V','stability_q_c_2V','stability_r_b_2V')})
    report=dict(source_operator='drela-moving-airflow-v1',base_operator=adapter.POLICY['structural_operator'],
        base_coefficients={name:0. for name in adapter.NAMES},numerical_gates=deepcopy(g),
        checks=[dict(name=name,metric=g['reciprocal_condition'] if name=='reciprocal_condition_gate' else 0.,
                     gate=gate,passed=True) for name,gate in gates.items()],
        factorization_count=int(derivative),response_columns=7 if derivative else 0,
        mass_properties=dict(zero_real_mass_verified=True,physical_real_centroid=None,origin=[0.,0.,0.],
            reported_real_centroid=[0.,0.,0.],apparent_reference=[0.,0.,0.],
            real_record_maxima=[dict(mass=0.,inertia=0.,spin=0.)],apparent_spatial_matrix=matrix,
            acceleration_recovered_apparent_spatial_matrix=deepcopy(matrix)),values=values)
    if derivative:
        matrix=[[float(7*i+j) for j in range(7)] for i in range(6)]
        values.update({name+suffix:matrix[i][j] for i,name in enumerate(adapter.NAMES)
                       for j,suffix in enumerate(('u','a','b','p','q','r','dF1'))})
        c=job['condition']
        report.update(parameters=list(adapter.OBSERVABLE_PARAMETERS),coefficient_rows=list(adapter.NAMES),
            response='fixed_acceleration',axes='stability',reciprocal_condition=1.,coefficient_derivatives=matrix,
            normalization=dict(qS=.5*c['density']*c['speed']**2*.185,chord=.15,span=1.2192,
                axes='fixed base stability axes',angles='radians',rates='p b/2V, q c/2V, r b/2V',control='file F1 units'))
    return report


@pytest.mark.parametrize('kind',['native_derivatives','native_mass_properties','native_normalized_rates'])
def test_complete_auxiliary_contract_accepts_independently_mapped_evidence(auxiliary_jobs,kind):
    job=auxiliary_jobs[kind];report=report_fixture(job)
    assert adapter.validate_observable_report(job,report,report['base_coefficients'])


@pytest.mark.parametrize('fault',['derivative_sign','mass_entry','rate_scale','missing_check','recovery',
    'normalization','rank','factor_reuse','real_mass','cg','nonfinite'])
def test_auxiliary_contract_rejects_mapping_or_numerical_evidence_changes(auxiliary_jobs,fault):
    job=auxiliary_jobs['native_derivatives'];report=report_fixture(job)
    if fault=='derivative_sign':report['values']['CldF1']*=-1
    if fault=='mass_entry':report['values']['apparent_inertia_centroid_yy']+=1
    if fault=='rate_scale':report['values']['stability_r_b_2V']=1
    if fault=='missing_check':report['checks'].pop()
    if fault=='recovery':report['mass_properties']['acceleration_recovered_apparent_spatial_matrix'][2][2]+=1
    if fault=='normalization':report['normalization']['angles']='degrees'
    if fault=='rank':report['reciprocal_condition']=1e-14
    if fault=='factor_reuse':report['factorization_count']=7
    if fault=='real_mass':report['mass_properties']['real_record_maxima'][0]['inertia']=1
    if fault=='cg':report['mass_properties']['physical_real_centroid']=[0.,0.,0.]
    if fault=='nonfinite':report['coefficient_derivatives'][0][0]=float('nan')
    with pytest.raises(ValueError):adapter.validate_observable_report(job,report,report['base_coefficients'])
