"""Check the captured app request through the native JSON bridge, without solving."""
import argparse
from pathlib import Path
from daedalus_bounded_job import run
from check_daedalus_load_sensitivity import ROOT,read

STUDY=ROOT/'artifacts/daedalus-level-flight-case-20261114'
REQUEST=STUDY/'app-bode-request.json'


def check(folder,args):
    import json
    import math
    from unittest.mock import patch
    from openswing.bridge import dispatch
    from openswing.circulation import mode_settings
    from openswing.discretization import normalize
    from openswing.time_state import condition_data,read_condition
    request=read(REQUEST)
    project=read(ROOT/'examples/dae-level-flight-project.json')
    config=next(c['configuration'] for c in project['cases'] if c['id']=='dae-level-bode')
    seed=config['equilibrium']['state'];calls=[]
    before=json.dumps(request,sort_keys=True)

    def boundary(model,condition,panels,**options):
        calls.append(True)
        assert model.beam_interpolation==config['numerics']['beam_interpolation']
        assert sorted(model.controls)==[2,3] and sorted(model.engine_controls)==[1]
        assert panels==normalize(config['mesh'],model)
        observed=condition_data(condition)
        expected=condition_data(read_condition(seed['launch']['condition']))
        for value in (observed,expected):
            modes=mode_settings(value['circulation_modes'])
            assert set(modes)<={b.index for b in model.beams if b.lifting}
            # CirculationBasis treats explicit zero and omitted counts equally.
            value['circulation_modes']={k:v for k,v in modes.items() if v}
        assert observed==expected
        assert options['structural_operator']==config['numerics']['structural_operator']
        assert options['frame']=='free' and options['initial_state']==seed
        assert options['inputs']==['control.2','control.3','power.1']
        assert options['matrices'] is False
        assert len(options['frequencies'])==41
        for index,hz in [(0,.1),(20,1),(40,10)]:
            assert abs(options['frequencies'][index]/(2*math.pi)-hz)<1e-14
        return dict(boundary_checked=True)

    # Stop precisely before FrequencyAnalysis builds or solves any matrices.
    with patch('openswing.frequency_sweep.start',side_effect=boundary):
        result=dispatch(request,_copy_frequency_result=False)
    assert calls==[True] and result['boundary_checked']
    assert result['numerics']==config['numerics']
    assert json.dumps(request,sort_keys=True)==before
    return dict(native_policy_accepted=True,request_unchanged=True,
        parsed_control_ids=[2,3],parsed_engine_ids=[1],
        same_physical_condition_as_checked_trim=True,same_saved_equilibrium=True,
        circulation_qualification='App has explicit zero mode counts; saved trim omits them. Both select the same pointwise CirculationBasis.',
        same_normalized_mesh=True,frame='free',frequency_count=41,
        frequency_hz_endpoints=[.1,10],includes_one_hz=True,
        qualification='Actual JSON dispatch, numerical policy, ASW parser, mesh normalization and FlightCondition conversion; retained-frequency solver replaced at its entry. No equilibrium, matrices, frequency solve, browser or WASM run.')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--tag',required=True)
    args=vars(parser.parse_args())
    inputs=[REQUEST,ROOT/'examples/dae-level-flight-project.json',ROOT/'web/main.js',
        ROOT/'tests/daedalus-request.test.mjs',ROOT/'docs/validation/ISAE_STATUS.md',
        *sorted((ROOT/'openswing').glob('*.py'))]
    run(STUDY,args['tag'],inputs,check,args,__file__)
