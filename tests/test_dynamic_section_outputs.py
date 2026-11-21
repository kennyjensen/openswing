"""Complex section outputs: analytic references and undefined-state boundaries."""
from pathlib import Path
import runpy
import numpy as np
import pytest
from openswing.asw import parse_asw
from openswing.aero import FlightCondition
from openswing.network import StaticNetwork
from openswing.linear_dynamics import DynamicSystem, output_perturbation
from test_volume import body_source

STUDY=runpy.run_path(str(Path(__file__).resolve().parents[1]/'scripts/verify-dynamic-section-outputs.py'))

@pytest.mark.parametrize('spec',[
    dict(kind='loaded',angle=70,stretch=1.25,panels=4),
    dict(kind='loaded',angle=-35,frozen=True,lag=False,units=[.3048,2,4.4482216152605]),
    dict(kind='frequency',panels=4),dict(kind='frequency',panels=4,lag=False),
    dict(kind='modes',panels=4)])
def test_independent_complex_section_references(spec):
    STUDY['compute'](spec)


def test_stagnant_base_incidence_remains_undefined_in_nonzero_complex_stencil():
    c=FlightCondition(speed=30,alpha=0,mach=0,gust=dict(type='uniform',velocity=[-30,0,0]))
    n=StaticNetwork(parse_asw(STUDY['SOURCE']({})),4,c,None,[])
    system=DynamicSystem(n,np.zeros(n.size));v=np.zeros(system.size,complex)
    v[:6*n.nn].reshape(n.nn,6)[:,4]=.7+.2j
    v[n.gamma_start:n.operating_start]=(.3+.4j)/n.gamma_scale
    output=output_perturbation(system,v,1j*v)
    assert all(s['da_eff'] is None for s in output['strips'])
    assert all(s['f_reac'] is not None for s in output['strips'])
    # Repeated recovery uses the same base validity mask, not the last stencil.
    again=output_perturbation(system,2*v,2j*v)
    assert all(s['da_eff'] is None for s in again['strips'])


@pytest.mark.parametrize('vacuum',[False,True])
def test_body_and_vacuum_outputs_do_not_invent_lifting_section_values(vacuum):
    n=StaticNetwork(parse_asw(body_source()),4,None if vacuum else FlightCondition(alpha=0,mach=0),[0,0,0],[])
    system=DynamicSystem(n,np.zeros(n.size));v=np.zeros(system.size,complex)
    output=output_perturbation(system,v,v)
    for row in output['strips']:
        assert all(row[key] is None for key in STUDY['KEYS'])
