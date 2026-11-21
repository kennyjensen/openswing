"""A pending AE-2 stage cannot authorize downstream work after a failed receipt."""
from copy import deepcopy

import pytest

from scripts.probe_isae_ae2_incidence_stages import stage_receipt, read, write, pin


def accepted_receipt(tmp_path):
    write(tmp_path/'plan.json', {'cases': ['control']})
    folder = tmp_path/'control/solve'
    terminal = dict(returncode=0, process_reaped=True, supervisor_timeout=False)
    write(folder/'terminal.json', terminal)
    write(folder/'sources-verified.json', dict(all_pins_checked_before_and_after=True,
        plan=pin(tmp_path/'plan.json'), terminal=pin(folder/'terminal.json')))
    return folder, terminal


def test_stage_accepts_only_bound_completed_receipt(tmp_path):
    _, terminal = accepted_receipt(tmp_path)
    assert stage_receipt(tmp_path, 'control', 'solve') == terminal


@pytest.mark.parametrize('change', ['exit', 'unreaped', 'timeout', 'unchecked_sources',
    'changed_plan', 'changed_receipt', 'missing_receipt'])
def test_stage_rejects_failed_or_unbound_evidence(tmp_path, change):
    folder, terminal = accepted_receipt(tmp_path)
    evidence = read(folder/'sources-verified.json')
    if change in ('exit', 'unreaped', 'timeout'):
        key, value = {'exit': ('returncode', -9), 'unreaped': ('process_reaped', False),
            'timeout': ('supervisor_timeout', True)}[change]
        altered = deepcopy(terminal); altered[key] = value
        write(folder/'terminal.json', altered)
        evidence['terminal'] = pin(folder/'terminal.json')
        write(folder/'sources-verified.json', evidence)
    elif change == 'unchecked_sources':
        evidence['all_pins_checked_before_and_after'] = False
        write(folder/'sources-verified.json', evidence)
    elif change == 'changed_plan':
        write(tmp_path/'plan.json', {'cases': ['another_control']})
    elif change == 'changed_receipt':
        write(folder/'terminal.json', {**terminal, 'later_rewrite': True})
    else:
        (folder/'terminal.json').unlink()
    with pytest.raises((AssertionError, FileNotFoundError)):
        stage_receipt(tmp_path, 'control', 'solve')
