"""Versioned smooth-table contract and actual legacy checkpoint compatibility."""
from pathlib import Path
from copy import deepcopy
import json
import numpy as np
import pytest
from openswing.asw import parse_asw
from openswing.aero import AnalysisError
from openswing.forcing import TimeForcing
from openswing.inertia import Motion
from openswing.time_state import read_condition,restore_checkpoint
from openswing.time_saved_history import scope_record,validate_scope,require_continuation,SCOPE_KEY

B=Path(__file__).resolve().parent


def legacy():
    return parse_asw((B.parent/'saved/inputs/both-root.asw').read_text()),json.loads((B/'inputs/legacy-linear-checkpoint.json').read_text())


def forcing(model,setup):
    return TimeForcing(setup['forcing'],model,read_condition(setup['condition']),Motion(**setup['motion']),.08,
        setup['frame'],None,start_time=.02,load_targets=setup['load_targets'],actuator_constraints=setup['actuator_constraints'])


def test_actual_version_one_checkpoint_restores_and_keeps_its_linear_contract():
    model,record=legacy();before=deepcopy(record)
    restored=restore_checkpoint(model,record)
    assert record==before
    assert restored[7]['acceptance_validation']['level']=='recorded_discrete_equations'
    setup=record['context']['setup'];assert setup[SCOPE_KEY]['version']==1
    row=validate_scope(setup,required=True)
    assert scope_record(row,version=1)==setup[SCOPE_KEY]
    require_continuation(setup,forcing(model,setup),.02,.04)
    setup['forcing']='time velocity_earth.y\n0 0\n.5 .3\n1 .6'
    with pytest.raises(AnalysisError,match='Legacy.*two distinct'):
        require_continuation(setup,forcing(model,setup),.02,.04)


def test_new_scope_accepts_curvature_and_an_interior_smooth_knot():
    model,record=legacy();setup=record['context']['setup']
    row=validate_scope(setup)
    setup[SCOPE_KEY]=scope_record(row,version=2)
    assert setup[SCOPE_KEY]['version']==2
    setup['forcing']='time velocity_earth.y\n0 0\n.04 .024\n1 .792'
    table=forcing(model,setup)
    require_continuation(setup,table,.02,.04)
    assert .04 in table.events and .04 not in table.breaks
    # Independently derived natural-spline value and acceleration at the knot.
    assert table.values(.04)['velocity_earth.y']==pytest.approx(.024,abs=1e-15)
    assert table.values(.04,derivative=1)['velocity_earth.y']==pytest.approx(.608,abs=1e-14)
    for derivative in (0,1,2):
        np.testing.assert_allclose(table.values(.04,'left',derivative=derivative)['velocity_earth.y'],
            table.values(.04,'right',derivative=derivative)['velocity_earth.y'],atol=1e-13)


@pytest.mark.parametrize('version,kind',[(True,'single-nonrotating-earth-velocity-linear-v1'),
    (2,'single-nonrotating-earth-velocity-linear-v1'),(1,'single-nonrotating-earth-velocity-spline-v2'),
    (3,'single-nonrotating-earth-velocity-spline-v2'),(2.0,'single-nonrotating-earth-velocity-spline-v2')])
def test_scope_versions_cannot_reinterpret_each_others_records(version,kind):
    _,record=legacy();setup=record['context']['setup']
    setup[SCOPE_KEY].update(version=version,kind=kind)
    with pytest.raises(AnalysisError,match='malformed or unsupported'):validate_scope(setup)


@pytest.mark.parametrize('table',[
    'time velocity_earth.y\n0 0\n.04 .024\n.04 .024\n1 .792',
    'time velocity_earth.y\n0 0\n.04 .024\n.04 .025\n1 .792'])
def test_new_smooth_scope_does_not_silently_cross_slope_or_value_breaks(table):
    model,record=legacy();setup=record['context']['setup']
    setup[SCOPE_KEY]=scope_record(validate_scope(setup),version=2);setup['forcing']=table
    with pytest.raises(AnalysisError,match='distinct increasing'):
        require_continuation(setup,forcing(model,setup),.02,.04)
