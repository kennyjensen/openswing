"""Finite rotations, main-wing errors and fine-only states must be checked."""
import importlib.util
import math
from pathlib import Path
import pytest

spec=importlib.util.spec_from_file_location('pm2_fields',Path(__file__).resolve().parents[1]/'scripts/isae_pm2_nodal_fields.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


def result(stations):
    nodes=[];positions=[];rotations=[];jig=[]
    for beam in (1,2):
        for t in stations:
            base=[0.,t,0.];p=[0.,t,.001*t if beam==1 else .1*t]
            theta=(.01 if beam==1 else math.pi/2)*t
            q=[[1.,0.,0.],[0.,math.cos(theta),-math.sin(theta)],[0.,math.sin(theta),math.cos(theta)]]
            nodes.append(dict(index=len(nodes),beam=beam,t=t,jig_position=base,position=p,rotation=q))
            positions.append(p);rotations.append([theta,0.,0.]);jig.append(base)
    return dict(converged=True,continuation_status='complete',nodes=nodes,
        equilibrium_state=dict(positions=positions,rotations=rotations,identity=dict(nodes=jig)))


def test_large_finite_rotation_uses_exact_geodesic():
    c,f=result([0.,1.]),result([0.,.5,1.])
    theta=math.pi/2-.002
    c['nodes'][-1]['rotation']=[[1.,0.,0.],[0.,math.cos(theta),-math.sin(theta)],[0.,math.sin(theta),math.cos(theta)]]
    c['equilibrium_state']['rotations'][-1]=[theta,0.,0.]
    report=module.compare(c,f);rotation=report['checks'][-1]
    assert rotation['maximum_absolute_change']==pytest.approx(.002)
    assert not rotation['passed'] and report['passed']==3


def test_large_tip_deflection_cannot_hide_main_wing_error():
    c,f=result([0.,1.]),result([0.,.5,1.])
    c['nodes'][1]['position'][2]+=.000002
    report=module.compare(c,f);row=report['checks'][0]
    assert row['fine_scale']==.001 and row['maximum_percent']==pytest.approx(.2)
    assert not row['passed']


def test_identical_fields_pass_without_claiming_all_fields():
    report=module.compare(result([0.,1.]),result([0.,.5,1.]))
    assert report['passed']==report['required']==4
    assert not report['all_field_accuracy_established'] and report['native_values_added']==0


@pytest.mark.parametrize('kind',['nonfinite','reflection','nonorthogonal','state_mismatch','missing_station','incomplete'])
def test_corrupt_mesh_or_fine_only_state_is_rejected(kind):
    c,f=result([0.,1.]),result([0.,.5,1.]);node=f['nodes'][1]
    if kind=='nonfinite':node['position'][0]=float('nan')
    elif kind=='reflection':node['rotation']=[[-1.,0.,0.],[0.,1.,0.],[0.,0.,1.]]
    elif kind=='nonorthogonal':node['rotation'][0][0]=2.
    elif kind=='state_mismatch':f['equilibrium_state']['rotations'][1]=[0.,0.,0.]
    elif kind=='missing_station':f['nodes'][2]['t']=.9
    elif kind=='incomplete':f['converged']=False
    with pytest.raises(ValueError):module.compare(c,f)
