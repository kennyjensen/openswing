"""Actual public controller/inverse setup and independently soluble mechanics."""
from pathlib import Path
import json
import os
import numpy as np
import pytest
from openswing.asw import parse_asw
from openswing.aero import AnalysisError, FlightCondition
from openswing.time_integration import solve_time

B = Path(__file__).resolve().parents[1]
TABLE = 'time velocity_earth.y +Ay\n0 0 .1\n1 .4 .1'
ROW = dict(variable='power.1',quantity='velocity_earth.y',target=0.)
CONTROL = dict(outputs=[dict(actuator='E2', expression="command('E2')+.5*error('Ay')+2*integral('Ay')+state('held')+.25*error('Ax')")],
    commands={'Ax':-.2},initial_integrals={'Ay':.03},
    states=[dict(name='held',initial=.2,scale=1.,unit='N',rate='.1')])

def model():
    m = parse_asw((B/'inputs/body.asw').read_text())
    second = m.records['engine'][0].copy();second[0]=2;m.records['engine'].append(second)
    return m

def settings(**changes):
    args = dict(condition=FlightCondition(speed=10.,alpha=0.,mach=0.,powers={2:.1}),
        panels=4,duration=.02,dt=.02,order=5,frame='mixed',gravity=[0.,0.,0.],
        load_targets={'force.y':0.},actuator_constraints=[ROW.copy()],forcing=TABLE,controller=CONTROL)
    args.update(changes);return args

def test_competing_actuator_ownership_remains_rejected():
    controller={'outputs':[{'actuator':'E1','expression':'0'}]}
    with pytest.raises(AnalysisError,match='both a time target and a controller'):
        solve_time(model(),**settings(controller=controller,forcing=''))

def test_controller_cannot_project_incompatible_initial_motion():
    with pytest.raises(AnalysisError,match='inconsistent with the prescribed initial frame state'):
        solve_time(model(),**settings(condition=FlightCondition(speed=10.,alpha=0.,beta=5.,mach=0.,powers={2:.1})))

def test_controller_cannot_silently_initialize_across_cutoff():
    with pytest.raises(AnalysisError,match='forcing cutoff'):
        solve_time(model(),**settings(forcing='time velocity_earth.y +Ay\n-1 -.4 .1\n0 0 .1'))
