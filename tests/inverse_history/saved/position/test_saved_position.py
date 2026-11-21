import json
from pathlib import Path
from copy import deepcopy
import pytest
root=Path(__file__).parent
from openswing.asw import parse_asw,AswError
from openswing.aero import AnalysisError
from openswing.time_initialization import launch_time
from openswing.time_state import checkpoint,restore_checkpoint,resume_time
from openswing.time_saved_history import SCOPE_KEY,SCOPE_KINDS,validate_scope

def inputs():
 return parse_asw((root.parent/'inputs/both-root.asw').read_text()),json.loads((root.parent/'inputs/saved-equilibrium.json').read_text())

def cp():return json.loads((root/'initial-checkpoint.json').read_text())

@pytest.mark.parametrize('case',['position','velocity','default'])
def test_incompatible_launch_fails_before_derivative_completion(monkeypatch,case):
 import openswing.time_transition_initial as helper
 model,saved=inputs();old=deepcopy(saved)
 forcing={'position':'time RY\n-1 .01\n0 .01\n1 .01',
          'velocity':'time RY\n-1 -.1\n0 0\n1 .1',
          'default':'time RY\n-1 .2\n0 0\n1 .2'}[case]
 def forbidden(*a,**k):raise AssertionError('Incompatibility reached derivative completion')
 monkeypatch.setattr(helper,'consistent_initial',forbidden)
 with pytest.raises(AnalysisError,match='(retained physical|position/velocity|saved default target)'):
  launch_time(model,saved,duration=.02,dt=.02,order=5,frame='mixed',load_targets={'force.y':0.},
    actuator_constraints=[dict(variable='power.1',quantity='position_earth.y',target=.01 if case=='default' else 0.)],forcing=forcing)
 assert saved==old

@pytest.mark.parametrize('version',[1,2,3])
def test_legacy_scope_cannot_be_relabeled_for_position(version):
 saved=cp();setup=saved['context']['setup'];setup[SCOPE_KEY].update(version=version,kind=SCOPE_KINDS[version])
 with pytest.raises(AnalysisError,match='matching its recorded scope'):validate_scope(setup)

def test_position_scope_cannot_be_relabeled_for_velocity():
 setup=cp()['context']['setup'];setup['actuator_constraints'][0]['quantity']='velocity_earth.y'
 setup[SCOPE_KEY]['quantity']='velocity_earth.y'
 with pytest.raises(AnalysisError,match='matching its recorded scope'):validate_scope(setup)

@pytest.mark.parametrize('case',['no_scope','sample','kind','quantity','no_record'])
def test_owned_checkpoint_tampering_rejected(case):
 model,_=inputs();saved=cp()
 if case=='no_scope':
  del saved['context']['setup'][SCOPE_KEY]
  del saved['accepted_method']['accepted_inputs']['setup'][SCOPE_KEY]
 elif case=='sample':saved['state']['position_history']['acceleration'][1]+=.01
 elif case=='kind':saved['context']['setup'][SCOPE_KEY]['kind']=SCOPE_KINDS[3]
 elif case=='quantity':saved['context']['setup']['actuator_constraints'][0]['quantity']='position_earth.z'
 else:del saved['accepted_method']
 with pytest.raises((AnalysisError,AswError)):restore_checkpoint(model,saved)

def test_initial_checkpoint_json_roundtrip_remains_owned():
 model,_=inputs();saved=cp();old=deepcopy(saved)
 restored=restore_checkpoint(model,json.loads(json.dumps(saved)))
 assert saved==old
 assert restored[-1]['acceptance_validation']['level']=='initial_physical_only'

@pytest.mark.parametrize('order',[1,2,5])
def test_public_continuation_matches_independent_spring_equations(order):
 import importlib.util
 source=Path(__file__).resolve().parents[4]/'scripts/verify-saved-position.py'
 spec=importlib.util.spec_from_file_location('saved_position_reference',source)
 reference=importlib.util.module_from_spec(spec);spec.loader.exec_module(reference)
 model,_=inputs();saved=cp();old=deepcopy(saved)
 result=resume_time(model,saved,duration=.02,dt=.01,order=order)
 assert saved==old
 assert reference.verify(result)['status']=='PASS'
 for i in range(len(result['snapshots'])):restore_checkpoint(model,checkpoint(result,i))
 assert result['restart_context']['setup'][SCOPE_KEY]['version']==4
