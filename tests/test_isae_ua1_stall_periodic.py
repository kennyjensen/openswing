"""Sensitivity checks for repeated-stall inputs, normalization and acceptance."""
from copy import deepcopy
import math
from pathlib import Path
import sys

import numpy as np
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from isae_ua_stall_reference import Section
from isae_ua_stall_production import request as cold_request
from isae_ua1_stall_periodic import request, summarize, checks


def histories(steps=64, perturbation=0.):
    section=Section()
    reference=[]
    for i in range(8*steps+1):
        t=section.period*i/steps;angle=2*math.pi*i/steps
        z,w,a=section.motion(t)
        reference.append(dict(time=t,CL=2.+.7*math.sin(angle)+.08*math.cos(2*angle),
            circulation=5.+1.2*math.sin(angle),circulation_rate=10.*math.cos(angle),
            CDp_fixed=.1+.08*math.sin(angle),section_cl=1.4+.2*math.sin(angle),
            displacement=z,velocity=w,acceleration=a))
    actual=[]
    for row in reference[:4*steps+1]:
        actual.append(dict(**{key:row[key] for key in ('time','CL','CDp_fixed','velocity')},
            position=row['displacement'],residual=1e-12,section_cl=[row['section_cl']]*4,
            circulation=[row['circulation']+perturbation]*4,
            circulation_rate=[row['circulation_rate']+perturbation]*4))
        actual[-1]['CL']+=perturbation;actual[-1]['CDp_fixed']+=perturbation
    return section,actual,dict(rows=reference,initial_circulation=5.)


def test_full_forcing_preserves_first_cycle_and_extends_before_startup():
    section=Section();old=cold_request(section,320);new=request(section,320,4)
    for key in ('source','numerics','panels','condition'):assert new[key]==old[key]
    assert new['time']['dt']==old['time']['dt']
    assert new['time']['duration']==4*section.period
    lines=new['time']['forcing'].splitlines()
    assert lines[:322]==old['time']['forcing'].splitlines()
    assert len(lines)==1282
    for line in lines[1:]:
        t,ax,az=map(float,line.split())
        expected=section.motion(t)[2]*section.heave
        np.testing.assert_allclose([ax,az],expected[[0,2]],rtol=0.,atol=1e-13)


@pytest.mark.parametrize('cycles',[0,1,2.5])
def test_incomplete_cycle_inputs_rejected(cycles):
    with pytest.raises(ValueError):request(Section(),320,cycles)


def test_individual_strip_error_and_constant_lift_offset_are_not_hidden():
    section,rows,reference=histories()
    rows[-10]['circulation'][3]+=.024
    for row in rows:row['CL']+=.014
    result=summarize(section,64,4,rows,reference,64)
    assert result['cycles'][-1]['error_fractions']['circulation']==pytest.approx(.02)
    assert result['cycles'][-1]['mean_lift_error_fraction']>.01


def test_cycle_drift_is_distinct_from_waveform_accuracy():
    section,rows,reference=histories()
    for row in rows[-64:]:row['CDp_fixed']+=.001
    result=summarize(section,64,4,rows,reference,64)
    assert result['cycles'][-1]['change_fractions']['CDp_fixed']>.005


def test_second_order_refinement_passes_but_error_plateau_fails():
    results={}
    for n in (32,64):
        section,rows,reference=histories(n,perturbation=.1/n**2)
        results[str(n)]=summarize(section,n,4,rows,reference,n)
    gates,ratios=checks(results,True,section)
    assert all(gates.values()),gates
    assert all(v==pytest.approx(.25,rel=1e-8) for group in ratios.values() for v in group.values())
    plateau=deepcopy(results)
    plateau['64']['cold_error_fractions']=deepcopy(plateau['32']['cold_error_fractions'])
    assert not checks(plateau,True,section)[0]['refinement']
    assert not checks(results,False,section)[0]['reference']


@pytest.mark.parametrize('corruption',['time','nan'])
def test_wrong_sample_time_and_nonfinite_physics_rejected(corruption):
    section,rows,reference=histories()
    if corruption=='time':rows[100]['time']+=1e-5
    else:rows[100]['circulation'][2]=float('nan')
    with pytest.raises(AssertionError):summarize(section,64,4,rows,reference,64)
