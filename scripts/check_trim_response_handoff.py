"""Check UI trim-to-response requests at the native bridge, without solving."""
import argparse
from daedalus_bounded_job import run
from check_daedalus_load_sensitivity import ROOT, read

STUDY = ROOT/'artifacts/trim-response-handoff-20261114'


def check(folder, args):
    import json
    from unittest.mock import patch
    from openswing.bridge import dispatch
    from openswing.circulation import mode_settings
    from openswing.discretization import normalize
    from openswing.time_state import condition_data, read_condition

    project = read(ROOT/'examples/dae-level-flight-project.json')
    config = next(c['configuration'] for c in project['cases'] if c['id']=='dae-level-bode')
    seed = config['equilibrium']['state']
    checked = []

    def model_check(model):
        assert model.beam_interpolation == config['numerics']['beam_interpolation']
        assert sorted(model.controls) == [2, 3]
        assert sorted(model.engine_controls) == [1]

    def response_boundary(model, condition, panels, **options):
        model_check(model)
        assert panels == normalize(config['mesh'], model)
        observed = condition_data(condition)
        expected = condition_data(read_condition(seed['launch']['condition']))
        for value in (observed, expected):
            modes = mode_settings(value['circulation_modes'])
            assert set(modes) <= {b.index for b in model.beams if b.lifting}
            value['circulation_modes'] = {k:v for k,v in modes.items() if v}
        assert observed == expected
        assert options['structural_operator'] == config['numerics']['structural_operator']
        assert options['frame'] == 'free' and options['initial_state'] == seed
        assert not options.get('operating_constraints')
        checked.append(True)
        return {'boundary_checked': True}

    def launch_boundary(model, saved, **options):
        model_check(model)
        assert saved == seed
        assert normalize(saved['launch']['panels'], model) == normalize(config['mesh'], model)
        assert options['frame'] == 'free'
        assert options['forcing'] == ''
        assert not options.get('actuator_constraints')
        checked.append(True)
        return {'boundary_checked': True}

    results = {}
    for mode, target, boundary in [
        ('frequency', 'openswing.frequency_sweep.start', response_boundary),
        ('modes', 'openswing.linear_dynamics.solve_modes', response_boundary),
        ('time', 'openswing.time_initialization.launch_time', launch_boundary),
    ]:
        request = read(STUDY/f'{mode}-request.json')
        original = json.dumps(request, sort_keys=True)
        assert request['source'] == config['source']
        assert not request.get('operating_constraints')
        before = len(checked)
        with patch(target, side_effect=boundary):
            result = dispatch(request, _copy_frequency_result=False)
        assert len(checked) == before+1 and result['boundary_checked']
        assert result['numerics'] == config['numerics']
        assert json.dumps(request, sort_keys=True) == original
        results[mode] = {'native_policy_accepted': True, 'saved_equilibrium_preserved': True,
                         'frame': 'free', 'trim_targets_released': True, 'request_unchanged': True}
    return {'branches': results,
            'qualification': 'Completed-trim replay through UI adoption and request construction, then actual native JSON policy/parser/dispatch. Solver entries intercepted before matrix assembly or time initialization. No cold trim, dynamics, browser or WASM solve.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tag', required=True)
    args = vars(parser.parse_args())
    inputs = [*sorted(STUDY.glob('*-request.json')), ROOT/'examples/dae-level-flight-project.json',
              ROOT/'web/main.js', ROOT/'web/steady-flight.js', ROOT/'web/case-settings.js',
              ROOT/'web/numerical-policy.js', ROOT/'tests/daedalus-request.test.mjs',
              *sorted((ROOT/'openswing').glob('*.py'))]
    run(STUDY, args['tag'], inputs, check, args, __file__)
