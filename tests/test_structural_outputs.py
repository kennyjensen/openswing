"""Physical section C, independent nonlinear references and reuse boundaries."""
from pathlib import Path
import numpy as np
import pytest
from scipy.spatial.transform import Rotation
from openswing.asw import parse_asw
from openswing.network import StaticNetwork
from openswing.linear_dynamics import DynamicSystem,output_perturbation
from openswing.structural_outputs import StructuralOutputTangent,StructuralOutputUnavailable,structural_outputs
from test_network import model,beam
from structural_output_reference import high_precision_sections

CASES=['offset','axis_jump','curved','missing','zero_shell','invalid_area','damped','mixed_units']

def system_for(name):
    source=beam(stiffness='100 200 80 1000 900 700')
    if name=='axis_jump':source=source.replace('2 0 2 0','1 .1 1 .2 100 200 80 1000 900 700\n1 .3 1 .4 100 200 80 1000 900 700\n2 .6 2 .5')
    if name=='curved':source=source.replace('2 0 2 0','1 .3 1 .5 100 200 80 1000 900 700\n2 .7 2 1.5')
    offsets='t Cta Nta Cea Nea EIcs EIcn EIsn\n0 .3 -.2 -.1 .07 8 -13 9\n2 .3 -.2 -.1 .07 8 -13 9\n'
    shell='' if name=='missing' else 't Cshell Nshell Atshell\n0 .2 .1 .003\n2 .2 .1 .003\n'
    if name=='zero_shell':shell=shell.replace('.2 .1 .003','0 0 .003')
    if name=='invalid_area':shell=shell.replace('.003','-1')
    damping='t tdeps tdgam\n0 .02 .03\n2 .02 .03\n' if name=='damped' else ''
    configuration=model(source.replace('End',offsets+shell+damping+'End'))
    if name=='mixed_units':
        configuration=parse_asw(configuration.dumps().replace('L 1 m','L .3048 ft').replace('T 1 s','T .01 cs').replace('F 1 N','F 4.4482216152605 lbf'))
    n=StaticNetwork(configuration,4,None,[0,0,0],[])
    if name=='damped':assert np.max(n.damping_times)>0
    x=np.random.default_rng(937).normal(0,.02,n.size)
    x[:6*n.nn].reshape(n.nn,6)[:,3:]+=[.7,-.3,.6]
    return DynamicSystem(n,x,'free')


def snapshots(system,vector,rate=None,step=1e-5):
    rate=.7j*vector if rate is None else rate
    return [system.snapshot(sign*step*part(vector),sign*step*part(rate))[1]
        for part in (np.real,np.imag) for sign in (1,-1)]


def snapshot_values(snapshot):
    result=[]
    for e in snapshot['elements']:
        result.append([*e['force_local'],*e['moment_local'],*e['strain'],*e['curvature_change'],
            e['axial_strain_tension'],e['shell']['axial_strain'] or 0.,e['shell']['shear_stress'] or 0.])
    return np.array(result)


@pytest.mark.parametrize('name',CASES)
def test_full_section_matrix_matches_independent_80_digit_physical_values(name):
    s=system_for(name);rng=np.random.default_rng(578);v=rng.normal(size=s.size)+1j*rng.normal(size=s.size)
    tangent=StructuralOutputTangent(s);actual=(tangent.matrix@v).reshape(s.network.ne,15)
    expected=high_precision_sections(s,v);refined=high_precision_sections(s,v,'1e-24')
    assert np.max(abs(actual-expected)/(1+abs(expected)))<2e-11
    assert np.max(abs(expected-refined)/(1+abs(refined)))<1e-18
    p,m,pi,mi=map(snapshot_values,snapshots(s,v))
    numerical=((p-m)+1j*(pi-mi))/(2e-5)
    assert np.max(abs(actual-numerical)/(1+abs(actual)))<2e-7
    values=tangent.apply(v,1e-5,snapshots(s,v))
    assert all((e['shell_strain'] is None)==(name=='missing') for e in values)
    assert all((e['shell_shear_stress'] is None)==(name in ['missing','invalid_area']) for e in values)
    # No circulation, rigid-frame, local-rate or controller column enters C.
    assert tangent.matrix[:,6*(s.network.nn+s.network.ne):].nnz==0


def test_reuse_is_owned_immutable_and_tracks_every_physical_context():
    s=system_for('offset');v=np.ones(s.size,complex);snaps=snapshots(s,v)
    before=structural_outputs(s,v,1e-5,snaps);first=s._structural_output_tangent
    assert structural_outputs(s,2*v,1e-5,snaps) is not None
    assert s._structural_output_tangent is first and not first.matches(system_for('offset'))
    assert all(not a.flags.writeable for a in [first.matrix.data,first.matrix.indices,first.matrix.indptr])
    for array,index in [(s.r0,(0,0)),(s.Q0,(0,0,0)),(s.network.offa,(0,0)),(s.network.R0a,(0,0,0)),
                        (s.network.offb,(0,0)),(s.network.R0b,(0,0,0)),(s.network.ds,0),(s.base,6*s.network.nn)]:
        original=array[index];array[index]+=.1
        try:assert not first.matches(s)
        finally:array[index]=original
    section=s.network.sections[0]
    for name in ['Cta','Nta','Cea','Nea']:
        old=getattr(section,name);setattr(section,name,old+.1)
        try:assert not first.matches(s)
        finally:setattr(section,name,old)
    dist=s.network.model.beams[0].distributions.pop('Cshell')
    try:assert not first.matches(s)
    finally:s.network.model.beams[0].distributions['Cshell']=dist
    from openswing.asw import Distribution
    beam=s.network.model.beams[0]
    for key in ['Cshell','Nshell','Atshell']:
        old=beam.distributions[key]
        beam.distributions[key]=Distribution(key,old.t,old.values*1.2,old.line)
        try:assert not first.matches(s)
        finally:beam.distributions[key]=old
    assert first.matches(s)
    after=structural_outputs(s,v,1e-5,snaps)
    for a,b in zip(before,after):
        for key in a:np.testing.assert_array_equal(a[key],b[key])


def test_budget_nonfinite_strain_law_and_rotation_branch_fallbacks():
    s=system_for('offset');v=np.ones(s.size,complex);snaps=snapshots(s,v)
    with pytest.raises(StructuralOutputUnavailable,match='budget'):StructuralOutputTangent(s,limit=1)
    s.base[6*s.network.nn]=np.nan
    assert structural_outputs(s,v,1e-5,snaps) is None
    assert 'Nonfinite' in s.structural_output_diagnostics['fallback']
    s=system_for('offset');t=StructuralOutputTangent(s);snaps=snapshots(s,v)
    snaps[0]['structure']['strain_source']='elastic_load_compliance'
    with pytest.raises(StructuralOutputUnavailable,match='recovery law'):t.apply(v,1e-5,snaps)
    with pytest.raises(StructuralOutputUnavailable,match='branch'):t.apply(v,1.,snapshots(s,np.zeros(s.size)))


def test_public_section_outputs_are_linear_and_preserve_geometric_damping_strain():
    s=system_for('damped');rng=np.random.default_rng(192);v=rng.normal(size=s.size)+1j*rng.normal(size=s.size)
    expected=high_precision_sections(s,v)
    keys=[('force_local',slice(0,3)),('moment_local',slice(3,6)),('strain',slice(6,9)),('curvature_change',slice(9,12)),
          ('axial_strain_tension',12),('shell_strain',13),('shell_shear_stress',14)]
    for amplitude in [1e-12,1.,1e12]:
        out=output_perturbation(s,amplitude*v,37j*amplitude*v)
        for e,section in enumerate(out['sections']):
            for name,index in keys:
                got=(np.asarray(section[name]['real'])+1j*np.asarray(section[name]['imag']))/amplitude
                assert np.max(abs(got-expected[e,index])/(1+abs(expected[e,index])))<2e-11
        assert s.structural_output_diagnostics['fallback'] is None


def test_prescribed_rates_and_aerodynamic_inputs_have_zero_explicit_section_partials():
    from openswing.aero import FlightCondition
    from openswing.frequency_response import HarmonicInput
    n=StaticNetwork(parse_asw(Path('examples/rectangular.asw').read_text()),4,FlightCondition(speed=20,alpha=3),None,[])
    s=DynamicSystem(n,np.zeros(n.size),'fixed');zero=np.zeros(s.size);rates=np.random.default_rng(145).normal(size=s.size)
    channel=HarmonicInput(s,'control.1',0);forcing,_=channel.at_frequency(.8)
    out=output_perturbation(s,zero,rates,forcing=forcing,input_scale=channel.scale)
    assert s.structural_output_diagnostics['rate_and_input_terms']=='zero'
    for section in out['sections']:
        for key in ['force_local','moment_local','strain','curvature_change','axial_strain_tension','shell_strain','shell_shear_stress']:
            if section[key] is not None:
                np.testing.assert_array_equal(section[key]['real'],np.zeros_like(section[key]['real']))
                np.testing.assert_array_equal(section[key]['imag'],np.zeros_like(section[key]['imag']))
