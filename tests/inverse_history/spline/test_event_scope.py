"""Version 3 planning permits transitions; physical completion still owns them."""
from copy import deepcopy
import pytest
from openswing.time_saved_history import validate_scope,scope_record,require_continuation,SCOPE_KEY
from openswing.aero import AnalysisError
from test_scope import legacy,forcing

@pytest.mark.parametrize('source,duration',[
    ('time velocity_earth.y\n0 0\n.04 .024\n.04 .024\n1 .6',.04),
    ('time velocity_earth.y\n0 0\n.04 .024\n.04 .025\n1 .6',.04),
    ('time velocity_earth.y\n0 0\n.04 0',.04),
    ('time velocity_earth.y\n0 0\n.04 .024',1.),
])
def test_v3_allows_planning_and_does_not_claim_physical_compatibility(source,duration):
    model,record=legacy();setup=record['context']['setup']
    setup[SCOPE_KEY]=scope_record(validate_scope(setup),version=3)
    before=deepcopy(setup)
    replacement=deepcopy(setup);replacement['forcing']=source
    require_continuation(setup,forcing(model,replacement),.02,duration)
    assert setup==before

@pytest.mark.parametrize('version',[1,2])
def test_old_scope_still_refuses_replacement_even_when_it_is_physically_compatible(version):
    model,record=legacy();setup=record['context']['setup']
    setup[SCOPE_KEY]=scope_record(validate_scope(setup),version=version)
    replacement=deepcopy(setup);replacement['forcing']='time velocity_earth.y\n0 0\n1 .7'
    with pytest.raises(AnalysisError,match='cannot replace'):
        require_continuation(setup,forcing(model,replacement),.02,.04)
