"""Annotated ROM exchange against independent mechanical transfer functions."""
from copy import deepcopy
import json
import re
from pathlib import Path
import numpy as np
import pytest
from openswing.aero import AnalysisError,FlightCondition
from openswing.asw import parse_asw,UnitSystem
from openswing.bridge import run_json
from openswing.rom_file import parse_rom,write_rom,real_rom,rom_response,export_rom,array
from openswing.reduced_model import solve_reduced_model


def mechanical_text():
    # Independently specified residues of 2 ydd+10 yd+500 y=u1-.3u2,
    # zdot+4z=2u2. Outputs [y+.1u2,yd,ydd,z]. Positive pole only.
    pole=complex(-2.5,np.sqrt(250-2.5**2));b=-1j/(4*pole.imag)
    names=['q pos [1]','v rate [1]','a acceleration [1]','filter value [1]']
    units=['m','m/s','m/s^2','custom']
    text='# Original two-input mechanical ROM\n# Op.Point : 7\n'
    def pair(x):return f'{x.real:.17e} {x.imag:.17e}'
    for index,root,inputs,outputs,states in [(3,pole,[b,-.3*b],[1,pole,pole*pole,0],[1,pole,0]),
                                          (8,-4,[0,2],[0,0,0,1],[0,0,1])]:
        text+=f'# Mode: {index}\n# Eigenvalue: {pair(root)} 1/s\n# Eigenvector...\n# Real(x) Imag(x)\n'
        for name,value in zip(['q','v','z'],states):text+=f'{pair(value)} {name}\n'
        text+=f'# Control variable influence-matrix row {index}\n# Real(w*B) Imag(w*B)\n'
        for name,value in zip(['Flap_01','Peng_02'],inputs):text+=f'{pair(value)} 1 / s = d(zdot {index}) / d({name})\n'
        text+=f'# Output variable dependence-matrix column {index}\n# Real(Cv+Qvl) Imag(Cv+Qvl)\n'
        for name,unit,value in zip(names,units,outputs):text+=f'{pair(value)} {unit} = d( {name} ) / d(z {index})\n'
    text+='# Output-variable dependence-matrix D + QVW*B\n'
    for input,values in [('Flap_01',[0,0,.5,0]),('Peng_02',[.1,0,-.15,0])]:
        text+=f'# Column for forcing variable: {input}\n# Real(D+QVW*B) Imag(D+QVW*B)\n'
        for name,unit,value in zip(names,units,values):text+=f'{pair(value)} {unit} = d( {name} ) / d({input})\n'
    return text


def test_positive_complex_representative_and_real_pole_match_independent_mimo_physics():
    text=mechanical_text();model=parse_rom(text);out=rom_response(model,[0,.1,2,15,30,100])
    assert [m['index'] for m in model['modes']]==[3,8]
    assert len(out['real_matrices']['A'])==3 and out['converged']
    assert model['inputs'][0]['unit'] is None
    for sample in out['samples']:
        s=1j*sample['omega'];h=1/(2*s*s+10*s+500)
        expected=np.array([[h,.1-.3*h],[s*h,-.3*s*h],[s*s*h,-.3*s*s*h],[0,2/(s+4)]])
        np.testing.assert_allclose(array(sample['response']),expected,atol=2e-15)
        a,b,c,d=(np.array(out['real_matrices'][key]) for key in ('A','B','C','D'))
        np.testing.assert_allclose(c@np.linalg.solve(s*np.eye(3)-a,b)+d,expected,atol=2e-15)
    roundtrip=parse_rom(write_rom(model))
    assert {k:v for k,v in model.items() if k!='source'}=={k:v for k,v in roundtrip.items() if k!='source'}
    assert model['source']==text


def test_real_pole_phase_normalization_does_not_change_residues():
    model=parse_rom(mechanical_text());phase=np.exp(.7j)
    for key in ['C','V']:
        value=array(model['matrices'][key]);value[:,1]*=phase
        model['matrices'][key]=dict(real=value.real.tolist(),imag=value.imag.tolist())
    value=array(model['matrices']['B']);value[1]/=phase
    model['matrices']['B']=dict(real=value.real.tolist(),imag=value.imag.tolist())
    a,b,c,d=(np.array(real_rom(model)[key]) for key in ['A','B','C','D'])
    assert (c@np.linalg.solve(3j*np.eye(3)-a,b)+d)[3,1]==pytest.approx(2/(4+3j),abs=1e-14)


def test_fortran_exponents_crlf_unknown_labels_and_units_are_preserved():
    text=re.sub(r'(?<=\d)e([+-]\d+)',r'D\1',mechanical_text()).replace('custom','widgets').replace('1/s','1/min')
    # Compact three-digit exponent, with no E, is also legal Fortran output.
    text=text.replace('1.00000000000000000D+00','1.00000000000000000+000').replace('\n','\r\n')
    model=parse_rom('\ufeff'+text)
    assert model['time_unit']=='min' and model['outputs'][-1]['unit']=='widgets'
    assert model['state_names']==['q','v','z']
    assert model['source'].startswith('\ufeff')
    assert rom_response(model,[1])['converged']


def test_input_coefficient_and_pole_time_units_are_reconciled_without_changing_printed_data():
    original=parse_rom(mechanical_text());model=deepcopy(original);model['time_unit']='min'
    for mode in model['modes']:mode['eigenvalue']=(np.array(mode['eigenvalue'])*60).tolist()
    before=deepcopy(model['matrices'])
    actual=rom_response(model,[180]);expected=rom_response(original,[3])
    np.testing.assert_allclose(array(actual['samples'][0]['response']),array(expected['samples'][0]['response']),atol=1e-15)
    assert model['matrices']==before and actual['real_matrices']['time_unit']=='min'
    model['time_unit']='unknown_clock'
    with pytest.raises(AnalysisError,match='Cannot convert different'):real_rom(model)


@pytest.mark.parametrize('edit,match',[
    (lambda s:s.replace('# Mode: 8','# Mode: 3'),'Duplicate mode'),
    (lambda s:s.replace('# Eigenvalue:', '# Lost:'),'Incomplete ROM mode'),
    (lambda s:s.replace('d(zdot 3)','d(zdot 8)',1),'mode index'),
    (lambda s:s.replace('d(z 8)','d(z 3)',1),'mode index'),
    (lambda s:s.replace(' / d(Peng_02)',' / d(Other)',1),'variable sets|direct matrix'),
    (lambda s:s.rsplit('\n',2)[0]+'\n','direct-matrix output'),
    (lambda s:s.replace('1 / s =','1 / hr =',1),'units differ'),
    (lambda s:s.replace('custom = d( filter value [1] ) / d(Peng_02)','other = d( filter value [1] ) / d(Peng_02)'),'output labels or units'),
    (lambda s:s.replace('5.00000000000000000e-01','1e999',1),'finite'),
    (lambda s:s.replace('5.00000000000000000e-01','********',1),'numeric columns'),
    (lambda s:s.replace('# Column for forcing variable: Peng_02','# Column for forcing variable: Flap_01'),'Duplicate direct'),
    (lambda s:s.replace('# Control variable influence-matrix row 8','# Control variable influence-matrix row 3'),'wrong mode'),
])
def test_malformed_or_incomplete_tables_are_not_silently_accepted(edit,match):
    with pytest.raises(AnalysisError,match=match):parse_rom(edit(mechanical_text()))


def test_empty_selected_eigenvector_and_empty_input_output_tables():
    text='# Autonomous\n# Mode: 1\n# Eigenvalue: -2 0 1/s\n# Eigenvector...\n# Control variable influence-matrix row 1\n# Output variable dependence-matrix column 1\n# Output-variable dependence-matrix D + QVW*B\n'
    model=parse_rom(text);out=rom_response(model,[0,1])
    assert out['real_matrices']['A']==[[-2.]] and out['real_matrices']['B']==[[]]
    assert out['real_matrices']['C']==[] and out['real_matrices']['V']==[]
    assert parse_rom(write_rom(model))['matrices']==model['matrices']


def test_complex_direct_terms_and_double_counted_conjugates_are_explicit_errors():
    model=parse_rom(mechanical_text());model['matrices']['D']['imag'][0][0]=.1
    with pytest.raises(AnalysisError,match='direct matrix is complex'):real_rom(model)
    model=parse_rom(mechanical_text());model['modes'][1]['eigenvalue']=[model['modes'][0]['eigenvalue'][0],-model['modes'][0]['eigenvalue'][1]]
    with pytest.raises(AnalysisError,match='both conjugate signs'):real_rom(model)


def test_poles_create_gaps_and_time_scaling_does_not_change_response():
    original=parse_rom(mechanical_text())
    for factor in (1e-10,1e10):
        model=deepcopy(original)
        for mode in model['modes']:mode['eigenvalue']=(np.array(mode['eigenvalue'])*factor).tolist()
        for part in ('real','imag'):model['matrices']['B'][part]=(np.array(model['matrices']['B'][part])*factor).tolist()
        np.testing.assert_allclose(array(rom_response(model,[3*factor])['samples'][0]['response']),array(rom_response(original,[3])['samples'][0]['response']),atol=1e-15)
    model=deepcopy(original);model['modes'][0]['eigenvalue']=[0,2]
    out=rom_response(model,[1,2,3]);assert [s['converged'] for s in out['samples']]==[True,False,True]


@pytest.fixture(scope='module')
def generated():
    source=Path('examples/instrumented-oscillator.asw').read_text().replace('L 1 m','L 2 m').replace('T 1 s','T 2 s').replace('F 1 N','F 3 N')
    model=parse_asw(source)
    result=solve_reduced_model(model,FlightCondition(speed=10,alpha=0,mach=0),4,gravity=[0,0,0],count=2,
        outputs=['RY[2]','UY[2]','Ay[2]'],frequencies=[0,2,20])
    return model,result


def test_export_si_units_conjugate_normalization_and_direct_acceleration(generated):
    model,result=generated
    text=export_rom(result,model.units,model.name);parsed=parse_rom(text);out=rom_response(parsed,[0,1,10])
    assert parsed['time_unit']=='s' and parsed['inputs'][0]['name']=='Peng_01'
    assert parsed['inputs'][0]['unit']=='file engine setting'
    assert [o['unit'] for o in parsed['outputs']]==['m','m/s','m/s^2']
    for sample in out['samples']:
        # These declarations describe m=12 kg,c=30 Ns/m,k=750 N/m and
        # engine gain=3 N/setting; this reference is assembled in SI.
        s=1j*sample['omega'];expected=3*np.array([1,s,s*s])/(12*s*s+30*s+750)
        np.testing.assert_allclose(array(sample['response'])[:,0],expected,rtol=2e-8,atol=1e-9)
    bridge=json.loads(run_json(json.dumps(dict(action='rom_import',text=text,frequencies=[0,10]))))
    assert bridge['model']['name']==model.name and bridge['converged']


def test_export_does_not_discard_nonzero_derivative_input_or_guess_units(generated):
    model,result=generated;modified=deepcopy(result);modified['matrices']['D_rate'][2][0]=.1
    with pytest.raises(AnalysisError,match='D_rate'):export_rom(modified,model.units)
    units=UnitSystem(dict(L=(1.,'furlong'),T=(1.,'s'),F=(1.,'N')))
    with pytest.raises(ValueError,match='Unknown SI conversion'):export_rom(result,units)


def test_custom_command_input_is_scaled_to_si_and_not_renamed_as_a_legacy_actuator(generated):
    model,result=generated;modified=deepcopy(result)
    modified['inputs'][0].update(name='command.RY[2]',kind='command',unit='input L')
    baseline=rom_response(parse_rom(export_rom(result,model.units)),[3])
    custom=rom_response(parse_rom(export_rom(modified,model.units)),[3])
    assert custom['model']['inputs'][0]['name']=='command.RY[2]' and custom['model']['inputs'][0]['unit']=='m'
    np.testing.assert_allclose(array(custom['samples'][0]['response']),array(baseline['samples'][0]['response'])/2,atol=1e-15)
