"""Actual public cold setup; intercept only the prepared-state march handoff."""
from dataclasses import asdict
from pathlib import Path
import json
import math
import os
import numpy as np
import pytest
from openswing.aero import AnalysisError, FlightCondition
from openswing.asw import parse_asw
from openswing.forcing import TimeForcing
from openswing.operating import time_operating_constraints
from openswing.time_cold_initial import cold_history_targets
import openswing.time_integration as time_api


BASE = Path(__file__).parents[1]
TABLE = 'time velocity_earth.y\n0 0\n1 .4'
ROW = dict(variable='power.1', quantity='velocity_earth.y', target=0.)


def model():
    return parse_asw((BASE/'inputs/body.asw').read_text())


def setup(**kwargs):
    return dict(condition=FlightCondition(speed=10.,alpha=0.,mach=0.), panels=4,
                duration=.02,dt=.02,frame='mixed',gravity=[0.,0.,0.],
                load_targets={'force.y':0.},actuator_constraints=[ROW.copy()],forcing=TABLE, **kwargs)


