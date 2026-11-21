from dataclasses import replace
from pathlib import Path
import runpy
import numpy as np
import pytest
from openswing.aero import FlightCondition, evaluate_aerodynamics, solve_rigid
from openswing.asw import parse_asw
from openswing.geometry import model_meshes
from openswing.network import StaticNetwork, network_result
from test_volume import body_source

STUDY=runpy.run_path(str(Path(__file__).resolve().parents[1]/'scripts/verify-section-outputs.py'))


@pytest.mark.parametrize('spec',[
    dict(kind='rigid',panels=4),
    dict(kind='elliptic_load',panels=8),
    dict(kind='moving',angle=35.,stretch=1.2,panels=4),
    dict(kind='moving',angle=-35.,stretch=1.15,panels=4,frozen=True,lag=False,units=[.3048,2.,4.4482216152605]),
    dict(kind='stationary_history',panels=4)])
def test_independent_normal_load_and_moving_section_references(spec):
    STUDY['compute'](spec)


def test_elastic_incidence_excludes_flap_and_zero_lift_offsets_and_stagnation_is_a_gap():
    source=STUDY['source']({}).replace('Cdf Cm dCMdF1','Cdf Cm dCMdF1 alpha dCLdF1').replace('.02 -.04 .005 ','.02 -.04 .005 4 .1 ')
    model=parse_asw(source);meshes=model_meshes(model,4)
    condition=FlightCondition(speed=30,alpha=0,mach=0,controls={1:3.})
    result=evaluate_aerodynamics(model,condition,meshes,circulation=np.zeros(4))
    assert all(s['da_eff']==0 for s in result['strips'])
    assert all('f_reac' not in s for s in result['strips'])
    stopped=evaluate_aerodynamics(model,replace(condition,gust=dict(type='uniform',velocity=[-30,0,0])),meshes,circulation=np.zeros(4))
    assert all(s['da_eff'] is None for s in stopped['strips'])


def test_gravity_only_changes_reaction_output_even_when_aerodynamic_cache_is_reused():
    model=parse_asw(STUDY['source']({}));net=StaticNetwork(model,4,FlightCondition(alpha=0,mach=0),None,[])
    state=np.zeros(net.size)
    first=network_result(net,state,gravity_override=[0,0,-3])
    cached=net.aero_cached
    second=network_result(net,state,gravity_override=[0,0,-7])
    assert net.aero_cached is cached
    for a,b in zip(first['strips'],second['strips']):
        assert a['f_reac']==pytest.approx(-7.5)
        assert b['f_reac']==pytest.approx(-17.5)
    assert all('f_reac' not in s for s in cached['strips'])


def test_body_only_strips_have_no_invented_lifting_section_diagnostics():
    result=solve_rigid(parse_asw(body_source()),FlightCondition(alpha=0,mach=0),4)
    for row in result['strips']:
        assert all(key not in row for key in ['cm','f_aero','f_reac','da_eff'])
