"""Sensitivity checks for the added rigid-motion and structural-load gates."""
import copy
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from isae_ua1_stall_expanded import physical_row, comparison_fields
from isae_ua1_stall_browser import difference


@pytest.fixture(scope='module')
def fixture():
    sample = json.loads((ROOT/'tests/fixtures/ua1-stall-expanded-state.json').read_text())
    return sample, dict(alpha_deg=9., speed=10.)


@pytest.mark.parametrize('field', ['local_velocity','local_rates','local_acceleration','local_rate_derivative'])
def test_detects_local_motion_even_if_runtime_targets_agree(fixture, field):
    sample, section = fixture
    physical_row(sample, section)
    altered = copy.deepcopy(sample)
    altered[field][0][0] = 3e-8
    with pytest.raises(AssertionError, match='Rigid local motion'):
        physical_row(altered, section)


def test_structural_load_difference_participates(fixture):
    sample, section = fixture
    expected = physical_row(sample, section)
    altered = copy.deepcopy(sample)
    altered['restart']['state']['network']['internal_force'][0][0] += .5*1.225*100*200000*1e-6
    actual = physical_row(altered, section)
    assert 'internal_force_coefficient' in comparison_fields(actual)
    assert difference(actual['internal_force_coefficient'], expected['internal_force_coefficient']) > 2e-8


def test_nonfinite_nodal_state_is_rejected(fixture):
    sample, section = fixture
    altered = copy.deepcopy(sample)
    altered['restart']['state']['network']['positions'][0][0] = float('nan')
    with pytest.raises(AssertionError, match='Nonfinite'):
        physical_row(altered, section)
