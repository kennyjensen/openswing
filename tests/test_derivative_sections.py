"""Signed local section sensitivities, independently balanced and re-solved."""
from dataclasses import replace
from pathlib import Path
import json
import numpy as np
import pytest
from openswing.asw import parse_asw
from openswing.aero import FlightCondition
from openswing.network import solve_static
from openswing.derivatives import SECTION_OUTPUTS


def spring_result(panels=4, source=None):
    source=Path('examples/axial-torsion.asw').read_text() if source is None else source
    return solve_static(parse_asw(source),FlightCondition(speed=10,alpha=0,mach=0,powers={1:.2}),
        panels=panels,gravity=[0,0,0],tolerance=1e-10,derivatives=dict(parameters=['power.1']))


@pytest.mark.parametrize('panels',[4,8,12])
def test_axial_torque_derivatives_match_independent_section_balance(panels):
    result=spring_result(panels);d=result['derivatives'];m=d['matrices']
    # End-force and end-torque balance, axial compliance, torsion compliance,
    # and Bredt's closed-shell shear law, independently of recovered outputs.
    expected={'section_force_local':[0,3,0], 'section_moment_local':[0,2,0],
              'section_moment_axes':[0,2,0], 'section_strain':[0,.003,0],
              'section_curvature':[0,.004,0], 'section_axial_strain':.003,
              'shell_axial_strain':.003, 'shell_shear_stress':250.}
    for key,value in expected.items():
        actual=np.asarray(m[key])[...,0]
        np.testing.assert_allclose(actual,np.broadcast_to(value,actual.shape),rtol=2e-7,atol=2e-8)
        assert all(d['section_output_fields'][key]['available'])
    assert d['section_output_fields']['shell_shear_stress']['unit']=='input F / L^2'
    assert all(row['t0']<row['t']<row['t1'] for row in d['element_order'])
    assert d['section_output_fields']['shell_axial_strain']['components'] is None
    json.dumps(d,allow_nan=False)


@pytest.mark.parametrize('shell_line,replacement,missing',[
    ('t Cshell Nshell Atshell\n0 .1 .2 .004\n2 .1 .2 .004\n','', ['shell_axial_strain','shell_shear_stress']),
    ('t Cshell Nshell Atshell\n0 .1 .2 .004\n2 .1 .2 .004\n','t Cshell Nshell Atshell\n0 .1 .2 0\n2 .1 .2 0\n',['shell_shear_stress']),
])
def test_missing_shell_data_remain_null_instead_of_zero(shell_line,replacement,missing):
    d=spring_result(source=Path('examples/axial-torsion.asw').read_text().replace(shell_line,replacement))['derivatives']
    for key in missing:
        assert d['base_outputs'][key]==[None]*len(d['element_order'])
        assert d['matrices'][key]==[[None]]*len(d['element_order'])
        assert not any(d['section_output_fields'][key]['available'])
    np.testing.assert_allclose(np.array(d['matrices']['section_axial_strain'])[:,0],.003,rtol=2e-7)
    json.dumps(d,allow_nan=False)


def test_large_deformation_local_strain_stress_derivatives_match_resolved_equilibria():
    model=parse_asw(Path('examples/stress-wing.asw').read_text())
    condition=FlightCondition(speed=30,alpha=5,mach=0)
    result=solve_static(model,condition,panels=4,tolerance=1e-10,derivatives=dict(parameters=['alpha']))
    assert result['max_displacement']>.05
    h=2e-4
    plus,minus=[solve_static(model,replace(condition,alpha=5+s*np.rad2deg(h)),panels=4,tolerance=1e-10) for s in (1,-1)]
    for key,(path,*_) in SECTION_OUTPUTS.items():
        def values(result):
            rows=[]
            for element in result['elements']:
                value=element
                for part in path.split('.'):value=value[part]
                rows.append(value)
            return np.array(rows)
        expected=(values(plus)-values(minus))/(2*h)
        np.testing.assert_allclose(np.asarray(result['derivatives']['matrices'][key])[...,0],expected,rtol=4e-5,atol=2e-7)


def test_partial_shell_stress_availability_keeps_element_alignment():
    source=Path('examples/axial-torsion.asw').read_text().replace(
        't Cshell Nshell Atshell\n0 .1 .2 .004\n2 .1 .2 .004',
        't Cshell Nshell\n0 .1 .2\n2 .1 .2\nt Atshell\n0 0\n1 0\n1 .004\n2 .004')
    d=spring_result(source=source)['derivatives']
    assert d['section_output_fields']['shell_shear_stress']['available']==[False,False,True,True]
    assert d['matrices']['shell_shear_stress'][:2]==[[None],[None]]
    np.testing.assert_allclose(np.asarray(d['matrices']['shell_shear_stress'][2:])[:,0],250.,rtol=2e-7)
    json.dumps(d,allow_nan=False)


def test_consistent_length_units_preserve_physical_strain_stress_sensitivity():
    # One input L=.001 m, F=1 N and T=1 s. Dimensional conversion is
    # independently applied to every geometric/stiffness/engine/air input.
    unit=.001
    source=Path('examples/axial-torsion.asw').read_text()
    source=source.replace('L 1 m',f'L {unit} m').replace('9.80665 1.225 340.294',f'{9.80665/unit} {1.225*unit**4} {340.294/unit}')
    source=source.replace('Reference\n2 1 2',f'Reference\n{2/unit**2} {1/unit} {2/unit}')
    source=source.replace('1 0 1 2 0 2 0 0 1 0 3 2 -1 0 0',f'1 0 1 2 0 {2/unit} 0 0 1 0 3 {2/unit} {-1/unit} 0 0')
    source=source.replace('0 0 1000 500\n2 2 1000 500',f'0 0 1000 {500/unit**2}\n2 {2/unit} 1000 {500/unit**2}')
    source=source.replace('0 .1 .2 .004\n2 .1 .2 .004',f'0 {.1/unit} {.2/unit} {.004/unit**3}\n2 {.1/unit} {.2/unit} {.004/unit**3}')
    result=solve_static(parse_asw(source),FlightCondition(speed=10/unit,alpha=0,mach=0,powers={1:.2}),
        panels=4,gravity=[0,0,0],tolerance=1e-10,derivatives=dict(parameters=['power.1']))
    m=result['derivatives']['matrices']
    np.testing.assert_allclose(np.asarray(m['shell_axial_strain'])[:,0],.003,rtol=2e-7)
    np.testing.assert_allclose(np.asarray(m['section_curvature'])[:,1,0]/unit,.004,rtol=2e-7)
    np.testing.assert_allclose(np.asarray(m['shell_shear_stress'])[:,0]*result['structure']['units']['stress_to_pa'],250,rtol=2e-7)
